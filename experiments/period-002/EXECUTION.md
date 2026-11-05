# 第2期の実行開始記録 — 2026-11-02

## 2026-11-06 引き継ぎ監査（測定停止を維持）

以下の11月2日の「生成中」「待機中」は当時の記録です。HumanEval/35は保存・採点済み。新規能力回答は588件、通常9B HE ONは8問中7問正解で残り12問未実施、全体未収集1,012件です。[比較ページ](reports/index.html)と[監査記録](AUDIT.md)を参照してください。現在の測定writer・llama-server・古いshutdown監視・関連Windows予約・8089待受は監査時に存在しません。旧監視設定はenabled=trueの履歴として保持し、起動していません。shutdown_requestedは電源断時刻の証明ではありません。停止フラグ・過去期限はそのまま、新しい取得/推論/shutdown予約は行っていません。

## 最新の停止指示 — 2026-11-02 16:56 JST

停電開始が早まるとの追加指示により、**現在生成中の1問を保存・採点したら、次の問題・条件・モデル・取得を開始せず停止**します。旧04:00までの実行枠より、この即時保留が優先します。対象は通常Qwen3.5-9B Q4_K_M、64K/F16、MTP OFF、`-ngl24`のHumanEval思考ON、8問目`HumanEval/35`です。7問の保存済み応答を確認しています。

`execution-window.json`の`stop_after_current_task`を有効化し、既にロード済みの旧admissionコードにも効くよう、`finish_by`を保留指示時点（16:58:11 JST）に設定しました。旧04:00目標は`finish_by_before_hold`として保持します。これにより現在のHTTP応答を強制停止せず、保存・採点後の次の開始境界で保留になります。途中条件はモデルの0点や完了とせず、部分結果と停止理由を維持します。別モデルの新規起動や未実施条件の再試行・自動再開は行いません。

同時点で約37,853 tokensを生成済み、直近約8.3 tok/sでした。生成が出力上限まで続く場合の目安は17:50〜18:10 JSTで、途中で回答が終了すれば前倒しになります。2時間のAPI待機上限に達した場合も再試行せず、保存済み7問とサーバーログ等を残して終了します。この予想は条件20問全部の完了時刻ではなく、現在の1問と後処理の終了目安です。

シャットダウン予約の変更確認への回答を受け、**現在の1問と後処理が終了したらPCをシャットダウン**する設定に変更しました。11月3日06:00のWindows予約は解除・不存在を照合済みです。`scripts/shutdown_after_request.py`が当該条件/モデル/親runの終端、保存応答と採点または記録済み失敗、所有サーバーのcleanup、元の4プロセスの終了を待ちます。PID再利用を誤認しないよう起動時刻を照合して元のプロセスhandleを保持し、記録が揃う前にはシャットダウンしません。現在のリクエストや測定プロセスを強制終了しません。待機状態の照合記録は非公開`.local/validation/shutdown-after-request-20261102-state.json`、設定は同ディレクトリの`shutdown-after-request-20261102.json`です。

## 停電前の実行制限（追加指示）

2026-11-03のお昼に停電予定のため、**2026-11-03 04:00 JSTを完了目標**とします。新規タスクは保守的な所要時間と30分の保存余裕を足してもこの時刻に収まる場合だけ開始します。日付・時差込みの[実行窓設定](configs/execution-window.json)を第2期だけに適用し、後の実験期に恒久的な04:00制限を持ち込みません。

追加指示により、Windowsタスクスケジューラに一回限りの`Codex-PlannedShutdown-20261103-0600-JST`を登録し、次回実行が**2026-11-03 06:00 JST**であることを照合しました。現在ユーザーのInteractive/Limitedタスクで、ロック状態では実行できますがログイン状態を維持する必要があります。`shutdown.exe /s /t 0`（planned reason、強制アプリ終了なし）、WakeToRun有効、バッテリーでも実行、時刻を逃した後の遅延実行は無効です。実機の登録照合記録は非公開`.local/validation/shutdown-20261103-0600.json`に保存しています。06:00予約が04:00の測定完了目標を延長することはありません。

