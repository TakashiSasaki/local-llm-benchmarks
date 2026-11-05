"""Independently audit partial Mage trials and dense-placement throughput; no inference."""
import argparse,collections,hashlib,json,pathlib,random,re,statistics,sys,gzip
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,validate_run
from local_llm_benchmarks.bfcl import components
from local_llm_benchmarks.output_errors import is_output_parser_error

Q4='20261031-mage-q4-text-64k-parser-errors-mage-text-off'
Q3='20261031-mage-q3-text-64k-q3-off'
GPU='20261031-mage-q3-text-64k-gpu-placement'

def speed(name,count=256,repeats=3):
    path=ROOT/'runs'/name;m=validate_run(path);assert m['status']=='complete'
    profile=m['config']['profile'];args=profile['server_args']
    assert profile['mtp']=='off' and args[args.index('-c')+1]=='65536'
    assert args[args.index('-ctk')+1]==args[args.index('-ctv')+1]=='f16'
    rows=[load(f) for f in sorted((path/'raw').glob('*.json')) if f.name!='warmup.json'];assert len(rows)==3*repeats
    warmup=load(path/'raw/warmup.json');assert warmup['warmup'] and warmup['response']['timings']['predicted_n']==64
    dataset=ROOT/'datasets/mtp-speed/v1';prompts={p['id']:p['prompt'] for p in load(dataset/'prompts.json')}
    assert hashlib.sha256((dataset/'prompts.json').read_bytes()).hexdigest()==load(dataset/'manifest.json')['files']['prompts.json']
    assert collections.Counter(r['prompt_id'] for r in rows)=={key:repeats for key in prompts}
    assert len({(r['prompt_id'],r['repeat']) for r in rows})==len(rows)
    saved=load(path/'summaries/speed-cases.json')
    for r,e in zip(rows,saved):
        req=r['request'];resp=r['response'];t=resp['timings']
        assert all(req[k]==v for k,v in {'n_predict':count,'temperature':0,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'seed':42,'cache_prompt':False,'ignore_eos':True,'stream':False,'return_tokens':True}.items())
        assert prompts[r['prompt_id']] in req['prompt'] and t['cache_n']==0
        assert t['predicted_n']==count and len(resp['tokens'])==count and t.get('draft_n',0)==0
        assert e['timings']==t and e['tokens']==resp['tokens'] and e['content_sha256']==hashlib.sha256(resp['content'].encode()).hexdigest()
    s=load(path/'summary.json');assert s['median_decode_tokens_per_second']==statistics.median(r['response']['timings']['predicted_per_second'] for r in rows)
    assert s['attempted']==len(rows) and s['tokens_per_case']==count
    parent=ROOT/'runs'/m['config']['parent_run'];pm=validate_run(parent)
    verified=load(parent/'configs/model-file-verification.json');assert verified['verified'] and verified['sha256']==profile['model_hash']==pm['config']['model']['sha256']
    props=load(parent/'configs/server-props.json');assert props['build_info']=='b11960-8642541b2' and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
    assert load(parent/'configs/cleanup.json')['server_stopped'] and not load(parent/'configs/cleanup.json')['resource_guard']
    return {'run':name,'cases_checked':len(rows),'ngl':int(args[args.index('-ngl')+1]),'median_tok_s':s['median_decode_tokens_per_second']}

def bfcl(name):
    p=ROOT/'runs'/name;m=validate_run(p);entries=load(p/'summaries/bfcl-cases.json');cases,convert,grade=components();errors=0;regraded=0
    assert len(list((p/'raw').glob('*.json')))==len(entries)
    for c,e in zip(cases,entries):
        assert c['problem']['id']==e['id'];r=load(p/'raw'/(e['id']+'.json'));req=r['request']
        assert req['tools']==convert(c) and req['messages']==c['problem']['question'][0]
        assert req['chat_template_kwargs']['enable_thinking']==(m['execution']['thinking']=='on')
        assert all(req[k]==v for k,v in {'temperature':0,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'seed':42,'cache_prompt':False}.items())
        assert req['max_tokens']==min(64000,65536-r['estimated_prompt_tokens']-32)
        if is_output_parser_error(r):
            assert m['execution']['output_parser_error_policy'] and e['passed'] is False and e['usage'] is None and e['reasoning_observed'] is None and e['finish_reason'] is None;errors+=1
        else:
            out=grade(c,r['response']);assert (out['passed'],out['decoded'])==(e['passed'],e['decoded']);assert e['usage']==r['response']['usage'];regraded+=1
    s=load(p/'summary.json') if (p/'summary.json').exists() else None
    if s:
        assert m['status']=='complete' and len(entries)==80 and s['passed']==sum(e['passed'] for e in entries)
        assert s['server_output_parser_errors']==errors and s['unavailable_response_stats_cases']==errors
    else:assert m['status']=='failed' and len(entries)<80
    return {'run':name,'status':m['status'],'saved_records':len(entries),'correct_saved_records':sum(e['passed'] for e in entries),'official_outputs_regraded':regraded,'parser_errors_verified':errors,'summary':s}

