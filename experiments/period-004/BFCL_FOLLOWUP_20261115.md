# TUFA15の追加BFCL試験準備（2026年11月15日）

評価対象は既設のGemma 4 E4B IT Q4_K_M、llama.cpp b11960、BFCL V4 f7cf7359b7ac615a0b294831c5ba2bc95ee4a000。既存のraw、採点、GGUF、ランタイム、Python環境は保管し、追加分は新しいrun IDで扱う。[前回の集計](GEMMA4_RESULTS_20261115.md)

| 次の段階 | 範囲 | この時点の状態 |
| --- | --- | --- |
| SearXNG接続試験 | 公開のダミー検索 Python official documentation、各試験1回、Gemmaなし、ページ取得なし | 11月16日、duckduckgo webで3件取得 |
| Web-search予備試験 | 元データの0, 11, 22, 33, 44, 55, 66, 77, 88, 99を抜粋あり／なしで各1回、計20件 | 固定ID、公式loaderによる対の照合、疑似応答・採点の検証を実施 |
| multi-turn base補完 | 0, 7, 23, 26, 55, 90を最初のユーザーターンから各1回 | 元の29 HTTP応答、6 manifest、既存794件との非重複を照合 |

全200件のWeb-searchは、予備試験から検索・取得・失敗・経過時間を見積もった後に判断する。multi-turnのうち別に採点済みのcontext超過7件はこの計画に含めない。過去のbase 194件と新規6件の結果は別runに保存し、全6件が採点できた段階で合算の可否を確認する。過去の途中応答は証拠のみとして保存する。

## Web-searchの実行条件

- TUFA15のBFCLアダプターが既存SearXNGのStreamable HTTP MCPへ接続し、MCP 2025-11-25、JSON応答、searxng_searchのスキーマを検証する。エンジンはサーバーが案内する duckduckgo web に固定し、organic_only=true を明示する。既存のPython依存のみで使用できる。エンドポイントはプロセス環境変数 BFCL_SEARXNG_MCP_URL に設定し、必要なら BFCL_SEARXNG_MCP_BEARER から認証ヘッダーを組み立てる。トークン値はrunへ記録しない。11月16日の接続試験は認証ヘッダーなしで成功した。
- BFCLの既定 wt-wt は language=all として明示する。接続試験では search_info.language_applied=all を確認した。他のロケールの実効値はサーバー側の設定・仕様にも依存する。結果のうち duckduckgo web と明示された行をサーバーの返却順で渡し、構造化応答を研究用記録に保存する。no_snippetではモデルへの出力からbodyを省く。実行順は同じ設問の2条件を隣接させ、先に実行する条件を対ごとに交替する。
- ページ取得はTUFA15から公開HTTP(S)に直接アクセスする。元のツール名とraw／markdown／truncateを維持し、検証済み公開IPへ接続してTLSは元ホスト名で照合する。標準ポートのみ、リダイレクト先を再検証、各リダイレクトをHTTP GET上限に算入、応答上限2 MiB。これらの制限は固定版のページ取得に加えた差分。Crawl4AIは今回の実行経路に含めない。
- 検索用MCPツール呼出しとページHTTP GETを別カウンターで制限する。予備20件の開始上限の案はそれぞれ60回。呼出しを超えた場合やMCP側のHTTP 429などの障害では中断し、未完了分を採点しない。上限は承認済みの値を実行引数で指定する。この上限はMCPクライアントからの試行数であり、SearXNGサーバーの上流ネットワーク実装による内部呼出し数までは表さない。初回のクライアント再試行は0回。接続試験では固定の公開ダミー文字列1件を使用し、モデル・問題・回答データは送信しない。
- 予備試験ではGemmaが作った検索語を自前SearXNGへ送る。SearXNGから選択エンジンへの問い合わせが発生し得る。ページ取得ではGemmaが選んだ公開URLへ接続する。このため接続試験と20件の本試験はそれぞれ実行許可を明示して開始する。

## コマンド

リポジトリ直下で、既存の隔離BFCL Pythonを使用する。planは今回実行済み。probeとcollectは次の実行指示を受けた段階のコマンド。すべてのrun IDは未使用のものを指定する。

