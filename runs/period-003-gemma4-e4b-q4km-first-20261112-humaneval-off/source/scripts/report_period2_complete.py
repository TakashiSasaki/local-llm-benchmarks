"""Render the completed period-002 audit without changing historical snapshots."""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / 'experiments/period-002/reports'
LABELS = {
    'q35-4b-base': 'Qwen3.5-4B 通常版',
    'q35-4b-abliterix': 'Abliterix 4B',
    'q35-9b-base': 'Qwen3.5-9B 通常版',
    'q35-9b-huihui': 'Huihui 9B',
    'q35-9b-heretic': 'Heretic 9B',
    'q35-9b-defiant': 'Defiant 9B',
    'q36-35b-base': 'Qwen3.6-35B-A3B 通常版',
    'q36-35b-huihui': 'Huihui 35B-A3B',
}


def inline(value):
    value = html.escape(value)
    value = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', value)
    value = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', value)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', value)


def render_html(lines):
    out = []
    table = False
    row = 0
    for line in lines:
        if line.startswith('|'):
            if not line.replace('|', '').replace(' ', '').replace(':', '').replace('-', ''):
                continue
            if not table:
                out.append('<div class="scroll"><table>')
                table = True
                row = 0
            tag = 'th' if row == 0 else 'td'
            out.append('<tr>' + ''.join(f'<{tag}>' + inline(cell.strip()) + f'</{tag}>' for cell in line.strip('|').split('|')) + '</tr>')
            row += 1
            continue
        if table:
            out.append('</table></div>')
            table = False
        if line.startswith('# '):
            out.append('<h1>' + inline(line[2:]) + '</h1>')
        elif line.startswith('## '):
            out.append('<h2>' + inline(line[3:]) + '</h2>')
        elif line:
            out.append('<p>' + inline(line) + '</p>')
    if table:
        out.append('</table></div>')
    return ''.join(out)


