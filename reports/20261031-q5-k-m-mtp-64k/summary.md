# Qwen3.6 / Empero Q5_K_M × MTP・思考 OFF/ON

65,536 context・最大64,000出力・F16 KV・b11960-8642541b2 CUDA12.4。BFCL80問／HumanEval20問の固定部分集合。

| 構成 | 取得 | 状態 | BFCL OFF | ON | HE OFF | ON | 固定長 tok/s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-35B-A3B Q5_K_M / MTP off / CPU MoE 35層 | 新規推論 | complete | 73/80 | 72/80 | 18/20 | 19/20 | 32.28 |
| Qwen3.6-35B-A3B Q5_K_M / MTP on / CPU MoE 35層 | 新規推論 | complete | 73/80 | 72/80 | 18/20 | 19/20 | 41.77 |
| Qwen3.6-35B-A3B Q4_K_M / MTP off / CPU MoE 35層 | 新規推論 | complete | 75/80 | 72/80 | 18/20 | 19/20 | 36.25 |
| Qwen3.6-35B-A3B Q4_K_M / MTP on / CPU MoE 35層 | 新規推論 | complete | 74/80 | 72/80 | 18/20 | 18/20 | 46.34 |
| Empero Qwen3.8-35B-A3B-Distill Q5_K_M / MTP off / CPU MoE 34層 | 新規推論 | complete | 74/80 | 72/80 | 19/20 | 20/20 | 34.16 |
| Empero Qwen3.8-35B-A3B-Distill Q5_K_M / MTP on / CPU MoE 34層 | 新規推論 | complete | 73/80 | 71/80 | 17/20 | 19/20 | 48.69 |
| Empero Qwen3.8-35B-A3B-Distill Q4_K_M / MTP off / CPU MoE 34層 | 既存run参照 | complete | 71/80 | 72/80 | 18/20 | 19/20 | 38.20 |
| Empero Qwen3.8-35B-A3B-Distill Q4_K_M / MTP on / CPU MoE 34層 | 既存run参照 | complete | 71/80 | 71/80 | 18/20 | 17/20 | 46.47 |

MTP qwen36-q5m: 1.294倍（+29.4%）。

MTP qwen36-q4-control: 1.278倍（+27.8%）。

MTP empero-q5m: 1.425倍（+42.5%）。

MTP empero-q4-control: 1.217倍（+21.7%）。
