"""Completed 64K-context / large-output comparison, with the old budgets retained."""
import html,json,pathlib,statistics,sys
from install_lfm3_runtime import save
run=pathlib.Path(sys.argv[1]);r=json.loads((run/'results.json').read_text(encoding='utf-8'));stage='--lfm-stage' in sys.argv
all_done='error' not in r and len(r['models'])==6 and all(len(m['human_eval']['off'])==20 and len(m['human_eval']['on'])==20 and len(m['bfcl'])==80 and m.get('test_server_stopped') for m in r['models'].values())
labels={'lfm3':'LFM3 Text QAD 4bit','lfm3-vl-q4':'LFM3 VL QAD 4bit','lfm3-q8':'LFM3 Text Q8_0','lfm3-vl-q8':'LFM3 VL Q8_0','qwen-daily':'Qwen3.5-4B Q4_K_M','qwen-large':'Qwen3.6-35B-A3B UD-Q3_K_M'}
assert stage or all_done
old=json.loads(pathlib.Path(r['previous_4096_reference']).read_text(encoding='utf-8'))
qh=json.loads(pathlib.Path(r['human_eval_reference']).read_text(encoding='utf-8'));qb=json.loads(pathlib.Path(r['bfcl_reference']).read_text(encoding='utf-8'))
def stat(entries):
    timings=[e['timings'] for e in entries if e.get('timings')];ms=sum(t.get('predicted_ms',0) for t in timings)
    return {'passed':sum(e['passed'] for e in entries),'attempted':len(entries),'median_seconds':statistics.median(e['seconds'] for e in entries),'total_seconds':sum(e['seconds'] for e in entries),'tokens_per_second':1000*sum(t.get('predicted_n',0) for t in timings)/ms if ms else None,'output_cap_hits':sum(e.get('finish_reason')=='length' for e in entries),'no_final_code':sum(e.get('failure_kind') in ['budget_exhausted_before_final_code','no_final_code'] for e in entries),'reasoning_observed_cases':sum(e.get('reasoning_observed',False) for e in entries),'maximum_actual_output_tokens':max(e.get('usage',{}).get('completion_tokens',0) for e in entries),'maximum_actual_total_tokens':max(e.get('usage',{}).get('total_tokens',0) for e in entries)}
models=[]
for key in (list(old['models']) if stage else r['protocol']['order']):
    m=r['models'][key]
    assert len(m['human_eval']['off'])==20 and len(m['human_eval']['on'])==20 and len(m['bfcl'])==80 and m.get('test_server_stopped')
    if key in old['models']:
        prior=old['models'][key];prior_he=prior['human_eval'];prior_bf=prior['bfcl']
    else:
        short=key.removeprefix('qwen-');prior_he=qh['models'][short]['modes'];prior_bf=qb['models'][short]['cases']
    row={'key':key,'model':labels[key],'runtime':m['runtime'],'human_eval':{mode:stat(es) for mode,es in m['human_eval'].items()},'bfcl':stat(m['bfcl']),'previous_human_eval':{mode:stat(es) for mode,es in prior_he.items()},'previous_bfcl':stat(prior_bf),'memory':m['memory'],'bfcl_categories':{c:stat([e for e in m['bfcl'] if e['category']==c]) for c in ['simple_python','multiple','parallel','irrelevance']}}
    row['human_eval_outcome_changes']={}
    for mode in ['off','on']:
        before={e['task_id']:e for e in prior_he[mode]}; after={e['task_id']:e for e in m['human_eval'][mode]}
        row['human_eval_outcome_changes'][mode]=[{'task_id':pid,'previous_passed':before[pid]['passed'],'now_passed':after[pid]['passed'],'previous_finish_reason':before[pid].get('finish_reason'),'now_finish_reason':after[pid].get('finish_reason')} for pid in before if before[pid]['passed']!=after[pid]['passed']]
    models.append(row)
def pair(a,b,idkey):
    aa={e[idkey]:e['passed'] for e in a};bb={e[idkey]:e['passed'] for e in b};assert aa.keys()==bb.keys()
    return {'both_pass':sum(aa[k] and bb[k] for k in aa),'text_only':sum(aa[k] and not bb[k] for k in aa),'vl_only':sum(not aa[k] and bb[k] for k in aa),'both_fail':sum(not aa[k] and not bb[k] for k in aa)}
