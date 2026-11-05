"""Own sequential pinned downloads and 64K smoke probes; never delete download fragments."""
import json,os,pathlib,shutil,socket,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,snapshot_sources,now


def run():
    prefix='period-002-stage-a-preparation-20261102'
    parent=create_run('Period 002 stage A acquisition and 64K preflight','period2-preparation',run_id=prefix,experiment_type='capacity',config={'models':['q35-4b-base','q35-4b-abliterix'],'capability_answers':0,'disk_reserve_bytes':32*1024**3,'primary_humaneval_grader':'Pending pinned standard-compatible implementation; no HE inference in this preparation'})
    snapshot_sources(parent);m=load(parent/'manifest.json');m.update(status='running',started_at=now(),owner_pid=os.getpid());save(parent/'manifest.json',m);children=[]
    def event(**v):
        v={'at':now(),**v}
        with (parent/'logs/progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(v)+'\n')
        print(json.dumps(v),flush=True)
    def execute(command,name,reserve=False):
        with (parent/'logs'/(name+'.log')).open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
            event(event='child_started',step=name,pid=proc.pid)
            try:
                while proc.poll() is None:
                    if reserve and shutil.disk_usage('C:/LocalLLM/models').free<32*1024**3:raise RuntimeError('Disk reserve reached; keep partial weights')
                    time.sleep(2)
                if proc.returncode:raise RuntimeError('Step failed: '+name+'; see owned log')
            finally:
                if proc.poll() is None:
                    subprocess.run(['taskkill.exe','/PID',str(proc.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);proc.wait()
        event(event='child_complete',step=name)
    try:
        assert not list((ROOT/'runs').glob(prefix+'-capacity-*')),'Do not duplicate preparation'
        for key in m['config']['models']:
            original=ROOT/'experiments/period-002/models'/(key+'.json');meta=load(original)
            assert shutil.disk_usage('C:/LocalLLM/models').free>meta['bytes']+32*1024**3
            event(event='download_start',model=key,bytes=meta['bytes'])
            execute([sys.executable,'-B',str(ROOT/'scripts/download_pinned_model.py'),'--manifest',str(original),'--model-dir','C:/LocalLLM/models','--connections','1'],key+'-download',True)
            save(parent/'configs'/(key+'-verified.json'),{'sha256':meta['sha256'],'bytes':meta['bytes'],'filename':meta['filename'],'verified_by':'pinned downloader full-file SHA256'})
        for key in m['config']['models']:
            profile='experiments/period-002/configs/'+key+'-preflight.json';meta=load(ROOT/'experiments/period-002/models'/(key+'.json'));meta.update(model='Qwen3.5-4B '+('ordinary' if key.endswith('base') else 'Abliterix'),status='Stage A selected artifact')
            save(parent/'configs'/(key+'-model.json'),meta)
            with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Existing server remains untouched'
            name=prefix+'-capacity-'+key;children.append(name)
            execute([sys.executable,'-B',str(ROOT/'scripts/run_mtp_study.py'),'--id',name,'--model-manifest',(parent/'configs'/(key+'-model.json')).relative_to(ROOT).as_posix(),'--profile',profile,'--mtp','off','--cpu-moe','0','--load-mode','none','--pilot'],key+'-preflight')
            assert load(ROOT/'runs'/name/'configs/cleanup.json')['server_stopped']
            memory=load(ROOT/'runs'/name/'summaries/memory.json');assert memory['peak_gpu_used_mib_system_total'] is not None and memory['peak_gpu_used_mib_system_total']<=7676,'GPU reserve check failed'
            event(event='preflight_complete',model=key,memory=memory)
        save(parent/'summary.json',{'outcome':'passed','scope':'Two verified downloads and 64K speed/tool/mode preflight; zero capability answers','child_runs':children,'next':'Pin and validate standard-compatible HumanEval policy before capability inference'})
        m.update(status='complete',completed_at=now())
    except BaseException as exc:
        m.update(status='failed',error=repr(exc),completed_at=now());event(event='preparation_failed',error=repr(exc));raise
    finally:save(parent/'manifest.json',m)


if __name__=='__main__':run()
