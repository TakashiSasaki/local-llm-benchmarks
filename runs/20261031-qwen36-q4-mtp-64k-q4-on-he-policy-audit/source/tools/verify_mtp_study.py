"""Check saved MTP trials, fixed-length outputs and official BFCL grades; no inference."""
import argparse, collections, gzip, hashlib, importlib.util, json, pathlib, random, statistics, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,validate_run,save,sha
from local_llm_benchmarks.bfcl import components

def verify(prefix):
    dataset=ROOT/'datasets/mtp-speed/v1';dm=load(dataset/'manifest.json');assert hashlib.sha256((dataset/'prompts.json').read_bytes()).hexdigest()==dm['files']['prompts.json']
    prompts={p['id']:p['prompt'] for p in load(dataset/'prompts.json')}
    cases,convert,grade=components();count=0;cells=[]
    root=ROOT/'runs'/prefix;root_manifest=validate_run(root);assert root_manifest['status']=='complete'
    definition=root_manifest['config'];cell_runs=definition.get('cell_runs',{})
    pair_only=definition.get('study_type')=='mtp-pair'
    expected_cells=2 if pair_only else 4
    expected_answers=expected_cells*200
    rows=[json.loads(s) for s in gzip.decompress((ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
    problems=[rows[i] for i in sorted(random.Random(42).sample(range(len(rows)),20))]
    spec=importlib.util.spec_from_file_location('humaneval_evidence_check',ROOT/'benchmarks/humaneval.py');he=importlib.util.module_from_spec(spec);spec.loader.exec_module(he);unused,unwrap=he.grader()
    template_hashes=[]
    for quant in (['q4'] if pair_only else ['q4','iq3']):
        for mtp in ['off','on']:
            parent=ROOT/'runs'/cell_runs.get(quant+'-'+mtp,prefix+'-'+quant+'-'+mtp);m=validate_run(parent);assert m['status']=='complete'
            cfg=m['config'];profile=cfg['profile'];args=profile['server_args']
            assert args[args.index('--n-cpu-moe')+1]=='34'
            assert args[args.index('--spec-type')+1]==('draft-mtp' if mtp=='on' else 'none')
            if mtp=='on':
                for key,value in {'--spec-draft-n-max':'3','--spec-draft-p-min':'0','--spec-draft-ngl':'all','--spec-draft-n-ubatch':'128','--spec-draft-type-k':'f16','--spec-draft-type-v':'f16'}.items():assert args[args.index(key)+1]==value
            props=load(parent/'configs/server-props.json');assert props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
            assert props['build_info']=='b11960-8642541b2';template_hashes.append(props['chat_template'])
            for key,value in {'-ctk':'f16','-ctv':'f16','-np':'1','-c':'65536','-t':'8'}.items():assert args[args.index(key)+1]==value
            if quant=='q4' and definition.get('q4_load_mode'):assert args[args.index('--load-mode')+1]==definition['q4_load_mode']
            verified=load(parent/'configs/model-file-verification.json')
            assert verified['verified'] and verified['bytes']==cfg['model']['bytes']
            assert cfg['model']['sha256']==profile['model_hash']==verified['sha256']
            clean=load(parent/'configs/cleanup.json');assert clean['server_stopped'] and not clean['resource_guard']
            speed=ROOT/'runs'/(parent.name+'-speed');sm=validate_run(speed);assert sm['status']=='complete'
            raw=[load(f) for f in sorted((speed/'raw').glob('*.json')) if f.name!='warmup.json'];assert len(raw)==9
            assert collections.Counter(r['prompt_id'] for r in raw)=={name:3 for name in prompts}
            assert all(r['response']['timings']['predicted_n']==256 and r['request']['ignore_eos'] and r['request']['temperature']==0 and r['request']['cache_prompt'] is False for r in raw)
            assert all(r['response']['timings']['cache_n']==0 and prompts[r['prompt_id']] in r['request']['prompt'] for r in raw)
            assert all(len(r['response']['tokens'])==256 for r in raw)
            assert all(all(r['request'][key]==value for key,value in {'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'seed':42,'n_predict':256,'stream':False}.items()) for r in raw)
            drafted=sum(r['response']['timings'].get('draft_n',0) for r in raw);accepted=sum(r['response']['timings'].get('draft_n_accepted',0) for r in raw)
            assert (drafted>0)==(mtp=='on') and 0<=accepted<=drafted
            summary=load(speed/'summary.json');assert summary['draft_tokens']==drafted and summary['accepted_draft_tokens']==accepted
            assert summary['median_decode_tokens_per_second']==statistics.median(r['response']['timings']['predicted_per_second'] for r in raw)
            scores={}
            for suite in ['bfcl','humaneval']:
                for thinking in ['off','on']:
                    child=ROOT/'runs'/(parent.name+'-'+suite+'-'+thinking);cm=validate_run(child);assert cm['status']=='complete'
                    assert cm['runtime_build']==props['build_info']
                    entries=load(child/('summaries/bfcl-cases.json' if suite=='bfcl' else 'summaries/cases.json'));assert len(entries)==(80 if suite=='bfcl' else 20)
                    if suite=='humaneval':assert all(c['passed'] for c in load(child/'configs/canonical-controls.json'))
                    actual_caps=0;native_drafts=0;observed_reasoning=0
                    for i,e in enumerate(entries):
                        cid=e.get('id') or e['task_id'];r=load(child/'raw'/(cid.replace('/','_')+'.json'));req=r['request'];resp=r['response']
                        assert req['chat_template_kwargs']['enable_thinking']==(thinking=='on') and req['model']==profile['profile_id']
                        expected_sampling={'top_p':1 if suite=='bfcl' else 0.95,'top_k':0 if suite=='bfcl' else 20,'min_p':0,'repeat_penalty':1,'seed':42,'cache_prompt':False}
                        assert all(req[key]==value for key,value in expected_sampling.items())
                        if suite=='humaneval':assert req['presence_penalty']==0
                        assert req['max_tokens']==min(64000,65536-r['estimated_prompt_tokens']-32)
                        assert resp['usage']['total_tokens']<=65536 and resp['usage']==e['usage']
                        assert e['seconds']==r['seconds']
                        observed=bool((resp['choices'][0]['message'].get('reasoning_content') or '').strip())
                        assert e['reasoning_observed']==observed
                        observed_reasoning+=observed
                        actual_caps+=resp['choices'][0]['finish_reason']=='length'
                        native_drafts+=resp.get('timings',{}).get('draft_n',0)
                        if suite=='bfcl':
                            assert cid==cases[i]['problem']['id'] and req['tools']==convert(cases[i]) and req['messages']==cases[i]['problem']['question'][0] and req['temperature']==0
                            out=grade(cases[i],resp);assert (out['passed'],out['decoded'])==(e['passed'],e['decoded']);count+=1
                        else:
                            p=problems[i];assert cid==p['task_id'] and req['messages'][1]['content']==p['prompt'] and req['temperature']==0.6
                            content=resp['choices'][0]['message'].get('content') or '';expected=unwrap(content,p['prompt'],p['entry_point']) if content.strip() else ''
                            assert e['code']==expected
                    s=load(child/'summary.json');assert s['passed']==sum(e['passed'] for e in entries) and s['attempted']==len(entries)
                    assert s['output_cap_hits']==actual_caps and (native_drafts>0)==(mtp=='on')
                    assert s['reasoning_observed_cases']==observed_reasoning
                    if suite=='humaneval':assert s['grading_python'].startswith('3.14.9 ')
                    scores[suite+'_'+thinking]={'passed':s['passed'],'attempted':s['attempted'],'caps':s['output_cap_hits']}
            audit=ROOT/'runs'/(parent.name+'-he-policy-audit')
            if pair_only:assert audit.exists(),'Completed pair must include its declared secondary audits'
            if audit.exists():
                am=validate_run(audit);assert am['kind']=='replay' and am['status']=='complete' and am['config']['model']['sha256']==cfg['model']['sha256']
                ar=load(audit/'summaries/results.json')
                baseline=load(ROOT/ar['baseline_reference'])
                assert ar['worker_sha256']==sha(audit/'grade_worker.py')==baseline['secondary_worker_sha256'] and all(c['passed'] for c in ar['canonical'])
                for mode in ['off','on']:
                    v=ar['iq3_m'][mode];assert v['original_passed']==scores['humaneval_'+mode]['passed'] and v['secondary_passed']==sum(c['secondary']['passed'] for c in v['cases'])
                    assert [c['task_id'] for c in v['cases']]==[p['task_id'] for p in problems]
            cells.append({'run':parent.name,'scores':scores,'draft_tokens':drafted,'accepted_draft_tokens':accepted})
    assert len(set(template_hashes))==1
    report=load(ROOT/'reports'/prefix/'matrix-data.json');assert len(report['cells'])==expected_cells and all(c['status']=='complete' for c in report['cells'])
    for c in report['cells']:
        checked=next(row for row in cells if row['run']==c['run'])
        for key,s in checked['scores'].items():
            assert c['metrics'][key]['passed']==s['passed'] and c['metrics'][key]['attempted']==s['attempted'] and c['metrics'][key]['output_cap_hits']==s['caps']
        assert c['speed']['draft_tokens']==checked['draft_tokens'] and c['speed']['accepted_draft_tokens']==checked['accepted_draft_tokens']
    assert sum(s['attempted'] for c in cells for s in c['scores'].values())==expected_answers
    assert len(report['truncations'])==sum(s['caps'] for c in cells for s in c['scores'].values())
    summary=load(root/'summary.json');assert summary['conditions']==expected_cells*4 and summary['answers']==expected_answers
    assert summary['new_answers']+summary['referenced_answers']==expected_answers
    if pair_only:
        reference=load(ROOT/'runs'/definition['reference_matrix']/'manifest.json')
        assert reference['status']=='complete'
        assert {c['run'] for c in report['references']}==set(reference['config']['cell_runs'].values())
        for c in report['references']:
            assert validate_run(ROOT/'runs'/c['run'])['status']=='complete'
            for key,value in c['metrics'].items():
                saved=load(ROOT/'runs'/(c['run']+'-'+key.replace('_','-'))/'summary.json')
                assert all(value[k]==saved[k] for k in ['passed','attempted','total_seconds','output_cap_hits'])
    deployment=[]
    for mtp in ['off','on']:
        parent=ROOT/'runs'/(prefix+'-iq3-cpu30-'+mtp)
        if not parent.exists():continue
        m=validate_run(parent);assert m['config']['speed_only']
        args=m['config']['profile']['server_args'];assert args[args.index('--n-cpu-moe')+1]=='30'
        assert load(parent/'configs/cleanup.json')['server_stopped']
        if m['status']=='failed':
            assert m.get('error');deployment.append({'run':parent.name,'status':'failed','error':m['error'],'speed_cases_checked':0});continue
        assert m['status']=='complete'
        speed=ROOT/'runs'/(parent.name+'-speed');assert validate_run(speed)['status']=='complete'
        rows=[load(f) for f in sorted((speed/'raw').glob('*.json')) if f.name!='warmup.json'];assert len(rows)==9
        assert collections.Counter(r['prompt_id'] for r in rows)=={name:3 for name in prompts}
        assert all(r['response']['timings']['predicted_n']==256 and r['response']['timings']['cache_n']==0 and prompts[r['prompt_id']] in r['request']['prompt'] for r in rows)
        drafted=sum(r['response']['timings'].get('draft_n',0) for r in rows);assert (drafted>0)==(mtp=='on')
        assert load(speed/'summary.json')['median_decode_tokens_per_second']==statistics.median(r['response']['timings']['predicted_per_second'] for r in rows)
        deployment.append({'run':parent.name,'status':'complete','speed_cases_checked':len(rows)})
    assert len(deployment) in (0,2)
    return {'passed':True,'cells':cells,'bfcl_raw_outputs_regraded':count,'humaneval_saved_records_checked':expected_cells*40,'fixed_length_cases':expected_cells*9,'deployment_speed':deployment,'model_inference_performed':False,'generated_code_executed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prefix',default='20261031-empero-mtp-load-none');p.add_argument('--report',type=pathlib.Path);a=p.parse_args();result=verify(a.prefix)
    if a.report:save(a.report,result)
    print(json.dumps(result))
