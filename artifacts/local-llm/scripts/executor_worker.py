"""Job worker and JSON RPC, shared by Windows PowerShell and SSH Linux Bash.

State lives outside fixture directories. Script text goes to UTF-8 files.
Linux requires python3, bash and POSIX process groups; no PTY is allocated.
"""
import base64, codecs, datetime, json, os, pathlib, signal, subprocess, sys, time, uuid

def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(path,data):
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path)
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def process_identity(pid):
    if os.name!='nt':
        try: return pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
        except FileNotFoundError: return None
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]; kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    h=kernel.OpenProcess(0x1000,False,pid)
    if not h: return None
    try:
        created=ctypes.c_ulonglong(); exited=ctypes.c_ulonglong(); cpu_kernel=ctypes.c_ulonglong(); cpu_user=ctypes.c_ulonglong()
        return str(created.value) if kernel.GetProcessTimes(h,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(cpu_kernel),ctypes.byref(cpu_user)) else None
    finally: kernel.CloseHandle(h)
def check_cwd(cwd,root):
    p=pathlib.Path(cwd).resolve(); r=pathlib.Path(root).resolve()
    if not p.is_relative_to(r): raise ValueError('cwd must be inside configured workspace')
    if not p.is_dir(): raise ValueError('cwd does not exist')
    return str(p)

def launch(request):
    request['cwd']=check_cwd(request['cwd'],request['workspace_root'])
    root=pathlib.Path(request['state_root']).resolve(); root.mkdir(parents=True,exist_ok=True)
    job_id=request.get('job_id') or uuid.uuid4().hex
    if len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id): raise ValueError('Invalid managed job id')
    d=root/job_id
    if d.exists():
        old=read(d/'request.json')
        if any(old.get(k)!=request.get(k) for k in ['script','cwd','env','host','powershell']): raise ValueError('Job id belongs to a different request')
        return poll(root,job_id)
    d.mkdir()
    request.update(job_id=job_id,started_utc=utc(),host=request['host'],status='starting')
    put(d/'request.json',request)
    kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    with (d/'worker.log').open('wb') as f:
        proc=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'work',str(d)],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,**kwargs)
    put(d/'worker.json',{'pid':proc.pid,'identity':process_identity(proc.pid)})
    deadline=time.monotonic()+min(max(float(request.get('timeout',1)),0),60)
    while time.monotonic()<deadline and not (d/'status.json').exists(): time.sleep(.05)
    return poll(root,job_id,0,0)

