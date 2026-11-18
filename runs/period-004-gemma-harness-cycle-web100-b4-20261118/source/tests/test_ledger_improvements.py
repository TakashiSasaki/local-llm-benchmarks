"""Evidence selection aids must not turn an unsupported claim into a fact."""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integrations/page_harness'))
from ledger import ResearchLedger
from page_harness import PageStore


class EvidenceSelectionTests(unittest.TestCase):
    def test_empty_ids_offer_only_shown_pointers_without_updating_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            store = PageStore(base / 'pages')
            page = store.add('https://example.org', '# Sample\nAlpha. Beta. Gamma.')
            saved = store.pages[page['page_id']]
            ledger = ResearchLedger(base / 'ledger.json', 'What is the answer?')
            req = ledger.add_requirement('Identify the answer')
            first = ledger.add_evidence(saved, 0, 8, 'read_page')
            unseen = ledger.add_evidence(saved, 9, 15, 'find_in_page', mode='ranked_terms')
            ledger.mark_seen([first])
            before = (base / 'ledger.json').read_bytes()

            with self.assertRaises(ValueError) as caught:
                ledger.update_requirement(req['id'], 'candidate', 'Alpha', [])
            message = str(caught.exception)
            self.assertIn('candidate needs 1-5 evidence IDs', message)
            self.assertIn('E1(page_1:0-8)', message)
            self.assertNotIn(unseen, message)
            self.assertIn('not verification', message)
            self.assertEqual((base / 'ledger.json').read_bytes(), before)
            self.assertEqual(ledger.requirements[1]['status'], 'open')
            self.assertEqual(ledger.requirements[1]['evidence_ids'], [])

            with self.assertRaises(ValueError) as caught:
                ledger.update_requirement(req['id'], 'candidate', 'Alpha', [unseen])
            self.assertIn('have been shown', str(caught.exception))
            self.assertEqual((base / 'ledger.json').read_bytes(), before)

            # A caller must explicitly select a shown ID; even this is a candidate only.
            result = ledger.update_requirement(req['id'], 'candidate', 'Alpha', [first])
            self.assertEqual(result['status'], 'candidate')
            self.assertIn('not automatically verified', result['caveat'])

    def test_context_offers_bounded_recent_seen_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base = pathlib.Path(directory)
            store = PageStore(base / 'pages')
            info = store.add('https://example.org', '0123456789abcdef')
            page = store.pages[info['page_id']]
            ledger = ResearchLedger(base / 'ledger.json', 'Question')
            ids = [ledger.add_evidence(page, n, n + 1, 'read_page') for n in range(8)]
            ledger.mark_seen(ids[:7])
            shown = ledger.eligible_evidence()
            self.assertEqual([x['id'] for x in shown['entries']], list(reversed(ids[2:7])))
            self.assertEqual((shown['total_shown'], shown['not_listed']), (7, 2))
            self.assertNotIn(ids[7], json.dumps(ledger.context()['shown_evidence_for_selection']))
            self.assertIn('not verified', ledger.context()['scope'])
            with self.assertRaises(ValueError):
                ledger.eligible_evidence(0)
            with self.assertRaises(ValueError):
                ledger.eligible_evidence(True)

    def test_without_shown_sources_the_instruction_is_to_read_or_leave_open(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = ResearchLedger(pathlib.Path(directory) / 'ledger.json', 'Question')
            with self.assertRaises(ValueError) as caught:
                ledger.update_requirement('R1', 'candidate', 'unsupported', [])
            self.assertIn('No shown evidence', str(caught.exception))
            self.assertIn('leave the requirement open', str(caught.exception))
            self.assertEqual(ledger.requirements[0]['status'], 'open')


if __name__ == '__main__':
    unittest.main()
