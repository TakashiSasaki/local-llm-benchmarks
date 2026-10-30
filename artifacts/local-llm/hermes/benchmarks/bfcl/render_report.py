"""Render the recorded BFCL subset comparison without changing any model responses."""
import html
import json
from pathlib import Path
import sys

run=Path(sys.argv[1]);report=json.loads((run/'results.json').read_text(encoding='utf-8'));models=report['models']
esc=lambda v:html.escape(str(v))
labels={'daily':'Qwen3.5-4B / Q4_K_M','large':'Qwen3.6-35B-A3B / UD-Q3_K_M'}
categories={'simple_python':'単一ツール','multiple':'複数候補から選択','parallel':'複数回の呼び出し','irrelevance':'不要な呼び出しの抑制'}
summary=[]
for key,m in models.items():
    s=m['summary'];summary.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [labels[key],f"{s['passed']}/{s['attempted']}",s['median_seconds'],s['total_seconds'],s['generation_tokens_per_second'],s['minimum_available_ram_gib'],s['maximum_system_gpu_mib']])+'</tr>')
parts=['<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BFCL 4B・35B 比較</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1150px;margin:40px auto;padding:0 24px;background:#f5f7fa;color:#18212b}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}th,td{padding:10px;border-bottom:1px solid #dce2e8;text-align:left}th{background:#e6edf5}details{padding:12px;background:white;border-radius:6px;margin:8px 0}pre{white-space:pre-wrap;background:#17212b;color:#eaf0f8;padding:16px;overflow:auto}.pass{color:#167347}.fail{color:#a52c33}.scroll{overflow:auto}</style><h1>BFCL：4B・35B ツール呼び出し比較</h1><p>公式データから4分類×20問を固定抽出し、各モデルに1回ずつ質問しました。呼び出し先・引数を評価し、外部ツールは実行していません。フル版リーダーボードのスコアではありません。</p><div class="scroll"><table><tr><th>構成</th><th>正解数</th><th>応答中央値 秒</th><th>全80問 秒</th><th>生成 token/秒</th><th>最小空きRAM GiB</th><th>最大システムGPU MiB</th></tr>'+''.join(summary)+'</table></div><h2>分類別</h2><table><tr><th>分類</th><th>4B</th><th>35B</th></tr>']
for category,label in categories.items():
    cells=[]
    for key in ['daily','large']:
        s=models[key]['categories'][category];cells.append('<td>'+esc(f"{s['passed']}/{s['attempted']}")+'</td>')
    parts.append('<tr><td>'+esc(label)+'</td>'+''.join(cells)+'</tr>')
parts.append('</table><h2>条件と採点</h2><ul><li>同じ80問、同じ質問・関数定義。各分類でseed 42により20行を選択。temperature 0、思考OFF、出力上限1024、tool_choice=auto、並列呼び出しON。</li><li>BFCL公式のPython AST採点コードを変更せず使用。関数定義のOpenAI形式への変換も、公式の変換関数をそのまま使用。ローカルモデル用に名前のドット→下線変換の登録情報だけを補っています。</li><li>公式の全CLIではなく、このPCのllama-serverへ接続する軽量アダプターを使用。80件の正解例が合格し、空の呼び出し等の不正例が不合格になることを生成前に確認。</li><li>抑制問題では呼び出しゼロを要求。不正JSON呼び出しを「適切な抑制」として加点しません。公式のデコード失敗時の扱いより厳密です。不正出力の件数は詳細JSONに記録。</li><li>実際のメッセージ送信・予約・外部API操作は行っていません。Hermes全体の自律作業や複数ターンの性能を測ったものではありません。</li><li>両方とも64Kコンテキスト・同一llama.cpp b11946。4BはGPU、35Bは既存のCPU混在設定。世代・量子化・配置が違うため、パラメーター数だけの比較ではありません。</li><li>モデル順は4B→35B。1問1回・小規模抽出で、熱・他アプリ等は完全には統制していません。RAM/GPU値はシステム全体の定期観測で、モデル単体の割り当て量・厳密なピークではありません。</li></ul>')
problems={}
for category in report['categories']:
    path=run.parent/'bfcl_eval/data'/('BFCL_v4_'+category+'.json')
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            p=json.loads(line);problems[p['id']]=p
parts.append('<h2>問題別結果と応答</h2><p>項目を開くと、質問・呼び出し・採点理由を確認できます。</p>')
for task_id in report['selected_ids']:
    entries={key:next(c for c in m['cases'] if c['id']==task_id) for key,m in models.items()}
    title=task_id+' — '+ ' / '.join(('4B' if key=='daily' else '35B')+(': 合格' if r['passed'] else ': 不合格')+f" ({r['seconds']}秒)" for key,r in entries.items())
    parts.append('<details><summary>'+esc(title)+'</summary><p>'+esc(problems[task_id]['question'][0][0]['content'])+'</p>')
    for key,r in entries.items():
        parts.append('<h3>'+esc(labels[key])+'</h3><pre>'+esc(json.dumps({'calls':r['decoded'],'text':r['message'].get('content'),'grade':r['grade']},ensure_ascii=False,indent=2))+'</pre>')
    parts.append('</details>')
parts.append('<h2>再現情報</h2><p>上流commit: '+esc(report['commit'])+'</p><p>データと採点コードのSHA-256、全応答、実行設定、メモリ記録は <a href="results.json">results.json</a> と同じフォルダーに保存しています。</p><p><a href="https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard">BFCL公式</a></p></html>')
(run/'report.html').write_text(''.join(parts),encoding='utf-8')
print(json.dumps({'report':str(run/'report.html'),'models':{key:{'summary':m['summary'],'categories':m['categories']} for key,m in models.items()}},ensure_ascii=False))
