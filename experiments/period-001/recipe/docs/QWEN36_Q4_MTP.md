# Qwen3.6-35B-A3B Q4_K_M × MTP

2026-10-31測定完了。新規2構成・8条件・400回答、固定長速度18試行を収録しました。[比較ページ](../reports/20261031-qwen36-q4-mtp-64k/index.html)、[GitHub用集計表](../reports/20261031-qwen36-q4-mtp-64k/summary.md)を参照してください。

## 結果

| MTP | BFCL 思考OFF /80 | ON /80 | HumanEval 思考OFF /20 | ON /20 | 固定長生成 tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| OFF | 75 | 73 | 18 | 19 | 36.64 |
| ON | 74 | 73 | 18 | 19 | 47.38 |

固定長生成の中央値はMTPで**1.293倍、約29.3%向上**しました。本文が同一だった速度試験は0/9で、同一プロンプト・同一出力トークン数による比較です。BFCLの全問正解は、今回のどの設定でも達成しませんでした。MTPによる成否変化はBFCL思考OFFの `irrelevance_26` の正解→不正解1件だけで、BFCL思考ONとHumanEvalの成否は変わりませんでした。

| 条件 | MTP OFF 合計秒 | ON 合計秒 | 所要時間の短縮 |
| --- | ---: | ---: | ---: |
| BFCL 思考OFF | 413.6 | 316.6 | 23.4% |
| BFCL 思考ON | 1,823.5 | 1,341.9 | 26.4% |
| HumanEval 思考OFF | 149.1 | 107.3 | 28.0% |
| HumanEval 思考ON | 1,344.1 | 917.1 | 31.8% |

上の時間は生成API往復の合計です。生成量も変わり得るため、固定長の生成速度とは別の指標です。**全400回答で出力打ち切り0件、最終回答とツール呼び出しが両方空の応答0件**でした。

HumanEval思考ONの残る1件は両MTP条件とも `HumanEval/22` の `type()` 不許可エラーです。既存の補助ポリシーによる再採点では、両方とも**20/20**でした。思考OFFの `/62` と `/163` のアルゴリズムの失敗は補助採点でも残り、18/20です。主得点は置き換えず、別auditに記録しています。監査JSONの `iq3_m` は過去のスキーマを維持したキー名で、実際のモデルは `model` とmanifestにあるQwen3.6 Q4_K_Mです。

| MTP | 最小空きRAM GiB | 最大GPU使用 MiB |
| --- | ---: | ---: |
| OFF | 5.16 | 6,583 |
| ON | 4.76 | 7,815 |

RAM/GPUはサーバー稼働中のサンプル値で、GPUはシステム全体です。RAM保護停止はなく、測定用サーバーは両条件とも終了しました。

## 条件

- 以前のIQ3_Mと同じBartowski配布、同じ固定revision `5c2410d71524f4f72b023ce8daf7a80528226d5f` のQ4_K_M。
- `Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`、22,285,080,192 bytes、SHA256 `b46fedd33e0bfb0cae308aa3c158d0a4b2c4a1d2185a1ed6f093cdaf39064772`。モデル重みと取得用の一時ファイルはGit管理外。
- llama.cpp b11960 / 8642541b2 / CUDA12.4、65,536 context、最大64,000出力、F16 KV、1slot、8threads、CPU MoE34層、`--load-mode none`。Emperoの4bit比較と配置を揃えます。
- MTP OFF/ONそれぞれBFCL80問・HumanEval20問を思考OFF/ONで測る、2構成・8条件・新規400回答。
- BFCLは従来の固定80問・公式AST採点・greedy。HumanEvalは固定20問・seed42・temperature0.6、既存の制限付きWindows採点器とPython3.14.9。
- 固定長の速度試験も従来と同じオリジナル3プロンプト各3回、思考OFF・greedy・256出力トークン、`cache_prompt=false`。64トークン予熱を集計から除外。
- ONは `draft-mtp`、draft最大3、p-min0、draft GPU全層、draft ubatch128、draft KV F16。起動引数に加え実応答のdraft/accepted数も確認します。デフォルトpropsがnoneでも実行時のMTP無効とは判定しません。

最初に同じ配置・64KのMTP ON予備試験で読み込みと動作を確認します。予備試験は128トークン×3種類で、主比較の速度や正答数に混ぜません。所有サーバーのRAMを監視し、空きRAMが1GiB未満で3回連続したら停止して証拠を保存します。他のサーバーを交換・停止しません。

## 比較の範囲

先行Emperoの4構成は元runの参照です。今回のQwen3.6新規400回答には数えず、以前の測定を再生成と表示しません。以前のQwen3.6 IQ3_MはCPU MoE30層で、今回のMTP OFFの速度対照には流用しません。

以前のQwen3.6 IQ3_Mの主得点はHumanEval思考OFF19/20・ON19/20、BFCL OFF74/80・ON72/80、出力打ち切り0件でした。[当時の記録](IQ3_M.md)を得点の参考として参照できます。同じ配布元・revisionでも、今回とはCPU配置や量子化のテンソル精度等が異なるため、差をビット数だけの効果と断定しません。

得点は各問題1回答、速度は各プロンプト3回の小規模試験です。条件ごとのブロック順で、実行順の無作為化はしていません。MTPの有無で本文や生成量が変わることがあるため、固定長の速度・総時間・問題別成否・出力打ち切り・空の最終回答を別々に保存します。BFCLはAST採点で、Hermesや外部関数の実行試験ではありません。

65,536は設定したコンテキスト容量です。入力は短い固定問題・速度プロンプトで、64K近い長文入力の性能試験ではありません。実際の入力・出力トークン数は各応答のusageと保存された要求で確認できます。

HumanEvalの既知の`type()`制限は、既存の補助ポリシーで保存済み失敗コードを再採点する別replayで確認します。主得点は書き換えません。

## 再現・保存データの照合

[実験定義](../configs/qwen36-q4-mtp-64k.json)、[モデル識別](../configs/models/qwen36-35b-q4-k-m.json)、[固定速度入力](../datasets/mtp-speed/v1/prompts.json)を保存しています。実測するときは新しいrun IDを使います。

```powershell
python -B scripts/download_pinned_model.py --manifest configs/models/qwen36-35b-q4-k-m.json --model-dir C:\LocalLLM\models --connections 12
python -B scripts/run_mtp_pair.py --prefix NEW_STUDY_ID --definition configs/qwen36-q4-mtp-64k.json --benchmark-python PATH_TO_PYTHON_3_14_9
python -B scripts/report_mtp_pair.py --prefix NEW_STUDY_ID
python -B scripts/mtp_progress.py --prefix NEW_STUDY_ID
python -B tools/verify_mtp_study.py --prefix NEW_STUDY_ID
```

照合コマンドは保存されたBFCLの公式再採点、HumanEvalの保存記録、モデルハッシュ、実行設定、固定長出力、MTP動作、ソースハッシュと停止記録を確認します。新しいモデル推論や生成コードの実行はしません。補助ポリシーauditの実行は別の明示的な手順です。

配布元: [固定revisionのGGUF一覧](https://huggingface.co/bartowski/Qwen_Qwen3.6-35B-A3B-GGUF/tree/5c2410d71524f4f72b023ce8daf7a80528226d5f)。
