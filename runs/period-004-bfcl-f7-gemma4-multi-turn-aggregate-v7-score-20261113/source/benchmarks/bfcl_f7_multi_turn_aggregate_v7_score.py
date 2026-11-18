"""Verify saved multi-turn cases and context failures, then score partial BFCL."""
import json,os,pathlib,re,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'benchmarks'))
from local_llm_benchmarks.study import load,save,sha,now
NEW=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-pending-v7-20261113'
RUN=ROOT/'runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v7-score-20261113'
PATTERN=re.compile(r'request \((\d+) tokens\) exceeds the available context size \((\d+) tokens\)')

def main():
    manifest=load(RUN/'manifest.json')
    try:
        manifest.update(status='running',started_at=now(),owner_pid=os.getpid());save(RUN/'manifest.json',manifest)
        while True:
            state=load(NEW/'manifest.json')['status']
            if state=='complete':break
            if state=='failed':raise RuntimeError('pending collection failed; no aggregate score')
            time.sleep(15)
        prior=load(NEW/'configs/prior-evidence.json');plan=load(NEW/'configs/case-plan.json')
        expected=plan['ids'];prior_ids=prior['completed_ids'];incomplete=prior['guard_interrupted_ids']
        assert len(expected)==len(set(expected))==479 and len(prior_ids)==len(set(prior_ids))==314
        assert len(incomplete)==6 and prior['context_failed_ids']==['multi_turn_long_context_120']
        assert not (set(expected)&(set(prior_ids)|set(incomplete)|set(prior['context_failed_ids'])))
        context=load(NEW/'configs/prior-context-failure.json')
        assert context['case_id']=='multi_turn_long_context_120' and context['input_tokens']==70411 and context['context_tokens']==65536
        original=ROOT/'runs'/context['source_run']
        assert sha(original/'logs/server.log')==context['server_log_sha256']
        assert sha(original/'raw/http'/context['last_saved_response'])==context['last_saved_response_sha256']
        sources={};combined={};raw_hashes={};context_failures={}
        for name in prior['prior_runs']+[NEW.name]:
            source=ROOT/'runs'/name;raw={}
            for p in sorted((source/'raw/http').glob('*.json')):
                row=load(p);raw.setdefault(row['case_id'],[]).append(row)
                raw_hashes[name+'/'+p.name]=sha(p)
                if source!=NEW:assert prior['raw_sha256'][name][p.name]==sha(p)
            result_dir=source/'raw/bfcl-results';ids=[]
            for p in result_dir.rglob('*_result.json'):
                if source!=NEW:assert prior['result_sha256'][name][p.relative_to(source).as_posix()]==sha(p)
                for line in p.read_text(encoding='utf8').splitlines():
                    if not line.strip():continue
                    entry=json.loads(line);case=entry['id'];assert case not in sources
                    ids.append(case);sources[case]=name
                    if 'context_limit_failure' in entry:
                        assert source==NEW and isinstance(entry['result'],str)
                        failure=entry['context_limit_failure'];ep=NEW/'raw/context-failures'/failure['evidence']
                        evidence=load(ep);match=PATTERN.search(evidence['response_body'])
                        assert evidence['case_id']==case and evidence['http_status']==400 and match
                        assert int(match.group(1))==evidence['input_tokens']>evidence['context_tokens']==65536
                        assert failure['input_tokens']==evidence['input_tokens'] and failure['retry'] is False
                        context_failures[case]=sha(ep)
                    else:
                        assert isinstance(entry['result'],list) and case in raw
                        steps=[step for turn in entry['result'] for step in turn]
                        responses=[r['response']['choices'][0]['message']['content'] or '' for r in raw[case]]
                        assert steps==responses,case
                    combined.setdefault(p.relative_to(result_dir),[]).append(entry)
            assert len(ids)==len(set(ids))
            if source==NEW:
                assert set(ids)==set(expected) and set(raw)<=set(ids)
                assert set(context_failures)=={p.stem for p in (NEW/'raw/context-failures').glob('*.json')}
            else:assert set(ids)<=set(prior_ids) and set(raw)-set(ids)<=set(incomplete)|set(prior['context_failed_ids'])
        assert set(sources)==set(prior_ids)|set(expected)
        historical={'id':context['case_id'],'result':'Error during inference: input 70411 exceeds context 65536',
                    'context_limit_failure':{'input_tokens':70411,'context_tokens':65536,
                                             'source_run':context['source_run'],'retry':False}}
        rel=pathlib.Path('local-gemma4-f7-prompt/multi_turn/BFCL_v4_multi_turn_long_context_result.json')
        assert rel in combined and context['case_id'] not in sources
        combined[rel].append(historical);sources[context['case_id']]=context['source_run']
        assert len(sources)==794 and sum(k.startswith('multi_turn_base_') for k in sources)==194
        target=RUN/'workspace/combined-results'
        for rel,entries in combined.items():
            path=target/rel;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('x',encoding='utf8') as f:
                for entry in entries:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
        save(RUN/'configs/evidence-verification.json',{'sources':sources,'raw_sha256':raw_hashes,
            'cases_including_context_failures':794,'context_failures':context_failures,
            'historical_context_failure':context,'excluded_guard_interrupted':incomplete,
            'result_sha256':{p.relative_to(target).as_posix():sha(p) for p in target.rglob('*_result.json')}})
        os.environ.update(LOCAL_SERVER_ENDPOINT='127.0.0.1',LOCAL_SERVER_PORT='8089',
            BFCL_PROJECT_ROOT=str(RUN/'workspace'),BFCL_RAW_HTTP_DIR=str(RUN/'raw/http'),
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        os.chdir(RUN/'workspace')
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING,ModelConfig
        from bfcl_eval.eval_checker import eval_runner
        from bfcl_f7_gemma4_guarded_adapter_v5 import GuardedGemma4
        from bfcl_f7_guarded_scoring_v5 import install_case_allowlists
        from bfcl_f7_guarded_executor_v5 import install_guarded_executor
        from bfcl_f7_guarded_decoder_v5 import install_guarded_decoder
        install_guarded_decoder();install_guarded_executor();install_case_allowlists(eval_runner)
        model='local-gemma4-f7-prompt'
        MODEL_CONFIG_MAPPING[model]=ModelConfig(model_name='period4-bfcl-gemma4',
            display_name='Gemma4 E4B Q4_K_M local prompt',url='https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF',
            org='local',license='see model repository',model_handler=GuardedGemma4,is_fc_model=False)
        eval_runner.main([model],['multi_turn_long_context','multi_turn_miss_func','multi_turn_miss_param'],
            str(target),str(RUN/'raw/full-category-scores'),partial_eval=False)
        eval_runner.main([model],['multi_turn_base'],str(target),
            str(RUN/'raw/partial-base-scores'),partial_eval=True)
        save(RUN/'summary.json',{'outcome':'scored','attempted_including_context_failures':794,
            'context_failures':1+len(context_failures),'scope':'three full categories; base 194/200 partial; no overall',
            'source_runs':prior['prior_runs']+[NEW.name]})
        manifest.update(status='complete',completed_at=now())
    except BaseException as exc:
        manifest.update(status='failed',failed_at=now(),error=repr(exc),
            summary={'outcome':'incomplete','model_failure':False});raise
    finally:save(RUN/'manifest.json',manifest)

if __name__=='__main__':main()
