"""Inventory token-limit events from adopted results without rerunning models."""
import collections,csv,datetime,gzip,hashlib,html,json,pathlib,sys
ROOT=pathlib.Path(r'C:\LocalLLM')
OUT=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'runs'/('truncation-audit-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
OUT.mkdir(exist_ok=True)
LABELS={'lfm3':'LFM3-1.7B Text QAD-Q4_0','lfm3-vl-q4':'LFM3-VL-2B QAD-Q4_0','lfm3-q8':'LFM3-1.7B Text Q8_0','lfm3-vl-q8':'LFM3-VL-2B Q8_0','qwen-daily':'Qwen3.5-4B Q4_K_M','qwen-large':'Qwen3.6-35B-A3B UD-Q3_K_M','lfm':'LFM2.5-24B-A2B QAD-Q4_0','glm':'GLM-4.7-Flash Q4_K_M'}
canon=lambda k:{'daily':'qwen-daily','large':'qwen-large'}.get(k,k)
read=lambda p:json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
dataset=ROOT/'hermes/benchmarks/HumanEval.jsonl.gz'
problems={p['task_id']:p for p in map(json.loads,gzip.decompress(dataset.read_bytes()).decode().splitlines())}
descriptions={'HumanEval/7':'部分文字列を含む文字列を抽出','HumanEval/22':'リストから整数を抽出','HumanEval/28':'文字列リストを連結','HumanEval/62':'多項式の導関数の係数を計算','HumanEval/151':'負数・非整数を除外し、奇数の二乗を合計','HumanEval/163':'指定範囲の偶数の1桁整数を列挙'}
plans=[('latest-added',ROOT/'runs/legacy-models-64k-20261030-180109/results.json',64000,True),('latest-reference',ROOT/'runs/bench64k-output-20261030-141002/results.json',64000,True),('historical-lfm-4096',ROOT/'runs/lfm3-bench-20261030-132439/results.json',4096,False),('historical-qwen-4096',ROOT/'hermes/benchmarks/thinking-comparison-20261029-174343/results.json',4096,False),('historical-qwen-1024-he',ROOT/'hermes/benchmarks/comparison-20261029-141429/results.json',1024,False),('historical-qwen-1024-bfcl',ROOT/'hermes/benchmarks/bfcl/comparison-20261029-142528/results.json',1024,False)]
sources={str(dataset):sha(dataset)};entries=[];latest={};model_stats={}
for experiment,path,cap,current in plans:
    r=read(path);assert 'error' not in r;sources[str(path)]=sha(path)
    for original_key,m in r['models'].items():
        key=canon(original_key);modes=m.get('human_eval') or m.get('modes')
        protocol=r.get('protocol',{})
        candidates=[protocol.get('context'),protocol.get('human_eval',{}).get('context'),protocol.get('bfcl',{}).get('context'),m.get('context'),m.get('profile',{}).get('context_tokens'),m.get('served_parameters',{}).get('n_ctx')]
        contexts=[v for v in candidates if isinstance(v,int)]
        assert contexts and set(contexts)=={65536},(path,key,contexts)
        context=contexts[0]
        suites=[]
        if isinstance(modes,dict):suites.extend(('HumanEval',mode,es) for mode,es in modes.items())
        if isinstance(m.get('humaneval'),list):suites.append(('HumanEval','off',m['humaneval']))
        bf=m.get('bfcl') or m.get('cases')
        if isinstance(bf,list):suites.append(('BFCL','off',bf))
        for suite,mode,es in suites:
            for e in es:
                task=e.get('task_id') or e.get('id');usage=e.get('usage') or {}
                item={'experiment':experiment,'current':current,'model_key':key,'model':LABELS[key],'suite':suite,'mode':mode,'problem':task,'entry_point':problems[task]['entry_point'] if suite=='HumanEval' else task,'description':descriptions.get(task,''),'runtime':m.get('runtime') or (m.get('profile') or {}).get('runtime_build'),'context_tokens':context,'output_limit':cap,'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),'total_tokens':usage.get('total_tokens'),'finish_reason':e.get('finish_reason'),'passed':e.get('passed'),'failure_kind':e.get('failure_kind'),'source':str(path)}
                if current:
                    assert usage['total_tokens']<context
                    identity=(key,suite,mode,task);assert identity not in latest;latest[identity]=item
                    model_stats.setdefault(key,{'model':LABELS[key],'scored':0,'output_caps':0})['scored']+=1
                if e.get('finish_reason')=='length':
                    assert usage['completion_tokens']==cap and usage['total_tokens']<context
                    item['kind']='output_limit';entries.append(item)
                    if current:model_stats[key]['output_caps']+=1
assert len(latest)==960 and len(model_stats)==8
for e in entries:
    now=latest[(e['model_key'],e['suite'],e['mode'],e['problem'])]
    e['latest_finish_reason']=now['finish_reason'];e['latest_passed']=now['passed']
    e['latest_status']='still_output_limited' if now['finish_reason']=='length' else 'completed_pass' if now['passed'] else 'completed_fail'
context_stops=[]
for p in sorted((ROOT/'runs').glob('*.summary.json')):
    r=read(p)
    if r.get('failure')!='context_budget':continue
    log=p.with_name(p.name.replace('.summary.json','.jsonl'));events=[json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()]
    profile=events[0]['profile'];checks=[e for e in events if e.get('event')=='context_check'];last=checks[-1]
    model='qwen-large' if 'Qwen3.6-35B' in profile['model'] else 'glm' if 'GLM-4.7-Flash' in profile['model'] else None
    assert model is not None and last['actual_input_tokens']+profile['max_tokens']>profile['context_tokens']
    sources[str(p)]=sha(p);sources[str(log)]=sha(log)
    context_stops.append({'kind':'context_reservation_guard','current':False,'experiment':r['run_id'],'model_key':model,'model':LABELS[model],'suite':'Custom agent','mode':'on' if r['thinking'].get('enable_thinking') else 'off','problem':r['task_id'],'entry_point':'Get-WeightedTotal.ps1','description':'PS4: PowerShellのCSV金額集計スクリプト修正','runtime':r['runtime_build'],'context_tokens':profile['context_tokens'],'output_limit':profile['max_tokens'],'prompt_tokens':last['actual_input_tokens'],'completion_tokens':None,'total_tokens':None,'required_input_plus_reserved_output':last['actual_input_tokens']+profile['max_tokens'],'remaining_tokens':last['remaining_tokens'],'finish_reason':'request_not_sent','passed':r['success'],'artifact_tests_passed':sum(c['passed'] for c in r['validator']['dynamic']['cases']),'artifact_tests_total':len(r['validator']['dynamic']['cases']),'source':str(p),'source_log':str(log)})
current_caps=[e for e in entries if e['current']]
historic=[e for e in entries if not e['current']]
assert len(current_caps)==6 and all(e['model_key']=='qwen-daily' and e['mode']=='on' and e['suite']=='HumanEval' and not e['passed'] for e in current_caps)
assert {e['problem'] for e in current_caps}=={'HumanEval/7','HumanEval/22','HumanEval/28','HumanEval/62','HumanEval/151','HumanEval/163'}
assert len(historic)==46 and len(entries)==52 and len(context_stops)==3
assert all(e['context_tokens']==16384 for e in context_stops)
for e in context_stops:e['shortfall_tokens']=e['required_input_plus_reserved_output']-e['context_tokens']
context_stops.sort(key=lambda e:(e['problem']!='PS4',{'qwen-large':0,'glm':1}[e['model_key']]))
groups=collections.defaultdict(list)
for e in historic:groups[(e['output_limit'],e['model'],e['suite'],e['mode'])].append(e['problem'])
audit={'scope':'Current eight-configuration HumanEval/BFCL results plus adopted historical 4096/1024-token results; root custom-task summaries scanned for explicit context_budget stops. Earlier abandoned benchmark attempts are not double-counted.','created_at':datetime.datetime.now().astimezone().isoformat(),'current_scored_generations':960,'current_total_context_exhaustions':0,'current_output_cap_events':len(current_caps),'historical_output_cap_events':len(historic),'output_cap_events_all_experiments':len(entries),'unique_output_limited_model_suite_mode_problem_combinations':len({(e['model_key'],e['suite'],e['mode'],e['problem']) for e in entries}),'context_guard_stops':context_stops,'current_output_caps':current_caps,'output_cap_events':entries,'current_model_status':model_stats,'source_sha256':sources,'notes':['finish_reason=length alone does not establish total-context exhaustion. All listed HumanEval/BFCL cap hits generated exactly the requested output limit while total usage remained below 65536.','Context guard stops occur before the next model request: history plus reserved output cannot fit. They are not interrupted in-flight completions.','Output-limit hits do not necessarily fail grading: one historical HumanEval and two historical BFCL cases still passed.','The Qwen35 thinking-OFF PS4 diagnostic stopped at tool_budget, and the old GLM near-64K-input capacity diagnostic was stopped for low available RAM; neither is classified here as context-token exhaustion.']}
audit['runner_sha256']=sha(pathlib.Path(__file__))
(OUT/'audit_truncations.py').write_bytes(pathlib.Path(__file__).read_bytes())
(OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
fields=['kind','experiment','current','model','suite','mode','problem','entry_point','description','runtime','context_tokens','output_limit','prompt_tokens','completion_tokens','total_tokens','required_input_plus_reserved_output','shortfall_tokens','remaining_tokens','finish_reason','passed','latest_status','latest_passed','artifact_tests_passed','artifact_tests_total','source','source_log']
with (OUT/'cases.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(context_stops+entries)
def table(head,rows):return '<table><tr>'+''.join('<th>'+html.escape(str(v))+'</th>' for v in head)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'
ct=table(['モデル','試行・問題','総枠','履歴入力','次回出力の予約','必要合計','不足token','成果物テスト'],[[e['model'],e['problem'],e['context_tokens'],e['prompt_tokens'],e['output_limit'],e['required_input_plus_reserved_output'],e['shortfall_tokens'],str(e['artifact_tests_passed'])+'/'+str(e['artifact_tests_total'])] for e in context_stops])
cur=table(['モデル','思考','HumanEval問題','内容','入力token','出力token','合計token'],[[e['model'],'ON',e['problem']+' / '+e['entry_point'],e['description'],e['prompt_tokens'],e['completion_tokens'],e['total_tokens']] for e in current_caps])
hist=table(['当時の出力上限','モデル','課題','思考','上限到達した問題ID'],[[cap,model,suite,mode.upper(),', '.join(ids)] for (cap,model,suite,mode),ids in sorted(groups.items())])
state=table(['モデル','今回の採点件数','出力上限到達'],[[v['model'],v['scored'],v['output_caps']] for v in model_stats.values()])
doc='''<!doctype html><html lang="ja"><meta charset="utf-8"><title>コンテキスト不足と出力上限の停止一覧</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:1400px;margin:32px auto;padding:0 24px;color:#182a3b}table{border-collapse:collapse;width:100%;margin:20px 0 32px;font-size:14px}td,th{border:1px solid #d3dce6;padding:8px;text-align:left}th{background:#edf2f7}.note{background:#fff5dc;padding:16px}</style><h1>コンテキスト不足と出力上限の停止一覧</h1><p>保存済みログの監査。新しいモデル生成は行っていない。現在の8構成・960件と、比較に採用した過去の標準ベンチマーク結果を調べ、独自タスクのcontext_budget記録も抽出した。</p><p class="note">今回のHumanEval/BFCLでは総コンテキスト不足0件。残る6件は、総枠65,536の中で出力上限64,000に達したQwen 4B・思考ON。過去の16K独自タスクPS4には、次回リクエストの履歴＋予約出力が入らず止まった3試行があった。</p><h2>総コンテキストの予約枠が不足した独自タスク</h2><p>すべてb11946・思考ON・16,384枠。PS4はGet-WeightedTotal.ps1のCSV集計バグ修正。次のモデル要求を送る前にハーネスが停止した。Qwenの通常試行では成果物の5検査は通っていたが、最終応答に到達しなかった。GLMとQwenの予約3,584診断は成果物にも不合格があり、コンテキストを増やせば必ず成功するとはいえない。</p>'''
doc+=ct+'<h2>最新の64K条件で残った出力上限到達</h2><p>すべてQwen3.5-4B Q4_K_M、思考ON、b11960。64,000出力tokenを使い切り、最終コードは出ていない。合計使用量は64,102〜64,182で、総枠65,536にはまだ余裕がある。</p>'+cur+'<h2>8構成の最新状態</h2>'+state+'<h2>過去の4,096／1,024出力token条件での上限到達</h2><p>以下は総コンテキスト65,536での出力制限。最新状態と混同しない。同じモデル・問題が再測定でも上限に達した場合は別試行として記録している。上限到達でも既に出したコードが合格したり、BFCLで呼び出し不要の判定が通る場合がある。</p>'+hist
doc+='<p>出力上限の記録は全実験で52試行・46種類のモデル×課題×思考×問題の組み合わせ。うち現在も残るのは上の6件。旧試行が通常終了に変わっても、必ず正解に変わったわけではない。</p><p><a href="cases.csv">全55記録のCSV（出力上限52＋コンテキスト予約不足3）</a> / <a href="audit.json">集計・根拠ファイル・最新結果との対応JSON</a></p></html>'
(OUT/'report.html').write_text(doc,encoding='utf-8')
assert all(sha(p)==digest for p,digest in sources.items())
print(json.dumps({'directory':str(OUT),'current_output_caps':6,'historical_output_caps':46,'context_guard_stops':3,'source_files_unchanged':True},ensure_ascii=False))
