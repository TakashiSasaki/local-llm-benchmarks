"""Collect the fixed BFCL 80 cases from an already running llama.cpp endpoint."""
import argparse,hashlib,json,pathlib,re,statistics,sys,time,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,resolve_run,snapshot_sources
from local_llm_benchmarks.bfcl import components
def public_props(value):
    if isinstance(value,dict):return {k:('[Model template omitted; SHA256 '+hashlib.sha256(v.encode()).hexdigest()+']' if k=='chat_template' and isinstance(v,str) else public_props(v)) for k,v in value.items()}
    if isinstance(value,list):return [public_props(v) for v in value]
    if isinstance(value,str):return re.sub(r'(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/"\r\n]+',lambda m:m[1]+'benchmark',value)
    return value
def run(args):
    path=resolve_run(args.run);manifest=load(path/'manifest.json')
    if manifest['status']=='complete':raise ValueError('Completed runs are immutable; create a new run ID')
    params={'endpoint':args.endpoint.rstrip('/'),'model':args.model,'thinking':args.thinking,'mode_control':args.mode_control,'context':args.context,'max_output':args.max_output,'dataset':'bfcl/6ea5797/selected-80.json','temperature':0,'seed':42}
    if manifest.get('execution') and manifest['execution']!=params:raise ValueError('Resume parameters differ from the recorded run')
    def api(route,payload=None,timeout=7200):
        req=urllib.request.Request(params['endpoint']+route,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=timeout) as f:return json.load(f)
    cases,convert,grade=components();props=api('/props',timeout=30)
    if props['default_generation_settings']['n_ctx']!=args.context or props['total_slots']!=1:raise ValueError('Expected configured context per slot and one slot')
    if props['model_alias']!=args.model:raise ValueError('Endpoint model alias differs')
    if manifest.get('runtime_build') and manifest['runtime_build']!=props.get('build_info'):raise ValueError('Runtime changed; create a new run ID')
    if manifest.get('execution'):
        for rel,value in load(path/'source-manifest.json')['files'].items():
            if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=value:raise ValueError('Source changed since this run; create a new run ID or restore its source snapshot')
    if not manifest.get('execution'):snapshot_sources(path)
    manifest.update(status='running',execution=params,started_at=manifest.get('started_at') or now(),runtime_build=props.get('build_info'));manifest.pop('error',None);save(path/'manifest.json',manifest);save(path/'configs/server-props.json',public_props(props))
    entries=[]
    try:
        warm={'model':args.model,'messages':[{'role':'user','content':'What is 17 times 23? Think carefully and then answer with the number.'}],'max_tokens':512,'temperature':0,'seed':42,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':args.thinking=='on'}}
        warm_response=api('/v1/chat/completions',warm);save(path/'configs/mode-warmup.json',{'request':warm,'response':warm_response})
        msg=warm_response['choices'][0]['message'];observed=bool(msg.get('reasoning_content') or msg.get('reasoning'))
        if observed!=(args.thinking=='on'):raise ValueError('Requested explicit thinking mode was not observed; check template/CLI settings')
        for c in cases:
            cid=c['problem']['id'];rawfile=path/'raw'/(cid+'.json')
            payload={'model':args.model,'messages':c['problem']['question'][0],'tools':convert(c),'tool_choice':'auto','parallel_tool_calls':True,'temperature':0,'seed':42,'top_p':1,'top_k':0,'min_p':0,'repeat_penalty':1,'max_tokens':args.max_output,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':args.thinking=='on'}}
            if rawfile.exists():
                raw=load(rawfile);expected=dict(payload,max_tokens=raw['request']['max_tokens']);assert raw['request']==expected
                assert expected['max_tokens']==min(args.max_output,args.context-raw['estimated_prompt_tokens']-32)
            else:
                templ=api('/apply-template',{k:v for k,v in payload.items() if k in ['messages','tools','tool_choice','parallel_tool_calls','chat_template_kwargs']},30)
                n=len(api('/tokenize',{'content':templ['prompt'],'add_special':False},30)['tokens']);payload['max_tokens']=min(args.max_output,args.context-n-32)
                if payload['max_tokens']<=0:raise ValueError('No output space remaining')
                start=time.monotonic();response=api('/v1/chat/completions',payload);elapsed=time.monotonic()-start
                raw={'id':cid,'request':payload,'response':response,'seconds':elapsed,'estimated_prompt_tokens':n};save(rawfile,raw)
            response=raw['response'];message=response['choices'][0]['message'];outcome=grade(c,response)
            entry={'id':cid,'category':c['category'],'seconds':raw['seconds'],**outcome,'finish_reason':response['choices'][0]['finish_reason'],'reasoning_observed':bool(message.get('reasoning_content') or message.get('reasoning')),'usage':response.get('usage')};entries.append(entry)
            save(path/'summaries/bfcl-cases.json',entries);print(json.dumps({'done':len(entries),'id':cid,'passed':entry['passed']}),flush=True)
        summary={'benchmark':'bfcl','thinking':args.thinking,'passed':sum(x['passed'] for x in entries),'attempted':len(entries),'expected':80,'median_seconds':statistics.median(x['seconds'] for x in entries),'total_seconds':sum(x['seconds'] for x in entries),'output_cap_hits':sum(x['finish_reason']=='length' for x in entries),'reasoning_observed_cases':sum(x['reasoning_observed'] for x in entries),'categories':{cat:{'passed':sum(x['passed'] for x in entries if x['category']==cat),'attempted':20} for cat in ['simple_python','multiple','parallel','irrelevance']},'tool_functions_executed':False}
        save(path/'summary.json',summary);manifest.update(status='complete',completed_at=now());save(path/'manifest.json',manifest);return summary
    except Exception as exc:
        manifest.update(status='failed',error=repr(exc),failed_at=now());save(path/'manifest.json',manifest);raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--endpoint',default='http://127.0.0.1:8089');p.add_argument('--model',required=True);p.add_argument('--thinking',choices=['off','on'],required=True);p.add_argument('--mode-control',choices=['native','runtime-forced'],default='native');p.add_argument('--context',type=int,default=65536);p.add_argument('--max-output',type=int,default=64000);a=p.parse_args();run(a)
