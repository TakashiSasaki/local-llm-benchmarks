# Gemma 4 E4B: MTP ON・出力上限なしのHumanEval+

2026年11月18日。Gemma 4 E4B IT Q4_K_MのHumanEvalPlus v0.1.10全164問を各1回測定し、EvalPlus 0.3.1（commit `e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2`）で採点した。Thinking ON、英語チャット、seed 42、temperature 1.0、top-p 0.95、top-k 64、min-p 0、repeat penalty 1.0、コンテキスト65,536、F16 KV、1スロット、GPU全層。Google E4B assistantのggml-org BF16変換版、llama.cpp b11960、draft-mtp、候補最大3。サーバーの `-n -1` と全164件の `max_tokens: -1` により固定出力上限なし、context shift無効。思考と最終回答は入力と合わせて同じ枠を使う。コードは隔離Linux VMで公式EvalPlus sanitize・採点を行い、既知の正常・失敗対照を実行した。

| 指標 | MTPなし・出力上限16,384 | MTPあり・固定出力上限なし |
|---|---:|---:|
| HumanEval基本 | 155/164 (94.51%) | 155/164 (94.51%) |
| HumanEval+ | 147/164 (89.63%) | 144/164 (87.80%) |
| デコード速度中央値 | 63.08 tokens/s | 151.78 tokens/s |
| 応答時間中央値 | 24.91秒 | 9.87秒 |
| 応答時間合計（生成のみ） | 4,048.32秒 | 1,747.86秒 |
| 専用VRAM使用ピーク（システム全体サンプル） | 6,513 MiB | 6,757 MiB |
| 最長出力 | 4,157 tokens | 5,340 tokens |
| 最終回答空・上限停止 | 0・0 | 0・0 |

生成速度中央値は約2.41倍、応答時間中央値は約2.52倍、応答時間合計は約2.32倍。比較元とのリクエストはaliasと `max_tokens` 以外一致し、比較元も上限到達はなかった。両条件とも出力はすべて16,384未満のため、今回の結果では出力上限拡大の効果を検証できていない。MTPだけの合格は5問、MTPなしだけの合格は8問。同じseedでも全164問の最終回答が異なり、各条件1回のため3問の正答差をMTPによる性能低下とは断定できない。

MTPでは実生成の候補255,345トークン中173,705トークンを採用（68.03%）。思考と最終回答は全164問で確認。最大出力はHumanEval/130の5,340トークン、入力＋出力の最大は5,630トークン。固定上限なしで実行したが、コンテキストを使い切った事例はない。実験中のGPU温度最高観測は85°C、RAMガード停止なし。VRAM値はシステム全体のサンプルで共有メモリは未取得。

起動ログは本体43/43層・CUDA0モデル5,091.51 MiB、assistant 5/5層・CUDA0モデル148.77 MiBとCUDA_Host 128 MiB、KVはCUDA0に1,024 MiBと40 MiBを確認。本体GGUF SHA-256 `85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87`、assistant GGUF SHA-256 `5fe3a6c5ebd2f241d9f27d2529fbf023564a6ac4c3db501fa7837887f37ece77`。[assistantの出所と小規模試験](GEMMA4_MTP_SMALL_PROBE_20261118.md)

生成run: `runs/period-004-gemma-e4b-mtp-thinking-fullctx-humaneval-20261118/`。採点run: `runs/period-004-gemma-e4b-mtp-thinking-fullctx-humaneval-plus-20261118/`。比較元: [MTPなし全GPUのHumanEval+](GEMMA4_ALLGPU_HUMANEVAL_PLUS_20261118.md)。採点サマリーの `only_chat_plus_pass_ids` は今回のみ合格、`only_raw_plus_pass_ids` は比較元のみ合格を意味する汎用取り込み器のラベル。
