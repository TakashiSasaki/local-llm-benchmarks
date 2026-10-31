# Mage-VL-Cowork Q4_K_M テキストベンチマーク・64K

65,536 context・最大64,000出力・F16 KV・b11960-8642541b2 CUDA12.4。BFCL80問／HumanEval20問の固定部分集合。 過去の測定と同じ65,536 context・最大64,000出力。公式のactive training/inference windowは32,768なので、その範囲を超えた拡張条件です。短い入力の能力試験であり、64K長文理解を検証しません。画像入力は使用しません。

| 構成 | 取得 | 状態 | BFCL OFF | ON | HE OFF | ON | 固定長 tok/s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Mage-VL-Cowork Q4_K_M / MTP off / CPU 17層 / GPU 19層＋出力層（-ngl 20） | 新規推論 | failed | 未完了 | 未完了 | 未完了 | 未完了 | 29.88 |

## 途中終了・未実施

保存できた分の正解数であり、全問の正答率ではありません。

- 20261031-mage-q4-text-64k-mage-text-off / bfcl / 思考off: failed、保存 2/80、保存分の正解 2。<HTTPError 500: 'Internal Server Error'>

- 20261031-mage-q4-text-64k-mage-text-off / bfcl / 思考on: not-started、保存 0/80、保存分の正解 0。

- 20261031-mage-q4-text-64k-mage-text-off / humaneval / 思考off: not-started、保存 0/20、保存分の正解 0。

- 20261031-mage-q4-text-64k-mage-text-off / humaneval / 思考on: not-started、保存 0/20、保存分の正解 0。
