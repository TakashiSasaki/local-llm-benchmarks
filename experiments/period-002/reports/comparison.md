# 第2期 主比較 — 保存済み部分結果

2026-11-06監査。測定停止中、期はopen。**588/1,600回答を保存、未収集1,012回答**。11条件完了・1条件部分収集・20条件未実施。速度probe、smoke、採点replayを新規能力回答に含めません。

| 配布物（すべてQ4_K_M、MTP OFF） | BFCL OFF | BFCL ON | HumanEval OFF | HumanEval ON |
| --- | ---: | ---: | ---: | ---: |
| 通常 Qwen3.5-4B | 69/80 | 70/80 | 14/20 | 17/20 |
| Abliterix4B | 71/80 | 65/80 | 16/20 | 17/20 |
| 通常 Qwen3.5-9B | 73/80 | 75/80 | 19/20 | 7/8（部分・残り12） |
| Huihui9B | 未実施 | 未実施 | 未実施 | 未実施 |
| Heretic9B | 未実施 | 未実施 | 未実施 | 未実施 |
| Defiant9B | 未実施 | 未実施 | 未実施 | 未実施 |
| 通常 Qwen3.6-35B-A3B | 未実施 | 未実施 | 未実施 | 未実施 |
| Huihui35B-A3B | 未実施 | 未実施 | 未実施 | 未実施 |

通常9B HE ONの7/8は保存済み8問の得点です。20問の完了得点にも、残り12問を不正解にした7/20にも換算しません。親/条件manifestのfailedは実行制限によるdeferred（model_failure=false）です。

## 出力・時間・形式

capはfinish_reason=lengthかつ要求出力数まで到達した回答。空finalはcontentもtool_callsも空の回答。BFCLの無呼び出し正解は実ツール実行成功とは異なります。秒数は保存済み回答のAPI待機時間合計、decode速度は保存されたAPI decode時間で重み付けした値で、短文probeとは別です。

| 配布物 | 条件 | 保存/予定 | cap | 空final | decode形式エラー | API合計秒 | decode tok/s | legacy HE replay |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 通常 Qwen3.5-4B | bfcl OFF | 80/80 | 0 | 0 | 0 | 146.6 | 73.41 | — |
| 通常 Qwen3.5-4B | bfcl ON | 80/80 | 0 | 0 | 0 | 313.6 | 73.28 | — |
| 通常 Qwen3.5-4B | humaneval OFF | 20/20 | 0 | 0 | 0 | 48.4 | 73.95 | 14/20 |
| 通常 Qwen3.5-4B | humaneval ON | 20/20 | 2 | 2 | 0 | 2991.4 | 60.18 | 17/20 |
| Abliterix4B | bfcl OFF | 80/80 | 0 | 0 | 0 | 160.5 | 73.23 | — |
| Abliterix4B | bfcl ON | 80/80 | 0 | 0 | 0 | 353.8 | 72.86 | — |
| Abliterix4B | humaneval OFF | 20/20 | 0 | 0 | 0 | 59.8 | 73.99 | 16/20 |
| Abliterix4B | humaneval ON | 20/20 | 1 | 1 | 0 | 1954.9 | 62.90 | 16/20 |
| 通常 Qwen3.5-9B | bfcl OFF | 80/80 | 0 | 0 | 0 | 436.8 | 22.88 | — |
| 通常 Qwen3.5-9B | bfcl ON | 80/80 | 0 | 0 | 0 | 983.5 | 22.74 | — |
| 通常 Qwen3.5-9B | humaneval OFF | 20/20 | 0 | 0 | 0 | 207.0 | 22.86 | 19/20 |
| 通常 Qwen3.5-9B | humaneval ON | 8/20 | 1 | 1 | 0 | 7095.6 | 10.07 | 7/8 |

通常4B HE ONで2問、Abliterix4B HE ONで1問がcapに到達。Abliterix HE ONの主得点17/20に対して、旧制限付きreplayは16/20です。通常9B HE ONのHumanEval/35はprompt130＋completion64,000、約6,763.7秒、no_final_code、不正解。出力上限でありAPI待機上限7,200秒やcontext65,536の不足ではありません。

## 速度probeとメモリ

速度は256 tokens×3 prompts×3回、思考OFFの中央値です。メモリは各モデルrun全体の約3秒間隔の標本で、GPUはシステム全体。条件ごとの瞬間最大値、共有GPUメモリ、連続した電力/温度/clockの統制は保証しません。

