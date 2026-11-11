"""Offline validation of immutable BFCL timeout references."""
import argparse, copy, importlib.util, io, json, pathlib, sys, tempfile, unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.bfcl_subset import make_plan,select,combined_score,positive_timeout,validate_target
from local_llm_benchmarks.study import load,sha

class BFCLSubset(unittest.TestCase):
    def setUp(self):
        self.plan=make_plan({'reason':'timeout extension','authorization':'user requested resuming timed-out question'})
        self.cases=load(ROOT/'datasets/bfcl/6ea5797/selected-80.json')

    def test_exact_seven_pending(self):
        pending=select(self.cases,self.plan)
        self.assertEqual(len(pending),7)
        self.assertEqual(pending[0]['problem']['id'],'irrelevance_139')
        self.assertEqual(len(self.plan['reference_saved_ids']),73)

    def test_reject_tampering_overlap_and_order(self):
        bad=[]
        for field in ['source_manifest_sha256','source_cases_sha256','source_snapshot_sha256','model_sha256']:
            p=copy.deepcopy(self.plan);p[field]='0'*64;bad.append(p)
        p=copy.deepcopy(self.plan);p['pending_ids'].reverse();bad.append(p)
        p=copy.deepcopy(self.plan);p['pending_ids'][0]=p['reference_saved_ids'][0];bad.append(p)
        p=copy.deepcopy(self.plan);p['reference_saved_ids'].reverse();bad.append(p)
        p=copy.deepcopy(self.plan);p['reference_raw_sha256'][p['reference_saved_ids'][0]]='0'*64;bad.append(p)
        p=copy.deepcopy(self.plan);p['timeout_policy_change']={};bad.append(p)
        p=copy.deepcopy(self.plan);p['api_timeout_seconds']=7200;bad.append(p)
        p=copy.deepcopy(self.plan);p['parent_evidence_sha256']['cleanup.json']='0'*64;bad.append(p)
        for p in bad:
            with self.subTest(p=p),self.assertRaises(ValueError):select(self.cases,p)

    def test_combined_reference_only(self):
        pending=select(self.cases,self.plan)
        new=[{'id':c['problem']['id'],'passed':True,'category':c['category']} for c in pending]
        score=combined_score(self.cases,self.plan,new)
        saved=load(ROOT/'runs'/self.plan['source_run']/'summaries/bfcl-cases.json')
        self.assertEqual(score['passed'],sum(e['passed'] for e in saved)+7)
        self.assertEqual((score['expected'],score['referenced_answers'],score['new_answers']),(80,73,7))
        self.assertEqual(score['categories']['irrelevance']['attempted'],20)
        with self.assertRaises(ValueError):combined_score(self.cases,self.plan,new[::-1])

    def test_valid_subset_collects_only_seven_and_separate_score(self):
        spec=importlib.util.spec_from_file_location('bfcl_seven_driver',ROOT/'benchmarks/bfcl.py')
        driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        source=load(ROOT/'runs'/self.plan['source_run']/'manifest.json')
        calls=[]
        def urlopen(req,timeout):
            route=req.full_url.split('8089')[-1]
            if route=='/props':data={'model_alias':source['execution']['model'],'default_generation_settings':{'n_ctx':65536},'total_slots':1,'build_info':source['runtime_build']}
            elif route=='/apply-template':data={'prompt':'test'}
            elif route=='/tokenize':data={'tokens':[1]}
            else:
                calls.append((json.loads(req.data),timeout))
                data={'choices':[{'message':{'content':'done','reasoning_content':'test'},'finish_reason':'stop'}],'usage':{}}
            return io.StringIO(json.dumps(data))
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)
            manifest=copy.deepcopy(source);manifest.pop('execution');manifest['status']='planned'
            manifest['config']['profile']['benchmark_extra_args']=['--api-timeout-seconds','14400']
            (path/'manifest.json').write_text(json.dumps(manifest))
            planfile=path/'plan.json';planfile.write_text(json.dumps(self.plan))
            args=argparse.Namespace(run='unused',model=source['execution']['model'],thinking='on',endpoint=source['execution']['endpoint'],mode_control='native',context=65536,max_output=64000,subset_plan=planfile,api_timeout_seconds=14400)
            with patch.object(driver,'resolve_run',return_value=path),patch.object(driver,'assert_run_writable'),patch.object(driver,'snapshot_sources'),patch.object(driver,'require'),patch.object(driver,'components',return_value=(self.cases,lambda c:[],lambda c,r:{'passed':True})),patch.object(driver.urllib.request,'urlopen',side_effect=urlopen):
                result=driver.run(args)
            self.assertEqual(len(calls),8)  # Seven fresh answers plus the unchanged mode warmup.
            self.assertEqual({timeout for _,timeout in calls},{14400})
            self.assertEqual({p.stem for p in (path/'raw').glob('*.json')},set(self.plan['pending_ids']))
            self.assertEqual((result['attempted'],result['expected']),(7,7))
            self.assertEqual(result['categories']['irrelevance']['attempted'],7)
            self.assertEqual(result['categories']['simple_python']['attempted'],0)
            self.assertEqual(result['combined_reference_score']['expected'],80)
            self.assertEqual(result['combined_reference_score']['referenced_answers'],73)

    def test_invalid_plan_no_network_no_source_mutation(self):
        spec=importlib.util.spec_from_file_location('bfcl_subset_driver',ROOT/'benchmarks/bfcl.py')
        driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        source=ROOT/'runs'/self.plan['source_run']
        before={str(p):sha(p) for p in source.rglob('*') if p.is_file()}
        plan=copy.deepcopy(self.plan);plan['pending_ids'].reverse()
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp);(path/'manifest.json').write_text('{"status":"planned"}')
            planfile=path/'plan.json';planfile.write_text(json.dumps(plan))
            args=argparse.Namespace(run='unused',model='unused',thinking='on',endpoint='http://localhost:8089',mode_control='native',context=65536,max_output=64000,subset_plan=planfile,api_timeout_seconds=14400)
            with patch.object(driver,'resolve_run',return_value=path),patch.object(driver,'assert_run_writable'),patch.object(driver,'components',return_value=(self.cases,None,None)),patch.object(driver.urllib.request,'urlopen') as api,patch.object(driver,'save') as save,patch.object(driver,'snapshot_sources') as snapshot:
                with self.assertRaises(ValueError):driver.run(args)
                api.assert_not_called();save.assert_not_called();snapshot.assert_not_called()
        self.assertEqual(before,{str(p):sha(p) for p in source.rglob('*') if p.is_file()})

if __name__=='__main__':unittest.main()
