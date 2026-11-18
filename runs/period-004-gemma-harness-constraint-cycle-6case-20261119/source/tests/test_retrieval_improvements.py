"""Regression controls for approximate excerpts and their provenance."""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integrations/page_harness'))
from page_harness import PageStore


class RetrievalImprovements(unittest.TestCase):
    def test_window_terms_are_not_misreported_as_excerpt_terms(self):
        text = '# Example\nalpha ' + 'x' * 1300 + ' beta gamma'
        with tempfile.TemporaryDirectory() as folder:
            store = PageStore(folder)
            page = store.add('https://example.org/example', text)
            result = store.find(page['page_id'], 'alpha beta gamma')
            self.assertEqual(result['mode'], 'ranked_terms')
            first = result['matches'][0]
            self.assertEqual(first['window_matched_terms'], ['alpha', 'beta', 'gamma'])
            self.assertEqual(first['matched_terms'], ['alpha'])
            self.assertEqual(first['missing_excerpt_terms'], ['beta', 'gamma'])
            self.assertNotIn('beta', first['excerpt'])
            self.assertEqual(text[first['excerpt_offset']:first['excerpt_end']], first['excerpt'])
            self.assertIn(first['excerpt'], store.read(page['page_id'], first['read_offset'])['content'])

    def test_adjacent_names_keep_their_distinguishing_context(self):
        text = ('# Results\n2024 awards winners: ' + 'x' * 80 +
                ' Hannah’s historical fiction novel The Women, Kelly Bishop’s memoir, '
                'The Third Gilmore Girl, and another story.')
        with tempfile.TemporaryDirectory() as folder:
            store = PageStore(folder)
            page = store.add('https://example.org/results', text)
            result = store.find(page['page_id'], '2024 fiction winner')
            self.assertEqual(result['mode'], 'ranked_terms')
            excerpt = result['matches'][0]['excerpt']
            self.assertIn('The Women', excerpt)
            self.assertIn('Kelly Bishop’s memoir', excerpt)
            self.assertIn('The Third Gilmore Girl', excerpt)

    def test_excerpt_offsets_and_size_with_unicode(self):
        text = '# 説明\n' + '水' * 1400 + '価格は100円。発売日は月曜日。' + '森' * 1600
        with tempfile.TemporaryDirectory() as folder:
            store = PageStore(folder)
            page = store.add('https://example.org/jp', text)
            result = store.find(page['page_id'], '価格 発売日')
            for hit in result['matches']:
                self.assertLessEqual(len(hit['excerpt']), 1000)
                self.assertEqual(text[hit['excerpt_offset']:hit['excerpt_end']], hit['excerpt'])
                self.assertTrue(all(term in hit['excerpt'].lower() for term in hit['matched_terms']))
                self.assertIn(hit['excerpt'], store.read(page['page_id'], hit['read_offset'])['content'])


if __name__ == '__main__':
    unittest.main()
