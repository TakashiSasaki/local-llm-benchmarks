"""Import only this study's historical Hermes evidence; never run Hermes or change its settings."""
import argparse,hashlib,json,os,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,sha,now

def scrub(text):
    text=re.sub(r'(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/"\r\n]+',lambda m:m[1]+'benchmark',text)
    text=re.sub(r'OneDrive - [^\\/"\r\n]+','OneDrive - ORGANIZATION',text)
    host=os.environ.get('COMPUTERNAME','')
    return text.replace(host,'BENCHMARK-PC') if len(host)>7 else text

def public_object(value):
    if isinstance(value,dict):
        return {scrub(k):('[Model-provided template omitted; SHA256 '+hashlib.sha256(v.encode()).hexdigest()+']' if k in {'chat_template','chat_template_tool_use','chat_template_default'} and isinstance(v,str) else public_object(v)) for k,v in value.items()}
    if isinstance(value,list):return [public_object(v) for v in value]
    return scrub(value) if isinstance(value,str) else value

def import_files(source):
    selected=[];h=source/'hermes'
    selected.extend(p for p in h.glob('*.py') if p.name!='server.py')
    selected.append(h/'README.md')
    selected.extend(p for p in (h/'runs').rglob('*') if p.is_file() and p.suffix in {'.py','.json','.jsonl','.log','.txt','.html'} and '__pycache__' not in p.parts)
    selected.extend(p for p in (h/'logs').glob('*') if p.suffix=='.log')
    selected.extend(p for p in (source/'workspace/hermes').rglob('*') if p.is_file() and p.suffix in {'.json','.csv','.py'} and '__pycache__' not in p.parts)
    reference=pathlib.Path(os.environ['USERPROFILE'])/'.codex/skills/local-llm-agent-harness/references/hermes-windows.md'
    records=[]
    pairs=[(p,ROOT/'artifacts/local-llm'/p.relative_to(source)) for p in selected]
    pairs.append((reference,ROOT/'docs/notes/hermes-windows.md'))
    for original,target in sorted(pairs):
        raw=original.read_bytes();text=raw.decode('utf-8-sig')
        if original.suffix=='.json':out=json.dumps(public_object(json.loads(text)),ensure_ascii=False,indent=2)+'\n'
        elif original.suffix=='.jsonl':out=''.join(json.dumps(public_object(json.loads(line)),ensure_ascii=False)+'\n' for line in text.splitlines() if line.strip())
        else:out=scrub(text)
        encoded=out.encode('utf-8')
        if target.exists() and target.read_bytes()!=encoded:raise ValueError('Refusing to replace existing evidence: '+str(target.relative_to(ROOT)))
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(encoded)
        records.append({'path':target.relative_to(ROOT).as_posix(),'kind':'file','original_sha256':hashlib.sha256(raw).hexdigest(),'exported_sha256':hashlib.sha256(encoded).hexdigest(),'changed':raw!=encoded,'bytes':len(encoded)})
    # First export is immutable; its timestamp is retained on a byte-identical retry.
    manifest=ROOT/'publication/hermes-export-manifest.json'
    value={'schema_version':1,'exported_at':now(),'scope':'Hermes study scripts, selected run/log files and synthetic workspaces; no state.db, auth, config.yaml or Codex config backups','entries':records}
    if manifest.exists():
        assert load(manifest)['entries']==records,'Historical sources changed; add a separate export instead'
    else:save(manifest,value)
    return len(records)

