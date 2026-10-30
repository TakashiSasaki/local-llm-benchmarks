"""P3 model-free SSH contract smoke on an explicitly configured Linux host.

Creates unique dedicated local/remote directories and preserves them as evidence.
No model inference, external host discovery, host-key changes or file deletion.
Actual SSH execution is opt-in via the required configured host alias.
"""
import argparse, base64, datetime, hashlib, json, pathlib, time, uuid
from bootstrap import Bridge
from executor import Executor
from server import ROOT

STDOUT='日本語 stdout'
STDERR='日本語 stderr'
ENV_VALUE='日本語 env [空白]'
ASYNC_TEXT='開始 α\n完了 β\n'
CHILD_READY='CHILD_READY'
PAYLOAD='一行目 日本語\r\n二行目\n終わり\r\n'.encode('utf-8')

class SmokeFailure(RuntimeError): pass

def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def smoke(alias,*,root=ROOT,bridge_factory=Bridge,executor_factory=Executor,clock=time,run_token=None):
    root=pathlib.Path(root); token=run_token or uuid.uuid4().hex
    if len(token)!=32 or any(c not in '0123456789abcdef' for c in token): raise ValueError('Invalid smoke token')
    if not isinstance(alias,str) or not alias: raise ValueError('Configured SSH host alias required')
    report={'kind':'real_ssh_contract_smoke','run_id':'ssh-contract-'+token,'host_alias':alias,
            'started_utc':utc(),'status':'running','passed':False,'ssh_attempted':False,'ssh_executed':False,
            'model_inference':False,'checks':[],'unresolved_jobs':[],'cleanup':[],
            'local_directory':None,'remote_directory':None,'error':None}
    report_dir=root/'runs'; report_dir.mkdir(parents=True,exist_ok=True)
    report_path=report_dir/(report['run_id']+'.json')
    if report_path.exists() or report_path.with_suffix('.tmp').exists():
        raise FileExistsError('Smoke report or pending report already exists')
    executor=None; stop_unverified=set(); interrupted=None
    def save():
        tmp=report_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(report_path)
    def check(name,passed,detail=None):
        report['checks'].append({'name':name,'passed':bool(passed),'detail':detail})
        save()
        if not passed: raise SmokeFailure(name)
    def record_job(result):
        if not isinstance(result,dict): raise SmokeFailure('tool returned non-object')
        if result.get('status') in ('unknown','tool_error') or result.get('may_be_running'):
            raise SmokeFailure('tool transport or job state unknown: '+str(result.get('error','unknown')))
        return result
    def append_output(result,chunks,offsets):
        for stream in ('stdout','stderr'):
            text=result.get(stream); reported_offset=result.get(stream+'_offset'); next_offset=result.get(stream+'_next_offset')
            if not isinstance(text,str) or isinstance(reported_offset,bool) or not isinstance(reported_offset,int) or isinstance(next_offset,bool) or not isinstance(next_offset,int):
                raise SmokeFailure('missing '+stream+' output or offset')
            if reported_offset!=offsets[stream]: raise SmokeFailure('mismatched requested '+stream+' offset')
            if next_offset<offsets[stream]: raise SmokeFailure('non-monotonic '+stream+' offset')
            if next_offset-offsets[stream]!=len(text.encode('utf-8')):
                raise SmokeFailure('invalid UTF-8 byte offset for '+stream)
            chunks[stream].append(text); offsets[stream]=next_offset
    def wait_job(initial,timeout=30,ready=None):
        result=record_job(initial); job_id=result.get('job_id')
        if not isinstance(job_id,str) or len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id): raise SmokeFailure('invalid job id')
        if result.get('host')!=alias: raise SmokeFailure('job host mismatch')
        offsets={'stdout':0,'stderr':0}; chunks={'stdout':[],'stderr':[]}
        append_output(result,chunks,offsets)
        deadline=clock.monotonic()+timeout; saw_running=result.get('status')=='running'
        while True:
            output=''.join(chunks['stdout'])
            if ready and ready in output:
                if result.get('status')!='running': raise SmokeFailure('long job completed before stop')
                return result,output,''.join(chunks['stderr']),saw_running
            if result.get('status')=='completed':
                if ready: raise SmokeFailure('long job ended before readiness')
                if result.get('executor_error') or result.get('exit_code') is None:
                    raise SmokeFailure('worker completion has unknown exit status')
                return result,output,''.join(chunks['stderr']),saw_running
            if result.get('status')!='running': raise SmokeFailure('unexpected job status')
            if clock.monotonic()>=deadline: raise SmokeFailure('poll deadline exceeded')
            clock.sleep(.2)
            result=record_job(executor.execute('poll_process',{'job_id':job_id,
                'stdout_offset':offsets['stdout'],'stderr_offset':offsets['stderr']}))
            if result.get('job_id')!=job_id or result.get('host')!=alias: raise SmokeFailure('poll job or host mismatch')
            append_output(result,chunks,offsets)
    def run(script,env=None,wait=10):
        return record_job(executor.execute('run_ssh_bash',{'host_alias':alias,'script':script,
            'cwd':remote,'env':env or {},'timeout':wait}))
    try:
        bridge=bridge_factory(alias)
        host=bridge.host
        workspace=pathlib.PurePosixPath(host['workspace_root'])
        parent=workspace.parent
        paths=[workspace,pathlib.PurePosixPath(host['state_root']),pathlib.PurePosixPath(host['worker_path'])]
        check('configured_dedicated_paths',parent.is_absolute() and len(parent.parts)>=4 and
              all(p.is_absolute() and '..' not in p.parts and p.is_relative_to(parent) for p in paths),
              {'workspace':str(workspace),'state':str(paths[1]),'worker':str(paths[2])})
        report['ssh_attempted']=True; save()
        preflight=bridge.preflight()
        check('linux_preflight',isinstance(preflight,dict) and bool(preflight.get('hostname')) and
              bool(preflight.get('bash')) and bool(preflight.get('worker_sha256')),preflight)
        report['ssh_executed']=True
        local=root/'workspace'/'ssh-contract'/token
        local.mkdir(parents=True,exist_ok=False); report['local_directory']=str(local)
        remote_requested=str(workspace/('ssh-contract-'+token))
        seeded=bridge({'action':'seed','directory':remote_requested,'files':{},'executable':[]})
        check('unique_remote_directory',seeded.get('seeded') is True and seeded.get('host')==preflight['hostname']
              and seeded.get('directory')==remote_requested,seeded)
        remote=seeded['directory']; report['remote_directory']=remote; save()
        executor=executor_factory(local)

        script="# smoke:stdio\nprintf '%s\\n' '"+STDOUT+"'\nprintf '%s\\n' '"+STDERR+"' >&2\nexit 7\n"
        result,out,err,_=wait_job(run(script))
        check('stdout_stderr_exit',result.get('host')==alias and result.get('exit_code')==7 and
              out==STDOUT+'\n' and err==STDERR+'\n',{'exit_code':result.get('exit_code'),'stdout':out,'stderr':err})

        env_name='LLM_SSH_SMOKE_'+token.upper()
        env_script="# smoke:environment\npython3 -c 'import json,os,socket; print(json.dumps({\"hostname\":socket.gethostname(),\"cwd\":os.getcwd(),\"value\":os.environ.get(\""+env_name+"\")},ensure_ascii=False))'\n"
        result,out,err,_=wait_job(run(env_script,{env_name:ENV_VALUE}))
        observed=json.loads(out)
        check('hostname_cwd_explicit_env',result.get('exit_code')==0 and not err and
              observed=={'hostname':preflight['hostname'],'cwd':remote,'value':ENV_VALUE},observed)
        result,out,err,_=wait_job(run(env_script))
        observed=json.loads(out)
        check('fresh_process_env',result.get('exit_code')==0 and not err and
              observed=={'hostname':preflight['hostname'],'cwd':remote,'value':None},observed)

        async_script="# smoke:async\nprintf '%s\\n' '開始 α'\nsleep 2\nprintf '%s\\n' '完了 β'\n"
        result,out,err,observed_running=wait_job(run(async_script,wait=0))
        check('async_poll_offsets',observed_running and result.get('exit_code')==0 and out==ASYNC_TEXT and not err,
              {'observed_running':observed_running,'stdout':out,'exit_code':result.get('exit_code')})

        stubborn_script='''# smoke:stubborn
python3 -u - <<'PY' &
import json,os,pathlib,signal,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
fields=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
pathlib.Path('child-identity.json').write_text(json.dumps({'pid':os.getpid(),'start':fields[19]}),encoding='utf-8')
print('CHILD_READY',flush=True)
time.sleep(12)
pathlib.Path('late-marker.txt').write_text('unexpected',encoding='utf-8')
PY
wait
'''
        initial=run(stubborn_script,wait=0)
        result,out,err,_=wait_job(initial,timeout=20,ready=CHILD_READY)
        ready_started=clock.monotonic()
        child_job=result['job_id']
        # Keep the job unresolved until both stop and the independent proof pass.
        stop_unverified.add(child_job)
        snapshot=bridge({'action':'snapshot','directory':remote})
        snapshot_info=snapshot if isinstance(snapshot,dict) else {}
        check('child_snapshot_host',snapshot_info.get('host')==preflight['hostname'] and
              snapshot_info.get('directory')==remote,{'host':snapshot_info.get('host'),'directory':snapshot_info.get('directory')})
        child=json.loads(base64.b64decode(snapshot['files']['child-identity.json']['base64'],validate=True))
        check('stubborn_child_ready',isinstance(child.get('pid'),int) and child['pid']>0 and
              isinstance(child.get('start'),str) and bool(child['start']),child)
        stopped=executor.execute('stop_process',{'job_id':child_job})
        check('stop_verified_group',stopped.get('job_id')==child_job and stopped.get('host')==alias and
              stopped.get('status')=='completed' and stopped.get('stop_verified') is True and
              stopped.get('process_group_exited') is True,stopped)
        # Wait beyond the child's marker deadline before independently checking it.
        clock.sleep(max(0,ready_started+13-clock.monotonic()))
        verify_script='''# smoke:stop-proof
python3 - <<'PY'
import json,os,pathlib
child=json.loads(pathlib.Path('child-identity.json').read_text(encoding='utf-8'))
p=pathlib.Path('/proc')/str(child['pid'])/'stat'
try:
    fields=p.read_text().rsplit(')',1)[1].split()
    same=fields[19]==child['start']
    alive=same and fields[0]!='Z'
except FileNotFoundError: alive=False
print(json.dumps({'same_process_alive':alive,'late_marker_exists':pathlib.Path('late-marker.txt').exists()}))
PY
'''
        result,out,err,_=wait_job(run(verify_script))
        proof=json.loads(out)
        check('stop_independent_process_and_marker',result.get('exit_code')==0 and not err and
              proof=={'same_process_alive':False,'late_marker_exists':False},proof)
        stop_unverified.discard(child_job)

        source=local/'送信 日本語.txt'; returned=local/'回収 日本語.txt'
        source.write_bytes(PAYLOAD)
        remote_name='転送 \'見本\' "日本語".txt'
        remote_file=remote+'/'+remote_name
        sent=executor.execute('transfer_file',{'host_alias':alias,'direction':'upload',
            'local_path':str(source),'remote_path':remote_file})
        check('scp_upload',sent.get('host')==alias and sent.get('status')=='completed' and sent.get('exit_code')==0 and
              sent.get('remote_path')==remote_file and pathlib.Path(sent.get('local_path','')).resolve()==source.resolve(),sent)
        snapshot=bridge({'action':'snapshot','directory':remote})
        snapshot_info=snapshot if isinstance(snapshot,dict) else {}
        check('transfer_snapshot_host',snapshot_info.get('host')==preflight['hostname'] and
              snapshot_info.get('directory')==remote,{'host':snapshot_info.get('host'),'directory':snapshot_info.get('directory')})
        entry=snapshot['files'][remote_name]; remote_bytes=base64.b64decode(entry['base64'],validate=True)
        digest=hashlib.sha256(PAYLOAD).hexdigest()
        check('remote_content_and_hash',remote_bytes==PAYLOAD and entry.get('sha256')==digest,
              {'expected_sha256':digest,'remote_sha256':entry.get('sha256'),'bytes':len(remote_bytes)})
        received=executor.execute('transfer_file',{'host_alias':alias,'direction':'download',
            'local_path':str(returned),'remote_path':remote_file})
        check('scp_download',received.get('host')==alias and received.get('status')=='completed' and received.get('exit_code')==0 and
              received.get('remote_path')==remote_file and pathlib.Path(received.get('local_path','')).resolve()==returned.resolve(),received)
        check('roundtrip_content_and_hash',returned.is_file() and returned.read_bytes()==PAYLOAD and
              hashlib.sha256(returned.read_bytes()).hexdigest()==digest,{'expected_sha256':digest})
        report['status']='completed'; report['passed']=True
    except KeyboardInterrupt as exc:
        interrupted=exc
        report['status']='interrupted'; report['error']={'type':'KeyboardInterrupt','message':'Interrupted by user'}
    except Exception as exc:
        report['status']='failed'; report['error']={'type':type(exc).__name__,'message':str(exc)}
    finally:
        unresolved=set(stop_unverified)
        if executor is not None:
            for job_id in sorted(executor.started_jobs):
                try:
                    state=executor.execute('poll_process',{'job_id':job_id})
                    if state.get('job_id')!=job_id or state.get('host')!=alias:
                        unresolved.add(job_id)
                        report['cleanup'].append({'job_id':job_id,'status':'unknown','error':'poll job or host mismatch'})
                        continue
                    if state.get('status')=='running':
                        state=executor.execute('stop_process',{'job_id':job_id})
                        if state.get('job_id')!=job_id or state.get('host')!=alias or state.get('stop_verified') is not True: unresolved.add(job_id)
                    elif state.get('status') not in ('completed','not_started') or state.get('executor_error'):
                        unresolved.add(job_id)
                    report['cleanup'].append({'job_id':job_id,'status':state.get('status'),
                        'stop_verified':state.get('stop_verified'),'error':state.get('error')})
                except Exception as exc:
                    unresolved.add(job_id)
                    report['cleanup'].append({'job_id':job_id,'status':'unknown','error':str(exc)})
        report['unresolved_jobs']=sorted(unresolved)
        if unresolved:
            report['passed']=False
            if report['status']!='interrupted': report['status']='failed'
        report['finished_utc']=utc(); save()
    if interrupted is not None: raise interrupted
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('host_alias'); args=parser.parse_args()
    result=smoke(args.host_alias)
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
