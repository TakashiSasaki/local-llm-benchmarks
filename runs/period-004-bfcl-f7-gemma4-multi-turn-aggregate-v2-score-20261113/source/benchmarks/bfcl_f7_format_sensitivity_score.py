"""Wait for complete collection, verify raw evidence, run pinned BFCL checker."""
import json, os, pathlib, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.study import ROOT,load,save,now,sha
COL=ROOT/'runs/period-004-bfcl-f7-gemma4-format-sensitivity-20261113'
RUN=ROOT/'runs/period-004-bfcl-f7-gemma4-format-sensitivity-score-20261113'

def main():
    manifest=load(RUN/'manifest.json')
    try:
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        while True:
            collection=load(COL/'manifest.json')
            if collection['status']=='complete':break
            if collection['status']=='failed':raise RuntimeError('Collection failed; no score')
            time.sleep(15)
        plan=load(COL/'configs/case-plan.json'); expected=plan['ids']
        assert len(expected)==len(set(expected))==plan['count']
        raw_files=sorted((COL/'raw/http').glob('*.json'))
        raw={}
        for p in raw_files:
            r=load(p); key=r['case_id'];assert key not in raw;raw[key]=r
        result_files=list((COL/'raw/bfcl-results').rglob('*_result.json'))
        results=[]
        for p in result_files:
            results.extend(json.loads(line) for line in p.read_text(encoding='utf8').splitlines() if line.strip())
        result_by_id={r['id']:r for r in results}
        assert len(result_by_id)==len(results)==len(raw)==len(expected)
        assert set(result_by_id)==set(raw)==set(expected)
        for key,r in raw.items():assert (r['response']['choices'][0]['message']['content'] or '')==result_by_id[key]['result']
        save(RUN/'configs/evidence-verification.json',{'source_run':COL.name,'case_count':len(expected),'unique_ids':len(raw),'missing':0,'duplicates':0,'raw_files':{p.name:sha(p) for p in raw_files},'result_files':{p.relative_to(COL).as_posix():sha(p) for p in result_files}})
        os.environ.update(LOCAL_SERVER_ENDPOINT='127.0.0.1',LOCAL_SERVER_PORT='8089',BFCL_PROJECT_ROOT=str(RUN/'workspace'),BFCL_RAW_HTTP_DIR=str(RUN/'raw/http'))
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING,ModelConfig
        from bfcl_eval.eval_checker import eval_runner
        from bfcl_f7_safe_score_adapter import GuardedScoringGemma4
        model='local-gemma4-f7-prompt'
        MODEL_CONFIG_MAPPING[model]=ModelConfig(model_name='period4-bfcl-gemma4',display_name='Gemma4 E4B Q4_K_M local prompt',url='https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF',org='local',license='see model repository',model_handler=GuardedScoringGemma4,is_fc_model=False)
        eval_runner.main([model],['format_sensitivity'],str(COL/'raw/bfcl-results'),str(RUN/'raw/official-scores'),partial_eval=False)
        score_files=list((RUN/'raw/official-scores').rglob('*'))
        save(RUN/'summary.json',{'outcome':'scored','samples':len(expected),'scope':'non-scoring format-sensitivity only; not official overall score','source_run':COL.name,'files':[p.relative_to(RUN).as_posix() for p in score_files if p.is_file()]})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:manifest.update(status='failed',failed_at=now(),error=repr(e));raise
    finally:save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
