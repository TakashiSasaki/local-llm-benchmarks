"""Regression for a synthetic season table and Unicode page slices."""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integrations/page_harness'))
from page_harness import PageStore


class PartialReadGuidance(unittest.TestCase):
    def test_partial_season_table_warns_without_guessing_final_record(self):
        text = 'x' * 20 + '\n| Week | Cumulative record |\n| 5 | 3–2 |\n' + 'x' * 2400 + '\n| Final | 7–10 |'
        with tempfile.TemporaryDirectory() as directory:
            store = PageStore(directory)
            page = store.add('https://example.org/season', text)
            part = store.read(page['page_id'], 20)
            self.assertEqual(part['content'], text[20:2420])
            self.assertTrue(part['has_earlier_text'])
            self.assertTrue(part['has_later_text'])
            self.assertGreater(part['detected_pipe_table_rows'], 0)
            self.assertEqual(part['next_offset'], 2420)
            self.assertIn('not necessarily a complete table', part['coverage_hint'])
            self.assertNotIn('7–10', part['content'])
            self.assertNotIn('7–10', part['coverage_hint'])

    def test_final_and_complete_slices_do_not_assert_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PageStore(directory)
            page = store.add('https://example.org/a', '猫' * 2600)
            first = store.read(page['page_id'], 0)
            last = store.read(page['page_id'], 2400)
            self.assertFalse(first['has_earlier_text'])
            self.assertTrue(first['has_later_text'])
            self.assertTrue(last['has_earlier_text'])
            self.assertFalse(last['has_later_text'])
            self.assertIsNone(last['next_offset'])
            self.assertEqual(last['content'], '猫' * 200)
            small = store.add('https://example.org/b', 'short text')
            full = store.read(small['page_id'], 0)
            self.assertFalse(full['has_earlier_text'])
            self.assertFalse(full['has_later_text'])
            self.assertIn('still require verification', full['coverage_hint'])


if __name__ == '__main__':
    unittest.main()