| 配布物 | 配置 | 短文decode tok/s | GPUピーク MiB | 最小空きRAM GiB | 標本数 |
| --- | --- | ---: | ---: | ---: | ---: |
| 通常 Qwen3.5-4B | 全層 / CPU MoE0 | 73.39 | 4973 | 19.62 | 1729 |
| Abliterix4B | 全層 / CPU MoE0 | 73.13 | 4971 | 19.28 | 1258 |
| 通常 Qwen3.5-9B | -ngl24 / CPU MoE0 | 22.77 | 5955 | 17.80 | 4249 |

9B共通-ngl24は試した候補内で成立した配置です。b11960の-nglは出力層込みで、decoder層数とは異なります。Defiantは-ngl28で7,681 MiB、-ngl24で7,059 MiBを観測。未試験の25〜27を含む理論上の最大配置とは呼びません。

## 対応する問題の変化

| 比較 | 条件 | 改善（誤→正） | 悪化（正→誤） |
| --- | --- | ---: | ---: |
| 通常4B→Abliterix4B | bfcl OFF | 3 | 1 |
| 通常4B→Abliterix4B | bfcl ON | 2 | 7 |
| 通常4B→Abliterix4B | humaneval OFF | 2 | 0 |
| 通常4B→Abliterix4B | humaneval ON | 3 | 3 |

bfcl OFF 改善: simple_python_279, irrelevance_8, irrelevance_26。悪化: irrelevance_22。


bfcl ON 改善: multiple_173, parallel_59。悪化: parallel_163, irrelevance_8, irrelevance_22, irrelevance_55, irrelevance_151, irrelevance_173, irrelevance_189。


humaneval OFF 改善: HumanEval/55, HumanEval/59。悪化: なし。


humaneval ON 改善: HumanEval/7, HumanEval/59, HumanEval/163。悪化: HumanEval/23, HumanEval/57, HumanEval/108。

## 条件と解釈の限界

b11960 / commit8642541b255bfb5dc39cd351a178be09013a55d6、context65,536、F16 K/V、1 slot、MTP OFF、最大出力64,000、入力から32 tokens予約。BFCL固定80問・公式AST・greedy/seed42。HumanEval固定20問・temperature0.6/seed42と保存済みsampler。

HumanEval主採点はhumaneval-b9453e8-windows-full-module-v1。公式test/実行本体を固定し、Windows JobObject/親watchdog（6秒・256 MiB・1 process）に適応。測定用Python3.14.9でcanonical164/164と正解・誤答・無限ループcontrolを検証済み。今回の保存108回答のreplayも一致。EvalPlusや公式Linux環境と完全同一とは呼びません。JobObject/reliability_guardは一般的なOSセキュリティsandboxではありません。

4B対はchat template SHAが一致しますが、Q4_K/Q5_K/Q6_K構成が異なります。これは配布物同士の比較で、拒否方向除去だけの因果効果を示しません。固定少数問題・単一seedから一般的な順位、無検閲性、日本語/数学能力は推定しません。XSTest、数学、日本語、Hermes実接続、MTP ON、追加27Bは別枠の未実施計画です。

## 停止と継続

2026-11-02 18:00 JST頃にshutdown_requestedと元所有プロセス全終了の記録あり。実際の電源断時刻は未検証。2026-11-06監査時、古い監視・関連Windows予約・8089待受・測定writerはなし。古い監視設定はenabled=trueのまま残るため再起動禁止。停止フラグと過去期限を維持し、新しいshutdown予約は作成していません。

再開にはユーザー指示が必要です。既存588回答を維持し、通常9B HE ONの未実施12問を新run/subsetで取得して既存8問を参照集計し、Huihui/Heretic/Defiant9Bの600問、35B対の400問を続けます。旧run/sourceをresume・上書きしません。run_period2_remaining.pyの丸ごと再実行は通常9Bの完了条件を再測定するので禁止。

## 原証拠と再現

[機械可読比較・全問題判定・raw参照・SHA](comparison.json) · [監査と継続手順](../AUDIT.md) · [取得/環境監査](../environment/handoff-20261106.json) · [主採点の定義](../../../vendor/humaneval/b9453e8/README.md)

検証: `python -B -X utf8 tools/verify_period2.py --regrade --report experiments/period-002/reports/comparison.json`（測定用Python）。推論APIには接続せず、rawは読み取り専用です。第1期の原結果・inventory・frozen recipe・比較ページを変更していません。
