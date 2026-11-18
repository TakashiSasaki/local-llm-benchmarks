"""Small paired Gemma MTP compatibility/performance probe; no generated code execution."""
import json, pathlib, socket, subprocess, sys, threading, time, urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks import study, memory_windows as memory

ROOT=study.ROOT
RUN=study.resolve_run('period-004-gemma-e4b-mtp-small-probe-20261118')
OLD=study.resolve_run('period-004-gemma-e4b-chat-thinking-allgpu-humaneval-20261118')
ASSISTANT=pathlib.Path('C:/LocalLLM/models/mtp-gemma-4-E4B-it-BF16-ggml-org.gguf')
EXPECTED='5fe3a6c5ebd2f241d9f27d2529fbf023564a6ac4c3db501fa7837887f37ece77'

def api(route,payload=None,timeout=15):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request('http://127.0.0.1:18094'+route,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as f:return json.load(f)

def condition(mode):
    args=study.load(OLD/'configs/server-command.json')['args']
    args[args.index('--port')+1]='18094';args[args.index('--alias')+1]='gemma-e4b-mtp-probe'
    if mode=='mtp':
        args[args.index('--spec-type')+1]='draft-mtp'
        args.extend(['--spec-draft-model',str(ASSISTANT),'--spec-draft-ngl','all','--spec-draft-n-max','3'])
    args.extend(['--log-verbosity','4'])
    study.save(RUN/'configs'/f'{mode}-command.json',{'args':args})
    with socket.socket() as s:assert s.connect_ex(('127.0.0.1',18094))!=0,'port occupied'
    hits=[];finished=threading.Event();server=None;monitor=None
    try:
        with (RUN/'logs'/f'{mode}-server.log').open('wb') as log:
            server=subprocess.Popen(args,cwd=pathlib.Path(args[0]).parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        monitor=memory.Monitor(server.pid,RUN/'logs'/f'{mode}-memory.jsonl').start()
        def guard():
            low=0
            while not finished.wait(3):
                s=memory.snapshot(server.pid);low=low+1 if s['available_ram_bytes']<3*1024**3 else 0
                if low>=3:hits.append('RAM reserve');server.terminate();return
        threading.Thread(target=guard,daemon=True).start()
        for _ in range(600):
            if server.poll() is not None:raise RuntimeError(f'server exited: {server.returncode}')
            try:
                if api('/health')['status']=='ok':break
            except (OSError,TimeoutError):pass
            time.sleep(1)
        else:raise TimeoutError('server startup')
        props=api('/props');assert props['total_slots']==1 and props['default_generation_settings']['n_ctx']==65536
        snap=memory.snapshot(server.pid);assert snap['gpu_used_mib'] is not None and snap['gpu_used_mib']<=7676 and snap['available_ram_bytes']>=3*1024**3
        study.save(RUN/'configs'/f'{mode}-admission.json',snap)
        for i in range(3):
            prev=study.load(OLD/'raw'/f'HumanEval_{i}.json');payload=prev['request'];payload['model']='gemma-e4b-mtp-probe';payload['max_tokens']=1024
            started=time.monotonic();response=api('/v1/chat/completions',payload,timeout=600)
            study.save(RUN/'raw'/f'{mode}-HumanEval_{i}.json',{'request':payload,'response':response,'seconds':time.monotonic()-started})
            print(json.dumps({'mode':mode,'task':i,'finish':response['choices'][0]['finish_reason'],'tokens':response['usage']['completion_tokens'],'timings':response.get('timings')}),flush=True)
        return {'status':'complete','cases':3}
    except Exception as e:
        print(f'{mode}: {e!r}',flush=True);return {'status':'failed','error':repr(e)}
    finally:
        finished.set()
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        if monitor:study.save(RUN/'summaries'/f'{mode}-memory.json',monitor.stop())
        study.save(RUN/'configs'/f'{mode}-cleanup.json',{'stopped':server is None or server.poll() is not None,'resource_guard':hits})

if __name__=='__main__':
    assert study.sha(ASSISTANT)==EXPECTED
    manifest=study.load(RUN/'manifest.json');manifest.update(status='running',started_at=study.now());study.save(RUN/'manifest.json',manifest)
    results={}
    try:
        for mode in ('mtp','baseline'):results[mode]=condition(mode)
        study.save(RUN/'summary.json',{'outcome':'complete' if all(x['status']=='complete' for x in results.values()) else 'partial','conditions':results})
        manifest.update(status='complete',completed_at=study.now())
    except BaseException as e:manifest.update(status='failed',error=repr(e));raise
    finally:study.save(RUN/'manifest.json',manifest)
