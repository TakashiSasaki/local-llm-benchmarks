"""BFCL prompt-mode search via the reviewed JSON Streamable HTTP MCP interface."""
import ipaddress
import json
import socket
import ssl
from urllib.parse import urljoin, urlsplit

import requests
import urllib3
from bs4 import BeautifulSoup
from html2text import HTML2Text


PROTOCOL = '2025-11-25'
SEARCH = 'searxng_search'
ENGINE = 'duckduckgo'
LIMIT_BYTES = 2 * 1024 * 1024
# BFCL uses DDG market codes, while SearXNG uses language and locale codes.
REGIONAL_LANGUAGES = {
    'wt-wt': 'all', 'xa-ar': 'ar', 'xa-en': 'en', 'jp-jp': 'ja-JP',
    'kr-kr': 'ko-KR', 'uk-en': 'en-GB', 'tw-tzh': 'zh-TW', 'tw-tz': 'zh-TW',
    'hk-tz': 'zh-HK', 'ct-ca': 'ca', 'xl-es': 'es', 'ue-es': 'es-US',
}
PAGE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
              'image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://www.google.com/',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-User': '?1',
    'Sec-Fetch-Dest': 'document',
}


class BackendStop(BaseException):
    """Infrastructure/budget stop. The upstream executor catches Exception."""


class CallBudget:
    def __init__(self, limit, label):
        self.limit = limit
        self.label = label
        self.used = 0

    def take(self):
        if self.used >= self.limit:
            raise BackendStop(f'{self.label}_budget_exhausted')
        self.used += 1


def language_for_region(region):
    market = (region or 'wt-wt').lower()
    if market in REGIONAL_LANGUAGES:
        return REGIONAL_LANGUAGES[market]
    country, separator, language = market.partition('-')
    if separator and len(country) == len(language) == 2 and market in BFCL_MARKETS:
        return f'{language}-{country.upper()}'
    raise ValueError('unsupported BFCL region')


BFCL_MARKETS = frozenset(
    'ar-es au-en at-de be-fr be-nl br-pt bg-bg ca-en ca-fr ct-ca cl-es cn-zh co-es '
    'hr-hr cz-cs dk-da ee-et fi-fi fr-fr de-de gr-el hu-hu in-en id-id id-en ie-en '
    'il-he it-it lv-lv lt-lt my-ms my-en mx-es nl-nl nz-en no-no pe-es ph-en ph-tl pl-pl '
    'pt-pt ro-ro ru-ru sg-en sk-sk sl-sl za-en es-es se-sv ch-de ch-fr ch-it '
    'th-th tr-tr ua-uk us-en ve-es vn-vi'.split()
)