pairs=[]
for a,b,q in [('lfm3','lfm3-vl-q4','QAD-Q4_0'),('lfm3-q8','lfm3-vl-q8','Q8_0')]:
    for mode in ['off','on']:pairs.append({'quantization':q,'benchmark':'HumanEval '+mode,**pair(r['models'][a]['human_eval'][mode],r['models'][b]['human_eval'][mode],'task_id')})
    pairs.append({'quantization':q,'benchmark':'BFCL off',**pair(r['models'][a]['bfcl'],r['models'][b]['bfcl'],'id')})
s={'models':models,'pairs':pairs,'context_per_slot':65536,'output_cap_target':64000,'requested_output_rule':r['protocol']['budget_rule'],'settings_unchanged':all(r['settings_unchanged'].values()),'limits':r['limits']}
audit_path=run/'grader-sensitivity/results.json'
if audit_path.exists():
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    audit['models']={k:v for k,v in audit['models'].items() if k in {m['key'] for m in models}}
    s['grader_sensitivity']={k:{mode:{f:v[f] for f in ['original_passed','secondary_passed','rescued_ids']} for mode,v in modes.items()} for k,modes in audit['models'].items()}
s['scope']='Four completed LFM configurations only' if stage else 'All six configurations complete'
s['all_six_complete']=all_done
summary_name='lfm3-stage-summary.json' if stage else 'summary.json'
save(run/summary_name,s)
def table(head,rows):return '<table><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in head)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'
score=table(['モデル','HE OFF /20','HE ON /20','BFCL OFF /80'],[[m['model'],m['human_eval']['off']['passed'],m['human_eval']['on']['passed'],m['bfcl']['passed']] for m in models])
categories=table(['モデル','単一関数 /20','候補から選択 /20','複数呼び出し /20','呼び出し不要 /20'],[[m['model']]+[m['bfcl_categories'][k]['passed'] for k in ['simple_python','multiple','parallel','irrelevance']] for m in models])
change=table(['モデル','HE OFF 4096→大出力','HE ON 4096→大出力','BFCL 1024→大出力'],[[m['model'],str(m['previous_human_eval']['off']['passed'])+' → '+str(m['human_eval']['off']['passed']),str(m['previous_human_eval']['on']['passed'])+' → '+str(m['human_eval']['on']['passed']),str(m['previous_bfcl']['passed'])+' → '+str(m['bfcl']['passed'])] for m in models])
budget=table(['モデル','HE ON 最大実生成token','HE ON 上限到達 /20','HE ON 最終回答欄が空 /20','HE ON 中央値 秒'],[[m['model'],m['human_eval']['on']['maximum_actual_output_tokens'],m['human_eval']['on']['output_cap_hits'],m['human_eval']['on']['no_final_code'],round(m['human_eval']['on']['median_seconds'],2)] for m in models])
performance=table(['モデル','HE OFF 中央値 秒','HE ON 中央値 秒','BFCL 中央値 秒','HE ON 生成token/秒','システム全体GPU最大 MiB','空きRAM最小 GiB'],[[m['model'],round(m['human_eval']['off']['median_seconds'],2),round(m['human_eval']['on']['median_seconds'],2),round(m['bfcl']['median_seconds'],2),round(m['human_eval']['on']['tokens_per_second'],1),m['memory']['peak_gpu_used_mib_system_total'],round(m['memory']['minimum_available_ram_bytes']/1024**3,2)] for m in models])
all_budget=table(['モデル','HE OFF 上限到達 /20','HE ON 上限到達 /20','BFCL 上限到達 /80','HE ON reasoning欄あり /20'],[[m['model'],m['human_eval']['off']['output_cap_hits'],m['human_eval']['on']['output_cap_hits'],m['bfcl']['output_cap_hits'],m['human_eval']['on']['reasoning_observed_cases']] for m in models])
pairtable=table(['量子化','課題','両方正解','Textのみ','VLのみ','両方不正解'],[[p[k] for k in ['quantization','benchmark','both_pass','text_only','vl_only','both_fail']] for p in pairs])
doc='''<!doctype html><html lang="ja"><meta charset="utf-8"><title>64Kコンテキスト・大出力予算 ベンチマーク再測定</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:1200px;margin:36px auto;padding:0 24px;color:#182a3b}table{border-collapse:collapse;width:100%;margin:24px 0 36px;font-size:14px}td,th{padding:9px;border:1px solid #d3dce6;text-align:left}th{background:#edf2f7}.note{background:#fff5dc;padding:16px}</style><h1>64Kコンテキスト・大出力予算での再測定</h1><p>6構成を新しく測定。総コンテキスト65,536、1 slot、出力上限は最大64,000。入力を実際にテンプレート展開・トークン化し、入力＋出力が総枠を超えないよう余裕を確保した。</p><p class="note">64Kは利用可能な総枠です。問題文を64Kまで水増しする長文読解試験ではありません。出力は毎回64,000生成させず、モデルが終了するまで待ちます。すべてb11960 CUDA 12.4で新規測定。Qwenの前回値はb11946のため、前回との差にはruntime変更の影響も含みます。</p>'''
doc+='<h2>今回の正解数</h2>'+score+'<h2>BFCLの内訳</h2>'+categories+'<h2>前回との比較</h2>'+change+'<h2>思考ONの実際の出力量と打切り</h2>'+budget+all_budget+'<h2>所要時間・生成速度・メモリ</h2><p>モデル準備後の定期サンプルであり、瞬間的なメモリピークや起動時ピークを保証しません。Qwen 35Bは30層のMoE重みをCPUに配置。他の5構成は言語モデルを全GPU配置。トークナイザーも異なるためtoken/秒は直接的な処理能力順位ではありません。</p>'+performance+'<h2>Text / VLの同一問題比較</h2>'+pairtable
if audit_path.exists():
    doc+='<h2>採点器の許可範囲の感度確認</h2><p>元条件を保持し、type() と operator.mul/add のみ許可した補助再採点。再生成はしていません。</p>'+table(['モデル','OFF 元→補助','ON 元→補助'],[[labels[k],str(v['off']['original_passed'])+' → '+str(v['off']['secondary_passed']),str(v['on']['original_passed'])+' → '+str(v['on']['secondary_passed'])] for k,v in audit['models'].items()])