def verify():
    for p in (ROOT/'runs').glob('20261031-mage-*'):
        if (p/'manifest.json').exists():assert validate_run(p)['status'] in ('complete','failed')
    bf=[bfcl(Q4+'-bfcl-off'),bfcl(Q3+'-bfcl-off'),bfcl(Q3+'-bfcl-on'),bfcl('20261031-mage-q4-text-64k-mage-text-off-bfcl-off')]
    assert [(r['saved_records'],r['correct_saved_records']) for r in bf[:3]]==[(8,7),(80,19),(80,21)]
    failures=[]
    for parent,child in [(Q4,Q4+'-bfcl-off'),(Q3,Q3+'-humaneval-off')]:
        p=ROOT/'runs'/parent;cm=load(ROOT/'runs'/child/'manifest.json');assert "TimeoutError('timed out')"==cm['error']
        assert 'TimeoutError: timed out' in (p/'logs'/('bfcl-off.log' if parent==Q4 else 'humaneval-off.log')).read_text(encoding='utf-8')
        cleanup=load(p/'configs/cleanup.json');assert cleanup['server_stopped'] and not cleanup['resource_guard']
        numbers=re.findall(r'n_gen\s*=\s*(\d+)',(p/'logs/llama-server.log').read_text(encoding='utf-8'));last=int(numbers[-1]);assert last<64000
        failures.append({'parent':parent,'child':child,'error':cm['error'],'last_observed_generated_tokens':last,'api_response_for_timed_out_case_saved':False,'output_token_cap_reached':False,'ram_guard_triggered':False})
    he=ROOT/'runs'/(Q3+'-humaneval-off');assert not list((he/'raw').glob('*.json'))
    controls=load(he/'configs/canonical-controls.json');assert len(controls)==20 and all(e['passed'] for e in controls)
    rows=[json.loads(s) for s in gzip.decompress((ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()];expected=[rows[i]['task_id'] for i in sorted(random.Random(42).sample(range(164),20))]
    assert [e['task_id'] for e in controls]==expected and expected[0]=='HumanEval/6'
    assert not (ROOT/'runs'/(Q3+'-humaneval-on')).exists()
    mtp=ROOT/'runs/20261031-mage-q3-text-64k-capacity-on';assert validate_run(mtp)['status']=='failed'
    assert "model doesn't contain MTP layers" in (mtp/'logs/llama-server.log').read_text(encoding='utf-8') and load(mtp/'configs/cleanup.json')['server_stopped']
    assert not (ROOT/'runs/20261031-mage-q4-text-64k-mtp-preflight').exists()
    g=ROOT/'runs'/GPU;gs=load(g/'summary.json');plan=load(g/'manifest.json')['config']['plan'];speedchecks=[speed(Q4+'-speed'),speed(Q3+'-speed')]
    for t in gs['trials']:
        p=ROOT/'runs'/t['run'];memory=load(p/'summaries/memory.json');assert t['memory']==memory and load(p/'configs/cleanup.json')['server_stopped']
        result=speed(t['run']+'-speed',128,1);assert result['ngl']==t['ngl_including_output']
        assert t['admissible']==(t['status']=='complete' and t['exit_code']==0 and not t['resource_guard'] and memory['peak_gpu_used_mib_system_total']<=plan['maximum_peak_gpu_mib'])
        assert t['cpu_decoder_layers']==37-result['ngl'] and t['gpu_decoder_layers']==result['ngl']-1
        speedchecks.append(result)
    assert [t['ngl_including_output'] for t in gs['trials']]==[21,22,23,24]
    assert gs['selected_ngl_including_output']==max(t['ngl_including_output'] for t in gs['trials'] if t['admissible'])==23
    final=speed(gs['selected_throughput']['run']+'-speed');assert final['ngl']==23;speedchecks.append(final)
    assert gs['fixed_length_speedup']==final['median_tok_s']/speedchecks[1]['median_tok_s']
    assert gs['baseline']['run']==Q3+'-speed' and gs['baseline']['summary']==load(ROOT/'runs'/(Q3+'-speed')/'summary.json')
    assert load(ROOT/'runs'/Q4/'configs/server-props.json')['chat_template']==load(ROOT/'runs'/Q3/'configs/server-props.json')['chat_template']
    speedchecks.extend([speed('20261031-mage-q4-text-64k-mage-text-off-speed'),speed('20261031-mage-q4-text-64k-preflight-speed',128,1),speed('20261031-mage-q3-text-64k-capacity-off-speed',128,1)])
    return {'passed':True,'scope':'Saved evidence integrity; Q4/Q3 full capability collection did NOT complete. No inference or generated-code replay performed.','bfcl':bf,'failures':failures,'humaneval_canonical_controls_checked':20,'humaneval_model_answers_saved':0,'native_mtp_q3':'unsupported: model contains no MTP layers','native_mtp_q4':'not attempted','speed_checks':speedchecks,'gpu_placement':{'selected_ngl_including_output':23,'cpu_decoder_layers':14,'gpu_decoder_layers':22,'output_layer_gpu':True,'fixed_length_speedup':gs['fixed_length_speedup'],'ngl24':'short probe passed but excluded by GPU reserve policy; no claim of OOM'},'model_inference_performed':False,'generated_code_executed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=pathlib.Path,default=ROOT/'publication/mage-text-evidence-validation.json');a=p.parse_args();result=verify();save(a.report,result);print(json.dumps({'passed':True,'bfcl_records_checked':sum(r['saved_records'] for r in result['bfcl']),'speed_cases_checked':sum(r['cases_checked'] for r in result['speed_checks'])}))
