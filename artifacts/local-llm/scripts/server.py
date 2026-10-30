"""Single-model server lifecycle. Uses an argument vector; never a shell string."""
import argparse, datetime, json, pathlib, socket, subprocess, sys, time, urllib.request

for stream in [sys.stdout,sys.stderr]:
    if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8',errors='replace')

ROOT=pathlib.Path(r'C:\LocalLLM')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load_profile(name): return json.loads((ROOT/'profiles'/f'{name}.json').read_text(encoding='utf-8'))
def get_json(url):
    with urllib.request.urlopen(url,timeout=3) as r: return json.load(r)

def start(name):
    state=ROOT/'server-state.json'
    if state.exists():
        old=json.loads(state.read_text())
        p=subprocess.run(['tasklist','/FI',f"PID eq {old['pid']}",'/FO','CSV','/NH'],capture_output=True,text=True)
        if 'llama-server.exe' in p.stdout:
            raise RuntimeError('A managed model is already running. Stop it before loading another.')
    p=load_profile(name)
    binary=ROOT/p['runtime_executable']; model=ROOT/p['model']
    if not model.exists(): raise FileNotFoundError(model)
    manifest=json.loads((ROOT/'model-manifest.json').read_text(encoding='utf-8'))
    if not any(x['filename']==model.name and x['sha256']==p['model_hash'] and x['bytes']==model.stat().st_size for x in manifest):
        raise RuntimeError('Verified model manifest entry required')
    try:
        connection=socket.create_connection(('127.0.0.1',p['port']),timeout=1)
    except OSError: pass
    else:
        connection.close()
        raise RuntimeError(f"Port {p['port']} is already in use; refusing to attach to another server")
    diagnostic=p.get('diagnostic_cpu_only',False)
    if diagnostic:
        if '--device' not in p['server_args'] or p['server_args'][p['server_args'].index('--device')+1]!='none':
            raise RuntimeError('CPU diagnostic must explicitly select device none')
    else:
        probe=subprocess.run([str(binary),'--list-devices'],cwd=binary.parent,capture_output=True,timeout=90)
        device_log=probe.stdout+probe.stderr
        (ROOT/'logs/device-preflight.log').write_bytes(device_log)
        if probe.returncode or b'CUDA0' not in device_log:
            raise RuntimeError('CUDA0 unavailable. Check logs/device-preflight.log and Windows Code Integrity policy; refusing CPU fallback.')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    log=ROOT/'logs'/f'server-{name}-{stamp}.log'
    args=[str(binary),'-m',str(model),'--host','127.0.0.1','--port',str(p['port']),'--alias',p['profile_id']]+p['server_args']
    started=time.monotonic()
    with log.open('wb') as f:
        proc=subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT,cwd=binary.parent,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    record={'pid':proc.pid,'profile':name,'profile_id':p['profile_id'],'diagnostic_cpu_only':diagnostic,'started_utc':now(),'args':args,'log':str(log),'ready':False}
    state.write_text(json.dumps(record,indent=2),encoding='utf-8')
    for _ in range(600):
        if proc.poll() is not None: raise RuntimeError(f'Server exited {proc.returncode}; see {log}')
        try:
            if get_json(p['base_url']+'/health').get('status')=='ok': break
        except Exception: pass
        time.sleep(1)
    else: raise TimeoutError(f'Server not ready; see {log}')
    props=get_json(p['base_url']+'/props')
    if props.get('model_alias')!=p['profile_id'] or not props.get('build_info','').startswith(p['runtime_build']+'-'):
        raise RuntimeError('Ready endpoint does not match the requested profile and runtime build')
    record.update(ready=True,load_seconds=time.monotonic()-started,ready_utc=now())
    state.write_text(json.dumps(record,indent=2),encoding='utf-8')
    (ROOT/'runs'/f'load-{name}-{stamp}.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    (ROOT/'runs'/f'props-{name}-{stamp}.json').write_text(json.dumps(props,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False),flush=True)

def stop():
    state=ROOT/'server-state.json'
    if not state.exists(): return
    record=json.loads(state.read_text())
    # Check the executable and creation timestamp to avoid killing a recycled PID.
    script="$p=Get-CimInstance Win32_Process -Filter 'ProcessId="+str(record['pid'])+"'; $started=[DateTimeOffset]::Parse('"+record['started_utc']+"').UtcDateTime; if ($p) { if ($p.Name -ne 'llama-server.exe' -or $p.ExecutablePath -ne '"+record['args'][0]+"' -or [Math]::Abs(($p.CreationDate.ToUniversalTime()-$started).TotalSeconds) -gt 2) { throw 'PID identity differs from managed server' }; $managed=Get-Process -Id $p.ProcessId -ErrorAction Stop; Stop-Process -InputObject $managed -Force -ErrorAction Stop; if (-not $managed.WaitForExit(15000)) { throw 'Managed server did not exit' } }"
    subprocess.run(['powershell.exe','-NoProfile','-Command',script],check=True,capture_output=True)
    state.unlink()
    print(json.dumps({'event':'server_stopped','pid':record['pid'],'at':now()}))

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['start','stop']); ap.add_argument('profile',nargs='?',default='qwen'); a=ap.parse_args()
    start(a.profile) if a.action=='start' else stop()
