"""Normalize existing comparisons without merging placements, retries or grader policies."""
import hashlib,json,pathlib
from .study import ROOT,load

BASE='reports/20261031-empero-qwen38-iq3m-64k/matrix-data.json'
EARLY='artifacts/local-llm/runs/bench64k-output-20261030-141002/results.json'
LEGACY='artifacts/local-llm/runs/legacy-models-64k-20261030-180109/results.json'
HISTORICAL=[
 'artifacts/local-llm/hermes/benchmarks/comparison-20261029-140654/results.json',
 'artifacts/local-llm/hermes/benchmarks/comparison-20261029-141429/results.json',
 'artifacts/local-llm/hermes/benchmarks/thinking-comparison-20261029-173548/results.json',
 'artifacts/local-llm/hermes/benchmarks/thinking-comparison-20261029-174343/results.json',
 'artifacts/local-llm/hermes/benchmarks/bfcl/comparison-20261029-142528/results.json',
 'artifacts/local-llm/runs/lfm3-bench-20261030-132439/results.json']
KEYS=['bfcl_off','bfcl_on','he_off','he_on']

def arg(args,name,default=None):return args[args.index(name)+1] if name in args else default

def reference(base,value):
    path=(ROOT/base).parent.joinpath(value).resolve();assert path.is_relative_to(ROOT)
    assert path.exists(),str(path);return path.relative_to(ROOT).as_posix()

def record(entry,raw,case_id,category):
    r=load(ROOT/raw);response=r.get('response',{});choice=(response.get('choices') or [{}])[0];message=choice.get('message',{});t=response.get('timings',{})
    grade=entry.get('grade',{});error=grade.get('error_type') if isinstance(grade,dict) else None
    return {'id':case_id,'category':category,'passed':bool(entry['passed']),'seconds':entry.get('seconds',r.get('seconds')),'finish_reason':entry.get('finish_reason',choice.get('finish_reason')),'reasoning_observed':entry.get('reasoning_observed'),'completion_tokens':(response.get('usage') or {}).get('completion_tokens'),'decode_tokens':t.get('predicted_n'),'decode_ms':t.get('predicted_ms'),'parsed_tool_calls':len(message.get('tool_calls') or []) if 'choices' in response else None,'empty_final':not bool(message.get('content') or message.get('tool_calls')) if 'choices' in response else None,'http_status':r.get('http_status',200),'error_type':error or entry.get('status'),'raw':raw,'request_max_tokens':r.get('request',{}).get('max_tokens')}

def condition(records,expected,status,evidence,error=None):
    complete=status=='complete' and len(records)==expected
    if status=='complete' and not complete:status='partial'
    known=[r for r in records if r['decode_tokens'] is not None and r['decode_ms']]
    return {'status':'complete' if complete else status,'complete':complete,'saved':len(records),'expected':expected,'passed_saved':sum(r['passed'] for r in records),'score':sum(r['passed'] for r in records) if complete else None,'seconds_saved':sum(r['seconds'] or 0 for r in records),'completion_tokens_known':sum(r['completion_tokens'] or 0 for r in records),'unknown_statistics':sum(r['completion_tokens'] is None for r in records),'caps_known':sum(r['finish_reason']=='length' for r in records),'reasoning_observed_known':sum(r['reasoning_observed'] is True for r in records),'parser_errors':sum(r['http_status']==500 for r in records),'empty_final_known':sum(r['empty_final'] is True for r in records),'benchmark_decode_tok_s':sum(r['decode_tokens'] for r in known)/(sum(r['decode_ms'] for r in known)/1000) if known else None,'decode_statistics_cases':len(known),'evidence':evidence,'error':error,'cases':records}

def sampler(records):
    """Expose actual request controls, rather than assuming every suite uses the profile sampler."""
    fields=['temperature','top_p','top_k','min_p','repeat_penalty','presence_penalty','seed','max_tokens','chat_template_kwargs','tool_choice','parallel_tool_calls']
    variants={}
    for item in records:
        request=load(ROOT/item['raw']).get('request',{})
        selected={k:request[k] for k in fields if k in request}
        variants[json.dumps(selected,sort_keys=True)]=selected
    return list(variants.values())

def metadata(profile):
    args=profile['server_args'];mtp=profile.get('mtp') or ('on' if arg(args,'--spec-type')=='draft-mtp' else 'off')
    return {'runtime':profile.get('runtime_build'),'context':int(arg(args,'-c',profile.get('context_tokens',0))),'max_output':profile.get('max_tokens',64000),'kv_k':arg(args,'-ctk'),'kv_v':arg(args,'-ctv'),'threads':arg(args,'-t'),'batch_threads':arg(args,'-tb'),'ngl':arg(args,'-ngl'),'cpu_moe_layers':arg(args,'--n-cpu-moe'),'load_mode':arg(args,'--load-mode','default (未指定)'),'mtp':mtp,'mtp_control':'explicit CLI' if '--spec-type' in args else 'saved props: none; CLI default','model_hash':profile.get('model_hash'),'profile':profile}

