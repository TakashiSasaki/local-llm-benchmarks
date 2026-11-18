"""Independent Gemma 4 BFCL transport probe; no benchmark test cases."""
import json, os, pathlib, socket, subprocess, sys, time, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_llm_benchmarks.study import create_run, load, save, snapshot_sources, now
from local_llm_benchmarks import memory_windows as memory

def api(route, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request('http://127.0.0.1:8089'+route, data=data, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=7200) as f: return json.load(f)

def main():
    run=create_run('BFCL f7 Gemma4 template probe', 'bfcl-adapter-validation', {'scope':'synthetic probe, not benchmark score','official_revision':'f7cf7359b7ac615a0b294831c5ba2bc95ee4a000'},run_id='period-004-bfcl-f7-gemma4-template-probe-20261112',period='period-004')
    snapshot_sources(run); manifest=load(run/'manifest.json');server=None
    try:
        with socket.socket() as s: assert s.connect_ex(('127.0.0.1',8089)) != 0, 'port occupied'
        snap=memory.snapshot(os.getpid()); assert snap['available_ram_bytes'] >= 3*1024**3 and snap['gpu_used_mib'] is not None and snap['gpu_used_mib'] <= 7676
        args=load(ROOT/'runs/period-004-gemma-humaneval-prefix-20261112/configs/server-command.json')['args'];args[args.index('--alias')+1]='period4-bfcl-gemma4'
        save(run/'configs/server-command.json',{'args':args});save(run/'configs/preflight.json',snap)
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(run/'manifest.json',manifest)
        with (run/'logs/server.log').open('wb') as log:server=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,cwd=pathlib.Path(args[0]).parent,creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(600):
            if server.poll() is not None: raise RuntimeError('server exited')
            try:
                if api('/health')['status']=='ok': break
            except OSError: pass
            time.sleep(1)
        else: raise TimeoutError('server startup')
        props=api('/props');assert props['total_slots']==1 and props['default_generation_settings']['n_ctx']==65536
        messages=[{'role':'system','content':'Respond with exactly one Python function call.'},{'role':'user','content':'Call add with a=1 and b=2.'}]
        rendered=api('/apply-template',{'messages':messages,'chat_template_kwargs':{'enable_thinking':False}})
        save(run/'raw/rendered-template.json',rendered)
        prompt=rendered.get('prompt','');assert prompt and 'Call add with a=1 and b=2.' in prompt and 'Respond with exactly one Python function call.' in prompt
        os.environ['BFCL_RAW_HTTP_DIR']=str(run/'raw/http')
        from bfcl_f7_gemma4_adapter import Gemma4LlamaChat
        h=Gemma4LlamaChat('period4-bfcl-gemma4',0.001,'local-gemma4',False)
        d={'message':messages,'function':[]};response,seconds=h._query_prompting(d)
        assert response.usage and isinstance(response.choices[0].text,str)
        save(run/'summary.json',{'outcome':'passed','scope':'Synthetic chat template and API transport only; BFCL correctness and multi-turn behavior remain unverified.','response_nonempty':bool(response.choices[0].text),'seconds':seconds})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:
        manifest.update(status='failed',failed_at=now(),error=repr(e));raise
    finally:
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        manifest['server_stopped']=server is None or server.poll() is not None;save(run/'manifest.json',manifest)

if __name__=='__main__':main()
