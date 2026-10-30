"""Bounded, monitored end-to-end Hermes trial; does not change the default model."""
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
install = json.loads((ROOT/'installation.json').read_text(encoding='utf-8'))
stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
OUT = ROOT/'runs'/('large-hermes-'+stamp)
OUT.mkdir()
WORK = Path(install['workspace'])/('large-trial-'+stamp)
WORK.mkdir()
env = dict(os.environ, HERMES_HOME=install['hermes_home'], PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
class MemoryStatus(ctypes.Structure):
    _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong),('total_phys',ctypes.c_ulonglong),
                ('avail_phys',ctypes.c_ulonglong),('total_pagefile',ctypes.c_ulonglong),
                ('avail_pagefile',ctypes.c_ulonglong),('total_virtual',ctypes.c_ulonglong),
                ('avail_virtual',ctypes.c_ulonglong),('avail_extended',ctypes.c_ulonglong)]
samples=[]
last_gpu=0
gpu=None
def sample(phase):
    global last_gpu,gpu
    m=MemoryStatus(); m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise ctypes.WinError()
    if time.monotonic()-last_gpu>6:
        try:
            s=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],
                             capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
            gpu=[int(v.strip()) for v in s.stdout.strip().split(',')] if s.returncode==0 else None
        except Exception: gpu=None
        last_gpu=time.monotonic()
    row={'at':dt.datetime.now().astimezone().isoformat(),'phase':phase,
         'available_ram_gib':round(m.avail_phys/2**30,3),'commit_headroom_gib':round(m.avail_pagefile/2**30,3),
         'gpu_used_mib':gpu[0] if gpu else None,'gpu_util_percent':gpu[1] if gpu else None}
    samples.append(row)
    with (OUT/'memory.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(row)+'\n')
    return row
def stop_model():
    state=ROOT/'server-state.json'
    if state.exists() and json.loads(state.read_text(encoding='utf-8')).get('profile')=='large':
        return subprocess.run([sys.executable,str(ROOT/'server.py'),'stop','large'],env=env,
                              capture_output=True,text=True,encoding='utf-8',timeout=45,
                              creationflags=subprocess.CREATE_NO_WINDOW).returncode
def watch(child,phase,timeout):
    start=time.monotonic(); last_notice=0; low=0
    try:
        while child.poll() is None:
            row=sample(phase)
            low=low+1 if row['available_ram_gib']<1 else 0
            if low>=3: raise RuntimeError('Resource guard: available RAM below 1 GiB for three samples; not an OOM')
            if time.monotonic()-start>timeout: raise TimeoutError(phase+' exceeded trial time budget')
            if time.monotonic()-last_notice>15:
                print(json.dumps({'phase':phase,'elapsed_s':round(time.monotonic()-start),**row}),flush=True)
                last_notice=time.monotonic()
            time.sleep(2)
        return child.returncode
    except BaseException:
        stop_model()
        if child.poll() is None:
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=20,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        raise
def get_props():
    with urllib.request.urlopen('http://127.0.0.1:8089/props',timeout=5) as response: return json.load(response)

report={'started_at':dt.datetime.now().astimezone().isoformat(),'directory':str(OUT),'workspace':str(WORK),
        'success':False,'default_model_changed':False,'test_model':'qwen3.6-35b-a3b-hermes-64k'}
hash_paths=[ROOT/'profiles/daily.json',ROOT/'profiles/large.json',Path(install['hermes_home'])/'config.yaml']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in hash_paths}
ticket='hermes35b-'+uuid.uuid4().hex[:12]
fixture={'ticket':ticket,'amounts':[137,259,83,41]}
expected={'ticket':ticket,'count':4,'total':520,'terminal_marker':'HERMES35B_TERMINAL_OK'}
(WORK/'input.json').write_text(json.dumps(fixture,indent=2),encoding='utf-8')
query=('Perform this local integration test using the actual tools, not a simulated answer. '
       'First read input.json with read_file. Then use the terminal tool to execute exactly '
       '`echo HERMES35B_TERMINAL_OK`. Then write output.json with exactly four keys: '
       'ticket copied from input.json, count equal to the number of amounts, total equal to their sum, '
       'and terminal_marker copied from the actual terminal output (trim whitespace). '
       'Do not change input.json. Finish with a concise result.')
(OUT/'query.txt').write_text(query,encoding='utf-8')
try:
    try:
        existing=get_props()
    except OSError: existing=None
    if existing: raise RuntimeError('A model is already running; refusing to replace it')
    report['baseline']=sample('baseline')
    print(json.dumps({'run_directory':str(OUT),'baseline':report['baseline']}),flush=True)
    with (OUT/'model-start.log').open('w',encoding='utf-8') as log:
        child=subprocess.Popen([sys.executable,str(ROOT/'launch.py'),'--model','large','--start-only'],
                               env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        code=watch(child,'model_load',180)
    if code: raise RuntimeError('Model launcher failed: '+str(code))
    props=get_props()
    report['served_model']={key:props.get(key) for key in ['model_alias','model_path','build_info','total_slots','default_generation_settings']}
    if props.get('model_alias')!=report['test_model'] or props['default_generation_settings']['n_ctx']!=65536:
        raise RuntimeError('Unexpected served model or context')
    command=[install['hermes_launcher'],'chat','--cli','--oneshot','--query-file',str(OUT/'query.txt'),
             '--provider','local-qwen','--model',report['test_model'],'--in',str(WORK),'--max-turns','12',
             '--format','stream-json']
    report['hermes_command']=command
    with (OUT/'hermes.stdout.jsonl').open('w',encoding='utf-8') as stdout, (OUT/'hermes.stderr.log').open('w',encoding='utf-8') as stderr:
        child=subprocess.Popen(command,env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        started=time.monotonic()
        report['hermes_exit_code']=watch(child,'hermes_tools',480)
        report['hermes_seconds']=round(time.monotonic()-started,2)
    if (WORK/'output.json').exists(): report['artifact']=json.loads((WORK/'output.json').read_text(encoding='utf-8-sig'))
    report['expected']=expected
    report['artifact_matches']=report.get('artifact')==expected
    report['input_unchanged']=json.loads((WORK/'input.json').read_text(encoding='utf-8'))==fixture
    report['success']=report['hermes_exit_code']==0 and report['artifact_matches'] and report['input_unchanged']
except Exception as exc:
    report['error']=str(exc)
finally:
    try: report['model_stop_exit_code']=stop_model()
    except Exception as exc: report['cleanup_error']=str(exc)
    report['final_sample']=sample('after_model_stop')
    report['minimum_available_ram_gib']=min(s['available_ram_gib'] for s in samples)
    report['maximum_system_gpu_used_mib']=max((s['gpu_used_mib'] for s in samples if s['gpu_used_mib'] is not None),default=None)
    report['settings_unchanged']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)] for p in hash_paths}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