def collect(root=ROOT):
    assert root==ROOT,'This report reads the declared repository evidence root'
    sources={}
    def read(rel):
        p=ROOT/rel;sources[rel]=hashlib.sha256(p.read_bytes()).hexdigest();return load(p)
    base=read(BASE);early=read(EARLY);legacy=read(LEGACY);rows=[]
    definitions={}
    period=ROOT/'experiments/period-001'
    definitions_root=period/'recipe/configs/models' if (period/'recipe/configs/models').exists() else ROOT/'configs/models'
    for p in sorted(definitions_root.glob('*.json')):
        rel=p.relative_to(ROOT).as_posix();v=read(rel);definitions[(v['model'],v['quantization'])]=(v,rel)
    for m in base['models']:
        key=m['key'];entry=None
        if key in early['models']:
            entry=early['models'][key];profile=entry['profile'];props=read(str(pathlib.PurePosixPath(EARLY).parent/(key+'-props.json')))
        elif key in legacy['models']:
            entry=legacy['models'][key];profile=entry['profile'];props=read(str(pathlib.PurePosixPath(LEGACY).parent/entry['props_paths']['off']))
        else:
            parent='20261030-qwen36-iq3m-64k' if key=='qwen-large-iq3m' else key
            profile=read('runs/'+parent+'/manifest.json')['config']['profile'];props=read('runs/'+parent+'/configs/server-props.json')
        assert props['default_generation_settings']['params']['speculative.types']=='none'
        row={'id':'baseline-'+key,'model':m['name'],'quantization':m['quant'],'kind':'quality','origin':'既存64K統合表示（回答は元run参照）','state':'complete','placement':m['placement'],'mode_control':m['mode_note'],'evidence':reference(BASE,m['source_report']),'fixed_speed':None,'memory':{'peak_gpu_mib':m.get('on_memory',{}).get('peak_system_gpu_mib'),'minimum_ram_gib':m.get('on_memory',{}).get('minimum_available_ram_gib'),'scope':'BFCL思考ONの標本'},'conditions':{},**metadata(profile)}
        row['runtime']=props.get('build_info',row['runtime']);row['mtp']='off'
        if row['placement']=='プロファイル参照':row['placement']='GPU '+str(row['ngl'])+'指定 / CPU MoE指定なし'
        if key not in early['models'] and key not in legacy['models']:row['evidence']='reports/'+parent+'/index.html'
        for suite in ['bfcl','he']:
            for mode in ['off','on']:
                metric=m['metrics'][suite+'_'+mode];records=[]
                for e in m['cases'][suite]:records.append(record(e[mode],reference(BASE,e[mode+'_raw']),e['id'],e.get('category',suite)))
                assert len(records)==metric['attempted'] and sum(r['passed'] for r in records)==metric['passed']
                row['conditions'][suite+'_'+mode]=condition(records,80 if suite=='bfcl' else 20,'complete' if metric['complete'] else 'partial',row['evidence'])
        rows.append(row)
    period_ids=set(load(period/'runs.json')['run_ids']) if (period/'runs.json').exists() else None
    manifests={p.parent.name:read(p.relative_to(ROOT).as_posix()) for p in sorted((ROOT/'runs').glob('*/manifest.json')) if period_ids is None or p.parent.name in period_ids}
    for name,m in manifests.items():
        cfg=m.get('config',{})
        if m['benchmark'] not in ['quantization-mtp','mtp-speed-only'] or cfg.get('pilot'):continue
        profile=cfg['profile'];model=cfg['model'];meta=metadata(profile);ngl=meta['ngl'];moe=meta['cpu_moe_layers']
        definition,definition_source=definitions.get((model['model'],model['quantization']),({},None))
        layers=model.get('decoder_layers') or (definition.get('decoder_layers') if model.get('sha256')==definition.get('sha256') else None)
        placement=f'CPU MoE {moe}層 / GPU {ngl}指定' if moe not in [None,'0'] else f'GPU {ngl}指定 / CPU MoE指定なし'
        if layers and ngl not in [None,'all']:
            gpu=int(ngl)-1;placement=f'CPU {layers-gpu}層 / GPU {gpu}層＋出力'
        row={'id':name,'model':model['model'],'quantization':model['quantization'],'kind':'speed-only' if cfg.get('speed_only') else 'quality','origin':'独立run（再測定を含む）','state':m['status'],'placement':placement,'mode_control':'native enable_thinking; requested mode and observed reasoning are separate','evidence':'runs/'+name+'/manifest.json','artifact':model,'conditions':{},'fixed_speed':None,'memory':{},**meta}
        props_path=ROOT/'runs'/name/'configs/server-props.json'
        if props_path.exists():
            props=read(props_path.relative_to(ROOT).as_posix());row['runtime']=props.get('build_info',row['runtime'])
            # /props reports request defaults as "none" even with a CLI MTP server.
            # Actual MTP ON is checked against positive draft counts in saved speed responses.
            if row['mtp']=='off':assert props['default_generation_settings']['params']['speculative.types']=='none'
        if layers:row['architecture_source']=definition_source
        speed=ROOT/'runs'/(name+'-speed')/'summary.json'
        if speed.exists():
            s=read(speed.relative_to(ROOT).as_posix());row['fixed_speed']={'tok_s':s['median_decode_tokens_per_second'],'cases':s['attempted'],'tokens_per_case':s['tokens_per_case'],'evidence':'runs/'+name+'-speed/summary.json'}
        memory=ROOT/'runs'/name/'summaries/memory.json'
        if memory.exists():
            v=read(memory.relative_to(ROOT).as_posix());row['memory']={'peak_gpu_mib':v.get('peak_gpu_used_mib_system_total'),'minimum_ram_gib':v.get('minimum_available_ram_bytes',0)/1024**3,'scope':'run全体の標本'}
        if row['kind']=='quality':
            for suite in ['bfcl','he']:
                for mode in ['off','on']:
                    child=name+'-'+('humaneval' if suite=='he' else suite)+'-'+mode;cm=manifests.get(child,{});path=ROOT/'runs'/child;filename='bfcl-cases.json' if suite=='bfcl' else 'cases.json';ep=path/'summaries'/filename
                    entries=read(ep.relative_to(ROOT).as_posix()) if ep.exists() else [];records=[]
                    for e in entries:
                        cid=e.get('id') or e['task_id'];raw='runs/'+child+'/raw/'+cid.replace('/','_')+'.json';records.append(record(e,raw,cid,e.get('category',suite)))
                    row['conditions'][suite+'_'+mode]=condition(records,80 if suite=='bfcl' else 20,cm.get('status','not-started'),'runs/'+child+'/manifest.json' if cm else row['evidence'],cm.get('error'))
        audit=ROOT/'runs'/(name+'-he-policy-audit')/'summary.json'
        if audit.exists():
            v=read(audit.relative_to(ROOT).as_posix())['iq3_m'];row['secondary_he']={mode:{k:v[mode][k] for k in ['original_passed','secondary_passed']} for mode in ['off','on']};row['secondary_evidence']=audit.relative_to(ROOT).as_posix()
        rows.append(row)
    assert len({r['id'] for r in rows})==len(rows)
    for i,row in enumerate(rows,1):
        row['label']='R'+str(i)
        for c in row['conditions'].values():
            c['samplers']=sampler(c['cases'])
            c['passed_without_final']=sum(r['passed'] and r['empty_final'] is True for r in c['cases'])
            if c['expected']==80:
                needed=[r for r in c['cases'] if r['category']!='irrelevance']
                c['tool_needed_saved']=len(needed)
                c['tool_needed_passed']=sum(r['passed'] for r in needed)
    raw=[c['raw'] for r in rows for v in r['conditions'].values() for c in v['cases']]
    assert len(raw)==len(set(raw)),'A source answer is counted twice'
    historical=[];fingerprints={}
    for source in HISTORICAL:
        d=read(source);protocol=d.get('protocol',{})
        for model,m in d['models'].items():
            groups=[]
            if isinstance(m.get('humaneval'),list):groups.append(('he','baseline',m['humaneval']))
            if isinstance(m.get('modes'),dict):groups.extend(('he',mode,items) for mode,items in m['modes'].items() if isinstance(items,list))
            if isinstance(m.get('human_eval'),dict):groups.extend(('he',mode,items) for mode,items in m['human_eval'].items() if isinstance(items,list))
            if isinstance(m.get('bfcl'),list):groups.append(('bfcl','off',m['bfcl']))
            if isinstance(m.get('cases'),list):groups.append(('bfcl','off',m['cases']))
            for suite,mode,entries in groups:
                rid=source+'::'+model+'::'+suite+'::'+mode;fingerprint=hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest();previous=fingerprints.setdefault(fingerprint,rid)
                controls=protocol.get('human_eval' if suite=='he' else suite,protocol)
                historical.append({'id':rid,'source':source,'model_key':model,'runtime':m.get('runtime'),'context':controls.get('context',m.get('context')),'max_output':controls.get('max_tokens','原記録参照'),'benchmark':suite,'thinking':mode,'saved':len(entries),'passed_saved':sum(bool(e['passed']) for e in entries),'expected':80 if suite=='bfcl' else 20,'caps':sum(e.get('finish_reason')=='length' for e in entries),'same_response_snapshot':previous if previous!=rid else None,'scope':'旧予算・旧ランタイムの参考記録。主比較の件数・順位に加算しない。'})
    inventory=[];ancillary={'speed':[],'capacity':[],'integration':[],'replay':[]}
    for name,m in manifests.items():
        p=ROOT/'runs'/name;sp=p/'summary.json';summary=read(sp.relative_to(ROOT).as_posix()) if sp.exists() else {}
        item={'run':name,'title':m['title'],'benchmark':m['benchmark'],'kind':m['kind'],'type':m.get('experiment_type','benchmark'),'status':m['status'],'outcome':summary.get('outcome'),'headline':summary.get('headline'),'error':m.get('error'),'evidence':'runs/'+name+'/manifest.json'};inventory.append(item)
        if m['benchmark']=='fixed-length-speed':ancillary['speed'].append({**item,'attempted':summary.get('attempted'),'tokens_per_case':summary.get('tokens_per_case'),'tok_s':summary.get('median_decode_tokens_per_second')})
        if item['type']=='capacity':ancillary['capacity'].append(item)
        if item['type'] in ['harness-integration','transport-integration']:ancillary['integration'].append({**item,'passed':summary.get('passed'),'attempted':summary.get('attempted')})
        if m['kind']=='replay':ancillary['replay'].append(item)
    pairs={(r['model'],r['quantization']) for r in rows}
    for m,_ in definitions.values():pairs.add((m['model'],m['quantization']))
    coverage=[]
    for model,quant in sorted(pairs):
        for mtp in ['off','on']:
            matches=[r for r in rows if (r['model'],r['quantization'],r['mtp'])==(model,quant,mtp)];states={}
            for key in KEYS:
                cs=[r['conditions'][key] for r in matches if key in r['conditions']];states[key]='complete' if any(c['complete'] for c in cs) else 'partial' if any(c['saved'] for c in cs) else 'failed' if any(c['status']=='failed' for c in cs) else 'not-measured'
            note=''
            if model=='Mage-VL-Cowork' and mtp=='on':note='実機でMTP層なしを確認' if quant=='Q3_K_M' else 'MTP層なしの構造情報あり、起動プローブは未実施'
            if quant in ['Q4_K_S','Q4_K_L'] and model=='Qwen3.6-35B-A3B':note='Sの取得失敗で準備終了。本測定なし。'
            coverage.append({'model':model,'quantization':quant,'mtp':mtp,'matching_rows':[r['id'] for r in matches],'states':states,'note':note})
    archives=[{'path':p.relative_to(ROOT).as_posix(),'role':'補助採点（replay）' if 'grader-sensitivity' in p.parts else '原集計／参照スナップショット（主比較に再加算しない）'} for p in sorted((ROOT/'artifacts/local-llm').rglob('results.json'))]
    conditions=[(r,c) for r in rows for c in r['conditions'].values()]
    counts={'configuration_rows':len(rows),'quality_rows':sum(r['kind']=='quality' for r in rows),'speed_only_rows':sum(r['kind']=='speed-only' for r in rows),'complete_quality_rows':sum(len(r['conditions'])==4 and all(c['complete'] for c in r['conditions'].values()) for r in rows),'complete_conditions':sum(c['complete'] for r,c in conditions),'condition_slots':len(conditions),'unique_saved_responses':len(raw),'unique_model_quant_pairs_measured':len({(r['model'],r['quantization']) for r in rows}),'unique_model_quant_mtp_measured':len({(r['model'],r['quantization'],r['mtp']) for r in rows}),'candidate_model_quant_pairs':len(pairs),'registered_runs':len(inventory),'historical_condition_snapshots':len(historical),'archived_result_files':len(archives)}
    return {'period':'period-001','title':'第1期 ローカルLLM測定の横断比較','scope':'主比較はb11960・65536 context・最大64000出力の固定HE20/BFCL80。旧予算・旧ランタイム、固定長速度、容量、実ツール、replayは区別する。未測定欄は対応保証や今後の測定計画を意味しない。','counts':counts,'rows':rows,'coverage':coverage,'historical':historical,'ancillary':ancillary,'inventory':inventory,'archives':archives,'sources':sources}
