"""Regression cases where aggregation could silently change the study's meaning."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.comprehensive import collect, condition


class Comprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = collect()
        cls.rows = {r['id']: r for r in cls.data['rows']}

    def test_reference_cells_do_not_create_new_inference_rows(self):
        q4 = [r for r in self.data['rows'] if r['id'] == '20261031-empero-mtp-load-none-q4-off']
        self.assertEqual(len(q4), 1)  # Also referenced by the Qwen Q4 and Q5 grids.
        raws = [x['raw'] for r in self.data['rows'] for c in r['conditions'].values() for x in c['cases']]
        self.assertEqual(len(raws), len(set(raws)))
        self.assertEqual(len(raws), 4776)

    def test_mage_partial_and_parser_unknowns_stay_distinct(self):
        q4 = self.rows['20261031-mage-q4-text-64k-parser-errors-mage-text-off']['conditions']['bfcl_off']
        self.assertEqual((q4['score'], q4['saved'], q4['passed_saved']), (None, 8, 7))
        self.assertEqual((q4['parser_errors'], q4['unknown_statistics'], q4['caps_known']), (1, 1, 0))
        q3 = self.rows['20261031-mage-q3-text-64k-q3-off']['conditions']
        self.assertEqual((q3['bfcl_off']['score'], q3['bfcl_on']['score']), (19, 21))
        self.assertIsNone(q3['he_off']['score'])
        self.assertEqual(q3['he_off']['saved'], 0)
        self.assertEqual(q3['he_on']['status'], 'not-started')

    def test_cap_can_pass_no_call_grading_without_final_answer(self):
        c = self.rows['20261031-empero-mtp-load-none-q4-on']['conditions']['bfcl_on']
        item = next(x for x in c['cases'] if x['id'] == 'irrelevance_139')
        self.assertEqual((item['passed'], item['empty_final'], item['finish_reason']), (True, True, 'length'))
        self.assertEqual(c['passed_without_final'], 1)

    def test_speed_only_does_not_imply_quality_coverage(self):
        r = self.rows['20261031-mage-q3-text-64k-gpu-placement-ngl23-throughput']
        self.assertEqual(r['conditions'], {})
        self.assertEqual(r['fixed_speed']['cases'], 9)
        unmeasured = [r for r in self.data['coverage'] if r['quantization'] in ['Q4_K_S', 'Q4_K_L']]
        self.assertEqual(len(unmeasured), 4)
        self.assertTrue(all(v == 'not-measured' for r in unmeasured for v in r['states'].values()))

    def test_short_collection_cannot_be_marked_complete(self):
        c = condition([], 80, 'complete', 'fixture')
        self.assertFalse(c['complete'])
        self.assertEqual(c['status'], 'partial')
        self.assertIsNone(c['score'])

    def test_historical_nested_budgets_and_copied_snapshots(self):
        old = self.data['historical']
        lfm = [r for r in old if 'lfm3-bench' in r['source']]
        self.assertTrue(all(r['max_output'] == (4096 if r['benchmark'] == 'he' else 1024) for r in lfm))
        copied = [r for r in old if r['same_response_snapshot']]
        self.assertEqual(len(copied), 2)


if __name__ == '__main__':
    unittest.main()
