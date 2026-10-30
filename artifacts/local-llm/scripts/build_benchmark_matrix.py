"""Build a standalone, offline dashboard from saved benchmark cases; never runs inference."""
import csv,datetime,hashlib,json,os,re,statistics,sys
from pathlib import Path
ROOT=Path(r'C:\LocalLLM');OUT=Path(sys.argv[1]);OUT.mkdir(exist_ok=True)
SIX=ROOT/'runs/bench64k-output-20261030-141002';TWO=ROOT/'runs/legacy-models-64k-20261030-180109'
META=[('qwen-large','Qwen3.6-35B-A3B','UD-Q3_K_M','Qwen','35B / 3B active'),('qwen-daily','Qwen3.5-4B','Q4_K_M','Qwen','4B'),('lfm3','LFM3-1.7B Text','QAD-Q4_0','LFM3','1.7B'),('lfm3-q8','LFM3-1.7B Text','Q8_0','LFM3','1.7B'),('lfm3-vl-q4','LFM3-VL-2B','QAD-Q4_0','LFM3 VL','2B'),('lfm3-vl-q8','LFM3-VL-2B','Q8_0','LFM3 VL','2B'),('lfm','LFM2.5-24B-A2B','QAD-Q4_0','LFM2.5','24B / 2B active'),('glm','GLM-4.7-Flash','Q4_K_M','GLM','30B / 3B active')]
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def link(path):return os.path.relpath(path,OUT).replace('\\','/')
def stat(entries,total,source):
    timings=[x['timings'] for x in entries if x.get('timings')];ms=sum(t.get('predicted_ms',0) for t in timings)
    return {'passed':sum(x['passed'] for x in entries),'attempted':len(entries),'expected':total,'complete':len(entries)==total,'rate':100*sum(x['passed'] for x in entries)/total if len(entries)==total else None,'median_seconds':statistics.median(x['seconds'] for x in entries) if entries else None,'max_seconds':max((x['seconds'] for x in entries),default=None),'total_seconds':sum(x['seconds'] for x in entries),'tokens_per_second':1000*sum(t.get('predicted_n',0) for t in timings)/ms if ms else None,'caps':sum(x.get('finish_reason')=='length' for x in entries),'reasoning':sum(bool(x.get('reasoning_observed')) for x in entries),'source':source,'total_completion_tokens':sum((x.get('usage') or {}).get('completion_tokens',0) for x in entries)}
def brief(case):
    value={k:case.get(k) for k in ['passed','seconds','finish_reason','reasoning_observed','reasoning_characters','usage','decoded','decode_error','failure_kind','grade']}
    value['final_content_characters']=len(case.get('content') or '')
    if isinstance(value.get('decoded'),list):
        value['tool_call_count']=len(value['decoded'])
        if len(value['decoded'])>5:value['tool_calls_omitted_in_preview']=len(value['decoded'])-5;value['decoded']=value['decoded'][:5]
    return value
six=read(SIX/'results.json');two=read(TWO/'results.json');orchestration=read(OUT/'orchestration.json')
allmodels={**six['models'],**two['models']};data={'updated_at':datetime.datetime.now().astimezone().isoformat(),'runtime':'llama.cpp b11960 / 8642541b2 / CUDA 12.4','context':65536,'output_cap':64000,'hardware':'Ryzen 9 7940HS · RAM 32 GiB · RTX 4070 Laptop 8 GiB','orchestration':orchestration,'models':[],'conditions_complete':0,'conditions_expected':32,'new_bfcl_on_done':0,'new_bfcl_on_expected':640,'old_result_count':960}
if orchestration['status'] not in ['complete','error']:
    active_key='qwen-large' if orchestration['status']=='waiting_for_qwen35' else orchestration.get('active_model')
    active_dir=Path(orchestration['qwen35_directory']) if active_key=='qwen-large' else OUT/(active_key or '')
    if (active_dir/'active-request.json').exists():
        active=read(active_dir/'active-request.json');active['model_key']=active_key
        lifecycle=ROOT/'hermes' if (active_key or '').startswith('qwen-') else ROOT
        if (lifecycle/'server-state.json').exists():
            serverstate=read(lifecycle/'server-state.json');log=Path(serverstate['log'])
            if log.exists():
                with log.open('rb') as f:f.seek(max(0,log.stat().st_size-12000));tail=f.read().decode('utf-8',errors='replace')
                events=re.findall(r'(?:print_timing|launch_slot_|release):[^\n]*',tail)
                match=re.search(r'n_gen\s*=\s*(\d+), tg\s*=\s*([\d.]+)',events[-1]) if events and events[-1].startswith('print_timing:') else None
                if match:active['generated_tokens_observed']=int(match[1]);active['generation_tps_observed']=float(match[2])
        data['active_request']=active
