"""Validate raw-prompt completion compatibility without executing model code."""
import argparse,ast,gzip,json,math,os,pathlib,socket,subprocess,sys,threading,time,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,sha,resolve_run,validate_run
from local_llm_benchmarks import memory_windows as memory

DATA=ROOT/'.local/official-humaneval-b9453e8/data/HumanEval.jsonl.gz'
CHAT_INSTRUCTION='Please provide a self-contained Python script that solves the following problem in a markdown code block:'

def api(route,payload=None,timeout=7200,*,port=8089):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+route,data=data,headers={'Content-Type':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req,timeout=timeout) as f:return json.load(f)

def chat_payload(problem,model,options=None):
    user_message=f"{CHAT_INSTRUCTION}\n```python\n{problem['prompt'].strip()}\n```"
    payload={'model':model,'messages':[{'role':'user','content':user_message}],
             'max_tokens':16384,'temperature':0.1,'top_p':1.0,'top_k':50,'min_p':0,
             'seed':42,'repeat_penalty':1.1,'cache_prompt':False,
             'chat_template_kwargs':{'enable_thinking':True}}
    if options:
        payload.update(options)
    return payload


def failed_chat_cases(score_id, problems, max_output, context):
    score=resolve_run(score_id)
    assert validate_run(score)['status']=='complete'
    summary=load(score/'summary.json')
    previous=resolve_run(summary['source_run'])
    assert validate_run(previous)['status']=='complete'
    statuses=load(score/'summaries/per-task.json')
    assert set(statuses)=={problem['task_id'] for problem in problems}
    assert not summary['unknown_base_statuses'] and not summary['unknown_additional_statuses']
    cases = {}
    for problem in problems:
        task=problem['task_id']
        if statuses[task]['plus_passed']:
            continue
        path=previous/'raw'/(task.replace('/','_')+'.json')
        raw=load(path)
        request=raw['request']
        assert request==chat_payload(problem,request['model'])
        assert request['max_tokens'] < max_output <= context - raw['response']['usage']['prompt_tokens']
        cases[task]={'request':dict(request,max_tokens=max_output),'previous_raw_sha256':sha(path),
                     'previous_finish_reason':raw['response']['choices'][0]['finish_reason']}
    assert len(cases)==summary['attempted']-summary['humaneval_plus']['passed']
    return {'original_score_run':score_id,'original_generation_run':previous.name,'cases':cases}


