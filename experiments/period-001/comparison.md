# 全測定の横断比較

[表示ページ](report.html) · [全条件CSV](conditions.csv) · [JSON](comparison.json)

主比較30行＝能力測定27行＋速度だけ3行。能力4条件が完了した測定は23行、完了条件94/108、重複を除く保存応答4,776件。16モデル・量子化ペア、MTPを含む21組み合わせを測定。配置・再測定は別行。

| ID | モデル | 量子化 | MTP | 配置 / load-mode | BFCL OFF | ON | HE OFF | ON | 固定長 tok/s |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| [R1](../../artifacts/local-llm/runs/bench64k-output-20261030-141002/report.html) | Qwen3.6-35B-A3B | UD-Q3_K_M | OFF | MoE先頭30層のexpertをCPU / default (未指定) | 72/80 | 72/80 | 17/20 | 20/20 | — |
| [R2](../../artifacts/local-llm/runs/bench64k-output-20261030-141002/report.html) | Qwen3.5-4B | Q4_K_M | OFF | GPU all指定 / CPU MoE指定なし / default (未指定) | 72/80 | 68/80 | 14/20 | 13/20 | — |
| [R3](../../artifacts/local-llm/runs/bench64k-output-20261030-141002/report.html) | LFM3-1.7B Text | QAD-Q4_0 | OFF | GPU all指定 / CPU MoE指定なし / default (未指定) | 70/80 | 73/80 | 15/20 | 19/20 | — |
| [R4](../../artifacts/local-llm/runs/bench64k-output-20261030-141002/report.html) | LFM3-1.7B Text | Q8_0 | OFF | GPU all指定 / CPU MoE指定なし / default (未指定) | 69/80 | 73/80 | 17/20 | 17/20 | — |
| [R5](../../artifacts/local-llm/runs/bench64k-output-20261030-141002/report.html) | LFM3-VL-2B | QAD-Q4_0 | OFF | GPU all指定 / CPU MoE指定なし / default (未指定) | 59/80 | 56/80 | 11/20 | 16/20 | — |
| [R6](../../artifacts/local-llm/runs/bench64k-output-20261030-141002/report.html) | LFM3-VL-2B | Q8_0 | OFF | GPU all指定 / CPU MoE指定なし / default (未指定) | 57/80 | 63/80 | 9/20 | 16/20 | — |
| [R7](../../artifacts/local-llm/runs/legacy-models-64k-20261030-180109/report.html) | LFM2.5-24B-A2B | QAD-Q4_0 | OFF | MoE先頭24層のexpertをCPU / default (未指定) | 63/80 | 60/80 | 11/20 | 19/20 | — |
| [R8](../../artifacts/local-llm/runs/legacy-models-64k-20261030-180109/report.html) | GLM-4.7-Flash | Q4_K_M | OFF | MoE先頭35層のexpertをCPU / default (未指定) | 70/80 | 72/80 | 12/20 | 19/20 | — |
| [R9](../../reports/20261030-qwen36-iq3m-64k/index.html) | Qwen3.6-35B-A3B | IQ3_M | OFF | 先頭30 MoE層のexpertをCPU配置 / default (未指定) | 74/80 | 72/80 | 19/20 | 19/20 | — |
| [R10](../../reports/20261031-empero-qwen38-iq3m-64k/index.html) | Empero Qwen3.8-35B-A3B-Distill | IQ3_M | OFF | 先頭30 MoE層のexpertをCPU配置 / default (未指定) | 72/80 | 72/80 | 18/20 | 20/20 | — |
| [R11](../../runs/20261031-empero-mtp-load-none-iq3-cpu30-off/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | IQ3_M | OFF | CPU MoE 30層 / GPU all指定 / default (未指定) | 速度のみ | 速度のみ | 速度のみ | 速度のみ | 40.48 |
| [R12](../../runs/20261031-empero-mtp-load-none-iq3-cpu30-on/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | IQ3_M | ON | CPU MoE 30層 / GPU all指定 / default (未指定) | 速度のみ | 速度のみ | 速度のみ | 速度のみ | 43.74 |
| [R13](../../runs/20261031-empero-mtp-load-none-q4-off/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | Q4_K_M | OFF | CPU MoE 34層 / GPU all指定 / none | 71/80 | 72/80 | 18/20 | 19/20 | 38.20 |
| [R14](../../runs/20261031-empero-mtp-load-none-q4-on/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | Q4_K_M | ON | CPU MoE 34層 / GPU all指定 / none | 71/80 | 71/80 | 18/20 | 17/20 | 46.47 |
| [R15](../../runs/20261031-empero-quant-mtp-64k-iq3-off/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | IQ3_M | OFF | CPU MoE 34層 / GPU all指定 / default (未指定) | 70/80 | 72/80 | 18/20 | 19/20 | 33.73 |
| [R16](../../runs/20261031-empero-quant-mtp-64k-iq3-on/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | IQ3_M | ON | CPU MoE 34層 / GPU all指定 / default (未指定) | 72/80 | 73/80 | 18/20 | 19/20 | 39.07 |
| [R17](../../runs/20261031-empero-quant-mtp-64k-q4-off/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | Q4_K_M | OFF | CPU MoE 34層 / GPU all指定 / default (未指定) | 71/80 | 72/80 | 18/20 | 19/20 | 37.77 |
| [R18](../../runs/20261031-empero-quant-mtp-64k-q4-on/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | Q4_K_M | ON | CPU MoE 34層 / GPU all指定 / default (未指定) | 未完了（保存6・正解6） | 未実施 | 未実施 | 未実施 | 45.95 |
| [R19](../../runs/20261031-mage-q3-text-64k-gpu-placement-ngl23-throughput/manifest.json) | Mage-VL-Cowork | Q3_K_M | OFF | CPU 14層 / GPU 22層＋出力 / none | 速度のみ | 速度のみ | 速度のみ | 速度のみ | 37.61 |
| [R20](../../runs/20261031-mage-q3-text-64k-q3-off/manifest.json) | Mage-VL-Cowork | Q3_K_M | OFF | CPU 17層 / GPU 19層＋出力 / none | 19/80 | 21/80 | 失敗（応答未保存） | 未実施 | 32.43 |
| [R21](../../runs/20261031-mage-q4-text-64k-mage-text-off/manifest.json) | Mage-VL-Cowork | Q4_K_M | OFF | CPU 17層 / GPU 19層＋出力 / none | 未完了（保存2・正解2） | 未実施 | 未実施 | 未実施 | 29.88 |
| [R22](../../runs/20261031-mage-q4-text-64k-parser-errors-mage-text-off/manifest.json) | Mage-VL-Cowork | Q4_K_M | OFF | CPU 17層 / GPU 19層＋出力 / none | 未完了（保存8・正解7） | 未実施 | 未実施 | 未実施 | 29.75 |
| [R23](../../runs/20261031-q5-k-m-mtp-64k-empero-q5m-off/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | Q5_K_M | OFF | CPU MoE 34層 / GPU all指定 / none | 74/80 | 72/80 | 19/20 | 20/20 | 34.16 |
| [R24](../../runs/20261031-q5-k-m-mtp-64k-empero-q5m-on/manifest.json) | Empero Qwen3.8-35B-A3B-Distill | Q5_K_M | ON | CPU MoE 34層 / GPU all指定 / none | 73/80 | 71/80 | 17/20 | 19/20 | 48.69 |
| [R25](../../runs/20261031-q5-k-m-mtp-64k-qwen36-q4-control-off/manifest.json) | Qwen3.6-35B-A3B | Q4_K_M | OFF | CPU MoE 35層 / GPU all指定 / none | 75/80 | 72/80 | 18/20 | 19/20 | 36.25 |
| [R26](../../runs/20261031-q5-k-m-mtp-64k-qwen36-q4-control-on/manifest.json) | Qwen3.6-35B-A3B | Q4_K_M | ON | CPU MoE 35層 / GPU all指定 / none | 74/80 | 72/80 | 18/20 | 18/20 | 46.34 |
| [R27](../../runs/20261031-q5-k-m-mtp-64k-qwen36-q5m-off/manifest.json) | Qwen3.6-35B-A3B | Q5_K_M | OFF | CPU MoE 35層 / GPU all指定 / none | 73/80 | 72/80 | 18/20 | 19/20 | 32.28 |
| [R28](../../runs/20261031-q5-k-m-mtp-64k-qwen36-q5m-on/manifest.json) | Qwen3.6-35B-A3B | Q5_K_M | ON | CPU MoE 35層 / GPU all指定 / none | 73/80 | 72/80 | 18/20 | 19/20 | 41.77 |
| [R29](../../runs/20261031-qwen36-q4-mtp-64k-q4-off/manifest.json) | Qwen3.6-35B-A3B | Q4_K_M | OFF | CPU MoE 34層 / GPU all指定 / none | 75/80 | 73/80 | 18/20 | 19/20 | 36.64 |
| [R30](../../runs/20261031-qwen36-q4-mtp-64k-q4-on/manifest.json) | Qwen3.6-35B-A3B | Q4_K_M | ON | CPU MoE 34層 / GPU all指定 / none | 74/80 | 73/80 | 18/20 | 19/20 | 47.38 |

固定長速度は256トークン×3プロンプト×3回の中央値。問題回答中の平均decode速度とは別です。未測定を0点にせず、未完了は保存分だけを表示します。BFCLの呼び出し0件による採点上の正解は、最終回答や実ツール実行の完了を保証しません。

旧予算24条件スナップショット、全173登録run、速度・容量・Hermes/MCP・補助採点の索引は表示ページで確認できます。
