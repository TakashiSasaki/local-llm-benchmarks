"""Common local agent CLI. Tool names are dispatched explicitly, never eval'd."""
import argparse, datetime, hashlib, json, pathlib, sys, time, urllib.error, zipfile
from client import Client
from executor import Executor, TOOLS
from memory import Monitor
from server import ROOT, get_json, load_profile

def run(profile,prompt,workspace,task_id=None,limit=300,validator=None,lock_check=None,diagnostic_profile=None):
    selected_profile=diagnostic_profile or profile
    p=load_profile(selected_profile); executor=Executor(workspace)
    run_id=(task_id or 'daily')+'-'+profile+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    log=ROOT/'runs'/f'{run_id}.jsonl'; c=Client(p,log)
    state=json.loads((ROOT/'server-state.json').read_text(encoding='utf-8'))
    if not state.get('ready') or state['profile']!=selected_profile: raise RuntimeError('Matching model server must be ready')
    expected_args=[str(ROOT/p['runtime_executable']),'-m',str(ROOT/p['model']),'--host','127.0.0.1','--port',str(p['port']),'--alias',p['profile_id']]+p['server_args']
    if state.get('args')!=expected_args: raise RuntimeError('Profile startup arguments changed; restart the server first')
    props=get_json(p['base_url']+'/props')
    if props.get('model_alias')!=p['profile_id'] or not props.get('build_info','').startswith(p['runtime_build']+'-'):
        raise RuntimeError('Live server identity differs from selected profile')
    # Preserve the exact harness, profile and manifests used for this run.
    archive=ROOT/'runs'/f'{run_id}.source.zip'
    source_files=list((ROOT/'scripts').glob('*.py'))+list((ROOT/'profiles').glob('*.json'))
    source_files += [ROOT/n for n in ['environment.json','executor-config.json','runtime-manifest.json','model-manifest.json','validation/suite-lock.json'] if (ROOT/n).exists()]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for path in source_files: z.write(path,str(path.relative_to(ROOT)))
        z.writestr('server-props.json',json.dumps(props,ensure_ascii=False,indent=2))
    archive_hash=hashlib.sha256(archive.read_bytes()).hexdigest()
    monitor=Monitor(state['pid'],ROOT/'runs'/f'{run_id}.memory.jsonl').start()
    start=time.perf_counter(); deadline=start+limit; calls=0; model_calls=0; pending=set(); failure=None; final=None; first_tool=None; responses=[]; tool_events=[]; interrupt_details=None
    executor.deadline=deadline
    hosts={k:{'workspace_root':v['workspace_root']} for k,v in executor.config['ssh_hosts'].items()}
    messages=[{'role':'system','content':'あなたはローカル作業エージェントです。依頼を実際にtoolで実行し、結果を確認してから報告してください。各runは新しいprocessです。cwdと必要なenvは毎回明示します。長い処理はjob_idをpollし、同じ処理を重複起動しないでください。実行先を確認し、作業ファイルは指定されたworkspace内で扱ってください。既存の実行ファイルは利用できます。tool結果のstdout/stderrはログ抜粋の場合があります。runningを完了とみなさないでください。採点処理・エージェント・profile・親ディレクトリなどworkspace外の作業ファイルを読んだり変更したりしないでください。Windows workspace: '+str(workspace)+'。PowerShell executable: '+executor.config['powershell']+'。許可済みSSH host: '+json.dumps(hosts,ensure_ascii=False)},
              {'role':'user','content':prompt}]
    c.record('run_start',run_id=run_id,task_id=task_id,profile=p,workspace=str(workspace),intervention=False,limits={'seconds':limit,'tool_calls':12},lock_valid=lock_check() if lock_check else None,source_archive=str(archive),source_archive_sha256=archive_hash,server_effective_defaults=props.get('default_generation_settings'))
    try:
        while time.perf_counter()<deadline:
            # Get the actual rendered token count including the tool schema.
            import urllib.request
            render={'messages':messages,'tools':TOOLS,'chat_template_kwargs':p['chat_template_kwargs'],'add_generation_prompt':True}
            request=urllib.request.Request(p['base_url']+'/apply-template',data=json.dumps(render,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=10) as r: rendered=json.load(r)
            request=urllib.request.Request(p['base_url']+'/tokenize',data=json.dumps({'content':rendered['prompt'],'add_special':False}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=10) as r: token_count=len(json.load(r)['tokens'])
            c.record('context_check',actual_input_tokens=token_count,remaining_tokens=p['context_tokens']-token_count)
            if token_count+p['max_tokens']>p['context_tokens']:
                failure='context_budget'; break
            model_calls+=1
            response=c.chat(messages,TOOLS,request_timeout=max(.1,deadline-time.perf_counter()))
            responses.append(response); message=response['message']; messages.append(message)
            if response['finish_reason']=='length': failure='token_budget'; break
            tools=message.get('tool_calls',[])
            if not tools:
                final=message.get('content',''); break
            for call in tools:
                if calls>=12: failure='tool_budget'; break
                if time.perf_counter()>=deadline: failure='timeout'; break
                calls+=1; ts=time.perf_counter()
                try:
                    name=call['function']['name']; args=json.loads(call['function']['arguments'])
                    definition=next((t['function']['parameters'] for t in TOOLS if t['function']['name']==name),None)
                    if definition is None or not isinstance(args,dict): raise ValueError('Invalid tool call')
                    if any(k not in args for k in definition['required']) or any(k not in definition['properties'] for k in args): raise ValueError('Invalid tool arguments')
                    for key,value in args.items():
                        typ=definition['properties'][key]['type']
                        if typ=='string' and not isinstance(value,str): raise ValueError('Expected string '+key)
                        if typ=='object' and (not isinstance(value,dict) or any(not isinstance(v,str) for v in value.values())): raise ValueError('Expected string-valued object '+key)
                        if typ in ['number','integer'] and (isinstance(value,bool) or not isinstance(value,(int,float))): raise ValueError('Expected number '+key)
                        if typ=='integer' and not isinstance(value,int): raise ValueError('Expected integer '+key)
                        prop=definition['properties'][key]
                        if 'enum' in prop and value not in prop['enum']: raise ValueError('Invalid enum '+key)
                        if 'minimum' in prop and value<prop['minimum']: raise ValueError('Below minimum '+key)
                        if 'maximum' in prop and value>prop['maximum']: raise ValueError('Above maximum '+key)
                    if first_tool is None: first_tool=time.perf_counter()-start
                    if name.startswith('run_'): args['timeout']=min(float(args.get('timeout',1)),max(0,deadline-time.perf_counter()),60)
                    result=executor.execute(name,args)
                    if result.get('job_id'):
                        if result['status'] in ['running','unknown']: pending.add(result['job_id'])
                        else: pending.discard(result['job_id'])
                except Exception as e:
                    result={'status':'tool_error','error':str(e),'type':type(e).__name__}
                tool_events.append({'call':call,'result':result})
                c.record('tool',call=call,result=result,elapsed_seconds=time.perf_counter()-ts)
                messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
            if failure: break
        if final is None and failure is None: failure='timeout'
    except KeyboardInterrupt as e:
        interrupt_details=getattr(e,'transport_details',None)
        failure='user_interrupted'; c.record('interrupted',reason='Ctrl+C; closing model stream and stopping jobs owned by this run',transport_details=interrupt_details)
    except Exception as e:
        # A timeout is a task-budget failure only when that budget has elapsed;
        # a premature network timeout remains an environmental failure.
        cause=e.reason if isinstance(e,urllib.error.URLError) else e
        failure='timeout' if isinstance(cause,TimeoutError) and time.perf_counter()>=deadline else 'environment_or_protocol_error'
        c.record('exception',error=str(e),type=type(e).__name__,failure_classification=failure)
    # Validation happens before cleanup. A final answer with a running job is incomplete.
    running=[]
    pending.update(executor.started_jobs)
    for job in pending:
        try:
            r=executor.execute('poll_process',{'job_id':job})
            if r['status'] in ['running','unknown']: running.append(job)
        except Exception: running.append(job)
    lock_valid=lock_check() if lock_check else None
    try:
        validation=validator(tool_events) if validator and not running and lock_valid is not False else {'passed':False,'reason':'running_jobs_or_changed_grader' if validator else 'not_independently_validated'}
    except Exception as e:
        validation={'passed':False,'reason':'validator_environment_error','error':str(e)}
    wall=time.perf_counter()-start
    validation['within_wall_budget']=wall<=limit
    if wall>limit and failure is None: failure='timeout'
    # Cleanup gets its own transport budget even after the task deadline so
    # that managed jobs can be polled and stopped rather than abandoned.
    executor.deadline=None
    cleanup_start=time.perf_counter(); cleanup_results=[]; still_running=[]
    for job in running:
        try:
            stopped=executor.execute('stop_process',{'job_id':job}); cleanup_results.append(stopped)
            c.record('cleanup',result=stopped)
            if stopped.get('status') not in ['completed','not_started'] or stopped.get('stop_verified') is False: still_running.append(job)
        except Exception as e:
            still_running.append(job); c.record('cleanup_error',job_id=job,error=str(e))
    cleanup_seconds=time.perf_counter()-cleanup_start
    memory=monitor.stop()
    token_counts=[(r['usage'] or {}).get('completion_tokens') for r in responses]
    generated_tokens=sum(token_counts) if len(responses)==model_calls and all(isinstance(n,int) for n in token_counts) else None
    summary={'run_id':run_id,'task_id':task_id,'profile_id':p['profile_id'],'diagnostic_cpu_only':p.get('diagnostic_cpu_only',False),'model_hash':p['model_hash'],'runtime_build':p['runtime_build'],'thinking':p['chat_template_kwargs'],'sampling':p['sampling'],'success':bool(validation.get('passed')) and failure is None and final is not None and validation['within_wall_budget'],'validator':validation,'lock_valid':lock_valid,'failure':failure,'final':final,'interrupt_transport_details':interrupt_details,'jobs_unfinished_at_validation':running,'uncompleted_jobs':still_running,'cleanup_results':cleanup_results,'cleanup_seconds':cleanup_seconds,'total_cli_seconds':time.perf_counter()-start,'wall_seconds':wall,'first_valid_tool_call_seconds':first_tool,'model_calls':model_calls,'tool_calls':calls,'generated_tokens':generated_tokens,'memory':memory,'intervention':False,'false_completion_claim':None,'wrong_host_operation':None}
    c.record('run_end',**summary)
    (ROOT/'runs'/f'{run_id}.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True); return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--profile',required=True,choices=['qwen','lfm','glm']); ap.add_argument('--prompt',required=True); ap.add_argument('--workspace',default=str(ROOT/'workspace')); ap.add_argument('--seconds',type=int,default=300); ap.add_argument('--diagnostic-profile'); a=ap.parse_args()
    result=run(a.profile,a.prompt,pathlib.Path(a.workspace),limit=a.seconds,diagnostic_profile=a.diagnostic_profile)
    raise SystemExit(130 if result['failure']=='user_interrupted' else 1 if result['failure'] else 0)
