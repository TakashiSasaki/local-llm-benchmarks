# Qwen3.6-35B-A3B Q4_K_M × MTP

主比較: 65,536 context · 最大64,000出力 · CPU MoE 34層 · F16 KV · load-mode none · b11960 / 8642541b2 / CUDA12.4。BFCL各80問、HumanEval各20問。

| 構成 | 状態 | BFCL OFF | ON | HE OFF | ON | 生成速度 tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-35B-A3B Q4_K_M / MTP off | complete | 75/80 | 73/80 | 18/20 | 19/20 | 36.64 |
| Qwen3.6-35B-A3B Q4_K_M / MTP on | complete | 74/80 | 73/80 | 18/20 | 19/20 | 47.38 |

速度は思考OFF・greedy・固定256出力トークン、3プロンプト各3回の中央値。生成内容の一致は保証しません。予熱は除外。得点は主採点で、各問題1回答です。

## 稼働中のメモリ（サンプル値）

| MTP | 最小空きRAM GiB | 最大GPU MiB |
| --- | ---: | ---: |
| off | 5.16 | 6583 |
| on | 4.76 | 7815 |

GPUはシステム全体のサンプル値です。

固定長生成の速度比: 1.293倍（+29.3%）

出力上限の打ち切り 0件、最終回答とツール呼び出しが両方とも空の応答 0件。BFCLの正解と回答の完了は別に確認してください。

## 長時間の問題

| 構成 | 試験 | 問題 | 秒 | 出力トークン | 終了 |
| --- | --- | --- | ---: | ---: | --- |
| MTP off | humaneval / 思考on | [HumanEval/129](../../runs/20261031-qwen36-q4-mtp-64k-q4-off-humaneval-on/raw/HumanEval_129.json) | 192.5 | 6944 | stop |
| MTP off | humaneval / 思考on | [HumanEval/154](../../runs/20261031-qwen36-q4-mtp-64k-q4-off-humaneval-on/raw/HumanEval_154.json) | 112.3 | 4022 | stop |
| MTP off | humaneval / 思考on | [HumanEval/108](../../runs/20261031-qwen36-q4-mtp-64k-q4-off-humaneval-on/raw/HumanEval_108.json) | 111.5 | 4004 | stop |
| MTP on | humaneval / 思考on | [HumanEval/129](../../runs/20261031-qwen36-q4-mtp-64k-q4-on-humaneval-on/raw/HumanEval_129.json) | 107.7 | 5267 | stop |
| MTP off | humaneval / 思考on | [HumanEval/151](../../runs/20261031-qwen36-q4-mtp-64k-q4-off-humaneval-on/raw/HumanEval_151.json) | 88.9 | 3197 | stop |
| MTP off | humaneval / 思考on | [HumanEval/70](../../runs/20261031-qwen36-q4-mtp-64k-q4-off-humaneval-on/raw/HumanEval_70.json) | 87.4 | 3122 | stop |
| MTP on | humaneval / 思考on | [HumanEval/163](../../runs/20261031-qwen36-q4-mtp-64k-q4-on-humaneval-on/raw/HumanEval_163.json) | 87.3 | 4335 | stop |
| MTP off | humaneval / 思考on | [HumanEval/163](../../runs/20261031-qwen36-q4-mtp-64k-q4-off-humaneval-on/raw/HumanEval_163.json) | 84.9 | 3040 | stop |
| MTP off | humaneval / 思考on | [HumanEval/59](../../runs/20261031-qwen36-q4-mtp-64k-q4-off-humaneval-on/raw/HumanEval_59.json) | 81.4 | 2917 | stop |
| MTP on | humaneval / 思考on | [HumanEval/154](../../runs/20261031-qwen36-q4-mtp-64k-q4-on-humaneval-on/raw/HumanEval_154.json) | 76.8 | 3869 | stop |

## HumanEval補助採点（主得点を置き換えない）

| MTP | 思考OFF 主→補助 | 思考ON 主→補助 |
| --- | ---: | ---: |
| off | 18 → 18 /20 | 19 → 20 /20 |
| on | 18 → 18 /20 | 19 → 20 /20 |

## 先行Empero測定の参照（新規推論ではない）

| 構成 | BFCL OFF | ON | HE OFF | ON | 速度 tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Empero Qwen3.8-35B-A3B-Distill IQ3_M / MTP off | 70/80 | 72/80 | 18/20 | 19/20 | 33.73 |
| Empero Qwen3.8-35B-A3B-Distill IQ3_M / MTP on | 72/80 | 73/80 | 18/20 | 19/20 | 39.07 |
| Empero Qwen3.8-35B-A3B-Distill Q4_K_M / MTP off | 71/80 | 72/80 | 18/20 | 19/20 | 38.20 |
| Empero Qwen3.8-35B-A3B-Distill Q4_K_M / MTP on | 71/80 | 71/80 | 18/20 | 17/20 | 46.47 |

[全データJSON](matrix-data.json) · [条件CSV](conditions.csv) · [打ち切りCSV](truncations.csv) · [表示ページ](index.html) · [条件・解釈](../../docs/QWEN36_Q4_MTP.md)
