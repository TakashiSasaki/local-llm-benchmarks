# 第2期 引き継ぎ監査 — 2026-11-06 JST

測定停止を維持し、期はopenです。停止フラグ解除、モデル起動、新規推論、取得、shutdown監視起動、shutdown予約は行っていません。第1期の原結果・inventory・recipe・比較ページも維持しています。

## 保存結果

[比較ページ](reports/index.html) / [比較表](reports/comparison.md) / [原回答参照とSHAを含むJSON](reports/comparison.json)。新規能力回答は588/1,600件、未収集1,012件。通常4B/Abliterix4Bは400件完了、通常9BはBFCL OFF80＋ON80＋HE OFF20＋HE ON8の188件です。11条件完了・1部分収集・20未実施。probe/smoke/replayは加算しません。

`tools/verify_period2.py`は全588 rawと問題順、保存採点、入力、sampler、seed、思考設定、token予約、usage、finish_reason、秒数を照合します。BFCL480件は固定公式ASTで再採点し、HE108件は同じ抽出器・主採点・測定用Python3.14.9で再実行して全件一致しました。model-runメモリjsonlの標本数/極値、速度probe9本の中央値も照合しました。原run/sourceは読み取り専用で、replayは新規回答として登録しません。

通常9B HE ONは7/8正解・12問未実施です。親/条件のstatus=failedとsummary.outcome=deferred、stop_reason=execution_window_deferred、model_failure=falseを両方残します。HumanEval/35はcompletion64,000＋prompt130、finish_reason=length、no_final_code、約6,763.7秒。出力上限でありAPI timeout/context不足ではありません。Abliterix HE ONは主17/20、旧legacy replay16/20を別記します。

## 停止・環境

監査時の関連測定writer、llama-server、古いshutdown監視、関連Windowsタスク、8089待受はいずれも0。関係ないHermes/Blender MCPプロセスには触れていません。私有プロセス一覧、タスク/port照合は`.local/validation/handoff-20261106/`に保持します。

旧`.local/validation/shutdown-after-request-20261102.json`はenabled=trueのままです。**scripts/shutdown_after_request.pyと旧設定を再起動しないこと**。保存済み終了条件で直ちにshutdownする恐れがあります。stateの2026-11-02T09:00:03.719137Zはshutdown_requestedと元所有プロセス全終了を記録していますが、実際の電源断時刻は検証していません。旧11月3日06:00予約は解除済み。execution-window.jsonのstop_after_current_task=trueと過去期限は維持します。

現行watcherコードには消費済みshutdown_requested/shutdown_startedの再利用を拒否するガードを追加し、OS API/終了コマンド/履歴書換より前に拒否することをmockテストで確認しました。旧source snapshotは変更していないため、引き続き旧監視を起動しない運用が必要です。

[環境/hash記録](environment/handoff-20261106.json)。maintenance Python3.12.14、benchmark Python3.14.9、llama-server b11960/8642541b2を実在/version/hashで確認。9B4ファイルを全SHA/bytes照合し一致、35B第2期候補2ファイルは未取得。C空き約88.8 GiB（監査時）、35B候補計42,333,517,152 bytes取得後も32 GiB予約を維持する見込みですが、再開時に再確認が必要です。モデル/ランタイムはGit外です。全測定でF16 K/V・context65,536・MTP OFFを固定しました。

## 再開指示後の継続方法

1. 古い停止/shutdown設定を履歴保存し、旧監視を明示的に無効化。新しいtimezone付き実行期限をユーザー指示に沿って設定します。新しいshutdownは別途指示なしに予約しません。
2. 既存588回答は再測定しません。通常9B HE ONは[continuation定義](configs/q35-9b-he-on-continuation.json)の未実施12 IDを固定順で新runへ収集します。参照8 ID、各raw SHA、採点一覧SHA、件数を固定しました。既存run/sourceへresumeしません。
3. HumanEvalドライバに`--subset-plan`を追加しました。定義の重複/欠落/順序/参照hashを検証し、新runへコピーします。既存8問をコピーして新rawとして計上せず、新12問のrun得点と参照8問をIDで合わせた20問の比較を分離します。現在の停止ではAPI問い合わせ前に拒否します。subset収集の実測はまだ行っていません。
4. 新runのconfig.modelには通常9Bの固定SHAを含め、モデル・runtime・-ngl24/CPU MoE0・既存sampler/思考ON/主採点を確認。`run_mtp_study.py`は全4条件を実行するため、そのままsubset用に使わず、所有サーバーの起動/cleanupとsubsetドライバをつなぐ専用オーケストレーションを再開時に作ります。
5. 続いてHuihui9B/Heretic9B/Defiant9Bを各200件（600）、35B対を各200件（400）。35B取得/配置preflightは未実施、第1期ファイルは代用しません。`run_period2_remaining.py`の新IDでの丸ごと再起動は通常9B完了条件を再収集するため禁止します。

## 公開範囲

開始HEADは227c485、origin/mainも一致。初期git status全文と公開前diffは`.local/validation/`へ保存。未追跡7,070ファイルを消さず監査し、実行コード・第2期run/固定source・vendorライセンスを公開対象にしました。個人パス/credential検査と既存sanitizerを実行し、今回の文字列変換は0件でした。私有原本を`.local/original-evidence/`に保持し、raw/source bytesを変更しません。独自コードMIT、上流HumanEval/BFCLの既存ライセンスを維持します。

必須検査と第2期専用検証の結果は[検証記録](reports/validation.json)に記録します。カタログ/checksumsはwriter停止確認後に更新します。第2期は閉鎖/タグ付けしません。
