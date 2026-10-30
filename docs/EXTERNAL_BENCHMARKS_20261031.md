# 外部のBFCL測定との比較（2026-10-31確認）

独立した利用者の測定と、量子化モデルの配布者による自己測定を調査した記録です。以下は外部の公表値で、このリポジトリで再実行した結果ではありません。同じモデル名・BFCLという名称だけでは問題・採点・思考設定の一致を保証できないため、外部の得点をローカルのマトリックスへ混在させません。

## 今回のローカル結果

出典は[最新の10構成比較](../reports/20261031-empero-qwen38-iq3m-64k/index.html)と[機械可読データ](../reports/20261031-empero-qwen38-iq3m-64k/matrix-data.json)です。

| モデル | 量子化 | BFCL 思考OFF | 思考ON |
| --- | --- | ---: | ---: |
| Qwen3.6-35B-A3B | UD-Q3_K_M | 72/80 (90.0%) | 72/80 (90.0%) |
| Qwen3.6-35B-A3B | IQ3_M | 74/80 (92.5%) | 72/80 (90.0%) |
| Empero Qwen3.8-35B-A3B-Distill | IQ3_M | 72/80 (90.0%) | 72/80 (90.0%) |

固定80問は `simple_python` / `multiple` / `parallel` / `irrelevance` 各20問、各条件1回答です。llama.cpp b11960、65,536コンテキスト、最大64,000出力トークン、temperature 0、固定版公式AST採点器を使用しています。外部関数は実行しません。複数ターン、Web検索、メモリ、live、parallel_multiple、Java/JavaScript等はこの80問には含まれません。

## 独立利用者の公表結果

