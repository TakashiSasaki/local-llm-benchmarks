"""Verify and score only six completed BFCL cases; no overall score."""
import json,os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'benchmarks'))
from local_llm_benchmarks.study import load,save,now,sha
COL=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-remaining-20261113'
RUN=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-six-score-20261113'

def main():
    manifest=load(RUN/'manifest.json')
    try:
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        prior=load(COL/'manifest.json')
        assert prior['status']=='failed' and prior['summary']['completed_cases']==6
        expected=[f'multi_turn_base_{i}' for i in range(1,7)]
        result_files=list((COL/'raw/bfcl-results').rglob('*_result.json'))
        entries=[]
        for p in result_files:entries.extend(json.loads(line) for line in p.read_text(encoding='utf8').splitlines() if line.strip())
        assert [e['id'] for e in entries]==expected
        raw_files=sorted((COL/'raw/http').glob('*.json')); raw={}
        for p in raw_files:
            item=load(p);raw.setdefault(item['case_id'],[]).append((p,item))
        assert set(raw)==set(expected)|{'multi_turn_base_7'}
        for entry in entries:
            steps=[s for turn in entry['result'] for s in turn]
            actual=[r['response']['choices'][0]['message']['content'] or '' for _,r in raw[entry['id']]]
            assert steps==actual,entry['id']
        save(RUN/'configs/evidence-verification.json',{'source_run':COL.name,
            'case_ids':expected,'incomplete_excluded':'multi_turn_base_7',
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
        eval_runner.main([model],['multi_turn_base'],str(COL/'raw/bfcl-results'),
            str(RUN/'raw/partial-scores'),partial_eval=True)
        save(RUN/'summary.json',{'outcome':'scored','attempted':6,'category_total':200,
            'scope':'six-case partial base category; not comparable to a complete category or overall',
            'source_run':COL.name})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:
        manifest.update(status='failed',failed_at=now(),error=repr(e),
            summary={'outcome':'incomplete','model_failure':False});raise
    finally:save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
