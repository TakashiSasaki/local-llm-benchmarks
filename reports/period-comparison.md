# 第1期・第2期の性能比較

2026-11-11作成。既存測定の読み取り集計です。新規推論やモデル取得は行っていません。第1期の30構成行・第2期の8配布物を、重み・配置・MTP・採点方針を混同せず整理します。

## 主要な結果

同一重み・配置の第1期8ペアでは、MTP ONの固定256-token生成中央値がOFFより約8〜43%高くなりました。ただし文章種別に依存し、Empero IQ3_M / CPU MoE30のproseでは約8.6%低下しました。速さが品質改善を意味するわけではありません。

第2期のMTP OFFでは4Bが約73 tok/s、9Bが約20〜23 tok/s、35B-A3Bが約38 tok/s。35BはMoEで配置も異なるため、パラメーター数だけで速度は説明できません。35Bの最小空きRAMは約3.8〜4.0 GiBで、4B/9Bより余裕が小さい観測でした。

旧b11946の32K/64K容量試験では、QwenとLFM2.5で長い入力側のdecode速度が約16%・12%低く、システムGPUピークはともに674 MiB増加しました。ただし各1試行でコンテキスト設定と実入力長が同時に増えています。単一要因の因果曲線や一般的な性能低下率とは呼べません。

## 比較の境界

[第1期の固定比較](../experiments/period-001/report.html)と[機械可読データ](../experiments/period-001/comparison.json)、[第2期の全件監査](../experiments/period-002/reports/completed.json)が正本です。主比較はいずれも65,536 contextですが、モデル配布元・hash・配置・採点方針が異なります。

同じQwen3.5-4B Q4_K_Mでも、第1期通常版はhash00fe7986…、第2期通常版は51eafbc1…。Qwen3.6 Q4も第1期R29はb46fedd3…、第2期通常版は1f05a928…。第1期→第2期の速度差を時系列の改善やruntime改善と解釈しません。正式な完全hashと配布revisionは各期のモデルmanifestを参照してください。

第1期のHumanEval主値は当時の制限付き採点、第2期は標準test Windows適応版です。両期の主値をそのまま統一ランキングへ混ぜません。第2期のlegacy_replayは同じ生成コードを旧方針で採点した橋渡し列ですが、重みや生成まで同一になるわけではありません。

## モデル・設定別の全体像

第1期のBFCL/HumanEvalは保存済み採点の成功数/収集数。部分収集は「部分」、未実施は「未測定」。速度欄は同じ256-token固定長9試行がある場合だけ表示します。能力試験の可変長decode速度を代用して順位を作りません。CPU欄はMoE expert weightsのCPU配置層数です。

