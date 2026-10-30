"""Add the two previously evaluated checkpoints to the pinned 64K text suite."""
import ast,copy,ctypes,datetime,gzip,hashlib,json,pathlib,random,socket,statistics,subprocess,sys,threading,time,urllib.request,zipfile
from ctypes import wintypes as w
from pathlib import Path
import memory,server
from install_lfm3_runtime import save,sha256
ROOT=Path(r'C:\LocalLLM');BENCH=ROOT/'hermes/benchmarks';BF=BENCH/'bfcl'
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'runs'/('legacy-models-64k-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
OUT.mkdir(exist_ok=True)
RESUME=json.loads((OUT/'results.json').read_text(encoding='utf-8')) if (OUT/'results.json').exists() else None
reference=ROOT/'runs/bench64k-output-20261030-141002/results.json'
ref=json.loads(reference.read_text(encoding='utf-8'))
assert 'error' not in ref and len(ref['models'])==6
source=(BENCH/'compare_models.py').read_text(encoding='utf-8')
exec(compile(source[source.index('class BasicLimits'):source.index('\ndef canonical_selfcheck')],'unchanged_windows_grader.py','exec'),globals())
tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='unwrap_code')
exec(compile(ast.Module(body=[node],type_ignores=[]),'unchanged_normalizer.py','exec'),globals())
ns={'__file__':str(BF/'run_comparison.py')};bf_source=(BF/'run_comparison.py').read_text(encoding='utf-8')
exec(compile(bf_source[:bf_source.index('selfcheck=[]')],'unchanged_bfcl_adapter.py','exec'),ns)
bf_cases=ns['SELECTED'];bf_check=ns['check'];convert=ns['convert_to_tool']
data=(BENCH/'HumanEval.jsonl.gz').read_bytes();assert hashlib.sha256(data).hexdigest()==ref['dataset_sha256']
rows=[json.loads(x) for x in gzip.decompress(data).decode().splitlines()]
problems=[rows[i] for i in sorted(random.Random(42).sample(range(len(rows)),20))]
assert [p['task_id'] for p in problems]==ref['human_eval_ids']
assert [c['problem']['id'] for c in bf_cases]==ref['bfcl_ids'] and ns['HASHES']==ref['bfcl_data_hashes']
canonical=[{'id':p['task_id'],**grade(p['prompt']+p['canonical_solution'],p)} for p in problems]
controls=[{'id':c['problem']['id'],'golden':bf_check(c,ns['golden'](c))['valid'],'negative_rejected':not bf_check(c,[{'not_a_valid_function':{}}] if c['category']=='irrelevance' else [])['valid']} for c in bf_cases]
assert all(c['passed'] for c in canonical) and all(c['golden'] and c['negative_rejected'] for c in controls)
save(OUT/'selfchecks.json',{'humaneval':canonical,'bfcl':controls});save(OUT/'selected-bfcl.json',bf_cases)
tracked=list((ROOT/'profiles').glob('*.json'))+list((ROOT/'hermes/profiles').glob('*.json'))+[ROOT/'runtime-current.json',ROOT/'model-manifest.json',ROOT/'hermes/model-manifest.json']
before={str(p):sha256(p) for p in tracked}
protocol=copy.deepcopy(ref['protocol']);protocol.pop('vl_input',None);protocol['order']=['lfm','glm']
protocol['human_eval']['reasoning_format']='Explicit CLI --reasoning-format deepseek'
protocol['human_eval']['mode_order']='LFM2.5 OFF then ON in separate server phases; GLM alternates by task as in the six-model reference'
protocol['mode_control']={'lfm':{'off':'CLI reasoning budget 0; embedded template ignores enable_thinking','on':'Native template with CLI reasoning budget -1'},'glm':{'off':'Embedded enable_thinking=false, CLI reasoning budget -1','on':'Embedded enable_thinking=true, CLI reasoning budget -1'}}
report={'directory':str(OUT),'started_at':datetime.datetime.now().astimezone().isoformat(),'python':sys.version,'models':{},'reference_64k':str(reference),'reference_64k_sha256':sha256(reference),'human_eval_reference':ref['human_eval_reference'],'bfcl_reference':ref['bfcl_reference'],'dataset_sha256':ref['dataset_sha256'],'human_eval_ids':ref['human_eval_ids'],'bfcl_ids':ref['bfcl_ids'],'bfcl_data_hashes':ref['bfcl_data_hashes'],'protocol':protocol,'original_hashes':before,'runner_sha256':sha256(Path(__file__)),'limits':ref['limits']+['New measurements only for LFM2.5-24B-A2B and GLM-4.7-Flash. The six reference configurations are reused, not regenerated.','LFM2.5 needs runtime-imposed zero thinking budget for OFF; its embedded template has no native enable_thinking switch. OFF/ON phases are sequential.','No historical HumanEval/BFCL baseline exists for these two checkpoints; old 16K custom-agent/log-speed results are different tests.']}
if RESUME:
    assert RESUME['protocol']==protocol and RESUME['reference_64k_sha256']==sha256(reference)
    report=RESUME;report.pop('error',None);before=report['original_hashes']
