# Gemma 4 E4B公式assistantのMTP小規模試験

2026-11-18、既存unsloth Gemma 4 E4B IT Q4_K_M（SHA-256 `85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87`）とllama.cpp b11960 CUDA 12.4で実施。Googleの `google/gemma-4-E4B-it-assistant` をggml-orgがGGUF変換したBF16版（`ggml-org/gemma-4-E4B-it-GGUF` revision `8903cb408c7df39cde2ed15fac397e6d7be92951`、171,766,880 bytes、SHA-256 `5fe3a6c5ebd2f241d9f27d2529fbf023564a6ac4c3db501fa7837887f37ece77`）を取得してサイズとハッシュを検証した。

両条件で同じ英語HumanEval/0〜2のチャット入力、Thinking ON、temperature 1.0、top-p 0.95、top-k 64、min-p 0、repeat penalty 1.0、seed 42、最大出力1,024、コンテキスト65,536、F16 KV、1スロット、全43層とKVのCUDA配置。MTPは `draft-mtp`、最大候補3、assistant全層GPU指定。入力リクエストは3問すべて両条件で完全一致した。

| 問題 | MTPなし decode tokens/s | MTPあり decode tokens/s | 比率 | 採用 / 候補 |
|---|---:|---:|---:|---:|
| HumanEval/0 | 65.40 | 144.75 | 2.21倍 | 679 / 1,029 |
| HumanEval/1 | 65.46 | 133.60 | 2.04倍 | 650 / 1,115 |
| HumanEval/2 | 65.79 | 148.46 | 2.26倍 | 330 / 489 |

速度の中央値は65.46→144.75 tokens/s（2.21倍）。サーバーの推論タイミングで、生成されるトークン数・内容は条件間で異なる。候補合計2,633、採用1,659（63.0%）。専用VRAM使用量のシステム全体サンプルのピークはMTPなし6,499 MiB、MTPあり6,753 MiBで差254 MiB。温度・時系列・標本数等の影響がある概算で、追加モデルのみの厳密な消費量ではない。起動ログでは本体43/43層・CUDAモデル5,091.51 MiB・CUDA KV 1,064 MiB、assistant 5/5層・CUDAモデル148.77 MiB・CUDA_Hostモデル128 MiBを確認。OS共有GPUメモリの測定値はなし。

問題0・1は両条件とも1,024出力上限に到達し、問題1では両条件とも最終回答が空。問題2は両条件とも正常停止して最終回答あり。生成コードは実行・採点していない。3問×各1回であり、正答率・長文時の速度・常時2倍の保証ではない。今までのHumanEval+ 164問と出力上限が異なるため、正答率比較に使用しない。MTP ON/OFFは連続してMTP ONから先に測定し、両条件でモデルサーバーを終了した。

生回答・実行条件・各メモリサンプル・サーバーログ: `runs/period-004-gemma-e4b-mtp-small-probe-20261118/`。対応する既存164問の測定: [全GPUと28層GPUの比較](GEMMA4_ALLGPU_HUMANEVAL_PLUS_20261118.md)。