~~~powershell
$bfclExec = '.\.local\bfcl-f7-isolated-20261113\Scripts\python.exe'
& $bfclExec -B -I -X utf8 benchmarks/bfcl_f7_followup.py plan web-pilot --run-id period-004-bfcl-web-pilot-preflight-local
& $bfclExec -B -I -X utf8 benchmarks/bfcl_f7_followup.py plan multi-base-six --run-id period-004-bfcl-multi-base-six-preflight-local
& $bfclExec -B -I -X utf8 benchmarks/validate_bfcl_f7_searxng_mcp.py
~~~

エンドポイントと必要な認証を環境変数で設定してから、SearXNGの実検索1件を試す。新規推論は伴わない。

~~~powershell
& $bfclExec -B -I -X utf8 benchmarks/bfcl_f7_followup.py probe web-pilot --run-id period-004-bfcl-searxng-transport-probe
~~~

collect前に、既存の [llama-server起動引数](../../runs/period-004-bfcl-f7-gemma4-memory-v5-20261113/configs/server-command.json) と同じ条件で、専用のローカルサーバーを起動する。ドライバーはサーバーを起動・停止しない。起動前に8089が空いていることと、Cドライブ32 GiB・RAM 3 GiBの空き基準を確認する。ドライバーはモデルと実行ファイルのハッシュ、ポート8089のalias・モデルパス・実行build・context 65,536・slot数1とRAM/GPUを検証する。承認後は試験を1種類ずつ実行し、終了時に所有しているサーバーを停止する。

~~~powershell
& $bfclExec -B -I -X utf8 benchmarks/bfcl_f7_followup.py collect web-pilot --run-id period-004-bfcl-searxng-pilot --search-budget 60 --page-budget 60
& $bfclExec -B -I -X utf8 benchmarks/bfcl_f7_followup.py collect multi-base-six --run-id period-004-bfcl-base-six-followup
~~~

出力先はruns/<run-id>。configsで固定問題・原証拠・条件を、raw/httpとraw/casesで推論応答を、raw/backend-events.jsonlで検索・取得を記録する。中断時は問題別に保存済みデータを保管する。全予定件数が揃った場合にピン留め済み公式評価器と既存のガードでカテゴリ別採点し、raw/category-scoresとsummary.jsonへ保存する。検索方式が公式SerpAPI条件と異なるためSearXNG条件として報告する。

## オフラインでの検証

- [更新後のWeb-search計画と検証](../../runs/period-004-bfcl-web-pilot-preflight-r6-20261116/summary.json)
- [multi-turn計画と検証](../../runs/period-004-bfcl-multi-base-six-preflight-r5-20261115/summary.json)
- [MCPとページ取得の検証コード](../../benchmarks/validate_bfcl_f7_searxng_mcp.py)

実サービスとモデルサーバーを使わず、MCPの初期化とJSON応答、認証値のログ分離、呼出し上限、429後の単発停止、問題と抜粋設定の対応、公開IP固定、内部IPへのリダイレクト拒否、3種類のページ出力を疑似応答で確認した。初期の検証ではローカルホスト名参照の許可、地域コード、生成と採点ハンドラーの分離を修正した。既存HumanEvalコード由来の個人パスが途中runのソースコピーに含まれたため、その7 runはGit管理外の .local/bfcl-followup-preflight-attempts-20261115 に保管した。最終版のソースコピーは今回使うファイルに限定した。リポジトリ全体の公開候補検査には既存HumanEvalコードと過去runの個人パスが残る。このオフライン検証では実検索、ページ取得、モデル推論、ソフトウェア導入、外部公開は0件。

## SearXNG接続試験（17:35 JST）