def work(d):
    r=read(d/'request.json'); started=utc(); shell_status=d/'shell-status.json'
    env=os.environ.copy(); env.update(r.get('env',{}))
    if os.name=='nt':
        script=d/'command.ps1'; script.write_text(r['script'],encoding='utf-8-sig',newline='')
        wrapper=d/'wrapper.ps1'
        wrapper.write_text("""param([string]$ScriptPath,[string]$StatusPath)
[Console]::InputEncoding=[Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$OutputEncoding=[Text.UTF8Encoding]::new($false)
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$true
$LASTEXITCODE=0
$kind='success'; $code=0; $errorInfo=$null
try {
  # Drain PowerShell's formatting pipeline before the explicit process exit.
  # Otherwise PSCustomObject/FileInfo output can disappear at shutdown.
  $script:commandSucceeded=$false
  & {
    & $ScriptPath
    $script:commandSucceeded=$?
  } | Out-Default
  if (-not $script:commandSucceeded) {
    if ($LASTEXITCODE -ne 0) { $code=$LASTEXITCODE; $kind='script_or_native_exit' }
    else { $code=1; $kind='powershell_failure' }
  }
} catch {
  $errorInfo=[ordered]@{message=$_.Exception.Message; type=$_.Exception.GetType().FullName; fully_qualified_error_id=$_.FullyQualifiedErrorId}
  if ($_.Exception -is [System.Management.Automation.NativeCommandExitException]) { $code=$_.Exception.ExitCode; $kind='native_exit' }
  else { $code=1; $kind='powershell_exception' }
  [Console]::Error.WriteLine($_.ToString())
} finally {
  [ordered]@{kind=$kind; exit_code=$code; last_native_exit_code=$LASTEXITCODE; error=$errorInfo} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatusPath -Encoding utf8
}
exit $code
""",encoding='utf-8-sig')
        command=[r['powershell'],'-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(wrapper),str(script),str(shell_status)]
        kwargs={'creationflags':subprocess.CREATE_NO_WINDOW}
    else:
        script=d/'command.sh'; script.write_text(r['script'],encoding='utf-8',newline='')
        command=['bash',str(script)]; kwargs={'start_new_session':True}
    with (d/'stdout.bin').open('wb') as out, (d/'stderr.bin').open('wb') as err:
        p=subprocess.Popen(command,cwd=r['cwd'],env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,**kwargs)
        try:
            put(d/'process.json',{'pid':p.pid,'identity':process_identity(p.pid),'started_utc':started,'command':command})
            code=p.wait()
        except BaseException:
            # A failure after Popen must not silently leave an unmanaged child.
            # The Popen handle still identifies this child until it is reaped.
            if p.poll() is None:
                try:
                    if os.name=='nt': subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10)
                    else: os.killpg(p.pid,signal.SIGKILL)
                except Exception: pass
                try:
                    if p.poll() is None: p.kill()
                    p.wait(timeout=10)
                except Exception: pass
            raise
    shell=read(shell_status) if shell_status.exists() else None
    put(d/'status.json',{'job_id':r['job_id'],'status':'completed','exit_code':code,'started_utc':started,'ended_utc':utc(),'host':r['host'],'cwd':r['cwd'],'shell_status':shell})

def job_dir(root,job_id):
    if len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id): raise ValueError('invalid managed job id')
    d=pathlib.Path(root).resolve()/job_id
    if not (d/'request.json').exists(): raise ValueError('unknown managed job id')
    return d

def poll(root,job_id,stdout_offset=0,stderr_offset=0,max_bytes=32768):
    d=job_dir(root,job_id); r=read(d/'request.json')
    state=read(d/'status.json') if (d/'status.json').exists() else {'job_id':job_id,'status':'running','exit_code':None,'host':r['host'],'cwd':r['cwd'],'started_utc':r['started_utc'],'ended_utc':None}
    for name,offset in [('stdout',stdout_offset),('stderr',stderr_offset)]:
        path=d/(name+'.bin'); size=path.stat().st_size if path.exists() else 0
        if offset<0 or offset>size: raise ValueError('invalid output offset')
        data=b''
        if size:
            with path.open('rb') as f: f.seek(offset); data=f.read(max_bytes)
        # Keep the next offset on a UTF-8 boundary so incremental polling does not
        # replace the two halves of a Japanese character with replacement glyphs.
        if data and (offset+len(data)<size or state['status']=='running'):
            decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
            decoder.decode(data,final=False); pending=decoder.getstate()[0]
            if pending: data=data[:-len(pending)]
        state[name+'_base64']=base64.b64encode(data).decode('ascii')
        state[name+'_offset']=offset; state[name+'_next_offset']=offset+len(data)
        state[name+'_bytes']=size; state[name+'_truncated']=offset+len(data)<size
        state[name+'_log']=str(path)
    state['timeout_means']='wait ended; job remains running' if state['status']=='running' else None
    state['real_execution']=True
    return state

