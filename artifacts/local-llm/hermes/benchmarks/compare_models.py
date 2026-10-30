"""Reproducible HumanEval subset plus native Hermes tasks on the two installed profiles."""
import ctypes
from ctypes import wintypes as w
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
import urllib.request

BENCH=Path(__file__).resolve().parent; ROOT=BENCH.parent
INSTALL=json.loads((ROOT/'installation.json').read_text(encoding='utf-8'))
RETRY_SOURCE=Path(sys.argv[sys.argv.index('--retry-schema')+1]) if '--retry-schema' in sys.argv else None
PREVIOUS=json.loads((RETRY_SOURCE/'results.json').read_text(encoding='utf-8')) if RETRY_SOURCE else None
ENV=dict(os.environ,HERMES_HOME=INSTALL['hermes_home'],PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
DATA=[json.loads(line) for line in gzip.decompress((BENCH/'HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
SELECTED=[DATA[i] for i in sorted(random.Random(42).sample(range(len(DATA)),20))]

# A worker waits for stdin until assigned to a job. Generated code has no file/process/network builtins.
class BasicLimits(ctypes.Structure):
    _fields_=[('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',w.DWORD),('MinWS',ctypes.c_size_t),('MaxWS',ctypes.c_size_t),('ActiveProcesses',w.DWORD),('Affinity',ctypes.c_size_t),('Priority',w.DWORD),('Scheduling',w.DWORD)]
class IO(ctypes.Structure): _fields_=[(n,ctypes.c_uint64) for n in ['ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes']]
class ExtendedLimits(ctypes.Structure):
    _fields_=[('Basic',BasicLimits),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
K=ctypes.WinDLL('kernel32',use_last_error=True)
K.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR]; K.CreateJobObjectW.restype=w.HANDLE
K.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
K.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
K.CloseHandle.argtypes=[w.HANDLE]
def grade(code,problem):
    job=K.CreateJobObjectW(None,None)
    if not job: raise ctypes.WinError(ctypes.get_last_error())
    child=None
    try:
        limits=ExtendedLimits(); limits.Basic.Flags=0x2000|0x100|0x8
        limits.Basic.ActiveProcesses=1; limits.ProcessMemory=256*1024*1024
        if not K.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)): raise ctypes.WinError(ctypes.get_last_error())
        child=subprocess.Popen([sys.executable,'-I',str(BENCH/'grade_worker.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        if not K.AssignProcessToJobObject(job,w.HANDLE(int(child._handle))): raise ctypes.WinError(ctypes.get_last_error())
        payload=json.dumps({'code':code,'test':problem['test'],'entry_point':problem['entry_point']})
        try: out,err=child.communicate(payload,timeout=6)
        except subprocess.TimeoutExpired:
            child.kill(); child.communicate(); return {'passed':False,'status':'timeout'}
        if child.returncode: return {'passed':False,'status':'worker_error','returncode':child.returncode,'detail':err[-300:]}
        return json.loads(out)
    finally:
        if child and child.poll() is None: child.kill(); child.wait()
        K.CloseHandle(job)

def canonical_selfcheck():
    checks=[{'task_id':p['task_id'],**grade(p['prompt']+p['canonical_solution'],p)} for p in SELECTED]
    (BENCH/'canonical-selfcheck.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks): raise RuntimeError('Canonical self-check failed: '+str([c for c in checks if not c['passed']]))
    print(json.dumps({'canonical_selfcheck':'passed','tasks':len(checks)}),flush=True)
if '--selfcheck' in sys.argv:
    canonical_selfcheck(); sys.exit(0)

STAMP=dt.datetime.now().strftime('%Y%m%d-%H%M%S'); OUT=BENCH/('comparison-'+STAMP); OUT.mkdir()
WORK=Path(INSTALL['workspace'])/('comparison-'+STAMP); WORK.mkdir()
class Memory(ctypes.Structure):
    _fields_=[('length',w.DWORD),('load',w.DWORD)]+[(n,ctypes.c_uint64) for n in ['total','available','pageTotal','pageAvailable','virtTotal','virtAvailable','extended']]
def available():
    m=Memory(); m.length=ctypes.sizeof(m); K.GlobalMemoryStatusEx(ctypes.byref(m)); return m.available/2**30
STATE={'profile':None,'phase':'setup','active':False}; SAMPLES=[]; STOP=threading.Event(); GUARD=threading.Event()
def lifecycle(action,profile):
    return subprocess.run([sys.executable,str(ROOT/'server.py'),action,profile],env=ENV,capture_output=True,text=True,encoding='utf-8',timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
def monitor():
    tick=0; low=0
    while not STOP.is_set():
        row={'at':dt.datetime.now().astimezone().isoformat(),**STATE,'available_ram_gib':round(available(),3)}
        if tick%5==0:
            try:
                gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
                if gpu.returncode==0: row['gpu_used_mib']=int(gpu.stdout.strip())
            except Exception: pass
        SAMPLES.append(row)
        with (OUT/'memory.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(row)+'\n')
        low=low+1 if STATE['active'] and row['available_ram_gib']<1 else 0
        if low>=3:
            GUARD.set()
            if STATE['profile']: lifecycle('stop',STATE['profile'])
            return
        tick+=1; STOP.wait(2)
def api(path,payload=None,timeout=180):
    request=urllib.request.Request('http://127.0.0.1:8089'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=timeout) as r:return json.load(r)
def unwrap_code(text,prompt,entry):
    fence=re.search(r'```(?:python|py)?\s*\n(.*?)```',text,re.S)
    code=fence.group(1) if fence else text.strip()
    if re.search(r'\bdef\s+'+re.escape(entry)+r'\s*\(',code):
        imports='\n'.join(line for line in prompt.splitlines() if line.startswith(('import ','from ')))
        return imports+'\n'+code
    import textwrap
    return prompt+textwrap.indent(textwrap.dedent(code),'    ')+'\n'
def write_report(report):
    (OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
def session_tools(log):
    finals=[]
    for line in log.read_text(encoding='utf-8').splitlines():
        try:
            e=json.loads(line)
            if e.get('type')=='result':finals.append(e)
        except ValueError:pass
    if not finals:return None,[]
    sid=finals[-1]['session_id']
    db=sqlite3.connect((Path(INSTALL['hermes_home'])/'state.db').as_uri()+'?mode=ro',uri=True); db.row_factory=sqlite3.Row
    rows=[]
    for r in db.execute("SELECT tool_name,content FROM messages WHERE session_id=? AND role='tool' ORDER BY id",(sid,)):
        try:content=json.loads(r['content'])
        except ValueError:content={'text':r['content']}
        rows.append({'name':r['tool_name'],'result':content})
    db.close(); return sid,rows
def agent_task(profile,alias,kind):
    directory=WORK/profile/kind; directory.mkdir(parents=True)
    marker='BENCH_'+kind.upper()+'_OK'; expected=None
    if kind=='json':
        fixture={'ticket':'comparison-'+STAMP,'amounts':[137,259,83,41]}
        (directory/'input.json').write_text(json.dumps(fixture,indent=2),encoding='utf-8')
        prompt='Read input.json with read_file, run exactly `echo '+marker+'` with terminal, then write output.json. Required JSON schema: an object with EXACTLY these four keys: "ticket" (string copied from input), "count" (integer number of amounts), "total" (integer sum of amounts), "terminal_marker" (string copied from actual echo output). Use "count", not "amount_count" or any other key name. Do not change input.json. Be concise.'
        expected={'ticket':fixture['ticket'],'count':4,'total':520,'terminal_marker':marker}; required={'read_file','terminal','write_file'}
    elif kind=='csv':
        (directory/'orders.csv').write_text('group,status,quantity,unit_cents\nA,paid,2,125\nB,paid,3,70\nA,pending,100,999\nA,paid,1,95\nB,cancelled,5,700\nA,paid,-1,30\n',encoding='utf-8')
        prompt='Read orders.csv with read_file. Include only status exactly paid, including negative quantities as refunds. Compute row count and sum(quantity*unit_cents) per group using integers. Run exactly `echo '+marker+'` with terminal. Write output.json. Required JSON schema: an object with EXACTLY three keys: "paid_orders" (integer row count), "totals_cents" (object mapping each group name DIRECTLY to an integer total, never a nested object; example shape {"A":123,"B":456}, these example numbers are not answers), and "terminal_marker" (string from the actual command output). Do not add per-group counts or other keys. Keep input unchanged. Be concise.'
        expected={'paid_orders':4,'totals_cents':{'A':315,'B':210},'terminal_marker':marker}; required={'read_file','terminal','write_file'}
    else:
        (directory/'intervals.py').write_text('def merge_intervals(intervals):\n    ordered = sorted(intervals)\n    result = []\n    for start, end in ordered:\n        if result and start <= result[-1][1]:\n            result[-1][1] = end\n        else:\n            result.append([start, end])\n    return result\n',encoding='utf-8')
        prompt='Read intervals.py and fix merge_intervals with a targeted patch. It must merge overlapping or touching closed intervals, handle contained intervals without shrinking an existing end, sort unsorted inputs, return [] for empty input, and leave the caller input unchanged. Then use terminal to run exactly `echo '+marker+'`. Do not add files. Be concise.'
        required={'read_file','patch','terminal'}
    input_hash={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.name!='intervals.py'}
    log=OUT/(profile+'-'+kind+'.jsonl'); err=OUT/(profile+'-'+kind+'.stderr.log')
    query=OUT/(kind+'-query.txt'); query.write_text(prompt,encoding='utf-8')
    command=[INSTALL['hermes_launcher'],'chat','--cli','--oneshot','--query-file',str(query),'--provider','local-qwen','--model',alias,'--in',str(directory),'--max-turns','12','--format','stream-json']
    started=time.monotonic(); timeout=False
    with log.open('w',encoding='utf-8') as out,err.open('w',encoding='utf-8') as stderr:
        child=subprocess.Popen(command,env=ENV,stdout=out,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        while child.poll() is None:
            if GUARD.is_set() or time.monotonic()-started>240:
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);timeout=True;break
            time.sleep(1)
    sid,tools=session_tools(log)
    terminal_ok=any(t['name']=='terminal' and t['result'].get('exit_code')==0 and t['result'].get('output','').strip()==marker for t in tools)
    artifact=False; detail=None
    if kind=='repair':
        tests='def check(candidate):\n    assert candidate([])==[]\n    assert candidate([[1,10],[2,3]])==[[1,10]]\n    assert candidate([[8,10],[1,4],[3,6]])==[[1,6],[8,10]]\n    assert candidate([[1,3],[3,5]])==[[1,5]]\n    data=[[5,7],[1,9],[2,3]]\n    assert candidate(data)==[[1,9]]\n    assert data==[[5,7],[1,9],[2,3]]\n'
        detail=grade((directory/'intervals.py').read_text(encoding='utf-8'),{'test':tests,'entry_point':'merge_intervals'});artifact=detail['passed']
    else:
        try:detail=json.loads((directory/'output.json').read_text(encoding='utf-8-sig'));artifact=detail==expected
        except Exception as exc:detail=str(exc)
    unchanged=all((directory/name).exists() and hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest for name,digest in input_hash.items())
    workflow=required.issubset({t['name'] for t in tools}) and terminal_ok
    return {'task':kind,'seconds':round(time.monotonic()-started,2),'session_id':sid,'exit_code':child.poll(),'timeout':timeout,'artifact_correct':artifact,'workflow_correct':workflow,'input_unchanged':unchanged,'passed':artifact and workflow and unchanged and not timeout and child.poll()==0,'artifact':detail,'tools':tools}

canonical_selfcheck()
gateway_status=subprocess.run([INSTALL['hermes_launcher'],'gateway','status'],env=ENV,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
initial_gateway_running='Gateway is running' in gateway_status.stdout
try:
    api('/props');raise RuntimeError('A model is already running; stop it from its owner first')
except OSError:pass
tracked=[ROOT/'profiles/daily.json',ROOT/'profiles/large.json',Path(INSTALL['hermes_home'])/'config.yaml']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
report={'started_at':dt.datetime.now().astimezone().isoformat(),'directory':str(OUT),'dataset_commit':(BENCH/'humaneval-revision.txt').read_text().strip(),'dataset_sha256':hashlib.sha256((BENCH/'HumanEval.jsonl.gz').read_bytes()).hexdigest(),'selection_seed':42,'task_ids':[p['task_id'] for p in SELECTED],'model_order':['daily','large'],'models':{},'limitations':['20/164 HumanEval tasks, one greedy sample each; instruction-adapted dataset with guarded custom execution, not an official full leaderboard score','One trial per Hermes task, not a general success-rate estimate','Different Qwen generations, quantizations and CPU/GPU placement; this compares the installed configurations, not parameter count alone','HumanEval thinking off, max_tokens 1024, temperature 0, seed 42; Hermes uses the same existing user configuration with thinking enabled','Memory values are sampled system availability and system GPU usage; not model-only allocations or exact peaks']}
thread=threading.Thread(target=monitor,daemon=True);thread.start()
if RETRY_SOURCE:
    report['schema_retry']={'original_run':str(RETRY_SOURCE),'reason':'Original JSON/CSV prompts did not specify the exact output schema sufficiently. Both models rerun on both clarified tasks. Original task results retained, not counted in final strict scores. HumanEval and repair results are reused from the original run, without resampling.'}
try:
    for profile in ['daily','large']:
        STATE.update(profile=profile,phase='load',active=True)
        print(json.dumps({'phase':'load','profile':profile,'directory':str(OUT)}),flush=True)
        loaded=lifecycle('start',profile)
        (OUT/(profile+'-load.log')).write_text(loaded.stdout+'\n'+loaded.stderr,encoding='utf-8')
        if loaded.returncode:raise RuntimeError('Failed model load: '+profile)
        props=api('/props');p=json.loads((ROOT/'profiles'/(profile+'.json')).read_text(encoding='utf-8'))
        if props['model_alias']!=p['profile_id'] or props['default_generation_settings']['n_ctx']!=65536:raise RuntimeError('Model identity/context differs')
        model={'alias':props['model_alias'],'model_file':props['model_path'],'model_hash':p['model_hash'],'runtime':props['build_info'],'context':65536,'baseline_ram_gib':round(available(),3),'humaneval':[],'hermes':[]}
        if PREVIOUS:
            model['humaneval']=PREVIOUS['models'][profile]['humaneval']
            model['hermes']=[r for r in PREVIOUS['models'][profile]['hermes'] if r['task']=='repair']
        report['models'][profile]=model; write_report(report)
        # Same warm-up; excluded from task latency aggregates.
        api('/v1/chat/completions',{'model':p['profile_id'],'messages':[{'role':'user','content':'Reply OK.'}],'max_tokens':8,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}})
        for problem in ([] if RETRY_SOURCE else SELECTED):
            STATE['phase']='humaneval/'+problem['task_id']
            payload={'model':p['profile_id'],'messages':[{'role':'system','content':'Implement the requested Python function. Return only a complete Python module with the specified signature and required imports. Do not include explanations, markdown, or tests.'},{'role':'user','content':problem['prompt']}],'temperature':0,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'seed':42,'max_tokens':1024,'chat_template_kwargs':{'enable_thinking':False},'cache_prompt':False}
            started=time.monotonic();response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-started
            text=response['choices'][0]['message'].get('content') or ''
            code=unwrap_code(text,problem['prompt'],problem['entry_point'])
            outcome=grade(code,problem)
            item={'task_id':problem['task_id'],'seconds':round(elapsed,3),'finish_reason':response['choices'][0].get('finish_reason'),'usage':response.get('usage'),'timings':response.get('timings'),'content':text,'code':code,**outcome}
            model['humaneval'].append(item);write_report(report)
            print(json.dumps({'profile':profile,'task':problem['task_id'],'passed':outcome['passed'],'seconds':round(elapsed,1),'available_ram_gib':round(available(),2)}),flush=True)
            if GUARD.is_set():raise RuntimeError('Memory guard stopped the model')
        for kind in (['json','csv'] if RETRY_SOURCE else ['json','csv','repair']):
            STATE['phase']='hermes/'+kind
            print(json.dumps({'profile':profile,'phase':STATE['phase']}),flush=True)
            item=agent_task(profile,p['profile_id'],kind);model['hermes'].append(item);write_report(report)
            print(json.dumps({'profile':profile,'hermes_task':kind,'passed':item['passed'],'seconds':item['seconds']}),flush=True)
            if GUARD.is_set():raise RuntimeError('Memory guard stopped the model')
        STATE['phase']='stop'; lifecycle('stop',profile);STATE['active']=False
        # The preflight found no gateway; only the trial's automatically started gateway is stopped.
        if not initial_gateway_running:
            subprocess.run([INSTALL['hermes_launcher'],'gateway','stop'],env=ENV,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(3)
except Exception as exc:
    report['error']=str(exc)
finally:
    if STATE['active'] and STATE['profile']:
        try:lifecycle('stop',STATE['profile'])
        except Exception as exc:report['cleanup_error']=str(exc)
    STATE['active']=False;STOP.set();thread.join(timeout=10)
    for profile,model in report['models'].items():
        rows=[s for s in SAMPLES if s['profile']==profile]
        model['minimum_available_ram_gib']=min((s['available_ram_gib'] for s in rows),default=None)
        model['maximum_system_gpu_mib']=max((s['gpu_used_mib'] for s in rows if 'gpu_used_mib'in s),default=None)
        if PREVIOUS:
            model['minimum_available_ram_gib']=min(model['minimum_available_ram_gib'],PREVIOUS['models'][profile]['minimum_available_ram_gib'])
            model['maximum_system_gpu_mib']=max(model['maximum_system_gpu_mib'],PREVIOUS['models'][profile]['maximum_system_gpu_mib'])
        h=model['humaneval'];a=model['hermes']
        model['summary']={'humaneval_passed':sum(x['passed'] for x in h),'humaneval_attempted':len(h),'humaneval_median_seconds':round(statistics.median(x['seconds'] for x in h),2) if h else None,'humaneval_total_seconds':round(sum(x['seconds'] for x in h),2),'hermes_passed':sum(x['passed'] for x in a),'hermes_attempted':len(a),'hermes_total_seconds':round(sum(x['seconds'] for x in a),2)}
    report['settings_unchanged']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p)] for p in tracked}
    report['finished_at']=dt.datetime.now().astimezone().isoformat();write_report(report)
    print(json.dumps({'report':str(OUT/'results.json'),'models':{p:m['summary'] for p,m in report['models'].items()},'error':report.get('error')}),flush=True)
