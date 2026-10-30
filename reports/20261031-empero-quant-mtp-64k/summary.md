# Empero Qwen3.8 Distill: 3bit / 4bit × MTP

主比較: CPU MoE 34層、65,536 context、最大64,000出力、b11960 / CUDA12.4。BFCL各80問、HumanEval各20問。得点は主採点です。

| 量子化 | MTP | 状態 | BFCL 思考OFF | BFCL 思考ON | HE 思考OFF | HE 思考ON | 固定長生成の中央値 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q4_K_M | off | complete | 71/80 | 72/80 | 18/20 | 19/20 | 37.77 tok/s |
| Q4_K_M | on | RAM保護停止 | 未測定 | 未測定 | 未測定 | 未測定 | 45.95 tok/s |
| IQ3_M | off | complete | 70/80 | 72/80 | 18/20 | 19/20 | 33.73 tok/s |
| IQ3_M | on | complete | 72/80 | 73/80 | 18/20 | 19/20 | 39.07 tok/s |

固定長生成は同一プロンプト・256トークン×3種類×3回。生成本文が同一とは限りません。予熱は除外。能力試験とは別の速度試験です。

能力試験の出力上限による打ち切り: 0件。最終回答とツール呼び出しが両方とも空の応答: 0件。

## 最も時間がかかった問題

| 構成 / 試験 | 問題 | 秒 | 出力トークン | 終了理由 |
| --- | --- | ---: | ---: | --- |
| Q4_K_M / MTP off / humaneval / 思考on | [HumanEval/129](../../runs/20261031-empero-quant-mtp-64k-q4-off-humaneval-on/raw/HumanEval_129.json) | 176.6 | 6325 | stop |
| Q4_K_M / MTP off / humaneval / 思考on | [HumanEval/154](../../runs/20261031-empero-quant-mtp-64k-q4-off-humaneval-on/raw/HumanEval_154.json) | 130.2 | 4720 | stop |
| IQ3_M / MTP off / humaneval / 思考on | [HumanEval/129](../../runs/20261031-empero-quant-mtp-64k-iq3-off-humaneval-on/raw/HumanEval_129.json) | 126.0 | 3998 | stop |
| IQ3_M / MTP off / humaneval / 思考off | [HumanEval/129](../../runs/20261031-empero-quant-mtp-64k-iq3-off-humaneval-off/raw/HumanEval_129.json) | 73.4 | 2257 | stop |
| IQ3_M / MTP on / humaneval / 思考on | [HumanEval/129](../../runs/20261031-empero-quant-mtp-64k-iq3-on-humaneval-on/raw/HumanEval_129.json) | 69.2 | 2760 | stop |

生成トークン数には思考を含みます。固定長生成が速くなっても、回答の完了が速くなるとは限りません。

## HumanEvalの補助採点（主結果は変更しない）

| 構成 | 思考OFF 主→補助 | 思考ON 主→補助 |
| --- | ---: | ---: |
| Q4_K_M / MTP off | 18 → 18 /20 | 19 → 20 /20 |
| IQ3_M / MTP off | 18 → 18 /20 | 19 → 19 /20 |
| IQ3_M / MTP on | 18 → 18 /20 | 19 → 19 /20 |

補助ポリシーはtypeとoperator.mul/addを追加。保存済み不正解コードの再実行であり、新しいモデル推論ではありません。

## 元run

- Q4_K_M / MTP off: [20261031-empero-quant-mtp-64k-q4-off](../../runs/20261031-empero-quant-mtp-64k-q4-off/manifest.json)
- Q4_K_M / MTP on: [20261031-empero-quant-mtp-64k-q4-on](../../runs/20261031-empero-quant-mtp-64k-q4-on/manifest.json)
- IQ3_M / MTP off: [20261031-empero-quant-mtp-64k-iq3-off](../../runs/20261031-empero-quant-mtp-64k-iq3-off/manifest.json)
- IQ3_M / MTP on: [20261031-empero-quant-mtp-64k-iq3-on](../../runs/20261031-empero-quant-mtp-64k-iq3-on/manifest.json)

[全データJSON](matrix-data.json) · [条件CSV](conditions.csv) · [打ち切りCSV](truncations.csv) · [表示ページ](index.html) · [条件・解釈](../../docs/EMPERO_MTP.md)
