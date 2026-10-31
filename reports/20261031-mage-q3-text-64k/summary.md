# Mage-VL-Cowork Q3_K_M / Q4_K_M テキスト比較・64K

65,536 context・最大64,000出力・F16 KV・b11960-8642541b2 CUDA12.4。BFCL80問／HumanEval20問の固定部分集合。 同じ-ngl20（CPU17 decoder層・GPU19層＋出力層）、64K/F16、画像なし。公式32K active windowを超える拡張条件。Q4は完了runのみ参照し、未完了分を正答率比較に含めません。形式エラーの統計は不明です。

| 構成 | 取得 | 状態 | BFCL OFF | ON | HE OFF | ON | 固定長 tok/s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Mage-VL-Cowork Q3_K_M / MTP off / CPU 17層 / GPU 19層＋出力層（-ngl 20） | 新規推論 | failed | 19/80 | 21/80 | 未完了 | 未完了 | 32.43 |

## 途中終了・未実施

保存できた分の正解数であり、全問の正答率ではありません。

- 20261031-mage-q3-text-64k-q3-off / humaneval / 思考off: failed、保存 0/20、保存分の正解 0。TimeoutError('timed out')

- 20261031-mage-q3-text-64k-q3-off / humaneval / 思考on: not-started、保存 0/20、保存分の正解 0。

不正なツール出力をllama.cppが拒否したHTTP 500は失敗として集計し、出力の修正や再試行はしていません。この応答では生成トークン数・思考の有無・終了理由が返らず不明です。トークン合計と打ち切り件数は統計が取得できた回答だけの値です。

bfcl / 思考off / irrelevance_139
bfcl / 思考off / irrelevance_163
bfcl / 思考off / multiple_28
bfcl / 思考on / multiple_163
bfcl / 思考on / parallel_189
bfcl / 思考on / parallel_28
bfcl / 思考on / parallel_7
bfcl / 思考on / simple_python_327
bfcl / 思考on / simple_python_379

## 容量などで測定できなかった条件

[
  {
    "model_manifest": "configs/models/mage-vl-cowork-q3-k-m.json",
    "mtp": [
      "on"
    ],
    "thinking": [
      "off",
      "on"
    ],
    "benchmarks": [
      "bfcl",
      "humaneval"
    ],
    "capacity_run": "20261031-mage-q3-text-64k-capacity-on",
    "reason": "Native MTP probe failed; no positive draft count. No ON capability score is assigned."
  },
  {
    "model_manifest": "configs/models/mage-vl-cowork-q4-k-m.json",
    "mtp": [
      "off"
    ],
    "run": "20261031-mage-q4-text-64k-parser-errors-mage-text-off",
    "reason": "Q4 did not finish all 200 answers; its partial evidence is retained, not counted as a complete comparison cell."
  }
]
