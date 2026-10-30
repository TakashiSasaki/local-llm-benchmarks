import argparse,contextlib,importlib.util,io,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.study import create_run,load

@unittest.skipUnless(sys.platform=='win32','The original grading worker uses Windows job limits')
class HumanEvalReplay(unittest.TestCase):
    def test_saved_qwen_off_matches_original_score(self):
        s=importlib.util.spec_from_file_location('he_driver',ROOT/'benchmarks/humaneval.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
        source=ROOT/'artifacts/local-llm/runs/bench64k-output-20261030-141002'
        original=load(source/'results.json')['models']['qwen-large']['human_eval']['off']
        records=[load(source/('qwen-large-off-'+e['task_id'].replace('/','_')+'.json')) for e in original];requests=[]
        alias=records[0]['request']['model']
        def serve(req,timeout=None):
            payload=json.loads(req.data) if req.data else None
            route=req.full_url.removeprefix('http://127.0.0.1:8089')
            if route=='/props':v={'model_alias':alias,'total_slots':1,'default_generation_settings':{'n_ctx':65536},'build_info':'replay-only'}
            elif route=='/apply-template':v={'prompt':'Replay fixture'}
            elif route=='/tokenize':v={'tokens':[0]*200}
            else:
                expected=records[len(requests)];self.assertEqual(payload,expected['request']);requests.append(payload);v=expected['response']
            return io.BytesIO(json.dumps(v).encode())
        with tempfile.TemporaryDirectory() as tmp:
            path=create_run('HumanEval saved response replay','humaneval',run_id='replay',root=pathlib.Path(tmp),kind='replay')
            args=argparse.Namespace(run='replay',endpoint='http://127.0.0.1:8089',model=alias,thinking='off')
            with patch.object(d,'resolve_run',return_value=path),patch('urllib.request.urlopen',side_effect=serve),contextlib.redirect_stdout(io.StringIO()):summary=d.run(args)
            self.assertEqual((summary['passed'],summary['attempted']),(17,20));self.assertEqual(len(requests),20)
            self.assertEqual([e['passed'] for e in load(path/'summaries/cases.json')],[e['passed'] for e in original])

if __name__=='__main__':unittest.main()