def main(run_id,stop_sequences,all_cases=False,server_command=None,chat_dataset=None,retry_score=None):
    RUN=resolve_run(run_id)
    manifest=load(RUN/'manifest.json');server=None;monitor=None;stop=threading.Event();hits=[]
    try:
        if server_command is None:
            args=load(ROOT/'runs/period-003-gemma4-e4b-q4km-first-20261112/configs/server-command.json')['args']
            args[args.index('--alias')+1]='period4-gemma-prefix-validation'
        else:
            args=load(server_command)['args']
        port=int(args[args.index('--port')+1])
        assert args[args.index('--host')+1]=='127.0.0.1','Server must bind the local loopback address'
        with socket.socket() as sock:
            assert sock.connect_ex(('127.0.0.1',port))!=0,f'Port {port} occupied'
        save(RUN/'configs/server-command.json',{'args':args})
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        with (RUN/'logs/llama-server.log').open('wb') as f:server=subprocess.Popen(args,cwd=pathlib.Path(args[0]).parent,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        monitor=memory.Monitor(server.pid,RUN/'logs/memory.jsonl').start()
        def guard():
            low=0
            while not stop.wait(3):
                s=memory.snapshot(server.pid);low=low+1 if s['available_ram_bytes']<3*1024**3 else 0
                if low>=3:hits.append({'reason':'RAM reserve','at':now()});server.terminate();return
        threading.Thread(target=guard,daemon=True).start()
        for _ in range(600):
            if server.poll() is not None:raise RuntimeError('server exited')
            try:
                if api('/health',timeout=5,port=port)['status']=='ok':break
            except OSError:pass
            time.sleep(1)
        else:raise TimeoutError('server load timeout')
        config=manifest['config']
        context=config.get('context',65536)
        props=api('/props',timeout=30,port=port);assert props['default_generation_settings']['n_ctx']==context and props['total_slots']==1 and props['build_info'].startswith('b11960-')
        save(RUN/'configs/served-properties.json',props)
        expected_penalty=manifest['config'].get('expected_server_repeat_penalty')
        if expected_penalty is not None:
            actual_penalty=props['default_generation_settings']['params']['repeat_penalty']
            if not math.isclose(actual_penalty,expected_penalty,abs_tol=1e-6):
                raise RuntimeError(f'Server repeat penalty {actual_penalty} differs from expected {expected_penalty}')
        snap=memory.snapshot(server.pid);assert snap['available_ram_bytes']>=3*1024**3 and snap['gpu_used_mib'] is not None and snap['gpu_used_mib']<=7676
        save(RUN/'configs/admission-memory.json',snap)
        dataset=(ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz') if server_command else DATA
        if chat_dataset:
            dataset=chat_dataset
        if manifest['config'].get('dataset_sha256') and sha(dataset)!=manifest['config']['dataset_sha256']:
            raise ValueError('Dataset hash does not match this run')
        problems=[json.loads(x) for x in gzip.decompress(dataset.read_bytes()).decode().splitlines()]
        if chat_dataset:
            alias=args[args.index('--alias')+1]
            assert props['model_alias']==alias and len(problems)==164
            chat_options=config.get('chat_request_options')
            preflight=chat_payload(problems[0],alias,chat_options)
            rendered=api('/apply-template',{k:preflight[k] for k in ['messages','chat_template_kwargs']},timeout=30,port=port)
            if config.get('thinking_template_check')=='gemma':
                disabled=dict(preflight['chat_template_kwargs'],enable_thinking=False)
                other=api('/apply-template',{'messages':preflight['messages'],'chat_template_kwargs':disabled},timeout=30,port=port)
                assert rendered['prompt'] != other['prompt'],'Thinking ON/OFF templates did not differ'
                save(RUN/'configs/rendered-nonthinking-prompt.json',other)
            else:
                assert rendered['prompt'].rstrip().endswith('<think>'),'Thinking prompt prefix missing'
            save(RUN/'configs/rendered-thinking-prompt.json',rendered)
        retry_cases={}
        if retry_score:
            assert chat_dataset and all_cases
            max_output=manifest['config']['max_output']
            plan=failed_chat_cases(retry_score,problems,max_output,props['default_generation_settings']['n_ctx'])
            retry_cases=plan['cases']
            assert retry_cases and all(case['request']['model']==alias for case in retry_cases.values())
            save(RUN/'configs/retry-plan.json',plan)
            problems=[problem for problem in problems if problem['task_id'] in retry_cases]
        results=[]
        for problem in (problems if all_cases else problems[:5]):
            if chat_dataset:
                payload=retry_cases[problem['task_id']]['request'] if retry_cases else chat_payload(problem,alias,chat_options)
                started=time.monotonic();response=api('/v1/chat/completions',payload,port=port)
                choice,=response['choices']
                message=choice['message']
                content=message.get('content') or ''
                result={'task_id':problem['task_id'],'finish_reason':choice['finish_reason'],
                        'output_tokens':response['usage']['completion_tokens'],
                        'reasoning_observed':bool(message.get('reasoning_content') or message.get('reasoning')),
                        'final_content_present':bool(content.strip())}
            else:
                payload={'prompt':problem['prompt'],'n_predict':16384,'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'seed':42,'cache_prompt':False,'stop':stop_sequences}
                started=time.monotonic();response=api('/completion',payload,port=port)
                content=response['content']
                try:ast.parse(problem['prompt']+content);parsable=True
                except SyntaxError:parsable=False
                result={'task_id':problem['task_id'],'parses_when_appended':parsable,'finish_reason':response.get('stop_type'),'output_tokens':response.get('tokens_predicted')}
            raw=RUN/'raw'/(problem['task_id'].replace('/','_')+'.json')
            save(raw,{'task_id':problem['task_id'],'request':payload,'response':response,'seconds':time.monotonic()-started})
            with (RUN/'summaries/samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'task_id':problem['task_id'],'completion':content},ensure_ascii=False)+'\n')
            results.append(result)
            save(RUN/'summaries/format-validation.json',results)
            print(json.dumps(results[-1]),flush=True)
        if chat_dataset:
            summary={'outcome':'collected','samples':len(results),'reasoning_observed':sum(r['reasoning_observed'] for r in results),
                     'final_content_present':sum(r['final_content_present'] for r in results),
                     'scope':'Chat response collection; generated code not executed by collector.'}
        else:
            summary={'outcome':('collected' if all_cases else 'passed' if all(r['parses_when_appended'] for r in results) else 'format_mismatch'),'samples':len(results),'syntax_valid':sum(r['parses_when_appended'] for r in results),'scope':('Full official HumanEval prompt collection; generated code not executed by collector.' if all_cases else 'Five independent adapter-validation samples; syntax check only, no test execution, not a benchmark score.')}
        save(RUN/'summary.json',summary)
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:manifest.update(status='failed',error=repr(e),failed_at=now());raise
    finally:
        stop.set()
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        if monitor:save(RUN/'summaries/memory.json',monitor.stop())
        save(RUN/'configs/cleanup.json',{'server_stopped':server is None or server.poll() is not None,'resource_guard':hits})
        save(RUN/'manifest.json',manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    parser.add_argument('--stop',action='append',default=[])
    parser.add_argument('--standard-completion-stops',action='store_true')
    parser.add_argument('--all',action='store_true')
    parser.add_argument('--server-command',type=pathlib.Path)
    parser.add_argument('--chat-dataset',type=pathlib.Path)
    parser.add_argument('--retry-failed-from')
    options=parser.parse_args()
    stops=options.stop+(['\n```','\nif __name__','\nprint(', '\nclass ', '\ndef '] if options.standard_completion_stops else [])
    main(options.run,stops,options.all,options.server_command,options.chat_dataset,options.retry_failed_from)