2026-11-15 17:35 JSTに承認済みの公開語句を1回送信した。認証ヘッダーを付けずにMCP初期化とツール一覧取得に成功し、検索ツールの呼出しもHTTP 200のJSON-RPC resultまで到達した。引数は DuckDuckGo、language=all、最大3件、force_refresh=false。クライアントは mcp_search_tool_error で停止した。旧クライアントのログはツールが報告した isError と structuredContent 欠落を同じコードにまとめていたため、サーバー側の原因・実効ロケールは未確認。サーバー側ログとの照合時刻は17:35:24 JST。再検索、ページ取得、モデル推論は0件。[接続試験の記録](../../runs/period-004-bfcl-searxng-transport-probe-20261115/raw/backend-events.jsonl)

次回の接続試験用に、ツールエラーと構造化結果欠落を別コードに分け、エラー時のツール応答をGit管理外の .local/bfcl-probe-errors に保存するようにした。

## サーバー更新後の接続試験（21:53 JST）

2026-11-15 21:53 JST、同じ公開語句と検索引数で1回呼び出した。MCP初期化・ツール定義の取得に成功した。サーバービルドは 2026.10.30+ffa88e3ba.local.7c2c6c504e14 で、ツール定義に organic_only が追加されていた。前回との比較のため、今回は新しい引数を送っていない。検索は isError=true と UPSTREAM_CAPTCHA を返した。サーバーの診断では選択したDuckDuckGoで上流障害が発生した。リクエストIDは 7695bea11172472ba7a350fac7a44c51、照合時刻は21:53:21 JST（12:53:21 UTC）。成功結果と実効ロケールは未検証。自動再試行、ページ取得、モデル推論は0件。[更新後の接続試験ログ](../../runs/period-004-bfcl-searxng-transport-probe-r2-20261115/raw/backend-events.jsonl)

## 新しいDuckDuckGo Webエンジンでの接続試験（2026-11-16 11:32 JST）

新しいサーバービルド 2026.10.30+ffa88e3ba.local.f8cf8f52d7b5 のツール定義では、旧duckduckgoエンジンが対象外になり、duckduckgo web が案内された。アダプターのエンジン名と結果検証をそろえ、organic_only=true を明示した。公開語句・最大3件・language=all・force_refresh=false の条件で検索1回。構造化結果3件はいずれも duckduckgo web のPython公式サイトで、各行に抜粋があった。search_info は明示エンジン選択、language_applied=all、cache_status=MISS、unresponsive_enginesなしを報告した。予備20件のオフライン検証とアダプターのユニットテスト8件は成功。接続試験ではページ取得・モデル推論は0件。旧試験との変更点はエンジン名とorganic_onlyの指定。予備20件の実運用は未実施。[成功run](../../runs/period-004-bfcl-searxng-transport-probe-r3-20261116/summary.json) · [ツール定義と応答ログ](../../runs/period-004-bfcl-searxng-transport-probe-r3-20261116/raw/backend-events.jsonl)

## Web-searchの実測再開（2026-11-16）

Gemma 4 E4B Q4_K_Mを、llama.cpp b11960-8642541b2、単一スロット65,536トークン、thinking OFF、temperature 0.001、seed 42、最大出力4,096で実行した。BFCL V4の固定コミット `f7cf7359b7ac615a0b294831c5ba2bc95ee4a000` の2カテゴリを使用した。公式実装はSerpAPIのDuckDuckGo検索を使い、この測定はSearXNG MCP `duckduckgo web`、`organic_only=true` と公開IPを検証したページ直接取得を使う。この測定では初回の検索・取得失敗を自動再試行しない。カテゴリ採点には固定版の評価器と既存のローカル実行ガードを使う。

予備20件の採点結果は、抜粋あり1/10、抜粋なし1/10。モデル応答は58件、検索は33回、ページHTTP GETは6回（200が5回、403が1回）。抜粋なし `web_search_no_snippet_0` ではローカルの入力が229,310トークンに達してコンテキスト制限で終了し、評価器が `agentic:inference_error` として分母に含めた。[予備20件の採点](../../runs/period-004-bfcl-searxng-pilot-20261116/summary.json) · [予備20件の検索・取得記録](../../runs/period-004-bfcl-searxng-pilot-20261116/raw/backend-events.jsonl)

