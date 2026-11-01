# 第1期 — WindowsローカルLLM比較、2026-11-01終了

[固定比較ページ](report.html) · [Markdown比較表](comparison.md) · [条件CSV](conditions.csv) · [全run索引](runs.json) · [期のmanifest](manifest.json)

Gitタグ **`period-001-2026-11-01`** が、この期の最終コード・入力・条件・結果を含むコミットを指します。対象のベース結果はコミット`b1e5eeaf3c0cab1c064fa73445eac320ab3f5086`までの記録です。終結用コミット自身のhashをファイル内へ自己参照させず、タグをGitで解決します。

```powershell
git clone https://github.com/TakashiSasaki/local-llm-benchmarks.git
cd local-llm-benchmarks
git checkout --detach period-001-2026-11-01
git rev-parse 'period-001-2026-11-01^{commit}'
```

## 範囲と配置

| 内容 | 固定場所 |
| --- | --- |
| 終了時のOS・CPU・GPU・RAM・ドライバー・Python・電源設定 | [environment.json](environment.json) |
| モデル19件（実体確認17件、未取得候補2件）・runtime2版の取得元とhash | [assets.json](assets.json)、[モデル表](MODELS.md)、[models/](models/) |
| 30測定行の起動プロファイル・sampler・配置 | [profiles.json](profiles.json)、[比較JSON](comparison.json)内の条件別samplers |
| 当時のソース・設定・補助手順 | [recipe/](recipe/)（ルートと同じ構成の固定コピー） |
| 原応答・条件・ログ・runごとのソース | [runs.json](runs.json)から元の`../../runs/<run-id>/`を参照 |
| 過去の原測定とHermes・画像smoke等 | 元の`../../artifacts/local-llm/`。凍結済み証拠を保持 |
| 入力問題・正解・公式採点器の固定コピー | `../../datasets/`、`../../data/`、`../../vendor/bfcl/`、ライセンスは各ディレクトリ |
| 全ファイルの整合性 | [inventory.json](inventory.json)とGitタグ、リポジトリ全体の`SHA256SUMS` |

結果の相対参照を保つため、既存runは移動・改名していません。閉鎖したrun IDの集合とhashで第1期を固定し、次の期とはディレクトリ、run IDのprefix、manifestの`period`、カタログ表示で区別します。旧runのmanifest自体も変更していません。

能力比較は8モデル名・16モデル/量子化ペア・MTPを含む21組み合わせです。配置や再測定を区別した30行（能力27・速度のみ3）、94/108能力条件完了、主比較の保存応答4,776件。独立した全173登録runには、親集計・子条件・取得失敗・容量・接続・replayも含みます。173回の能力測定ではありません。

## 実行環境

終了時に実機から採取した情報はWindows 11 Home 26H2、**10.0.26300.9818**、ASUS TUF Gaming A15 FA507XI、Ryzen 9 7940HS（8 core / 16 thread）、DDR5-5600 16 GiB×2、RTX 4070 Laptop（観測総量8,188 MiB）、NVIDIAドライバー**555.97**です。OS認識の利用可能物理RAMは装着32 GiBより少なくなります。ページファイルは自動管理。電源プランのGUIDだけでなく各設定値もenvironmentに保存しました。

主比較のllama.cppは **b11960 / v0.8.0 / `8642541b255bfb5dc39cd351a178be09013a55d6`**、Windows x64 / CUDA12.4配布です。古い比較・一部Hermesは **b11946 / `8ca4060b7e30e76baaa5670ee1ec1b760b7f8552`**。新版で旧版を置き換えた扱いにはしません。終了時にそれぞれ56ファイル、計112ファイルのSHA-256を配布時manifestと再照合しました。

能力測定・Windows HumanEval採点には**CPython 3.14.9**（2026-10-21ビルド、MSC v.1944 x64）を使用した記録があり、終了時にも同じ版を確認しました。集計・保守時のこのセッションはCPython **3.12.14**です。両方の実行バイナリ/DLLのhashと現在のパッケージ一覧をenvironmentに分けて保存しています。直接BFCL/HumanEvalの維持管理ドライバーは標準ライブラリと同梱の固定採点器を使います。

