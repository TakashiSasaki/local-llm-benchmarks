# LFM3-1.7B Text Q8_0のチャット形式・Thinking ON HumanEval+（2026年11月17日）

TUFA15で公式GGUFのLFM3-1.7B Text Q8_0にHumanEval+全164問を各1回送った。llama.cpp b11960 CUDA 12.4、全層GPU指定、コンテキスト65,536、最大出力16,384トークン、seed 42。GGUFに含まれるLiquid AIのチャットテンプレートを使い、`enable_thinking=true` とした。レンダリングした入力の末尾が `<think>` であることを確認した。コード向け推奨設定の温度0.1、top_k 50、繰り返しペナルティ1.1を指定し、残りはtop_p 1.0、min_p 0に設定した。[Liquid AIの推奨設定とチャットテンプレート](https://huggingface.co/LiquidAI/LFM3-1.7B#inference)

EvalPlus v0.3.1のOpenAI互換バックエンドと同じ形式で、自己完結したPythonコードを求めるユーザーメッセージにHumanEval+ v0.1.10の問題文を添えた。採点では、オフラインのDebian 12 VM上で公式EvalPlusの `sanitize` を最終回答欄に適用した。採点器への入力、公式JSONの出力、ハッシュを突き合わせた。欠測・除外は0件。

| Q8_0の生成条件 | HumanEval基本 | HumanEval+ | API応答時間中央値 | 164問のAPI応答時間合計 |
| --- | ---: | ---: | ---: | ---: |
| コード補完 | 55/164（33.54%） | 52/164（31.71%） | 0.86秒 | 14分25秒 |
| チャット・Thinking ON | 154/164（93.90%） | 147/164（89.63%） | 22.45秒 | 1時間29分59秒 |

チャット条件では、コード補完で合格した52問を含む147問がHumanEval+に合格した。正味95問、57.93ポイント増。追加テストで落ちたのは基本テスト合格154問のうち7問。全164問で思考欄があり、HumanEval/38、47、81、132の4問は出力上限で最終回答が空のまま不合格となった。出力トークン数の中央値は89から2,414へ増え、API応答時間には思考の生成を含む。[設問別結果](../../runs/period-004-lfm3-1p7b-q8-humaneval-plus-chat-thinking-20261117/summaries/per-task.json)

コード補完との差には、Thinking ONに加えて、チャット形式、温度等の生成設定、採点前のコード抽出の変更が含まれる。生成APIの合計時間はモデル起動と採点を除く。[コード補完の評価報告](LFM3_Q8_HUMANEVAL_PLUS_20261117.md)

[生成記録・設定](../../runs/period-004-lfm3-1p7b-q8-humaneval-chat-thinking-20261117/manifest.json) · [採点集計](../../runs/period-004-lfm3-1p7b-q8-humaneval-plus-chat-thinking-20261117/summary.json)
