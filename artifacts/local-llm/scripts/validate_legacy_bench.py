"""Validate the added model runs and their compatibility with the saved suite."""
import ast,gzip,hashlib,json,pathlib,re,socket,sys,zipfile
root=pathlib.Path(r'C:\LocalLLM');run=pathlib.Path(sys.argv[1]);read=lambda p:json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
digest=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
r=read(run/'results.json');s=read(run/'summary.json');refpath=pathlib.Path(r['reference_64k']);ref=read(refpath)
assert 'error' not in r and set(r['models'])=={'lfm','glm'} and r['reference_unchanged']
assert digest(refpath)==r['reference_64k_sha256']==s['reference_sha256']
assert read(refpath.parent/'validation.json')['completed_cases']==720
assert digest(root/'scripts/benchmark_legacy_models.py')==r['runner_sha256']
for rev in r['runner_revisions']:assert digest(run/rev['source'])==rev['sha256']
assert r['runner_revisions'][-1]['sha256']==r['runner_sha256']
assert r['human_eval_ids']==ref['human_eval_ids'] and r['bfcl_ids']==ref['bfcl_ids'] and r['bfcl_data_hashes']==ref['bfcl_data_hashes']
h=read(r['human_eval_reference']);b=read(r['bfcl_reference'])
assert digest(root/'hermes/benchmarks/HumanEval.jsonl.gz')==r['dataset_sha256']==ref['dataset_sha256']
grader_source=(root/'hermes/benchmarks/compare_models.py').read_text(encoding='utf-8')
assert hashlib.sha256(grader_source.encode()).hexdigest()==h['grader_source_sha256']
node=next(n for n in ast.parse(grader_source).body if isinstance(n,ast.FunctionDef) and n.name=='unwrap_code')
normalizer={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),'unchanged_normalizer_check.py','exec'),normalizer)
problems={p['task_id']:p for p in map(json.loads,gzip.decompress((root/'hermes/benchmarks/HumanEval.jsonl.gz').read_bytes()).decode().splitlines())}
assert digest(root/'hermes/benchmarks/grade_worker.py')==h['worker_sha256']
for name,sha in b['code_hashes'].items():assert digest(root/'hermes/benchmarks/bfcl'/name.replace(chr(92),'/'))==sha
assert all(r['settings_unchanged'].values()) and all(digest(p)==sha for p,sha in r['original_hashes'].items())
checks=read(run/'selfchecks.json');assert len(checks['humaneval'])==20 and all(x['passed'] for x in checks['humaneval'])
assert len(checks['bfcl'])==80 and all(x['golden'] and x['negative_rejected'] for x in checks['bfcl'])
count=0;cap_hits=0;max_input=0;max_total=0;caps=[];reasoning={};profiles=[]
for key,m in r['models'].items():
    assert m['test_server_stopped']
    row=next(x for x in s['models'] if x['key']==key);assert row['origin']=='new'
    for mode in ['off','on']:
        profile=m['profiles'][mode];args=profile['server_args'];props=read(run/m['props_paths'][mode]);profiles.append(profile)
        assert profile['runtime_build']=='b11960' and props['build_info']==m['runtime'] and m['runtime'].startswith('b11960-')
        assert props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
        assert props['model_alias']==profile['profile_id'] and props['model_path']==str(root/profile['model'])
        assert args[args.index('-c')+1]=='65536' and args[args.index('-n')+1]=='64000'
        assert args[args.index('--reasoning-format')+1]=='deepseek'
        assert args[args.index('--reasoning-budget')+1]==('0' if key=='lfm' and mode=='off' else '-1')
        base=read(root/'profiles'/(key+'.json'));assert profile['model_hash']==base['model_hash'] and profile['model']==base['model']
        for arg in ['--n-cpu-moe','-t','-tb','-ctk','-ctv','-b','-ub']:
            assert args[args.index(arg)+1]==base['server_args'][base['server_args'].index(arg)+1]
        assert m['warmups'][mode]['reasoning_observed']==(mode=='on')
        es=m['human_eval'][mode];assert len(es)==20 and [e['task_id'] for e in es]==r['human_eval_ids']
        assert sum(e['passed'] for e in es)==row['human_eval'][mode]['passed']
        reasoning[key+'-'+mode]=sum(e['reasoning_observed'] for e in es)
        for e in es:
            suffix=mode+'-'+e['task_id'].replace('/','_')+'.json';raw=read(run/(key+'-'+suffix));control=read(refpath.parent/('lfm3-'+suffix))
            req=raw['request'];resp=raw['response']
            problem=problems[e['task_id']]
            assert e['code']==(normalizer['unwrap_code'](e['content'],problem['prompt'],problem['entry_point']) if e['content'].strip() else '')
            assert req['model']==profile['profile_id'] and req['chat_template_kwargs']['enable_thinking']==(mode=='on')
            assert {k:v for k,v in req.items() if k not in ['model','max_tokens']}=={k:v for k,v in control['request'].items() if k not in ['model','max_tokens']}
            cap=req['max_tokens'];assert cap==resp['_benchmark_requested_output_tokens']==min(64000,65536-resp['_benchmark_estimated_prompt_tokens']-32)
            assert resp['usage']==e['usage'] and e['finish_reason']==resp['choices'][0]['finish_reason']
            assert e['usage']['prompt_tokens']+cap<=65536
            caps.append(cap);count+=1;cap_hits+=e['finish_reason']=='length';max_input=max(max_input,e['usage']['prompt_tokens']);max_total=max(max_total,e['usage']['total_tokens'])
    if key=='lfm':assert m['native_flag_renders_identical_prompts'] and not m['template_has_enable_thinking']
    else:assert m['template_has_enable_thinking']
    es=m['bfcl'];assert len(es)==80 and [e['id'] for e in es]==r['bfcl_ids']
    assert sum(e['passed'] for e in es)==row['bfcl']['passed']
    reasoning[key+'-bfcl']=sum(e['reasoning_observed'] for e in es)
    for e in es:
        raw=read(run/(key+'-bfcl-'+e['id']+'.json'));control=read(refpath.parent/('lfm3-bfcl-'+e['id']+'.json'));req=raw['request'];resp=raw['response']
        assert req['model']==m['profiles']['off']['profile_id']
        assert {k:v for k,v in req.items() if k not in ['model','max_tokens']}=={k:v for k,v in control['request'].items() if k not in ['model','max_tokens']}
        cap=req['max_tokens'];assert cap==resp['_benchmark_requested_output_tokens']==min(64000,65536-resp['_benchmark_estimated_prompt_tokens']-32)
        assert resp['usage']==e['usage'] and e['finish_reason']==resp['choices'][0]['finish_reason'] and e['usage']['prompt_tokens']+cap<=65536
        caps.append(cap);count+=1;cap_hits+=e['finish_reason']=='length';max_input=max(max_input,e['usage']['prompt_tokens']);max_total=max(max_total,e['usage']['total_tokens'])
