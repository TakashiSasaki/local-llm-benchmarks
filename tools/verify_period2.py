"""Audit saved period-002 evidence; never contact an inference endpoint.

--regrade runs only saved HumanEval code in the pinned Windows worker. Use the
recorded benchmark Python. Reports are derived; raw runs/source are read only.
"""
import argparse,gzip,hashlib,importlib.util,json,pathlib,random,statistics,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,sha,validate_run
from local_llm_benchmarks.bfcl import components

PERIOD=ROOT/'experiments/period-002'
MODELS={
    'q35-4b-base':'period-002-stage-a-comparison-20261102-q35-4b-base',
    'q35-4b-abliterix':'period-002-stage-a-comparison-20261102-q35-4b-abliterix',
    'q35-9b-base':'period-002-core-followup-20261102-q35-9b-base',
}

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def audit(regrade=False):
    bf,convert,bgrade=components();bfmap={c['problem']['id']:c for c in bf}
    dataset=ROOT/'datasets/humaneval/b9453e8'
    for rel,digest in load(dataset/'manifest.json')['files'].items():assert sha(dataset/rel)==digest
    all_he=[json.loads(s) for s in gzip.decompress((dataset/'HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
    he=[all_he[i] for i in sorted(random.Random(42).sample(range(164),20))];hemap={p['task_id']:p for p in he}
    unwrap=module('he_driver',ROOT/'benchmarks/humaneval.py').grader()[1]
    from local_llm_benchmarks.humaneval_standard_windows import grade,provenance
    policy=provenance();validated=load(ROOT/'runs/period-002-he-policy-validation-20261102/summary.json')['policy']
    for k in ['policy','worker_sha256','adapter_sha256','timeout_seconds','process_memory_bytes','active_process_limit']:assert policy[k]==validated[k],k
    if regrade:assert sys.version==validated['python'],'Use recorded benchmark Python for primary replay'
    rows=[];seen=set();sources={};evidence={};case_rows=[];performance=[];replayed=0
    def evidence_hash(p):evidence[p.relative_to(ROOT).as_posix()]=sha(p)
    for key,parent_id in MODELS.items():
        parent=ROOT/'runs'/parent_id;validate_run(parent)
        model=load(PERIOD/'models'/(key+'.json'));verified=load(parent/'configs/model-file-verification.json')
        assert verified['sha256']==model['sha256'] and verified['bytes']==model['bytes'] and verified['verified'] is True
        runtime=load(parent/'configs/runtime-file-verification.json');assert runtime['sha256']=='81f65c6681d66099e5d48757aa2c050ba958dc43816e584f0bb4181eb7c910d8'
        for rel in ['configs/model-file-verification.json','configs/runtime-file-verification.json','summaries/memory.json','logs/memory.jsonl','configs/cleanup.json']:evidence_hash(parent/rel)
        cleanup=load(parent/'configs/cleanup.json');assert cleanup['server_stopped'] and not cleanup['resource_guard']
        mem=load(parent/'summaries/memory.json')
        samples=[json.loads(s) for s in (parent/'logs/memory.jsonl').read_text().splitlines() if s.strip()]
        assert len(samples)==mem['sample_count']
        mapping={'process_working_set_bytes':('peak_process_working_set_bytes',max),'process_private_bytes':('peak_process_private_bytes',max),'available_ram_bytes':('minimum_available_ram_bytes',min),'gpu_used_mib':('peak_gpu_used_mib_system_total',max),'gpu_temperature_c':('peak_gpu_temperature_c',max)}
        for field,(out,func) in mapping.items():assert func(s[field] for s in samples if s[field] is not None)==mem[out],(key,out)
        speed=ROOT/'runs'/(parent_id+'-speed');sp=load(speed/'summary.json')
        probes=[load(p) for p in sorted((speed/'raw').glob('*.json')) if p.name!='warmup.json']
        assert len(probes)==sp['attempted']==9
        # Speed probe stores the API response plus timing; capability rows below
        # have a separate aggregate based on API decode timings.
        rates=[p['response']['timings']['predicted_per_second'] for p in probes]
        assert statistics.median(rates)==sp['median_decode_tokens_per_second']
        assert all(p['request']['n_predict']==256 and p['request']['ignore_eos'] is True and p['request']['seed']==42 for p in probes)
        assert sp['draft_tokens']==sp['accepted_draft_tokens']==0
        assert sp['aggregate_decode_tokens_per_second']==sum(p['response']['timings']['predicted_n'] for p in probes)/(sum(p['response']['timings']['predicted_ms'] for p in probes)/1000)
        evidence_hash(speed/'summary.json')
        for p in sorted((speed/'raw').glob('*.json')):evidence_hash(p)
        performance.append({'model':key,'run':parent_id,'fixed256_median_decode_tps':sp['median_decode_tokens_per_second'],'memory_scope':'Model-run lifetime sampled every ~3 seconds, system-total GPU; not per-condition maxima','memory':mem})
        for suite,ordered in [('bfcl',[c['problem']['id'] for c in bf]),('humaneval',[p['task_id'] for p in he])]:
            for mode in ['off','on']:
                path=ROOT/'runs'/(parent_id+'-'+suite+'-'+mode);m=validate_run(path);summary=load(path/'summary.json')
                casepath=path/'summaries'/('bfcl-cases.json' if suite=='bfcl' else 'cases.json');saved=load(casepath)
                ids=[c['id' if suite=='bfcl' else 'task_id'] for c in saved]
                assert ids==ordered[:len(saved)] and len(set(ids))==len(ids)
                assert len(list((path/'raw').glob('*.json')))==len(saved)
                complete=m['status']=='complete';assert len(saved)==len(ordered) if complete else summary['outcome']=='deferred' and m['model_failure'] is False and m['stop_reason']=='execution_window_deferred'
                seconds=[];tokens=0;decode_ms=0;caps=[];empty=0;decode_errors=0;reasoning=0;legacy=0;categories={}
                for c,cid in zip(saved,ids):
                    rawpath=path/'raw'/(cid.replace('/','_')+'.json');rel=rawpath.relative_to(ROOT).as_posix();assert rel not in seen;seen.add(rel)
                    evidence_hash(rawpath);raw=load(rawpath);req=raw['request'];response=raw['response'];choice=response['choices'][0];msg=choice['message'];usage=response['usage'];sec=raw['seconds']
                    assert req['max_tokens']==min(64000,65536-raw['estimated_prompt_tokens']-32)
                    assert req['temperature']==(0 if suite=='bfcl' else 0.6) and req['seed']==42 and req['cache_prompt'] is False
                    assert req['chat_template_kwargs']=={'enable_thinking':mode=='on'}
                    assert c['usage']==usage and c['seconds']==sec and c['finish_reason']==choice['finish_reason']
                    assert usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']<=65536
                    assert c['reasoning_observed']==bool(msg.get('reasoning_content') or msg.get('reasoning'))
                    reasoning+=c['reasoning_observed'];seconds.append(sec);tokens+=usage['completion_tokens'];decode_ms+=response['timings']['predicted_ms']
                    if choice['finish_reason']=='length':caps.append(cid);assert usage['completion_tokens']==req['max_tokens']
                    empty+=not bool((msg.get('content') or '').strip() or msg.get('tool_calls'))
                    if suite=='bfcl':
                        b=bfmap[cid];out=bgrade(b,response)
                        for field in ['passed','decoded','decode_error']:assert out[field]==c[field],(path.name,cid,field)
                        assert req['messages']==b['problem']['question'][0] and req['tools']==convert(b)
                        assert {k:req[k] for k in ['top_p','top_k','min_p','repeat_penalty']}=={'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1}
                        decode_errors+=bool(out['decode_error']);cat=categories.setdefault(c['category'],{'passed':0,'saved':0});cat['passed']+=c['passed'];cat['saved']+=1
                    else:
                        p=hemap[cid];content=msg.get('content') or '';code=unwrap(content,p['prompt'],p['entry_point']) if content.strip() else ''
                        assert code==c['code'];assert req['messages'][1]=={'role':'user','content':p['prompt']}
                        assert {k:req[k] for k in ['top_p','top_k','min_p','presence_penalty','repeat_penalty']}=={'top_p':0.95,'top_k':20,'min_p':0,'presence_penalty':0,'repeat_penalty':1}
                        assert load(path/'configs/grader-policy.json')['policy']==policy['policy']
                        if regrade:
                            out=grade(code,p) if code else {'passed':False,'status':'no_final_code'}
                            assert out['passed']==c['passed'] and out['status']==c['status'],(path.name,cid,out,c['status']);replayed+=1
                        legacy+=c['legacy_replay']['passed']
                    case_rows.append({'model':key,'suite':suite,'thinking':mode,'id':cid,'passed':c['passed'],'status':c.get('status'),'category':c.get('category'),'finish_reason':choice['finish_reason'],'empty_final':not bool((msg.get('content') or '').strip() or msg.get('tool_calls')),'raw':rel})
                passed=sum(c['passed'] for c in saved)
                assert summary['attempted']==len(saved) and summary['expected']==len(ordered)
                assert summary['passed' if complete else 'passed_saved']==passed
                if complete:
                    assert summary['output_cap_hits']==len(caps) and summary['total_seconds']==sum(seconds) and summary['median_seconds']==statistics.median(seconds)
                    assert summary['reasoning_observed_cases']==reasoning
                    if suite=='humaneval':assert summary['legacy_replay_passed']==legacy
                    else:assert summary['categories']=={cat:{'passed':value['passed'],'attempted':value['saved']} for cat,value in categories.items()}
                evidence_hash(casepath);evidence_hash(path/'summary.json');evidence_hash(path/'manifest.json')
                rows.append({'model':key,'suite':suite,'thinking':mode,'run':path.name,'collection':'complete' if complete else 'deferred','saved':len(saved),'expected':len(ordered),'passed_saved':passed,'uncollected':len(ordered)-len(saved),'output_caps':caps,'empty_final_cases':empty,'decode_error_cases':decode_errors,'reasoning_observed_cases':reasoning,'total_api_seconds':sum(seconds),'median_api_seconds':statistics.median(seconds),'completion_tokens':tokens,'aggregate_decode_tps':tokens/(decode_ms/1000),'legacy_replay_passed':legacy if suite=='humaneval' else None,'categories':categories})
                if not complete:sources={'source_run':path.name,'reference_saved_ids':ids,'pending_ids':[cid for cid in ordered if cid not in ids],'reference_raw_sha256':{cid:sha(path/'raw'/(cid.replace('/','_')+'.json')) for cid in ids},'source_cases_sha256':sha(casepath)}
    assert len(seen)==588 and sum(r['uncollected'] for r in rows)==12
    assert len(rows)==12 and sum(r['collection']=='complete' for r in rows)==11
    final=load(ROOT/'runs'/sources['source_run']/'raw/HumanEval_35.json')
    assert final['response']['usage']['completion_tokens']==64000 and final['response']['usage']['prompt_tokens']==130 and final['response']['choices'][0]['finish_reason']=='length'
    return {'period':'period-002','scope':'Saved primary capability answers only; probes, controls and replay excluded','planned_answers':1600,'saved_answers':588,'uncollected_answers':1012,'conditions_complete':11,'conditions_partial':1,'conditions_unmeasured':20,'bfcl_regraded':480,'humaneval_records_verified':108,'humaneval_replayed':replayed,'new_inference_answers':0,'grader_policy':policy['policy'],'audit_python':sys.version,'conditions':rows,'model_performance':performance,'cases':case_rows,'continuation':sources,'evidence_sha256':evidence}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--regrade',action='store_true');ap.add_argument('--report',type=pathlib.Path);args=ap.parse_args();result=audit(args.regrade)
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['conditions','cases','model_performance','continuation','evidence_sha256']}))
