"""Check saved paired BFCL payloads, raw outputs, scores and provenance without inference."""
import copy, hashlib, json, socket, sys, zipfile
from pathlib import Path
ROOT=Path(r'C:\LocalLLM');BF=ROOT/'hermes/benchmarks/bfcl';OUT=Path(sys.argv[1])
ns={'__file__':str(BF/'run_comparison.py')};src=(BF/'run_comparison.py').read_text(encoding='utf-8')
exec(compile(src[:src.index('selfcheck=[]')],'pinned_bfcl_adapter.py','exec'),ns)
r=json.loads((OUT/'results.json').read_text(encoding='utf-8'));summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
assert 'error' not in r and r['test_server_stopped'] and r['warmup_mode_verified']
assert len(r['off'])==len(r['on'])==80
assert all(r['settings_unchanged'].values()) and all(r['sources_unchanged'].values())
assert ns['HASHES']==r['dataset_hashes']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for p,h in {**r['original_hashes'],**r['source_hashes']}.items():assert digest(Path(p))==h,p
props=json.loads((OUT/'props.json').read_text(encoding='utf-8'))
assert props['build_info']==r['runtime'] and props['default_generation_settings']['n_ctx']==65536 and props['total_slots']==1
assert props['model_path']==str(ROOT/r['profile']['model'])
case_audit=[]
for c,a,b in zip(ns['SELECTED'],r['off'],r['on']):
    cid=c['problem']['id'];assert a['id']==b['id']==cid
    old=json.loads((Path(r['baseline_directory'])/(r.get('model_key','qwen-large')+'-bfcl-'+cid+'.json')).read_text(encoding='utf-8'))
    new=json.loads((OUT/('on-'+cid+'.json')).read_text(encoding='utf-8'))
    expected=copy.deepcopy(old['request']);expected['chat_template_kwargs']['enable_thinking']=True
    expected['model']=r['profile']['profile_id']
    assert old['request']['model']==expected['model'] or r.get('model_key')=='lfm'
    assert new['request']==expected
    assert new['request']['max_tokens']==64000
    for mode,raw,item in [('off',old,a),('on',new,b)]:
        response=raw['response'];msg=response['choices'][0]['message'];decoded=[];err=None
        try:
            for call in msg.get('tool_calls') or []:
                args=json.loads(call['function']['arguments'])
                if not isinstance(args,dict):raise ValueError('Non-object arguments')
                decoded.append({call['function']['name']:args})
            grade=ns['check'](c,decoded)
        except (ValueError,KeyError,TypeError) as exc:err=str(exc);grade={'valid':False}
        assert grade['valid']==item['passed'] and decoded==item['decoded']
        assert bool(msg.get('reasoning_content') or msg.get('reasoning'))==item['reasoning_observed']
        assert item['finish_reason']==response['choices'][0]['finish_reason']
        assert item['usage']==response.get('usage') and item['timings']==response.get('timings')
        assert response['_benchmark_requested_output_tokens']==64000
        usage=response.get('usage',{});total=usage.get('total_tokens',0)
        assert total<=65536
        case_audit.append({'id':cid,'mode':mode,'passed':grade['valid'],'reasoning':item['reasoning_observed'],'finish_reason':item['finish_reason'],'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),'total_tokens':total,'malformed':err is not None})
for mode in ['off','on']:
    entries=[x for x in case_audit if x['mode']==mode]
    assert summary[mode]['passed']==sum(x['passed'] for x in entries)
    assert summary[mode]['output_cap_hits']==sum(x['finish_reason']=='length' for x in entries)
    for cat in ns['CATEGORIES']:
        selected=[x for x in r[mode] if x['category']==cat]
        assert len(selected)==20 and summary['categories'][cat][mode]['passed']==sum(x['passed'] for x in selected)
with zipfile.ZipFile(OUT/'sources.zip') as z:assert z.testzip() is None
try:conn=socket.create_connection(('127.0.0.1',8089),timeout=1)
except OSError:closed=True
else:conn.close();closed=False
assert closed
audit={'passed':True,'new_on_generations':80,'reused_off_responses':80,'raw_responses_regraded':160,'payload_differences':(['chat_template_kwargs.enable_thinking','model alias for separate LFM2.5 ON/OFF server phases'] if r.get('model_key')=='lfm' else ['chat_template_kwargs.enable_thinking']),'mode_control':('LFM2.5 OFF CLI budget 0 / ON -1; native flag ignored by template' if r.get('model_key')=='lfm' else 'Native enable_thinking false / true; CLI budget -1'),'same_context_runtime_model_placement_data':True,'original_hashes_unchanged':True,'port_closed':True,'maximum_actual_total_tokens':max(x['total_tokens'] for x in case_audit),'maximum_actual_prompt_tokens':max(x['prompt_tokens'] for x in case_audit),'on_reasoning_cases':sum(x['reasoning'] for x in case_audit if x['mode']=='on'),'off_reasoning_cases':sum(x['reasoning'] for x in case_audit if x['mode']=='off'),'cases':case_audit}
(OUT/'independent-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k!='cases'}))
