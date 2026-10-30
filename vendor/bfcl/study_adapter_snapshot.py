"""Pinned BFCL data + unchanged official Python AST checker over local native tool calls."""
import ast
import copy
import ctypes
import datetime as dt
import hashlib
import html
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
import types
import urllib.request

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent
INSTALL=json.loads((ROOT/'installation.json').read_text(encoding='utf-8'))
ENV=dict(os.environ,HERMES_HOME=INSTALL['hermes_home'],PYTHONIOENCODING='utf-8',PYTHONUTF8='1')
sys.path.insert(0,str(HERE))
# Only model-registry metadata is supplied locally; no provider SDK imports or scoring edits.
registry=types.ModuleType('bfcl_eval.constants.model_config')
registry.MODEL_CONFIG_MAPPING={'local':types.SimpleNamespace(underscore_to_dot=True)}
sys.modules[registry.__name__]=registry
from bfcl_eval.constants.enums import Language,ModelStyle
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker
# Load the two upstream converter definitions verbatim, avoiding unrelated SDK/parser imports.
upstream=ast.parse((HERE/'handler_utils.py').read_text(encoding='utf-8'))
definitions=[n for n in upstream.body if isinstance(n,ast.FunctionDef) and n.name in {'_cast_to_openai_type','convert_to_tool'}]
assert len(definitions)==2
namespace={'copy':copy,'re':re,'json':json,'GORILLA_TO_OPENAPI':GORILLA_TO_OPENAPI,'ModelStyle':ModelStyle}
exec(compile(ast.Module(body=definitions,type_ignores=[]),'official_converter.py','exec'),namespace)
convert_to_tool=namespace['convert_to_tool']
CATEGORIES=['simple_python','multiple','parallel','irrelevance']
def read_jsonl(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
SELECTED=[]; HASHES={}
for category in CATEGORIES:
    path=HERE/'bfcl_eval/data'/('BFCL_v4_'+category+'.json')
    rows=read_jsonl(path);HASHES[str(path.relative_to(HERE))]=hashlib.sha256(path.read_bytes()).hexdigest()
    answers={}
    if category!='irrelevance':
        answer_path=HERE/'bfcl_eval/data/possible_answer'/path.name
        answer_rows=read_jsonl(answer_path);assert len(answer_rows)==len(rows)
        # Official eval runner aligns prompt and ground truth by row index.
        answers={row['id']:a['ground_truth'] for row,a in zip(rows,answer_rows)}
        HASHES[str(answer_path.relative_to(HERE))]=hashlib.sha256(answer_path.read_bytes()).hexdigest()
    for index in sorted(random.Random(42).sample(range(len(rows)),20)):
        SELECTED.append({'category':category,'index':index,'problem':rows[index],'ground_truth':answers.get(rows[index]['id'])})

def check(item,decoded):
    if item['category']=='irrelevance':return {'valid':not decoded,'error':[] if not decoded else ['A tool call was emitted when none applies.']}
    return ast_checker(copy.deepcopy(item['problem']['function']),decoded,copy.deepcopy(item['ground_truth']),Language.PYTHON,item['category'],'local')
def golden(item):
    def nested(value):
        if isinstance(value,dict):return {k:nested(v[0] if isinstance(v,list) else v) for k,v in value.items()}
        if isinstance(value,list):return [nested(v) for v in value]
        return value
    decoded=[]
    for call in item['ground_truth'] or []:
        name,options=next(iter(call.items()));description=next(f for f in item['problem']['function'] if f['name']==name)
        params={k:nested(values[0]) for k,values in options.items() if k in description['parameters']['required'] or '' not in values}
        decoded.append({name.replace('.','_'):params})
    return decoded
selfcheck=[]
for item in SELECTED:
    good=check(item,golden(item))
    bad=check(item,[{'not_a_valid_function':{}}] if item['category']=='irrelevance' else [])
    tools=convert_to_tool(item['problem']['function'],GORILLA_TO_OPENAPI,ModelStyle.OPENAI_COMPLETIONS)
    names=[t['function']['name'] for t in tools]
    selfcheck.append({'id':item['problem']['id'],'golden_passed':good['valid'],'negative_rejected':not bad['valid'],'unique_tool_names':len(names)==len(set(names))})
(HERE/'selfcheck.json').write_text(json.dumps(selfcheck,indent=2),encoding='utf-8')
if not all(all(x[k] for k in ['golden_passed','negative_rejected','unique_tool_names']) for x in selfcheck):
    raise RuntimeError('Checker/conversion selfcheck failed: '+str([x for x in selfcheck if not all(x[k] for k in ['golden_passed','negative_rejected','unique_tool_names'])]))
print(json.dumps({'selfcheck':'passed','cases':len(selfcheck)}),flush=True)
if '--selfcheck' in sys.argv:sys.exit(0)

OUT=HERE/('comparison-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S'));OUT.mkdir()
class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_uint64) for n in ['total','available','pageTotal','pageAvailable','virtTotal','virtAvailable','extended']]
STATE={'profile':None,'phase':'setup','active':False};SAMPLES=[];STOP=threading.Event();GUARD=threading.Event()
def available():
    m=Memory();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise ctypes.WinError()
    return m.available/2**30