def render():
    d = json.loads((DEST / 'completed.json').read_text(encoding='utf-8'))
    rows = d['conditions']
    index = {(r['model'], r['suite'], r['thinking']): r for r in rows}
    caps = [c for c in d['cases'] if c['finish_reason'] == 'length']
    assert len(rows) == 32 and len(d['cases']) == 1600 and len(caps) == 14
    lines = [
        '# 第2期 完成結果と再現記録', '',
        '2026-11-11監査。**8配布物・32条件・1,600件の一意な能力回答を収集済み**。2026-11-02から11月11日に測定し、最終回収runは11月11日13:17 JSTに完了しました。BFCLは80問×思考OFF/ON、HumanEvalは20問×思考OFF/ON。すべてQ4_K_M、MTP OFFです。', '',
        '[全1,600件・原応答参照・SHA・検証結果](completed.json) / [再現手順](../REPRODUCE.md) / [固定モデル入手manifest](../models/) / [期の概要](../README.md)', '',
        '## 得点', '',
        'BFCLは固定80問のAST採点、HumanEvalは固定20問の標準test Windows適応版です。全公式ベンチマークや一般的なモデル順位ではありません。括弧内は、出力上限で最終回答が空の成功例を失敗として数える補助評価です。原採点の点数は変更していません。', '',
        '| 配布物 | BFCL OFF /80 | BFCL ON /80 | HumanEval OFF /20 | HumanEval ON /20 |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for key, label in LABELS.items():
        cells = []
        for suite, mode in [('bfcl', 'off'), ('bfcl', 'on'), ('humaneval', 'off'), ('humaneval', 'on')]:
            r = index[key, suite, mode]
            score = str(r['passed_saved'])
            adjusted = r.get('capped_no_final_aware_passed', r['passed_saved'])
            if adjusted != r['passed_saved']:
                score += f'（補助 {adjusted}）'
            cells.append(score)
        lines.append('| ' + label + ' | ' + ' | '.join(cells) + ' |')
    lines += [
        '', '## 出力上限と採点の解釈', '',
        '**全体の出力上限到達は14件**で、すべて最終回答が空です。最後の回収647件には8件、先行953件には6件あります。回収分だけの「8件」を全体の件数として扱わないでください。HumanEvalは10件すべてno_final_codeによる失敗。BFCLは4件で、そのうちirrelevanceの2件は呼び出しが空なので原AST採点では成功ですが、正常に回答を終えた成功とは区別します。', '',
        'Heretic 9BのBFCL ONは66/80（補助65/80）、Huihui 35BのBFCL ONは69/80（補助68/80）。BFCLはツール呼び出し形式と引数の採点であり、実際のツール関数は実行していません。', '',
        '| 配布物 | 条件 | 問題 | 原採点 | API秒 | 原応答 |',
        '| --- | --- | --- | --- | ---: | --- |',
    ]
    for c in caps:
        lines.append(f"| {LABELS[c['model']]} | {c['suite']} {c['thinking'].upper()} | {c['id']} | {'成功' if c['passed'] else '失敗'} | {c['seconds']:.1f} | [JSON](../../../{c['raw']}) |")
    lines += [
        '', '## 速度とメモリ', '',
        '短文速度は思考OFF、3種類の固定prompt×3回、出力256 tokens（EOSを無視）、seed42の9試行中央値です。能力試験の長い推論を含む平均速度とは別です。GPU使用量はシステム全体、RAMはモデルrun全体の約3秒間隔の標本です。専有GPUメモリや条件ごとの瞬間最大値ではありません。再開した同一モデルの全親runをまとめた最大/最小を示します。', '',
        '| 配布物 | 配置 | 固定256 token tok/s | GPUピーク MiB | 最小空きRAM GiB |',
        '| --- | --- | ---: | ---: | ---: |',
    ]
    for key, label in LABELS.items():
        perf = [p for p in d['model_performance'] if p['model'] == key]
        speeds = [p['fixed256_median_decode_tps'] for p in perf if p.get('fixed256_median_decode_tps') is not None]
        memories = [p['memory'] for p in perf if p.get('memory')]
        gpu = max(m['peak_gpu_used_mib_system_total'] for m in memories)
        ram = min(m['minimum_available_ram_bytes'] for m in memories) / 1024**3
        placement = 'GPU全層 / CPU MoE0' if key.startswith('q35-4b') else '-ngl24 / CPU MoE0' if key.startswith('q35-9b') else 'GPU全層 / CPU MoE34'
        speed = ' / '.join(f'{value:.3f}' for value in speeds)
        lines.append(f'| {label} | {placement} | {speed} | {gpu:.0f} | {ram:.2f} |')
    lines += [
        '', '9Bの-ngl24、35BのCPU MoE34は、宣言した候補内で共通に成立した配置です。全ての中間候補を網羅した理論的な最大GPU配置ではありません。4B/9B/35Bで配置が違うため、モデルサイズだけの効果とは解釈できません。', '',
        '## 条件別の時間と出力', '',
        'API秒は保存された最終応答の待ち時間合計です。失敗後の再試行前の7,200秒や、ロード・ダウンロード・停止時間は含みません。decode tok/sはAPIの生成token数を生成時間の合計で割った値です。', '',
        '| 配布物 | 条件 | 得点 | cap | API合計秒 | API中央値秒 | decode tok/s | legacy HE replay |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |',
    ]
    for r in rows:
        legacy = '-' if r['legacy_replay_passed'] is None else str(r['legacy_replay_passed']) + '/20'
        lines.append(f"| {LABELS[r['model']]} | {r['suite']} {r['thinking'].upper()} | {r['passed_saved']}/{r['expected']} | {len(r['output_caps'])} | {r['total_api_seconds']:.1f} | {r['median_api_seconds']:.1f} | {r['aggregate_decode_tps']:.2f} | {legacy} |")
    lines += [
        '', '## 実験方法・環境', '',
        'Windows 11、Ryzen 9 7940HS、nominal 32 GiB RAM、RTX 4070 Laptop GPU（8 GiB）。llama.cpp b11960、commit 8642541b255bfb5dc39cd351a178be09013a55d6、CUDA12.4。context65,536、F16 K/V、1 slot、MTP OFF、8 threads、load-mode none。サーバー実行ファイルSHA-256は81f65c6681d66099e5d48757aa2c050ba958dc43816e584f0bb4181eb7c910d8。', '',
        '出力予算はmin(64,000, 65,536 - rendered input tokens - 32)。BFCLはtemperature0/top_p1/top_k0/min_p0/repeat_penalty1、HumanEvalはtemperature0.6/top_p0.95/top_k20/min_p0/presence_penalty0/repeat_penalty1。いずれもseed42、cache_prompt false。思考OFF/ONはenable_thinkingで切り替え、観測されたreasoningの有無も別に保存しています。', '',
        'HumanEval主採点はhumaneval-b9453e8-windows-full-module-v1、CPython3.14.9。固定した上流test/実行コードを用い、POSIXの制御をWindows JobObjectと6秒watchdog、256 MiB、1 processへ適応。実験前canonical164/164と正解・誤答・非終了controlを検証しています。legacy列は第1期の制限付き採点を同じ保存コードに適用した補助結果で、新規推論ではありません。JobObject/reliability_guardは汎用のOSセキュリティsandboxではありません。', '',
        '[開始時環境](../environment/planning-20261102.json)、[11月6日監査](../environment/handoff-20261106.json)、各runのserver-command/props、モデルとruntime検証、source snapshot、memory標本、cleanupを合わせて参照してください。開始時のOS/driver/power情報が全測定期間に不変だったことまでは証明しません。', '',
        '## 中断・継続と待ち時間の変更', '',
        '953件の原応答をhashと問題IDで参照し、647件を追加取得して合計1,600件にしました。通常9B HumanEval ONは複数の停止・再開runを参照し、Heretic9B BFCL ONは元の73件と回収7件を統合しています。原回答をコピーして新規推論として数えていません。preflight、速度probe、採点replay、失敗して最終API応答がない試行は1,600件から除外しています。', '',
        '先行953件のAPI待機上限は7,200秒、回収647件は14,400秒です。2026-11-10のHeretic9B irrelevance_139は旧上限で失敗して原runを保持し、その問題を新runで再取得しました。延長したのはクライアント待ち時間だけで、64,000 token出力上限やsampler・採点器は変えていません。全件を同じ待ち時間上限で測り直した比較ではありません。[回収手順の記録](../TIMEOUT-RECOVERY-20261110.md)を参照してください。', '',
        '## 限界と結論の範囲', '',
        'これは通常版と無検閲系の配布物同士の実用比較です。同じQ4_K_M名でもtensor精度、変換・校正、元revisionが一致するとは限りません。4B対はchat template SHAが同一でもtensor精度構成が違います。拒否方向除去だけの因果効果や安全性、無検閲性そのものを測ったものではありません。', '',
        '固定少数問題、単一seed、原則1応答であり、信頼区間付きの一般順位を主張しません。日本語、数学、XSTest、Hermes実ツール接続、MTP ON、追加27Bは今回の主比較に含まれません。全てcontext65,536なので、コンテキスト長を増やした場合の速度/メモリ曲線はこの主表だけから推定できません。', '',
        '## 検証と再現', '',
        '保存結果を検証: `python -B -X utf8 tools/verify_period2_complete.py`。HumanEvalコードを実行しない通常の検証と、明示的な再採点、モデルによる新規推論を区別します。[再現手順](../REPRODUCE.md)にはモデルを含めず取得する方法、固定revision/SHA、runtime、Python、dry-run、新期/新runでの実行方法を記載しています。', '',
        'このページとMarkdownは`python -B -X utf8 scripts/report_period2_complete.py`でcompleted.jsonから再生成できます。[旧588件の比較](comparison.md)は11月6日時点の履歴として保持しています。第1期の凍結inventory・raw・recipe・報告は変更していません。', '',
    ]
    (DEST / 'completed.md').write_text('\n'.join(lines), encoding='utf-8')
    style = 'body{font:16px/1.7 system-ui;max-width:1240px;margin:24px auto;padding:20px;color:#18283b;background:#f7f9fc}table{border-collapse:collapse;background:white;min-width:650px;width:100%}th,td{padding:10px;border:1px solid #ccd5df;text-align:left}.scroll{overflow:auto;max-width:100%}p{overflow-wrap:anywhere}a{color:#176c65}code{overflow-wrap:anywhere}h2{margin-top:2em}'
    document = '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>第2期 完成結果 1,600回答</title><style>' + style + '</style></head><body>' + render_html(lines) + '</body></html>'
    (DEST / 'completed.html').write_text(document, encoding='utf-8')
    print(json.dumps({'conditions': len(rows), 'answers': len(d['cases']), 'caps': len(caps), 'rendered': ['completed.md', 'completed.html']}))


if __name__ == '__main__':
    render()
