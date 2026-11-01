# Empero Qwen3.8 Distill: 3bit / 4bitとMTPの比較

測定日2026-10-31。主比較の4構成・16条件・800回答は完了しました。[比較ページ](../reports/20261031-empero-mtp-load-none/index.html)、[GitHubで読める集計表](../reports/20261031-empero-mtp-load-none/summary.md)、[集計JSON](../reports/20261031-empero-mtp-load-none/matrix-data.json)を参照してください。

## 主結果

| 量子化 | MTP | BFCL OFF /80 | ON /80 | HumanEval OFF /20 | ON /20 | 固定長生成 tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| IQ3_M | OFF | 70 | 72 | 18 | 19 | 33.73 |
| IQ3_M | ON | 72 | 73 | 18 | 19 | 39.07 |
| Q4_K_M | OFF | 71 | 72 | 18 | 19 | 38.20 |
| Q4_K_M | ON | 71 | 71 | 18 | 17 | 46.47 |

得点は従来の主採点です。MTPによる固定長生成の速度比は3bitで1.158倍、4bitで1.217倍でした。BFCLは4bitでも満点に届かず、MTPを有効にすれば正答数が増えるという結果ではありません。4bit・思考ONのAPI総時間は約656秒から1,583秒へ増えました。後述の1問の64,000出力トークン打ち切りが大きく影響しています。打ち切りは主比較全800回答でこの1件でした。

HumanEvalの4bit・思考ONは、MTP OFFの1件、MTP ONの2件に既知の `type()` 不許可が含まれていました。既存の補助ポリシーではOFFが19→20/20、ONが17→19/20です。OFFの `HumanEval/22`、ONの `HumanEval/22` と `/151` が救済されました。ONの `/163` はアルゴリズムの不正解として残りました。3bitの得点は補助採点でも変わりません。主結果は置き換えていません。初回mmapの4bit OFFも別auditで19→20/20を確認しました。

## 比較条件

- 対象: `empero-ai/Qwen3.8-35B-A3B-Distill-GGUF`、revision `b1f9d1dcc3de8aa867669b0ab919384aeeb9b8d5`。
- 3bit: 既存IQ3_M。4bit: Q4_K_M、21,713,462,944 bytes、SHA256 `196103269085bc54c9b8f49ed21e9f53e1b56b465e8b796c6d8e31e06f63cfa5`。重みはリポジトリ外。
- b11960 / 8642541b2 / CUDA12.4、65,536 context、最大64,000出力、1 slot、F16 KV、8 threads、Flash Attention auto、同じ最初の34 MoE層をCPUへ配置。
- 各量子化でMTP OFFとONを新規測定。ONは `--spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-p-min 0 --spec-draft-ngl all --spec-draft-n-ubatch 128`、draft KVもF16。
- 主比較の3bitは既定のmmap、4bitは `--load-mode none`。4bitは後述のRAM保護停止を受け、OFF/ONの両方で読み込み方式を揃え直しました。
- BFCL固定80問・公式AST採点、HumanEval固定20問・既存の制限付きWindows採点器。それぞれ思考OFF/ONで1回答。合計4構成×200回答=800回答。
- 各構成の固定長速度試験は、オリジナルの文章・コード・JSONプロンプト各3回、思考OFF、greedy、256出力トークン。`ignore_eos=true` で長さを固定し、64トークンの予熱は集計から除外。正答率の試験ではありません。

4bitとMTPの追加メモリを確保するため、主比較の全構成はCPU MoE 34層です。過去のIQ3_M測定は30層だったので、その速度をMTP OFFの対照に流用しません。各量子化内ではMTP OFF/ONの読み込み方式を揃えていますが、3bitと4bitの間では読み込み方式も異なります。量子化ファイルによってテンソルごとの精度・較正等も異なり得るため、純粋なビット数だけの効果と断定しません。今回の3bit/4bitのテンプレートハッシュは同一でした。

以前のEmpero試験と同じCPU MoE 30層でも、IQ3_Mの速度のみを新規にOFF/ON測定しました。**40.48→43.74 tok/s、MTPで約8.1%向上**しました。主比較の800回答には含めません。run IDは `20261031-empero-mtp-load-none-iq3-cpu30-{off,on}`、`run_mtp_study.py --speed-only --cpu-moe 30` を使いました。この補足でCPU30層の能力得点を測ったことにはしません。

新しいIQ3_M・MTP OFFのBFCL思考OFFは70/80で、過去の72/80に対して `simple_python_279` と `parallel_8` が不正解へ変わりました。前者は引数の語句、後者は呼び出し件数が変化しています。同じ重み・seedでも実行配置等が異なれば回答の一致を保証できないため、今回の新規対照同士を比較します。回答の同一性を集計する際は、ランダムに発行されるtool-call IDを除外します。

モデルの取得中に3bit測定を開始しています。通常のPC上のブロック順測定であり、背景処理・温度・実行順の影響を完全に除いた測定ではありません。スループットの固定長試験と、生成量が変わり得るベンチマークの総時間を分けて比較してください。

## 4bitのRAM保護停止と読み込み方式の変更