def evidence(paths):
    found=set()
    for rel in paths:
        p=ROOT/rel
        found.update([p] if p.is_file() else (x for x in p.rglob('*') if x.is_file()))
    return [{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in sorted(found)]

def register(run_id,title,suite,typ,created,summary,paths,models):
    folder=ROOT/'runs'/run_id
    if folder.exists():return
    folder.mkdir(parents=True)
    save(folder/'manifest.json',{'schema_version':1,'run_id':run_id,'title':title,'benchmark':suite,'experiment_type':typ,'harness':'hermes','kind':'imported','status':'complete','created_at':created,'imported_at':now(),'models':models,'evidence':evidence(paths),'notes':'Historical saved results, not a fresh inference run. Complete means collection is complete; check summary outcome for failures and partial success.'})
    save(folder/'summary.json',summary)

def register_runs():
    a='artifacts/local-llm/hermes';w='artifacts/local-llm/workspace/hermes'
    native=load(ROOT/a/'runs/verification.json')
    register('20261028-hermes-native-smoke','Hermes native Windows read / terminal / write / resume','hermes-native-smoke','harness-integration',native['verified_utc'],{'outcome':'passed','headline':'Basic two-turn tool flow verified; initial terminal approval rejection retained','artifact_matches':native['artifact_actual']==native['artifact_expected'],'limitations':native['limitations']},[a+'/runs/verification.json',a+'/runs/smoke-events.jsonl',a+'/runs/smoke-events-2.jsonl',a+'/runs/smoke-events-3.jsonl',a+'/runs/smoke-query.txt',a+'/runs/smoke-query-3.txt',a+'/runs/resume-query.txt',a+'/runs/smoke-expected.json',w+'/validation-input.json',w+'/validation-output.json',a+'/configure_local.py',a+'/launch.py',a+'/profiles/daily.json'],[native['model']])
    large=load(ROOT/a/'runs/large-hermes-20261029-133137/report.json')
    register('20261029-hermes-35b-tools','Hermes Qwen 35B actual file / terminal tools','hermes-tools','harness-integration',large['started_at'],{'outcome':'passed' if large['success'] else 'failed','headline':'Read, terminal output and write checked independently','checks':large['independent_checks'],'seconds':large['hermes_seconds'],'maximum_observed_slot_tokens':large['maximum_observed_slot_tokens']},[a+'/runs/large-hermes-20261029-133137',w+'/large-trial-20261029-133137',a+'/test_large_model.py',a+'/verify_large_model.py',a+'/profiles/large.json'],[large['test_model']])
    context=load(ROOT/a/'runs/context64k-20261029-195220/results.json')
    register('20261029-hermes-context64k','64K raw capacity + separate short Hermes tool checks','hermes-context64k','capacity',context['started_at'],{'outcome':'passed' if all(m['hermes']['passed'] for m in context['models'].values()) else 'failed','headline':'Two short Hermes checks plus separate near-64K raw API tests','hermes':{k:v['hermes'] for k,v in context['models'].items()},'limitations':context['limitations']},[a+'/runs/context64k-20261029-195200',a+'/runs/context64k-20261029-195220',w+'/context64k-20261029-195220','artifacts/local-llm/hermes/benchmarks/context64k_probe.py','artifacts/local-llm/hermes/benchmarks/context64k_report.py'],[m['alias'] for m in context['models'].values()])
    mcp=load(ROOT/a/'runs/mcp-verification.json');app=load(ROOT/a/'runs/mcp-app-connection.json')
    register('20261029-hermes-mcp','Hermes MCP local stdio and app transport','hermes-mcp','transport-integration',mcp['verified_at'],{'outcome':'partial','headline':'Local stdio passed; app transport failed: tunnel_client_not_seen','local_stdio':'passed','tool_count':len(mcp['tools']),'app_transport':app['AppTransport'],'model_inference_tested':False,'required_client_step':app['RequiredClientStep']},[a+'/mcp_setup.py',a+'/runs/mcp-verification.json',a+'/runs/mcp-app-connection.json',a+'/logs/mcp-probe.stderr.log'],[])
    for suffix in ['140654','141429']:
        name='comparison-20261029-'+suffix;v=load(ROOT/a/'benchmarks'/name/'results.json')
        cases=[{'model':k,'task':c['task'],'passed':c['passed'],'artifact_correct':c['artifact_correct'],'workflow_correct':c['workflow_correct']} for k,m in v['models'].items() for c in m['hermes']]
        passed=sum(c['passed'] for c in cases)
        register('20261029-hermes-tasks-'+suffix,'Hermes JSON / CSV / repair tasks '+suffix,'hermes-tasks','harness-integration',v['started_at'],{'outcome':'passed' if passed==len(cases) else 'partial','headline':f'Hermes task checks: {passed}/{len(cases)}; historical attempt retained','passed':passed,'attempted':len(cases),'cases':cases,'limitations':['This source also contains direct HumanEval results; only its Hermes cases are counted here.','Single attempt per task; earlier and revised-schema runs remain separate.']},[a+'/benchmarks/'+name,w+'/'+name,a+'/benchmarks/compare_models.py',a+'/benchmarks/grade_worker.py'],[m['alias'] for m in v['models'].values()])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=pathlib.Path,required=True);args=ap.parse_args()
    count=import_files(args.source_root.resolve());register_runs();print(json.dumps({'hermes_files_exported':count,'historical_runs_registered':6,'live_inference_performed':False}))
