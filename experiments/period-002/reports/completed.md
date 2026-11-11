# 第2期 完成結果と再現記録

2026-11-11監査。**8配布物・32条件・1,600件の一意な能力回答を収集済み**。2026-11-02から11月11日に測定し、最終回収runは11月11日13:17 JSTに完了しました。BFCLは80問×思考OFF/ON、HumanEvalは20問×思考OFF/ON。すべてQ4_K_M、MTP OFFです。

[全1,600件・原応答参照・SHA・検証結果](completed.json) / [再現手順](../REPRODUCE.md) / [固定モデル入手manifest](../models/) / [期の概要](../README.md)

## 得点

BFCLは固定80問のAST採点、HumanEvalは固定20問の標準test Windows適応版です。全公式ベンチマークや一般的なモデル順位ではありません。括弧内は、出力上限で最終回答が空の成功例を失敗として数える補助評価です。原採点の点数は変更していません。

| 配布物 | BFCL OFF /80 | BFCL ON /80 | HumanEval OFF /20 | HumanEval ON /20 |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5-4B 通常版 | 69 | 70 | 14 | 17 |
| Abliterix 4B | 71 | 65 | 16 | 17 |
| Qwen3.5-9B 通常版 | 73 | 75 | 19 | 17 |
| Huihui 9B | 67 | 58 | 16 | 18 |
| Heretic 9B | 70 | 66（補助 65） | 18 | 15 |
| Defiant 9B | 73 | 73 | 16 | 17 |
| Qwen3.6-35B-A3B 通常版 | 72 | 71 | 17 | 19 |
| Huihui 35B-A3B | 73 | 69（補助 68） | 17 | 19 |

## 出力上限と採点の解釈

**全体の出力上限到達は14件**で、すべて最終回答が空です。最後の回収647件には8件、先行953件には6件あります。回収分だけの「8件」を全体の件数として扱わないでください。HumanEvalは10件すべてno_final_codeによる失敗。BFCLは4件で、そのうちirrelevanceの2件は呼び出しが空なので原AST採点では成功ですが、正常に回答を終えた成功とは区別します。

Heretic 9BのBFCL ONは66/80（補助65/80）、Huihui 35BのBFCL ONは69/80（補助68/80）。BFCLはツール呼び出し形式と引数の採点であり、実際のツール関数は実行していません。

| 配布物 | 条件 | 問題 | 原採点 | API秒 | 原応答 |
| --- | --- | --- | --- | ---: | --- |
| Qwen3.5-4B 通常版 | humaneval ON | HumanEval/7 | 失敗 | 1135.2 | [JSON](../../../runs/period-002-stage-a-comparison-20261102-q35-4b-base-humaneval-on/raw/HumanEval_7.json) |
| Qwen3.5-4B 通常版 | humaneval ON | HumanEval/59 | 失敗 | 1134.2 | [JSON](../../../runs/period-002-stage-a-comparison-20261102-q35-4b-base-humaneval-on/raw/HumanEval_59.json) |
| Abliterix 4B | humaneval ON | HumanEval/23 | 失敗 | 1134.6 | [JSON](../../../runs/period-002-stage-a-comparison-20261102-q35-4b-abliterix-humaneval-on/raw/HumanEval_23.json) |
| Qwen3.5-9B 通常版 | humaneval ON | HumanEval/35 | 失敗 | 6763.7 | [JSON](../../../runs/period-002-core-followup-20261102-q35-9b-base-humaneval-on/raw/HumanEval_35.json) |
| Qwen3.5-9B 通常版 | humaneval ON | HumanEval/62 | 失敗 | 7132.1 | [JSON](../../../runs/period-002-resumption-20261106-q35-9b-base-humaneval-on/raw/HumanEval_62.json) |
| Qwen3.5-9B 通常版 | humaneval ON | HumanEval/139 | 失敗 | 7028.7 | [JSON](../../../runs/period-002-resumption-20261110-q35-9b-base-humaneval-on/raw/HumanEval_139.json) |
| Heretic 9B | bfcl ON | irrelevance_139 | 成功 | 7321.6 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q35-9b-heretic-bfcl-on/raw/irrelevance_139.json) |
| Heretic 9B | humaneval ON | HumanEval/8 | 失敗 | 7267.0 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q35-9b-heretic-humaneval-on/raw/HumanEval_8.json) |
| Heretic 9B | humaneval ON | HumanEval/35 | 失敗 | 7286.4 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q35-9b-heretic-humaneval-on/raw/HumanEval_35.json) |
| Heretic 9B | humaneval ON | HumanEval/129 | 失敗 | 7315.2 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q35-9b-heretic-humaneval-on/raw/HumanEval_129.json) |
| Heretic 9B | humaneval ON | HumanEval/151 | 失敗 | 7267.5 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q35-9b-heretic-humaneval-on/raw/HumanEval_151.json) |
| Qwen3.6-35B-A3B 通常版 | bfcl ON | multiple_139 | 失敗 | 1882.6 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q36-35b-base-bfcl-on/raw/multiple_139.json) |
| Huihui 35B-A3B | bfcl ON | multiple_188 | 失敗 | 1879.2 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q36-35b-huihui-bfcl-on/raw/multiple_188.json) |
| Huihui 35B-A3B | bfcl ON | irrelevance_8 | 成功 | 1872.2 | [JSON](../../../runs/period-002-timeout-recovery-20261110-q36-35b-huihui-bfcl-on/raw/irrelevance_8.json) |

