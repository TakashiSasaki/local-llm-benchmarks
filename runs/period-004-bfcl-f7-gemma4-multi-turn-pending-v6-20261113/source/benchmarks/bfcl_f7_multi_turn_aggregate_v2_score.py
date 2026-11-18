"""Verify three BFCL sources and score complete categories plus partial base."""
import json,os,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'benchmarks'))
from local_llm_benchmarks.study import load,save,sha,now
OLD2=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-remaining-20261113'
OLD3=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-pending-20261113'
NEW=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-pending-v2-20261113'
RUN=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v2-score-20261113'

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
        incomplete=['multi_turn_base_0','multi_turn_base_7','multi_turn_base_23']
        assert prior['incomplete_ids']==incomplete
        first=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-20261113'
        first_raw=sorted((first/'raw/http').glob('*.json'))
        assert len(first_raw)==6 and all(prior['raw1_sha256'][p.name]==sha(p) for p in first_raw)
        new_ids=load(NEW/'configs/case-plan.json')['ids']
        assert len(new_ids)==len(set(new_ids))==776
        ids2=[f'multi_turn_base_{i}' for i in range(1,7)]
        ids3=[f'multi_turn_base_{i}' for i in range(8,23)]
        assert not (set(ids2+ids3+incomplete)&set(new_ids))
        combined={};sources={};raw_hashes={}
        specs=((OLD2,ids2,'multi_turn_base_7','raw2_sha256','result2_sha256'),
               (OLD3,ids3,'multi_turn_base_23','raw3_sha256','result3_sha256'),
               (NEW,new_ids,None,None,None))
        for source,expected,extra,raw_key,result_key in specs:
            raw={}
            for p in sorted((source/'raw/http').glob('*.json')):
                item=load(p);raw.setdefault(item['case_id'],[]).append(item)
                raw_hashes[source.name+'/'+p.name]=sha(p)
                if raw_key:assert prior[raw_key][p.name]==sha(p)
            result_dir=source/'raw/bfcl-results';files=list(result_dir.rglob('*_result.json'))
            results=[]
            for p in files:
                if result_key:assert prior[result_key][p.relative_to(source).as_posix()]==sha(p)
                for line in p.read_text(encoding='utf8').splitlines():
                    if line.strip():results.append((p.relative_to(result_dir),json.loads(line)))
            ids=[e['id'] for _,e in results]
            assert len(ids)==len(set(ids))==len(expected) and set(ids)==set(expected)
            assert set(raw)==set(expected)|({extra} if extra else set())
            for rel,e in results:
                steps=[step for turn in e['result'] for step in turn]
                responses=[r['response']['choices'][0]['message']['content'] or '' for r in raw[e['id']]]
                assert steps==responses,e['id']
                assert e['id'] not in sources;sources[e['id']]=source.name
                combined.setdefault(rel,[]).append(e)
        assert len(sources)==797 and sum(k.startswith('multi_turn_base_') for k in sources)==197
        target=RUN/'workspace/combined-results'
        for rel,entries in combined.items():
            p=target/rel;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('x',encoding='utf8') as f:
                for entry in entries:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
        save(RUN/'configs/evidence-verification.json',{'sources':sources,'raw_sha256':raw_hashes,
             'cases':797,'excluded_incomplete':incomplete,
             'result_sha256':{p.relative_to(target).as_posix():sha(p) for p in target.rglob('*_result.json')}})
        os.environ.update(LOCAL_SERVER_ENDPOINT='127.0.0.1',LOCAL_SERVER_PORT='8089',
            BFCL_PROJECT_ROOT=str(RUN/'workspace'),BFCL_RAW_HTTP_DIR=str(RUN/'raw/http'),
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        os.chdir(RUN/'workspace')
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING,ModelConfig
        from bfcl_eval.eval_checker import eval_runner
        from bfcl_f7_gemma4_guarded_adapter_memory_v2 import GuardedGemma4
        from bfcl_f7_guarded_scoring import install_case_allowlists
        from bfcl_f7_guarded_executor_memory_v2 import install_guarded_executor
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
        save(RUN/'summary.json',{'outcome':'scored','attempted':797,
            'scope':'three complete categories; base 197/200 partial; not official overall',
            'source_runs':[OLD2.name,OLD3.name,NEW.name]})
        manifest.update(status='complete',completed_at=now())
    except BaseException as e:
        manifest.update(status='failed',failed_at=now(),error=repr(e),
            summary={'outcome':'incomplete','model_failure':False});raise
    finally:save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