Python 3.14.9の配布アーカイブの元URLとアーカイブhashは当初保存されていません。実行バイナリhash・完全な版情報・保存済みソース・canonical controlsまでは固定できますが、同じ版名の別ビルドがバイト同一とは主張しません。将来の再測定では選んだPython配布物のURL/hashも新期に記録してください。OS更新、当時の常駐負荷・温度・実クロック・AC状態は全リクエストで保存していないため、終了時情報から過去の速度を完全に再現できるとは限りません。

Hermesは**v0.22.5 / `bf0203a794a07aac3ff764972ab9087baa4e4f4e`**。[当時の導入記録](../../artifacts/local-llm/hermes/installation.json)と[接続設定・fixture](recipe/integrations/hermes/README.md)を参照します。終了時ソースのcommit、依存定義`pyproject.toml`と`uv.lock`のhashも保存しました。再入手は`https://github.com/NousResearch/hermes-agent`の固定commitを使い、同commitの導入手順・lockに従います。個人の設定、認証情報、state.db全体は含めません。実際の試験用tool結果と生成物は保存済みrunに含まれます。全モデルのHermes適合を試したわけではありません。

## 同じ重み・runtimeを入手する

モデルは全て`repo`、40桁の固定`revision`、`filename`、`bytes`、全ファイルSHA-256、revision入りダウンロードURLを保存しています。プロジェクターも別ファイルです。終了時に存在した17 GGUF全てをストリーム読み出しで再ハッシュし、一致しました。Qwen Q4_K_S/Lは未取得の候補として残し、モデル成功件数に含めません。

例としてQwen3.6 IQ3_Mを、リポジトリ外のモデル専用ディレクトリへ取得します。ほかのモデルも`models/`内のmanifestを選ぶだけで同じ手順を使えます。既存ファイルもサイズとSHA-256を照合し、異なる重みを黙って使いません。

```powershell
$BenchPython = 'D:\Tools\Python314\python.exe' # 用意した3.14.9の実体。上記のビルド差の注意を確認
$ModelDir = 'D:\LocalLLM\models'
& $BenchPython -B scripts/download_pinned_model.py --manifest experiments/period-001/models/Qwen_Qwen3.6-35B-A3B-IQ3_M.gguf.json --model-dir $ModelDir --connections 1
```

ランタイムは`assets.json`の各runtimeにある**2つのzip**（CUDA依存とllamaバイナリ）を両方使います。`b11960`と`b11946`は別フォルダーへ展開してください。`latest`は使いません。

```powershell
$Asset = Get-Content experiments/period-001/assets.json -Raw | ConvertFrom-Json
$Runtime = $Asset.runtimes | Where-Object build -eq 'b11960'
$RuntimeDir = 'D:\LocalLLM\bin\b11960-cuda12.4'
$DownloadDir = 'D:\LocalLLM\downloads\period-001'
New-Item -ItemType Directory -Force $RuntimeDir,$DownloadDir | Out-Null
foreach ($Zip in $Runtime.assets) {
    $File = Join-Path $DownloadDir ([Uri]$Zip.url).Segments[-1]
    curl.exe --fail --location --output $File $Zip.url
    if ($LASTEXITCODE) { throw 'Download failed' }
    if ((Get-Item -LiteralPath $File).Length -ne $Zip.bytes -or (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Zip.sha256) { throw 'Runtime archive mismatch' }
    Expand-Archive -LiteralPath $File -DestinationPath $RuntimeDir -Force
}
& (Join-Path $RuntimeDir 'llama-server.exe') --version
```

展開したファイルの個別hashも`installed_files_verified`にあります。CUDA12.4はこのバイナリの依存版であり、NVIDIAドライバーが表示するCUDA対応上限とは別です。モデル・runtimeの実体や約20 GBの取得途中rangeファイルはGitへ含めません。

## 測定条件を再構成する

各30行の`profile.server_args`を[profiles.json](profiles.json)にまとめています。`configs/server-command.json`があるrunは実際の起動コマンドも参照してください。自分の外部モデル/runtimeパスと新しいalias/ポートへ置換し、元ファイルを書き換えず新期のconfigを作ります。単一の共通コマンドへ丸めると配置・load-mode・reasoning budgetの差が失われます。

