# 第4期 公式評価の移行記録

2026-11-12 JST。period-003は開いたまま維持し、この調査・新規runはperiod-004に分離。旧結果との数値互換性は生成・採点条件を確認するまで主張しません。

## HumanEval

OpenAI HumanEval b9453e8f1865df0a0057a1383767caa400acfbcf、公式HumanEval.jsonl.gz SHA256 b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef、全164問。公式入力はtask_id/completionのJSONL、公式実行コードはprompt + completion + test + checkを結合して実行、公式既定timeout 3秒・workers 4。生成関数は公式READMEに具体的な実装がなく、ここではllama.cppの/completionに公式promptそのものを与えます。

公式READMEは非保守・サンドボックスを推奨し実行行がコメントアウトと記載していますが、固定revisionのGit実ファイルはexec行が有効です。記述と実コードを区別して保存しました。

初回chat出力は関数全体・コードフェンスを含み、公式prefixとの連結に不適合。6件の原回答をperiod-004-gemma-humaneval-20261112にadapter-validationとして保存し、適合しない収集を中断しました。生prefixの停止文字列なし検証は5件中0件が連結後に構文成立。停止文字列を生成時に指定した別検証は5件中5件が構文成立しました。これは形式確認であり、正答率の証明ではありません。

本収集runはperiod-004-gemma-humaneval-prefix-20261112。量子化Q4_K_M、b11960、ctx65536、F16 KV、MTP off、ngl28、n_predict16384、温度0.6/top_p0.95/top_k20/min_p0/seed42、各問1サンプル、API timeout7200秒、自動再試行なし。生成時stopは改行後のコードフェンス、if __name__、print(、class、def。返答に抽出やimport追加は行いません。Raw prefixではchat-templateの思考ON/OFFを指定しないため両モード比較の測定ではありません。テスト・canonical solutionをモデルに送信しません。

本人は安全性の説明後、隔離が未確認のtufa15上でGemma生成コードを実行することを明示承認。非管理者で、隔離機能としてではなく資源制限としてJobObject 256 MiB・1プロセスと親watchdogを適用。固定upstream unsafe_executeと結合順は維持し、WindowsでPOSIX SIGALRMとmultiprocessingを置き換え、上限4秒のwall timeout、1 workerに変更。したがって公式Linux実行と厳密同一ではありません。生成完了後period-004-gemma-humaneval-score-20261112で採点。スコアは採点完了まで未確定です。

## BFCL V4

Gorilla 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8。固定checkoutとソース・データのSHAはconfigs/official-source-inventory.json、入力ごとのSHAはconfigs/official-sources.jsonに記録。全scoringカテゴリは下記の5,106ケース。memory書込み前提は各backend 37件、計111件を別途実行。format_sensitivityは非採点で200問題×26形式=5,200件。

| category | scoring cases |
| --- | ---: |
| simple_python | 400 |
| simple_java | 100 |
| simple_javascript | 50 |
| multiple | 200 |
| parallel | 200 |
| parallel_multiple | 200 |
| irrelevance | 240 |
| live_simple | 258 |
| live_multiple | 1053 |
| live_parallel | 16 |
| live_parallel_multiple | 24 |
| live_irrelevance | 884 |
| live_relevance | 16 |
| multi_turn_base | 200 |
| multi_turn_miss_func | 200 |
| multi_turn_miss_param | 200 |
| multi_turn_long_context | 200 |
| memory_kv | 155 |
| memory_vector | 155 |
| memory_rec_sum | 155 |
| web_search_base | 100 |
| web_search_no_snippet | 100 |

公式BFCLは多ターン・memoryでツールbackend実行、web_searchでSerpAPI keyと外部接続が必要。公式Gemma handlerはGemma3等の登録で、対象Gemma4はモデルregistry未登録。現行環境にはofficial bfcl_evalと複数必須依存が未導入。公式handlerは外部tokenizer設定、SDKの再試行設定、llama.cppと生成形式の一致を確認する必要があり、BFCL本測定・公式全体スコアはまだありません。

公式AST checker等の固定ソースと既存vendorコピーは改行正規化後に一致。登録shimと既存80 fixturesによる正負コントロールが通過しました。これは公式BFCL全体のGemmaスコアではありません。
.local/period004-bfcl-controls.jsonにコントロール証拠を保存。

公式出典: https://github.com/openai/human-eval/tree/b9453e8f1865df0a0057a1383767caa400acfbcf ・ https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard
