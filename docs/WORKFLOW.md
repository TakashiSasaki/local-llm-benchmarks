# 追加実験からコミット・プッシュまで

ローカルGitルートは `C:\LocalLLM\local-llm-benchmarks` です。以下のコマンドはこのフォルダーで実行します。

## ディレクトリの使い分け

| 場所 | 用途 |
| --- | --- |
| `benchmarks/` | モデル単体の測定スクリプト。最初の対応例は `bfcl.py` |
| `integrations/<harness>/scripts/` | Hermes等の接続・実ツール動作の検証コード |
| `integrations/<harness>/fixtures/` | 各エージェントの共有テスト定義・期待値 |
| `configs/hermes/` | 公開できる接続条件・Hermes版・モデルとランタイムの識別 |
| `src/local_llm_benchmarks/` | 実行管理・採点などの共通処理 |
| `scripts/` | runの作成、一覧ページ生成、公開前チェック、Git操作 |
| `tools/` | 過去の公開データ照合、チェックサム、任意のブラウザーQA |
| `datasets/<benchmark>/<revision>/` | 共有するテスト入力・正解データ・出典・ハッシュ |
| `configs/` | 公開できる実験条件の定義 |
| `runs/<run-id>/` | 新しい測定ごとの条件・生データ・集計・ソース記録 |
| `reports/` | 測定一覧と、各実験の表示用ページ |
| `artifacts/local-llm/` | 過去の原測定スクリプトと結果の匿名化済みスナップショット。今後の編集先ではありません |
| `.local/`, `.cache/` | 公開しない個別PC設定や作業用ファイル。Git管理外 |

モデルとランタイムはGitルートの外です。元PCではモデルが `C:\LocalLLM\models`、llama.cppが `C:\LocalLLM\bin\b11960-cuda12.4`、Hermes接続補助が `C:\LocalLLM\hermes` にあります。Hermes本体はCodexアプリ用のLocalCache内です。GitHubへは、それらの識別子・リビジョン・ハッシュ・起動条件を記録します。

## 新しいrunを作る

```powershell
python -B scripts/new_run.py --name "Qwen BFCL thinking on" --benchmark bfcl --config configs/bfcl-64k.example.json
```

作成された `runs/<run-id>` のIDを後続コマンドに渡します。別の実験は新しいIDにします。共通入力は `datasets/` に置き、試験のために新しく作った入力や補助データはそのrun内へ保存します。

```text
runs/<run-id>/
  manifest.json           タイトル・試験名・状態・条件・時刻
  configs/                実際のサーバー情報・モード確認
  raw/                    各問題のrequest / response / 時間
  logs/                   stderr・メモリ・承認等の補助ログ
  workspace/              合成入力・生成物（公開前に内容を確認）
  summaries/              問題別の採点
  summary.json            実験全体の集計
  source/                 実行時コードのスナップショット
  source-manifest.json    ソースのハッシュ、Gitコミットとdirty状態
```

## Hermesの接続・実ツール動作を検証する

```powershell
python -B scripts/new_run.py --name "Hermes tool roundtrip" --benchmark hermes-file-roundtrip --type harness-integration --harness hermes --config configs/hermes/tool-roundtrip.example.json
```

`--type` は `benchmark`（既定）、`harness-integration`、`transport-integration`、`capacity` です。`--harness hermes` で使用エージェントを記録します。過去の6件は共通の `runs/` へ登録し、凍結した証拠を `manifest.json.evidence` からハッシュ付きで参照しています。コード・fixture・記録項目の詳しい説明は [Hermes検証](../integrations/hermes/README.md) にあります。

モデルがツール呼び出しを出力しただけのBFCL採点、Hermesがツールを実行した結果、MCP通信の結果は別の試験です。収集の `status: complete` と試験結果の `outcome: passed/partial/failed` も区別します。失敗した結果を残し、新しい試験は別runで実行します。

## BFCLを測る

先に別途llama.cppを対象モデル・コンテキスト・CPU/GPU配置で起動します。ドライバーは既存サーバーを交換・停止しません。実際にserveしているaliasを指定します。