def lifecycle(action,profile):
    return subprocess.run([sys.executable,str(ROOT/'server.py'),action,profile],env=ENV,capture_output=True,text=True,encoding='utf-8',timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
def monitor():
    tick=0;low=0
    while not STOP.is_set():
        row={'at':dt.datetime.now().astimezone().isoformat(),**STATE,'available_ram_gib':round(available(),3)}
        if tick%5==0:
            try:
                gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
                if gpu.returncode==0:row['gpu_used_mib']=int(gpu.stdout.strip())
            except Exception:pass
        SAMPLES.append(row)
        with (OUT/'memory.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        low=low+1 if STATE['active'] and row['available_ram_gib']<1 else 0
        if low>=3:
            GUARD.set();lifecycle('stop',STATE['profile']);return
        tick+=1;STOP.wait(2)
def api(path,payload=None):
    request=urllib.request.Request('http://127.0.0.1:8089'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=180) as r:return json.load(r)
def save(): (OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
try:
    api('/props');raise RuntimeError('A model is already running; refusing to replace it')
except OSError:pass
tracked=[ROOT/'profiles/daily.json',ROOT/'profiles/large.json',Path(INSTALL['hermes_home'])/'config.yaml']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
report={'started_at':dt.datetime.now().astimezone().isoformat(),'directory':str(OUT),'repository':'https://github.com/ShishirPatil/gorilla','commit':(HERE/'revision.txt').read_text().strip(),'data_hashes':HASHES,'categories':CATEGORIES,'cases_per_category':20,'selection_seed':42,'selected_ids':[i['problem']['id'] for i in SELECTED],'models':{},'protocol':{'temperature':0,'seed':42,'thinking':False,'max_tokens':1024,'tool_choice':'auto','parallel_tool_calls':True,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'context':65536,'system_prompt':None,'messages':'Unmodified official question[0]','grading':'Pinned unchanged official Python AST checker; native tool_calls JSON decoding; official convert_to_tool definitions. Minimal local model registry entry sets underscore_to_dot=True, as OpenAI native FC schemas normalize dots. Irrelevance requires zero emitted tool calls; malformed calls fail rather than count as abstention.'},'limitations':['80-case stratified subset, one greedy answer per case, not full official BFCL leaderboard results','Model responses generated through a custom local API adapter, not the full bfcl CLI','No functions actually executed: evaluates tool names, arguments, parallel-call selection and abstention, not Hermes end-to-end workflows or multi-turn agency','Different Qwen generations, quantizations and CPU/GPU placements; not an isolated parameter-count comparison','Fixed 4B then 35B order; sampled system RAM/GPU use, thermal/app background variation uncontrolled']}
thread=threading.Thread(target=monitor,daemon=True);thread.start()
try:
    for profile in ['daily','large']:
        STATE.update(profile=profile,phase='load',active=True)
        print(json.dumps({'profile':profile,'phase':'load','directory':str(OUT)}),flush=True)
        started=lifecycle('start',profile)
        (OUT/(profile+'-load.log')).write_text(started.stdout+'\n'+started.stderr,encoding='utf-8')
        if started.returncode:raise RuntimeError('Failed model load: '+profile)
        props=api('/props');p=json.loads((ROOT/'profiles'/(profile+'.json')).read_text(encoding='utf-8'))
        if props['model_alias']!=p['profile_id'] or props['default_generation_settings']['n_ctx']!=65536:raise RuntimeError('Unexpected served model/context')
        model={'alias':props['model_alias'],'model_file':props['model_path'],'model_hash':p['model_hash'],'runtime':props['build_info'],'cases':[]};report['models'][profile]=model;save()
        api('/v1/chat/completions',{'model':p['profile_id'],'messages':[{'role':'user','content':'Reply OK.'}],'max_tokens':8,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}})
        for item in SELECTED:
            problem=item['problem'];STATE['phase']=problem['id']
            tools=convert_to_tool(problem['function'],GORILLA_TO_OPENAPI,ModelStyle.OPENAI_COMPLETIONS)
            payload={'model':p['profile_id'],'messages':problem['question'][0],'tools':tools,'tool_choice':'auto','parallel_tool_calls':True,'temperature':0,'seed':42,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'max_tokens':1024,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':False}}
            t=time.monotonic();response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-t
            message=response['choices'][0]['message'];calls=message.get('tool_calls') or [];decoded=[];decode_error=None
            try:
                for call in calls:
                    params=json.loads(call['function']['arguments'])
                    if not isinstance(params,dict):raise ValueError('Tool arguments are not an object')
                    decoded.append({call['function']['name']:params})
                grade=check(item,decoded)
            except (ValueError,KeyError,TypeError) as exc:
                decode_error=str(exc);grade={'valid':False,'error':['Malformed tool output: '+str(exc)]}
            result={'id':problem['id'],'category':item['category'],'passed':grade['valid'],'seconds':round(elapsed,3),'grade':grade,'decoded':decoded,'decode_error':decode_error,'message':message,'finish_reason':response['choices'][0].get('finish_reason'),'usage':response.get('usage'),'timings':response.get('timings')}
            model['cases'].append(result);save()
            print(json.dumps({'profile':profile,'id':problem['id'],'passed':grade['valid'],'seconds':round(elapsed,2),'available_ram_gib':round(available(),2)}),flush=True)
            if GUARD.is_set():raise RuntimeError('Memory guard stopped this trial; not an OOM')
        STATE['phase']='stop';stopped=lifecycle('stop',profile)
        if stopped.returncode:raise RuntimeError('Model stop failed: '+profile)
        STATE['active']=False;time.sleep(3)
except Exception as exc:report['error']=str(exc)
finally:
    if STATE['active'] and STATE['profile']:
        try:lifecycle('stop',STATE['profile'])
        except Exception as exc:report['cleanup_error']=str(exc)
    STATE['active']=False;STOP.set();thread.join(timeout=10)
    for profile,model in report['models'].items():
        rows=[s for s in SAMPLES if s['profile']==profile];cases=model['cases']
        model['categories']={category:{'passed':sum(c['passed'] for c in cases if c['category']==category),'attempted':sum(c['category']==category for c in cases)} for category in CATEGORIES}
        times=[c['timings'] for c in cases if c.get('timings')];n=sum(t.get('predicted_n',0) for t in times);ms=sum(t.get('predicted_ms',0) for t in times)
        model['summary']={'passed':sum(c['passed'] for c in cases),'attempted':len(cases),'median_seconds':round(statistics.median(c['seconds'] for c in cases),2) if cases else None,'total_seconds':round(sum(c['seconds'] for c in cases),2),'generation_tokens_per_second':round(n/ms*1000,2) if ms else None,'minimum_available_ram_gib':min((s['available_ram_gib'] for s in rows),default=None),'maximum_system_gpu_mib':max((s['gpu_used_mib'] for s in rows if 'gpu_used_mib'in s),default=None),'truncated_answers':sum(c.get('finish_reason')=='length' for c in cases),'malformed_outputs':sum(c.get('decode_error') is not None for c in cases)}
    report['settings_unchanged']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)] for p in tracked}
    report['finished_at']=dt.datetime.now().astimezone().isoformat()
    files=[Path(__file__),HERE/'handler_utils.py',HERE/'bfcl_eval/eval_checker/ast_eval/ast_checker.py',HERE/'bfcl_eval/constants/enums.py',HERE/'bfcl_eval/constants/type_mappings.py']
    report['code_hashes']={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'run_comparison.py').write_bytes(Path(__file__).read_bytes());save()
    print(json.dumps({'report':str(OUT/'results.json'),'models':{k:{'summary':m['summary'],'categories':m['categories']} for k,m in report['models'].items()},'error':report.get('error')}),flush=True)
