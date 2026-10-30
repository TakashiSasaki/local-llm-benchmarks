"""Create fresh fixtures, run one model task, then validate outside the agent."""
import argparse, datetime, json, pathlib, re, shlex
from agent import run
from bootstrap import Bridge
from fixtures import TASKS, prepare, prompt
from grading import capture_lock, grade_b4, grade_ps4, snapshot, static_grade
from server import ROOT

def _direct_script(script,directory,cwd,filename,depth=0):
    """Recognize direct fixture launches, not names in echo, comments or data.

    This conservative trace check is not a complete Bash interpreter. Dynamic
    command construction can require manual review instead of being accepted.
    """
    if not isinstance(script,str) or depth>2 or not directory: return False
    try:
        lexer=shlex.shlex(script,posix=True,punctuation_chars=';&|()<>\n')
        lexer.whitespace=' \t\r'; lexer.whitespace_split=True; lexer.commenters='#'
        tokens=list(lexer)
    except ValueError: return False
    # A textual command in a conditional branch, heredoc, background job or
    # command substitution does not prove that the polled shell ran it to
    # completion. Such traces need manual review instead of automatic credit.
    ambiguous={'&&','||','&','if','then','else','elif','fi','for','while','until','case','esac','function','{','}',
               'exit','return','break','continue','cd','pushd','popd','eval','source','exec','trap','--noexec'}
    if any(t in ambiguous or t.startswith('<<') or re.fullmatch(r'-[A-Za-z]*n[A-Za-z]*',t) for t in tokens) or '$(' in script or '`' in script: return False
    separators={';','&&','||','|','&','\n','(',')'}
    def matches(path,via_shell=False):
        if path==filename and not via_shell: return False
        if path in [filename,'./'+filename]:
            return isinstance(cwd,str) and cwd.rstrip('/')==directory.rstrip('/')
        return path==directory.rstrip('/')+'/'+filename
    def segment_runs(words):
        words=list(words)
        while words and (re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',words[0]) or words[0] in ['command','exec','time']): words.pop(0)
        if words and words[0]=='env':
            words.pop(0)
            while words and (words[0]=='--' or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',words[0])): words.pop(0)
        if not words: return False
        if matches(words[0]): return True
        if pathlib.PurePosixPath(words[0]).name not in ['bash','sh']: return False
        words.pop(0)
        while words and words[0].startswith('-'):
            option=words.pop(0)
            if option=='-c': return bool(words) and _direct_script(words[0],directory,cwd,filename,depth+1)
            if option=='--': break
        return bool(words) and matches(words[0],via_shell=True)
    segment=[]
    for token in tokens:
        if token in separators:
            if segment_runs(segment): return True
            segment=[]
        else: segment.append(token)
    return segment_runs(segment)

def _direct_long_script(script,remote,cwd,depth=0):
    return _direct_script(script,remote,cwd,'long.sh',depth)

def _valid_job_id(value):
    return isinstance(value,str) and len(value)==32 and all(c in '0123456789abcdef' for c in value)

def _successful(result):
    return result.get('status')=='completed' and type(result.get('exit_code')) is int and result['exit_code']==0

def execution_trace(task,events,alias,remote,local):
    """Verify trace-dependent task conditions from recorded tool calls."""
    parsed=[]
    for event in events:
        try:
            name=event['call']['function']['name']
            args=json.loads(event['call']['function']['arguments'])
            result=event['result']
            if isinstance(args,dict) and isinstance(result,dict): parsed.append((name,args,result))
        except (KeyError,TypeError,ValueError): pass
    trace={}
    if task=='S2':
        directory=remote.rstrip('/')+'/work'; jobs={}; successful_first=set(); second_done=False
        def finish(job):
            nonlocal second_done
            stage,first_before_start=jobs[job]
            if stage=='step1': successful_first.add(job)
            elif first_before_start: second_done=True
        for name,args,r in parsed:
            if name=='run_ssh_bash':
                env=args.get('env'); cwd=args.get('cwd'); job=r.get('job_id')
                if args.get('host_alias')!=alias or r.get('host')!=alias or not isinstance(cwd,str) or cwd.rstrip('/')!=directory or not isinstance(env,dict) or env.get('BUILD_LABEL')!='日本語 label' or env.get('REGION')!='test-east' or not _valid_job_id(job) or job in jobs or r.get('status') not in ['running','completed','unknown']: continue
                first=_direct_script(args.get('script'),directory,cwd,'step1.sh')
                second=_direct_script(args.get('script'),directory,cwd,'step2.sh')
                if first==second: continue
                if r.get('status')=='completed' and not _successful(r): continue
                jobs[job]=('step1' if first else 'step2',bool(successful_first-{job}))
                if _successful(r): finish(job)
            elif name=='poll_process':
                job=args.get('job_id')
                if job in jobs and r.get('job_id')==job and r.get('host')==alias and _successful(r): finish(job)
        trace['explicit_cwd_env_on_separate_jobs']=len(jobs)>=2
        trace['step1_completed_successfully']=bool(successful_first)
        trace['step2_started_after_step1_and_completed']=second_done
    if task=='S3':
        jobs=set(); completed=False
        for name,args,r in parsed:
            if name=='run_ssh_bash' and args.get('host_alias')==alias and r.get('host')==alias and _valid_job_id(r.get('job_id')) and r.get('status') in ['running','completed','unknown'] and _direct_long_script(args.get('script'),remote,args.get('cwd')):
                if r.get('status')!='completed' or (type(r.get('exit_code')) is int and r['exit_code']==0): jobs.add(r['job_id'])
            if name=='poll_process' and args.get('job_id') in jobs and r.get('job_id')==args['job_id'] and r.get('host')==alias and r.get('status')=='completed' and type(r.get('exit_code')) is int and r['exit_code']==0:
                completed=True
        trace['polled_remote_job_completed_successfully']=completed
    if task=='S4':
        source=pathlib.Path(local,'source 日本語.txt').resolve()
        roundtrip=pathlib.Path(local,'roundtrip 日本語.txt').resolve()
        remote_copy=pathlib.PurePosixPath(remote)/'remote copy 日本語.txt'
        upload_indices=[]; download_indices=[]
        for index,(name,args,r) in enumerate(parsed):
            if name!='transfer_file' or args.get('host_alias')!=alias or r.get('host')!=alias or r.get('status')!='completed' or type(r.get('exit_code')) is not int or r['exit_code']!=0: continue
            try:
                local_path=pathlib.Path(args['local_path'])
                result_local=pathlib.Path(r['local_path'])
                remote_path=pathlib.PurePosixPath(args['remote_path'])
                result_remote=pathlib.PurePosixPath(r['remote_path'])
                if not local_path.is_absolute() or not result_local.is_absolute() or remote_path!=remote_copy or result_remote!=remote_copy: continue
                if args.get('direction')=='upload' and local_path.resolve()==source and result_local.resolve()==source: upload_indices.append(index)
                if args.get('direction')=='download' and local_path.resolve()==roundtrip and result_local.resolve()==roundtrip: download_indices.append(index)
            except (KeyError,TypeError,ValueError,OSError): continue
        trace['specified_upload_completed']=bool(upload_indices)
        trace['specified_download_completed']=bool(download_indices)
        trace['upload_before_download']=any(a<b for a in upload_indices for b in download_indices)
    trace['no_wrong_ssh_host']=not any(name in ['run_ssh_bash','transfer_file'] and args.get('host_alias')!=alias for name,args,r in parsed)
    return trace

def trial(profile,task,alias=None):
    check=capture_lock(); trial_id=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+profile
    local,definition=prepare(task,trial_id); remote=None; bridge=None
    if task.startswith(('B','S')):
        if not alias: raise ValueError('SSH task requires --host')
        bridge=Bridge(alias); remote=bridge.host['workspace_root'].rstrip('/')+'/'+trial_id+'/'+task
        seeded=bridge({'action':'seed','directory':remote,'files':definition['remote'],'executable':definition['executable']})
        (ROOT/'runs'/f'fixture-{trial_id}-{task}.json').write_text(json.dumps({'local':str(local),'remote':seeded},ensure_ascii=False,indent=2),encoding='utf-8')
    config=json.loads((ROOT/'executor-config.json').read_text(encoding='utf-8-sig'))
    def validate(events):
        remote_files=bridge({'action':'snapshot','directory':remote})['files'] if bridge else {}
        result=static_grade(task,snapshot(local),remote_files,lock_valid=check())
        if task=='PS4': result['dynamic']=grade_ps4(local,config['powershell']); result['passed'] &= result['dynamic']['passed']
        if task=='B3':
            invocation=bridge({'action':'invoke','directory':remote,'script':'broken.sh','args':[]})
            result['dynamic']={'passed':invocation['exit_code']==0,'exit_code':invocation['exit_code']}; result['passed'] &= result['dynamic']['passed']
            after=static_grade(task,snapshot(local),bridge({'action':'snapshot','directory':remote})['files'],lock_valid=check())
            result['after_reexecution']=after; result['passed'] &= after['passed']
        if task=='B4': result['dynamic']=grade_b4(bridge,remote); result['passed'] &= result['dynamic']['passed']
        trace=execution_trace(task,events,alias,remote,local)
        result['execution_trace']=trace; result['passed'] &= all(trace.values())
        if task in ['S2','S3'] and not all(trace.values()):
            result['trace_review_required']=True
            result['trace_review_note']='Shell trace recognition is conservative; inspect dynamic or control-flow commands manually before attributing a model failure.'
        # Check again after executing repaired programs to detect grader changes.
        result['lock_after_dynamic']=check(); result['passed'] &= result['lock_after_dynamic']
        return result
    return run(profile,prompt(task,local,remote,alias),local,task_id=task,limit=480 if task in ['S3','S4'] else 300,validator=validate,lock_check=check)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--profile',required=True,choices=['qwen','lfm','glm']); ap.add_argument('--task',required=True,choices=list(TASKS)); ap.add_argument('--host'); a=ap.parse_args()
    trial(a.profile,a.task,a.host)