for key,name,quant,family,parameters in META:
    baseline=allmodels[key];base=TWO if key in two['models'] else SIX
    ondir=Path(orchestration['qwen35_directory']) if key=='qwen-large' else OUT/key
    added=read(ondir/'results.json') if (ondir/'results.json').exists() else None
    on=added['on'] if added else []
    record={'key':key,'name':name,'quant':quant,'family':family,'parameters':parameters,'metrics':{},'cases':{'he':[],'bfcl':[]},'categories':{},'improved':[],'regressed':[],'failed_both':[],'source_report':link(base/'report.html'),'on_report':link(ondir/'report.html') if (ondir/'report.html').exists() else None,'on_validation':link(ondir/'independent-audit.json') if (ondir/'independent-audit.json').exists() else None,'mode_note':'OFFはCLI思考予算0、ONは-1。埋込テンプレートはenable_thinkingを無視。' if key=='lfm' else 'モデルのenable_thinkingをfalse / trueに切り替え。','on_error':added.get('error') if added else None}
    for mode in ['off','on']:
        entries=baseline['human_eval'][mode];record['metrics']['he_'+mode]=stat(entries,20,'保存済み')
    record['metrics']['bfcl_off']=stat(baseline['bfcl'],80,'保存済み')
    record['metrics']['bfcl_on']=stat(on,80,'今回追加')
    for a,b in zip(baseline['human_eval']['off'],baseline['human_eval']['on']):
        assert a['task_id']==b['task_id']
        record['cases']['he'].append({'id':a['task_id'],'category':'humaneval','off':brief(a),'on':brief(b),'off_raw':link(base/(key+'-off-'+a['task_id'].replace('/','_')+'.json')),'on_raw':link(base/(key+'-on-'+a['task_id'].replace('/','_')+'.json'))})
    on_by_id={x['id']:x for x in on}
    for a in baseline['bfcl']:
        b=on_by_id.get(a['id']);pair={'id':a['id'],'category':a['category'],'off':brief(a),'on':brief(b) if b else None,'off_raw':link(base/(key+'-bfcl-'+a['id']+'.json')),'on_raw':link(ondir/('on-'+a['id']+'.json')) if b else None}
        record['cases']['bfcl'].append(pair)
        if b:
            if not a['passed'] and b['passed']:record['improved'].append(a['id'])
            elif a['passed'] and not b['passed']:record['regressed'].append(a['id'])
            elif not a['passed'] and not b['passed']:record['failed_both'].append(a['id'])
    for cat in ['simple_python','multiple','parallel','irrelevance']:
        record['categories'][cat]={mode:stat([x for x in entries if x['category']==cat],20,'保存済み' if mode=='off' else '今回追加') for mode,entries in [('off',baseline['bfcl']),('on',on)]}
    profile=baseline.get('profiles',{}).get('on',baseline['profile']);args=profile['server_args']
    record['placement']='MoE先頭'+args[args.index('--n-cpu-moe')+1]+'層のexpertをCPU' if '--n-cpu-moe' in args else 'プロファイル参照'
    record['threads']=args[args.index('-t')+1];record['model_file']=Path(profile['model']).name
    mem=added.get('memory') if added else None
    record['on_memory']={'minimum_available_ram_gib':mem['minimum_available_ram_bytes']/2**30,'peak_system_gpu_mib':mem['peak_gpu_used_mib_system_total']} if mem and mem.get('minimum_available_ram_bytes') is not None else None
    data['conditions_complete']+=sum(x['complete'] for x in record['metrics'].values());data['new_bfcl_on_done']+=len(on)
    data['models'].append(record)
for filename,value in [('matrix-data.json',data)]:
    target=OUT/filename;tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
target=OUT/'conditions.csv';tmp=target.with_suffix('.tmp')
with tmp.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f);writer.writerow(['model','quantization','condition','complete','passed','attempted','expected','success_percent','median_seconds','max_seconds','total_seconds','generation_tokens_per_second','output_cap_hits','reasoning_observed_cases','source'])
    for m in data['models']:
        for condition,s in m['metrics'].items():writer.writerow([m['name'],m['quant'],condition,s['complete'],s['passed'],s['attempted'],s['expected'],s['rate'],s['median_seconds'],s['max_seconds'],s['total_seconds'],s['tokens_per_second'],s['caps'],s['reasoning'],s['source']])
tmp.replace(target)
truncated=[]
for m in data['models']:
    for suite,pairs in m['cases'].items():
        for pair in pairs:
            for mode in ['off','on']:
                x=pair[mode]
                if x and x['finish_reason']=='length':
                    usage=x.get('usage') or {}
                    truncated.append({'model':m['name'],'quantization':m['quant'],'suite':suite,'mode':mode,'problem':pair['id'],'passed':x['passed'],'seconds':x['seconds'],'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),'total_tokens':usage.get('total_tokens'),'configured_context':65536,'output_cap':64000,'reasoning_characters':x.get('reasoning_characters'),'parsed_tool_call_count':x.get('tool_call_count'),'final_content_characters':x['final_content_characters'],'raw_response':pair[mode+'_raw']})
target=OUT/'truncations.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(truncated,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
if truncated:
    target=OUT/'truncations.csv';tmp=target.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(truncated[0]));writer.writeheader();writer.writerows(truncated)
    tmp.replace(target)
template=(ROOT/'scripts/benchmark_matrix_template.html').read_text(encoding='utf-8')
payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
page=template.replace('__BENCHMARK_DATA__',payload);target=OUT/'index.html';tmp=target.with_suffix('.tmp');tmp.write_text(page,encoding='utf-8');tmp.replace(target)
if __name__=='__main__':print(json.dumps({'matrix_conditions_complete':data['conditions_complete'],'bfcl_on_done':data['new_bfcl_on_done']}),flush=True)
