"""Rebuild the offline cross-study comparison from saved evidence; no inference."""
import csv
import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.comprehensive import collect, KEYS
from local_llm_benchmarks.study import ROOT, save

OUTPUT = ROOT / 'reports/comprehensive'

STYLE = '''
:root{color-scheme:light;--ink:#152b39;--muted:#526b78;--line:#d9e4e9;--teal:#087e83}*{box-sizing:border-box}
body{margin:0;background:#f4f7fa;color:var(--ink);font:15px/1.65 system-ui,sans-serif}a{color:#006f79}button,input,select{font:inherit}
header{padding:30px max(20px,calc((100vw - 1420px)/2));background:#102d3c;color:#edf8fc}header a{color:#9be5df}h1{font-size:clamp(24px,3vw,36px);line-height:1.3;margin:12px 0}h2{font-size:22px;margin:0 0 12px}h3{font-size:17px}
header p{max-width:1000px;color:#c6dae4}main{max-width:1460px;margin:auto;padding:22px 20px}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:0 0 22px}.metric{padding:16px;background:white;border:1px solid var(--line);border-radius:10px}.metric strong{display:block;font-size:28px;line-height:1.2}.metric span,small,.note{color:var(--muted)}
nav,.filters{display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin:12px 0 20px}button,select,input{border:1px solid #b9cbd4;background:white;border-radius:6px;padding:8px 11px;color:var(--ink)}button{cursor:pointer}button[aria-selected=true]{background:var(--teal);color:white;border-color:var(--teal)}button:focus-visible,a:focus-visible{outline:3px solid #edac46;outline-offset:2px}label{display:grid;gap:3px;font-size:13px}.filters input{min-width:260px}section,.box{background:white;border:1px solid var(--line);border-radius:10px;padding:20px;margin:16px 0}section[hidden]{display:none}.scroll{overflow:auto;max-height:650px;border:1px solid var(--line);border-radius:6px}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}thead th{position:sticky;top:0;background:#eaf2f5;z-index:2;white-space:nowrap}th button{padding:0;border:0;background:transparent;font-weight:700;border-radius:0}tbody tr:hover{background:#f0f8f8}.primary{min-width:1290px}td small{display:block}.rowmodel{min-width:235px;max-width:285px}.score{white-space:nowrap;font-variant-numeric:tabular-nums}.partial{color:#8b5010}.pill{display:inline-block;border-radius:4px;padding:1px 6px;background:#e9f1f5;font-size:12px}.complete{color:#06644f;background:#e1f3eb}.failed{color:#923c2f;background:#fcebe5}.speed-only{color:#405597;background:#edf0fd}.warning{border-left:4px solid #d18a22;padding:9px 12px;background:#fff8eb}.detailgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.detailgrid pre{margin:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:12px;font-size:12px}summary{cursor:pointer;font-weight:600}code{overflow-wrap:anywhere}.heat{width:max-content;min-width:100%;font-size:11px}.heat td,.heat th{padding:3px;text-align:center}.heat th:first-child{min-width:260px;text-align:left}.heat td{min-width:24px}.heat .ok{background:#ddf0e9;color:#08694c}.heat .bad{background:#f8ddd9;color:#9a352d}.heat .cap{background:#ffe4ad;color:#7c4d00}.heat .unknown{background:#edf0f3;color:#75818b}.heat a{display:block;color:inherit;text-decoration:none}.legend{display:flex;gap:16px;flex-wrap:wrap}.muted{color:var(--muted)}.wrap{overflow-wrap:anywhere}.index{min-width:750px}.compact{max-height:440px}.empty{padding:24px;color:var(--muted)}
@media(max-width:800px){.metrics{grid-template-columns:repeat(2,1fr)}.metric:last-child{grid-column:1/-1}.detailgrid{grid-template-columns:1fr}main{padding:12px}section{padding:14px}.filters label,.filters input{width:100%;min-width:0}nav button{flex:1;white-space:nowrap;font-size:13px}header{padding:22px 18px}}
'''