残り180件の最初の開始時に、MCPビルドが `2026.10.30+ffa88e3ba.local.f8cf8f52d7b5` から `2026.10.30+ffa88e3ba.local.df444bc07294` に変わったため、モデル推論・検索の前に停止した。公表ツール定義の差分は応答への任意の `search_info.request_id` の追加だった。予備20件は保存時のファイルをハッシュ付きで参照し、新しいビルドを明示して残り180件を別runで開始した。ビルドの混在を記録し、ツール定義の照合は任意の `request_id` を除いた定義全体を比較する。定義の照合で確認できるのは検索・応答のインターフェースまで。[最初の開始記録](../../runs/period-004-bfcl-searxng-full-20261116/summary.json) · [180件の実行計画](../../runs/period-004-bfcl-searxng-full-r2-20261116/configs/case-plan.json)

新ビルドで28件を収集した後、`web_search_base_16` の2回目の検索が `UPSTREAM_ENGINE_FAILURE` になった。MCPの構造化診断では `duckduckgo web` の `parsing error`。照合時刻は11:50:27 JST（02:50:27 UTC）、リクエストIDは `3687384dfb6d427a964f80c33e6421f8`。この問題は欠測のまま残し、保存済み48件を流用して未着手の151件に進んだ。続行runはこの構造化診断に一致したときに問題単位で欠測とし、次の未着手の問題へ進む。HTTPの429や他のMCPエラーは従来どおり停止する。[中断run](../../runs/period-004-bfcl-searxng-full-r2-20261116/raw/backend-events.jsonl) · [続行の対象と除外](../../runs/period-004-bfcl-searxng-full-r3-20261116/configs/case-plan.json)

### 採点結果

| カテゴリ | 予定 | 採点 | 正解 | 正答率 | コンテキスト超過（採点内） | 欠測 |
|---|---:|---:|---:|---:|---:|---:|
| `web_search_base`（抜粋あり） | 100 | 99 | 7 | 7.07% | 0 | 1 |
| `web_search_no_snippet`（抜粋なし） | 100 | 100 | 3 | 3.00% | 4 | 0 |

全200件に着手し、予備20件と中断runの28件を再利用して合計199件を採点した。採点ファイルの行、回答、再利用元のハッシュ、欠測IDの重複・欠落を照合した。旧MCPビルドは抜粋あり1/10、抜粋なし1/10。新ビルドは抜粋あり6/89、抜粋なし2/90。この内訳は実施順による問題の違いを含む。公式のエージェント型採点器は最終応答から正解文字列を照合する。採点対象で検索を呼んだのは抜粋あり46件、抜粋なし47件。抜粋なしの実測コンテキスト超過4件を除いた不正解は、抜粋あり92件、抜粋なし93件でいずれも `agentic:answer_not_found`。この結果はSearXNG構成でのWeb-searchカテゴリ別実測値。[集計](../../runs/period-004-bfcl-searxng-full-r3-20261116/summary.json) · [抜粋ありの採点](../../runs/period-004-bfcl-searxng-full-r3-20261116/raw/category-scores/local-gemma4-f7-prompt/agentic/BFCL_v4_web_search_base_score.json) · [抜粋なしの採点](../../runs/period-004-bfcl-searxng-full-r3-20261116/raw/category-scores/local-gemma4-f7-prompt/agentic/BFCL_v4_web_search_no_snippet_score.json)

検索は193回（キャッシュMISS 141、HIT 51、上流エラー1）。成功時の実効言語は `all` 188、`en-US` 3、`fr-FR` 1。ページHTTP GETはリダイレクトを含め56回（200が49回、301が1回、401が1回、403が5回）。保存したモデル応答は443件で、コンテキスト制限による拒否は別途記録した。試験用サーバーの停止と8089の待受解消を確認した。Cドライブの終了時空きは91.1 GiB。[続行runの検索・取得記録](../../runs/period-004-bfcl-searxng-full-r3-20261116/raw/backend-events.jsonl)

アダプターのユニットテストは8件成功。リポジトリ全体のユニットテストでは91件中2件がHumanEval採点・再評価で失敗した。公開候補のリポジトリ検査は既存のHumanEval関連ファイルにあるローカルのユーザーパスを検出した。

