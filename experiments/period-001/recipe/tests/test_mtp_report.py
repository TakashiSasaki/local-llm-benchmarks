"""Check generic report arithmetic against pinned, already measured evidence."""
import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mtp_pair_report',ROOT/'scripts/report_mtp_pair.py')
report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)

class MtpReport(unittest.TestCase):
    def test_mtp_pair_keeps_caps_and_primary_secondary_scores_separate(self):
        off=report.cell('20261031-empero-mtp-load-none-q4-off')
        on=report.cell('20261031-empero-mtp-load-none-q4-on')
        self.assertEqual(off['metrics']['humaneval_on']['passed'],19)
        self.assertEqual(off['secondary_humaneval']['on']['secondary_passed'],20)
        self.assertEqual(on['metrics']['humaneval_on']['passed'],17)
        self.assertEqual(on['secondary_humaneval']['on']['secondary_passed'],19)
        self.assertEqual([r['case_id'] for r in on['truncations']],['irrelevance_139'])
        self.assertEqual([r['case_id'] for r in on['empty_responses']],['irrelevance_139'])
        comparison=report.compare(off,on)
        self.assertAlmostEqual(comparison['fixed_length_speedup'],1.2166057999,places=6)
        self.assertEqual(comparison['capability_changes']['bfcl_off']['score_changes'],[])
        self.assertEqual(comparison['capability_changes']['bfcl_on']['score_changes'],[{'id':'multiple_26','mtp_off':True,'mtp_on':False}])

if __name__=='__main__':unittest.main()