| 第1期行 | モデル・量子化 | MTP | GPU層 / CPU層 / load | 固定長 tok/s | BFCL OFF / ON | HumanEval OFF / ON（旧方針） |
| --- | --- | --- | --- | ---: | --- | --- |
| R1 | Qwen3.6-35B-A3B UD-Q3_K_M | off | all / 30 / default (未指定) | 未測定 | 72/80 / 72/80 | 17/20 / 20/20 |
| R2 | Qwen3.5-4B Q4_K_M | off | all / None / default (未指定) | 未測定 | 72/80 / 68/80 | 14/20 / 13/20 |
| R3 | LFM3-1.7B Text QAD-Q4_0 | off | all / None / default (未指定) | 未測定 | 70/80 / 73/80 | 15/20 / 19/20 |
| R4 | LFM3-1.7B Text Q8_0 | off | all / None / default (未指定) | 未測定 | 69/80 / 73/80 | 17/20 / 17/20 |
| R5 | LFM3-VL-2B QAD-Q4_0 | off | all / None / default (未指定) | 未測定 | 59/80 / 56/80 | 11/20 / 16/20 |
| R6 | LFM3-VL-2B Q8_0 | off | all / None / default (未指定) | 未測定 | 57/80 / 63/80 | 9/20 / 16/20 |
| R7 | LFM2.5-24B-A2B QAD-Q4_0 | off | all / 24 / default (未指定) | 未測定 | 63/80 / 60/80 | 11/20 / 19/20 |
| R8 | GLM-4.7-Flash Q4_K_M | off | all / 35 / default (未指定) | 未測定 | 70/80 / 72/80 | 12/20 / 19/20 |
| R9 | Qwen3.6-35B-A3B IQ3_M | off | all / 30 / default (未指定) | 未測定 | 74/80 / 72/80 | 19/20 / 19/20 |
| R10 | Empero Qwen3.8-35B-A3B-Distill IQ3_M | off | all / 30 / default (未指定) | 未測定 | 72/80 / 72/80 | 18/20 / 20/20 |
| R11 | Empero Qwen3.8-35B-A3B-Distill IQ3_M | off | all / 30 / default (未指定) | 40.48 | 未測定 / 未測定 | 未測定 / 未測定 |
| R12 | Empero Qwen3.8-35B-A3B-Distill IQ3_M | on | all / 30 / default (未指定) | 43.74 | 未測定 / 未測定 | 未測定 / 未測定 |
| R13 | Empero Qwen3.8-35B-A3B-Distill Q4_K_M | off | all / 34 / none | 38.20 | 71/80 / 72/80 | 18/20 / 19/20 |
| R14 | Empero Qwen3.8-35B-A3B-Distill Q4_K_M | on | all / 34 / none | 46.47 | 71/80 / 71/80 | 18/20 / 17/20 |
| R15 | Empero Qwen3.8-35B-A3B-Distill IQ3_M | off | all / 34 / default (未指定) | 33.73 | 70/80 / 72/80 | 18/20 / 19/20 |
| R16 | Empero Qwen3.8-35B-A3B-Distill IQ3_M | on | all / 34 / default (未指定) | 39.07 | 72/80 / 73/80 | 18/20 / 19/20 |
| R17 | Empero Qwen3.8-35B-A3B-Distill Q4_K_M | off | all / 34 / default (未指定) | 37.77 | 71/80 / 72/80 | 18/20 / 19/20 |
| R18 | Empero Qwen3.8-35B-A3B-Distill Q4_K_M | on | all / 34 / default (未指定) | 45.95 | 6/6 部分 / 未測定 | 未測定 / 未測定 |
| R19 | Mage-VL-Cowork Q3_K_M | off | 23 / 0 / none | 37.61 | 未測定 / 未測定 | 未測定 / 未測定 |
| R20 | Mage-VL-Cowork Q3_K_M | off | 20 / 0 / none | 32.43 | 19/80 / 21/80 | 未測定 / 未測定 |
| R21 | Mage-VL-Cowork Q4_K_M | off | 20 / 0 / none | 29.88 | 2/2 部分 / 未測定 | 未測定 / 未測定 |
| R22 | Mage-VL-Cowork Q4_K_M | off | 20 / 0 / none | 29.75 | 7/8 部分 / 未測定 | 未測定 / 未測定 |
| R23 | Empero Qwen3.8-35B-A3B-Distill Q5_K_M | off | all / 34 / none | 34.16 | 74/80 / 72/80 | 19/20 / 20/20 |
| R24 | Empero Qwen3.8-35B-A3B-Distill Q5_K_M | on | all / 34 / none | 48.69 | 73/80 / 71/80 | 17/20 / 19/20 |
| R25 | Qwen3.6-35B-A3B Q4_K_M | off | all / 35 / none | 36.25 | 75/80 / 72/80 | 18/20 / 19/20 |
| R26 | Qwen3.6-35B-A3B Q4_K_M | on | all / 35 / none | 46.34 | 74/80 / 72/80 | 18/20 / 18/20 |
| R27 | Qwen3.6-35B-A3B Q5_K_M | off | all / 35 / none | 32.28 | 73/80 / 72/80 | 18/20 / 19/20 |
| R28 | Qwen3.6-35B-A3B Q5_K_M | on | all / 35 / none | 41.77 | 73/80 / 72/80 | 18/20 / 19/20 |
| R29 | Qwen3.6-35B-A3B Q4_K_M | off | all / 34 / none | 36.64 | 75/80 / 73/80 | 18/20 / 19/20 |
| R30 | Qwen3.6-35B-A3B Q4_K_M | on | all / 34 / none | 47.38 | 74/80 / 73/80 | 18/20 / 19/20 |