- 主比較はcontext **65,536 / 1 slot / F16 K,V**、最大出力**64,000**、短い固定問題。上限は入力長によって`min(64000,65536-rendered_input-32)`。64K近くの入力を埋めた性能試験とは別です。
- BFCLは固定**80問**（simple_python / multiple / parallel / irrelevance各20）、revision **`6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`**、固定AST checker / converter。temperature0、top_p1、top_k0、min_p0、repeat_penalty1、seed42、tool_choice auto、parallel_tool_calls true。関数の実行はしません。
- HumanEvalは固定**20問**、revision **`b9453e8f1865df0a0057a1383767caa400acfbcf`**、元データhash **`b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef`**。選択IDは保存済みraw/datasetに固定。temperature0.6、top_p0.95、top_k20、min_p0、presence_penalty0、repeat_penalty1、seed42。
- HumanEval主採点はWindows Job Objectの単一プロセス・256 MiB上限と6秒待機、制限されたbuiltins、固定コード抽出・grader。`type()`を追加する補助ポリシーの結果は別replayです。Pythonを変える際にも主採点を黙って変更しません。
- 思考OFF/ONは要求とreasoning欄の観測を別に保存。LFM2.5 OFFはCLI budget0強制。MTPも別軸です。b11960の`/props`の既定`speculative.types=none`だけからMTP ONを否定せず、実際のdraft tokensと起動CLIで確認します。
- 速度は思考OFF、固定256出力×3プロンプト×3回、greedy、ignore_eos、cache_prompt falseのdecode中央値。128トークン×3の起動プローブ、回答中の平均decode、API壁時計は別です。
- CPU MoEはexpert配置の層数であり、decoder全体のCPU配置ではありません。Qwen/Emperoは30/34/35等の差を保ちます。Mageの`-ngl20`はCPU17 decoder・GPU19 decoder＋出力、`-ngl23`速度補足はCPU14/GPU22＋出力です。
- 初期64KドライバーのAPI待機3,600秒と後続の7,200秒、RAM guard、GPU容量探索の7,676 MiB閾値、sampled memoryの観測区間は元run/ソースを優先します。profile内の通常対話limitsは能力試験のAPI timeoutと同じではありません。

失敗も再現対象に含めます。Mage Q4はAPIタイムアウトで8件保存（7正解＋形式エラー1）、Mage Q3はBFCL19/80・21/80だけ完了、HE未完了。Q3 MTPはMTP重み不足、Q4 MTPは起動未実施。Q4 S/Lは取得失敗・本測定なし。[Mage総評](../../docs/MAGE_VL_COWORK.md)、[全比較の注意](../../docs/COMPREHENSIVE_COMPARISON.md)を参照してください。未完了を全問の0点や完了した正答率にしません。

## 保存済み結果だけを検証する

以下の`verify_*`はモデルを起動せず、生成コードも再実行しません。`unittest`には保存済みHumanEvalコードをWindowsの制限付きworkerで再採点するテストも含まれますが、新しいモデル推論ではありません。新しい推論は別期でのみ行います。

```powershell
& $BenchPython -B tools/verify_period.py --period period-001
& $BenchPython -B tools/verify_comprehensive.py
& $BenchPython -B tools/verify_mage_study.py
& $BenchPython -B tools/verify_mtp_study.py --prefix 20261031-q5-k-m-mtp-64k
& $BenchPython -B tools/verify_publication.py
& $BenchPython -B integrations/hermes/scripts/verify_saved_evidence.py
& $BenchPython -B -m unittest discover -s tests -v
& $BenchPython -B tools/make_checksums.py --check
```

期のinventoryは入力・証拠・当期レポートとrecipeを保護します。ルートの維持管理コードとカタログは次期に更新可能です。同じコードを取り出すには必ずタグをcheckoutしてください。第1期の比較集計はrun索引とrecipe内モデル定義に限定され、次期のrunを自動で足しません。

新規の再測定は[次期の開始手順](../README.md)で新期を開き、`period-002-...`等の新しいIDを使います。たとえば同じMTPセルを再現するときは`run_mtp_study.py`へ固定model manifest、新期へコピーしてパス等を調整したprofile、元の`--mtp`/`--cpu-moe`/`--load-mode`、明示した`--benchmark-python`を渡します。既存IDへの上書きや、取得失敗したキューの自動再開はしません。