TEMPLATE = '''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ローカルLLM・全測定比較</title><style>STYLE</style></head><body>
<header><a href="../../index.html">測定カタログ</a> / <a href="../../README.md">README</a><h1>ローカルLLM・全測定比較</h1><p>モデル・量子化・MTP・思考OFF/ONを、配置と測定条件を保ったまま横断する。RTX 4070 Laptop 8 GB / Ryzen 9 7940HS / RAM 32 GiB。保存済み記録から再集計。</p><a href="summary.md">比較表 Markdown</a> · <a href="conditions.csv">全条件 CSV</a> · <a href="results.json">集計 JSON</a> · <a href="../../docs/COMPREHENSIVE_COMPARISON.md">読み方・再生成</a></header>
<main><div class="metrics" id="metrics"></div><p class="note">主比較は b11960、コンテキスト65,536、最大出力64,000、F16 KV。固定 HumanEval 20問 / BFCL 80問の部分集合です。配置・ロード方式・配布重みが異なる行を含むため、単一のモデル順位とは扱いません。</p>
<nav aria-label="表示切り替え"><button data-tab="comparison" aria-selected="true">測定比較</button><button data-tab="cases" aria-selected="false">問題別</button><button data-tab="coverage" aria-selected="false">網羅性</button><button data-tab="historical" aria-selected="false">旧条件</button><button data-tab="inventory" aria-selected="false">検証・全記録</button></nav>
<div class="filters"><label>検索（モデル・run・量子化）<input id="search" type="search" placeholder="例: Qwen、Mage、IQ3_M"></label><label>モデル<select id="model"><option value="">すべて</option></select></label><label>MTP<select id="mtp"><option value="">すべて</option><option value="off">OFF</option><option value="on">ON</option></select></label><label>測定<select id="kind"><option value="">すべて</option><option value="complete">能力4条件完了</option><option value="incomplete">能力測定に未完了あり</option><option value="speed-only">速度だけ</option></select></label><button id="reset">解除</button></div>
<section id="comparison"><h2>配置を含む測定単位の比較</h2><p id="shown" role="status"></p><p class="note">列見出しで並べ替え。数値は主採点の正解数。未完了は保存分だけを表示し、全問の正答率に換算しません。MTPと思考は別の設定です。</p><div class="scroll"><table class="primary" id="main-table"><thead><tr><th><button data-sort="model">モデル / 量子化 ↕</button></th><th><button data-sort="mtp">MTP ↕</button></th><th>CPU / GPU配置<br>load-mode・threads</th><th><button data-sort="bfcl_off">BFCL OFF /80 ↕</button></th><th><button data-sort="bfcl_on">BFCL ON /80 ↕</button></th><th><button data-sort="he_off">HE OFF /20 ↕</button></th><th><button data-sort="he_on">HE ON /20 ↕</button></th><th><button data-sort="speed">固定長 tok/s ↕</button></th><th>収集状態 / 詳細</th></tr></thead><tbody></tbody></table></div><p class="warning">BFCLは呼び出し形式・引数の採点です。irrelevance 20問は「呼び出さない」が正解となり、出力上限で最終回答が空でも採点上は正解になる例があります。実際のツール実行の成功とは区別してください。</p><div id="details" class="box" aria-live="polite"></div></section>
<section id="cases" hidden><h2>同じ問題に対する成否</h2><div class="filters"><label>試験・思考<select id="case-key"><option value="bfcl_off">BFCL 思考OFF</option><option value="bfcl_on">BFCL 思考ON</option><option value="he_off">HumanEval 思考OFF</option><option value="he_on">HumanEval 思考ON</option></select></label></div><p class="legend"><span>緑 ✓ 正解</span><span>赤 × 不正解</span><span>黄 ! 出力上限（採点の成否は別）</span><span>灰 — 応答未保存 / 未実施</span></p><p class="note">各マスは生のリクエスト・応答へリンク。HTTP500形式エラーは不正解で、トークン数・終了理由が欠ける場合は不明です。</p><div id="heatmap" class="scroll"></div><h3>完了条件での失敗が多い問題</h3><p class="note">分母は表示中の完了測定行です。同じモデルの再測定・配置違いを含み、独立したモデル数を意味しません。未完了行は集計しません。</p><div id="failures"></div></section>
<section id="coverage" hidden><h2>測れた組み合わせ・残っている組み合わせ</h2><p class="note">モデル×量子化×MTPの棚卸しです。主比較の重複行はここでは同じ組み合わせにまとめます。「未測定」は対応保証・追加測定の予定を意味しません。速度だけ成功した条件にも能力得点は付けません。検索・モデル・MTPのフィルターが適用されます。</p><div id="coverage-table" class="scroll"></div></section>
<section id="historical" hidden><h2>旧ランタイム・旧出力予算の参考表</h2><p class="note">主比較の94完了条件や4,776応答には加算しません。再掲された同一応答スナップショットを明示します。中断した試験に全体の正答率は付けません。この表には上部フィルターを適用しません。</p><div id="history-table" class="scroll"></div></section>
<section id="inventory" hidden><h2>補足試験と全証拠の索引</h2><p class="note">固定長速度・短いプローブ、容量試験、Hermes実ツール、MCP接続、補助採点replayを区別します。completeは収集完了であり、試験成功とは限りません。この索引には上部フィルターを適用しません。</p><div id="ancillary"></div><details><summary>全173登録run</summary><div id="run-table" class="scroll compact"></div></details><details><summary>凍結した原集計20ファイル</summary><div id="archives"></div></details></section>
<p class="note">LFM2.5の思考OFFはランタイムbudget 0で強制。Mageは公式の32K設定を64Kへ拡張したテキスト試験で、画像・GUI操作を評価していません。Q3のMTPは重み不足を実機確認、Q4のMTP起動プローブは先行試験失敗で未実施。Qwen Q4 S/Lは取得準備に失敗し、本測定なし。</p></main><script id="data" type="application/json">DATA</script><script src="dashboard.js"></script></body></html>'''