### 低スコアの内訳

保存済みの採点結果とMCP検索ログを問題IDで照合した。採点199件のうち検索が実行された93件は9件正解（抜粋あり7/46、抜粋なし2/47）。検索が実行されなかった106件は1件正解（抜粋あり0/53、抜粋なし1/53）。両条件で検索が実行されず不正解だった元問題は50問。

検索が実行されなかった不正解105件のうち、70件の最終応答に `I cannot answer this question` があった。別に、抜粋あり12件・抜粋なし11件の最終応答には `<|tool_call>call:` が残っており、23件すべての元推論ログに構文エラーがあった。例えば `web_search_base_14` は検索関数名とクエリを生成したが、MCPへの検索送信に至らなかった。アダプターがその形式を処理できるよう修正した場合の最終正答数は未測定。検索が実行されても84件が不正解で、検索後に情報をつなげられなかった応答や、ページHTTP 403で止まった応答もあった。[形式不一致の例](../../runs/period-004-bfcl-searxng-full-r2-20261116/raw/cases/web_search_base_14.json)

## Gemma固有の呼び出し形式を修正して再計測（2026-11-17）

Web-search用のアダプターに、先頭が `<|tool_call>call:` の応答の処理を追加した。観測された末尾タグや呼び出し全体を囲む二重引用符を取り除き、許可済みのWeb検索・ページ取得の呼び出しを既存の検査と実行経路へ渡す。関数名が省略されたJSON応答1件は、登録された2つの関数のうち `keywords` 引数で識別できる検索を使う。タグのない既存の応答も従来どおり処理する。固定版BFCLの採点器と既存ガードを使い、Web-searchのこの構成は `--gemma-web-native-calls` として記録する。[アダプター](../../benchmarks/bfcl_f7_gemma4_web_calls.py)

前回の元HTTP応答から抽出した23件をローカルで再検証し、旧版で23件の構文エラー、新版で23件の検索呼び出し解釈を確認した。通常形式とタグ付きページ取得の2件、拒否すべき7件も検証した。オフライン計画では同じ200件を選択し、疑似検索で通常形式とタグ付き形式の両方が検索実行・抜粋制御・最終採点まで通った。[オフライン計画](../../runs/period-004-bfcl-gemma-web-calls-plan-r2-20261117/summary.json)

新規runで前回と同じ200件の収集を開始した。モデル、量子化、モデルとランタイムのハッシュ、生成設定、問題・採点版、SearXNGのエンジン、ページ取得条件を維持した。MCPは前回の後半179採点件と同じビルド `2026.10.30+ffa88e3ba.local.df444bc07294` に固定した。前回の予備20件には別ビルドが含まれ、検索・ページの実レスポンスは取得時点に依存する。[再計測の設定](../../runs/period-004-bfcl-searxng-gemma-web-calls-20261117/configs/case-plan.json)

以後、Web-searchの通常実行ではタグ付き応答の処理を有効にする。前回のローカルアダプター条件を再現する場合は `--no-gemma-web-native-calls` を指定する。両方のモードで200件の選択とオフライン実行・採点を確認した。[通常の計画](../../runs/period-004-bfcl-gemma-web-calls-default-plan-20261117/summary.json) · [前回条件の計画](../../runs/period-004-bfcl-gemma-web-calls-legacy-plan-20261117/summary.json)

### 全200件の再計測結果

| カテゴリ | 前回 | 修正後 | 両回採点した同一IDで前回→修正後 |
|---|---:|---:|---:|
| 抜粋あり | 7/99（7.07%） | 11/100（11.00%） | 7/99 → 11/99 |
| 抜粋なし | 3/100（3.00%） | 5/100（5.00%） | 3/100 → 5/100 |

