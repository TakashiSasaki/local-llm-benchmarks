"""Queue pinned variants, verify capacity, and collect a matched quantization grid."""
import argparse,json,os,pathlib,socket,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,create_run,snapshot_sources

def run(a):
    plan=load(ROOT/a.plan);prefix=plan['prefix']
    parent=create_run(plan['title']+' preparation','variant-grid-preparation',run_id=prefix+'-preparation',experiment_type='capacity',config={'plan':plan,'capability_answers':0})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now());save(parent/'manifest.json',m)
    def event(**v):
        v={'at':now(),**v}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(v)+'\n')
        print(json.dumps(v),flush=True)
    def execute(command,name,check=True):
        event(event='step_start',step=name)
        with (parent/'logs'/(name+'.log')).open('w',encoding='utf-8') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
        event(event='step_finished',step=name,exit_code=r.returncode)
        if check and r.returncode:raise RuntimeError('Preparation step failed: '+name)
        return r.returncode
    def capacity(variant,mode):
        name=prefix+'-'+variant['key']+'-capacity-'+mode
        execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_capacity_sweep.py'),'--prefix',name,'--model-manifest',variant['model_manifest'],'--profile',plan['profile'],'--mtp',mode],name)
        result=load(ROOT/'runs'/name/'summary.json');return name,result['selected_cpu_moe']
    def pilot(variant,mode,cpu):
        name=prefix+'-'+variant['key']+'-common-cpu'+str(cpu)+'-'+mode
        code=execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',variant['model_manifest'],'--profile',plan['profile'],'--mtp',mode,'--cpu-moe',str(cpu),'--load-mode',plan['load_mode'],'--pilot'],name,check=False)
        clean=load(ROOT/'runs'/name/'configs/cleanup.json');assert clean['server_stopped'],'Owned pilot server still running'
        return name,code==0 and load(ROOT/'runs'/name/'manifest.json')['status']=='complete'
    selected=[];unavailable=[]
    def unavailable_condition(variant,states,evidence,reason):
        unavailable.append({'model_manifest':variant['model_manifest'],'mtp':states,'thinking':['off','on'],'benchmarks':['bfcl','humaneval'],'capacity_run':evidence,'reason':reason})
    try:
        wait=plan.get('wait_for_study')
        if wait:
            event(event='queued_after_study',run=wait)
            deadline=time.monotonic()+24*3600
            while True:
                f=ROOT/'runs'/wait/'manifest.json'
                if f.exists() and load(f)['status'] in ['complete','failed']:break
                if time.monotonic()>deadline:raise TimeoutError('Preceding study did not finish in 24 hours')
                time.sleep(30)
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Existing server retained; preparation did not start'
        for variant in plan['variants']:
            execute([sys.executable,'-B',str(ROOT/'scripts/download_model_managed.py'),'--manifest',variant['model_manifest'],'--model-dir',str(a.model_dir),'--connections','32','--min-free-gib','32','--report','publication/'+prefix+'-'+variant['key']+'-download.json'],variant['key']+'-download')
            name,cpu=capacity(variant,'on');states=['off','on']
            if cpu is None:
                unavailable_condition(variant,['on'],name,'No tested placement completed the unchanged 64K/F16 MTP ON probe. This is not a zero capability score.')
                name,cpu=capacity(variant,'off');states=['off']
            if cpu is None:unavailable_condition(variant,['off'],name,'No tested placement completed the unchanged MTP OFF probe.');continue
            selected.append({**variant,'cpu':cpu,'states':states})
        common=max([plan['default_cpu_moe_layers']]+[v['cpu'] for v in selected]);groups=[]
        for variant in selected:
            if variant['cpu']!=common:
                name,passed=pilot(variant,variant['states'][-1],common)
                if not passed:unavailable_condition(variant,variant['states'],name,'The shared CPU placement did not complete the unchanged capacity probe.');continue
            groups.append({'key':variant['key'],'model_manifest':variant['model_manifest'],'profile':plan['profile'],'cpu_moe_layers':common,'load_mode':plan['load_mode'],'states':variant['states'],'role':'target'})
        if groups:
            states=sorted(set(s for g in groups for s in g['states']),key=['off','on'].index)
            control={'key':'q4m-control','model_manifest':plan['control_manifest'],'profile':plan['profile'],'cpu_moe_layers':common,'load_mode':plan['load_mode'],'states':states,'role':'matched M control'}
            if common==plan['default_cpu_moe_layers']:control['reference_runs']={s:plan['control_references'][s] for s in states}
            else:
                name,passed=pilot(control,states[-1],common)
                if not passed:unavailable_condition(control,states,name,'Matched M control did not complete the common-placement capacity probe.');control=None
            if control:groups.append(control)
        definition={'title':plan['title'],'groups':groups,'unavailable':unavailable,'plan':a.plan,'common_cpu_moe_layers':common,'scope':'S/L fresh inference, M explicitly referenced only if its placement/load-mode match. BFCL80 and HumanEval20, native thinking OFF/ON, MTP OFF/ON. Fixed-length speed 256 tokens x 3 prompts x 3 repeats.'}
        definition_path='configs/'+prefix+'.json';save(ROOT/definition_path,definition)
        event(event='grid_start',definition=definition_path,common_cpu_moe=common,groups=len(groups),unavailable=len(unavailable))
        execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_grid.py'),'--prefix',prefix,'--definition',definition_path,'--benchmark-python',str(a.benchmark_python)],'full-grid')
        save(parent/'summary.json',{'outcome':'partial' if unavailable else 'passed','headline':'Variant preparation and collection finished','benchmark_run':prefix,'common_cpu_moe_layers':common,'unavailable':unavailable,'capability_answers':0,'scope':'All capability answers belong to the separate benchmark runs; preparation contains downloads and capacity probes.'})
        m.update(status='complete',completed_at=now())
    except BaseException as e:m.update(status='failed',error=repr(e));raise
    finally:save(parent/'manifest.json',m)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--model-dir',type=pathlib.Path,required=True);p.add_argument('--benchmark-python',type=pathlib.Path,required=True);run(p.parse_args())
