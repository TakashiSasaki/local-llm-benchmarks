"""Matched-budget HumanEval thinking ON/OFF trial; preserves all earlier runs."""
import ast
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
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

BENCH=Path(__file__).resolve().parent;ROOT=BENCH.parent
INSTALL=json.loads((ROOT/'installation.json').read_text(encoding='utf-8'))
ENV=dict(os.environ,HERMES_HOME=INSTALL['hermes_home'],PYTHONIOENCODING='utf-8',PYTHONUTF8='1',LLAMA_ARG_THINK='deepseek')
# Reuse the existing Windows job-limited grader definitions, without its benchmark main program.
source=(BENCH/'compare_models.py').read_text(encoding='utf-8')
guard_source=source[source.index('class BasicLimits'):source.index('\ndef canonical_selfcheck')]
exec(compile(guard_source,'existing_job_grader.py','exec'),globals())
tree=ast.parse(source)
unwrap_node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='unwrap_code')
exec(compile(ast.Module(body=[unwrap_node],type_ignores=[]),'existing_extractor.py','exec'),globals())
reference_path=BENCH/'comparison-20261029-141429'/'results.json'
reference=json.loads(reference_path.read_text(encoding='utf-8'))
dataset=(BENCH/'HumanEval.jsonl.gz').read_bytes()
assert hashlib.sha256(dataset).hexdigest()==reference['dataset_sha256']
DATA=[json.loads(line) for line in gzip.decompress(dataset).decode().splitlines()]
SELECTED=[DATA[i] for i in sorted(random.Random(42).sample(range(len(DATA)),20))]
assert [p['task_id'] for p in SELECTED]==reference['task_ids']
canonical=[{'task_id':p['task_id'],**grade(p['prompt']+p['canonical_solution'],p)} for p in SELECTED]
if not all(r['passed'] for r in canonical):raise RuntimeError('Canonical grading failed: '+str(canonical))
STAMP=dt.datetime.now().strftime('%Y%m%d-%H%M%S');OUT=BENCH/('thinking-comparison-'+STAMP);OUT.mkdir()
(OUT/'canonical-selfcheck.json').write_text(json.dumps(canonical,indent=2),encoding='utf-8')
(OUT/'thinking_comparison.py').write_bytes(Path(__file__).read_bytes())

class Memory(ctypes.Structure):
    _fields_=[('length',w.DWORD),('load',w.DWORD)]+[(n,ctypes.c_uint64) for n in ['total','available','pageTotal','pageAvailable','virtTotal','virtAvailable','extended']]
def available():
    m=Memory();m.length=ctypes.sizeof(m)
    if not K.GlobalMemoryStatusEx(ctypes.byref(m)):raise ctypes.WinError(ctypes.get_last_error())
    return m.available/2**30
