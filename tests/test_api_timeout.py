"""Offline HTTP timeout plumbing, without a live endpoint or model."""
import argparse,contextlib,gzip,importlib.util,io,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.bfcl_subset import positive_timeout

class APITimeout(unittest.TestCase):
    def test_positive_integer_validation(self):
        self.assertEqual(positive_timeout('14400'),14400)
        for value in [0,-1,True,1.5,'1.5','nan',None]:
            with self.subTest(value=value),self.assertRaises(ValueError):positive_timeout(value)

    def test_completion_timeout_both_drivers(self):
        for name in ['bfcl','humaneval']:
            for seconds in [7200,14400]:
                with self.subTest(driver=name,seconds=seconds):self.exercise(name,seconds)

    def exercise(self,name,seconds):
        spec=importlib.util.spec_from_file_location('timeout_'+name,ROOT/'benchmarks'/f'{name}.py')
        d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
        calls=[]
        def urlopen(req,timeout):
            route=req.full_url.split('8089')[-1];calls.append((route,timeout))
            if route=='/props':data={'model_alias':'test','default_generation_settings':{'n_ctx':65536},'total_slots':1,'build_info':'test'}
            elif route=='/apply-template':data={'prompt':'test'}
            elif route=='/tokenize':data={'tokens':[1]}
            else:data={'choices':[{'message':{'content':'pass','reasoning_content':'test'},'finish_reason':'stop'}],'usage':{}}
            return io.StringIO(json.dumps(data))
        with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
            path=pathlib.Path(tmp);(path/'manifest.json').write_text('{"status":"planned"}')
            args=argparse.Namespace(run='unused',model='test',thinking='on',endpoint='http://localhost:8089',mode_control='native',context=65536,max_output=64000,api_timeout_seconds=seconds)
            for target,replacement in [('resolve_run',lambda _:path),('assert_run_writable',lambda _:None),('snapshot_sources',lambda _:None),('require',lambda *a:None)]:stack.enter_context(patch.object(d,target,replacement))
            stack.enter_context(patch.object(d.urllib.request,'urlopen',side_effect=urlopen))
            if name=='bfcl':
                cases=[{'problem':{'id':'test','question':[[{'role':'user','content':'test'}]]},'category':'irrelevance'}]
                stack.enter_context(patch.object(d,'components',return_value=(cases,lambda c:[],lambda c,r:{'passed':True})))
            else:
                stack.enter_context(patch.object(d,'grader',return_value=(lambda c,p:{'passed':True},lambda *a:'pass')))
            result=d.run(args)
            self.assertEqual(json.loads((path/'manifest.json').read_text())['execution']['api_timeout_seconds'],seconds)
            completion=[timeout for route,timeout in calls if route=='/v1/chat/completions']
            self.assertTrue(completion);self.assertEqual(set(completion),{seconds})
            if name=='bfcl':self.assertEqual({timeout for route,timeout in calls if route!='/v1/chat/completions'},{30})

if __name__=='__main__':unittest.main()
