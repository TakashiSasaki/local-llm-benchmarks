"""Collect untouched completions for official HumanEval; never execute generated code."""
import gzip,hashlib,json,os,pathlib,socket,subprocess,sys,threading,time,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now
from local_llm_benchmarks import memory_windows as memory

RUN=ROOT/'runs/period-004-gemma-humaneval-20261112'
MODEL=pathlib.Path('C:/LocalLLM/models/gemma-4-E4B-it-Q4_K_M.gguf')
RUNTIME=pathlib.Path('C:/LocalLLM/bin/b11960-cuda12.4/llama-server.exe')
SOURCE=ROOT/'.local/official-humaneval-b9453e8/data/HumanEval.jsonl.gz'

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def request(url,payload=None,timeout=7200):
    data=None if payload is None else json.dumps(payload).encode('utf-8')
    req=urllib.request.Request('http://127.0.0.1:8089'+url,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)

def main():
    manifest=load(RUN/'manifest.json');server=None;monitor=None;guard=threading.Event();hits=[]
    try:
        assert digest(MODEL)=='85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87'
        assert digest(RUNTIME)=='81f65c6681d66099e5d48757aa2c050ba958dc43816e584f0bb4181eb7c910d8'
        assert digest(SOURCE)=='b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef'
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',8089))!=0,'Port 8089 occupied'
        original=load(ROOT/'runs/period-003-gemma4-e4b-q4km-first-20261112/configs/server-command.json')['args']
        args=list(original);args[args.index('--alias')+1]='period4-gemma-official-he'
        save(RUN/'configs/server-command.json',{'args':args})
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        with (RUN/'logs/llama-server.log').open('wb') as log:server=subprocess.Popen(args,cwd=RUNTIME.parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        monitor=memory.Monitor(server.pid,RUN/'logs/memory.jsonl').start()
        def watch():
            lows=0
            while not guard.wait(3):
                snap=memory.snapshot(server.pid);lows=lows+1 if snap['available_ram_bytes']<3*1024**3 else 0
                if lows>=3:hits.append({'reason':'RAM reserve','at':now()});server.terminate();return
        threading.Thread(target=watch,daemon=True).start()
        for _ in range(600):
            if server.poll() is not None:raise RuntimeError('Server exited while loading')
            try:
                if request('/health',timeout=5)['status']=='ok':break
            except OSError:pass
            time.sleep(1)
        else:raise TimeoutError('Server did not load')
        props=request('/props',timeout=30);assert props['model_alias']=='period4-gemma-official-he' and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1 and props['build_info'].startswith('b11960-')
        snap=memory.snapshot(server.pid);assert snap['gpu_used_mib'] is not None and snap['gpu_used_mib']<=7676 and snap['available_ram_bytes']>=3*1024**3
        save(RUN/'configs/admission-memory.json',snap)
        # The model receives the official prompt only, never test or canonical_solution.
        rows=[json.loads(s) for s in gzip.decompress(SOURCE.read_bytes()).decode('utf-8').splitlines()]
        assert len(rows)==164 and len({p['task_id'] for p in rows})==164
        for mode in ['off','on']:
            for p in rows:
                name=p['task_id'].replace('/','_');raw=RUN/'raw'/(mode+'-'+name+'.json')
                assert not raw.exists(),'No implicit resume or retry'
                payload={'model':'period4-gemma-official-he','messages':[{'role':'user','content':p['prompt']}],'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'presence_penalty':0,'repeat_penalty':1,'seed':42,'max_tokens':16384,'cache_prompt':False,'chat_template_kwargs':{'enable_thinking':mode=='on'}}
                started=time.monotonic();response=request('/v1/chat/completions',payload)
                save(raw,{'task_id':p['task_id'],'thinking':mode,'request':payload,'response':response,'seconds':time.monotonic()-started})
                # Official evaluator input: untouched message content, completion only.
                content=response['choices'][0]['message'].get('content') or ''
                with (RUN/'summaries'/('samples-'+mode+'.jsonl')).open('a',encoding='utf-8') as f:f.write(json.dumps({'task_id':p['task_id'],'completion':content},ensure_ascii=False)+'\n')
                print(json.dumps({'event':'saved','mode':mode,'task_id':p['task_id'],'finish_reason':response['choices'][0]['finish_reason']}),flush=True)
        save(RUN/'summary.json',{'outcome':'collected','samples_per_mode':164,'new_answers':328,'official_scoring':'pending isolated Linux sandbox','scope':'Generation complete; no generated code executed'})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:
        manifest.update(status='failed',error=repr(e),failed_at=now());raise
    finally:
        guard.set()
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        if monitor:save(RUN/'summaries/memory.json',monitor.stop())
        save(RUN/'configs/cleanup.json',{'server_stopped':server is None or server.poll() is not None,'resource_guard':hits})
        save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