## 速度とメモリ

短文速度は思考OFF、3種類の固定prompt×3回、出力256 tokens（EOSを無視）、seed42の9試行中央値です。能力試験の長い推論を含む平均速度とは別です。GPU使用量はシステム全体、RAMはモデルrun全体の約3秒間隔の標本です。専有GPUメモリや条件ごとの瞬間最大値ではありません。再開した同一モデルの全親runをまとめた最大/最小を示します。

| 配布物 | 配置 | 固定256 token tok/s | GPUピーク MiB | 最小空きRAM GiB |
| --- | --- | ---: | ---: | ---: |
| Qwen3.5-4B 通常版 | GPU全層 / CPU MoE0 | 73.394 | 4973 | 19.62 |
| Abliterix 4B | GPU全層 / CPU MoE0 | 73.131 | 4971 | 19.28 |
| Qwen3.5-9B 通常版 | -ngl24 / CPU MoE0 | 22.773 | 5955 | 15.84 |
| Huihui 9B | -ngl24 / CPU MoE0 | 22.239 | 5965 | 16.11 |
| Heretic 9B | -ngl24 / CPU MoE0 | 21.191 | 5811 | 15.97 |
| Defiant 9B | -ngl24 / CPU MoE0 | 20.098 | 7093 | 16.78 |
| Qwen3.6-35B-A3B 通常版 | GPU全層 / CPU MoE34 | 37.555 | 6385 | 3.83 |
| Huihui 35B-A3B | GPU全層 / CPU MoE34 | 37.664 | 6365 | 3.95 |

9Bの-ngl24、35BのCPU MoE34は、宣言した候補内で共通に成立した配置です。全ての中間候補を網羅した理論的な最大GPU配置ではありません。4B/9B/35Bで配置が違うため、モデルサイズだけの効果とは解釈できません。

## 条件別の時間と出力

API秒は保存された最終応答の待ち時間合計です。失敗後の再試行前の7,200秒や、ロード・ダウンロード・停止時間は含みません。decode tok/sはAPIの生成token数を生成時間の合計で割った値です。