モデル200回答の新規cellは初期見積もり4時間、各条件/新規問題は既存API待機上限も考慮して2時間を確保する設定です。したがって新規モデルは原則23:30 JSTまで、新規問題は原則01:30 JSTまでが開始可能な境界になります。これは成功・終了を保証する値ではなく、安全側の開始判定です。所要不明は保留し、推論の出力上限・sampler・採点条件は変えません。期限保留時は保存済み部分結果と`execution_window_deferred`を残し、モデル不良や完了0点として扱いません。

設定追加時点で稼働中だったのは、すでに起動済みの段階A・最後のHumanEval思考ONです。このプロセスを再起動・途中停止して設定を注入せず、13:59:53 JSTに400回答の完了を確認しました。取得・preflight・model runnerと各新規問題の開始判定に制限を組み込みました。新しい段階の実装や手動起動でもこの設定を先に確認します。

14:06 JSTに後続`period-002-core-followup-20261102`を起動しました。段階Aの8条件400原応答・集計・source hashと採点器の固定SHA/Python一致を照合してから、承認済みのB（9B×4）→C（35B×2）を順次進めます。新規は1,200回答で、Aの400件を新規推論として数え直しません。取得は1接続・32GiBディスク予約・全SHA検証です。各cohort内で共通の安全な配置をpreflightし、MTP OFF/64K/F16とsampler/採点は維持します。9BはGPU全層から候補32/31/30/28/24、35BはCPU MoE34〜40の順で試した候補内の共通配置を選び、明示的CUDA割当失敗またはGPU予約超過以外の不明な失敗を単なる容量不足として再試行しません。期限で保留された時点で自動終了し、停電後の無断再開はしません。

```powershell
& $MaintenancePython -B -X utf8 scripts/run_period2_remaining.py --id period-002-NEW-followup --stage-a period-002-stage-a-comparison-20261102 --validation period-002-he-policy-validation-20261102 --benchmark-python $BenchmarkPython
```

段階Aから開始します。本測定の予定は通常Qwen3.5-4BとWangzhang/Abliterix配布物のQ4_K_M対で、BFCL80問とHumanEval20問、各思考OFF/ON、8条件400回答です。9B/35B、追加セット、Hermes、MTP ONはまだ開始していません。

## 原記録と順序

| run | 役割 |
| --- | --- |
| `period-002-he-policy-validation-20261102` | 実際のbenchmark Pythonで主採点器を検証。164/164 canonical、type/operator正解・誤答・timeout control成功。新規モデル推論0件 |
| `period-002-stage-a-preparation-20261102` | 最初の取得試行。転送切替時の重複を止めたfailed記録 |
| `period-002-stage-a-preparation-20261102-r2` | 再開した途中ファイルのサイズ/SHA不整合でfailed。モデル起動・採点未実施 |
| `period-002-stage-a-preparation-20261102-r3` | 排他ロック導入後の新規取得と、2モデルの64K/speed/tool/mode preflight |
| `period-002-stage-a-comparison-20261102` | r3の全ゲート成功を待つ400回答の本測定。失敗ゲートやAPI timeoutの際は原回答を残して停止 |

各runは`runs/`直下にあります。表は役割と開始時点の記録であり、実行中の件数・成否は`manifest.json`、`logs/progress.jsonl`、子runの`summary.json`を参照します。smokeの8例や短文速度3本をBFCL80/HumanEval20の完了数に含めません。

通常版ファイル`Qwen3.5-4B.Q4_K_M.gguf`の2,708,804,800 bytes/SHA照合は成功済み。Abliterixも同じ固定revision・期待SHAで取得し直し、2,707,514,688 bytes/SHA照合に成功しました。不整合だった2,876,065,088-byte途中ファイルはrepo外に`.part.invalid-sha-20261102-r2`として保持し、削除・採点には使いません。両方の候補manifestは`models/`に固定しています。各取得プロセスと段階A準備/本測定に排他ロックを追加しました。