class SearxngMCP:
    def __init__(self, url, budget, record, token=None, *, record_tool_error=None):
        parts = urlsplit(url)
        if (parts.scheme != 'https' or not parts.hostname or parts.username is not None
                or parts.query or parts.fragment):
            raise ValueError('use an HTTPS MCP URL without embedded credentials or query')
        self.url = url
        self.budget = budget
        self.record = record
        self.record_tool_error = record_tool_error
        self.http = requests.Session()
        self.http.trust_env = False
        self.http.headers.update({'Accept': 'application/json, text/event-stream'})
        if token:
            self.http.headers['Authorization'] = f'Bearer {token}'
        self.request_id = 0
        self.connected = False

    def _rpc(self, method, params=None):
        message = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            message['params'] = params
        notification = method == 'notifications/initialized'
        if not notification:
            self.request_id += 1
            message['id'] = self.request_id
        try:
            with self.http.post(self.url, json=message, timeout=(5, 20), stream=True,
                                allow_redirects=False) as response:
                if notification and response.status_code == 202:
                    return None
                if response.status_code != 200:
                    raise BackendStop(f'mcp_http_{response.status_code}')
                if response.headers.get('MCP-Session-Id'):
                    self.http.headers['MCP-Session-Id'] = response.headers['MCP-Session-Id']
                if not response.headers.get('Content-Type', '').startswith('application/json'):
                    raise BackendStop('mcp_expected_json_response')
                data = response.raw.read(LIMIT_BYTES + 1, decode_content=True)
            if len(data) > LIMIT_BYTES:
                raise BackendStop('mcp_response_too_large')
            received = json.loads(data)
        except (OSError, ValueError, requests.RequestException, urllib3.exceptions.HTTPError) as exc:
            raise BackendStop(f'mcp_transport_{type(exc).__name__}') from None
        if (not isinstance(received, dict) or received.get('id') != self.request_id
                or not isinstance(received.get('result'), dict)):
            raise BackendStop('mcp_protocol_error')
        return received['result']

    def connect(self):
        init = self._rpc('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {},
                                       'clientInfo': {'name': 'bfcl-f7-followup', 'version': '1'}})
        if init.get('protocolVersion') != PROTOCOL:
            raise BackendStop('mcp_protocol_version_changed')
        self.http.headers['MCP-Protocol-Version'] = PROTOCOL
        self._rpc('notifications/initialized')
        tools = self._rpc('tools/list', {})
        search = next((tool for tool in tools.get('tools', []) if tool.get('name') == SEARCH), None)
        required = {'query', 'language', 'engines', 'max_results', 'force_refresh'}
        if search is None or not required <= set(search.get('inputSchema', {}).get('properties', {})):
            raise BackendStop('mcp_search_tool_schema_changed')
        self.record({'operation': 'mcp_setup', 'server': init.get('serverInfo'), 'tool': search})
        self.connected = True

    def close(self):
        try:
            if self.http.headers.get('MCP-Session-Id'):
                with self.http.delete(self.url, timeout=(5, 5), allow_redirects=False) as response:
                    self.record({'operation': 'mcp_close', 'http_status': response.status_code})
        except requests.RequestException:
            self.record({'operation': 'mcp_close', 'status': 'transport_error'})
        finally:
            self.http.close()

    def search(self, keywords, max_results, language):
        if not self.connected:
            self.connect()
        arguments = {'query': keywords, 'language': language, 'engines': [ENGINE],
                     'max_results': min(max_results, 50), 'force_refresh': False}
        self.budget.take()
        try:
            reply = self._rpc('tools/call', {'name': SEARCH, 'arguments': arguments})
            structured = reply.get('structuredContent')
            if reply.get('isError') or not isinstance(structured, dict):
                if self.record_tool_error is not None:
                    self.record_tool_error(reply)
                reason = ('mcp_search_tool_reported_error' if reply.get('isError')
                          else 'mcp_search_structured_content_missing')
                raise BackendStop(reason)
            rows, info = structured.get('result'), structured.get('search_info')
            if not isinstance(rows, list) or not isinstance(info, dict):
                raise BackendStop('mcp_search_schema_mismatch')
            if (info.get('selected_engines') != [ENGINE]
                    or set(info.get('observed_engines', [])) - {ENGINE}):
                raise BackendStop('mcp_unexpected_search_engine')
            if not rows and info.get('unresponsive_engines'):
                raise BackendStop('mcp_search_engine_unresponsive')
            for result in rows:
                if (not isinstance(result, dict)
                        or not all(isinstance(result.get(key), str) for key in ('title','url','content','engine'))):
                    raise BackendStop('mcp_search_row_schema_mismatch')
        except BackendStop as exc:
            self.record({'operation': 'search', 'arguments': arguments, 'error': str(exc)})
            raise
        self.record({'operation': 'search', 'arguments': arguments, 'response': structured})
        return rows