| 配布物 | 条件 | 得点 | cap | API合計秒 | API中央値秒 | decode tok/s | legacy HE replay |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen3.5-4B 通常版 | bfcl OFF | 69/80 | 0 | 146.6 | 1.0 | 73.41 | - |
| Qwen3.5-4B 通常版 | bfcl ON | 70/80 | 0 | 313.6 | 2.9 | 73.28 | - |
| Qwen3.5-4B 通常版 | humaneval OFF | 14/20 | 0 | 48.4 | 2.2 | 73.95 | 14/20 |
| Qwen3.5-4B 通常版 | humaneval ON | 17/20 | 2 | 2991.4 | 32.1 | 60.18 | 17/20 |
| Abliterix 4B | bfcl OFF | 71/80 | 0 | 160.5 | 1.1 | 73.23 | - |
| Abliterix 4B | bfcl ON | 65/80 | 0 | 353.8 | 2.8 | 72.86 | - |
| Abliterix 4B | humaneval OFF | 16/20 | 0 | 59.8 | 2.2 | 73.99 | 16/20 |
| Abliterix 4B | humaneval ON | 17/20 | 1 | 1954.9 | 37.6 | 62.90 | 16/20 |
| Qwen3.5-9B 通常版 | bfcl OFF | 73/80 | 0 | 436.8 | 3.4 | 22.88 | - |
| Qwen3.5-9B 通常版 | bfcl ON | 75/80 | 0 | 983.5 | 9.3 | 22.74 | - |
| Qwen3.5-9B 通常版 | humaneval OFF | 19/20 | 0 | 207.0 | 7.2 | 22.86 | 19/20 |
| Qwen3.5-9B 通常版 | humaneval ON | 17/20 | 3 | 22975.9 | 58.7 | 10.25 | 16/20 |
| Huihui 9B | bfcl OFF | 67/80 | 0 | 468.0 | 3.7 | 22.37 | - |
| Huihui 9B | bfcl ON | 58/80 | 0 | 948.1 | 10.4 | 22.34 | - |
| Huihui 9B | humaneval OFF | 16/20 | 0 | 305.2 | 7.6 | 22.30 | 15/20 |
| Huihui 9B | humaneval ON | 18/20 | 0 | 2364.6 | 44.5 | 19.52 | 18/20 |
| Heretic 9B | bfcl OFF | 70/80 | 0 | 525.3 | 3.9 | 21.25 | - |
| Heretic 9B | bfcl ON | 66/80 | 1 | 8378.0 | 9.8 | 10.24 | - |
| Heretic 9B | humaneval OFF | 18/20 | 0 | 211.1 | 9.8 | 21.30 | 18/20 |
| Heretic 9B | humaneval ON | 15/20 | 4 | 30305.9 | 51.0 | 9.23 | 15/20 |
| Defiant 9B | bfcl OFF | 73/80 | 0 | 492.2 | 3.7 | 20.19 | - |
| Defiant 9B | bfcl ON | 73/80 | 0 | 968.8 | 9.0 | 20.12 | - |
| Defiant 9B | humaneval OFF | 16/20 | 0 | 185.7 | 8.0 | 20.27 | 16/20 |
| Defiant 9B | humaneval ON | 17/20 | 0 | 846.4 | 34.3 | 20.07 | 17/20 |
| Qwen3.6-35B-A3B 通常版 | bfcl OFF | 72/80 | 0 | 443.0 | 4.2 | 37.30 | - |
| Qwen3.6-35B-A3B 通常版 | bfcl ON | 71/80 | 1 | 3718.3 | 23.0 | 35.24 | - |
| Qwen3.6-35B-A3B 通常版 | humaneval OFF | 17/20 | 0 | 144.8 | 5.9 | 37.37 | 17/20 |
| Qwen3.6-35B-A3B 通常版 | humaneval ON | 19/20 | 0 | 1510.7 | 63.8 | 36.34 | 18/20 |
| Huihui 35B-A3B | bfcl OFF | 73/80 | 0 | 391.8 | 3.8 | 37.53 | - |
| Huihui 35B-A3B | bfcl ON | 69/80 | 2 | 5627.5 | 24.8 | 34.91 | - |
| Huihui 35B-A3B | humaneval OFF | 17/20 | 0 | 175.1 | 6.3 | 36.99 | 16/20 |
| Huihui 35B-A3B | humaneval ON | 19/20 | 0 | 1824.1 | 75.5 | 36.24 | 19/20 |

