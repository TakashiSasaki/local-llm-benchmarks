import argparse, importlib.util, pathlib, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mtp_bfcl_recovery',ROOT/'scripts/run_mtp_study.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)

class RecoveryConditions(unittest.TestCase):
    def test_bfcl_subset_does_not_repeat_bfcl_off(self):
        self.assertEqual(driver.capability_conditions(bfcl_continuation='plan'), [('bfcl','on'),('humaneval','off'),('humaneval','on')])
        self.assertEqual(driver.capability_conditions(continuation='plan'), [('humaneval','on')])
        self.assertEqual(len(driver.capability_conditions()),4)
    def test_conflicting_plans_are_rejected(self):
        with self.assertRaises(ValueError):driver.capability_conditions('one','two')
    def test_invalid_capability_mode_starts_no_run(self):
        for pilot,speed,mtp in [(True,False,'off'),(False,True,'off'),(False,False,'on')]:
            args=argparse.Namespace(model_manifest='model',profile='profile',continuation_plan=None,bfcl_continuation_plan='subset',pilot=pilot,speed_only=speed,mtp=mtp)
            with patch.object(driver,'load',return_value={}),patch.object(driver,'create_run') as create,patch.object(driver.subprocess,'Popen') as spawn:
                with self.assertRaises(ValueError):driver.run(args)
                create.assert_not_called();spawn.assert_not_called()

if __name__=='__main__':unittest.main()
