"""Reuse pinned HumanEval/BFCL subsets and graders for Text/VL Q4/Q8."""
import ast, copy, ctypes, datetime, gzip, hashlib, html, json, os, pathlib, random, re, statistics, subprocess, sys, threading, time, types, urllib.request, zipfile
from ctypes import wintypes as w
from pathlib import Path
import memory, server
from install_lfm3_runtime import save, sha256

ROOT=Path(r'C:\LocalLLM');BENCH=ROOT/'hermes/benchmarks';BF=BENCH/'bfcl'
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'runs'/('bench64k-output-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));OUT.mkdir(exist_ok=True)
RESUME=json.loads((OUT/'results.json').read_text(encoding='utf-8')) if (OUT/'results.json').exists() else None
source=(BENCH/'compare_models.py').read_text(encoding='utf-8')
exec(compile(source[source.index('class BasicLimits'):source.index('\ndef canonical_selfcheck')],'existing_job_grader.py','exec'),globals())
tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='unwrap_code')
exec(compile(ast.Module(body=[node],type_ignores=[]),'existing_extractor.py','exec'),globals())
ns={'__file__':str(BF/'run_comparison.py')}
bf_source=(BF/'run_comparison.py').read_text(encoding='utf-8')
exec(compile(bf_source[:bf_source.index('selfcheck=[]')],'existing_bfcl_adapter.py','exec'),ns)
bf_cases=ns['SELECTED'];bf_check=ns['check'];convert=ns['convert_to_tool']
he_ref=json.loads((BENCH/'thinking-comparison-20261029-174343/results.json').read_text(encoding='utf-8'))
bf_ref=json.loads((BF/'comparison-20261029-142528/results.json').read_text(encoding='utf-8'))
data=(BENCH/'HumanEval.jsonl.gz').read_bytes();assert hashlib.sha256(data).hexdigest()==he_ref['dataset_sha256']
rows=[json.loads(s) for s in gzip.decompress(data).decode().splitlines()]
problems=[rows[i] for i in sorted(random.Random(42).sample(range(len(rows)),20))]
assert [p['task_id'] for p in problems]==he_ref['task_ids']
assert [c['problem']['id'] for c in bf_cases]==bf_ref['selected_ids'] and ns['HASHES']==bf_ref['data_hashes']
canonical=[{'id':p['task_id'],**grade(p['prompt']+p['canonical_solution'],p)} for p in problems]
assert all(x['passed'] for x in canonical)
bf_controls=[{'id':c['problem']['id'],'golden':bf_check(c,ns['golden'](c))['valid'],'negative_rejected':not bf_check(c,[{'not_a_valid_function':{}}] if c['category']=='irrelevance' else [])['valid']} for c in bf_cases]
assert all(c['golden'] and c['negative_rejected'] for c in bf_controls)
save(OUT/'selfchecks.json',{'humaneval':canonical,'bfcl':bf_controls})
save(OUT/'selected-bfcl.json',bf_cases)
tracked=list((ROOT/'profiles').glob('*.json'))+list((ROOT/'hermes/profiles').glob('*.json'))+[ROOT/'runtime-current.json',ROOT/'model-manifest.json',ROOT/'hermes/model-manifest.json']
before={str(p):sha256(p) for p in tracked}
report={'directory':str(OUT),'started_at':datetime.datetime.now().astimezone().isoformat(),'python':sys.version,'models':{},'human_eval_reference':str(BENCH/'thinking-comparison-20261029-174343/results.json'),'bfcl_reference':str(BF/'comparison-20261029-142528/results.json'),'dataset_sha256':he_ref['dataset_sha256'],'human_eval_ids':he_ref['task_ids'],'bfcl_ids':bf_ref['selected_ids'],'bfcl_data_hashes':ns['HASHES'],'protocol':{'human_eval':he_ref['protocol'],'bfcl':bf_ref['protocol'],'runtime':'b11960 CUDA 12.4','vl_input':'Text only, no images; shared F16 projector remains loaded','order':['lfm3','lfm3-vl-q4','lfm3-q8','lfm3-vl-q8','qwen-daily','qwen-large']},'limits':['HumanEval 20 / BFCL 80 pinned selected tasks, not full leaderboard scores.','One sample per condition, fixed model order; uncontrolled background/thermal variation.','Qwen references used b11946; do not attribute cross-runtime differences solely to models.','Existing restricted HumanEval grader unchanged; guard rejection is separate from test failure.','BFCL only grades parsed function calls; no tool execution or Hermes workflow.','Requested thinking mode and observed reasoning are separately recorded.']}
report['protocol']['human_eval']={**report['protocol']['human_eval'],'max_tokens':64000,'request_timeout_seconds':3600}
report['protocol']['bfcl']={**report['protocol']['bfcl'],'max_tokens':64000,'request_timeout_seconds':3600}
report['protocol']['budget_rule']='min(64000, 65536 - rendered_input_tokens - 32); no input padding'
report['previous_4096_reference']=str(ROOT/'runs/lfm3-bench-20261030-132439/results.json')
report['limits']=[x for x in report['limits'] if not x.startswith('Qwen references')]
report['limits'].append('All six configurations are newly measured on b11960. Prior 4096-token Qwen controls used b11946.')
report['limits'].append('64K is configured capacity; actual prompts remain unchanged and short. Every request is token-counted and reserves output space.')
if RESUME:
    assert RESUME['protocol']==report['protocol'] and RESUME['human_eval_ids']==report['human_eval_ids']
    report=RESUME;report.pop('error',None)
    before=report['original_hashes']
    before.setdefault(str(ROOT/'hermes/model-manifest.json'),sha256(ROOT/'hermes/model-manifest.json'))
