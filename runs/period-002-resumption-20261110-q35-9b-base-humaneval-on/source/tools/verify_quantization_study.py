"""Independently regrade saved BFCL and inspect fresh HumanEval/Hermes evidence, without inference."""
import argparse,ast,gzip,json,pathlib,random,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.study import ROOT,load,save,sha,validate_run
from local_llm_benchmarks.bfcl import components

def verify(study):
    parent=ROOT/'runs'/study;m=validate_run(parent);assert m['status']=='complete'
    cfg=m['config'];assert cfg['model']['sha256']==cfg['profile']['model_hash']
    verified=load(parent/'configs/model-file-verification.json');assert verified['verified'] and verified['sha256']==cfg['model']['sha256'] and verified['bytes']==cfg['model']['bytes']
    for item in load(ROOT/'publication'/(study+'-redactions.json'))['entries']:assert sha(ROOT/item['path'])==item['public_sha256'],item['path']
    props=load(parent/'configs/server-props.json');assert props['build_info'].startswith('b11960-') and props['model_alias']==cfg['profile']['profile_id'] and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
    cases,_,grade=components();bfcl_count=he_count=0;scores={}
    source=(ROOT/'artifacts/local-llm/hermes/benchmarks/compare_models.py').read_text(encoding='utf-8');node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='unwrap_code');scope={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),'pinned_extractor.py','exec'),scope)
    rows=[json.loads(x) for x in gzip.decompress((ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()];problems=[rows[i] for i in sorted(random.Random(42).sample(range(164),20))]
    for mode in ['off','on']:
        for suite in ['humaneval','bfcl']:
            path=ROOT/'runs'/(study+'-'+suite+'-'+mode);manifest=validate_run(path);assert manifest['status']=='complete'
            assert manifest['config']['model']['sha256']==cfg['model']['sha256'] and manifest['runtime_build']==props['build_info']
            entries=load(path/('summaries/cases.json' if suite=='humaneval' else 'summaries/bfcl-cases.json'));assert len(entries)==(20 if suite=='humaneval' else 80)
            for entry,case in zip(entries,problems if suite=='humaneval' else cases):
                cid=entry.get('id') or entry['task_id'];assert cid==(case['task_id'] if suite=='humaneval' else case['problem']['id'])
                raw=load(path/'raw'/(cid.replace('/','_')+'.json'));response=raw['response'];request=raw['request'];message=response['choices'][0]['message']
                assert request['model']==cfg['profile']['profile_id'] and request['chat_template_kwargs']['enable_thinking']==(mode=='on')
                assert request['max_tokens']==min(64000,65536-raw['estimated_prompt_tokens']-32)
                assert response['usage']==entry['usage'] and response['usage']['total_tokens']<=65536
                assert entry['seconds']==raw['seconds'] and entry['finish_reason']==response['choices'][0]['finish_reason']
                assert entry['reasoning_observed']==bool(message.get('reasoning_content') or message.get('reasoning'))
                if suite=='bfcl':
                    outcome=grade(case,response);assert (entry['passed'],entry['decoded'])==(outcome['passed'],outcome['decoded']);bfcl_count+=1
                else:
                    content=message.get('content') or '';expected=scope['unwrap_code'](content,case['prompt'],case['entry_point']) if content.strip() else ''
                    assert entry['code']==expected
                    if not expected:assert not entry['passed']
                    he_count+=1
            summary=load(path/'summary.json');assert summary['passed']==sum(e['passed'] for e in entries) and summary['attempted']==len(entries)
            assert summary['output_cap_hits']==sum(e['finish_reason']=='length' for e in entries)
            scores[suite+'_'+mode]={'passed':summary['passed'],'attempted':len(entries),'caps':summary['output_cap_hits']}
    hermes=ROOT/'runs'/(study+'-hermes');hm=validate_run(hermes);assert hm['status']=='complete'
    inp=load(hermes/'workspace/input.json');expected={'ticket':inp['ticket'],'count':len(inp['amounts']),'total':sum(inp['amounts']),'terminal_marker':'HERMES35B_TERMINAL_OK'}
    assert expected==load(hermes/'configs/expected.json') and sha(hermes/'workspace/input.json')==load(hermes/'configs/input-sha256.json')['input_sha256']
    hs=load(hermes/'summary.json');tool_export=load(hermes/'raw/session-tools.json');tools=tool_export['tools']
    assert hs['outcome']==('passed' if all(hs['checks'].values()) else 'failed')
    if hs['outcome']=='passed':
        assert load(hermes/'workspace/output.json')==expected
        assert tool_export['session']['model']==cfg['profile']['profile_id'] and tool_export['session']['billing_base_url']=='http://127.0.0.1:8089/v1'
        assert any(t['tool_name']=='read_file' and inp['ticket'] in t['result'].get('content','') for t in tools)
        assert any(t['tool_name']=='terminal' and t['result'].get('exit_code')==0 and t['result'].get('output','').strip()==expected['terminal_marker'] for t in tools)
        assert any(t['tool_name']=='write_file' and t['result'].get('verified') for t in tools)
    return {'passed':True,'study':study,'bfcl_raw_outputs_regraded':bfcl_count,'humaneval_saved_records_checked':he_count,'scores':scores,'hermes_outcome':hs['outcome'],'model_inference_performed':False,'generated_humaneval_code_executed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--report',type=pathlib.Path);a=p.parse_args();v=verify(a.study)
    if a.report:save(a.report,v)
    print(json.dumps(v))
