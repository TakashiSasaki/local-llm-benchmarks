"""Collect pinned upstream BFCL multi-turn categories with a Gemma4 adapter."""
import json, os, pathlib, socket, subprocess, sys, threading, time, urllib.request
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'benchmarks'))
from local_llm_benchmarks.study import create_run,load,save,snapshot_sources,now,sha
from local_llm_benchmarks import memory_windows as memory

def api(route):
    with urllib.request.urlopen('http://127.0.0.1:8089'+route,timeout=5) as f:return json.load(f)

def main():
    run=create_run('BFCL f7 Gemma4 multi turn collection','bfcl',{'official_commit':'f7cf7359b7ac615a0b294831c5ba2bc95ee4a000','categories':'multi_turn','call_guard':'conservative AST allowlist: stops on unsupported syntax without scoring as failure','mode':'prompt','temperature':0.001,'seed':42,'max_output':4096,'thinking':'off requested via GGUF chat template','api_timeout_seconds':7200,'automatic_retries':0,'threads':1,'adapter':'llama.cpp GGUF chat template; adapted from BFCL OSS prompt handler','template_probe':'period-004-bfcl-f7-gemma4-template-probe2-20261112','scope':'all official multi-turn cases; not an overall leaderboard score'},run_id='period-004-bfcl-f7-gemma4-multi-turn-20261113',period='period-004')
    snapshot_sources(run);os.chdir(run/'workspace');manifest=load(run/'manifest.json');server=None;monitor=None;stop=threading.Event();hits=[]
    try:
        os.environ.update(LOCAL_SERVER_ENDPOINT='127.0.0.1',LOCAL_SERVER_PORT='8089',BFCL_PROJECT_ROOT=str(run/'workspace'),BFCL_RAW_HTTP_DIR=str(run/'raw/http'))
        import bfcl_f7_gemma4_adapter as adapter
        from bfcl_f7_gemma4_guarded_adapter import GuardedGemma4
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING,ModelConfig
        from bfcl_eval.model_handler.local_inference.base_oss_handler import OSSHandler
        from bfcl_eval import _llm_response_generation as gen
        from bfcl_eval.model_handler.utils import default_decode_ast_prompting
        assert default_decode_ast_prompting('add(a=1, b=2)') == [{'add':{'a':1,'b':2}}]
        model='local-gemma4-f7-prompt'
        MODEL_CONFIG_MAPPING[model]=ModelConfig(model_name='period4-bfcl-gemma4',display_name='Gemma4 E4B Q4_K_M local prompt',url='https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF',org='local',license='see model repository',model_handler=GuardedGemma4,is_fc_model=False)
        # Upstream's skip-server path still loads a separate Hugging Face tokenizer;
        # the adapter uses the GGUF's actual chat template via llama.cpp instead.
        def attach(self,**kwargs): self.model_path_or_id='period4-bfcl-gemma4'
        def detach(self): pass
        OSSHandler.spin_up_local_server=attach;OSSHandler.shutdown_local_server=detach
        def one(handler,test_case,include_input_log,exclude_state_log):
            adapter.CURRENT_CASE=test_case['id']
            result,metadata=handler.inference(test_case,include_input_log,exclude_state_log)
            return {'id':test_case['id'],'result':result,**metadata}
        gen.multi_threaded_inference=one
        with socket.socket() as s:assert s.connect_ex(('127.0.0.1',8089))!=0,'port occupied'
        snap=memory.snapshot(os.getpid());assert snap['available_ram_bytes']>=3*1024**3 and snap['gpu_used_mib'] is not None and snap['gpu_used_mib']<=7676
        args=load(ROOT/'runs/period-004-gemma-humaneval-prefix-20261112/configs/server-command.json')['args'];args[args.index('--alias')+1]='period4-bfcl-gemma4'
        save(run/'configs/server-command.json',{'args':args});save(run/'configs/preflight.json',snap)
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(run/'manifest.json',manifest)
        with (run/'logs/server.log').open('wb') as f:server=subprocess.Popen(args,cwd=pathlib.Path(args[0]).parent,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        monitor=memory.Monitor(server.pid,run/'logs/memory.jsonl').start()
        def guard():
            low=0
            while not stop.wait(3):
                s=memory.snapshot(server.pid);low=low+1 if s['available_ram_bytes']<3*1024**3 else 0
                if low>=3:hits.append({'reason':'RAM reserve','at':now()});server.terminate();return
        threading.Thread(target=guard,daemon=True).start()
        for _ in range(600):
            if server.poll() is not None:raise RuntimeError('server exited')
            try:
                if api('/health')['status']=='ok':break
            except OSError:pass
            time.sleep(1)
        else:raise TimeoutError('server startup')
        props=api('/props');assert props['total_slots']==1 and props['default_generation_settings']['n_ctx']==65536 and props['build_info'].startswith('b11960-')
        snap=memory.snapshot(server.pid);assert snap['available_ram_bytes']>=3*1024**3 and snap['gpu_used_mib'] is not None and snap['gpu_used_mib']<=7676
        save(run/'configs/admission-memory.json',snap)
        categories,entries=gen.get_involved_test_entries(['multi_turn'],False)
        opts=SimpleNamespace(model=[model],test_category=['multi_turn'],temperature=.001,include_input_log=True,exclude_state_log=False,num_gpus=1,num_threads=1,gpu_memory_utilization=.9,backend='vllm',skip_server_setup=True,local_model_path=None,result_dir=run/'raw/bfcl-results',allow_overwrite=False,run_ids=False)
        cases=gen.collect_test_cases(opts,model,categories,entries)
        assert len(cases)==800 and len({c['id'] for c in cases})==800
        save(run/'configs/case-plan.json',{'categories':categories,'count':len(cases),'ids':[c['id'] for c in cases]})
        gen.generate_results(opts,model,cases)
        save(run/'summary.json',{'outcome':'collected','planned_cases':len(cases),'result_files':[p.relative_to(run).as_posix() for p in (run/'raw/bfcl-results').rglob('*_result.json')],'scope':'multi-turn only; official category scoring pending'})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:manifest.update(status='failed',failed_at=now(),error=repr(e));raise
    finally:
        stop.set()
        if server and server.poll() is None:server.terminate();server.wait(timeout=30)
        if monitor:save(run/'summaries/memory.json',monitor.stop())
        save(run/'configs/cleanup.json',{'server_stopped':server is None or server.poll() is not None,'guard':hits});save(run/'manifest.json',manifest)

if __name__=='__main__':main()
