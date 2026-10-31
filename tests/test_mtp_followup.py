"""A failed native-MTP probe must never become an ON accuracy cell."""
import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mtp_followup',ROOT/'scripts/prepare_mtp_followup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class Followup(unittest.TestCase):
    def test_failed_probe_keeps_only_off_reference_and_marks_on_unavailable(self):
        plan={'model_manifest':'model.json','benchmark_profile':'profile.json','reference_off':'saved-off','wait_for_study':'prior'}
        result=module.definition(plan,False,'probe')
        self.assertEqual(result['groups'][0]['states'],['off'])
        self.assertEqual(result['groups'][0]['reference_runs'],{'off':'saved-off'})
        self.assertEqual(result['unavailable'][0]['mtp'],['on'])
        self.assertEqual(result['unavailable'][0]['capacity_run'],'probe')
        self.assertNotIn('passed',result['unavailable'][0])
        supported=module.definition(plan,True,'probe')
        self.assertEqual(supported['groups'][0]['states'],['off','on'])
        self.assertEqual(supported['unavailable'],[])

if __name__=='__main__':unittest.main()
