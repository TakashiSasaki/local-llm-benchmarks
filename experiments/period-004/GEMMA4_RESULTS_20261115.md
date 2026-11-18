# TUFA15での Gemma 4 E4B 評価（2026年11月15日）

担当Codexスレッドの最終報告はMemory開始時点だった。実際には11月14日01:08 JSTに576件を保存し、所有サーバーが終了していた。第4期README・移行記録・安全性監査の「収集中」「未着手」は執筆時点の状態である。後続のBFCL本測定は f7cf735 固定で、初期検証の6ea5797とは異なる。第2期READMEのopen表記に対し、最新レジストリでは第2期は11月12日にclosed。第3期・第4期はopen。

作業開始時のCドライブ空きは44.24 GiB。ベンチマーク用Python・llamaプロセスおよび8089の待受を検出しなかった。存在したPythonはBlender MCPとHermes用。今回の新規推論、外部サービスへ評価データ送信、Web-search API利用、課金、生成コード実行、モデル取得は各0件。

## 測定条件と出典

- **モデル**はUnslothの Gemma 4 E4B IT、gemma-4-E4B-it-Q4_K_M.gguf、4,977,171,584 bytes、配布版 bfc15c382204943c3a8fff0c750b94ae2364d7a3。実測SHA-256は 85a896a047553e842f25297ee5b031d64ff30147d9c4af17b1e4b394cd1fab87。後発tokenizer修正前のGGUFで、変換元の厳密なリビジョンは未確認。[固定モデル記録](../period-003/models/gemma4-e4b-q4km.json)
- **実行環境**はllama.cpp b11960 CUDA 12.4、commit 8642541b255bfb5dc39cd351a178be09013a55d6。llama-server.exeの実測SHA-256は 81f65c6681d66099e5d48757aa2c050ba958dc43816e584f0bb4181eb7c910d8。65,536 context、F16 K/V、1 slot、28 GPU layers指定、CPU 8 threads、MTP OFF。[Memoryの起動引数](../../runs/period-004-bfcl-f7-gemma4-memory-v5-20261113/configs/server-command.json)
- **HumanEval**はOpenAI b9453e8f1865df0a0057a1383767caa400acfbcf。公式164問のgzip SHA-256は b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef。公式promptをraw /completionに渡し、各問1本、温度0.6、top_p .95、top_k 20、min_p 0、seed 42、出力上限16,384、API待機上限7,200秒。改行で始まるコードフェンス・if __name__・print(・class・def はローカルの生成時stop。chat用思考フラグの指定や、出力のコード抽出・import追加は行っていない。Windows採点は公式の prompt + completion + test + check を用い、POSIX SIGALRM・multiprocessingをWindows上の親watchdog 4秒とJobObject（256 MiB・1プロセス）に置き換え、Python 3.14.9・1 worker。公式CLI既定は3秒・4 workers。[Windows採点ポリシー](../../runs/period-004-gemma-humaneval-score-combined-20261112/configs/scoring-policy.json) · [固定版の実行コード](https://raw.githubusercontent.com/openai/human-eval/b9453e8f1865df0a0057a1383767caa400acfbcf/human_eval/execution.py)
- **BFCL V4**はBerkeley/Gorilla f7cf7359b7ac615a0b294831c5ba2bc95ee4a000、bfcl-eval 2025.12.17。Gemma 4の標準登録がないため、公式のツール説明・prompt処理にローカル登録とllama.cppのGGUF chat templateを組み合わせた。温度0.001、seed 42、生成上限4,096、思考OFF要求、API待機上限7,200秒、逐次、クライアント自動再試行0。公式AST／multi-turn／agentic判定に、ローカルの安全な式解釈・許可関数ガードを組み合わせた。multi-turnとMemoryの収集には模擬ツール実行を含む。GGUF・生成設定・ガード・実行環境・カテゴリのカバレッジが公式掲載条件との比較を制限する。単独runのoverall CSVは対象外カテゴリをゼロ扱いするため使用しない。[BFCL V4と固定版](https://gorilla.cs.berkeley.edu/leaderboard.html) · [ソースのインベントリ](configs/bfcl-f7cf735-source-inventory.json)

## 第2期・第3期およびHumanEval

- 第2期は選抜BFCL 80問・HumanEval 20問を使った32条件・1,600回答。完了検証器を再実行し、7,200秒コホート953件・14,400秒コホート647件、出力上限到達14件を確認。古い部分収集は履歴として保存されている。[第2期完了報告](../period-002/reports/completed.md)
- 第3期のGemma選抜比較はBFCL OFF 72/80、ON 75/80、HumanEval OFF 18/20、ON 19/20。生成速度中央値25.82 tokens/sは、短い入力・思考OFF・greedy・EOS無視で256 tokensを出した9回のプローブ（ウォームアップ除外）。第2期とは出力枠が異なる。[第3期のGemma集計](../../runs/period-003-gemma4-e4b-q4km-first-20261112/summary.json)
- 第4期HumanEvalは **132/164（80.49%）**、不合格32、除外0。初回chatの6件は形式検証。正式raw-prefixはGPU解放指示により89件で中断し、別runで75件を収集。集約した全164件で正規prompt、元応答、参照SHA、Windows採点の対応を再確認した。[HumanEval採点](../../runs/period-004-gemma-humaneval-score-combined-20261112/summary.json) · [今回の既存結果監査](../../runs/period-004-gemma4-saved-evidence-audit-r2-20261115/summary.json)

## BFCL single-turnと形式感度

全13カテゴリ3,641件。non-live **79.38%**、live **73.21%** は公式CSVのカテゴリ階層に基づく集約。件数で直接割るとそれぞれ1,130/1,390（81.29%）、1,615/2,251（71.75%）。全カテゴリで未採点0。[single-turn採点](../../runs/period-004-bfcl-f7-gemma4-single-turn-score-20261112/summary.json)

| カテゴリ | 正解/採点 | 不合格 |
| --- | ---: | ---: |
| simple_python | 360/400 | 40 |
| simple_java | 66/100 | 34 |
| simple_javascript | 39/50 | 11 |
| multiple | 183/200 | 17 |
| parallel | 178/200 | 22 |
| parallel_multiple | 118/200 | 82 |
| irrelevance | 186/240 | 54 |
| live_simple | 204/258 | 54 |
| live_multiple | 757/1,053 | 296 |
| live_parallel | 13/16 | 3 |
| live_parallel_multiple | 15/24 | 9 |
| live_irrelevance | 612/884 | 272 |
| live_relevance | 14/16 | 2 |

形式感度も200問×26形式の5,200件を保存・採点済み。3,469/5,200、形式別23.50〜81.00%、最大差57.5ポイント。BFCLの総合点集計からは除外される。[形式感度採点](../../runs/period-004-bfcl-f7-gemma4-format-sensitivity-score-20261113/summary.json)

## BFCL multi-turn

| カテゴリ | 正解/採点 | 不合格 | 除外 |
| --- | ---: | ---: | ---: |
| base | 50/194 | 144 | 6 |
| miss_func | 43/200 | 157 | 0 |
| miss_param | 36/200 | 164 | 0 |
| long_context | 45/200 | 155 | 0 |

全800問のうち787問は収集終了、7問は65,536 contextを超えたため失敗としてlong_contextの分母に含めた。該当ID末尾は120/121/124/132/134/135/148、拒否された入力は67,819〜84,121 tokens。120（70,411 tokens）は過去のサーバーログに基づく派生失敗記録で、失敗した要求・応答本文がない。他の6件はHTTP 400本文も保存済み。採点済みは一意な794件。[元の集計と根拠](../../runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v7-score-20261113/summaries/REPORT.md)

baseのガード中断6件はすべて最初のユーザーターン。元の問題、例外、保存HTTP本文29件とハッシュを突合した。後続ターンへの応答が存在しないため採点不能。旧分母を維持した。[問題ID・元run・応答への参照](../../runs/period-004-gemma4-saved-evidence-audit-r2-20261115/summaries/multi-turn-exclusions.json)

| base ID末尾 | 保存HTTP数 | 予定ターン | 当時の中断原因 |
| --- | ---: | ---: | --- |
| 0 | 6 | 4 | cdの位置引数 |
| 7 | 16 | 3 | echoの入れ子の呼び出し |
| 23 | 4 | 3 | no-call応答Noneを旧ガードが拒否 |
| 26 | 1 | 3 | ls(a=true)の裸の名前 |
| 55 | 1 | 5 | 未定義のget_ticket_login_status |
| 90 | 1 | 4 | 150/3.78541の算術式 |

再開する場合は、この6 IDを固定した新runで、元と同じ生成条件と事前検証済みv5ガードで各会話を先頭から一度だけ実行する。新旧をそれぞれ保存し、再度中断したら欠測扱い。完全収集時間は未実測。既存v7の479件全体の再実行は不要。context超過7件を拡張contextに移す場合は別条件。

## BFCL Memoryの保存回答採点

独立した採点runで、固定版の公式agentic採点関数とカテゴリ出力関数を、収集時のv5デコーダーガードと問題別allowlistで使用した。この公式採点関数は最後の非ツール呼び出し応答に正解情報が含まれるかを判定する。採点中の推論・外部通信経路は無効。既存の分離venvのPython 3.12.14を使用し、108のPythonファイルと71のデータファイルが固定チェックアウトと改行正規化後に一致した。前提会話の模擬ツールは再実行していない。収集時のベクトル用埋め込みはall-MiniLM-L6-v2、固定版1110a243fdf4706b3f48f1d95db1a4f5529b4d41、ローカルCPU。収集時の文脈・保存状態も得点に反映される。[採点run](../../runs/period-004-bfcl-f7-gemma4-memory-saved-score-r4-20261115/summary.json)

| 方式 | 正解/採点 | 正解率 | 不合格 | 欠測 |
| --- | ---: | ---: | ---: | ---: |
| KV | 11/155 | 7.10% | 144 | 0 |
| 再帰要約 | 68/155 | 43.87% | 87 | 0 |
| ベクトル | 15/155 | 9.68% | 140 | 0 |
| 計 | 94/465 | 20.22% | 371 | 0 |

2,845件の生HTTP応答とサーバーログの2,845リクエスト完了記録を確認。576件の保存レコードで回答本文・要求・推論ログ、manifest、ケース計画と公式ローダーのIDを照合し、重複・欠落・context超過0。前提会話は3方式×37件で、465問の依存会話が先に実行されたこと、111の個別チェックポイントと方式・シナリオごとの15の最終snapshotが対応することを確認した。[証拠と依存関係](../../runs/period-004-bfcl-f7-gemma4-memory-saved-score-r4-20261115/configs/evidence-verification.json)

| 前提会話 | 保存/予定 | 全ターン終了 | ステップ上限で途中終了 | 状態変化あり | ツールエラーを含む会話 |
| --- | ---: | ---: | ---: | ---: | ---: |
| KV | 37/37 | 32 | 5 | 32 | 22 |
| 再帰要約 | 37/37 | 21 | 16 | 25 | 17 |
| ベクトル | 37/37 | 25 | 12 | 34 | 16 |

状態変化は前のチェックポイントとの差で、正しい記憶内容の判定は含まない。ツールエラー数はログの明示的なerrorまたは実行例外に基づく。上限による途中終了も保存済みメモリを後続が利用したモデル挙動なので、前提会話の実行異常として後続得点からは除外しない。111件はいずれも採点の分母に含めない。起動時のラッパー不具合を修正した前3試行も別runとして保存し、成功runで公式形式の出力と全465件の個別判定を読み戻した。

## 残課題と判断

### Web-search（未実施200件）

固定版は100問をsnippet有／無に展開。検索はSerpAPIのDuckDuckGoエンジンをGoogleSearch経由で呼び、別ツールfetch_url_contentはURLとリダイレクト先へHTTPアクセスする。プロセス・ユーザー・マシン環境にSERPAPI_API_KEYは見当たらず、既存分離venvにserpapiモジュールもない。google-search-results 2.4.2はsdist配布。承認後はハッシュを照合した分離環境で依存をビルド・導入し、キーは実行プロセスのみに設定する。固定コードは例外・応答本文の429で無限再試行する。初回自動再試行0、単発タイムアウト、予算・毎時上限、リダイレクトを含む接続先制御をスタブで先に検証し、キーをログから除く。[固定Web実装](https://github.com/ShishirPatil/gorilla/blob/f7cf7359b7ac615a0b294831c5ba2bc95ee4a000/berkeley-function-call-leaderboard/bfcl_eval/eval_checker/multi_turn_eval/func_source_code/web_search.py) · [SerpApi検索仕様](https://serpapi.com/duckduckgo-search-api) · [依存パッケージ](https://pypi.org/project/google-search-results/2.4.2/)

初回は10問×2条件ほどで、検索の試行数、課金対象の非キャッシュ成功数、キャッシュ／失敗、URL取得を別々に測る。条件別の平均検索数×100を足して全体を概算。200問が平均1検索なら約200試行、平均2検索なら約400試行。公開料金ではFree月250検索・毎時50、Starter月1,000検索・毎時200・月25 USD。残枠は未確認。承認時にキー・送信先・試行数と費用の上限を決め、枠到達で停止する。代替は固定検索結果・ローカルページを使うツール経路の診断。ライブ検索のスコアには利用しない。[SerpApi公開料金](https://serpapi.com/pricing)

### 保存済みHumanEvalのLinux再採点

集約samples.jsonlは公式のtask_id/completion形式で、全164 ID、SHA-256 e1e40c5ed94bd0fe04957c4a57876a86a853eaa49645d2d53029947f40a431e6。未変更のLinux公式評価器にそのまま入力できる。固定ソースのexec行は有効で、READMEにはコメントアウトとの旧説明が残る。TUFA15でWSLディストリビューションと稼働中のDockerは検出されず、既設の隔離済みLinuxゲストは確認できなかった。Windowsでハイパーバイザーの稼働を観測したが、それだけではVMを準備できるとは限らない。[既存の提出用JSONL](../../runs/period-004-gemma-humaneval-aggregate-20261112/summaries/samples.jsonl) · [公式README](https://raw.githubusercontent.com/openai/human-eval/b9453e8f1865df0a0057a1383767caa400acfbcf/README.md)

第一候補はローカルの使い捨てLinux VM。2〜4 vCPU・RAM 4 GiB、ディスク目安8〜12 GiB、GPU不要。32 GiB空き確保とイメージ／一時領域も含めた容量を事前確認。ネットワーク、ホスト共有・クリップボード、資格情報の受け渡しを無効化し、読み取り専用媒体から固定コード・データ・回答を持ち込み、ゲスト内でSHAを照合。canonical、意図的誤答、無限ループを制御例にしてから、作業コピーに対して evaluate_functional_correctness samples.jsonl --k=1 --n_workers=4 --timeout=3.0 を実行する。持ち出す結果はJSONLとIDを検証しWindows結果と突合する。OS隔離を先に確認する必要がある。既存のWindows実行承認の範囲は当時のTUFA15評価であり、VM導入・実行や別サービスへの送信は今回の判断事項。

### 比較・実用測定の優先順位

| 優先 | 候補 | 既存測定との差と必要資源 |
| ---: | --- | --- |
| 1 | 既設の通常Qwen3.5-4Bとの同条件比較 | 第2・3期の選抜成績を参照し、第4期BFCLの一部100問を固定版・prompt方式・思考OFF・4,096出力で対照評価。Gemma側は同じ問題と有効設定の保存回答を再利用。新規GGUF 0、1モデルずつ。Gemma single-turnの実績では100問約3分相当。Qwenの実時間は短い予備実測で見積もる。 |
| 2 | 日本語指示追従・実ツール完遂 | 2モデル×日本語30問とローカルファイル／構造化出力／手順失敗からの回復10シナリオずつ。既存の模擬ツールや他モデルでのHermes基本smokeから進め、最終ファイル・権限境界・不要操作を検査。合成fixtureと人手確認を用意。 |
| 3 | 長文の品質・速度・RAM/VRAM | Gemmaで8K/32K/60K×検索・根拠統合を各5問程度。TTFT、prefill・decode、正答率、RAM/VRAMを同じ試行で計測。既存短文速度、他モデルの容量試験、BFCL long_contextの失敗数から得られない比較。60K時は実効入力＋4,096出力が65,536内か事前確認。開始時の既存基準は空きRAM 3 GiB以上、システムGPU使用7,676 MiB以下。 |
| 4 | 数学、過剰拒否、seed感度 | 第2期未測定計画の固定GSM8K候補100問で最終値を判定。XSTestは固定版safe250で過剰拒否と回答の適切さを確認し、日本語追加データは独立集計。価値の高い20〜50問を先に固定して3 seed。seed42を同条件で再利用できれば追加は1モデル40〜100回答。 |

44.24 GiBの空きから32 GiBを引いた作業余裕は約12.24 GiB。モデル追加とVM導入を同時に仮定せず、その時点の空きと一時領域で判断する。

## 監査範囲

HumanEval164件・Memory576件・multi-turn除外6件は元データと直接照合した。既存single-turn・形式感度は採点時の完全性検証記録を用い、現在のファイル集合と採点内訳を再照合した。後者2種の全応答SHAは今回再計算していない。過去のrun・原データ・採点は保持し、今回の監査とMemory採点は別runに保存した。公開資料の参照には検索／取得でクレジットを消費するFirecrawlの代わりに公開Web参照を使用した。
