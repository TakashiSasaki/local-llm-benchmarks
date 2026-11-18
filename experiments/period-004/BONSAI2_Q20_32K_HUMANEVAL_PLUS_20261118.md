# Ternary Bonsai 2 27B Q2_0の32K HumanEval+（2026年11月18日）

TUFA15でBonsai 2 27B Q2_0のHumanEval+全164問を各1回生成し、保存済みのLFM3とGemma 4の回答の採点結果に並べた。生成はローカルllama.cpp b11960 CUDA 12.4、採点はネットワーク接続のないDebian 12 VMの公式EvalPlus v0.3.1、HumanEval+ v0.1.10。各問の最終回答欄に公式のコード抽出処理を適用し、基本・追加テストを実行した。欠測・除外・採点不明は各0件。

| モデルと生成方式 | HumanEval基本 | HumanEval+ | API応答時間中央値 | 全164問のAPI応答時間合計 |
| --- | ---: | ---: | ---: | ---: |
| Bonsai 2 27B Q2_0・チャット Thinking ON | 159/164（96.95%） | 152/164（92.68%） | 55.20秒 | 3時間8分18秒 |
| LFM3-1.7B Q8_0・チャット Thinking ON | 154/164（93.90%） | 147/164（89.63%） | 22.45秒 | 1時間29分59秒 |
| Gemma 4 E4B Q4_K_M・コード補完 | 132/164（80.49%） | 122/164（74.39%） | 6.70秒 | 32分8秒 |

BonsaiはLFM3の初回成績より正味5問（3.05ポイント）上だった。Bonsaiだけが合格した問題が11問、LFM3だけが合格した問題が6問。全164問で思考欄を確認し、最終回答は163問にあった。HumanEval/132は16,384出力トークンで最終回答が空のまま終了し、不合格に含めた。基本テスト合格159問のうち、追加テストで7問が不合格。[設問別結果](../../runs/period-004-bonsai2-27b-q20-32k-humaneval-plus-20261118/summaries/per-task.json)

## 生成条件

Bonsaiはコンテキスト32,768、最大出力16,384、seed 42、1スロット、MTP OFF。チャットテンプレートはGGUF内蔵版。コードを求める英語ユーザーメッセージは、LFM3のチャット試験と同じEvalPlus v0.3.1の形式を用いた。

Prism MLのThinking向け設定に従い温度1.0、top_p 0.95、top_k 20、min_p 0.05、presence_penalty 0、repeat_penalty 1.0を明示した。reasoning_effortはmediumを選択し、xhighと異なる入力をレンダリングすることを検証した。LFM3は温度0.1、top_k 50、repeat_penalty 1.1などのLiquid AI推奨設定、コンテキスト65,536、F16 KV、全層GPU指定。Gemmaはコード補完、コンテキスト65,536、F16 KV、28層GPU指定だった。モデル・生成方式・サンプリング・思考指定・KV精度・配置が異なる条件間の比較である。[Prism MLの設定](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf#best-practices) · [LFM3の初回測定](LFM3_Q8_CHAT_THINKING_HUMANEVAL_PLUS_20261117.md) · [Gemmaの測定](HUMANEVAL_PLUS_20261117.md)

LFM3の不合格17問を32,768出力トークンで再試行した148/164は二段階の運用成績として別途保存されている。上の表は各モデルの初回1回答を採点した値を掲載した。[LFM3の再試行](LFM3_Q8_CHAT_THINKING_32K_RETRY_20261117.md)

## 32Kでのメモリ配置

KVキャッシュはK/Vともq4_0を選択した。全65層GPU指定は起動成功し、専用VRAMは7,895 MiBだった。容量の余裕を確保して、58層指定を本測定条件として選び、出力重みをCUDA0に明示した。起動ログは58/65層のGPU配置を報告した。

本測定のCUDA0モデルバッファは6,206.93 MiB、ホスト側モデルバッファは1,055.20 MiB。KVはCUDA0 540 MiBとCPU 36 MiB、再帰状態はCUDA0 130.92 MiBとCPU 18.70 MiBだった。生成速度中央値は17.09 tokens/s、システム全体の専用VRAMピーク観測値は7,293 MiB。Windowsのプロセス別カウンターでも専用約7,281 MiB、共有約1,158 MiBを1回観測した。共有値にはホスト確保分の影響が含まれ、ページ移動やスラッシングは測定していない。[配置・容量プローブ](../../runs/period-004-bonsai2-27b-q20-32k-humaneval-chat-20261118/configs/gpu-probes/partial-58-kv4/result.json) · [Windows GPUメモリ観測](../../runs/period-004-bonsai2-27b-q20-32k-humaneval-chat-20261118/configs/wddm-memory-observation.json)

## 取得と保存先

Prism ML公式のQ2_0ファイルは7,626,008,928 bytes、リビジョン839bd57023c1558945afea70a74fa83c054f35f9、SHA-256 4f99aed01b8a877e153f9aa6569a4440fe17c59701cc0953e36d7f460549e70e。サイズと全ファイルハッシュを照合した。モデルはリポジトリ外のmodelsに保存し、取得済みの部分ファイルと範囲キャッシュも保全した。終了時のCドライブ空きは約73.27 GiB。測定用サーバーと採点VMの終了を確認した。

[生成run](../../runs/period-004-bonsai2-27b-q20-32k-humaneval-chat-20261118/manifest.json) · [採点集計](../../runs/period-004-bonsai2-27b-q20-32k-humaneval-plus-20261118/summary.json) · [比較データ](reports/bonsai2-32k-humaneval-comparison-20261118.json)
