"""Validate raw-prompt completion compatibility without executing model code."""
import ast,gzip,json,os,pathlib,socket,subprocess,sys,threading,time,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now
from local_llm_benchmarks import memory_windows as memory

RUN=ROOT/'runs/period-004-gemma-prefix-validation-20261112'
DATA=ROOT/'.local/official-humaneval-b9453e8/data/HumanEval.jsonl.gz'

def api(route,payload=None,timeout=7200):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request('http://127.0.0.1:8089'+route,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as f:return json.load(f)

def main():
    manifest=load(RUN/'manifest.json');server=None;monitor=None;stop=threading.Event();hits=[]
    try:
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Port 8089 occupied'
        original=load(ROOT/'runs/period-003-gemma4-e4b-q4km-first-20261112/configs/server-command.json')['args']
        args=list(original);args[args.index('--alias')+1]='period4-gemma-prefix-validation'
        save(RUN/'configs/server-command.json',{'args':args})
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        with (RUN/'logs/llama-server.log').open('wb') as f:server=subprocess.Popen(args,cwd=pathlib.Path(args[0]).parent,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        monitor=memory.Monitor(server.pid,RUN/'logs/memory.jsonl').start()
        def guard():
            low=0
            while not stop.wait(3):
                s=memory.snapshot(server.pid);low=low+1 if s['available_ram_bytes']<3*1024**3 else 0
                if low>=3:hits.append({'reason':'RAM reserve','at':now()});server.terminate();return
        threading.Thread(target=guard,daemon=True).start()
        for _ in range(600):
            if server.poll() is not None:raise RuntimeError('server exited')
            try:
                if api('/health',timeout=5)['status']=='ok':break
            except OSError:pass
            time.sleep(1)
        else:raise TimeoutError('server load timeout')
        props=api('/props',timeout=30);assert props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1 and props['build_info'].startswith('b11960-')
        snap=memory.snapshot(server.pid);assert snap['available_ram_bytes']>=3*1024**3 and snap['gpu_used_mib'] is not None and snap['gpu_used_mib']<=7676
        save(RUN/'configs/admission-memory.json',snap)
        problems=[json.loads(x) for x in gzip.decompress(DATA.read_bytes()).decode().splitlines()]
        results=[]
        for problem in problems[:5]:
            payload={'prompt':problem['prompt'],'n_predict':16384,'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'seed':42,'cache_prompt':False}
            started=time.monotonic();response=api('/completion',payload)
            content=response['content'];raw=RUN/'raw'/(problem['task_id'].replace('/','_')+'.json')
            save(raw,{'task_id':problem['task_id'],'request':payload,'response':response,'seconds':time.monotonic()-started})
            try:ast.parse(problem['prompt']+content);parsable=True
            except SyntaxError:parsable=False
            results.append({'task_id':problem['task_id'],'parses_when_appended':parsable,'finish_reason':response.get('stop_type'),'output_tokens':response.get('tokens_predicted')})
            save(RUN/'summaries/format-validation.json',results)
            print(json.dumps(results[-1]),flush=True)
        save(RUN/'summary.json',{'outcome':'passed' if all(r['parses_when_appended'] for r in results) else 'format_mismatch','samples':len(results),'syntax_valid':sum(r['parses_when_appended'] for r in results),'scope':'Five independent adapter-validation samples; syntax check only, no test execution, not a benchmark score.'})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:manifest.update(status='failed',error=repr(e),failed_at=now());raise
    finally:
        stop.set()
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        if monitor:save(RUN/'summaries/memory.json',monitor.stop())
        save(RUN/'configs/cleanup.json',{'server_stopped':server is None or server.poll() is not None,'resource_guard':hits})
        save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