再計測は欠測0件で、前回欠測だった `web_search_base_16` も採点した。同一IDでは7件が不正解から正解へ、1件が正解から不正解へ変わった。前回も同じMCPビルドだった問題に限ると、抜粋あり6/89→9/89、抜粋なし2/90→3/90。前回に構文エラーで検索できなかった23件は、今回は20件で検索に成功し、4件が正解した。前回と同じ最初の応答が得られたのは、両回採点できた199件中114件。検索応答や生成結果にも変動がある。[200件の採点・分母](../../runs/period-004-bfcl-searxng-gemma-web-calls-20261117/summary.json) · [実行時のアダプター](../../runs/period-004-bfcl-searxng-gemma-web-calls-20261117/source/benchmarks/bfcl_f7_gemma4_web_calls.py)

検索に成功したケースは前回93件から今回116件に増加した。今回は検索242回（HIT 185、MISS 57）、ページGET 64回、モデルの完了応答500件を記録。コンテキスト上限超過は抜粋あり1件、抜粋なし4件で、いずれも実測の推論失敗として採点分母に含めた。再計測のHTTP・ケース・採点ファイルを問題IDで照合し、試験用サーバーの終了を確認した。[再計測の検索・取得記録](../../runs/period-004-bfcl-searxng-gemma-web-calls-20261117/raw/backend-events.jsonl)

全件再計測中に現れた、JSON文字列で囲まれた呼び出し（抜粋なし48）と `tool_name`・`params` のJSON形式（抜粋なし66）にも対応した。再計測時のタグ付き応答を再検証した結果、追加の2応答を解釈でき、前の版が受理した43応答は同じ呼び出しとして解釈した。問題46の両条件は外側の引用符と括弧・波括弧が不整合だったため、構文エラーとして扱った。最新のアダプターで抜粋なし48・66を別runで再計測すると、両方で検索が実行され（1回と5回）、正解は0/2だった。2件とも初回応答は全件runで見つけた形式と異なるタグ付き形式を生成した。追加2形式の解釈は保存応答を使ったオフライン検証で確認した。[追加のオフライン計画](../../runs/period-004-bfcl-gemma-web-calls-extra-plan-20261117/summary.json) · [追加2件の採点](../../runs/period-004-bfcl-searxng-gemma-web-calls-extra-20261117/summary.json)

今回の変更に関するオフライン検証とSearXNGアダプターの8件は成功した。リポジトリ全体のテストは前回と同じHumanEval関連2件で失敗し、公開候補の検査は過去のHumanEval関連ファイル中のローカルユーザーパスを検出した。

## Thinking ONとOFFの比較（2026-11-17）

OFFの全200件runを比較元とし、同じ問題と実行順、GGUF・llama.cpp、BFCL固定版、ローカルの呼び出しガード、SearXNGのMCPビルドとエンジン、ページ取得条件、seed、temperature、コンテキスト上限65,536、各応答の出力上限4,096でThinking ONを開始した。Web-searchパーサーはOFFの全件runに保存した版をハッシュ照合して使う。別runで行った2ケースの追加対応はこの比較のパーサーに含めていない。`enable_thinking=true` をモデルへの各リクエストに設定し、最初の2応答で別欄の `reasoning_content` が返ることを確認した。ライブ検索結果とページ本文は各測定時点に依存する。[OFFの結果](../../runs/period-004-bfcl-searxng-gemma-web-calls-20261117/summary.json) · [ONの計画検証](../../runs/period-004-bfcl-gemma-thinking-on-plan-20261117/summary.json) · [ONの実行計画](../../runs/period-004-bfcl-searxng-gemma-thinking-on-20261117/configs/case-plan.json)

10件収集後の `web_search_no_snippet_5` でDuckDuckGo上流が `UPSTREAM_TIMEOUT` を返した。照合時刻は12:20:59 JST（03:20:59 UTC）、リクエストIDは `bb67600b9aef449c9bb35c5e8374433f`。このケースは再試行せず欠測とし、保存済み10件を参照して未着手の189件を別runで開始した。アダプターが確認できる上流の解析エラーとタイムアウトは問題単位の欠測とする。HTTP 429、認証やその他のサービス障害は停止する。[中断時のMCPログ](../../runs/period-004-bfcl-searxng-gemma-thinking-on-20261117/raw/backend-events.jsonl) · [再開計画](../../runs/period-004-bfcl-gemma-thinking-on-resume-plan-20261117/summary.json)

