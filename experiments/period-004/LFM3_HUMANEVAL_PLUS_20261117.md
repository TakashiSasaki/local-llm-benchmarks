# LFM3-1.7B TextのHumanEval+（2026年11月17日）

TUFA15でLiquidAI LFM3-1.7B Text QAD-Q4_0の全164問を各1回生成し、Gemma 4 E4Bの既存結果と問題ごとに比較した。両モデルともEvalPlus v0.3.1、HumanEval+ v0.1.10、オフラインのDebian 12 VMで採点。LFM3の除外・欠測は0件。

| モデル | HumanEval基本 pass@1 | HumanEval+ pass@1 | 1問のAPI応答時間中央値 |
| --- | ---: | ---: | ---: |
| LFM3-1.7B Text QAD-Q4_0 | 50/164（30.49%） | 48/164（29.27%） | 0.58秒 |
| Gemma 4 E4B IT Q4_K_M | 132/164（80.49%） | 122/164（74.39%） | 6.70秒 |

LFM3は基本テストで114問不合格。基本テストを通過した50問のうち、追加テストでHumanEval/22とHumanEval/86が不合格になった。元のプロンプトと補完を連結したコードのホスト側構文確認では116問が構文解析できた。出力上限到達は0件。LFM3とGemmaのHumanEval+の差は45.12ポイント。LFM3だけが合格した問題は2問、Gemmaだけが合格した問題は76問。[設問別結果](../../runs/period-004-lfm3-1p7b-qad-q4-humaneval-plus-20261117/summaries/per-task.json)

生成はllama.cpp b11960 CUDA 12.4のローカル `/completion`。HumanEvalの原文プロンプト、コンテキスト65,536、出力上限16,384、温度0.6、top_p 0.95、top_k 20、min_p 0、seed 42、同一の停止文字列を用いた。164問の送信内容をGemmaの記録と照合した。両方のリクエストで繰り返しペナルティを省略しており、実効値はLFM3がGGUF既定の1.1、Gemmaが1.0だった。記録された全164回答にこの差がある。

LFM3は全層GPU指定、Gemmaは28層GPU指定。量子化、配置、実効ペナルティ、出力長が異なる。API応答時間は各リクエストの開始から応答の受信までで、ロード時間と採点時間を集計対象から外した。生成速度中央値はLFM3 167.55 tokens/s、Gemma 28.71 tokens/s。LFM3のピーク専用VRAM使用量はシステム全体の観測値で2,065 MiB。

[生成記録と実行条件](../../runs/period-004-lfm3-1p7b-qad-q4-humaneval-20261117/manifest.json) · [採点・比較集計](../../runs/period-004-lfm3-1p7b-qad-q4-humaneval-plus-20261117/summary.json) · [Gemmaの評価報告](HUMANEVAL_PLUS_20261117.md)