12:16 JSTに両配布物のpreflightが完了し、12:16:59 JSTに本測定の通常版cellを起動しました。両方とも64K/F16・GPU全層配置でロード、思考OFF/ONとツール出力を確認できています。preflightのシステム全GPUピークは各4,971 MiB、最小空きRAMは通常版21,378,215,936 bytes/Abliterix21,193,494,528 bytes、RAM guardなし、所有サーバー停止済みです。短文128-token×3本の中央値は通常版72.849/Abliterix72.896 tok/sでした。これは起動時の速度probeであり、最終能力や長文速度の結果とは扱いません。本測定では別の256-token×3 prompts×3回を保存します。

ローカルGGUFの[ヘッダー照合](research/stage-a-local-header-audit-20261102.json)では、両方ともqwen35・32 decoder層・native context262,144、chat templateのSHAは同一でした。一方、内部tensor精度は一致していません。通常版はF32×177/Q4_K×216/Q6_K×33、AbliterixはF32×177/Q4_K×203/Q5_K×24/Q6_K×22です。したがって同じQ4_K_M名でも、能力差を拒否方向の除去だけの効果とは解釈せず、配布物同士の比較として扱います。

## 採点・条件

主採点は`humaneval-b9453e8-windows-full-module-v1`。元と同じ20問、同じ抽出器とrequest samplerを使い、[固定した公式test実行コード](../../vendor/humaneval/b9453e8/README.md)へ完全なPython moduleを渡します。POSIX signal/multiprocessingをWindows JobObjectと親の6秒watchdog（256 MiB、1 process）に置き換えた標準testのWindows適応です。EvalPlusや公式Linuxと完全同一の環境とは呼びません。第1期の制限付き採点は同じ保存コードの`legacy_replay`に別記し、主点数を上書きしません。validation runに実Python版・worker/adapter/vendorのSHAと164件の原判定があります。本測定開始時に一致を再照合します。

最初の容量候補は65,536 context、F16 K/V、1 slot、GPU全層、8 threads、load-mode none、MTP OFF。物理空きRAM3 GiB、システム全GPU使用7,676 MiB以下をゲートにします。両モデルが成立しなければ本測定を開始せず、別配置の試行には別runを使います。mainの出力上限64,000 tokens、API待機7,200秒、入力長から32 tokensを予約する規則を維持します。

準備はmaintenance Python、主能力推論/採点はplanning environmentに記録したbenchmark Python 3.14.9を使います。実際のserver command、served props、モデルSHA、ソースsnapshot、メモリ標本、所有サーバー停止記録は各runに保存します。第1期のfrozenデータと報告は変更しません。

## 実行コマンド

`$MaintenancePython`と`$BenchmarkPython`はrepo外の既存interpreterを明示します。以下は新規IDでの再現手順であり、すでに起動済みのrunを重複起動する手順ではありません。

```powershell
& $BenchmarkPython -B -X utf8 scripts/validate_humaneval_standard.py --id period-002-NEW-he-validation
& $MaintenancePython -B -X utf8 scripts/prepare_period2_stage_a.py --id period-002-NEW-preparation
& $MaintenancePython -B -X utf8 scripts/run_period2_stage_a.py --id period-002-NEW-comparison --preparation period-002-NEW-preparation --validation period-002-NEW-he-validation --benchmark-python $BenchmarkPython
```

本測定は各モデルの条件を順次実行し、速度probe・legacy replayと400個の新規回答を区別します。段階Aの所要時間・能力差・失敗を確認してから段階B/Cへ進めます。進行中の原証拠はwriter停止・匿名化・検証・checksum更新前に公開完了とは扱いません。
