# Mage-VL-Cowork Q4_K_M テキストベンチマーク・64K（形式エラーも記録）

65,536 context・最大64,000出力・F16 KV・b11960-8642541b2 CUDA12.4。BFCL80問／HumanEval20問の固定部分集合。 65,536 context・最大64,000出力。公式active windowの32,768を超える拡張条件です。64K長文理解の検証ではありません。画像入力は使用しません。形式エラーは失敗として数え、返らないトークン数・思考状態・終了理由は不明のまま保存します。

| 構成 | 取得 | 状態 | BFCL OFF | ON | HE OFF | ON | 固定長 tok/s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Mage-VL-Cowork Q4_K_M / MTP off / CPU 17層 / GPU 19層＋出力層（-ngl 20） | 新規推論 | failed | 未完了 | 未完了 | 未完了 | 未完了 | 29.75 |

## 途中終了・未実施

保存できた分の正解数であり、全問の正答率ではありません。

- 20261031-mage-q4-text-64k-parser-errors-mage-text-off / bfcl / 思考off: failed、保存 8/80、保存分の正解 7。TimeoutError('timed out')

- 20261031-mage-q4-text-64k-parser-errors-mage-text-off / bfcl / 思考on: not-started、保存 0/80、保存分の正解 0。

- 20261031-mage-q4-text-64k-parser-errors-mage-text-off / humaneval / 思考off: not-started、保存 0/20、保存分の正解 0。

- 20261031-mage-q4-text-64k-parser-errors-mage-text-off / humaneval / 思考on: not-started、保存 0/20、保存分の正解 0。
