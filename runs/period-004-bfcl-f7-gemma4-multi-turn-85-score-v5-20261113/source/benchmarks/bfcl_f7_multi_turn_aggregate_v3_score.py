"""Verify three BFCL sources and score complete categories plus partial base."""
import json,os,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'benchmarks'))
from local_llm_benchmarks.study import load,save,sha,now
OLD2=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-remaining-20261113'
OLD3=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-pending-20261113'
NEW=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-pending-v3-20261113'
RUN=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v3-score-20261113'

def main():
    manifest=load(RUN/'manifest.json')
    try:
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        while True:
            state=load(NEW/'manifest.json')['status']
            if state=='complete':break
            if state=='failed':raise RuntimeError('pending collection failed; no aggregate score')
            time.sleep(15)
        prior=load(NEW/'configs/prior-evidence.json')
        incomplete=['multi_turn_base_0','multi_turn_base_7','multi_turn_base_23','multi_turn_base_26']
        assert prior['incomplete_ids']==incomplete
        new_ids=load(NEW/'configs/case-plan.json')['ids']
        assert len(new_ids)==len(set(new_ids))==773
        prior_ids=prior['completed_ids'];assert len(prior_ids)==len(set(prior_ids))==23
        assert not (set(prior_ids+incomplete)&set(new_ids))
        combined={};sources={};raw_hashes={}
        old_runs=[ROOT/'runs'/name for name in prior['prior_runs']]
        assert len(old_runs)==4
        for source in old_runs+[NEW]:
            raw={}
            for p in sorted((source/'raw/http').glob('*.json')):
                item=load(p);raw.setdefault(item['case_id'],[]).append(item)
                raw_hashes[source.name+'/'+p.name]=sha(p)
                if source!=NEW:assert prior['raw_sha256'][source.name][p.name]==sha(p)
            result_dir=source/'raw/bfcl-results';files=list(result_dir.rglob('*_result.json'))
            results=[]
            for p in files:
                if source!=NEW:assert prior['result_sha256'][source.name][p.relative_to(source).as_posix()]==sha(p)
                for line in p.read_text(encoding='utf8').splitlines():
                    if line.strip():results.append((p.relative_to(result_dir),json.loads(line)))
            ids=[e['id'] for _,e in results]
            assert len(ids)==len(set(ids))
            if source==NEW:assert set(ids)==set(raw)==set(new_ids)
            else:assert set(ids)<=set(prior_ids) and set(raw)-set(ids)<=set(incomplete)
            for rel,e in results:
                steps=[step for turn in e['result'] for step in turn]
                responses=[r['response']['choices'][0]['message']['content'] or '' for r in raw[e['id']]]
                assert steps==responses,e['id']
                assert e['id'] not in sources;sources[e['id']]=source.name
                combined.setdefault(rel,[]).append(e)
        assert set(sources)==set(prior_ids)|set(new_ids)
        assert len(sources)==796 and sum(k.startswith('multi_turn_base_') for k in sources)==196
        target=RUN/'workspace/combined-results'
        for rel,entries in combined.items():
            p=target/rel;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('x',encoding='utf8') as f:
                for entry in entries:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
        save(RUN/'configs/evidence-verification.json',{'sources':sources,'raw_sha256':raw_hashes,
             'cases':796,'excluded_incomplete':incomplete,
             'result_sha256':{p.relative_to(target).as_posix():sha(p) for p in target.rglob('*_result.json')}})
        os.environ.update(LOCAL_SERVER_ENDPOINT='127.0.0.1',LOCAL_SERVER_PORT='8089',
            BFCL_PROJECT_ROOT=str(RUN/'workspace'),BFCL_RAW_HTTP_DIR=str(RUN/'raw/http'),
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        os.chdir(RUN/'workspace')
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING,ModelConfig
        from bfcl_eval.eval_checker import eval_runner
        from bfcl_f7_gemma4_guarded_adapter_v3 import GuardedGemma4
        from bfcl_f7_guarded_scoring import install_case_allowlists
        from bfcl_f7_guarded_executor_v3 import install_guarded_executor
        install_guarded_executor();install_case_allowlists(eval_runner)
        model='local-gemma4-f7-prompt'
        MODEL_CONFIG_MAPPING[model]=ModelConfig(model_name='period4-bfcl-gemma4',
            display_name='Gemma4 E4B Q4_K_M local prompt',
            url='https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF',org='local',
            license='see model repository',model_handler=GuardedGemma4,is_fc_model=False)
        eval_runner.main([model],['multi_turn_long_context','multi_turn_miss_func','multi_turn_miss_param'],
            str(target),str(RUN/'raw/full-category-scores'),partial_eval=False)
        eval_runner.main([model],['multi_turn_base'],str(target),
            str(RUN/'raw/partial-base-scores'),partial_eval=True)
        save(RUN/'summary.json',{'outcome':'scored','attempted':796,
            'scope':'three complete categories; base 196/200 partial; not official overall',
            'source_runs':prior['prior_runs']+[NEW.name]})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:
        manifest.update(status='failed',failed_at=now(),error=repr(e),
            summary={'outcome':'incomplete','model_failure':False});raise
    finally:save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