def build():
    data = collect()
    counts = data['counts']
    OUTPUT.mkdir(parents=True, exist_ok=True)
    save(OUTPUT / 'results.json', data)
    template = TEMPLATE.replace('94完了条件や4,776応答', f"{counts['complete_conditions']}完了条件や{counts['unique_saved_responses']:,}応答").replace('全173登録run', f"全{counts['registered_runs']}登録run").replace('原集計20ファイル', f"原集計{counts['archived_result_files']}ファイル")
    text = template.replace('STYLE', STYLE).replace('DATA', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'))
    (OUTPUT / 'index.html').write_text(text, encoding='utf-8')
    (OUTPUT / 'dashboard.js').write_bytes((ROOT / 'tools/comprehensive_dashboard.cjs').read_bytes())
    buf = io.StringIO(newline='')
    fields = ['row', 'run', 'model', 'quantization', 'mtp', 'placement', 'load_mode', 'threads', 'runtime', 'context', 'max_output', 'condition', 'status', 'score', 'saved', 'expected', 'passed_saved', 'caps_known', 'unknown_statistics', 'parser_errors', 'passed_without_final', 'seconds_saved', 'benchmark_decode_tok_s', 'fixed_length_tok_s', 'evidence']
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    intro = f"主比較{counts['configuration_rows']}行＝能力測定{counts['quality_rows']}行＋速度だけ{counts['speed_only_rows']}行。能力4条件が完了した測定は{counts['complete_quality_rows']}行、完了条件{counts['complete_conditions']}/{counts['condition_slots']}、重複を除く保存応答{counts['unique_saved_responses']:,}件。{counts['unique_model_quant_pairs_measured']}モデル・量子化ペア、MTPを含む{counts['unique_model_quant_mtp_measured']}組み合わせを測定。配置・再測定は別行。"
    md = ['# 全測定の横断比較', '', '[表示ページ](index.html) · [全条件CSV](conditions.csv) · [JSON](results.json)', '', intro, '', '| ID | モデル | 量子化 | MTP | 配置 / load-mode | BFCL OFF | ON | HE OFF | ON | 固定長 tok/s |', '| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for row in data['rows']:
        scores = []
        for key in KEYS:
            c = row['conditions'].get(key)
            scores.append(f"{c['score']}/{c['expected']}" if c and c['complete'] else f"未完了（保存{c['saved']}・正解{c['passed_saved']}）" if c and c['saved'] else '失敗（応答未保存）' if c and c['status']=='failed' else '速度のみ' if row['kind']=='speed-only' else '未実施')
        speed = row.get('fixed_speed')
        md.append('| ' + ' | '.join([f"[{row['label']}](../../{row['evidence']})", row['model'], row['quantization'], row['mtp'].upper(), row['placement'] + ' / ' + row['load_mode'], *scores, f"{speed['tok_s']:.2f}" if speed else '—']) + ' |')
        for key, c in row['conditions'].items() or [('speed-only', {})]:
            writer.writerow({'row': row['label'], 'run': row['id'], **{k: row[k] for k in ['model', 'quantization', 'mtp', 'placement', 'load_mode', 'threads', 'runtime', 'context', 'max_output']}, 'condition': key, **{k: c.get(k) for k in fields if k in c and k not in ['evidence']}, 'fixed_length_tok_s': speed['tok_s'] if speed else None, 'evidence': c.get('evidence', row['evidence'])})
    md.extend(['', '固定長速度は256トークン×3プロンプト×3回の中央値。問題回答中の平均decode速度とは別です。未測定を0点にせず、未完了は保存分だけを表示します。BFCLの呼び出し0件による採点上の正解は、最終回答や実ツール実行の完了を保証しません。', '', f"旧予算{counts['historical_condition_snapshots']}条件スナップショット、全{counts['registered_runs']}登録run、速度・容量・Hermes/MCP・補助採点の索引は表示ページで確認できます。"])
    (OUTPUT / 'conditions.csv').write_text(buf.getvalue(), encoding='utf-8-sig', newline='')
    (OUTPUT / 'summary.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(json.dumps(data['counts']))


if __name__ == '__main__':
    build()
