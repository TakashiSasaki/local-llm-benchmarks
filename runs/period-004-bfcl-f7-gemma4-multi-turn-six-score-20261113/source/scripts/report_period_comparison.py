"""Generate a descriptive cross-period report from published evidence, no inference."""
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def render():
    first = load('experiments/period-001/comparison.json')
    second = load('experiments/period-002/reports/completed.json')
    lines = [
        '# 第1期・第2期の性能比較', '',
        '2026-11-11作成。既存測定の読み取り集計です。新規推論やモデル取得は行っていません。第1期の30構成行・第2期の8配布物を、重み・配置・MTP・採点方針を混同せず整理します。', '',
        '## 主要な結果', '',
        '同一重み・配置の第1期8ペアでは、MTP ONの固定256-token生成中央値がOFFより約8〜43%高くなりました。ただし文章種別に依存し、Empero IQ3_M / CPU MoE30のproseでは約8.6%低下しました。速さが品質改善を意味するわけではありません。', '',
        '第2期のMTP OFFでは4Bが約73 tok/s、9Bが約20〜23 tok/s、35B-A3Bが約38 tok/s。35BはMoEで配置も異なるため、パラメーター数だけで速度は説明できません。35Bの最小空きRAMは約3.8〜4.0 GiBで、4B/9Bより余裕が小さい観測でした。', '',
        '旧b11946の32K/64K容量試験では、QwenとLFM2.5で長い入力側のdecode速度が約16%・12%低く、システムGPUピークはともに674 MiB増加しました。ただし各1試行でコンテキスト設定と実入力長が同時に増えています。単一要因の因果曲線や一般的な性能低下率とは呼べません。', '',
        '## 比較の境界', '',
        '[第1期の固定比較](../experiments/period-001/report.html)と[機械可読データ](../experiments/period-001/comparison.json)、[第2期の全件監査](../experiments/period-002/reports/completed.json)が正本です。主比較はいずれも65,536 contextですが、モデル配布元・hash・配置・採点方針が異なります。', '',
        '同じQwen3.5-4B Q4_K_Mでも、第1期通常版はhash00fe7986…、第2期通常版は51eafbc1…。Qwen3.6 Q4も第1期R29はb46fedd3…、第2期通常版は1f05a928…。第1期→第2期の速度差を時系列の改善やruntime改善と解釈しません。正式な完全hashと配布revisionは各期のモデルmanifestを参照してください。', '',
        '第1期のHumanEval主値は当時の制限付き採点、第2期は標準test Windows適応版です。両期の主値をそのまま統一ランキングへ混ぜません。第2期のlegacy_replayは同じ生成コードを旧方針で採点した橋渡し列ですが、重みや生成まで同一になるわけではありません。', '',
        '## モデル・設定別の全体像', '',
        '第1期のBFCL/HumanEvalは保存済み採点の成功数/収集数。部分収集は「部分」、未実施は「未測定」。速度欄は同じ256-token固定長9試行がある場合だけ表示します。能力試験の可変長decode速度を代用して順位を作りません。CPU欄はMoE expert weightsのCPU配置層数です。', '',
        '| 第1期行 | モデル・量子化 | MTP | GPU層 / CPU層 / load | 固定長 tok/s | BFCL OFF / ON | HumanEval OFF / ON（旧方針） |',
        '| --- | --- | --- | --- | ---: | --- | --- |',
    ]

    def score(row, key):
        c = row['conditions'].get(key)
        if not c or not c.get('saved'):
            return '未測定'
        return f"{c['passed_saved']}/{c['saved']}" + (' 部分' if not c.get('complete') else '')

    for number, r in enumerate(first['rows'], 1):
        speed = f"{r['fixed_speed']['tok_s']:.2f}" if r.get('fixed_speed') else '未測定'
        lines.append(f"| R{number} | {r['model']} {r['quantization']} | {r['mtp']} | {r.get('ngl')} / {r.get('cpu_moe_layers')} / {r.get('load_mode')} | {speed} | {score(r,'bfcl_off')} / {score(r,'bfcl_on')} | {score(r,'he_off')} / {score(r,'he_on')} |")
    lines += ['', '第2期は全配布物Q4_K_M・MTP OFF。BFCL80問、HumanEval20問、思考OFF/ONで合計1,600件です。', '',
              '| 第2期モデル | GPU層 / CPU層 | 固定長 tok/s | BFCL OFF / ON | HumanEval OFF / ON（新方針） | legacy HE OFF / ON |',
              '| --- | --- | ---: | --- | --- | --- |']
    index = {(r['model'], r['suite'], r['thinking']): r for r in second['conditions']}
    keys = list(dict.fromkeys(r['model'] for r in second['conditions']))
    for key in keys:
        perf = next(p for p in second['model_performance'] if p['model'] == key and p.get('fixed256_median_decode_tps'))
        placement = perf['placement']
        bf = [index[key, 'bfcl', mode]['passed_saved'] for mode in ('off', 'on')]
        he = [index[key, 'humaneval', mode]['passed_saved'] for mode in ('off', 'on')]
        old = [index[key, 'humaneval', mode]['legacy_replay_passed'] for mode in ('off', 'on')]
        lines.append(f"| {key} | {placement['gpu_layers']} / {placement['cpu_moe_layers']} | {perf['fixed256_median_decode_tps']:.3f} | {bf[0]}/80 / {bf[1]}/80 | {he[0]}/20 / {he[1]}/20 | {old[0]}/20 / {old[1]}/20 |")
    lines += ['', '**出力上限と完成度:** 第2期の空の打ち切りは14件（最後の回収分に8件）。Heretic9B BFCL ONの66/80とHuihui35B ONの69/80には、空のirrelevance応答が原採点で成功となるものを各1件含みます。補助値は65/80・68/80。第1期にも同種の例があるため、「採点成功」「回答完了」「実ツール成功」を区別します。', '',
              '## MTP ON/OFFを同条件で比べる', '',
              'b11960、context65,536、F16 KV、思考OFF、3 prompt（prose/code/json）×3回、各256 tokens。対応ペア内のモデルhashと非spec引数一致を確認しています。MTP ONはdraft-mtp、n-max3、p-min0、draft GPU全層、ubatch128、draft K/V f16。', '',
              '| 対応行 | モデル・量子化 | CPU層 / load | OFF tok/s | ON tok/s | 変化 | 速度原記録 |',
              '| --- | --- | --- | ---: | ---: | ---: | --- |']
    for i, j in [(11, 12), (13, 14), (15, 16), (17, 18), (23, 24), (25, 26), (27, 28), (29, 30)]:
        a, b = first['rows'][i - 1], first['rows'][j - 1]
        assert a['model_hash'] == b['model_hash'] and a['mtp'] == 'off' and b['mtp'] == 'on'
        off, on = a['fixed_speed']['tok_s'], b['fixed_speed']['tok_s']
        links = f"[OFF](../{a['fixed_speed']['evidence']}) / [ON](../{b['fixed_speed']['evidence']})"
        lines.append(f"| R{i}/R{j} | {a['model']} {a['quantization']} | {a['cpu_moe_layers']} / {a['load_mode']} | {off:.2f} | {on:.2f} | {(on/off-1)*100:+.1f}% | {links} |")
    lines += ['', 'ONのdraft受理率は約59.9〜66.4%。MTPの計算・メモリ負担があるため受理率だけで高速化は決まりません。観測されたシステムGPUピーク差はON側が+856〜1,250 MiB。ただしモデルrun全体の標本最大であり、MTP専有メモリの厳密な差ではありません。', '',
              'Empero IQ3_M / CPU MoE30では文章種別で、proseが40.05→36.61 tok/s（−8.6%）、codeが+6.9%、jsonが+20.9%。9試行をpoolしたIQRには3種類のpromptの差が含まれ、反復ノイズだけの尺度でも平均の信頼区間でもありません。全8ペアの中央値改善を全入力へ保証しません。', '',
              'MTPは生成速度を上げてもBFCL/HumanEval得点を一貫して上げません。例えば第1期Empero Q4 / load none / thinking ONには64,000-token打ち切りがあり、短文速度が改善しても条件全体の応答時間が伸びました。品質や完了率と合わせて選ぶ必要があります。', '',
              '## 32Kから64Kにした容量・長入力試験', '',
              '[32K原記録](../artifacts/local-llm/runs/capacity-32k-20261028-194457.json) / [64K原記録](../artifacts/local-llm/runs/capacity-64k-20261028-213856.json)。2026-10-28、旧llama.cpp b11946、F16 KV、各モデル1回、合成raw入力、生成上限64 tokens。同一モデルhashと配置ですが、設定容量と実入力長を同時に変えています。主比較b11960・短文256-token試験とは分けて扱います。', '',
              '| モデル / 配置 | 実入力tokens 32K→64K | prefill tok/s 32K→64K | decode tok/s 32K→64K | sampled GPU MiB 32K→64K |',
              '| --- | ---: | ---: | ---: | ---: |',
              '| Qwen3.6 UD-Q3_K_M / CPU MoE30 | 31,776→63,886 | 503.18→463.27（−7.9%） | 31.42→26.49（−15.7%） | 6,907→7,581（+674） |',
              '| LFM2.5 QAD-Q4_0 / CPU MoE24 | 31,780→63,880 | 752.49→667.29（−11.3%） | 41.46→36.67（−11.6%） | 7,033→7,707（+674） |',
              '| GLM-4.7-Flash Q4 / CPU MoE35 | 32Kのみ完了 | 260.75→未測定 | 23.46→未測定 | 7,821→比較不可 |', '',
              'GLMの64Kは空きRAMが約1.31 GiBまで低下して手動停止。未測定の速度を0にしたり、完全なOOM発生を主張したりしません。OSファイルcacheは消去せず、GPU/RAMは周期標本なので瞬間ピークを取り逃がし得ます。単発の容量確認は長時間安定性、長文検索精度、会話品質を示しません。二点の間を補間して曲線を描く根拠もありません。', '',
              '## 第2期のメモリ余裕', '',
              '正式モデル親run全体（中断・再開を含む、容量preflightは除外）の標本を集約。GPUはシステム全体、WSは対象server process working set、privateはcommitで物理RAM使用量と同じではありません。共有GPUメモリは未取得。機種・同時負荷・試験時間の違いを含み、必要RAM/VRAMの保証値ではありません。', '',
              '| 配布物 | GPUピーク MiB | 最小空きRAM GiB | 最大process WS GiB | 最大private commit GiB |',
              '| --- | ---: | ---: | ---: | ---: |']
    for key in keys:
        perf = [p for p in second['model_performance'] if p['model'] == key]
        ms = [p['memory'] for p in perf]
        lines.append(f"| {key} | {max(m['peak_gpu_used_mib_system_total'] for m in ms):.0f} | {min(m['minimum_available_ram_bytes'] for m in ms)/1024**3:.2f} | {max(m['peak_process_working_set_bytes'] for m in ms)/1024**3:.2f} | {max(m['peak_process_private_bytes'] for m in ms)/1024**3:.2f} |")
    lines += ['', '## 再現・今後の測定', '',
              '[第2期の再現手順](../experiments/period-002/REPRODUCE.md)は固定revision・SHA付きモデル取得、runtime/Python照合、新しい期・一意なrun IDでの実行を説明します。モデル重みとruntimeバイナリはGit管理外です。[第1期の固定recipe](../experiments/period-001/README.md)は変更していません。', '',
              'この文書は`python -B -X utf8 scripts/report_period_comparison.py`で再生成できます。集計元JSONに原応答・設定・hashが残ります。過去953件のAPI待機上限7,200秒と、回収647件の14,400秒の違いも第2期に明記しています。単一seedの小規模subsetであるため、差が数問のときに統計的優劣を断言しません。', '',
              '厳密なコンテキスト影響を追加測定するなら、同じ重み・runtime・配置・電源条件で、(A)実入力長を固定して予約contextだけ変える試験と、(B)予約contextを固定して実入力長だけ変える試験を分け、複数反復と時系列RAM/VRAMを取る必要があります。これは提案であり、今回新規実験は開始していません。', '',
              '## 集計入力のSHA-256', '']
    for relative in ['experiments/period-001/comparison.json', 'experiments/period-002/reports/completed.json', 'artifacts/local-llm/runs/capacity-32k-20261028-194457.json', 'artifacts/local-llm/runs/capacity-64k-20261028-213856.json']:
        lines.append(f"- [{relative}](../{relative}): `{hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()}`")
    (ROOT / 'reports/period-comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'first_period_rows': len(first['rows']), 'second_period_models': len(keys), 'mtp_pairs': 8, 'new_inference': 0}))


if __name__ == '__main__':
    render()
