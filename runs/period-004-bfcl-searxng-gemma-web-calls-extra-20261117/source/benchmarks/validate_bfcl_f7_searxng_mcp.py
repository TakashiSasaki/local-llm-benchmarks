"""Offline regression controls for the BFCL search and page adapters."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bfcl_f7_searxng_mcp import (BackendStop, CallBudget, PublicPageFetcher, SearxngMCP,
                               WebSearchAPI, public_address)

TOOL = {'name': 'searxng_search', 'inputSchema': {'properties': {
    key: {} for key in ('query', 'language', 'engines', 'max_results', 'force_refresh', 'organic_only')}}}
ROW = {'title': 'example', 'url': 'https://example.org/', 'content': 'snippet', 'engine': 'duckduckgo web'}


class Reply:
    def __init__(self, data=None, status=200, headers=None):
        self.data = json.dumps(data).encode()
        self.status = self.status_code = status
        self.headers = headers or {'Content-Type': 'application/json'}
        self.raw = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def read(self, amount, decode_content):
        return self.data[:amount]


def jsonrpc(request_id, result):
    return Reply({'jsonrpc': '2.0', 'id': request_id, 'result': result})


class SearchTests(unittest.TestCase):
    def test_observed_json_transport_and_budget(self):
        events = []
        client = SearxngMCP('https://fixture.example/mcp', CallBudget(1, 'search'), events.append, 'test-token')
        self.addCleanup(client.close)
        response = {'structuredContent': {'result': [ROW],
                    'search_info': {'selected_engines': ['duckduckgo web'], 'observed_engines': ['duckduckgo web'],
                                    'language_applied': 'all'}}}
        client.http.post = Mock(side_effect=[
            jsonrpc(1, {'protocolVersion': '2025-11-25'}), Reply(status=202),
            jsonrpc(2, {'tools': [TOOL]}), jsonrpc(3, response)])
        self.assertEqual(client.search('fixture', 10, 'all'), [ROW])
        methods = [call.kwargs['json']['method'] for call in client.http.post.call_args_list]
        self.assertEqual(methods, ['initialize', 'notifications/initialized', 'tools/list', 'tools/call'])
        params = client.http.post.call_args.kwargs['json']['params']
        self.assertEqual(params['arguments'], {'query': 'fixture', 'max_results': 10, 'language': 'all',
                                               'engines': ['duckduckgo web'], 'force_refresh': False,
                                               'organic_only': True})
        self.assertEqual(events[-1]['response']['search_info']['language_applied'], 'all')
        self.assertNotIn('test-token', json.dumps(events))
        with self.assertRaisesRegex(BackendStop, 'budget_exhausted'):
            client.search('fixture again', 10, 'all')
        self.assertEqual(client.http.post.call_count, 4)

    def test_does_not_accept_results_from_the_old_engine(self):
        client = SearxngMCP('https://fixture.example/mcp', CallBudget(1, 'search'), lambda row: None)
        self.addCleanup(client.close)
        client.connected = True
        result = {'structuredContent': {'result': [{**ROW, 'engine': 'duckduckgo'}],
                  'search_info': {'selected_engines': ['duckduckgo web'], 'observed_engines': ['duckduckgo']}}}
        client.http.post = Mock(return_value=jsonrpc(1, result))
        with self.assertRaisesRegex(BackendStop, 'mcp_unexpected_search_engine'):
            client.search('fixture', 10, 'all')
        self.assertEqual(client.http.post.call_count, 1)

    def test_rate_limit_is_single_attempt_and_stops(self):
        client = SearxngMCP('https://fixture.example/mcp', CallBudget(3, 'search'), lambda row: None)
        self.addCleanup(client.close)
        client.connected = True
        client.http.post = Mock(return_value=Reply(status=429))
        with self.assertRaisesRegex(BackendStop, 'mcp_http_429'):
            client.search('fixture', 10, 'all')
        self.assertEqual(client.http.post.call_count, 1)
        self.assertEqual(client.budget.used, 1)

    def test_distinguishes_tool_error_from_missing_structured_output(self):
        for result, code in (
            ({'isError': True, 'content': [{'type': 'text', 'text': 'fixture error'}]},
             'mcp_search_tool_reported_error'),
            ({'content': [{'type': 'text', 'text': 'fixture response'}]},
             'mcp_search_structured_content_missing'),
        ):
            with self.subTest(code=code):
                events = []
                diagnostics = []
                client = SearxngMCP('https://fixture.example/mcp', CallBudget(1, 'search'),
                                    events.append, record_tool_error=diagnostics.append)
                self.addCleanup(client.close)
                client.connected = True
                client.http.post = Mock(return_value=jsonrpc(1, result))
                with self.assertRaisesRegex(BackendStop, code):
                    client.search('fixture', 10, 'all')
                self.assertEqual(client.http.post.call_count, 1)
                self.assertEqual(diagnostics, [result])
                self.assertEqual(events[0]['error'], code)
                self.assertNotIn('content', events[0])

    def test_snippet_exclusion_and_input_translation(self):
        backend = Mock()
        backend.search.return_value = [{**ROW, 'engine': 'answer'}, ROW]
        tool = WebSearchAPI()
        tool.search_backend = backend
        tool._load_scenario({'show_snippet': False})
        self.assertEqual(tool.search_engine_query('fixture', 1, 'jp-jp'),
                         [{'title': 'example', 'href': 'https://example.org/'}])
        backend.search.assert_called_once_with('fixture', 1, 'ja-JP')
        tool._load_scenario({'show_snippet': True})
        self.assertEqual(tool.search_engine_query('fixture', 1)[0]['body'], 'snippet')


class PageTests(unittest.TestCase):
    def test_rejects_private_and_mixed_dns_records(self):
        for ip in ('127.0.0.1', '169.254.169.254', '192.168.1.1', '::1', 'fc00::1', '224.0.0.1'):
            with self.subTest(address=ip), patch('socket.getaddrinfo', return_value=[
                (None, None, None, None, ('93.184.216.34', 443)), (None, None, None, None, (ip, 443))]):
                with self.assertRaisesRegex(ValueError, 'non-public'):
                    public_address('https://fixture.example/')

    def test_public_ip_is_pinned_and_private_redirect_stops_before_second_get(self):
        addresses = [(None, None, None, None, ('93.184.216.34', 443))]
        private_addresses = [(None, None, None, None, ('127.0.0.1', 443))]
        reply = Reply(status=302, headers={'Location': 'https://localhost/admin'})
        with patch('socket.getaddrinfo', side_effect=[addresses, private_addresses]), \
                patch('urllib3.HTTPSConnectionPool') as pool:
            instance = pool.return_value
            instance.urlopen.return_value = reply
            fetcher = PublicPageFetcher(CallBudget(4, 'page'), lambda row: None)
            with self.assertRaisesRegex(ValueError, 'non-public'):
                fetcher.fetch('https://fixture.example/')
        self.assertEqual(pool.call_args.args, ('93.184.216.34', 443))
        self.assertEqual(pool.call_args.kwargs['server_hostname'], 'fixture.example')
        self.assertEqual(instance.urlopen.call_args.kwargs['headers']['Host'], 'fixture.example')
        self.assertFalse(instance.urlopen.call_args.kwargs['retries'])
        self.assertEqual(fetcher.budget.used, 1)
        self.assertEqual(instance.urlopen.call_count, 1)

    def test_all_output_modes(self):
        tool = WebSearchAPI()
        html = '<h1>Fixture</h1><script>hidden();</script><p>Output</p>'
        tool.page_backend = SimpleNamespace(fetch=lambda url: html)
        self.assertEqual(tool.fetch_url_content('https://fixture.example/', 'raw')['content'], html)
        self.assertIn('# Fixture', tool.fetch_url_content('https://fixture.example/', 'markdown')['content'])
        self.assertEqual(tool.fetch_url_content('https://fixture.example/', 'truncate')['content'],
                         'Fixture\nOutput')


if __name__ == '__main__':
    unittest.main(verbosity=2)