| 測定者・出典 | モデル・形式 | 公表BFCL | 確認できた条件・限界 |
| --- | --- | ---: | --- |
| [Sam / Sams.Help](https://sams.help/local-ai-ledger/) | Empero Qwen3.8-35B-A3B-Distill、MLX 4bit表記 | 83.0% | 2026-10-07、DGX Spark、custom runtime、思考OFF。並列呼び出しの悪化を報告。BFCLの版・問題ID・件数・採点コードは当該記録から確認できず。 |
| [DanTup / spark-evals](https://github.com/DanTup/spark-evals) | Qwen3.6-35B-A3B FP8 | 78.0% | DGX Spark、Inspect AIによる旧測定表。公開手順は50件、7 epochs、median集計。こちらの80問・単回とは異なる。 |
| 同上 | Qwen3.6-35B-A3B NVFP4 | 80.0% | 同じ旧測定表。FP8より2ポイント高いが、これだけで低精度の優位性は判断できない。 |
| 同上 | Qwen3.6-35B-A3B FP8、FP8 KV cache | 76.0% | KV条件も異なる。FP8の別行と単純に量子化方式だけの比較にしない。 |
| [Reddit u/gvij](https://www.reddit.com/r/LocalLLaMA/comments/1sotj4n/qwen_36_35b_a3b_q4_k_m_quant_evaluation/) | Qwen3.6-35B-A3B Unsloth Q4_K_M | 46/100 (46.0%) | CPU、llama-cpp-python 0.3.20、独自統合ハーネス。BFCLの版・問題ID・思考設定・採点実装の詳細は未確認。参考値に留める。 |

Samの記録にある `n=100` は思考ONの時間比較の記述に付いています。**BFCL自体の問題数が100問と確認できたわけではありません。** 思考ONについては品質が同程度・タスク時間が約半分という定性的な記録で、数値のBFCL ONスコアは記載されていません。94.5→83という列も、元モデルの同条件を十分追跡できないため直接比較には使いません。

DanTupの[旧手順を固定したREADME](https://github.com/DanTup/spark-evals/blob/d616997698e796cc05be3c29ea1fb353bf854b85/README.md)には `inspect-ai==0.3.220` / `inspect-evals==0.11.0`、`--limit 1-50 --epochs 7 --epochs-reducer median`、カテゴリ指定 `exec_parallel_multiple` / `irrelevance`、1タスク1,800秒制限が掲載されています。指定カテゴリが各25問ずつ等とは読み取れません。現行READMEには旧表が残りますが、個別の旧runログ・思考設定を十分確認できていないため、「公開手順」と「各得点の実行条件が検証済み」を区別します。表の時間とトークン量は複数ベンチマーク全体の値なので、BFCLだけの所要時間として使いません。

Reddit投稿のHumanEvalは78/164でしたが、同じスレッドの別利用者はIQ4_XS・思考OFF・llama-server b8815で149/164と報告しています。測定条件と採点の確認なしに、低い得点をモデル固有の能力限界と判断できない例です。いずれも投稿者の自己申告で、こちらで再現検証していません。

## 量子化モデル配布者による補足測定

[EschaLabsのモデルカード](https://huggingface.co/EschaLabs/Qwen3.6-35B-A3B-Escha-W2/blob/main/README.md)では、同一ドライバーによるBFCL-ASTの1,000件・4つのnon-liveカテゴリの加重得点として、Qwen3.6-35B-A3B FP8が88.2%、独自2bit Escha-W2が88.9%です。思考OFF、BFCLの出力上限4,096、SGLangベースの同社ランタイムで測定したと説明しています。

これは第三者利用者による独立再現ではなく、圧縮モデル配布者の自己測定です。また、この得点はBFCL V4全体の総合スコアでも、irrelevanceを25%含むこちらの80問スコアでもありません。FP8でも100%ではなかったという同社試験内の事実は参考になりますが、0.7ポイント差を有意な改善とは判断しません。Escha-W2は今回のIQ3_Mとは異なる形式です。

## 比較から言えること

- 確認した外部公表値でもBFCLの失敗は残っています。今回の80問を満点にできない原因が、このPCの少ないVRAMやIQ3_Mだけにあるとは判断できません。
- 同じEmpero版で並列呼び出しの悪化が報告されている点は、こちらの思考ONのparallel 17/20という残存課題と方向が共通します。ただし問題IDも条件も違うため、同じ失敗原因と確認できたわけではありません。こちらのOFFはparallel 18/20、ONは17/20です。
- こちらの90–92.5%が外部の78–88.9%を上回るからといって、こちらの設定・量子化が優れているとは言えません。問題の難度・構成・採点・再試行集計が異なります。
- 高精度化や思考ONで全問正解になるという根拠は得られませんでした。量子化・ランタイム・思考の影響を切り分けるには、同じ問題ID、テンプレート、採点器、出力上限での再測定が必要です。

BFCL V4の[公式説明](https://gorilla.cs.berkeley.edu/blogs/15_bfcl_v4_web_search.html)では総合得点はAgentic 40%、Multi-Turn 30%、Live 10%、Non-Live 10%、Hallucination 10%です。固定80問の得点を、この総合得点や単一のnon-live得点に換算することはできません。

今回確認した範囲では、**同じIQ3_Mファイル・同じ固定80問・思考OFF/ONを揃えた独立測定**は見つかりませんでした。LFM3 Text/VLの同条件による独立BFCL測定も確認できませんでした。検索で見つかる開発元の公表値やその転載は、独立利用者の再測定と区別しています。

## 比較から除外した例

[sparkinferのquality README](https://github.com/gittensor-ai-lab/sparkinfer/blob/main/bench/quality/README.md)にはQwen3.6 UD-Q4_K_Mの「BFCL 74.67%」がありますが、同READMEのデータ説明では `NousResearch/hermes-function-calling-v1` を使い、独自のJSON関数名・引数一致で採点しています。公式BFCLデータとAST採点による値としては扱わず、比較表から除外しました。名称だけで同じ試験とみなさないための記録です。

検索で見つかったSyzygyResearchの2bit比較は、確認時に元モデルカードへHTTP 401でアクセスできませんでした。検索の抜粋だけでプロトコルを確定せず、主要な比較値には採用していません。

この調査では新しいモデル推論は実施していません。引用先の本文・画像・全データを転載せず、出典リンクと必要な数値・測定条件の要約を保存しています。
