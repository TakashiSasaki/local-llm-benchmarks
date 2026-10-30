"""Verify the completed LFM stage without waiting for the Qwen stage."""
import json,pathlib,sys
run=pathlib.Path(sys.argv[1]);read=lambda p:json.loads(p.read_text(encoding='utf-8'))
r=read(run/'results.json');oldpath=pathlib.Path(r['previous_4096_reference']);oldrun=oldpath.parent;old=read(oldpath);total=0;changes=0
def verify_raw(fname,item):
    raw=read(run/fname);prior=read(oldrun/fname)
    assert {k:v for k,v in raw['request'].items() if k not in ['model','max_tokens']}=={k:v for k,v in prior['request'].items() if k not in ['model','max_tokens']},fname
    assert item['finish_reason'] in ('stop','tool_calls'),fname
    assert item['usage']['prompt_tokens']+raw['request']['max_tokens']<=65536,fname
for key in old['models']:
    m=r['models'][key];assert m['test_server_stopped'];props=read(run/(key+'-props.json'))
    assert props['total_slots']==1 and props['default_generation_settings']['n_ctx']==65536 and props['build_info'].startswith('b11960-')
    for mode in ['off','on']:
        assert [e['task_id'] for e in m['human_eval'][mode]]==r['human_eval_ids']
        before={e['task_id']:e for e in old['models'][key]['human_eval'][mode]}
        for e in m['human_eval'][mode]:
            verify_raw(key+'-'+mode+'-'+e['task_id'].replace('/','_')+'.json',e)
            if e['passed']!=before[e['task_id']]['passed']:
                assert e['passed'] and before[e['task_id']]['finish_reason']=='length';changes+=1
            total+=1
    assert [e['id'] for e in m['bfcl']]==r['bfcl_ids']
    for e in m['bfcl']:
        verify_raw(key+'-bfcl-'+e['id']+'.json',e);total+=1
assert total==480 and changes==20
out={'scope':'Four completed LFM configurations only; not the final six-model validation.','scored_generations':total,'new_correct_humaneval_cases':changes,'all_new_correct_cases_were_previously_output_capped':True,'requests_unchanged_except_model_alias_and_output_limit':True,'context_per_slot':65536,'all_generations_naturally_finished':True,'actual_input_plus_reserved_output_fits_context':True,'all_four_runtime_builds':'b11960','all_four_owned_model_servers_stopped':True}
(run/'lfm3-stage-validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out))