else:
    save(OUT/'runner-started.py.source.json',{'sha256':report['runner_sha256']})
    (OUT/'runner-started.py').write_bytes(Path(__file__).read_bytes())
save(OUT/'results.json',report)
def persist():save(OUT/'results.json',report)
def emit(event,**fields):print(json.dumps({'event':event,**fields}),flush=True)
def api(path,payload=None,timeout=3600):
    n=None
    if path=='/v1/chat/completions' and payload.get('max_tokens',0)>256:
        rendered=api('/apply-template',{k:v for k,v in payload.items() if k in ('messages','tools','tool_choice','parallel_tool_calls','chat_template_kwargs')},30)
        n=len(api('/tokenize',{'content':rendered['prompt'],'add_special':False},30)['tokens'])
        payload['max_tokens']=min(64000,65536-n-32);assert payload['max_tokens']>0
    req=urllib.request.Request('http://127.0.0.1:8089'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as response:result=json.load(response)
    if n is not None:result.update(_benchmark_estimated_prompt_tokens=n,_benchmark_requested_output_tokens=payload['max_tokens'])
    return result
def info(response):
    message=response['choices'][0]['message'];reason=message.get('reasoning_content') or message.get('reasoning') or ''
    return {'content':message.get('content') or '','reasoning_observed':bool(reason),'reasoning_characters':len(reason),'finish_reason':response['choices'][0].get('finish_reason'),'usage':response.get('usage'),'timings':response.get('timings')}
def stat(entries):
    times=[e['timings'] for e in entries if e.get('timings')];ms=sum(t.get('predicted_ms',0) for t in times)
    return {'passed':sum(e['passed'] for e in entries),'attempted':len(entries),'median_seconds':statistics.median(e['seconds'] for e in entries) if entries else None,'total_seconds':sum(e['seconds'] for e in entries),'generation_tokens_per_second':1000*sum(t.get('predicted_n',0) for t in times)/ms if ms else None,'output_cap_hits':sum(e.get('finish_reason')=='length' for e in entries),'reasoning_observed_cases':sum(e.get('reasoning_observed',False) for e in entries),'failure_kinds':{k:sum(e.get('failure_kind')==k for e in entries) for k in set(e.get('failure_kind') for e in entries) if k}}
def request(base,phase,mode,task,payload,fname):
    active={'profile':base,'phase':phase,'mode':mode,'task':task,'started_at':datetime.datetime.now().astimezone().isoformat()}
    save(OUT/'active-request.json',active);emit('request_start',**active)
    started=time.monotonic();response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-started
    save(OUT/fname,{'request':payload,'response':response,'seconds':elapsed})
    return response,elapsed
def merge_memory(phases):
    result={}
    for k in next(iter(phases.values())):
        values=[p[k] for p in phases.values() if p[k] is not None]
        result[k]=(sum(values) if k=='sample_count' else min(values) if k.startswith('minimum_') else max(values)) if values else None
    return result
emit('start',directory=str(OUT),canonical_passed=20,bfcl_controls_passed=80)
try:
    try:api('/props',timeout=3)
    except OSError:pass
    else:raise RuntimeError('An inference server is already running; refusing replacement')
    for base in protocol['order']:
        model=report['models'].setdefault(base,{'base_profile':base,'human_eval':{'off':[],'on':[]},'bfcl':[],'profiles':{},'props_paths':{},'warmups':{},'memory_by_phase':{},'phase_server_stopped':{},'mode_control':protocol['mode_control'][base]})
        plans=[('off',['off'],0),('on',['on'],-1)] if base=='lfm' else [('combined',['off','on'],-1)]
        for phase,modes,budget in plans:
            if all(len(model['human_eval'][mode])==20 for mode in modes) and ('off' not in modes or len(model['bfcl'])==80):continue
            p=copy.deepcopy(server.load_profile(base));p['runtime_build']='b11960';p['runtime_executable']='bin/b11960-cuda12.4/llama-server.exe'
            p['context_tokens']=65536;p['max_tokens']=64000;p['server_args'][p['server_args'].index('-c')+1]='65536'
            if '-n' in p['server_args']:p['server_args'][p['server_args'].index('-n')+1]='64000'
            else:p['server_args']+=['-n','64000']
            p['server_args']+=['--reasoning-format','deepseek','--reasoning-budget',str(budget)]
            pname='legacy64k-'+base+'-'+phase+'-'+OUT.name[-6:];p['profile_id']=pname;p['status']='Isolated b11960 64K text benchmark; not a change to the original evaluation/Hermes profiles'
            save(ROOT/'profiles'/(pname+'.json'),p)
            for mode in modes:model['profiles'][mode]=p;model['props_paths'][mode]=base+'-'+phase+'-props.json'
            model.setdefault('profile',p);persist();monitor=None;guard_stop=threading.Event();guard_thread=None;state_file=ROOT/'server-state.json'
            try:
                server.start(pname);state=json.loads(state_file.read_text(encoding='utf-8'))
                monitor=memory.Monitor(state['pid'],OUT/(base+'-'+phase+'-memory.jsonl')).start()
                def guard_memory():
                    low=0
                    while not guard_stop.wait(3):
                        if not monitor.samples:continue
                        low=low+1 if monitor.samples[-1]['available_ram_bytes']<1024**3 else 0
                        if low>=3:
                            model['resource_interruption']='Available RAM below 1 GiB for three observations; not an observed OOM';persist()
                            current=json.loads(state_file.read_text(encoding='utf-8'))
                            if current['profile']==pname and current['pid']==state['pid']:server.stop()
                            return
                guard_thread=threading.Thread(target=guard_memory,daemon=True);guard_thread.start()
                props=api('/props');save(OUT/(base+'-'+phase+'-props.json'),props)
                assert props['model_alias']==p['profile_id'] and props['model_path']==str(ROOT/p['model']) and props['total_slots']==1 and props['default_generation_settings']['n_ctx']==65536
                model['runtime']=props['build_info'];model['template_has_enable_thinking']='enable_thinking' in props['chat_template']
                if base=='lfm':
                    assert not model['template_has_enable_thinking']
                    rendered=[api('/apply-template',{'messages':[{'role':'user','content':'What is 17 times 23? Think carefully and then answer with the number.'}],'chat_template_kwargs':{'enable_thinking':v}})['prompt'] for v in [False,True]]
                    assert rendered[0]==rendered[1];model['native_flag_renders_identical_prompts']=True
                else:assert model['template_has_enable_thinking']
                for mode in modes:
                    payload={'model':p['profile_id'],'messages':[{'role':'user','content':'What is 17 times 23? Think carefully and then answer with the number.'}],'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'repeat_penalty':1,'presence_penalty':0,'seed':42,'max_tokens':256,'chat_template_kwargs':{'enable_thinking':mode=='on'},'cache_prompt':False}
                    response=api('/v1/chat/completions',payload);save(OUT/(base+'-warmup-'+mode+'.json'),response);model['warmups'][mode]=info(response)
                    assert model['warmups'][mode]['reasoning_observed']==(mode=='on'),(base,mode,model['warmups'][mode])
                    emit('mode_check',profile=base,mode=mode,reasoning=model['warmups'][mode]['reasoning_observed'],cli_budget=budget)
                persist()
                for index,problem in enumerate(problems):
                    for mode in (['off','on'] if index%2==0 else ['on','off']):
                        if mode not in modes or any(e['task_id']==problem['task_id'] for e in model['human_eval'][mode]):continue
                        payload={'model':p['profile_id'],'messages':[{'role':'system','content':'Implement the requested Python function. Return only a complete Python module with the specified signature and required imports. Do not include explanations, markdown, or tests.'},{'role':'user','content':problem['prompt']}],'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'presence_penalty':0,'repeat_penalty':1,'seed':42,'max_tokens':64000,'chat_template_kwargs':{'enable_thinking':mode=='on'},'cache_prompt':False}
                        response,elapsed=request(base,'humaneval',mode,problem['task_id'],payload,base+'-'+mode+'-'+problem['task_id'].replace('/','_')+'.json')
                        item={'task_id':problem['task_id'],'mode':mode,'seconds':elapsed,**info(response)}
                        if item['content'].strip():
                            code=unwrap_code(item['content'],problem['prompt'],problem['entry_point']);outcome=grade(code,problem)
                            try:ast.parse(code);syntax=True
                            except SyntaxError:syntax=False
                            kind=None if outcome['passed'] else ('syntax_error' if not syntax else outcome['status'])
                        else:code='';outcome={'passed':False,'status':'no_final_code'};kind='budget_exhausted_before_final_code' if item['finish_reason']=='length' else 'no_final_code'
                        item.update(passed=outcome['passed'],grade=outcome,code=code,failure_kind=kind);model['human_eval'][mode].append(item);persist()
                        emit('humaneval',profile=base,mode=mode,task=problem['task_id'],passed=item['passed'],seconds=round(elapsed,2),finish=item['finish_reason'],reasoning=item['reasoning_observed'])
                if 'off' in modes:
                    for c in bf_cases:
                        if any(e['id']==c['problem']['id'] for e in model['bfcl']):continue
                        problem=c['problem'];tools=convert(problem['function'],ns['GORILLA_TO_OPENAPI'],ns['ModelStyle'].OPENAI_COMPLETIONS)
                        payload={'model':p['profile_id'],'messages':problem['question'][0],'tools':tools,'tool_choice':'auto','parallel_tool_calls':True,'temperature':0,'seed':42,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'max_tokens':64000,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':False}}
                        response,elapsed=request(base,'bfcl','off',problem['id'],payload,base+'-bfcl-'+problem['id']+'.json')
                        message=response['choices'][0]['message'];decoded=[];decode_error=None
                        try:
                            for call in message.get('tool_calls') or []:
                                params=json.loads(call['function']['arguments'])
                                if not isinstance(params,dict):raise ValueError('Non-object arguments')
                                decoded.append({call['function']['name']:params})
                            outcome=bf_check(c,decoded)
                        except (ValueError,KeyError,TypeError) as error:decode_error=str(error);outcome={'valid':False,'error':[str(error)]}
                        item={'id':problem['id'],'category':c['category'],'seconds':elapsed,**info(response),'passed':outcome['valid'],'grade':outcome,'decoded':decoded,'decode_error':decode_error,'failure_kind':None if outcome['valid'] else ('malformed_call' if decode_error else 'ast_mismatch')}
                        model['bfcl'].append(item);persist();emit('bfcl',profile=base,done=len(model['bfcl']),task=problem['id'],passed=item['passed'],seconds=round(elapsed,2))
            finally:
                guard_stop.set()
                if guard_thread:guard_thread.join(6)
                if monitor:model['memory_by_phase'][phase]=monitor.stop();model['memory']=merge_memory(model['memory_by_phase'])
                if state_file.exists():
                    current=json.loads(state_file.read_text(encoding='utf-8'))
                    if current.get('profile')==pname:server.stop();model['phase_server_stopped'][phase]=True
                persist()
            emit('phase_complete',profile=base,phase=phase)
        model['summary']={'human_eval':{mode:stat(entries) for mode,entries in model['human_eval'].items()},'bfcl':stat(model['bfcl']),'bfcl_categories':{cat:stat([e for e in model['bfcl'] if e['category']==cat]) for cat in ns['CATEGORIES']}}
        model['test_server_stopped']=all(model['phase_server_stopped'].get(phase) for phase,_,_ in plans);persist();emit('model_complete',profile=base,summary=model['summary'])
except Exception as error:report['error']=repr(error);raise
finally:
    report['settings_unchanged']={p:sha256(Path(p))==digest for p,digest in before.items()}
    report['reference_unchanged']=sha256(reference)==report['reference_64k_sha256'];report['finished_at']=datetime.datetime.now().astimezone().isoformat();persist()
    with zipfile.ZipFile(OUT/'sources.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in [Path(__file__),ROOT/'scripts/server.py',ROOT/'scripts/memory.py',BENCH/'compare_models.py',BENCH/'grade_worker.py',BF/'run_comparison.py',BF/'handler_utils.py',BF/'bfcl_eval/eval_checker/ast_eval/ast_checker.py',ROOT/'model-manifest.json',ROOT/'bin/b11960-cuda12.4/runtime-manifest.json',ROOT/'profiles/lfm.json',ROOT/'profiles/glm.json']:
            z.write(p,str(p.relative_to(ROOT)))
        for key,m in report['models'].items():
            for mode,p in m['profiles'].items():z.writestr('measured-profiles/'+key+'-'+mode+'.json',json.dumps(p,ensure_ascii=False,indent=2))
emit('complete',report=str(OUT/'results.json'))
