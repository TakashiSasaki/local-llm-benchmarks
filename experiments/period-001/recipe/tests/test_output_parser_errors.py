"""Malformed model output must fail even no-call questions; infrastructure errors still abort."""
import argparse,contextlib,importlib.util,io,json,pathlib,sys,tempfile,unittest,urllib.error
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.study import create_run,load
from local_llm_benchmarks.output_errors import read_output_parser_error,is_output_parser_error

ERROR={'error':{'code':500,'message':'The model produced output that does not match the expected peg-native format','type':'server_error'}}
def http_error(code=500,body=ERROR):return urllib.error.HTTPError('http://localhost/test',code,'test',{},io.BytesIO(json.dumps(body).encode()))
def driver(name):
    spec=importlib.util.spec_from_file_location('test_'+name,ROOT/'benchmarks'/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class OutputErrors(unittest.TestCase):
    def test_report_excludes_rejected_output_from_empty_and_token_totals(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        import report_mtp_pair as report
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);parent=root/'runs/fixture';child=root/'runs/fixture-bfcl-off';(child/'raw').mkdir(parents=True);parent.mkdir()
            def write(path,value):path.write_text(json.dumps(value),encoding='utf-8')
            write(parent/'manifest.json',{'status':'complete','config':{'model':{'model':'fixture','quantization':'Q4_K_M'},'profile':{'mtp':'off'}}})
            write(child/'summary.json',{'passed':0,'attempted':2,'expected':80})
            write(child/'raw/error.json',{'response':ERROR,'http_status':500,'request':{'max_tokens':64000},'seconds':1})
            write(child/'raw/empty.json',{'response':{'choices':[{'message':{'content':''},'finish_reason':'stop'}],'usage':{'completion_tokens':3}},'request':{'max_tokens':64000},'seconds':2})
            with patch.object(report,'ROOT',root),patch.object(report,'resolve_run',return_value=parent):cell=report.cell('fixture')
            self.assertEqual(cell['metrics']['bfcl_off']['completion_tokens'],3)
            self.assertEqual(len(cell['empty_responses']),1);self.assertEqual(cell['truncations'],[])
            self.assertEqual(len(cell['output_parser_errors']),1)
            self.assertIsNone(cell['output_parser_errors'][0]['completion_tokens'])
            (child/'summary.json').unlink();(child/'summaries').mkdir()
            write(child/'summaries/bfcl-cases.json',[{'passed':True},{'passed':False,'server_output_parser_error':True}])
            write(child/'manifest.json',{'status':'failed','error':'timeout'})
            with patch.object(report,'ROOT',root),patch.object(report,'resolve_run',return_value=parent):partial=report.cell('fixture')
            self.assertNotIn('bfcl_off',partial['metrics'])
            incomplete=partial['incomplete_conditions'][0]
            self.assertEqual((incomplete['saved_records'],incomplete['correct_saved_records'],incomplete['server_output_parser_errors_saved']),(2,1,1))

    def test_only_explicit_parser_rejection_is_accepted(self):
        self.assertEqual(read_output_parser_error(http_error()),ERROR)
        for code,body in [(429,ERROR),(500,{'error':{'code':500,'message':'CUDA out of memory'}}),(500,{'error':{'code':400,'message':ERROR['error']['message']}})]:
            with self.subTest(code=code,body=body),self.assertRaises(urllib.error.HTTPError):read_output_parser_error(http_error(code,body))
        self.assertFalse(is_output_parser_error({'response':ERROR}))

    def collect(self,name,enabled=True,error_body=ERROR):
        module=driver(name);calls=[]
        def serve(req,timeout=None):
            payload=json.loads(req.data) if req.data else None;route=req.full_url.split(':8089')[-1]
            if route=='/props':v={'model_alias':'fixture','total_slots':1,'default_generation_settings':{'n_ctx':65536},'build_info':'fixture'}
            elif route=='/apply-template':v={'prompt':'fixture'}
            elif route=='/tokenize':v={'tokens':[0]*100}
            elif payload['max_tokens']==512:v={'choices':[{'message':{'content':'391'}}]}
            else:
                calls.append(payload)
                # Reject every BFCL irrelevance item; these must not turn into valid no-calls.
                reject=name=='humaneval' and len(calls)==1
                if name=='bfcl':reject=len(calls)>60
                if reject:raise http_error(body=error_body)
                v={'choices':[{'message':{'content':''},'finish_reason':'stop'}],'usage':{'completion_tokens':1,'total_tokens':101}}
            return io.BytesIO(json.dumps(v).encode())
        with tempfile.TemporaryDirectory() as directory:
            path=create_run('fixture',name,run_id='fixture',root=pathlib.Path(directory),kind='replay')
            args=argparse.Namespace(run='fixture',endpoint='http://127.0.0.1:8089',model='fixture',thinking='off',mode_control='native',context=65536,max_output=64000,continue_on_output_parser_error=enabled)
            with patch.object(module,'resolve_run',return_value=path),patch.object(module,'snapshot_sources'),patch('urllib.request.urlopen',side_effect=serve),contextlib.redirect_stdout(io.StringIO()):
                if name=='humaneval':
                    with patch.object(module,'grader',return_value=(lambda code,p:{'passed':True,'status':'passed'},lambda *args:'')):summary=module.run(args)
                else:summary=module.run(args)
            entries=load(path/('summaries/bfcl-cases.json' if name=='bfcl' else 'summaries/cases.json'))
            failures=[e for e in entries if e.get('server_output_parser_error')]
            self.assertTrue(all(e['passed'] is False and e['usage'] is None and e['reasoning_observed'] is None and e['finish_reason'] is None for e in failures))
            for entry in failures:
                cid=(entry.get('id') or entry['task_id']).replace('/','_');raw=load(path/'raw'/(cid+'.json'))
                self.assertEqual(raw['response'],ERROR);self.assertEqual(raw['http_status'],500)
            return summary,entries

    def test_bfcl_collects_all_and_no_call_parser_errors_fail(self):
        summary,entries=self.collect('bfcl')
        self.assertEqual(summary['attempted'],80);self.assertEqual(summary['server_output_parser_errors'],20)
        self.assertEqual(summary['categories']['irrelevance']['passed'],0)
        self.assertEqual(summary['unavailable_response_stats_cases'],20)

    def test_humaneval_keeps_missing_statistics_unknown(self):
        summary,entries=self.collect('humaneval')
        self.assertEqual(summary['attempted'],20);self.assertEqual(summary['server_output_parser_errors'],1)
        self.assertEqual(entries[0]['status'],'server_output_parser_error')

    def test_default_and_infrastructure_error_still_abort(self):
        with self.assertRaises(urllib.error.HTTPError):self.collect('bfcl',enabled=False)
        with self.assertRaises(urllib.error.HTTPError):self.collect('bfcl',error_body={'error':{'code':500,'message':'CUDA out of memory'}})

if __name__=='__main__':unittest.main()