次のrunでは21件収集後、`web_search_base_16` で上流応答に `results` 欄がないことを示す `MISSING_RESULTS` が返った。照合時刻は12:54:54 JST（03:54:54 UTC）、リクエストIDは `4c530a3083ca483ab1e7fe275bd758c4`。これも欠測とし、以後は同じ構造化診断を問題単位で扱う。次回の開始前にMCPビルドが `2026.10.30+ffa88e3ba.local.ef80ea4aa094` に変わったため、推論・検索前に一度停止した。新旧の検索ツール定義を照合し、同じ定義とエンジン指定であることを確認したうえで、新ビルドを記録して167件を再開した。全件の比較にはビルド変更が含まれる。OFFと同じビルドで両回採点した最初の31件では、抜粋あり1/16→9/16、抜粋なし0/15→1/15だった。[結果欄の欠落ログ](../../runs/period-004-bfcl-searxng-gemma-thinking-on-r2-20261117/raw/backend-events.jsonl) · [続行計画](../../runs/period-004-bfcl-searxng-gemma-thinking-on-r4-20261117/configs/case-plan.json)

最初に採点できた抜粋なし9件では、9件が検索し、7件が再検索し、7件がページ取得を実行した。4件は取得後の入力が65,536トークンを超えた。別の `web_search_no_snippet_11` は入力65,459と生成77でちょうど65,536に達し、生成が途中で終わって採点も不正解だった。254応答時点で生成トークン数の中央値は249、2,048超は0件。46件時点では、いずれかの入力が3万トークンを超えた12件のうち2件が正解した（`web_search_base_5` は最大56,993、`web_search_no_snippet_23` は最大31,877）。これらは途中時点の観測。[問題11のケースログ](../../runs/period-004-bfcl-searxng-gemma-thinking-on-r2-20261117/raw/cases/web_search_no_snippet_11.json)

### 28層GPUのThinking比較結果

| 条件 | 抜粋あり | 抜粋なし | 採点合計 | 検索に成功した採点ケース |
|---|---:|---:|---:|---:|
| Thinking OFF | 11/100（11.00%） | 5/100（5.00%） | 16/200 | 116 |
| Thinking ON | 43/98（43.88%） | 17/99（17.17%） | 60/197 | 197 |

両回採点した同一197件でOFFは16件、ONは60件正解。50件が正解に変わり、6件が不正解に変わった。欠測3件は `web_search_no_snippet_5`、`web_search_base_16`、`web_search_base_82`。最後の1件は新ビルドでの上流タイムアウトで、16:17:39 JST（07:17:39 UTC）に記録した。これらを再試行せず、他の197件を固定版の評価器で採点した。検索・ページ内容は取得時点に依存し、ON途中にMCPビルドも変わった。[Thinking ON集計](../../runs/period-004-bfcl-searxng-gemma-thinking-on-r4-20261117/summary.json) · [最後の欠測ログ](../../runs/period-004-bfcl-searxng-gemma-thinking-on-r4-20261117/summaries/unscored-cases.json)

ONの完了HTTP応答973回中787回に `reasoning_content` があり、全197件の採点ケースで一度以上観測した。OFFは500応答で0回。ONは入力上限で28件を拒否し、別の1件では生成中にコンテキスト上限へ到達した。出力上限4,096に達して本文が空になったのは13件で、すべて抜粋なし。OFFでは入力拒否5件、出力上限0件。1ケースあたりの生成トークン中央値はOFFの119.5からONの1,027、完了したモデルHTTP呼び出しの計測時間の合計は約26.8分から約290.1分に変わった。ONの検索試行650回、ページGET 161回。外部ツール待ち時間はモデルHTTPの合計に含まない。

### 全層GPUでの追加測定の準備