## 実験方法・環境

Windows 11、Ryzen 9 7940HS、nominal 32 GiB RAM、RTX 4070 Laptop GPU（8 GiB）。llama.cpp b11960、commit 8642541b255bfb5dc39cd351a178be09013a55d6、CUDA12.4。context65,536、F16 K/V、1 slot、MTP OFF、8 threads、load-mode none。サーバー実行ファイルSHA-256は81f65c6681d66099e5d48757aa2c050ba958dc43816e584f0bb4181eb7c910d8。

出力予算はmin(64,000, 65,536 - rendered input tokens - 32)。BFCLはtemperature0/top_p1/top_k0/min_p0/repeat_penalty1、HumanEvalはtemperature0.6/top_p0.95/top_k20/min_p0/presence_penalty0/repeat_penalty1。いずれもseed42、cache_prompt false。思考OFF/ONはenable_thinkingで切り替え、観測されたreasoningの有無も別に保存しています。

HumanEval主採点はhumaneval-b9453e8-windows-full-module-v1、CPython3.14.9。固定した上流test/実行コードを用い、POSIXの制御をWindows JobObjectと6秒watchdog、256 MiB、1 processへ適応。実験前canonical164/164と正解・誤答・非終了controlを検証しています。legacy列は第1期の制限付き採点を同じ保存コードに適用した補助結果で、新規推論ではありません。JobObject/reliability_guardは汎用のOSセキュリティsandboxではありません。

[開始時環境](../environment/planning-20261102.json)、[11月6日監査](../environment/handoff-20261106.json)、各runのserver-command/props、モデルとruntime検証、source snapshot、memory標本、cleanupを合わせて参照してください。開始時のOS/driver/power情報が全測定期間に不変だったことまでは証明しません。

## 中断・継続と待ち時間の変更

953件の原応答をhashと問題IDで参照し、647件を追加取得して合計1,600件にしました。通常9B HumanEval ONは複数の停止・再開runを参照し、Heretic9B BFCL ONは元の73件と回収7件を統合しています。原回答をコピーして新規推論として数えていません。preflight、速度probe、採点replay、失敗して最終API応答がない試行は1,600件から除外しています。

先行953件のAPI待機上限は7,200秒、回収647件は14,400秒です。2026-11-10のHeretic9B irrelevance_139は旧上限で失敗して原runを保持し、その問題を新runで再取得しました。延長したのはクライアント待ち時間だけで、64,000 token出力上限やsampler・採点器は変えていません。全件を同じ待ち時間上限で測り直した比較ではありません。[回収手順の記録](../TIMEOUT-RECOVERY-20261110.md)を参照してください。

## 限界と結論の範囲

これは通常版と無検閲系の配布物同士の実用比較です。同じQ4_K_M名でもtensor精度、変換・校正、元revisionが一致するとは限りません。4B対はchat template SHAが同一でもtensor精度構成が違います。拒否方向除去だけの因果効果や安全性、無検閲性そのものを測ったものではありません。

固定少数問題、単一seed、原則1応答であり、信頼区間付きの一般順位を主張しません。日本語、数学、XSTest、Hermes実ツール接続、MTP ON、追加27Bは今回の主比較に含まれません。全てcontext65,536なので、コンテキスト長を増やした場合の速度/メモリ曲線はこの主表だけから推定できません。

## 検証と再現

保存結果を検証: `python -B -X utf8 tools/verify_period2_complete.py`。HumanEvalコードを実行しない通常の検証と、明示的な再採点、モデルによる新規推論を区別します。[再現手順](../REPRODUCE.md)にはモデルを含めず取得する方法、固定revision/SHA、runtime、Python、dry-run、新期/新runでの実行方法を記載しています。

このページとMarkdownは`python -B -X utf8 scripts/report_period2_complete.py`でcompleted.jsonから再生成できます。[旧588件の比較](comparison.md)は11月6日時点の履歴として保持しています。第1期の凍結inventory・raw・recipe・報告は変更していません。