STATE={'profile':None,'mode':None,'phase':'setup','owned':False};STOP=threading.Event();GUARD=threading.Event();SAMPLES=[]
def lifecycle(action,profile):
    return subprocess.run([sys.executable,str(ROOT/'server.py'),action,profile],env=ENV,capture_output=True,text=True,encoding='utf-8',timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
def monitor():
    low=0;tick=0
    while not STOP.is_set():
        row={'at':dt.datetime.now().astimezone().isoformat(),**STATE,'available_ram_gib':round(available(),3)}
        if tick%5==0:
            try:
                r=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
                if r.returncode==0:row['gpu_used_mib']=int(r.stdout.strip())
            except Exception:pass
        SAMPLES.append(row)
        with (OUT/'memory.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        low=low+1 if STATE['owned'] and row['available_ram_gib']<1 else 0
        if low>=3:
            GUARD.set();lifecycle('stop',STATE['profile']);return
        tick+=1;STOP.wait(2)
def api(path,payload=None,timeout=240):
    req=urllib.request.Request('http://127.0.0.1:8089'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def inspect_response(response):
    msg=response['choices'][0]['message'];content=msg.get('content') or '';reason=msg.get('reasoning_content') or msg.get('reasoning') or ''
    return {'content':content,'reasoning_observed':bool(reason),'reasoning_characters':len(reason),
            'reasoning_tokens_reported':response.get('usage',{}).get('completion_tokens_details',{}).get('reasoning_tokens'),
            'finish_reason':response['choices'][0].get('finish_reason'),'usage':response.get('usage'),'timings':response.get('timings')}
def save():
    (OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
try:
    live=api('/props',timeout=4)
except OSError:live=None
if live:
    (OUT/'blocked.json').write_text(json.dumps({'reason':'Existing model is in use; it was not stopped','model':live.get('model_alias')}),encoding='utf-8')
    print(json.dumps({'blocked':'Existing model is in use','directory':str(OUT)}));sys.exit(2)
tracked=[ROOT/'profiles/daily.json',ROOT/'profiles/large.json',Path(INSTALL['hermes_home'])/'config.yaml']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
report={'started_at':dt.datetime.now().astimezone().isoformat(),'directory':str(OUT),'dataset_commit':reference['dataset_commit'],'dataset_sha256':reference['dataset_sha256'],'task_ids':reference['task_ids'],'previous_1024_reference':str(reference_path),
        'protocol':{'temperature':0,'seed':42,'max_tokens':4096,'thinking_modes':['off','on'],'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'cache_prompt':False,'reasoning_format':'deepseek via LLAMA_ARG_THINK inherited by model process','request_timeout_seconds':240,'context':65536,'mode_order':'Alternates OFF/ON and ON/OFF by task index, identical for both models'},
        'models':{},'limitations':['20 selected tasks, one sample per model/mode; not full official HumanEval scores','Custom instruction-format prompting and guarded official-test execution, matching earlier benchmark','Previous OFF results used 1024 tokens; main comparison here uses matched 4096 for both modes','Thinking traces consume the same total output budget as final code','System RAM/GPU periodically sampled; not exact peaks or model-only usage','Different Qwen generations, quantizations and placement; fixed 4B then 35B model order','Only reported reasoning token counts are used; no estimates from characters'],
        'grader_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'worker_sha256':hashlib.sha256((BENCH/'grade_worker.py').read_bytes()).hexdigest()}
save();thread=threading.Thread(target=monitor,daemon=True);thread.start()
print(json.dumps({'directory':str(OUT),'canonical_passed':20,'baseline_ram_gib':round(available(),3)}),flush=True)
try:
    for profile in ['daily','large']:
        STATE.update(profile=profile,mode=None,phase='load',owned=True)
        result=lifecycle('start',profile)
        (OUT/(profile+'-load.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        if result.returncode:raise RuntimeError('Model load failed: '+profile)
        props=api('/props');p=json.loads((ROOT/'profiles'/(profile+'.json')).read_text(encoding='utf-8'))
        if props.get('model_alias')!=p['profile_id'] or props['default_generation_settings']['n_ctx']!=65536:raise RuntimeError('Unexpected served identity/context')
        model={'alias':props['model_alias'],'path':props['model_path'],'runtime':props['build_info'],'served_parameters':props['default_generation_settings'],'warmup':{},'modes':{'off':[],'on':[]}}
        report['models'][profile]=model;save()
        for mode in ['off','on']:
            STATE.update(mode=mode,phase='mode_verification')
            response=api('/v1/chat/completions',{'model':p['profile_id'],'messages':[{'role':'user','content':'What is 17 times 23? Think carefully and then answer with the number.'}],'max_tokens':256,'temperature':0,'seed':42,'chat_template_kwargs':{'enable_thinking':mode=='on'},'cache_prompt':False})
            (OUT/(profile+'-warmup-'+mode+'.json')).write_text(json.dumps(response,ensure_ascii=False,indent=2),encoding='utf-8')
            model['warmup'][mode]=inspect_response(response);save()
        if not model['warmup']['on']['reasoning_observed'] or model['warmup']['off']['reasoning_observed']:
            raise RuntimeError('Reasoning mode separation not verified: '+profile)
        print(json.dumps({'profile':profile,'mode_separation':'verified'}),flush=True)
        for index,problem in enumerate(SELECTED):
            for mode in (['off','on'] if index%2==0 else ['on','off']):
                STATE.update(mode=mode,phase=problem['task_id'])
                payload={'model':p['profile_id'],'messages':[{'role':'system','content':'Implement the requested Python function. Return only a complete Python module with the specified signature and required imports. Do not include explanations, markdown, or tests.'},{'role':'user','content':problem['prompt']}],
                         'temperature':0,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'seed':42,'max_tokens':4096,'chat_template_kwargs':{'enable_thinking':mode=='on'},'cache_prompt':False}
                t=time.monotonic()
                try:
                    response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-t
                    raw=OUT/(profile+'-'+mode+'-'+problem['task_id'].replace('/','_')+'.response.json')
                    raw.write_text(json.dumps(response,ensure_ascii=False,indent=2),encoding='utf-8')
                    data=inspect_response(response)
                    if data['content'].strip():
                        code=unwrap_code(data['content'],problem['prompt'],problem['entry_point'])
                        try:ast.parse(code);syntax=True
                        except SyntaxError:syntax=False
                        grade_result=grade(code,problem)
                        failure=None if grade_result['passed'] else ('syntax_error' if not syntax else grade_result['status'])
                    else:
                        code='';grade_result={'passed':False,'status':'no_final_code'}
                        failure='budget_exhausted_before_final_code' if data['finish_reason']=='length' else 'no_final_code'
                    entry={'task_id':problem['task_id'],'mode':mode,'seconds':round(elapsed,3),**data,'code':code,'passed':grade_result['passed'],'grade':grade_result,'failure_kind':failure,'raw_response':raw.name}
                except (urllib.error.URLError,TimeoutError,OSError) as exc:
                    entry={'task_id':problem['task_id'],'mode':mode,'seconds':round(time.monotonic()-t,3),'passed':False,'failure_kind':'inference_error','error':str(exc)}
                model['modes'][mode].append(entry);save()
                print(json.dumps({'profile':profile,'mode':mode,'task':problem['task_id'],'passed':entry['passed'],'seconds':entry['seconds'],'reasoning_observed':entry.get('reasoning_observed'),'reasoning_characters':entry.get('reasoning_characters'),'reasoning_tokens_reported':entry.get('reasoning_tokens_reported'),'finish_reason':entry.get('finish_reason'),'available_ram_gib':round(available(),3)}),flush=True)
                if GUARD.is_set():raise RuntimeError('Memory guard stopped the trial; not an observed OOM')
        STATE['phase']='stop';stopped=lifecycle('stop',profile)
        if stopped.returncode:raise RuntimeError('Model cleanup failed: '+profile)
        STATE['owned']=False;save();time.sleep(3)
except Exception as exc:report['error']=str(exc)
finally:
    if STATE['owned']:
        try:
            cleanup=lifecycle('stop',STATE['profile']);report['cleanup_exit_code']=cleanup.returncode
        except Exception as exc:report['cleanup_error']=str(exc)
    STATE['owned']=False;STOP.set();thread.join(timeout=10)
    for profile,model in report['models'].items():
        rows=[s for s in SAMPLES if s['profile']==profile]
        model['minimum_available_ram_gib']=min((s['available_ram_gib'] for s in rows),default=None)
        model['maximum_system_gpu_mib']=max((s['gpu_used_mib'] for s in rows if 'gpu_used_mib' in s),default=None)
        model['summary']={}
        for mode,entries in model['modes'].items():
            reported=[e['reasoning_tokens_reported'] for e in entries if e.get('reasoning_tokens_reported') is not None]
            model['summary'][mode]={'passed':sum(e['passed'] for e in entries),'attempted':len(entries),'median_seconds':round(statistics.median(e['seconds'] for e in entries),2) if entries else None,'total_seconds':round(sum(e['seconds'] for e in entries),2),'output_cap_hits':sum(e.get('finish_reason')=='length' for e in entries),'reasoning_observed_cases':sum(bool(e.get('reasoning_observed')) for e in entries),'reasoning_tokens_reported_total':sum(reported) if reported else None,'reasoning_token_count_available_cases':len(reported),'no_final_code':sum(e.get('failure_kind')=='budget_exhausted_before_final_code' for e in entries),'failure_kinds':{k:sum(e.get('failure_kind')==k for e in entries) for k in {e['failure_kind'] for e in entries if e.get('failure_kind')}}}
    report['settings_unchanged']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p)] for p in tracked}
    report['finished_at']=dt.datetime.now().astimezone().isoformat();save()
    print(json.dumps({'report':str(OUT/'results.json'),'models':{k:v['summary'] for k,v in report['models'].items()},'error':report.get('error')}),flush=True)
