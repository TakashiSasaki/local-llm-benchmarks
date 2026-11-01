"""Allocation success alone must not be accepted without GPU headroom evidence."""
import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dense_followup',ROOT/'scripts/prepare_dense_placement_followup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class DensePlacement(unittest.TestCase):
    def test_missing_telemetry_and_guard_or_reserve_breach_are_rejected(self):
        result={'status':'complete','exit_code':0,'resource_guard':[],'memory':{'peak_gpu_used_mib_system_total':7500}}
        self.assertTrue(module.admissible(result,7676))
        self.assertFalse(module.admissible(dict(result,memory={}),7676))
        self.assertFalse(module.admissible(dict(result,memory={'peak_gpu_used_mib_system_total':7800}),7676))
        self.assertFalse(module.admissible(dict(result,resource_guard=[{'reason':'low RAM'}]),7676))
        self.assertFalse(module.admissible(dict(result,status='failed',exit_code=1),7676))

if __name__=='__main__':unittest.main()