第2期は全配布物Q4_K_M・MTP OFF。BFCL80問、HumanEval20問、思考OFF/ONで合計1,600件です。

| 第2期モデル | GPU層 / CPU層 | 固定長 tok/s | BFCL OFF / ON | HumanEval OFF / ON（新方針） | legacy HE OFF / ON |
| --- | --- | ---: | --- | --- | --- |
| q35-4b-base | all / 0 | 73.394 | 69/80 / 70/80 | 14/20 / 17/20 | 14/20 / 17/20 |
| q35-4b-abliterix | all / 0 | 73.131 | 71/80 / 65/80 | 16/20 / 17/20 | 16/20 / 16/20 |
| q35-9b-base | 24 / 0 | 22.773 | 73/80 / 75/80 | 19/20 / 17/20 | 19/20 / 16/20 |
| q35-9b-huihui | 24 / 0 | 22.239 | 67/80 / 58/80 | 16/20 / 18/20 | 15/20 / 18/20 |
| q35-9b-heretic | 24 / 0 | 21.191 | 70/80 / 66/80 | 18/20 / 15/20 | 18/20 / 15/20 |
| q35-9b-defiant | 24 / 0 | 20.098 | 73/80 / 73/80 | 16/20 / 17/20 | 16/20 / 17/20 |
| q36-35b-base | all / 34 | 37.555 | 72/80 / 71/80 | 17/20 / 19/20 | 17/20 / 18/20 |
| q36-35b-huihui | all / 34 | 37.664 | 73/80 / 69/80 | 17/20 / 19/20 | 16/20 / 19/20 |

**出力上限と完成度:** 第2期の空の打ち切りは14件（最後の回収分に8件）。Heretic9B BFCL ONの66/80とHuihui35B ONの69/80には、空のirrelevance応答が原採点で成功となるものを各1件含みます。補助値は65/80・68/80。第1期にも同種の例があるため、「採点成功」「回答完了」「実ツール成功」を区別します。

## MTP ON/OFFを同条件で比べる

b11960、context65,536、F16 KV、思考OFF、3 prompt（prose/code/json）×3回、各256 tokens。対応ペア内のモデルhashと非spec引数一致を確認しています。MTP ONはdraft-mtp、n-max3、p-min0、draft GPU全層、ubatch128、draft K/V f16。

