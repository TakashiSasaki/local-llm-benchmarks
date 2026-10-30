"""One owned Windows server, four 64K conditions and one actual Hermes roundtrip."""
import argparse,datetime,hashlib,importlib.util,json,os,pathlib,socket,subprocess,sys,threading,time,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,create_run,load,save,sha,snapshot_sources,now
from local_llm_benchmarks import memory_windows as memory

def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def run(a):
    modelmeta=load(ROOT/a.model_manifest);profile=load(ROOT/a.profile);model=pathlib.Path(profile['model'])
    parent=create_run('Qwen3.6 35B IQ3_M 64K comparison','humaneval+bfcl+hermes',config={'model':modelmeta,'profile':profile,'comparison':'artifacts/local-llm/runs/benchmark-matrix-20261030-194424/matrix-data.json','limitations':['Distributed-artifact comparison; different quantizers/calibration may contribute.','HumanEval is mode-blocked rather than alternating OFF/ON within each task; one sample per condition.']},run_id=a.id)
    snapshot_sources(parent);manifest=load(parent/'manifest.json');manifest.update(status='running',started_at=now());save(parent/'manifest.json',manifest)
    while not model.exists():
        print(json.dumps({'event':'waiting_for_model','file':model.name}),flush=True);time.sleep(30)
    assert model.stat().st_size==modelmeta['bytes'],'Wrong model size'
    h=hashlib.sha256()
    with model.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    assert h.hexdigest()==modelmeta['sha256'],'Model hash mismatch'
    try:
        with socket.create_connection(('127.0.0.1',8089),timeout=1):raise RuntimeError('Port in use; refusing to replace a model')
    except (ConnectionRefusedError,TimeoutError):pass
    binary=pathlib.Path(profile['runtime_executable']);device=subprocess.run([str(binary),'--list-devices'],capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    assert device.returncode==0 and b'CUDA0' in device.stdout+device.stderr,'CUDA unavailable'
    save(parent/'configs/baseline-memory.json',memory.snapshot(os.getpid()))
    arguments=[str(binary),'-m',str(model),'--host','127.0.0.1','--port','8089','--alias',profile['profile_id']]+profile['server_args']
    save(parent/'configs/server-command.json',{'args':arguments})
    server=None;monitor=None;guard_stop=threading.Event();guard_hits=[];children=[];initial_gateway=None;gateway_stopped=False;install=load(a.installation)
    env=dict(os.environ,HERMES_HOME=install['hermes_home'],PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    try:
        started=time.monotonic()
        with (parent/'logs/llama-server.log').open('wb') as log:server=subprocess.Popen(arguments,cwd=binary.parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        monitor=memory.Monitor(server.pid,parent/'logs/memory.jsonl').start()
        def guard():
            count=0
            while not guard_stop.wait(3):
                snap=memory.snapshot(server.pid);count=count+1 if snap['available_ram_bytes']<1024**3 else 0
                if count>=3:guard_hits.append({'at':now(),'reason':'Available physical RAM below 1 GiB for three samples'});server.terminate();return
        threading.Thread(target=guard,daemon=True).start()
        def api(route):
            with urllib.request.urlopen('http://127.0.0.1:8089'+route,timeout=5) as f:return json.load(f)
        for _ in range(600):
            if server.poll() is not None:raise RuntimeError('Server exited during load: '+str(server.returncode))
            try:
                if api('/health')['status']=='ok':break
            except OSError:pass
            time.sleep(1)
        else:raise TimeoutError('Server load timeout')
        props=api('/props');assert props['build_info'].startswith('b11960-') and props['model_alias']==profile['profile_id'] and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
        bf=module('bfcl_driver',ROOT/'benchmarks/bfcl.py');save(parent/'configs/server-props.json',bf.public_props(props));save(parent/'configs/server-load.json',{'seconds':time.monotonic()-started,'pid':server.pid})
        print(json.dumps({'event':'model_ready','load_seconds':round(time.monotonic()-started,2)}),flush=True)
        for suite in ['humaneval','bfcl']:
            for mode in ['off','on']:
                child=create_run('Qwen3.6 35B IQ3_M '+suite+' '+mode,suite,config={'model':modelmeta,'profile':profile,'parent_run':parent.name},run_id=parent.name+'-'+suite+'-'+mode);children.append(child.name)
                command=[sys.executable,'-B',str(ROOT/'benchmarks'/(suite+'.py')),'--run',child.name,'--model',profile['profile_id'],'--thinking',mode]
                print(json.dumps({'event':'condition_start','suite':suite,'mode':mode,'run':child.name}),flush=True)
                with (parent/'logs'/(suite+'-'+mode+'.log')).open('w',encoding='utf-8') as log:completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                if completed.returncode:raise RuntimeError('Condition failed: '+child.name)
                print(json.dumps({'event':'condition_complete',**load(child/'summary.json')}),flush=True)
        gateway=subprocess.run([install['hermes_launcher'],'gateway','status'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW);initial_gateway='Gateway is running' in gateway.stdout
        child=create_run('Qwen3.6 35B IQ3_M Hermes actual tools','hermes-tools',config={'model':modelmeta,'profile':profile,'parent_run':parent.name},run_id=parent.name+'-hermes',experiment_type='harness-integration',harness='hermes');children.append(child.name)
        command=[sys.executable,'-B',str(ROOT/'integrations/hermes/scripts/tool_roundtrip.py'),'--run',child.name,'--model',profile['profile_id'],'--installation',str(a.installation)]
        with (parent/'logs/hermes.log').open('w',encoding='utf-8') as log:completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode:raise RuntimeError('Hermes trial driver failed')
        summaries={name:load(ROOT/'runs'/name/'summary.json') for name in children}
        save(parent/'summary.json',{'outcome':'passed' if summaries[child.name]['outcome']=='passed' else 'partial','headline':'IQ3_M: four benchmark conditions and actual Hermes tools','child_runs':children,'conditions':4,'answers':200,'summaries':summaries,'scope':'Collection completed; benchmark pass counts and Hermes checks are separate.'})
        manifest.update(status='complete',completed_at=now())
    except BaseException as exc:manifest.update(status='failed',error=repr(exc));raise
    finally:
        guard_stop.set()
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        if monitor:save(parent/'summaries/memory.json',monitor.stop())
        if initial_gateway is False:
            r=subprocess.run([install['hermes_launcher'],'gateway','stop'],env=env,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);gateway_stopped=r.returncode==0
        save(parent/'configs/cleanup.json',{'server_stopped':server is None or server.poll() is not None,'resource_guard':guard_hits,'gateway_initially_running':initial_gateway,'test_started_gateway_stop_succeeded':gateway_stopped,'child_runs':children});save(parent/'manifest.json',manifest)
    print(json.dumps({'event':'study_complete','run':parent.name}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--id',required=True);p.add_argument('--model-manifest',default='configs/models/qwen36-35b-iq3-m.json');p.add_argument('--profile',default='configs/qwen36-35b-iq3m-64k.json');p.add_argument('--installation',type=pathlib.Path,required=True);run(p.parse_args())
