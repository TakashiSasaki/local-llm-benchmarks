"""Model -> real SSH Bash -> model protocol smoke, separate from P5.

Requires an explicitly configured and independently authenticated Linux target.
Creates only fresh UUID-named directories beneath the configured workspaces.
"""
import argparse, base64, hashlib, json, pathlib, re, uuid
from agent import run
from bootstrap import Bridge
from grading import capture_lock
from server import ROOT

def make_script(filename,token):
    out='OUT-'+token; err='ERR-'+token; content='実行確認 '+token+'\n'
    # The random value exists only in the seeded remote file, not the prompt.
    script=("python3 -c \"import hashlib,pathlib,socket,sys; "
            "data=pathlib.Path('.smoke-input').read_bytes(); "
            "pathlib.Path('"+filename+"').write_bytes(data); "
            "token=data.decode('utf-8').removeprefix('実行確認 ').strip(); "
            "print('OUT-'+token); print('ERR-'+token,file=sys.stderr); print('HOSTNAME='+socket.gethostname()); "
            "print(hashlib.sha256(data).hexdigest()); sys.exit(7)\"")
    return script,content.encode('utf-8'),out,err

def evidence(events,alias,remote,script,filename,expected,stdout_token,stderr_token,snapshot,expected_host,lock_ok):
    calls=[]; malformed=False
    for event in events:
        try:
            name=event['call']['function']['name']; args=json.loads(event['call']['function']['arguments']); result=event['result']
            if not isinstance(args,dict) or not isinstance(result,dict): raise ValueError('Invalid tool event')
            calls.append((name,args,result))
        except (KeyError,TypeError,ValueError): malformed=True
    starts=[(i,args,result) for i,(name,args,result) in enumerate(calls) if name=='run_ssh_bash']
    start_index,args,start=starts[0] if starts else (-1,{}, {})
    job=start.get('job_id'); related=[start] if starts else []
    for i,(name,a,r) in enumerate(calls):
        if i>start_index and name=='poll_process' and job and a.get('job_id')==job: related.append(r)
    stdout=''.join(r.get('stdout','') for r in related); stderr=''.join(r.get('stderr','') for r in related)
    completed=any(r.get('status')=='completed' and r.get('exit_code')==7 and r.get('host')==alias for r in related)
    wanted=hashlib.sha256(expected).hexdigest(); file_data=(snapshot.get('files') or {}).get(filename,{})
    try: actual=base64.b64decode(file_data.get('base64',''),validate=True)
    except (ValueError,TypeError): actual=None
    checks={'one_exact_start':len(starts)==1 and args.get('host_alias')==alias and args.get('cwd')==remote and args.get('script')==script,
            'has_job_id':isinstance(job,str) and len(job)==32 and all(c in '0123456789abcdef' for c in job),
            'related_results_match_job_host_and_cwd':all(r.get('job_id')==job and r.get('host')==alias and r.get('cwd')==remote for r in related),
            'only_start_and_its_polls':not malformed and all((n=='run_ssh_bash' and i==start_index) or (n=='poll_process' and i>start_index and a.get('job_id')==job) for i,(n,a,r) in enumerate(calls)),
            'completed_exit_7':completed,
            'stdout_token':stdout_token in stdout,'stderr_token':stderr_token in stderr,
            'stdout_hostname_matches_preflight':('HOSTNAME='+expected_host) in stdout.splitlines(),
            'stdout_sha256':wanted in stdout.lower(),'snapshot_host_matches_preflight':snapshot.get('host')==expected_host,
            'snapshot_directory_exact':snapshot.get('directory')==remote,
            'snapshot_bytes_exact':actual==expected,'snapshot_sha256_exact':file_data.get('sha256')==wanted,
            'no_wrong_ssh_host':not any(n in ['run_ssh_bash','transfer_file'] and a.get('host_alias')!=alias for n,a,r in calls),
            'suite_unchanged':bool(lock_ok)}
    return {'passed':all(checks.values()),'checks':checks,'expected_sha256':wanted,
            'stdout_token':stdout_token,'stderr_token':stderr_token,'job_id':job,'test_version':'ssh-bash-fixed-script-v1'}

def final_evidence(final,stdout_token,stderr_token,sha256):
    final=final if isinstance(final,str) else ''
    checks={'stdout_reported':stdout_token in final,'stderr_reported':stderr_token in final,
            'hash_reported':sha256 in final.lower(),
            'exit_7_reported':re.findall(r'^[ \t]*exit_code[ \t]*:[ \t]*(\d+)[ \t]*\r?$',final,re.I|re.M)==['7']}
    return {'passed':all(checks.values()),'checks':checks}

def test(model,alias):
    bridge=Bridge(alias)  # Reject an unconfigured alias before creating any fixture.
    lock=capture_lock()   # Do not modify the remote or local workspace if the suite is stale.
    host=bridge.preflight()
    if not lock(): raise RuntimeError('Suite changed during SSH preflight')
    token=uuid.uuid4().hex[:16]; filename='[日本語] 空白 メモ.txt'
    script,expected,out,err=make_script(filename,token)
    local=ROOT/'workspace'/('ssh-model-smoke-'+uuid.uuid4().hex); local.mkdir(parents=True,exist_ok=False)
    remote=str(pathlib.PurePosixPath(bridge.host['workspace_root'])/('ssh-model-smoke-'+uuid.uuid4().hex))
    seeded=bridge({'action':'seed','directory':remote,'files':{'.smoke-input':base64.b64encode(expected).decode('ascii')},'executable':[]})
    if seeded.get('host')!=host['hostname']: raise RuntimeError('SSH host identity changed after preflight')
    remote=seeded['directory']
    prompt=('SSHの実行系疎通試験です。run_ssh_bashを一度呼び、host_alias='+alias+'、cwd='+remote+
            '、scriptには次のBashコードブロックの中身をそのまま渡してください。フェンスを含めず、行間はLF、最後に改行を加えません。\n```bash\n'+script+
            '\n```\nこのscriptの終了コード7は試験の予定値です。runningなら同じjob_idをpollして終了を確認してください。'
            '実際のstdout、stderr、exit_codeを確認後、stdoutの確認コードとSHA-256、stderrの確認コードを最終回答に含め、'
            '終了コードは exit_code: 7 の形式で一行単独に記載してください。')
    def validate(events):
        snapshot=bridge({'action':'snapshot','directory':remote})
        return evidence(events,alias,remote,script,filename,expected,out,err,snapshot,host['hostname'],lock())
    result=run(model,prompt,local,task_id='ssh-model-smoke',limit=180,validator=validate,lock_check=lock)
    wanted=hashlib.sha256(expected).hexdigest(); final=final_evidence(result.get('final'),out,err,wanted)
    report={'passed':bool(result.get('success')) and final['passed'],'real_ssh_executed':True,
            'main_score_eligible':False,'model':model,'host_alias':alias,'preflight_hostname':host['hostname'],
            'remote_directory':remote,'local_directory':str(local),'agent_run_id':result['run_id'],
            'agent_success':result['success'],'validator':result['validator'],'final_answer_checks':final,
            'uncompleted_jobs':result['uncompleted_jobs']}
    path=ROOT/'runs'/('ssh-model-smoke-'+model+'-'+token+'.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('model',choices=['qwen','lfm','glm']); ap.add_argument('--host',required=True); a=ap.parse_args()
    report=test(a.model,a.host); print(json.dumps(report,ensure_ascii=False))
    raise SystemExit(0 if report['passed'] else 1)