| 対応行 | モデル・量子化 | CPU層 / load | OFF tok/s | ON tok/s | 変化 | 速度原記録 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| R11/R12 | Empero Qwen3.8-35B-A3B-Distill IQ3_M | 30 / default (未指定) | 40.48 | 43.74 | +8.1% | [OFF](../runs/20261031-empero-mtp-load-none-iq3-cpu30-off-speed/summary.json) / [ON](../runs/20261031-empero-mtp-load-none-iq3-cpu30-on-speed/summary.json) |
| R13/R14 | Empero Qwen3.8-35B-A3B-Distill Q4_K_M | 34 / none | 38.20 | 46.47 | +21.7% | [OFF](../runs/20261031-empero-mtp-load-none-q4-off-speed/summary.json) / [ON](../runs/20261031-empero-mtp-load-none-q4-on-speed/summary.json) |
| R15/R16 | Empero Qwen3.8-35B-A3B-Distill IQ3_M | 34 / default (未指定) | 33.73 | 39.07 | +15.8% | [OFF](../runs/20261031-empero-quant-mtp-64k-iq3-off-speed/summary.json) / [ON](../runs/20261031-empero-quant-mtp-64k-iq3-on-speed/summary.json) |
| R17/R18 | Empero Qwen3.8-35B-A3B-Distill Q4_K_M | 34 / default (未指定) | 37.77 | 45.95 | +21.7% | [OFF](../runs/20261031-empero-quant-mtp-64k-q4-off-speed/summary.json) / [ON](../runs/20261031-empero-quant-mtp-64k-q4-on-speed/summary.json) |
| R23/R24 | Empero Qwen3.8-35B-A3B-Distill Q5_K_M | 34 / none | 34.16 | 48.69 | +42.5% | [OFF](../runs/20261031-q5-k-m-mtp-64k-empero-q5m-off-speed/summary.json) / [ON](../runs/20261031-q5-k-m-mtp-64k-empero-q5m-on-speed/summary.json) |
| R25/R26 | Qwen3.6-35B-A3B Q4_K_M | 35 / none | 36.25 | 46.34 | +27.8% | [OFF](../runs/20261031-q5-k-m-mtp-64k-qwen36-q4-control-off-speed/summary.json) / [ON](../runs/20261031-q5-k-m-mtp-64k-qwen36-q4-control-on-speed/summary.json) |
| R27/R28 | Qwen3.6-35B-A3B Q5_K_M | 35 / none | 32.28 | 41.77 | +29.4% | [OFF](../runs/20261031-q5-k-m-mtp-64k-qwen36-q5m-off-speed/summary.json) / [ON](../runs/20261031-q5-k-m-mtp-64k-qwen36-q5m-on-speed/summary.json) |
| R29/R30 | Qwen3.6-35B-A3B Q4_K_M | 34 / none | 36.64 | 47.38 | +29.3% | [OFF](../runs/20261031-qwen36-q4-mtp-64k-q4-off-speed/summary.json) / [ON](../runs/20261031-qwen36-q4-mtp-64k-q4-on-speed/summary.json) |

ONのdraft受理率は約59.9〜66.4%。MTPの計算・メモリ負担があるため受理率だけで高速化は決まりません。観測されたシステムGPUピーク差はON側が+856〜1,250 MiB。ただしモデルrun全体の標本最大であり、MTP専有メモリの厳密な差ではありません。

Empero IQ3_M / CPU MoE30では文章種別で、proseが40.05→36.61 tok/s（−8.6%）、codeが+6.9%、jsonが+20.9%。9試行をpoolしたIQRには3種類のpromptの差が含まれ、反復ノイズだけの尺度でも平均の信頼区間でもありません。全8ペアの中央値改善を全入力へ保証しません。

MTPは生成速度を上げてもBFCL/HumanEval得点を一貫して上げません。例えば第1期Empero Q4 / load none / thinking ONには64,000-token打ち切りがあり、短文速度が改善しても条件全体の応答時間が伸びました。品質や完了率と合わせて選ぶ必要があります。

## 32Kから64Kにした容量・長入力試験

[32K原記録](../artifacts/local-llm/runs/capacity-32k-20261028-194457.json) / [64K原記録](../artifacts/local-llm/runs/capacity-64k-20261028-213856.json)。2026-10-28、旧llama.cpp b11946、F16 KV、各モデル1回、合成raw入力、生成上限64 tokens。同一モデルhashと配置ですが、設定容量と実入力長を同時に変えています。主比較b11960・短文256-token試験とは分けて扱います。

| モデル / 配置 | 実入力tokens 32K→64K | prefill tok/s 32K→64K | decode tok/s 32K→64K | sampled GPU MiB 32K→64K |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.6 UD-Q3_K_M / CPU MoE30 | 31,776→63,886 | 503.18→463.27（−7.9%） | 31.42→26.49（−15.7%） | 6,907→7,581（+674） |
| LFM2.5 QAD-Q4_0 / CPU MoE24 | 31,780→63,880 | 752.49→667.29（−11.3%） | 41.46→36.67（−11.6%） | 7,033→7,707（+674） |
| GLM-4.7-Flash Q4 / CPU MoE35 | 32Kのみ完了 | 260.75→未測定 | 23.46→未測定 | 7,821→比較不可 |