```powershell
python -B benchmarks/bfcl.py --run <run-id> --model "served-model-alias" --thinking on
```

デフォルトは `http://127.0.0.1:8089`、コンテキスト65,536、最大出力64,000です。必要なら `--endpoint`、`--context`、`--max-output` を明示します。モデル名・量子化・ファイルハッシュ・使用ランタイム・ハードウェア等は公開configにも記録してください。aliasだけではモデル重みの同一性は保証できません。

原測定と同じ固定80問・公式AST採点器・greedy条件を使い、思考の観測確認をしてから収録します。外部ツールの関数は実行しません。LFM2.5はテンプレートがスイッチを無視するため、OFFでは外部サーバーのCLI budget 0、ONでは-1を用意し、必要に応じ `--mode-control runtime-forced` と明記します。

通信途中で失敗しても、保存済みの応答を消しません。同じコマンドを同じrunに再実行すると、条件とソースが一致する場合だけ未保存の問題を続行します。完了runは再生成できません。コードやモデル／ランタイムを変える場合は、新しいrunを作ります。

その他のベンチマークも同じrun構造を使えます。測定コードを `benchmarks/` に追加し、最後に `summary.json` と `manifest.json` の状態を保存すると一覧に載せられます。HumanEval等の過去の実行方式は、凍結した原スクリプトを資料として参照してください。

## 集計・チェック

```powershell
python -B scripts/refresh_reports.py
python -B scripts/check_repository.py
python -B tools/verify_publication.py
python -B integrations/hermes/scripts/verify_saved_evidence.py
python -B -m unittest discover -s tests -v
```

`index.html` と `reports/index.html` は測定の一覧です。2026-10-30の32条件の比較ページは `reports/2026-10-30-matrix/index.html` に固定して残します。将来の結果で過去の比較ページを上書きしません。

テストは保存済み応答のreplayと一時ディレクトリを使います。モデル推論は行わず、replayを新しい測定結果としてカタログに載せません。

## コミット・プッシュ

IQ3_Mの追加測定では `scripts/download_pinned_model.py` で固定リビジョンのモデルをリポジトリ外へ取得し、`scripts/run_quantization_study.py` で4条件とHermesの別runを保存しました。`benchmarks/humaneval.py` と `integrations/hermes/scripts/tool_roundtrip.py` が追加されています。保存済み結果の照合は `python -B tools/verify_quantization_study.py --study 20261030-qwen36-iq3m-64k`、追加比較ページの再生成は `scripts/report_quantization_study.py --study 20261030-qwen36-iq3m-64k` です。[具体的な条件](IQ3_M.md)も参照してください。新しく実測する場合は新しいrun IDを使います。採点器の補助ポリシーは `kind: replay` の別runに保存し、生成済みの主結果を書き換えません。

差分を確認した後、次のコマンドで照合・テスト・レポート更新・チェックサム更新をしてコミットできます。

```powershell
git diff --stat
powershell -File scripts/publish.ps1 -Message "Add benchmark results for ..."
```

GitHubへ送るときは `-Push` を付けます。通常の `git add` / `git commit` / `git push` を使うこともできます。タイマーで勝手にプッシュする設定は入れていません。

```powershell
powershell -File scripts/publish.ps1 -Message "Add benchmark results for ..." -Push
```

モデルやランタイムは追加せず、ソース・入力データ・条件・結果・必要なログをコミットします。秘密情報や個人パスのチェックはパターン検査なので、公開する差分自体も確認してください。

## 別のモデルを追加する例

Empero Qwen3.8 Distillの記録は [EMPERO_QWEN38.md](EMPERO_QWEN38.md) にあります。`run_quantization_study.py` は `--model-manifest`、`--profile`、`--reference` でモデル・実行条件・比較元を指定し、実際のOFF/ONモード確認をしてから測定します。新しい実測は必ず新しい `--id` を使います。追加比較ページは `report_model_study.py --study <run-id>` で作り、以前の比較ページを残します。
