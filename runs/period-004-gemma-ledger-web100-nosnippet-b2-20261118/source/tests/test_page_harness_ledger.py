"""Offline checks for the ledger and whole-turn compaction."""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integrations/page_harness'))
import context_manager as ctx
import ledger_live_probe as live
import page_harness as pages
import run_probe as probe
from ledger import ResearchLedger


def function_call(name, args, call_id):
    return {'id': call_id, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(args)}}


def assistant_call(name, args, call_id):
    return {'role': 'assistant', 'content': None,
            'tool_calls': [function_call(name, args, call_id)]}


class LedgerTest(unittest.TestCase):
    def test_evidence_requires_a_seen_real_range_and_is_not_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory)
            store = pages.PageStore(directory / 'pages')
            info = store.add('https://example.org/fact', '# Fact\nLargest natural lake: X.\n')
            page = store.pages[info['page_id']]
            ledger = ResearchLedger(directory / 'ledger.json', 'What is the largest lake?')
            requirement = ledger.add_requirement('largest lake, not limited to natural lakes')
            evidence_id = ledger.add_evidence(page, 7, 30, 'read_page')
            self.assertEqual(ledger.add_evidence(page, 7, 30, 'read_page'), evidence_id)
            with self.assertRaisesRegex(ValueError, 'shown'):
                ledger.update_requirement(requirement['id'], 'candidate', 'X', [evidence_id])
            ledger.mark_seen([evidence_id])
            with self.assertRaisesRegex(ValueError, 'shown'):
                ledger.update_requirement(requirement['id'], 'candidate', 'X', ['E999'])
            result = ledger.update_requirement(requirement['id'], 'candidate', 'X', [evidence_id])
            self.assertIn('not automatically verified', result['caveat'])
            self.assertEqual(result['status'], 'candidate')
            evidence = ledger.inspect()['evidence'][0]
            self.assertEqual(evidence['range_sha256'], hashlib.sha256(page['text'][7:30].encode()).hexdigest())
            self.assertEqual(evidence['page_sha256'], page['sha256'])
            self.assertTrue(evidence['seen_by_model'])
            excerpt = ledger.read_evidence(evidence_id, store.pages)
            self.assertEqual(excerpt['content'], page['text'][7:30])
            self.assertEqual(ledger.relevant_excerpts(store.pages)['excerpts'][0]['evidence_id'], evidence_id)
            omitted = ledger.relevant_excerpts(store.pages, max_characters=1)
            self.assertEqual(omitted['not_included'], 1)
            self.assertEqual(omitted['excerpts'], [])
            altered = dict(page, text=page['text'] + 'tampered')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                ledger.read_evidence(evidence_id, {page['id']: altered})
            ledger.update_requirement(requirement['id'], 'open')
            saved = json.loads((directory / 'ledger.json').read_text(encoding='utf8'))
            self.assertEqual(saved['requirements'][1]['status'], 'open')
            self.assertEqual(saved['requirements'][1]['evidence_ids'], [])
            with self.assertRaises(FileExistsError):
                ResearchLedger(directory / 'ledger.json', 'other')
            with self.assertRaises(ValueError):
                ledger.add_evidence(page, -1, 7, 'read_page')

    def test_approximate_find_records_exact_source_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            store = pages.PageStore(directory)
            info = store.add('https://example.org/a', '# Test\n' + 'x' * 2000 + '\nprice is 42 yen')
            found = store.find(info['page_id'], 'price total 42')
            self.assertEqual(found['mode'], 'ranked_terms')
            for hit in found['matches']:
                self.assertEqual(store.pages[info['page_id']]['text'][hit['excerpt_offset']:hit['excerpt_end']], hit['excerpt'])

    def test_complete_turns_are_archived_and_retrievable_in_pages(self):
        messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'question'}]
        for i in range(6):
            calls = [function_call('search', {'query': str(i)}, f'{i}a')]
            if i == 2:
                calls.append(function_call('search', {'query': 'second'}, f'{i}b'))
            messages.append({'role': 'assistant', 'content': None, 'tool_calls': calls, '_turn': i})
            for c in calls:
                messages.append({'role': 'tool', 'tool_call_id': c['id'], 'content': 'data' * 800, '_turn': i})
        candidates = ctx.archive_candidates(messages, recent_turns=2)
        self.assertEqual(candidates, [1, 2, 3])
        visible = ctx.public_messages(messages, candidates)
        self.assertEqual(visible[:2], messages[:2])
        assistant_ids = {c['id'] for m in visible if m['role'] == 'assistant' for c in m['tool_calls']}
        tool_ids = {m['tool_call_id'] for m in visible if m['role'] == 'tool'}
        self.assertEqual(assistant_ids, tool_ids)
        self.assertTrue(all(not any(k.startswith('_') for k in m) for m in visible))
        first = ctx.archived_turn_page(messages, candidates, 2, 0)
        chunks = [first['content']]
        offset = first['next_offset']
        while offset is not None:
            part = ctx.archived_turn_page(messages, candidates, 2, offset)
            chunks.append(part['content'])
            offset = part['next_offset']
        text = ''.join(chunks)
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), first['sha256'])
        self.assertEqual(len(json.loads(text)['messages']), 3)
        with self.assertRaises(ValueError):
            ctx.archived_turn_page(messages, candidates, 0, 0)
        messages[5]['_unseen'] = True
        self.assertNotIn(messages[5]['_turn'], ctx.archive_candidates(messages, recent_turns=2))

    def _run_compaction_fixture(self, directory, summary_finish='stop', no_reduction=False, repeat=False, below=False):
        sequence = [assistant_call('add_requirement', {'description': 'find the total'}, 'a'),
                    assistant_call('search', {'query': 'fact'}, 'b'),
                    assistant_call('open_page', {'url': 'https://example.org/fact'}, 'c'),
                    assistant_call('read_page', {'page_id': 'page_1', 'offset': 0}, 'd'),
                    assistant_call('update_requirement', {'requirement_id': 'R2', 'status': 'candidate',
                                                          'claim': '42', 'evidence_ids': ['E1']}, 'e'),
                    assistant_call('read_archived_turn', {'turn': 1, 'offset': 0}, 'f'),
                    assistant_call('read_evidence', {'evidence_id': 'E1'}, 'g'),
                    {'role': 'assistant', 'content': '42 https://example.org/fact'}]
        generated = []
        summary_requests = []

        class Search:
            def call(self, name, args):
                return {'result': [{'title': 'fact', 'url': 'https://example.org/fact', 'content': 'hint'}]}

        def count(messages, available_tools=None, thinking=True):
            if not thinking:
                return 80
            if below:
                return 32767
            assistant_turns = sum(m.get('role') == 'assistant' for m in messages)
            if no_reduction and 'Earlier-turn summary' in messages[0]['content']:
                return 32768
            if repeat:
                return 32768 if assistant_turns >= 4 else 100
            return 32768 if assistant_turns >= 4 and 'Earlier-turn summary' not in messages[0]['content'] else 100

        def api(route, data=None, timeout=0):
            self.assertEqual(route, '/v1/chat/completions')
            if not data['chat_template_kwargs']['enable_thinking']:
                summary_requests.append(data)
                return {'choices': [{'message': {'role': 'assistant', 'content': 'Earlier search found a source.'},
                                     'finish_reason': summary_finish}], 'usage': {'prompt_tokens': 80}}
            generated.append(data)
            return {'choices': [{'message': sequence.pop(0), 'finish_reason': 'stop'}]}

        (directory / 'raw').mkdir()
        with patch.object(probe, 'local_api', side_effect=api), \
                patch.object(probe, 'prompt_tokens', side_effect=count), \
                patch.object(probe, 'public_url'), \
                patch.object(probe, 'fetch_snapshot', return_value=('# Fact\nthe answer is 42', {})):
            answer = probe.run_case(directory, 'example', 'What is the total?', Search(), object())
        case = directory / 'raw/example'
        return answer, case, generated, summary_requests

    def test_model_compaction_uses_ledger_and_preserves_recent_tool_pairs(self):
        with tempfile.TemporaryDirectory() as d:
            answer, case, generated, summaries = self._run_compaction_fixture(pathlib.Path(d))
            self.assertEqual(answer, '42 https://example.org/fact')
            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]['chat_template_kwargs']['enable_thinking'], False)
            events = json.loads((case / 'events.json').read_text(encoding='utf8'))
            event = next(x for x in events if x['type'] == 'compaction')
            self.assertEqual(event['trigger_prompt_tokens'], 32768)
            self.assertEqual(event['post_compaction_prompt_tokens'], 100)
            self.assertEqual(event['archived_turns'], [1])
            self.assertTrue((case / 'compaction-04-request.json').exists())
            self.assertTrue((case / 'compaction-04-response.json').exists())
            ledger = json.loads((case / 'ledger.json').read_text(encoding='utf8'))
            self.assertEqual(ledger['archived_turns'], [1])
            self.assertEqual(ledger['requirements'][1]['status'], 'candidate')
            self.assertEqual(ledger['requirements'][1]['evidence_ids'], ['E1'])
            self.assertTrue(ledger['evidence'][0]['seen_by_model'])
            self.assertIn('Earlier search found a source.', generated[-1]['messages'][0]['content'])
            self.assertIn('the answer is 42', generated[-1]['messages'][0]['content'])
            self.assertIn('What is the total?', generated[-1]['messages'][1]['content'])
            restored = next(x for x in events if x.get('name') == 'read_archived_turn' and x['type'] == 'tool')
            self.assertIn('fact', restored['result']['content'])
            reread = next(x for x in events if x.get('name') == 'read_evidence' and x['type'] == 'tool')
            self.assertIn('the answer is 42', reread['result']['content'])
            self.assertTrue((case / 'model-01.json').exists())

    def test_failed_summary_retains_history_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as d:
            answer, case, generated, summaries = self._run_compaction_fixture(pathlib.Path(d), 'length')
            self.assertEqual(answer, '')
            self.assertEqual(len(summaries), 1)
            result = json.loads((case / 'result.json').read_text(encoding='utf8'))
            self.assertEqual(result['status'], 'context_compaction_failed')
            ledger = json.loads((case / 'ledger.json').read_text(encoding='utf8'))
            self.assertEqual(ledger['archived_turns'], [])
            self.assertTrue((case / 'model-01.json').exists())
            self.assertTrue((case / 'compaction-04-response.json').exists())
            self.assertEqual(len(generated), 4)

    def test_summary_that_does_not_reduce_prompt_is_not_used(self):
        with tempfile.TemporaryDirectory() as d:
            answer, case, generated, summaries = self._run_compaction_fixture(pathlib.Path(d), no_reduction=True)
            self.assertEqual(answer, '')
            self.assertEqual(len(summaries), 1)
            result = json.loads((case / 'result.json').read_text(encoding='utf8'))
            self.assertEqual(result['status'], 'context_compaction_failed')
            self.assertEqual(json.loads((case / 'ledger.json').read_text(encoding='utf8'))['archived_turns'], [])
            events = json.loads((case / 'events.json').read_text(encoding='utf8'))
            self.assertIn('did not reduce', events[-1]['error'])

    def test_later_compaction_includes_the_previous_summary(self):
        with tempfile.TemporaryDirectory() as d:
            answer, case, generated, summaries = self._run_compaction_fixture(pathlib.Path(d), repeat=True)
            self.assertTrue(answer)
            self.assertGreaterEqual(len(summaries), 2)
            second_data = json.loads(summaries[1]['messages'][1]['content'])
            self.assertEqual(second_data['previous_summary'], 'Earlier search found a source.')
            events = json.loads((case / 'events.json').read_text(encoding='utf8'))
            archive_sets = [set(x['archived_turns']) for x in events if x['type'] == 'compaction']
            self.assertTrue(all(not (a & b) for i, a in enumerate(archive_sets) for b in archive_sets[i+1:]))

    def test_below_half_context_does_not_generate_a_summary(self):
        with tempfile.TemporaryDirectory() as d:
            answer, case, generated, summaries = self._run_compaction_fixture(pathlib.Path(d), below=True)
            self.assertTrue(answer)
            self.assertEqual(summaries, [])
            events = json.loads((case / 'events.json').read_text(encoding='utf8'))
            self.assertFalse(any(x['type'] == 'compaction' for x in events))

    def test_source_snapshot_is_reproducible_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            run = pathlib.Path(d)
            probe.snapshot_harness_sources(run)
            manifest = json.loads((run / 'source-manifest.json').read_text(encoding='utf8'))
            for name in ['integrations/page_harness/ledger.py', 'integrations/page_harness/context_manager.py',
                         'integrations/page_harness/run_probe.py', 'tests/test_page_harness_ledger.py']:
                self.assertEqual(hashlib.sha256((run / 'source' / name).read_bytes()).hexdigest(), manifest['files'][name])
            with self.assertRaisesRegex(ValueError, 'preserved'):
                probe.snapshot_harness_sources(run)

    def test_live_fixture_requires_normal_answer_and_exact_evidence(self):
        page = {'url': 'https://example.org/lakes', 'text': 'Bantam then Candlewood'}
        answer = 'Bantam and Candlewood https://example.org/lakes'
        event = {'tool': 'read_evidence', 'result': {'evidence_id': 'E1', 'offset': 0,
                                                     'end': len(page['text']), 'content': page['text']}}
        self.assertEqual(live.assess_fixture(answer, 'stop', 'E1', [event], page)['outcome'], 'passed')
        self.assertEqual(live.assess_fixture(answer, 'length', 'E1', [event], page)['outcome'], 'partial')
        self.assertEqual(live.assess_fixture(answer, 'stop', 'E1', [], page)['outcome'], 'partial')
        event['result']['content'] = 'tampered'
        self.assertEqual(live.assess_fixture(answer, 'stop', 'E1', [event], page)['outcome'], 'partial')


if __name__ == '__main__':
    unittest.main()
