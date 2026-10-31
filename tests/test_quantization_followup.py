"""Incomplete preceding Q4 runs must not become completed Q3 comparison references."""
import importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('quant_followup',ROOT/'scripts/prepare_quantization_followup.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class QuantizationFollowup(unittest.TestCase):
    def test_failed_reference_is_not_counted_and_completed_reference_keeps_id(self):
        plan={'model_manifest':'q3.json','profile':'profile3.json','reference_off':'prior-off','reference_on':'prior-on','reference_manifest':'q4.json','reference_profile':'profile4.json','reference_report':'reports/prior/index.html'}
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);prior=root/'runs/prior-off';prior.mkdir(parents=True)
            (prior/'manifest.json').write_text(json.dumps({'status':'failed'}),encoding='utf-8')
            result=module.definition(plan,False,'mtp-probe',root)
            self.assertEqual(len(result['groups']),1);self.assertEqual(result['groups'][0]['states'],['off'])
            self.assertEqual(len(result['unavailable']),2);self.assertNotIn('reference_runs',result['groups'][0])
            (prior/'manifest.json').write_text(json.dumps({'status':'complete'}),encoding='utf-8')
            result=module.definition(plan,False,'mtp-probe',root)
            self.assertEqual(len(result['groups']),2)
            self.assertEqual(result['groups'][1]['reference_runs'],{'off':'prior-off'})
            self.assertEqual(result['groups'][1]['states'],['off'])
            self.assertEqual(len(result['unavailable']),1)

if __name__=='__main__':unittest.main()
