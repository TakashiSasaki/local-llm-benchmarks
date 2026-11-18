"""Verify the actual loop delivers advisory source context without inventing evidence."""
import json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'integrations/page_harness'))
import run_probe as probe

class ConstraintLoopTests(unittest.TestCase):
    def test_source_advisories_reach_model_and_answer_is_retained(self):
        def call(name,args,ident):
            return {'role':'assistant','content':None,'tool_calls':[{'id':ident,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        replies=[call('search',{'query':'lake'},'a'),call('open_page',{'url':'https://example.org/a'},'b'),
                 call('read_page',{'page_id':'page_1','offset':0},'c'),
                 {'role':'assistant','content':'The largest natural lake is Lake X.'}]
        class Search:
            def call(self,*args):return {'result':[{'title':'lake','url':'https://example.org/a','content':'hint'}]}
        captured=[]
        def api(route,data=None,timeout=0):
            if route=='/apply-template':return {'prompt':'fixture'}
            if route=='/tokenize':return {'tokens':[1,2,3]}
            captured.append(data)
            return {'choices':[{'message':replies.pop(0),'finish_reason':'stop'}]}
        text='# Source\nUpdated in 2026. The largest natural lake is Lake X.'
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe,'local_api',side_effect=api), \
             patch.object(probe,'public_url'),patch.object(probe,'fetch_snapshot',return_value=(text,{})):
            root=pathlib.Path(tmp);(root/'raw').mkdir()
            answer=probe.run_case(root,'case','What was the largest lake as of April 2025?',Search(),object())
            self.assertEqual(answer,'The largest natural lake is Lake X.')
            result=json.loads((root/'raw/case/result.json').read_text(encoding='utf8'))
            self.assertEqual(result['constraint_warnings'][0]['kind'],'possible_natural_only_narrowing')
            tool=next(m for m in captured[-1]['messages'] if m.get('tool_call_id')=='c')
            content=json.loads(tool['content'])
            self.assertEqual(content['constraint_warnings'][0]['kind'],'possible_natural_only_narrowing')
            self.assertEqual(content['temporal_advisory']['later_years'][0]['year'],2026)
            self.assertIn('may describe publication',content['temporal_advisory']['scope'])

    def test_url_date_advisory_reaches_model_without_snippet(self):
        replies=[{'role':'assistant','content':None,'tool_calls':[{'id':'a','type':'function','function':{'name':'search','arguments':json.dumps({'query':'mayor'})}}]},
                 {'role':'assistant','content':'Insufficient historical evidence.'}]
        class Search:
            def call(self,*args):return {'result':[{'title':'mayor','url':'https://example.org/20260322-mayor','content':'hidden snippet'}]}
        requests=[]
        def api(route,data=None,timeout=0):
            if route=='/apply-template':return {'prompt':'fixture'}
            if route=='/tokenize':return {'tokens':[1,2]}
            requests.append(data);return {'choices':[{'message':replies.pop(0),'finish_reason':'stop'}]}
        with tempfile.TemporaryDirectory() as tmp,patch.object(probe,'local_api',side_effect=api):
            root=pathlib.Path(tmp);(root/'raw').mkdir()
            probe.run_case(root,'case','Who was mayor as of April 2025?',Search(),object(),{'show_snippets':False})
            msg=next(m for m in requests[-1]['messages'] if m.get('tool_call_id')=='a')
            result=json.loads(msg['content'])['results'][0]
            self.assertNotIn('snippet',result)
            self.assertEqual(result['temporal_url_advisory']['later_path_dates'][0]['path_date'],'2026-03-22')
            self.assertIn('not necessarily a publication date',result['temporal_url_advisory']['scope'])

if __name__=='__main__':unittest.main()