else:report['original_hashes']=before
save(OUT/'results.json',report)
def api(path,payload=None,timeout=3600):
    n=None
    req=urllib.request.Request('http://127.0.0.1:8089'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    if path=='/v1/chat/completions' and payload.get('max_tokens',0)>256:
        rendered=api('/apply-template',{k:v for k,v in payload.items() if k in ('messages','tools','tool_choice','parallel_tool_calls','chat_template_kwargs')},timeout=30)
        n=len(api('/tokenize',{'content':rendered['prompt'],'add_special':False},timeout=30)['tokens'])
        payload['max_tokens']=min(64000,65536-n-32)
        assert payload['max_tokens']>0
        req=urllib.request.Request('http://127.0.0.1:8089'+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:result=json.load(r)
    if n is not None:
        result['_benchmark_estimated_prompt_tokens']=n
        result['_benchmark_requested_output_tokens']=payload['max_tokens']
    return result
def info(response):
    message=response['choices'][0]['message'];reason=message.get('reasoning_content') or message.get('reasoning') or ''
    return {'content':message.get('content') or '', 'reasoning_observed':bool(reason),'reasoning_characters':len(reason),'finish_reason':response['choices'][0].get('finish_reason'),'usage':response.get('usage'),'timings':response.get('timings')}
def persist():save(OUT/'results.json',report)
def summary(entries):
    times=[x['timings'] for x in entries if x.get('timings')];tokens=sum(t.get('predicted_n',0) for t in times);ms=sum(t.get('predicted_ms',0) for t in times)
    return {'passed':sum(e['passed'] for e in entries),'attempted':len(entries),'median_seconds':statistics.median(e['seconds'] for e in entries) if entries else None,'total_seconds':sum(e['seconds'] for e in entries),'generation_tokens_per_second':tokens/ms*1000 if ms else None,'output_cap_hits':sum(e.get('finish_reason')=='length' for e in entries),'reasoning_observed_cases':sum(e.get('reasoning_observed',False) for e in entries),'failure_kinds':{kind:sum(e.get('failure_kind')==kind for e in entries) for kind in set(e.get('failure_kind') for e in entries) if kind}}
print(json.dumps({'event':'start','directory':str(OUT),'canonical_passed':20,'bfcl_controls_passed':80,'python':sys.version}),flush=True)
try:
    try:api('/props',timeout=3)
    except OSError:pass
    else:raise RuntimeError('A model is already running; refusing to replace it')
    for base in report['protocol']['order']:
        if base in report['models'] and all(len(report['models'][base]['human_eval'][mode])==20 for mode in ['off','on']) and len(report['models'][base]['bfcl'])==80:
            continue
        if base.startswith('qwen-'):
            p=json.loads((ROOT/'hermes/profiles'/(base.removeprefix('qwen-')+'.json')).read_text(encoding='utf-8'))
        else:p=copy.deepcopy(server.load_profile(base))
        lifecycle_root=ROOT/'hermes' if base.startswith('qwen-') else ROOT
        server.ROOT=lifecycle_root;state_file=lifecycle_root/'server-state.json'
        p['runtime_build']='b11960';p['runtime_executable']=str(ROOT/'bin/b11960-cuda12.4/llama-server.exe') if base.startswith('qwen-') else 'bin/b11960-cuda12.4/llama-server.exe'
        p['max_tokens']=64000;p['server_args'][p['server_args'].index('-n')+1]='64000'
        pname='bench64k-'+base;p['profile_id']='benchmark64k-'+p['profile_id']
        p['server_args']+=['--reasoning-format','deepseek','--reasoning-budget','-1']
        ppath=lifecycle_root/'profiles'/(pname+'.json');save(ppath,p)
        model=report['models'].get(base) or {'base_profile':base,'profile':p,'human_eval':{'off':[],'on':[]},'bfcl':[],'warmups':{}}
        if not any(model['human_eval'].values()) and not model['bfcl']:model['profile']=p
        model['lifecycle_root']=str(lifecycle_root)
        report['models'][base]=model;persist();monitor=None;owned=False;guard_stop=threading.Event();guard_thread=None
        try:
            # No configuration of the user's daily profiles or Hermes is changed.
            server.start(pname);owned=True
            state=json.loads(state_file.read_text(encoding='utf-8'))
            monitor=memory.Monitor(state['pid'],OUT/(base+'-memory.jsonl')).start()
            def guard_memory():
                low=0
                while not guard_stop.wait(3):
                    if not monitor.samples:continue
                    latest=monitor.samples[-1];low=low+1 if latest['available_ram_bytes']<1024**3 else 0
                    if low>=3:
                        model['resource_interruption']='Available RAM below 1 GiB for three observations; not an observed OOM';persist()
                        current=json.loads(state_file.read_text(encoding='utf-8'))
                        if current['profile']==pname and current['pid']==state['pid']:server.stop()
                        return
            guard_thread=threading.Thread(target=guard_memory,daemon=True);guard_thread.start()
            props=api('/props');save(OUT/(base+'-props.json'),props)
            assert props['model_alias']==p['profile_id'] and props['model_path']==str(ROOT/p['model']) and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
            model['runtime']=props['build_info']
            for mode in ['off','on']:
                payload={'model':p['profile_id'],'messages':[{'role':'user','content':'What is 17 times 23? Think carefully and then answer with the number.'}], 'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'repeat_penalty':1,'presence_penalty':0,'seed':42,'max_tokens':256,'chat_template_kwargs':{'enable_thinking':mode=='on'},'cache_prompt':False}
                response=api('/v1/chat/completions',payload);save(OUT/(base+'-warmup-'+mode+'.json'),response);model['warmups'][mode]=info(response)
            persist();print(json.dumps({'event':'mode_check','profile':base,'off_reasoning':model['warmups']['off']['reasoning_observed'],'on_reasoning':model['warmups']['on']['reasoning_observed']}),flush=True)
            for index,problem in enumerate(problems):
                for mode in (['off','on'] if index%2==0 else ['on','off']):
                    if any(e['task_id']==problem['task_id'] for e in model['human_eval'][mode]):continue
                    payload={'model':p['profile_id'],'messages':[{'role':'system','content':'Implement the requested Python function. Return only a complete Python module with the specified signature and required imports. Do not include explanations, markdown, or tests.'},{'role':'user','content':problem['prompt']}],'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'presence_penalty':0,'repeat_penalty':1,'seed':42,'max_tokens':64000,'chat_template_kwargs':{'enable_thinking':mode=='on'},'cache_prompt':False}
                    active={'profile':base,'phase':'humaneval','mode':mode,'task':problem['task_id'],'started_at':datetime.datetime.now().astimezone().isoformat()}
                    save(OUT/'active-request.json',active);print(json.dumps({'event':'request_start',**active}),flush=True)
                    started=time.monotonic();response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-started
                    save(OUT/(base+'-'+mode+'-'+problem['task_id'].replace('/','_')+'.json'),{'request':payload,'response':response,'seconds':elapsed})
                    item={'task_id':problem['task_id'],'mode':mode,'seconds':elapsed,**info(response)}
                    if item['content'].strip():
                        code=unwrap_code(item['content'],problem['prompt'],problem['entry_point']);outcome=grade(code,problem)
                        try:ast.parse(code);syntax=True
                        except SyntaxError:syntax=False
                        kind=None if outcome['passed'] else ('syntax_error' if not syntax else outcome['status'])
                    else:
                        code='';outcome={'passed':False,'status':'no_final_code'};kind='budget_exhausted_before_final_code' if item['finish_reason']=='length' else 'no_final_code'
                    item.update(passed=outcome['passed'],grade=outcome,code=code,failure_kind=kind);model['human_eval'][mode].append(item);persist()
                    print(json.dumps({'event':'humaneval','profile':base,'mode':mode,'task':problem['task_id'],'passed':item['passed'],'seconds':round(elapsed,2),'finish':item['finish_reason'],'reasoning':item['reasoning_observed']}),flush=True)
            for c in bf_cases:
                if any(e['id']==c['problem']['id'] for e in model['bfcl']):continue
                problem=c['problem'];tools=convert(problem['function'],ns['GORILLA_TO_OPENAPI'],ns['ModelStyle'].OPENAI_COMPLETIONS)
                payload={'model':p['profile_id'],'messages':problem['question'][0],'tools':tools,'tool_choice':'auto','parallel_tool_calls':True,'temperature':0,'seed':42,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'max_tokens':64000,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':False}}
                active={'profile':base,'phase':'bfcl','task':problem['id'],'started_at':datetime.datetime.now().astimezone().isoformat()}
                save(OUT/'active-request.json',active);print(json.dumps({'event':'request_start',**active}),flush=True)
                started=time.monotonic();response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-started
                save(OUT/(base+'-bfcl-'+problem['id']+'.json'),{'request':payload,'response':response,'seconds':elapsed})
                message=response['choices'][0]['message'];decoded=[];decode_error=None
                try:
                    for call in message.get('tool_calls') or []:
                        params=json.loads(call['function']['arguments'])
                        if not isinstance(params,dict):raise ValueError('Non-object arguments')
                        decoded.append({call['function']['name']:params})
                    outcome=bf_check(c,decoded)
                except (ValueError,KeyError,TypeError) as error:decode_error=str(error);outcome={'valid':False,'error':[str(error)]}
                item={'id':problem['id'],'category':c['category'],'seconds':elapsed,**info(response),'passed':outcome['valid'],'grade':outcome,'decoded':decoded,'decode_error':decode_error,'failure_kind':None if outcome['valid'] else ('malformed_call' if decode_error else 'ast_mismatch')}
                model['bfcl'].append(item);persist()
                print(json.dumps({'event':'bfcl','profile':base,'done':len(model['bfcl']),'id':problem['id'],'passed':item['passed'],'seconds':round(elapsed,2)}),flush=True)
            model['summary']={'human_eval':{mode:summary(entries) for mode,entries in model['human_eval'].items()},'bfcl':summary(model['bfcl']),'bfcl_categories':{cat:summary([x for x in model['bfcl'] if x['category']==cat]) for cat in ns['CATEGORIES']}}
        finally:
            guard_stop.set()
            if guard_thread:guard_thread.join(6)
            if monitor:model['memory']=monitor.stop()
            statepath=state_file
            if statepath.exists():
                state=json.loads(statepath.read_text(encoding='utf-8'))
                if state.get('profile')==pname:server.stop();model['test_server_stopped']=True
            persist()
        print(json.dumps({'event':'model_complete','profile':base,'summary':model['summary']}),flush=True)
except Exception as error:
    report['error']=repr(error);raise
finally:
    report['settings_unchanged']={path:sha256(Path(path))==digest for path,digest in before.items()}
    report['finished_at']=datetime.datetime.now().astimezone().isoformat();persist()
    with zipfile.ZipFile(OUT/'sources.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in [Path(__file__),BENCH/'compare_models.py',BENCH/'grade_worker.py',BF/'run_comparison.py',BF/'handler_utils.py',BF/'bfcl_eval/eval_checker/ast_eval/ast_checker.py',ROOT/'model-manifest.json',ROOT/'hermes/model-manifest.json',ROOT/'scripts/server.py',ROOT/'bin/b11960-cuda12.4/runtime-manifest.json']:
            z.write(path,str(path.relative_to(ROOT)))
print(json.dumps({'event':'complete','report':str(OUT/'results.json')}),flush=True)
