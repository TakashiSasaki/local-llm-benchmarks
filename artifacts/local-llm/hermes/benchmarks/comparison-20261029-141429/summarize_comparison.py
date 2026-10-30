"""Verify model routing, add speed metrics, and render a local benchmark report."""
from pathlib import Path
import html
import json
import sqlite3
import sys
import hashlib

run=Path(sys.argv[1]); report=json.loads((run/'results.json').read_text(encoding='utf-8'))
install=json.loads((run.parent.parent/'installation.json').read_text(encoding='utf-8'))
db=sqlite3.connect((Path(install['hermes_home'])/'state.db').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
for key,model in report['models'].items():
    for task in model['hermes']:
        if task['session_id']:
            session=db.execute('SELECT id,model,billing_base_url FROM sessions WHERE id=?',(task['session_id'],)).fetchone()
            task['session_identity']=dict(session)
            task['session_identity_verified']=session['model']==model['alias'] and session['billing_base_url']=='http://127.0.0.1:8089/v1'
            task['passed']=task['passed'] and task['session_identity_verified']
        else:task['session_identity_verified']=False;task['passed']=False
        if task['task']=='csv' and isinstance(task.get('artifact'),dict):
            values=task['artifact'].get('totals_cents',{})
            values={k:(v.get('total_cents') if isinstance(v,dict) else v) for k,v in values.items()}
            task['numeric_totals_correct']=values=={'A':315,'B':210} and task['artifact'].get('paid_orders')==4
    timings=[r['timings'] for r in model['humaneval'] if r.get('timings')]
    tokens=sum(t.get('predicted_n',0) for t in timings);ms=sum(t.get('predicted_ms',0) for t in timings)
    model['summary']['generation_tokens_per_second']=round(tokens/ms*1000,2) if ms else None
    model['summary']['hermes_passed']=sum(t['passed'] for t in model['hermes'])
    model['summary']['truncated_answers']=sum(t.get('finish_reason')=='length' for t in model['humaneval'])
    model['summary']['guard_rejections']=[{'task_id':t['task_id'],'detail':t.get('detail')} for t in model['humaneval'] if t['status']=='guard_rejected']
db.close()
report['evaluation_method']='Official HumanEval tests, seed-42 subset of 20, custom chat-format prompting and deterministic code-fence/signature extraction. Canonical solutions all passed before model evaluation. Worker: 6-second timeout, 256-MiB Windows process-job memory limit, one process, restricted Python imports/builtins/AST. Not the original official CLI or full leaderboard protocol.'
report['hardware']='ASUS TUF A15 FA507XI; Ryzen 9 7940HS; 32 GiB installed RAM; RTX 4070 Laptop 8188 MiB; native Windows.'
report['source_archives']={}
for source in ['compare_models.py','grade_worker.py','summarize_comparison.py']:
    data=(run.parent/source).read_bytes()
    (run/source).write_bytes(data)
    report['source_archives'][source]=hashlib.sha256(data).hexdigest()
if report.get('schema_retry'):
    report['memory_measurement_scope']='Worst observed across original run and schema retry; HumanEval and repair measured in original run, JSON/CSV strict scores use clarified retry.'
(run/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
esc=lambda value:html.escape(str(value))
models=report['models']; names={'daily':'Qwen3.5-4B Q4_K_M','large':'Qwen3.6-35B-A3B UD-Q3_K_M'}
rows=[]
for key,m in models.items():
    s=m['summary']
    rows.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in [names[key],f"{s['humaneval_passed']}/{s['humaneval_attempted']}",f"{s['hermes_passed']}/{s['hermes_attempted']}",s['humaneval_median_seconds'],s['generation_tokens_per_second'],s['hermes_total_seconds'],m['minimum_available_ram_gib'],m['maximum_system_gpu_mib']])+'</tr>')