ユーザーの指示に従い、28層GPUのThinking ON比較を完了してから全層GPUを別runで実行する。GGUFには42ブロックがあり、llama.cppのオフロード表示は出力層を含め43層。今回のビルドでは通常の全層オフロードでも入力層をCPUに配置する実装なので、全モデルテンソルのCUDA0指定を最初に試す。起動ログで43/43層とモデル・KVバッファの配置を照合し、実際のVRAM使用量を確認する。コンテキスト65,536、K/V f16、バッチ等は前回条件に合わせる。[全GPUのオフライン計画](../../runs/period-004-bfcl-gemma-thinking-on-all-gpu-plan-20261117/summary.json) · [固定版llama.cppの入力層配置](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/src/llama-model.cpp#L1699-L1701)

全GPU版はコンテキスト65,536、1スロットでロード成功。起動ログで43/43層、CUDA0のモデルバッファ5,091.51 MiB、KVバッファ1,024 MiBと40 MiBを確認した。起動後のNVIDIAの専用VRAM使用量は6,487/8,188 MiB。Windowsのプロセス別表示にはホスト共有メモリも約154 MiBあった。全モデル・KVバッファをCUDA0に確保できたことを起動ログで確認して、全200件の比較へ進む。

全GPUの検証開始時にMCPのビルドが `2026.10.30+ffa88e3ba.local.4244dcfa4e4b` に変わった。旧ビルド指定のままでは推論・検索前に停止した。差分はツールの説明文への上流エラー時の案内の追記で、入力・出力スキーマは同じだった。`duckduckgo web` を明示する従来の条件で、新ビルドを記録し直して全GPU runを開始した。両配置の正答率比較には検索時点とMCP更新の影響も含まれる。[起動時の配置検証](../../runs/period-004-bfcl-searxng-gemma-thinking-on-all-gpu-20261117/configs/live-server.json) · [全GPUの実行計画](../../runs/period-004-bfcl-searxng-gemma-thinking-on-all-gpu-r2-20261117/configs/case-plan.json)

### 全GPUの追加測定結果

| Thinking ONの配置 | 抜粋あり | 抜粋なし | 採点合計 | 欠測 |
|---|---:|---:|---:|---:|
| GPUに28層 | 43/98（43.88%） | 17/99（17.17%） | 60/197 | 3 |
| 全モデル・KVをCUDA0 | 48/100（48.00%） | 21/100（21.00%） | 69/200 | 0 |

同じ197件にそろえると60/197→67/197（抜粋あり43/98→46/98、抜粋なし17/99→21/99）。16件が正解に変わり、9件が不正解に変わった。全GPUでは検索665回、ページGET 164回、完了したモデルHTTP応答995回を記録した。全200件で検索に成功し、801応答に推論欄があった。入力上限拒否は23件、別の1件は生成中にコンテキスト上限へ到達し、11件は出力上限4,096で本文が空になった。入力拒否23件と出力上限11件はすべて抜粋なしだった。正答率と失敗件数はライブ検索の取得時点とMCPビルドの違いも含む。[全GPUの集計](../../runs/period-004-bfcl-searxng-gemma-thinking-on-all-gpu-r2-20261117/summary.json) · [検索・取得記録](../../runs/period-004-bfcl-searxng-gemma-thinking-on-all-gpu-r2-20261117/raw/backend-events.jsonl)

両配置の最初のモデル入力が一致した197件について、llama.cppのデコード速度中央値は25.36→62.65 tokens/s（2.47倍）。全完了応答での中央値は24.81→61.72 tokens/s。完了HTTP応答の計測時間合計は17406.69秒（約4時間50分）から5565.83秒（約1時間33分）に減少した。外部ツール待ちはこの時間に含まない。全GPUの収集開始から採点完了までは17:22:17〜19:01:48 JST（約1時間40分）。全GPU runで43/43層とCUDA0のモデル・KVバッファを再確認し、試験用サーバーの終了、8089の待受解消、Cドライブ空き90.27 GiBを確認した。[全GPU実行時の配置・ハッシュ](../../runs/period-004-bfcl-searxng-gemma-thinking-on-all-gpu-r2-20261117/configs/live-server.json)

配置用の起動引数とログ検証はオフラインの正例・負例でも確認した。リポジトリ全体のユニットテストは従来と同じHumanEval関連2件が失敗し、公開候補検査は既存のHumanEval関連のローカルユーザーパスを検出した。