GLMの64Kは空きRAMが約1.31 GiBまで低下して手動停止。未測定の速度を0にしたり、完全なOOM発生を主張したりしません。OSファイルcacheは消去せず、GPU/RAMは周期標本なので瞬間ピークを取り逃がし得ます。単発の容量確認は長時間安定性、長文検索精度、会話品質を示しません。二点の間を補間して曲線を描く根拠もありません。

## 第2期のメモリ余裕

正式モデル親run全体（中断・再開を含む、容量preflightは除外）の標本を集約。GPUはシステム全体、WSは対象server process working set、privateはcommitで物理RAM使用量と同じではありません。共有GPUメモリは未取得。機種・同時負荷・試験時間の違いを含み、必要RAM/VRAMの保証値ではありません。

| 配布物 | GPUピーク MiB | 最小空きRAM GiB | 最大process WS GiB | 最大private commit GiB |
| --- | ---: | ---: | ---: | ---: |
| q35-4b-base | 4973 | 19.62 | 1.19 | 6.44 |
| q35-4b-abliterix | 4971 | 19.28 | 1.20 | 6.45 |
| q35-9b-base | 5955 | 15.84 | 2.90 | 9.11 |
| q35-9b-huihui | 5965 | 16.11 | 2.91 | 9.12 |
| q35-9b-heretic | 5811 | 15.97 | 3.03 | 9.10 |
| q35-9b-defiant | 7093 | 16.78 | 2.91 | 10.23 |
| q36-35b-base | 6385 | 3.83 | 16.42 | 23.15 |
| q36-35b-huihui | 6365 | 3.95 | 16.42 | 23.12 |

## 再現・今後の測定

[第2期の再現手順](../experiments/period-002/REPRODUCE.md)は固定revision・SHA付きモデル取得、runtime/Python照合、新しい期・一意なrun IDでの実行を説明します。モデル重みとruntimeバイナリはGit管理外です。[第1期の固定recipe](../experiments/period-001/README.md)は変更していません。

この文書は`python -B -X utf8 scripts/report_period_comparison.py`で再生成できます。集計元JSONに原応答・設定・hashが残ります。過去953件のAPI待機上限7,200秒と、回収647件の14,400秒の違いも第2期に明記しています。単一seedの小規模subsetであるため、差が数問のときに統計的優劣を断言しません。

厳密なコンテキスト影響を追加測定するなら、同じ重み・runtime・配置・電源条件で、(A)実入力長を固定して予約contextだけ変える試験と、(B)予約contextを固定して実入力長だけ変える試験を分け、複数反復と時系列RAM/VRAMを取る必要があります。これは提案であり、今回新規実験は開始していません。

## 集計入力のSHA-256

- [experiments/period-001/comparison.json](../experiments/period-001/comparison.json): `978913aa3b5d700fc59b28fca4e60030b9eae412600727c2c071bbcab611d14c`
- [experiments/period-002/reports/completed.json](../experiments/period-002/reports/completed.json): `839716b2d23184faaeca3a02aad920b45e0b39af3f80dce07830054b2dd5423a`
- [artifacts/local-llm/runs/capacity-32k-20261028-194457.json](../artifacts/local-llm/runs/capacity-32k-20261028-194457.json): `c080cf5dcdd741bf19c1bf9deb6397775783d9727e5c60ca31b419193bfc0d3d`
- [artifacts/local-llm/runs/capacity-64k-20261028-213856.json](../artifacts/local-llm/runs/capacity-64k-20261028-213856.json): `59618ac84073b29ca8e613f0805f130f9ce9e640ce4c609c8a54e15135d7f2cb`
