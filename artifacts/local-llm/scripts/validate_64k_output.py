"""Validate a completed run against saved requests and original benchmark evidence."""
import gzip,hashlib,json,pathlib,sys,zipfile
run=pathlib.Path(sys.argv[1]); root=pathlib.Path(r'C:\LocalLLM')
read=lambda p:json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
digest=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
r=read(run/'results.json'); h=read(r['human_eval_reference']); b=read(r['bfcl_reference']); s=read(run/'summary.json')
assert 'error' not in r and len(r['models'])==6
for revision in r['runner_revisions']:
    assert digest(run/revision['source'])==revision['sha256']
assert digest(root/'scripts/benchmark_64k_output.py')==r['runner_revisions'][-1]['sha256']
assert r['human_eval_ids']==h['task_ids'] and r['bfcl_ids']==b['selected_ids'] and r['bfcl_data_hashes']==b['data_hashes']
assert digest(root/'hermes/benchmarks/HumanEval.jsonl.gz')==r['dataset_sha256']==h['dataset_sha256']
problems={p['task_id']:p for p in map(json.loads,gzip.decompress((root/'hermes/benchmarks/HumanEval.jsonl.gz').read_bytes()).decode().splitlines())}
bf_cases={c['problem']['id']:c['problem'] for c in read(run/'selected-bfcl.json')}
system='Implement the requested Python function. Return only a complete Python module with the specified signature and required imports. Do not include explanations, markdown, or tests.'
source=(root/'hermes/benchmarks/compare_models.py').read_text(encoding='utf-8')
assert hashlib.sha256(source.encode()).hexdigest()==h['grader_source_sha256']
assert digest(root/'hermes/benchmarks/grade_worker.py')==h['worker_sha256']
for p,sha in b['code_hashes'].items():
    assert digest(root/'hermes/benchmarks/bfcl'/p.replace(chr(92),'/'))==sha, p
assert all(r['settings_unchanged'].values())
assert all(digest(p)==sha for p,sha in r['original_hashes'].items())
total=0; on=0; off=0; maximum=0; caphits=0; maxprompt=0; requested=[]
for key in r['protocol']['order']:
    m=r['models'][key]; profile=m['profile']; args=profile['server_args']
    assert m['test_server_stopped'] and profile['runtime_build']=='b11960'
    assert args[args.index('-c')+1]=='65536' and args[args.index('-np')+1]=='1'
    assert args[args.index('-n')+1]=='64000' and args[args.index('--reasoning-budget')+1]=='-1'
    assert args[args.index('--reasoning-format')+1]=='deepseek'
    props=read(run/(key+'-props.json'))
    assert props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
    assert props['build_info']==m['runtime'] and m['runtime'].startswith('b11960-')
    assert props['model_alias']==profile['profile_id'] and props['model_path']==str(root/profile['model'])
    row=next(x for x in s['models'] if x['key']==key)
    for mode,entries in m['human_eval'].items():
        assert len(entries)==20 and [x['task_id'] for x in entries]==h['task_ids']
        assert sum(x['passed'] for x in entries)==row['human_eval'][mode]['passed']
        for item in entries:
            raw=read(run/(key+'-'+mode+'-'+item['task_id'].replace('/','_')+'.json'))
            req=raw['request']; resp=raw['response']
            assert req['model']==profile['profile_id']
            assert req['chat_template_kwargs']['enable_thinking']==(mode=='on')
            for setting in ['temperature','top_p','top_k','min_p','repeat_penalty','presence_penalty','seed','cache_prompt']:
                assert req[setting]==h['protocol'][setting], (key,mode,setting)
            assert req['messages']==[{'role':'system','content':system},{'role':'user','content':problems[item['task_id']]['prompt']}]
            assert item['usage']==resp['usage'] and item['finish_reason']==resp['choices'][0]['finish_reason']
            if mode=='on':on+=bool(item['reasoning_observed'])
            else:off+=bool(item['reasoning_observed'])
            n=resp['_benchmark_estimated_prompt_tokens']; cap=resp['_benchmark_requested_output_tokens']
            assert req['max_tokens']==cap==min(64000,65536-n-32)
            assert item['usage']['prompt_tokens']+cap<=65536
            maximum=max(maximum,item['usage']['total_tokens']);maxprompt=max(maxprompt,item['usage']['prompt_tokens'])
            caphits+=item['finish_reason']=='length';requested.append(cap);total+=1
    assert len(m['bfcl'])==80 and [x['id'] for x in m['bfcl']]==b['selected_ids']
    assert sum(x['passed'] for x in m['bfcl'])==row['bfcl']['passed']
    for item in m['bfcl']:
        raw=read(run/(key+'-bfcl-'+item['id']+'.json'));req=raw['request'];resp=raw['response']
        assert req['model']==profile['profile_id']
        assert req['chat_template_kwargs']['enable_thinking'] is False
        for setting in ['temperature','seed','top_p','top_k','min_p','repeat_penalty','tool_choice','parallel_tool_calls']:
            assert req[setting]==b['protocol'][setting], (key,setting)
        assert req['messages']==bf_cases[item['id']]['question'][0] and req['cache_prompt'] is False
        assert item['usage']==resp['usage']
        n=resp['_benchmark_estimated_prompt_tokens'];cap=resp['_benchmark_requested_output_tokens']
        assert req['max_tokens']==cap==min(64000,65536-n-32)
        assert item['usage']['prompt_tokens']+cap<=65536
        maximum=max(maximum,item['usage']['total_tokens']);maxprompt=max(maxprompt,item['usage']['prompt_tokens'])
        caphits+=item['finish_reason']=='length';requested.append(cap);total+=1
assert total==720
assert not (root/'server-state.json').exists()
assert not (root/'hermes/server-state.json').exists()
import socket
with socket.socket() as sock:
    sock.settimeout(2); assert sock.connect_ex(('127.0.0.1',8089))!=0
out={'completed_cases':total,'models':6,'same_selected_questions':True,'same_original_graders':True,'same_sampling_and_messages_protocol':True,'runner_revisions_verified':len(r['runner_revisions']),'context_per_slot':65536,'requested_output_cap_range':[min(requested),max(requested)],'maximum_actual_prompt_tokens':maxprompt,'maximum_actual_total_tokens':maximum,'output_cap_hits':caphits,'observed_reasoning_on':on,'observed_reasoning_off':off,'all_original_settings_unchanged':True,'test_servers_stopped':True,'endpoint_closed':True,'summary_matches_raw':True,'reasoning_format':'explicit --reasoning-format deepseek','reasoning_budget':-1}
(run/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(run/'sources.zip','a',zipfile.ZIP_DEFLATED) as z:
    for p in ['validate_64k_output.py','validate_lfm3_stage.py','report_64k_output.py','audit_64k_grading.py']:
        z.write(root/'scripts'/p,'scripts/'+p)
    for revision in r['runner_revisions']:
        z.write(run/revision['source'],'runner-revisions/'+revision['source'])
    z.writestr('runner-revisions/metadata.json',json.dumps({'revisions':r['runner_revisions'],'interruption_history':r['interruption_history']},ensure_ascii=False,indent=2))
    for key,m in r['models'].items():
        base=root/'hermes/profiles'/(key.removeprefix('qwen-')+'.json') if key.startswith('qwen-') else root/'profiles'/(key+'.json')
        z.write(base,str(base.relative_to(root)))
        z.writestr('measured-profiles/'+key+'.json',json.dumps(m['profile'],ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False))