def public_address(url):
    parts = urlsplit(url)
    ports = {'http': 80, 'https': 443}
    if (parts.scheme not in ports or not parts.hostname or parts.username is not None
            or parts.port not in (None, ports[parts.scheme])):
        raise ValueError('URL must use public HTTP(S) on its standard port')
    port = ports[parts.scheme]
    records = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    addresses = [ipaddress.ip_address(item[4][0]) for item in records]
    if not addresses or any(not addr.is_global or addr.is_multicast or addr.is_reserved for addr in addresses):
        raise ValueError('non-public URL destination')
    # Connect to the checked address, keeping the original Host and TLS identity.
    return parts, str(addresses[0]), port


class PublicPageFetcher:
    def __init__(self, budget, record):
        self.budget = budget
        self.record = record

    def fetch(self, url):
        for hop in range(6):
            parts, address, port = public_address(url)
            if parts.scheme == 'https':
                pool = urllib3.HTTPSConnectionPool(address, port, server_hostname=parts.hostname,
                                                   assert_hostname=parts.hostname,
                                                   ssl_context=ssl.create_default_context())
            else:
                pool = urllib3.HTTPConnectionPool(address, port)
            request = requests.PreparedRequest()
            request.prepare_url(url, None)
            try:
                self.budget.take()
                with pool.urlopen('GET', request.path_url, headers={**PAGE_HEADERS, 'Host': parts.netloc},
                                  retries=False, redirect=False, preload_content=False,
                                  timeout=urllib3.Timeout(connect=5, read=20)) as reply:
                    self.record({'operation': 'page_get', 'url': url, 'status': reply.status, 'hop': hop})
                    if reply.status in (301, 302, 303, 307, 308) and reply.headers.get('Location'):
                        url = urljoin(url, reply.headers['Location'])
                        continue
                    if reply.status >= 400:
                        raise ValueError(f'page returned HTTP {reply.status}')
                    data = reply.read(LIMIT_BYTES + 1, decode_content=True)
                    if len(data) > LIMIT_BYTES:
                        raise ValueError('page exceeded response size limit')
                    encoding = requests.utils.get_encoding_from_headers(reply.headers) or 'utf-8'
                    return data.decode(encoding, errors='replace')
            finally:
                pool.close()
        raise ValueError('page exceeded redirect limit')


class WebSearchAPI:
    """Methods named by the upstream BFCL WebSearchAPI function documents."""
    search_backend = None
    page_backend = None

    def _load_scenario(self, initial_config, long_context=False):
        self.show_snippet = initial_config['show_snippet']

    def search_engine_query(self, keywords, max_results=10, region='wt-wt'):
        if not isinstance(keywords, str) or not keywords.strip():
            return {'error': 'keywords must be a non-empty string'}
        limit = 10 if max_results is None else max_results
        if type(limit) is not int or limit < 1:
            return {'error': 'max_results must be a positive integer'}
        try:
            language = language_for_region(region)
        except (ValueError, AttributeError):
            return {'error': 'unsupported search region'}
        rows = self.search_backend.search(keywords, limit, language)
        results = []
        for row in [row for row in rows if row['engine'] == ENGINE][:limit]:
            item = {'title': row['title'], 'href': row['url']}
            if self.show_snippet:
                item['body'] = row['content']
            results.append(item)
        return results

    def fetch_url_content(self, url, mode='raw'):
        if not isinstance(url, str):
            return {'error': 'URL must be a string'}
        if mode not in ('raw', 'markdown', 'truncate'):
            return {'error': 'unsupported page mode'}
        try:
            content = self.page_backend.fetch(url)
            if mode == 'markdown':
                content = HTML2Text().handle(content)
            elif mode == 'truncate':
                soup = BeautifulSoup(content, 'html.parser')
                for tag in soup(['script', 'style']):
                    tag.extract()
                content = soup.get_text(separator='\n', strip=True)
            return {'content': content}
        except (ValueError, OSError, LookupError, urllib3.exceptions.HTTPError) as exc:
            return {'error': f'page fetch failed: {str(exc)}' if isinstance(exc, ValueError)
                    else f'page fetch failed: {type(exc).__name__}'}