assert count==240 and len(s['models'])==8 and s['new_scored_generations']==240 and s['reused_scored_generations']==720
audit=read(run/'grader-sensitivity/results.json');old_audit=read(refpath.parent/'grader-sensitivity/results.json')
assert audit['original_worker_sha256']==old_audit['original_worker_sha256'] and audit['secondary_worker_sha256']==old_audit['secondary_worker_sha256']
assert all(e['passed'] for e in audit['canonical'])
for key,modes in audit['models'].items():
    for mode,entry in modes.items():assert entry['original_passed']==sum(e['passed'] for e in r['models'][key]['human_eval'][mode])
assert not (root/'server-state.json').exists() and not (root/'hermes/server-state.json').exists()
with socket.socket() as sock:sock.settimeout(2);assert sock.connect_ex(('127.0.0.1',8089))!=0
out={'new_scored_cases':count,'reused_scored_cases':720,'compared_configurations':8,'same_questions_graders_and_request_fields':True,'served_runtime':'b11960','context_per_slot':65536,'output_cap_range':[min(caps),max(caps)],'maximum_actual_input_tokens':max_input,'maximum_actual_total_tokens':max_total,'output_cap_hits':cap_hits,'reasoning_observed':reasoning,'lfm_off_control':'CLI reasoning budget 0; native flag renders identical prompts','glm_off_control':'Native template flag false; CLI reasoning budget -1','runner_revisions_verified':len(r['runner_revisions']),'original_settings_unchanged':True,'reference_results_unchanged':True,'supplemental_worker_matches_reference':True,'task_owned_servers_stopped':True,'endpoint_closed':True,'summary_matches_raw':True}
save_path=run/'validation.json';save_path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(run/'sources.zip','a',zipfile.ZIP_DEFLATED) as z:
    for name in ['report_legacy_models.py','validate_legacy_bench.py','audit_legacy_grading.py']:z.write(root/'scripts'/name,'scripts/'+name)
    for revision in r['runner_revisions']:z.write(run/revision['source'],'runner-revisions/'+revision['source'])
    z.writestr('runner-revisions/metadata.json',json.dumps({'revisions':r['runner_revisions'],'interruption_history':r['interruption_history'],'reference_source':r['reference_64k'],'reference_sha256':r['reference_64k_sha256']},ensure_ascii=False,indent=2))
    for key in ['lfm','glm']:
        metadata=run/(key+'-model-metadata.json')
        if metadata.exists():z.write(metadata,metadata.name)
print(json.dumps(out,ensure_ascii=False))