[初回mmap試行](../reports/20261031-empero-quant-mtp-64k/index.html)は別に保存しました。4bit・MTP OFFは200回答を完了しましたが、MTP ONは固定長試験の後、BFCL思考OFFを6問保存したところで保護停止しました。空きRAMが1GiB未満で3回連続検出されたため、所有サーバーを停止したものです。最小空きRAMは921,505,792 bytes、最大GPUは7,231MiBでした。**コンテキスト不足による打ち切りでも、確認済みのOOMでもありません。**

既存データは書き換えず、`20261031-empero-mtp-load-none` で4bitのOFF/ONを両方 `--load-mode none`（mmapを使わない読み込み）にして新しく測り直しました。モデルファイル、CPU MoE34層、64K、F16 KV等は保ちます。初回3bitの400回答は元のIDのまま参照し、再生成とは扱いません。主比較は800回答ですが、初回4bitの200回答と中断までの6回答も別に残ります。

変更後の短い予備試験では最小空きRAMが約5.3GiBになりました。これはサンプル値であり、全用途での余裕を保証する値ではありません。Windowsのprocess private bytesはcommitで、物理RAM使用量やGPU使用量と同じものではありません。

## MTPの動作確認

今回のランタイムでは、MTPをCLIで有効にしても `/props` のデフォルト `speculative.types` は `none` のままでした。一方、実際の `/completion` 応答では `none,draft-mtp`、`timings.draft_n` / `draft_n_accepted`、サーバーログにもdraft acceptanceが記録されました。**デフォルトpropsの文字列だけで実行時のOFF/ONを判定しません。** OFFは実測draft数0、ONは実測draft数が正であることも照合します。

`20261031-empero-iq3m-mtp-preflight` は、このpropsの値を厳密に検査したため収集前に終了した計測器側の失敗記録です。モデルがMTP非対応という結果ではありません。修正後の `...-preflight-02` では3bit・64KでMTP動作を確認しました。予備試験は短い128トークン出力で、主比較の得点や速度へ混ぜません。

MTPは高速化の仕組みで、思考設定とは独立しています。今回の実行ではMTPの有無で回答内容も変わったため、得点・問題ごとの成否変化・同一回答数・draft採用数を別々に保存します。差が生じた内部原因は、この測定だけでは特定していません。

4bit・MTP ON・思考ONの [`irrelevance_139`](../runs/20261031-empero-mtp-load-none-q4-on-bfcl-on/raw/irrelevance_139.json) は、思考だけで64,000出力トークンを使い切り、約1,113秒で `finish_reason: length` となりました。入力333・合計64,333トークンで、65,536のコンテキスト容量自体には収まっています。最終回答は空、ツール呼び出しは0件でした。呼び出し不要問題のため公式AST採点では正解ですが、回答の完了を意味しません。同じ問題の4bit・MTP OFF・思考ONは約20.9秒・723出力トークンで自然終了しました。固定長の生成速度と、課題を完了するまでの時間を分けて評価すべきケースです。

参考: [llama.cppの固定リビジョンの例](https://github.com/ggml-org/llama.cpp/blob/8642541b2/examples/speculative-simple/README.md)、[モデル配布元](https://huggingface.co/empero-ai/Qwen3.8-35B-A3B-Distill-GGUF/tree/b1f9d1dcc3de8aa867669b0ab919384aeeb9b8d5)。BFCLは外部関数を実行せず、今回の試験はHermesの実ツール往復とは別です。

## 再現・照合

[公開実験定義](../configs/empero-quant-mtp-64k.json)と[速度試験の共通入力](../datasets/mtp-speed/v1/prompts.json)も保存しています。共通入力は初期3bit試験の保存ソースにある3プロンプトと同じ原文で、照合器でも各応答の入力との一致を確認します。

`scripts/download_pinned_model.py` で固定ハッシュのモデルをリポジトリ外へ取得し、`scripts/run_mtp_study.py` で1構成ずつ起動・収集・停止します。既存ポートが使用中ならサーバーを交換せず終了します。元runのIDは集計JSONの `cells[].run` と、親manifestの `config.cell_runs` に記録し、子runにspeed / BFCL / HumanEvalを保存します。

新しく全4構成を測る例です。Python実行ファイルは同じ採点環境の3.14.9を指定し、毎回新しいprefixを使います。`--reference-iq3-prefix` を指定した場合だけ、同じモデルハッシュ・CPU34層・64Kの完了済み3bitを元IDで参照します。

```powershell
python -B scripts/run_mtp_matrix.py --prefix NEW_STUDY_ID --q4-load-mode none --benchmark-python PATH_TO_PYTHON_3_14_9
python -B scripts/finish_mtp_extras.py --prefix NEW_STUDY_ID --benchmark-python PATH_TO_PYTHON_3_14_9
```

```powershell
python -B scripts/report_mtp_study.py
python -B tools/verify_mtp_study.py --report publication/mtp-validation.json
```

照合は保存済みBFCLを公式採点器で再採点し、HumanEvalの保存済み採点・固定長・MTP動作・ソースハッシュ・停止記録を確認します。新しいモデル推論や生成コードの再実行はしません。

`finish_mtp_extras.py` は主比較の完了後にCPU MoE30層の速度試験と、保存済みHumanEval失敗の補助ポリシー再採点を行います。主採点の得点は変更しません。`publish.ps1` でもMTP比較の保存データ照合を実行します。公開用のモデル識別JSONは `configs/models/` に含め、重みファイルは含めません。
