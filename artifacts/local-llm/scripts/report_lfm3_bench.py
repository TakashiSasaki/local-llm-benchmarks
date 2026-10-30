"""Summarize completed local LFM3 Text/VL and historical Qwen results."""
import html,json,pathlib,statistics,sys
from install_lfm3_runtime import save
root=pathlib.Path(r'C:\LocalLLM');run=pathlib.Path(sys.argv[1]);r=json.loads((run/'results.json').read_text(encoding='utf-8'))
assert 'error' not in r and len(r['models'])==4
labels={'lfm3':'LFM3 Text QAD 4bit','lfm3-vl-q4':'LFM3 VL QAD 4bit','lfm3-q8':'LFM3 Text Q8_0','lfm3-vl-q8':'LFM3 VL Q8_0'}
def aggregate(entries):
    timings=[e['timings'] for e in entries if e.get('timings')];ms=sum(t.get('predicted_ms',0) for t in timings)
    return {'passed':sum(e['passed'] for e in entries),'total':len(entries),'median_seconds':statistics.median(e['seconds'] for e in entries),'tokens_per_second':sum(t.get('predicted_n',0) for t in timings)/ms*1000 if ms else None,'output_cap_hits':sum(e.get('finish_reason')=='length' for e in entries),'reasoning_observed_cases':sum(bool(e.get('reasoning_observed')) for e in entries),'guard_rejections':sum(e.get('failure_kind')=='guard_rejected' for e in entries)}
rows=[]
for key,m in r['models'].items():
    assert len(m['human_eval']['off'])==20 and len(m['human_eval']['on'])==20 and len(m['bfcl'])==80 and m.get('test_server_stopped')
    rows.append({'key':key,'model':labels[key],'human_eval_off':aggregate(m['human_eval']['off']),'human_eval_on':aggregate(m['human_eval']['on']),'bfcl':aggregate(m['bfcl']),'bfcl_categories':m['summary']['bfcl_categories'],'memory':m['memory'],'runtime':m['runtime']})
he=json.loads(pathlib.Path(r['human_eval_reference']).read_text(encoding='utf-8'));bf=json.loads(pathlib.Path(r['bfcl_reference']).read_text(encoding='utf-8'))
qwen=[]
for key,label in [('daily','Qwen3.5-4B Q4_K_M'),('large','Qwen3.6-35B-A3B UD-Q3_K_M')]:
    qwen.append({'model':label,'human_eval_off':aggregate(he['models'][key]['modes']['off']),'human_eval_on':aggregate(he['models'][key]['modes']['on']),'bfcl':aggregate(bf['models'][key]['cases']),'runtime':'b11946 (historical)'})
def paired(a,b,idkey):
    aa={x[idkey]:x['passed'] for x in a};bb={x[idkey]:x['passed'] for x in b};assert aa.keys()==bb.keys()
    return {'both_pass':sum(aa[i] and bb[i] for i in aa),'text_only_pass':sum(aa[i] and not bb[i] for i in aa),'vl_only_pass':sum(not aa[i] and bb[i] for i in aa),'both_fail':sum(not aa[i] and not bb[i] for i in aa)}
pairs=[]
for text,vl,quant in [('lfm3','lfm3-vl-q4','QAD-Q4_0'),('lfm3-q8','lfm3-vl-q8','Q8_0')]:
    for mode in ['off','on']:pairs.append({'quantization':quant,'benchmark':'HumanEval '+mode,**paired(r['models'][text]['human_eval'][mode],r['models'][vl]['human_eval'][mode],'task_id')})
    pairs.append({'quantization':quant,'benchmark':'BFCL off',**paired(r['models'][text]['bfcl'],r['models'][vl]['bfcl'],'id')})
summary={'models':rows,'historical_qwen':qwen,'text_vl_paired':pairs,'all_original_settings_unchanged':all(r['settings_unchanged'].values()),'human_eval_cases':20,'bfcl_cases':80,'source':str(run/'results.json'),'limits':r['limits']+['Text and VL are differently post-trained checkpoints. Differences do not isolate the causal effect of adding vision.','OFF means enable_thinking=False, not proof of absence of prose deliberation. Actual reasoning fields are counted separately.','HumanEval sampling matches the previous Qwen comparison, not per-model recommended-parameter optimization.']}
assert summary['all_original_settings_unchanged'];save(run/'summary.json',summary)
esc=lambda x:html.escape(str(x))
def table(headers,body):return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in body)+'</tbody></table>'
allrows=qwen+rows
score=table(['モデル','HumanEval OFF /20','HumanEval ON /20','BFCL OFF /80','runtime'],[[m['model'],m['human_eval_off']['passed'],m['human_eval_on']['passed'],m['bfcl']['passed'],m['runtime']] for m in allrows])
timing=table(['モデル','HE OFF 中央値 秒','HE ON 中央値 秒','BFCL 中央値 秒','HE ON 上限到達 /20'],[[m['model'],round(m['human_eval_off']['median_seconds'],2),round(m['human_eval_on']['median_seconds'],2),round(m['bfcl']['median_seconds'],2),m['human_eval_on']['output_cap_hits']] for m in allrows])
pairtable=table(['量子化','課題','両方正解','Textのみ正解','VLのみ正解','両方不正解'],[[p[k] for k in ['quantization','benchmark','both_pass','text_only_pass','vl_only_pass','both_fail']] for p in pairs])
bfcat=table(['モデル','単一ツール /20','候補選択 /20','複数呼出 /20','呼出不要 /20'],[[m['model']]+[m['bfcl_categories'][c]['passed'] for c in ['simple_python','multiple','parallel','irrelevance']] for m in rows])
details=''
for key,m in r['models'].items():
    failures=[]
    for mode,entries in m['human_eval'].items():
        for e in entries:
            if not e['passed']:failures.append(['HumanEval '+mode,e['task_id'],e.get('failure_kind'),e.get('grade',{}).get('detail',''),e['finish_reason']])
    for e in m['bfcl']:
        if not e['passed']:failures.append(['BFCL OFF',e['id'],e['failure_kind'],str(e['grade'].get('error','')),e['finish_reason']])
    details+='<details><summary>'+esc(labels[key])+' の失敗ケース</summary>'+table(['試験','ID','分類','採点詳細','終了理由'],failures)+'</details>'
doc='''<!doctype html><html lang="ja"><meta charset="utf-8"><title>LFM3 Text / VL テキスト能力比較</title><style>body{font:16px/1.65 system-ui,sans-serif;max-width:1250px;margin:36px auto;padding:0 24px;color:#172332}table{border-collapse:collapse;width:100%;margin:20px 0 32px;font-size:14px}th,td{border:1px solid #d7dee7;padding:9px;text-align:left;vertical-align:top}th{background:#eef3f8}td{overflow-wrap:anywhere}h1,h2{line-height:1.3}details{margin:20px 0}p,li{max-width:1050px}.note{background:#fff6df;padding:16px}</style><h1>LFM3 Text / VL テキスト能力比較</h1><p>このPCで同一のテキスト課題を実行。Text/VL × QAD 4bit/Q8_0 の4構成。画像入力なし。Qwenは保存済みの同一問題・採点条件の結果。</p><p class="note">HumanEvalは選択20問、BFCLは選択80問の各1試行。公式フルスコアではありません。Text/VLは追加学習も異なるため、差を視覚機能の追加だけに帰属できません。</p>'''
doc+='<h2>正解数</h2>'+score+'<h2>TextとVLの同一問題での比較</h2>'+pairtable+'<h2>BFCLの内訳</h2>'+bfcat+'<h2>応答時間と出力上限</h2>'+timing
text_wins=sum(p['text_only_pass']>p['vl_only_pass'] for p in pairs)
vl_wins=sum(p['vl_only_pass']>p['text_only_pass'] for p in pairs)
lead=f'<p><strong>今回の6条件では、Text専用版が高得点だった条件は{text_wins}、VL版が高得点だった条件は{vl_wins}でした。</strong>TextはLFM3-1.7B、VLはLFM3-VL-2Bです。これはコード生成・関数呼び出しの選択課題での結果で、日本語一般能力や文章読解全般の順位ではありません。</p>'
doc=doc.replace('<h2>正解数</h2>',lead+'<h2>正解数</h2>',1)
doc+='<h2>条件と読み方</h2><ul><li>HumanEval: 前回と同じ20問・制限付き採点器。temperature 0.6、seed 42、4096出力トークン。思考ON/OFFの実行順は問ごとに交互。</li><li>BFCL: 前回と同じ4カテゴリ各20問、temperature 0、1024出力トークン、思考OFF指定。ツールは実行せず、公式ASTチェッカーで呼出内容を採点。</li><li>共通: context 65536、1 slot、同じb11960 CUDA 12.4。VLはF16画像処理モデルも読み込むが入力はテキストのみ。</li><li>Qwenの旧結果はb11946。runtime・量子化・CPU/GPU配置が異なるため、速度差をモデルだけの差とは扱わない。</li><li>OFF指定でも説明文中で検討を続ける場合がある。reasoning_contentの有無は別記録。ONの思考も4096トークンに含む。未完了の思考からコードを救済しない。</li><li>採点器の許可構文・import制限により実行拒否になる場合がある。モデルの誤りと区別して失敗分類を保持。</li><li>メモリは周期観測のシステム値で、厳密なピークではない。</li></ul>'
doc+='<h2>失敗ケース</h2>'+details+'<p>詳細: <a href="results.json">results.json</a> / <a href="summary.json">summary.json</a> / <a href="sources.zip">sources.zip</a></p></html>'
audit_path=run/'grader-sensitivity/results.json'
if audit_path.exists():
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    name_map={**labels,'qwen_daily':'Qwen3.5-4B Q4_K_M','qwen_large':'Qwen3.6-35B-A3B UD-Q3_K_M'}
    sensitivity=table(['モデル','OFF 元条件 → 追加許可','ON 元条件 → 追加許可'],[[name_map[k],str(v['off']['original_passed'])+' → '+str(v['off']['secondary_passed']),str(v['on']['original_passed'])+' → '+str(v['on']['secondary_passed'])] for k,v in audit['models'].items()])
    extra='<h2>採点器の許可範囲による影響</h2><p>元の得点を保持したまま、type() と operator.mul/add を許可して、全モデルの保存済み不合格コードを同条件で再採点した感度確認。生成のやり直しはしていません。新しい得点で元の結果を上書きしません。</p>'+sensitivity+'<p><a href="grader-sensitivity/results.json">再採点の詳細</a></p>'
    doc=doc.replace('</html>',extra+'</html>')
    summary['grader_sensitivity']={k:{mode:{field:v[field] for field in ['original_passed','secondary_passed','rescued_ids']} for mode,v in modes.items()} for k,modes in audit['models'].items()};save(run/'summary.json',summary)
(run/'report.html').write_text(doc,encoding='utf-8')
print(json.dumps({'report':str(run/'report.html'),'models':[{k:m[k] for k in ['model','human_eval_off','human_eval_on','bfcl']} for m in allrows],'pairs':pairs},ensure_ascii=False))
