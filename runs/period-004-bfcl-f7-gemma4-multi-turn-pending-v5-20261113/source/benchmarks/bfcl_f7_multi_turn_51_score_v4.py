"""Verify 51 completed prior BFCL cases and score only that subset."""
import json,os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'benchmarks'))
from local_llm_benchmarks.study import load,save,sha,now
NEW=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-pending-v4-20261113'
RUN=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-51-score-v4-20261113'

def main():
    manifest=load(RUN/'manifest.json')
    try:
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        prior=load(NEW/'configs/prior-evidence.json')
        expected=prior['completed_ids'];incomplete=prior['incomplete_ids']
        assert len(expected)==len(set(expected))==51 and len(incomplete)==5
        combined={};sources={};raw_hashes={}
        for name in prior['prior_runs']:
            source=ROOT/'runs'/name;raw={}
            for p in sorted((source/'raw/http').glob('*.json')):
                item=load(p);raw.setdefault(item['case_id'],[]).append(item)
                raw_hashes[name+'/'+p.name]=sha(p);assert prior['raw_sha256'][name][p.name]==sha(p)
            result_dir=source/'raw/bfcl-results'
            for p in result_dir.rglob('*_result.json'):
                assert prior['result_sha256'][name][p.relative_to(source).as_posix()]==sha(p)
                for line in p.read_text(encoding='utf8').splitlines():
                    if not line.strip():continue
                    e=json.loads(line);case=e['id'];assert case in expected and case not in sources
                    steps=[step for turn in e['result'] for step in turn]
                    responses=[r['response']['choices'][0]['message']['content'] or '' for r in raw[case]]
                    assert steps==responses,case
                    sources[case]=name;combined.setdefault(p.relative_to(result_dir),[]).append(e)
            assert set(raw)-set(sources)<=set(incomplete)
        assert set(sources)==set(expected) and not (set(sources)&set(incomplete))
        target=RUN/'workspace/combined-results'
        for rel,entries in combined.items():
            p=target/rel;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('x',encoding='utf8') as f:
                for entry in entries:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
        save(RUN/'configs/evidence-verification.json',{'sources':sources,'raw_sha256':raw_hashes,
             'cases':51,'excluded_incomplete':incomplete,
             'result_sha256':{p.relative_to(target).as_posix():sha(p) for p in target.rglob('*_result.json')}})
        os.environ.update(LOCAL_SERVER_ENDPOINT='127.0.0.1',LOCAL_SERVER_PORT='8089',
            BFCL_PROJECT_ROOT=str(RUN/'workspace'),BFCL_RAW_HTTP_DIR=str(RUN/'raw/http'),
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        os.chdir(RUN/'workspace')
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING,ModelConfig
        from bfcl_eval.eval_checker import eval_runner
        from bfcl_f7_gemma4_guarded_adapter_v4 import GuardedGemma4
        from bfcl_f7_guarded_scoring_v4 import install_case_allowlists
        from bfcl_f7_guarded_executor_v4 import install_guarded_executor
        install_guarded_executor();install_case_allowlists(eval_runner)
        model='local-gemma4-f7-prompt'
        MODEL_CONFIG_MAPPING[model]=ModelConfig(model_name='period4-bfcl-gemma4',
            display_name='Gemma4 E4B Q4_K_M local prompt',
            url='https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF',org='local',
            license='see model repository',model_handler=GuardedGemma4,is_fc_model=False)
        eval_runner.main([model],['multi_turn_base'],str(target),
            str(RUN/'raw/partial-base-scores'),partial_eval=True)
        save(RUN/'summary.json',{'outcome':'scored','attempted':51,'category_total':200,
            'scope':'51-case partial base; not comparable to complete category or overall',
            'source_runs':prior['prior_runs']})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:
        manifest.update(status='failed',failed_at=now(),error=repr(e),
            summary={'outcome':'incomplete','model_failure':False});raise
    finally:save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
