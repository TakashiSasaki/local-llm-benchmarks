# Gemma 4 E4BのHumanEval+再採点（2026年11月17日）

TUFA15で生成済みの Gemma 4 E4B IT Q4_K_M の164回答を、公式EvalPlus v0.3.1（`e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2`）とHumanEval+ v0.1.10で再採点した。各問1回答。新規生成0件、欠測・除外0件。[EvalPlus v0.3.1](https://github.com/evalplus/evalplus/releases/tag/v0.3.1) · [データセット](https://github.com/evalplus/humanevalplus_release/releases/tag/v0.1.10)

| 採点条件 | 合格 / 採点 | 不合格 | pass@1 |
| --- | ---: | ---: | ---: |
| EvalPlusのHumanEval基本テスト | 132 / 164 | 32 | 80.49% |
| HumanEval+（基本と追加の両方） | 122 / 164 | 42 | 74.39% |

追加テストで10問が不合格になり、pass@1は6.10ポイント下がった。前回のWindows版HumanEvalの合否と、今回のEvalPlus基本テストの合否は164問すべてで一致した。[前回のWindows採点](../../runs/period-004-gemma-humaneval-score-combined-20261112/summary.json) · [今回の設問別結果](../../runs/period-004-gemma-humaneval-plus-replay-20261117/summaries/per-task.json)

元のHumanEvalのプロンプトと保存済みの補完をそのまま連結し、EvalPlusの `solution` として渡した。HumanEval/115ではデータセット間で `import math` の位置が異なるため、生成時のプロンプトを使用した。生成時の設定は[11月15日の評価報告](GEMMA4_RESULTS_20261115.md#測定条件と出典)に記載。

実行環境はTUFA15上のDebian 12 VM、Python 3.11.2、2ワーカー。未改変の公式 `evalplus.evaluate` を、デフォルトの判定・タイムアウト設定で実行した。VMにはネットワーク機器やホスト共有を接続せず、入力を読み取り専用で取り付けた。ゲストで入力のハッシュと正解・不正解の確認用コードの判定を検証した。

集計、公式採点器の出力、実行引数、依存パッケージ一覧、入力ハッシュを別runに保存した。[集計](../../runs/period-004-gemma-humaneval-plus-replay-20261117/summary.json) · [実行記録](../../runs/period-004-gemma-humaneval-plus-replay-20261117/manifest.json)
