# Gemma 4 E4B HumanEval+: 全GPUと28層GPUの比較

2026年11月18日、Gemma 4 E4B IT Q4_K_MでHumanEvalPlus v0.1.10の全164問を各1回答した。前回の28層GPU版と同じ英語チャット指示、Thinking ON、温度1.0、top-p 0.95、top-k 64、min-p 0、repeat penalty 1.0、seed 42、コンテキスト65,536、F16 KV、1スロット、出力上限16,384。164問すべての保存済みリクエストを比較し、モデルalias以外は一致した。前回と同一のGGUF SHA-256 `85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87` とllama.cpp b11960を使用した。

| 指標 | 28層GPU | 全モデルGPU |
|---|---:|---:|
| HumanEval基本 | 155/164 (94.51%) | 155/164 (94.51%) |
| HumanEval+ | 150/164 (91.46%) | 147/164 (89.63%) |
| デコード速度中央値 | 23.55 tokens/s | 63.08 tokens/s |
| 1問の応答時間中央値 | 64.70秒 | 24.91秒 |
| 164問の応答時間合計 | 10,905.35秒 | 4,048.32秒 |
| 出力トークン中央値 | 1,515.5 | 1,564.5 |
| 専用GPUメモリ使用ピーク（システム全体、サンプリング） | 3,061 MiB | 6,513 MiB |
| 出力上限到達・最終回答空 | 0・0 | 0・0 |

速度中央値は約2.68倍、応答時間中央値は約2.60倍、応答時間合計は約2.69倍。モデル起動・採点時間は含まない。全GPU版では43/43層、CUDA0モデルバッファ5,091.51 MiB、CUDA0 KVバッファ1,024 MiBと40 MiBを起動ログから検証してから生成した。起動直後のシステム専用VRAMは6,487/8,188 MiB。共有GPUメモリは監視では取得できず、全GPUプロセスのあらゆるメモリがVRAMにあったとまでは主張しない。

HumanEval+では全GPUだけの合格が2問（HumanEval/121、130）、28層だけの合格が5問（HumanEval/48、76、93、120、122）。同じseedでも生成された最終回答は164問すべてで異なった。配置や数値演算等の違いが影響する可能性はあるが原因は特定していない。各条件1回の結果であり、3問差が配置自体によるものかは判断できない。

両条件の回答を同じEvalPlus 0.3.1（commit `e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2`）、同じHumanEvalPlus v0.1.10、Debian 12ネットワークなしVMで採点。全164問の採点状態を確認し、欠測・除外・上限到達はゼロ。全GPU版生成中のRAM監視は有効で、リソースガード停止なし。

生成と配置根拠: `runs/period-004-gemma-e4b-chat-thinking-allgpu-humaneval-20261118/`。採点結果と問題別結果: `runs/period-004-gemma-e4b-chat-thinking-allgpu-humaneval-plus-20261118/`。比較元: `runs/period-004-gemma-e4b-chat-thinking-humaneval-plus-20261118/`。採点サマリーの `only_chat_plus_pass_ids` は今回のみ合格、`only_raw_plus_pass_ids` は比較元のみ合格を意味し、名称は汎用取り込み器の歴史的なラベルである。
