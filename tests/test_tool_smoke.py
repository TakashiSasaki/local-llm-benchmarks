import importlib.util,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
spec=importlib.util.spec_from_file_location('tool_smoke',ROOT/'benchmarks/tool_smoke.py');smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)

class Smoke(unittest.TestCase):
    def test_capability_scores_are_not_claimed_by_short_smoke(self):
        cases=[{'category':c,'problem':{'id':c+'_1','question':[[{'role':'user','content':'test'}]]}} for c in ['simple_python','multiple','parallel','irrelevance']]
        def api(route,payload,timeout):
            self.assertLessEqual(payload['max_tokens'],2048)
            msg={'content':'391','reasoning_content':'calculation' if payload['chat_template_kwargs']['enable_thinking'] else ''}
            if 'tools' in payload:msg['tool_calls']=[{'type':'function','function':{'name':'f','arguments':'{}'}}]
            return {'choices':[{'message':msg,'finish_reason':'stop'}]}
        with tempfile.TemporaryDirectory() as tmp,patch.object(smoke,'components',return_value=(cases,lambda c:[],lambda c,r:{'passed':False})):
            result=smoke.collect(pathlib.Path(tmp),api,'test')
        self.assertTrue(result['transport_and_mode_checks_passed'])
        self.assertEqual(len(result['cases']),8)
        self.assertTrue(all(not c['passed'] for c in result['cases']))
        self.assertNotIn('accuracy',result)
