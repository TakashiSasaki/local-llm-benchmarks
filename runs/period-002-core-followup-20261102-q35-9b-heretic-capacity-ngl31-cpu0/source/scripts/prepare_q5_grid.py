"""Sequential pinned downloads, unchanged-capacity probes, then a declared benchmark grid."""
import argparse,json,os,pathlib,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now

def run(a):
    plan=load(ROOT/a.plan);prefix=plan['prefix'];groups=[];unavailable=[]
    logs=ROOT/'.local'/prefix;logs.mkdir(parents=True,exist_ok=True)
    def event(**v):
        value={'at':now(),**v}
        with (logs/'preparation.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    def execute(command,name):
        event(event='command_start',step=name)
        with (logs/(name+'.log')).open('w',encoding='utf-8') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        if r.returncode:raise RuntimeError('Preparation step failed: '+name)
        event(event='command_complete',step=name)
    def wait_complete(name):
        parent=ROOT/'runs'/name;deadline=time.monotonic()+4*3600
        while True:
            m=load(parent/'manifest.json')
            if m['status']=='complete':return load(parent/'summary.json')
            if m['status']=='failed':raise RuntimeError('Capacity orchestrator failed: '+name)
            if time.monotonic()>deadline:raise TimeoutError('Waiting for capacity run: '+name)
            time.sleep(15)
    def capacity(item,mtp):
        name=item.get('existing_capacity') if mtp=='on' else None
        if name:event(event='waiting_for_existing_capacity',run=name)
        else:
            name=prefix+'-'+item['key']+'-capacity-'+mtp
            execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_capacity_sweep.py'),'--prefix',name,'--model-manifest',item['model_manifest'],'--profile',item['profile'],'--mtp',mtp],name)
        return name,wait_complete(name)
    for item in plan['models']:
        if item.get('existing_capacity'):
            # Its independently started managed downloader owns the file. Do not duplicate it.
            deadline=time.monotonic()+4*3600
            while not (ROOT/item['download_report']).exists():
                if time.monotonic()>deadline:raise TimeoutError('Existing managed download did not finish')
                time.sleep(15)
        else:
            execute([sys.executable,'-B',str(ROOT/'scripts/download_model_managed.py'),'--manifest',item['model_manifest'],'--model-dir',str(a.model_dir),'--connections','32','--min-free-gib','32','--report',item['download_report']],item['key']+'-download')
        name,result=capacity(item,'on');cpu=result['selected_cpu_moe'];states=['off','on']
        if cpu is None:
            unavailable.append({'model_manifest':item['model_manifest'],'mtp':'on','thinking':['off','on'],'benchmarks':['bfcl','humaneval'],'capacity_run':name,'reason':'No tested placement completed the unchanged 65536-context/F16 short probe; not a zero capability score.'})
            name,result=capacity(item,'off');cpu=result['selected_cpu_moe'];states=['off']
        if cpu is None:
            unavailable.append({'model_manifest':item['model_manifest'],'mtp':'off','thinking':['off','on'],'benchmarks':['bfcl','humaneval'],'capacity_run':name,'reason':'No tested placement completed the unchanged capacity probe; capability answers were not collected.'});continue
        group={'key':item['key']+'-q5m','model_manifest':item['model_manifest'],'profile':item['profile'],'cpu_moe_layers':cpu,'load_mode':'none','states':states,'role':'target'};groups.append(group)
        control={**group,'key':item['key']+'-q4-control','model_manifest':item['control_manifest'],'role':'matched Q4 control'}
        if cpu==34:control['reference_runs']={k:v for k,v in item['control_references'].items() if k in states}
        groups.append(control)
        event(event='capacity_selected',model=item['key'],cpu_moe=cpu,states=states,control_fresh=cpu!=34)
    definition={'title':'Qwen3.6 / Empero Q5_K_M × MTP・思考 OFF/ON','scope':plan['scope'],'groups':groups,'unavailable':unavailable,'capacity_policy':'Keep 65536 context, 64000 output cap and F16 target/draft KV. First short-probe placement is not a guarantee for long prompts. Q4 controls match placement and load-mode.','plan':a.plan}
    path='configs/'+prefix+'.json';save(ROOT/path,definition);event(event='grid_definition_ready',definition=path,groups=len(groups),unavailable=len(unavailable))
    execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_grid.py'),'--prefix',prefix,'--definition',path,'--benchmark-python',str(a.benchmark_python)],'full-grid')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',default='configs/q5-k-m-plan.json');p.add_argument('--model-dir',type=pathlib.Path,required=True);p.add_argument('--benchmark-python',type=pathlib.Path,required=True);run(p.parse_args())
