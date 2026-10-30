"""Run the original 20-task HumanEval protocol against an existing endpoint."""
import argparse,ast,ctypes,gzip,hashlib,json,pathlib,random,re,statistics,subprocess,sys,time,urllib.request
from ctypes import wintypes as w
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,resolve_run,snapshot_sources

def grader():
    bench=ROOT/'artifacts/local-llm/hermes/benchmarks'
    source=(bench/'compare_models.py').read_text(encoding='utf-8')
    scope={'ctypes':ctypes,'w':w,'subprocess':subprocess,'sys':sys,'json':json,'BENCH':bench,'re':re}
    exec(compile(source[source.index('class BasicLimits'):source.index('\ndef canonical_selfcheck')],'pinned_windows_grader.py','exec'),scope)
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='unwrap_code')
    exec(compile(ast.Module(body=[node],type_ignores=[]),'pinned_code_extractor.py','exec'),scope)
    return scope['grade'],scope['unwrap_code']

def run(a):
    path=resolve_run(a.run);manifest=load(path/'manifest.json')
    if manifest['status']=='complete':raise ValueError('Completed run is immutable')
    params={'endpoint':a.endpoint.rstrip('/'),'model':a.model,'thinking':a.thinking,'context':65536,'max_output':64000,'temperature':0.6,'seed':42}
    if manifest.get('execution') and manifest['execution']!=params:raise ValueError('Resume conditions changed')
    if not manifest.get('execution'):snapshot_sources(path)
    def api(route,payload=None):
        req=urllib.request.Request(params['endpoint']+route,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=7200) as f:return json.load(f)
    props=api('/props');assert props['model_alias']==a.model and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
    grade,unwrap=grader();dataset=ROOT/'datasets/humaneval/b9453e8'
    for rel,expected in load(dataset/'manifest.json')['files'].items():assert hashlib.sha256((dataset/rel).read_bytes()).hexdigest()==expected,rel
    data=gzip.decompress((dataset/'HumanEval.jsonl.gz').read_bytes());rows=[json.loads(s) for s in data.decode().splitlines()]
    problems=[rows[i] for i in sorted(random.Random(42).sample(range(len(rows)),20))]
    controls=[{'task_id':p['task_id'],**grade(p['prompt']+p['canonical_solution'],p)} for p in problems];assert all(x['passed'] for x in controls);save(path/'configs/canonical-controls.json',controls)
    manifest.update(status='running',execution=params,started_at=manifest.get('started_at') or now(),runtime_build=props['build_info']);save(path/'manifest.json',manifest);entries=[]
    try:
        for p in problems:
            cid=p['task_id'].replace('/','_');rawfile=path/'raw'/(cid+'.json')
            payload={'model':a.model,'messages':[{'role':'system','content':'Implement the requested Python function. Return only a complete Python module with the specified signature and required imports. Do not include explanations, markdown, or tests.'},{'role':'user','content':p['prompt']}],'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'presence_penalty':0,'repeat_penalty':1,'seed':42,'max_tokens':64000,'chat_template_kwargs':{'enable_thinking':a.thinking=='on'},'cache_prompt':False}
            if rawfile.exists():
                raw=load(rawfile);assert raw['request']==dict(payload,max_tokens=raw['request']['max_tokens'])
            else:
                templ=api('/apply-template',{k:v for k,v in payload.items() if k in ['messages','chat_template_kwargs']})
                n=len(api('/tokenize',{'content':templ['prompt'],'add_special':False})['tokens']);payload['max_tokens']=min(64000,65536-n-32)
                start=time.monotonic();response=api('/v1/chat/completions',payload);raw={'request':payload,'response':response,'seconds':time.monotonic()-start,'estimated_prompt_tokens':n};save(rawfile,raw)
            response=raw['response'];msg=response['choices'][0]['message'];content=msg.get('content') or ''
            code=unwrap(content,p['prompt'],p['entry_point']) if content.strip() else ''
            outcome=grade(code,p) if code else {'passed':False,'status':'no_final_code'}
            entry={'task_id':p['task_id'],**outcome,'code':code,'seconds':raw['seconds'],'finish_reason':response['choices'][0]['finish_reason'],'reasoning_observed':bool(msg.get('reasoning_content') or msg.get('reasoning')),'usage':response['usage']};entries.append(entry);save(path/'summaries/cases.json',entries)
            print(json.dumps({'suite':'humaneval','mode':a.thinking,'done':len(entries),'task':p['task_id'],'passed':entry['passed']}),flush=True)
        summary={'benchmark':'humaneval','thinking':a.thinking,'passed':sum(e['passed'] for e in entries),'attempted':len(entries),'expected':20,'median_seconds':statistics.median(e['seconds'] for e in entries),'total_seconds':sum(e['seconds'] for e in entries),'output_cap_hits':sum(e['finish_reason']=='length' for e in entries),'reasoning_observed_cases':sum(e['reasoning_observed'] for e in entries),'grading_python':sys.version,'grader_policy':'Original restricted Windows worker; no reasoning salvage or normalizer changes'}
        save(path/'summary.json',summary);manifest.update(status='complete',completed_at=now());save(path/'manifest.json',manifest);return summary
    except Exception as e:manifest.update(status='failed',error=repr(e));save(path/'manifest.json',manifest);raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--model',required=True);p.add_argument('--thinking',choices=['off','on'],required=True);p.add_argument('--endpoint',default='http://127.0.0.1:8089');run(p.parse_args())
