# Hermesとの接続・実動作の検証

このリポジトリは、モデル単体のHumanEval/BFCLだけでなく、Hermesがローカルモデルに接続して実際にツールを使えるかの検証も扱います。

| 場所 | 内容 |
| --- | --- |
| `integrations/hermes/scripts/` | 継続して使うHermes検証・照合コード。現在は保存済み証拠の検証器 |
| `integrations/hermes/fixtures/` | 個人情報を含まない共有テスト定義。実行ごとに新しいticketを使う |
| `configs/hermes/` | 公開できる接続条件・モデル・コンテキスト・バージョンの記録例 |
| `runs/<run-id>/` | 実験定義、実行時ソース、API応答、Hermesイベント、ツール結果、生成物、集計 |
| `artifacts/local-llm/hermes/` | 当時の接続設定スクリプト・起動補助・検証コード・ログ・結果の匿名化コピー |
| `artifacts/local-llm/workspace/hermes/` | 過去試験で使った合成入力と、実際に書かれた出力ファイル |
| `.local/hermes/` | 手元のインストール先など、公開しない個別PC情報 |

## 過去の記録

測定一覧 `../../index.html` に6件を登録しました。すべて過去の実行記録からのimportであり、新規推論ではありません。

- `20261028-hermes-native-smoke`: 4Bのread_file・terminal・write_file・再開・patch。最初のterminal拒否と、その後の成功を両方保存。
- `20261029-hermes-35b-tools`: 35Bの実ツール結果、終了コード、入力維持、独立計算と出力ファイルの一致。
- `20261029-hermes-tasks-140654` / `141429`: JSON・CSV・修正課題。初回とスキーマ修正後を別runにし、失敗も保持。
- `20261029-hermes-context64k`: 生APIの約64K入力試験と、**別途行った短いHermes会話**。Hermesの履歴を64Kまで埋めた試験ではありません。
- `20261029-hermes-mcp`: ローカルstdioのinitialize・tools/list・読み取り成功。アプリのtransportは当時 `tunnel_client_not_seen` で失敗した記録です。MCPブリッジ通信の成功をモデルによるツール実行の成功として扱いません。

各runの `manifest.json.evidence` からスクリプト・結果・入力・出力へ直接たどれます。SHA256を記録し、元の公開コピーの `publication/export-manifest.json` と追加分の `publication/hermes-export-manifest.json` を分けています。全体のHermes履歴データベース `state.db` は公開しません。対象試験の実ツール結果はreport/results JSONに含まれます。

当時のスクリプトは `artifacts/local-llm/hermes/{configure_local,launch,mcp_setup,test_large_model,verify_large_model}.py`、共同比較・容量試験は `artifacts/local-llm/hermes/benchmarks/` にあります。相対配置・元PCのインストールに依存する凍結資料です。`configure_local.py` や `mcp_setup.py` は実行すると設定を書き換えるコードなので、現行の照合処理はこれらを実行・importしません。新しい実行用に変更するときは `integrations/hermes/scripts/` に別のドライバーを作り、そのrunへソースを保存します。

## 今後の試験を作る

リポジトリのルートで実行します。

```powershell
python -B scripts/new_run.py --name "Hermes Qwen file tools" --benchmark hermes-file-roundtrip --type harness-integration --harness hermes --config configs/hermes/tool-roundtrip.example.json
```

MCP通信だけの試験は `--type transport-integration`、容量試験は `--type capacity` にします。保存先は分類にかかわらず `runs/<run-id>/` で、コードと結果を同じ階層へ混在させません。

1. `configs/` に実際に使ったHermes版・コミット、llama.cpp版、モデル/量子化/重みハッシュ、endpoint、context、思考ON/OFFと観測、起動引数を保存。
2. `workspace/` に新しいticket付き合成入力を用意し、期待値をモデルとは独立に計算。実際に書かれたファイルも保存。
3. `raw/` にHermes stdoutのイベントと対象セッションのツール呼び出し・実行結果を保存。`logs/` にstderr、時間、メモリ、承認で止まった記録を保存。
4. `source/` と `source-manifest.json` にその試験のソースを保存。共通処理 `snapshot_sources()` は `integrations/` も含めます。
5. `summary.json` に各チェックと `outcome`（passed / partial / failed）を保存。CLI終了コードやモデルの完了文だけで合格にしません。manifestのcompleteは収集の完了を表します。

秘密鍵・トークン・実ユーザーの全会話・config.yaml・Codex設定のバックアップ・モデル・Hermes本体は含めません。セッション識別子、実ツール結果、テスト用ファイルは対象実験分だけを保存します。

## モデルなしで照合

```powershell
python -B integrations/hermes/scripts/verify_saved_evidence.py
```

131追加ファイルのハッシュ、6つのrunと証拠への参照、4つの基本ファイル往復の生成物、実ツール結果、MCPの成功/失敗の記録を照合します。過去の採点を一律に成功へ書き換えたり、生成されたPythonを再実行したりはしません。全体の公開手順は [WORKFLOW.md](../../docs/WORKFLOW.md) を参照してください。