parts=['<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Qwen 4B・35B ローカル比較</title><style>body{font:16px/1.6 system-ui,sans-serif;background:#f6f7f9;color:#18212b;max-width:1200px;margin:40px auto;padding:0 24px}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}th,td{border-bottom:1px solid #dce2e8;text-align:left;padding:10px}th{background:#e9eef4}pre{white-space:pre-wrap;background:#17212b;color:#e7edf3;padding:16px;overflow:auto}.pass{color:#147846}.fail{color:#b63737}details{background:white;padding:12px;margin:8px 0;border-radius:6px}small{color:#586775}.scroll{overflow:auto}</style><h1>Qwen 4B・35B：このPCでの比較</h1><p>HumanEval公式データの固定20問と、Hermes独自3課題。各1回。フル版・公式リーダーボードの成績ではありません。</p><div class="scroll"><table><tr><th>構成</th><th>HumanEval</th><th>Hermes</th><th>コード応答中央値 秒</th><th>生成 token/秒</th><th>Hermes合計 秒</th><th>最小空きRAM GiB</th><th>最大システムGPU MiB</th></tr>'+''.join(rows)+'</table></div>']
if report.get('schema_retry'):
    original=Path(report['schema_retry']['original_run']).name
    parts.append('<p><strong>採点仕様の修正：</strong>初回のJSON/CSV指示にキー名・値の形の曖昧さがありました。そのため両モデルに同じ明示スキーマを提示して2課題ずつ再測定し、その結果を最終採点に使いました。HumanEvalとパッチ課題は初回の結果をそのまま使用しています。<a href="../'+esc(original)+'/results.json">初回の全記録</a>も保存済みです。メモリ欄は両測定を合わせた最悪観測値です。</p>')
parts.append('<h2>比較条件と解釈</h2><ul><li>同じ20問、同じプロンプト、temperature=0、seed=42、思考OFF、最大1024出力トークン。モデルを順に1つずつ起動。</li><li>Hermesは同じ既存設定、思考ON。ファイル操作・端末・パッチを実行し、成果物とstate.dbのツール結果を独立確認。</li><li>両モデルとも64Kコンテキスト設定。64Kを埋める長文試験ではありません。</li><li>世代・量子化・GPU/CPU配置が異なります。パラメーター数だけの効果ではなく、このPCに導入した2構成の比較です。</li><li>各課題1回・20問の小規模試験です。メモリは定期採取で、モデル単体の使用量・厳密なピークではありません。</li><li>4B→35Bの順。温度・他アプリ等の影響を完全には統制していません。</li></ul>')
parts.append('<h2>HumanEval 問題別結果</h2><table><tr><th>問題</th><th>4B</th><th>35B</th></tr>')
for task_id in report['task_ids']:
    cells=[]
    for key in ['daily','large']:
        r=next(r for r in models[key]['humaneval'] if r['task_id']==task_id)
        label=('合格' if r['passed'] else '不合格')+' / '+str(r['seconds'])+'秒'
        if r.get('finish_reason')=='length':label+=' / 出力上限'
        cells.append('<td class="'+('pass' if r['passed'] else 'fail')+'">'+esc(label)+'</td>')
    parts.append('<tr><td>'+esc(task_id)+'</td>'+''.join(cells)+'</tr>')
parts.append('</table><h2>Hermes 作業結果</h2>')
for key,m in models.items():
    parts.append('<h3>'+esc(names[key])+'</h3><ul>')
    for r in m['hermes']:
        label=f"{r['task']}: {'合格' if r['passed'] else '不合格'} / {r['seconds']}秒 / 成果物={r['artifact_correct']} / ツール手順={r['workflow_correct']}"
        if r['task']=='csv':label+=f" / 計算値={r.get('numeric_totals_correct')}"
        parts.append('<li>'+esc(label)+'</li>')
    parts.append('</ul>')
parts.append('<h2>失敗した回答を確認</h2>')
for key,m in models.items():
    for r in m['humaneval']:
        if not r['passed']:parts.append('<details><summary>'+esc(names[key]+' / '+r['task_id']+' / '+r['status'])+'</summary><p>'+esc(r.get('detail',''))+'</p><pre>'+esc(r['code'])+'</pre></details>')
parts.append('<h2>再現情報</h2><p>'+esc(report['hardware'])+'</p><p>HumanEval revision: '+esc(report['dataset_commit'])+'<br>dataset SHA-256: '+esc(report['dataset_sha256'])+'</p><p>選択seed: 42、公式データの行番号からrandom.sampleで20件を抽出して昇順。検証スクリプトは親フォルダに保存。</p><p><a href="https://github.com/openai/human-eval">HumanEval公式（古典的指標・現在は保守終了）</a> / <a href="https://gorilla.cs.berkeley.edu/leaderboard.html">BFCL</a> / <a href="https://github.com/harbor-framework/terminal-bench">Terminal-Bench</a></p><p><a href="results.json">詳細JSON</a></p></html>')
(run/'report.html').write_text(''.join(parts),encoding='utf-8')
print(json.dumps({k:{**m['summary'],'minimum_available_ram_gib':m['minimum_available_ram_gib'],'maximum_system_gpu_mib':m['maximum_system_gpu_mib']} for k,m in models.items()},ensure_ascii=False))
