"""Verify complete multi-turn evidence and run pinned, guarded BFCL scoring."""
import json, os, pathlib, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'benchmarks'))
from local_llm_benchmarks.study import load,save,now,sha

COL=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-20261113'
RUN=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-score-20261113'

def main():
    manifest=load(RUN/'manifest.json')
    try:
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        while True:
            state=load(COL/'manifest.json')['status']
            if state=='complete': break
            if state=='failed': raise RuntimeError('collection failed; no scoring')
            time.sleep(15)
        plan=load(COL/'configs/case-plan.json'); expected=plan['ids']
        assert len(expected)==len(set(expected))==plan['count']==800
        raw_files=sorted((COL/'raw/http').glob('*.json')); raw={}
        for path in raw_files:
            record=load(path); raw.setdefault(record['case_id'],[]).append(record)
        result_files=list((COL/'raw/bfcl-results').rglob('*_result.json'))
        results=[]
        for path in result_files:
            results.extend(json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line.strip())
        by_id={r['id']:r for r in results}
        assert len(by_id)==len(results)==len(expected) and set(by_id)==set(raw)==set(expected)
        for case_id,requests in raw.items():
            result=by_id[case_id]['result']
            assert isinstance(result,list) and all(isinstance(turn,list) for turn in result)
            content=[step for turn in result for step in turn]
            actual=[r['response']['choices'][0]['message']['content'] or '' for r in requests]
            assert content==actual,case_id
        save(RUN/'configs/evidence-verification.json',{
            'source_run':COL.name,'cases':len(expected),'http_responses':len(raw_files),
            'missing':0,'duplicate_case_results':0,
            'raw_sha256':{p.name:sha(p) for p in raw_files},
            'result_sha256':{p.relative_to(COL).as_posix():sha(p) for p in result_files}})
        os.environ.update(LOCAL_SERVER_ENDPOINT='127.0.0.1',LOCAL_SERVER_PORT='8089',
            BFCL_PROJECT_ROOT=str(RUN/'workspace'),BFCL_RAW_HTTP_DIR=str(RUN/'raw/http'),
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING,ModelConfig
        from bfcl_eval.eval_checker import eval_runner
        from bfcl_f7_gemma4_guarded_adapter import GuardedGemma4
        from bfcl_f7_guarded_scoring import install_case_allowlists
        install_case_allowlists(eval_runner)
        model='local-gemma4-f7-prompt'
        MODEL_CONFIG_MAPPING[model]=ModelConfig(model_name='period4-bfcl-gemma4',
            display_name='Gemma4 E4B Q4_K_M local prompt',
            url='https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF',org='local',
            license='see model repository',model_handler=GuardedGemma4,is_fc_model=False)
        eval_runner.main([model],['multi_turn'],str(COL/'raw/bfcl-results'),
            str(RUN/'raw/official-scores'),partial_eval=False)
        save(RUN/'summary.json',{'outcome':'scored','samples':800,
            'scope':'four complete multi-turn categories only; not official overall',
            'source_run':COL.name})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:
        manifest.update(status='failed',failed_at=now(),error=repr(e),
            summary={'outcome':'incomplete','model_failure':False});raise
    finally: save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