def stop(root,job_id):
    d=job_dir(root,job_id)
    def terminal():
        path=d/'status.json'
        return path.exists() and read(path).get('status')!='unknown'
    if terminal(): return poll(root,job_id)
    deadline=time.monotonic()+3
    while not (d/'process.json').exists() and not terminal() and time.monotonic()<deadline: time.sleep(.05)
    if terminal(): return poll(root,job_id)
    if not (d/'process.json').exists():
        if (d/'status.json').exists(): return poll(root,job_id)
        raise RuntimeError('Job is still starting; stop not verified, poll before retrying')
    process=read(d/'process.json'); pid=process['pid']
    identity=process_identity(pid)
    if identity is not None and identity!=process.get('identity'):
        raise RuntimeError('PID identity differs from managed job; refusing to stop')
    if identity is None:
        deadline=time.monotonic()+3
        while not terminal() and time.monotonic()<deadline: time.sleep(.05)
        if (d/'status.json').exists(): return poll(root,job_id)
        raise RuntimeError('Managed process identity unavailable; poll before retrying stop')
    if os.name=='nt':
        stopped=subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,text=True)
        # Worker reaps the child and writes the real exit state.
        if stopped.returncode and not (d/'status.json').exists(): raise RuntimeError(stopped.stderr)
        deadline=time.monotonic()+10
        while not (d/'status.json').exists() and time.monotonic()<deadline: time.sleep(.05)
        state=poll(root,job_id); state['stop_verified']=state['status']=='completed'
    else:
        signal_error=None; group_gone=False
        try: os.killpg(pid,signal.SIGTERM)
        except ProcessLookupError: group_gone=True
        except OSError as e: signal_error=str(e)
        if signal_error is None and not group_gone:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try: os.killpg(pid,0)
                except ProcessLookupError:
                    group_gone=True; break
                except OSError as e:
                    signal_error=str(e); break
                time.sleep(.05)
        # Do not signal an already-vanished group: its numeric id can be reused.
        if signal_error is None and not group_gone:
            try: os.killpg(pid,signal.SIGKILL)
            except ProcessLookupError: group_gone=True
            except OSError as e: signal_error=str(e)
        deadline=time.monotonic()+10
        if signal_error is None:
            while True:
                # Recheck even if an earlier probe saw no group; an id may be reused.
                try: os.killpg(pid,0); group_gone=False
                except ProcessLookupError: group_gone=True
                except OSError as e:
                    group_gone=False; signal_error=str(e); break
                if group_gone and (d/'status.json').exists(): break
                if time.monotonic()>=deadline: break
                time.sleep(.05)
        state=poll(root,job_id)
        state['process_group_exited']=group_gone if signal_error is None else None
        state['stop_verified']=signal_error is None and group_gone and state['status']=='completed'
        if signal_error is not None: state['stop_error']=signal_error
    state['stop_scope']='Windows process tree' if os.name=='nt' else 'remote POSIX process group'
    if state['stop_verified']:
        state['stopped']=True
        put(d/'status.json',{k:v for k,v in state.items() if not k.endswith('_base64')})
    return state

def rpc(r):
    action=r.pop('action')
    if action=='start': return launch(r)
    if action=='poll': return poll(r['state_root'],r['job_id'],r.get('stdout_offset',0),r.get('stderr_offset',0),r.get('max_bytes',32768))
    if action=='stop': return stop(r['state_root'],r['job_id'])
    raise ValueError('unknown action')

def record_worker_exception(directory,error):
    # An exception can occur after the shell was started. The error alone is
    # not proof that the shell or its descendants have terminated.
    r=read(directory/'request.json')
    put(directory/'status.json',{'job_id':r['job_id'],'status':'unknown','exit_code':None,
        'started_utc':r['started_utc'],'ended_utc':None,'host':r['host'],'cwd':r['cwd'],
        'executor_error':str(error),'error_type':type(error).__name__,'may_be_running':True})

if __name__=='__main__':
    for stream in [sys.stdin,sys.stdout,sys.stderr]:
        if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8',errors='strict')
    if len(sys.argv)>1 and sys.argv[1]=='work':
        directory=pathlib.Path(sys.argv[2])
        try: work(directory)
        except Exception as e:
            record_worker_exception(directory,e)
            raise
    else:
        try: result=rpc(json.load(sys.stdin)); print(json.dumps(result,ensure_ascii=False))
        except Exception as e: print(json.dumps({'error':str(e),'type':type(e).__name__})); sys.exit(1)
