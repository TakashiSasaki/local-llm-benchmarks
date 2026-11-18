# Gemma 4 E4B: HumanEval+ 英語チャット・Thinking ON

2026年11月18日。HumanEvalPlus v0.1.10の164問を各1回答、seed 42、出力上限16,384トークンで生成した。164問すべてで思考と最終回答を確認し、上限到達・除外・採点状態不明はなかった。思考は最終回答の抽出対象には含めない。

| モデル・量子化 | HumanEval 基本テスト | HumanEval+ | 生成時間中央値 | 上限到達 |
|---|---:|---:|---:|---:|
| Gemma 4 E4B IT Q4_K_M | 155/164 (94.51%) | 150/164 (91.46%) | 64.70秒 | 0 |
| LFM3-1.7B Text Q8_0 | 154/164 (93.90%) | 147/164 (89.63%) | 22.45秒 | 4 |
| Ternary Bonsai 2 27B Q2_0 | 159/164 (96.95%) | 152/164 (92.68%) | 既存記録参照 | 既存記録参照 |

全モデルの各164問のユーザーメッセージが完全一致することを保存済みリクエストで照合した。いずれも英語チャット、Thinking ON、出力上限16,384、同じEvalPlusデータと採点器を用いた。ただしサンプリングとハードウェア配置には差があり、点差をモデルの能力だけの差と断定できない。各モデル1試行であり、ばらつきも未評価。

Gemmaの実際の全164リクエストはtemperature 1.0、top-p 0.95、top-k 64、min-p 0、repeat penalty 1.0。LFM3はtemperature 0.1、top-p 1.0、top-k 50、min-p 0、repeat penalty 1.1。Bonsaiはtemperature 1.0、top-p 0.95、top-k 20、min-p 0.05、repeat penalty 1.0、reasoning effort medium。GemmaとLFM3はコンテキスト65,536・KV f16で、GPUオフロードはGemma 28層、LFM3全層。Bonsaiはコンテキスト32,768・KV q4_0、GPU 58層。

Gemmaの生成runのmanifestと、その内容を転記した採点summaryには、汎用補完モード用のtemperature 0.6・top-k 20、停止文字列、Windows採点予定の古い記述が残っている。今回実際に使われたのは `chat_request_options` と各rawファイル内の `request` であり、上記の通り。古い記録を上書きせず、この差をここに明記する。

採点はEvalPlus 0.3.1、commit `e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2`、Debian 12/Python 3.11.2のネットワーク接続なしVM、2 workers。同一の英語チャット回答からEvalPlusのsanitizeでコードを抽出し、基本・追加テストを実施。既知の正解・不正解の対照も実行した。Gemmaは基本のみ合格して追加テストで失敗したものが5問。生成時間の合計は10,905.35秒、出力トークン中央値1,515.5、デコード速度中央値23.55 tokens/s。モデルSHA-256は `85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87`。

生成・生回答: `runs/period-004-gemma-e4b-chat-thinking-humaneval-20261118/`。採点・問題別結果: `runs/period-004-gemma-e4b-chat-thinking-humaneval-plus-20261118/`。採点は保存済み回答から行い、採点段階で追加生成は行っていない。既存のコード補完方式Gemma結果やLFM3失敗問のみの再試行は上表に混ぜていない。
