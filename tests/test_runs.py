import argparse,importlib.util,io,json,pathlib,sys,tempfile,unittest,urllib.error
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.study import create_run,resolve_run,load,validate_run,save,sha,snapshot_sources
spec=importlib.util.spec_from_file_location('bfcl_driver',ROOT/'benchmarks/bfcl.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
class Runs(unittest.TestCase):
    def test_hermes_sources_and_artifact_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            fixture=root/'integrations/hermes/fixtures/test.json';save(fixture,{'amounts':[1,2]})
            driver=root/'integrations/hermes/scripts/check.py';driver.parent.mkdir(parents=True);driver.write_text('pass\n',encoding='utf-8')
            path=create_run('Hermes trial','file-tools',run_id='hermes-trial',root=root,experiment_type='harness-integration',harness='hermes')
            snapshot_sources(path,root)
            self.assertEqual(load(path/'source-manifest.json')['files']['integrations/hermes/fixtures/test.json'],sha(fixture))
            self.assertTrue((path/'source/integrations/hermes/scripts/check.py').exists())
            self.assertTrue((path/'workspace').is_dir());self.assertEqual(validate_run(path)['harness'],'hermes')
            artifact=path/'workspace/output.json';save(artifact,{'total':3})
            m=load(path/'manifest.json');m['evidence']=[{'path':artifact.relative_to(root).as_posix(),'sha256':sha(artifact)}];save(path/'manifest.json',m)
            validate_run(path);save(artifact,{'total':999})
            with self.assertRaises(AssertionError):validate_run(path)
    def test_invalid_experiment_type_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            with self.assertRaises(ValueError):create_run('Bad','generic',root=root,experiment_type='unknown')
            self.assertEqual(list(root.iterdir()),[])
    def test_run_paths_and_immutability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);p=create_run('Test','generic',run_id='safe-run',root=root,kind='replay')
            self.assertEqual(validate_run(p)['status'],'planned')
            with self.assertRaises(FileExistsError):create_run('Test','generic',run_id='safe-run',root=root)
            for bad in ['../outside','/absolute','a/b','..']:
                with self.assertRaises(ValueError):resolve_run(bad,root)
    def test_recorded_response_replay_and_resume(self):
        source=ROOT/'artifacts/local-llm/runs/qwen35-bfcl-thinking-20261030-194028'
        cases=load(source/'selected-bfcl.json');records=[load(source/('on-'+c['problem']['id']+'.json')) for c in cases]
        self.assertEqual(len(records),80);props=load(source/'props.json');success=[];failed_once=[False]
        def open_mock(req,timeout=None):
            payload=json.loads(req.data) if req.data else None;route=req.full_url.split('http://127.0.0.1:8089')[-1]
            if route=='/props':value=props
            elif route=='/apply-template':value={'prompt':'Replay-only template fixture'}
            elif route=='/tokenize':value={'tokens':[0]*200}
            elif payload['max_tokens']==512:value={'choices':[{'message':{'content':'391','reasoning_content':'17*23=391'},'finish_reason':'stop'}]}
            else:
                index=len(success);self.assertEqual(payload,records[index]['request'])
                if len(success)==2 and not failed_once[0]:failed_once[0]=True;raise urllib.error.URLError('Synthetic interrupted request')
                success.append(cases[index]['problem']['id']);value=records[index]['response']
            return io.BytesIO(json.dumps(value).encode())
        with tempfile.TemporaryDirectory() as tmp:
            path=create_run('Replay test','bfcl',run_id='test-replay',root=pathlib.Path(tmp),kind='replay')
            args=argparse.Namespace(run=path.name,endpoint='http://127.0.0.1:8089',model=props['model_alias'],thinking='on',mode_control='native',context=65536,max_output=64000)
            with patch.object(driver,'resolve_run',return_value=path),patch('urllib.request.urlopen',side_effect=open_mock),patch('builtins.print'):
                with self.assertRaises(urllib.error.URLError):driver.run(args)
                self.assertEqual(load(path/'manifest.json')['status'],'failed');self.assertEqual(len(list((path/'raw').glob('*.json'))),2)
                result=driver.run(args)
                self.assertEqual((result['passed'],result['attempted'],result['output_cap_hits']),(72,80,2))
                self.assertEqual(len(success),80);self.assertEqual(len(set(success)),80)
                self.assertEqual(validate_run(path)['status'],'complete')
                with self.assertRaises(ValueError):driver.run(args)
    def test_too_small_context_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=create_run('Replay context','bfcl',run_id='test-context',root=pathlib.Path(tmp),kind='replay')
            args=argparse.Namespace(run=path.name,endpoint='http://127.0.0.1:8089',model='m',thinking='on',mode_control='native',context=65536,max_output=64000)
            response={'default_generation_settings':{'n_ctx':16384},'total_slots':1,'model_alias':'m'}
            with patch.object(driver,'resolve_run',return_value=path),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaises(ValueError):driver.run(args)
if __name__=='__main__':unittest.main()