doc+='<h2>測定条件と限界</h2><ul><li>HumanEvalは同じ選択20問、思考ON/OFF、temperature 0.6、top_p 0.95、top_k 20、seed 42。前回と同じ制限付き採点器。BFCLは同じ選択80問、temperature 0、思考OFF、ツール実行なし。</li><li>出力予算は思考と最終回答で共有。独立した思考予算は無制限（-1）。1要求の待機上限は3600秒。上限到達と不正解は別記録。</li><li>VLはF16画像処理モデルを読み込むが、入力はテキストのみ。Text/VLは追加学習も違うため、差を画像対応そのものだけに帰属しない。</li><li>各条件1試行・少数選択課題。公式フルスコア、一般的な言語能力順位、長文読解品質、Hermesの動作確認ではない。</li></ul><p><a href="results.json">全結果</a> / <a href="summary.json">集計JSON</a> / <a href="sources.zip">再現用ソース</a></p></html>'
report_name='lfm3-stage-report.html' if stage else 'report.html'
if stage:
    status_note='全6構成の測定が完了しました。<a href="report.html">全体レポートはこちら</a>。' if all_done else 'Qwenの新規測定は継続中です。'
    doc=doc.replace('6構成を新しく測定。','LFMの4構成の測定が完了。'+status_note+'このページはLFMステージのみの結果です。').replace('href="summary.json"','href="'+summary_name+'"').replace('<a href="sources.zip">再現用ソース</a>','<a href="runner-started.py">LFMステージのソース</a>')
(run/report_name).write_text(doc,encoding='utf-8')
print(json.dumps({'report':str(run/report_name),'models':[{'model':m['model'],'off':m['human_eval']['off']['passed'],'on':m['human_eval']['on']['passed'],'bfcl':m['bfcl']['passed'],'on_cap_hits':m['human_eval']['on']['output_cap_hits']} for m in models]},ensure_ascii=False))
