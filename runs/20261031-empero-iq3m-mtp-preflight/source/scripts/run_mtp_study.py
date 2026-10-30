"""Owned Windows server for a quantization/MTP cell; immutable child runs."""
import argparse, hashlib, importlib.util, json, os, pathlib, socket, subprocess, sys, threading, time, urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,sha,snapshot_sources,now
from local_llm_benchmarks import memory_windows as memory

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def run(a):
    metadata=load(ROOT/a.model_manifest); profile=load(ROOT/'configs/qwen38-35b-distill-iq3m-64k.json')
    model=pathlib.Path(r'C:\LocalLLM\models')/metadata['filename']; binary=pathlib.Path(profile['runtime_executable'])
    alias='mtp-study-'+metadata['quantization'].lower().replace('_','-')+'-'+a.mtp
    args=list(profile['server_args']); args[args.index('--n-cpu-moe')+1]=str(a.cpu_moe)
    args += ['--spec-type','draft-mtp' if a.mtp=='on' else 'none']
    if a.mtp=='on': args += ['--spec-draft-n-max','3','--spec-draft-p-min','0','--spec-draft-ngl','all','--spec-draft-n-ubatch','128','--spec-draft-type-k','f16','--spec-draft-type-v','f16']
    profile.update(profile_id=alias,model=str(model),model_hash=metadata['sha256'],server_args=args,status='Isolated matched placement quantization/MTP experiment',mtp=a.mtp)
    title='Empero '+metadata['quantization']+' MTP '+a.mtp+(' preflight' if a.pilot else ' 64K')
    parent=create_run(title,'mtp-preflight' if a.pilot else 'quantization-mtp',config={'model':metadata,'profile':profile,'pilot':a.pilot,'historical_comparison':'Main placement deliberately matched at '+str(a.cpu_moe)+' CPU MoE layers; historical runs used 30, so historical timings are not the paired control.'},run_id=a.id,experiment_type='capacity' if a.pilot else 'benchmark')
    snapshot_sources(parent); manifest=load(parent/'manifest.json'); manifest.update(status='running',started_at=now()); save(parent/'manifest.json',manifest)
    server=None; mon=None; stop=threading.Event(); guard_hits=[]; children=[]
    try:
        assert model.exists() and model.stat().st_size==metadata['bytes'],'Model absent or size differs'
        h=hashlib.sha256()
        with model.open('rb') as f:
            for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
        assert h.hexdigest()==metadata['sha256'],'Model hash differs'
        save(parent/'configs/model-file-verification.json',{'filename':model.name,'bytes':model.stat().st_size,'sha256':h.hexdigest(),'verified':True})
        with socket.socket() as sock: assert sock.connect_ex(('127.0.0.1',8089))!=0,'Port occupied; existing server will not be replaced'
        save(parent/'configs/baseline-memory.json',memory.snapshot(os.getpid()))
        command=[str(binary),'-m',str(model),'--host','127.0.0.1','--port','8089','--alias',alias]+args
        save(parent/'configs/server-command.json',{'args':command})
        started=time.monotonic()
        with (parent/'logs/llama-server.log').open('wb') as log: server=subprocess.Popen(command,cwd=binary.parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        mon=memory.Monitor(server.pid,parent/'logs/memory.jsonl').start()
        def guard():
            low=0
            while not stop.wait(3):
                snap=memory.snapshot(server.pid); low=low+1 if snap['available_ram_bytes']<1024**3 else 0
                if low>=3: guard_hits.append({'at':now(),'reason':'Physical available RAM under 1 GiB for three samples'}); server.terminate(); return
        threading.Thread(target=guard,daemon=True).start()
        def api(route,payload=None,timeout=15):
            req=urllib.request.Request('http://127.0.0.1:8089'+route,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=timeout) as f:return json.load(f)
        for _ in range(600):
            if server.poll() is not None: raise RuntimeError('Owned server exited while loading: '+str(server.returncode))
            try:
                if api('/health')['status']=='ok':break
            except OSError: pass
            time.sleep(1)
        else: raise TimeoutError('Server load timeout')
        props=api('/props'); bf=module('bfcl_driver',ROOT/'benchmarks/bfcl.py')
        assert props['build_info'].startswith('b11960-') and props['model_alias']==alias
        assert props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
        spec=props['default_generation_settings']['params']['speculative.types']
        assert ('draft-mtp' in spec.split(','))==(a.mtp=='on'),spec
        save(parent/'configs/server-props.json',bf.public_props(props)); save(parent/'configs/server-load.json',{'seconds':time.monotonic()-started,'pid':server.pid,'speculative.types':spec})
        print(json.dumps({'event':'ready','run':parent.name,'load_seconds':round(time.monotonic()-started,2),'speculative.types':spec}),flush=True)
        speed=create_run(title+' fixed length speed','fixed-length-speed',config={'parent_run':parent.name,'model':metadata,'profile':profile},run_id=parent.name+'-speed'); children.append(speed.name)
        sm=load(speed/'manifest.json'); snapshot_sources(speed); sm.update(status='running',started_at=now());save(speed/'manifest.json',sm)
        try:
            summary=module('mtp_speed',ROOT/'benchmarks/mtp_speed.py').collect(speed,'http://127.0.0.1:8089',alias,count=128 if a.pilot else 256,repeats=1 if a.pilot else 3)
            if a.mtp=='on': assert summary['draft_tokens']>0,'MTP requested but no draft tokens observed'
            sm.update(status='complete',completed_at=now()); save(speed/'manifest.json',sm)
        except BaseException as e: sm.update(status='failed',error=repr(e));save(speed/'manifest.json',sm);raise
        print(json.dumps({'event':'speed_complete','run':parent.name,**summary}),flush=True)
        if not a.pilot:
            for suite in ['bfcl','humaneval']:
                for thinking in ['off','on']:
                    child=create_run(title+' '+suite+' thinking '+thinking,suite,config={'parent_run':parent.name,'model':metadata,'profile':profile},run_id=parent.name+'-'+suite+'-'+thinking); children.append(child.name)
                    command=[str(a.benchmark_python),'-B',str(ROOT/'benchmarks'/(suite+'.py')),'--run',child.name,'--model',alias,'--thinking',thinking]
                    print(json.dumps({'event':'condition_start','run':child.name}),flush=True)
                    with (parent/'logs'/(suite+'-'+thinking+'.log')).open('w',encoding='utf-8') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
                    if result.returncode:raise RuntimeError('Condition failed: '+child.name)
                    print(json.dumps({'event':'condition_complete','run':child.name,**load(child/'summary.json')}),flush=True)
        save(parent/'summary.json',{'outcome':'passed','headline':title,'child_runs':children,'mtp':a.mtp,'quantization':metadata['quantization'],'cpu_moe_layers':a.cpu_moe,'pilot':a.pilot,'summaries':{name:load(ROOT/'runs'/name/'summary.json') for name in children},'scope':'Collection complete; capability scores are recorded separately from throughput.'})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e: manifest.update(status='failed',error=repr(e));raise
    finally:
        stop.set()
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        if mon:save(parent/'summaries/memory.json',mon.stop())
        save(parent/'configs/cleanup.json',{'server_stopped':server is None or server.poll() is not None,'resource_guard':guard_hits,'child_runs':children})
        save(parent/'manifest.json',manifest)
    print(json.dumps({'event':'cell_complete','run':parent.name}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--id',required=True);p.add_argument('--model-manifest',required=True);p.add_argument('--mtp',choices=['off','on'],required=True);p.add_argument('--cpu-moe',type=int,default=34);p.add_argument('--pilot',action='store_true');p.add_argument('--benchmark-python',type=pathlib.Path,default=sys.executable);run(p.parse_args())
