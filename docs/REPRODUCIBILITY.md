# Reproducibility

## まず保存された結果を照合する

リポジトリ直下で `python -B tools/verify_publication.py` を実行します。外部サービスへの接続・モデル推論・生成コードの実行はありません。公開用ハッシュと固定版公式BFCL採点器を使い、1,280件のOFF/ON応答を再採点します。HumanEvalの320件は保存済み採点記録との整合性確認です。

この照合と、実際にモデルをロードして回答を再生成することは別です。`publication/validation.json` は前者の結果です。原測定時の検証記録も各runに保存しています。

## データと採点器

- HumanEval: `openai/human-eval`, revision `b9453e8f1865df0a0057a1383767caa400acfbcf`。`artifacts/local-llm/hermes/benchmarks/HumanEval.jsonl.gz` は元の圧縮データを保持。SHA256 `b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef`。
- 選択したHumanEval IDs: 6, 7, 8, 22, 23, 26, 28, 35, 55, 57, 59, 62, 70, 108, 129, 139, 143, 151, 154, 163。
- BFCL: `ShishirPatil/gorilla`, revision `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`。`artifacts/local-llm/hermes/benchmarks/bfcl/bfcl_eval/data/` に4カテゴリーと正解データを収録。使用した80問は各runの `selected-bfcl.json` にあります。
- 公式AST採点器と必要な依存ソースを同梱。ネイティブAPIのドット→アンダースコア変換に合わせ、原測定と同じ最小のローカルモデル登録を照合ツール内で行います。採点アルゴリズムの変更はありません。

## 原測定の環境

Windows 11 / Ryzen 9 7940HS / nominal 32 GiB RAM / RTX 4070 Laptop GPU 8 GiB。最終32条件は llama.cpp b11960 / commit `8642541b255bfb5dc39cd351a178be09013a55d6` / CUDA 12.4、1スロット、コンテキスト65,536、F16 KV、Flash Attention auto、`--fit off`、context shiftなし。以前のb11946測定は別runです。

モデル名・量子化・モデルファイルのSHA256・ダウンロード元リビジョンは `artifacts/local-llm/model-manifest.json` と `hermes/model-manifest.json`、起動コマンドは各runのprofile/state/propsにあります。Qwen 35Bは初期30層、LFM2.5は24層、GLMは35層のMoE expert weightsをCPUに置いた構成です。

HumanEvalの制限付きWindowsワーカーはPython **3.14.9** で実行しました。このワーカーはプロセス数・時間・メモリ等を制限しますが、汎用のOSサンドボックスではありません。原採点の再実行には原ワーカー・normalizer・Python版を揃えます。独立したBFCL照合はPython 3.12.14と3.14.9で確認しています。

## 凍結したスクリプトを再利用する

`artifacts/local-llm/scripts/`、`hermes/benchmarks/` とソースZIPには原測定のプログラムを収録しています。公開準備のために個人パス等を置換したコピーであり、モデルを含む実行環境を丸ごと複製したものではありません。

再測定には以下を揃えます。

1. Windows上の作業ディレクトリ、Python、NVIDIAドライバー。
2. manifestに記録したモデルとllama.cppを別途取得し、バイト数・SHA256を確認。
3. 凍結スクリプトの `ROOT`、profileのモデル／実行ファイルパス、Hermesのinstallation情報を自分の環境に合わせる。匿名化したユーザーパスは実在しません。
4. ループバックの8089番ポートを使い、モデルを1つずつロード。propsでモデル・build・1スロット当たり65,536 contextを確認。
5. 測定runごとに新しい出力ディレクトリを使う。過去の回答を上書きしない。

`benchmark_qwen_tool_thinking.py` はQwen 35B、`benchmark_model_tool_thinking.py` は指定した既存構成のBFCL ONを追加します。`run_tool_benchmark_matrix.py` は渡された完了済みQwen runと、既に監査済みのモデルrunを**再利用**します。日付入りの固定参照先があるため、再実験の前に必ず読んでください。過去の結果を再利用したのに「全件を新規生成した」と扱わないでください。

生成条件は保存されたrequest JSONが正本です。BFCLは温度0、top_p 1、top_k 0、min_p 0、repeat_penalty 1、seed 42、cache_prompt false、native tool_calls、parallel_tool_calls true。ON/OFFで変えるのはthinking設定で、LFM2.5だけはCLI budgetとルーティングaliasも異なります。出力予算は `min(64000, 65536 - rendered_input_tokens - 32)` です。

Qwen 35BのHTTP待ち時間は3,600秒、後続7構成は7,200秒にしています。これは低速モデルでも同じ64,000出力トークンまで到達できるようにする通信上限で、生成トークン予算を増やしたものではありません。

## 公開コピーのハッシュ

run内部の `original_hashes` 等は**匿名化前の原本**を指します。公開コピーのファイルにそのまま当てると一致しないものがあります。

- `publication/export-manifest.json`: 原本と公開コピーのSHA256、ZIP内ファイル、除外・置換内容。
- `SHA256SUMS`: READMEや照合ツールを含む公開パッケージ全体のSHA256。
- `tools/verify_publication.py`: 公開コピー用の照合。

モデル提供のチャットテンプレート本文は公開コピーから除外しました。そのSHA256は置換したフィールドまたは除外記録に残っています。同じGGUFを別途取得すれば元のテンプレートを確認できます。

## Hermesの接続・実ツール試験

`python -B integrations/hermes/scripts/verify_saved_evidence.py` で、追加分のハッシュと4件の基本ファイル往復、6実験への参照、保存されたMCP成功/失敗を照合できます。詳細は [Hermes検証](../integrations/hermes/README.md) を参照してください。過去のHermes試験はb11946等の当時の構成であり、b11960の全モデルの対応試験とは別です。近64Kの生API入力試験と、短いHermes会話も別々に記録しています。
