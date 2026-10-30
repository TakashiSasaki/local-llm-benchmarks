"""Bounded 64K capacity/retrieval and separate short Hermes tool smoke tests."""
import ctypes
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parent.parent
INSTALL=json.loads((ROOT/'installation.json').read_text(encoding='utf-8'))
ENV=dict(os.environ,HERMES_HOME=INSTALL['hermes_home'],PYTHONUTF8='1',PYTHONIOENCODING='utf-8',LLAMA_ARG_THINK='deepseek')
OUT=ROOT/'runs'/('context64k-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S'));OUT.mkdir()
(OUT/'context64k_probe.py').write_bytes(Path(__file__).read_bytes())
spec=importlib.util.spec_from_file_location('observed_memory',ROOT.parent/'scripts/memory.py')
memory=importlib.util.module_from_spec(spec);spec.loader.exec_module(memory)
TRACKED=[ROOT/'profiles/daily.json',ROOT/'profiles/large.json',Path(INSTALL['hermes_home'])/'config.yaml']
HASHES={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in TRACKED}
REPORT={'directory':str(OUT),'started_at':dt.datetime.now().astimezone().isoformat(),'context_requested':65536,'raw_target_input':63800,'raw_thinking':False,'models':{},'limitations':['One synthetic three-marker retrieval/tool test per model, not a long-context quality benchmark','Hermes smoke test is short and separate from the near-64K raw API test','No 64K generated output or extended autonomous workflow tested','Memory periodically sampled; not exact peaks or model-only allocations']}
STATE={'profile':None,'phase':'baseline','pid':None,'owned':False}
STOP=threading.Event();GUARD=threading.Event();SAMPLES=[]

def save(): (OUT/'results.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
def api(path,payload=None,timeout=600):
    req=urllib.request.Request('http://127.0.0.1:8089'+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def lifecycle(action,profile):
    return subprocess.run([sys.executable,str(ROOT/'server.py'),action,profile],env=ENV,capture_output=True,text=True,encoding='utf-8',timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
def stop_owned():
    if not STATE['owned']:return
    path=ROOT/'server-state.json'
    if path.exists():
        record=json.loads(path.read_text())
        if record['profile']!=STATE['profile'] or (STATE['pid'] is not None and record['pid']!=STATE['pid']):raise RuntimeError('Model ownership changed; refusing cleanup')
        stopped=lifecycle('stop',STATE['profile'])
        if stopped.returncode:raise RuntimeError('Cleanup failed: '+stopped.stderr)
    STATE['owned']=False
def monitor():
    low=0
    while not STOP.is_set():
        s=memory.snapshot(STATE['pid'] or os.getpid());s.update(at=dt.datetime.now().astimezone().isoformat(),profile=STATE['profile'],phase=STATE['phase'])
        SAMPLES.append(s)
        with (OUT/'memory.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(s)+'\n')
        low=low+1 if STATE['owned'] and s['available_ram_bytes']<2**30 else 0
        if low>=3:
            GUARD.set()
            try:stop_owned()
            except Exception as e:REPORT['guard_cleanup_error']=str(e)
            return
        STOP.wait(2)
def token_count(payload):
    rendered=api('/apply-template',{k:v for k,v in payload.items() if k in ('messages','tools','tool_choice','chat_template_kwargs')},timeout=30)
    return len(api('/tokenize',{'content':rendered['prompt'],'add_special':False},timeout=30)['tokens'])

TOOLS=[{'type':'function','function':{'name':'record_markers','description':'Record the three exact marker values found in the supplied log.','parameters':{'type':'object','properties':{k:{'type':'string'} for k in ['alpha','beta','gamma']},'required':['alpha','beta','gamma'],'additionalProperties':False}}}]
EXPECTED={'alpha':'violet-7429','beta':'amber-5183','gamma':'cobalt-9067'}
def payload_for(lines,alias):
    rows=[f'row {i:05d} subsystem=worker status=OK latency={10+i%19} tag={i*7919%100003:05d}' for i in range(lines)]
    for fraction,(key,value) in zip([.1,.5,.9],EXPECTED.items()):rows[int(lines*fraction)]=f'IMPORTANT marker {key} = {value}'
    messages=[{'role':'system','content':'Read the supplied log and call record_markers with its three exact IMPORTANT marker values. Do not infer values from ordinary rows.'},{'role':'user','content':'BEGIN LOG\n'+'\n'.join(rows)+'\nEND LOG\nCall record_markers for alpha, beta and gamma.'}]
    return {'model':alias,'messages':messages,'tools':TOOLS,'tool_choice':{'type':'function','function':{'name':'record_markers'}},'chat_template_kwargs':{'enable_thinking':False},'max_tokens':512,'temperature':0,'top_p':1,'top_k':0,'seed':42,'cache_prompt':False}

def raw_probe(profile,alias):
    lo,hi=3,5000
    while lo<hi:
        mid=(lo+hi+1)//2
        if token_count(payload_for(mid,alias))<=63800:lo=mid
        else:hi=mid-1
    payload=payload_for(lo,alias);n=token_count(payload)
    if not 63500<=n<=63800 or n+512>=65536:raise RuntimeError('Input sizing failed')
    (OUT/(profile+'-long-request.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'profile':profile,'phase':'near64k','rendered_input_tokens':n}),flush=True)
    STATE['phase']='near64k';start=time.monotonic();response=api('/v1/chat/completions',payload)
    elapsed=round(time.monotonic()-start,2)
    (OUT/(profile+'-long-response.json')).write_text(json.dumps(response,ensure_ascii=False,indent=2),encoding='utf-8')
    msg=response['choices'][0]['message'];calls=msg.get('tool_calls') or []
    arguments=json.loads(calls[0]['function']['arguments']) if calls else None
    correct=len(calls)==1 and calls[0]['function']['name']=='record_markers' and arguments==EXPECTED
    item={'rendered_input_tokens':n,'output_limit':512,'seconds':elapsed,'usage':response.get('usage'),'timings':response.get('timings'),'finish_reason':response['choices'][0].get('finish_reason'),'marker_arguments':arguments,'markers_correct':correct,'reasoning_observed':bool(msg.get('reasoning_content'))}
    if correct:
        # Execute only this deterministic local fixture acknowledgement; no external function runs.
        messages=payload['messages']+[msg,{'role':'tool','tool_call_id':calls[0]['id'],'content':'Markers verified and recorded. Reply exactly OK.'}]
        follow={'model':alias,'messages':messages,'tools':TOOLS,'tool_choice':'none','chat_template_kwargs':{'enable_thinking':False},'max_tokens':128,'temperature':0,'cache_prompt':True}
        item['followup_rendered_tokens']=token_count(follow)
        if item['followup_rendered_tokens']+128>=65536:raise RuntimeError('Followup would exceed context')
        start=time.monotonic();r=api('/v1/chat/completions',follow)
        (OUT/(profile+'-long-followup.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
        item['followup']={'seconds':round(time.monotonic()-start,2),'usage':r.get('usage'),'content':r['choices'][0]['message'].get('content'),'finish_reason':r['choices'][0].get('finish_reason')}
    return item

def hermes_smoke(profile,alias):
    STATE['phase']='hermes_short_tools'
    work=Path(INSTALL['workspace'])/OUT.name/profile;work.mkdir(parents=True)
    fixture={'ticket':uuid.uuid4().hex,'amounts':[137,259,83,41]};expected={'ticket':fixture['ticket'],'count':4,'total':520}
    inp=work/'input.json';inp.write_text(json.dumps(fixture),encoding='utf-8');digest=hashlib.sha256(inp.read_bytes()).hexdigest()
    query=OUT/(profile+'-hermes-query.txt');query.write_text('Use the actual read_file tool to read input.json, then the actual write_file tool to write output.json with exactly these keys: ticket copied from input.json, count as the number of amounts, total as their sum. Do not modify input.json. Then finish concisely.',encoding='utf-8')
    command=[INSTALL['hermes_launcher'],'chat','--cli','--oneshot','--query-file',str(query),'--provider','local-qwen','--model',alias,'--in',str(work),'--max-turns','8','--format','stream-json']
    start=time.monotonic()
    with (OUT/(profile+'-hermes.stdout.jsonl')).open('w',encoding='utf-8') as out,(OUT/(profile+'-hermes.stderr.log')).open('w',encoding='utf-8') as err:
        child=subprocess.Popen(command,env=ENV,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
        while child.poll() is None:
            if GUARD.is_set() or time.monotonic()-start>300:
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                raise RuntimeError('Hermes trial stopped by resource/time limit')
            time.sleep(1)
    events=[]
    for line in (OUT/(profile+'-hermes.stdout.jsonl')).read_text(encoding='utf-8').splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    final=next((e for e in reversed(events) if e.get('type')=='result'),{})
    sid=final.get('session_id');tools=[];session=None
    if sid:
        db=sqlite3.connect((Path(INSTALL['hermes_home'])/'state.db').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        row=db.execute('SELECT model,billing_base_url FROM sessions WHERE id=?',(sid,)).fetchone();session=dict(row) if row else None
        for row in db.execute("SELECT tool_name,content FROM messages WHERE session_id=? AND role='tool' ORDER BY id",(sid,)):
            tools.append(dict(row))
        db.close()
    artifact=json.loads((work/'output.json').read_text(encoding='utf-8-sig')) if (work/'output.json').exists() else None
    checks={'exit_zero':child.returncode==0,'artifact_correct':artifact==expected,'input_unchanged':hashlib.sha256(inp.read_bytes()).hexdigest()==digest,'model_correct':bool(session and session['model']==alias),'endpoint_local':bool(session and '127.0.0.1:8089' in str(session['billing_base_url'])),'required_tools_used':{'read_file','write_file'}.issubset({t['tool_name'] for t in tools})}
    return {'seconds':round(time.monotonic()-start,2),'session_id':sid,'session':session,'tool_results':tools,'checks':checks,'passed':all(checks.values()),'artifact':artifact,'workspace':str(work)}

try:
    with socket.create_connection(('127.0.0.1',8089),timeout=1):raise RuntimeError('Port in use; existing model left untouched')
except ConnectionRefusedError:pass
gateway=subprocess.run([INSTALL['hermes_launcher'],'gateway','status'],env=ENV,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
INITIAL_GATEWAY='Gateway is running' in gateway.stdout
REPORT['initial_gateway_running']=INITIAL_GATEWAY;save();thread=threading.Thread(target=monitor,daemon=True);thread.start()
print(json.dumps({'directory':str(OUT),'baseline_available_ram_gib':round(memory.snapshot(os.getpid())['available_ram_bytes']/2**30,3)}),flush=True)
try:
    for profile in ['daily','large']:
        STATE.update(profile=profile,phase='load',pid=None,owned=True)
        loaded=lifecycle('start',profile);(OUT/(profile+'-load.log')).write_text(loaded.stdout+'\n'+loaded.stderr,encoding='utf-8')
        if loaded.returncode:raise RuntimeError('Model load failed: '+profile)
        state=json.loads((ROOT/'server-state.json').read_text());STATE['pid']=state['pid']
        props=api('/props');p=json.loads((ROOT/'profiles'/(profile+'.json')).read_text(encoding='utf-8'))
        if props['model_alias']!=p['profile_id'] or props['default_generation_settings']['n_ctx']!=65536 or props['total_slots']!=1:raise RuntimeError('Unexpected model/context/slots')
        model={'alias':props['model_alias'],'context_per_slot':65536,'slots':1,'load_seconds':state['load_seconds'],'server_log':state['log'],'raw':None,'hermes':None};REPORT['models'][profile]=model;save()
        (OUT/(profile+'-props.json')).write_text(json.dumps(props,ensure_ascii=False,indent=2),encoding='utf-8')
        model['raw']=raw_probe(profile,p['profile_id']);save();print(json.dumps({'profile':profile,'raw':model['raw']}),flush=True)
        if GUARD.is_set():raise RuntimeError('Memory guard interruption, not observed OOM')
        model['hermes']=hermes_smoke(profile,p['profile_id']);save();print(json.dumps({'profile':profile,'hermes_passed':model['hermes']['passed'],'seconds':model['hermes']['seconds']}),flush=True)
        STATE['phase']='stop';stop_owned()
        if not INITIAL_GATEWAY:subprocess.run([INSTALL['hermes_launcher'],'gateway','stop'],env=ENV,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
except Exception as e:REPORT['error']=str(e)
finally:
    try:stop_owned()
    except Exception as e:REPORT['cleanup_error']=str(e)
    if not INITIAL_GATEWAY:subprocess.run([INSTALL['hermes_launcher'],'gateway','stop'],env=ENV,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
    STOP.set();thread.join(10)
    for profile,model in REPORT['models'].items():
        rows=[s for s in SAMPLES if s['profile']==profile]
        model['minimum_available_ram_gib']=round(min(s['available_ram_bytes'] for s in rows)/2**30,3) if rows else None
        model['maximum_system_gpu_mib']=max((s['gpu_used_mib'] for s in rows if s['gpu_used_mib'] is not None),default=None)
    REPORT['settings_unchanged']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()==HASHES[str(p)] for p in TRACKED}
    REPORT['finished_at']=dt.datetime.now().astimezone().isoformat();save()
    print(json.dumps({'finished':str(OUT/'results.json'),'error':REPORT.get('error')}),flush=True)
