# ローカル3モデル比較（Windows部分の評価）

更新: 2026-10-28T16:40:34+09:00

3モデルを同一のWindows CUDA runtimeで導入し、PowerShellの4課題を比較した。Linux BashとSSH運用の8課題×3構成は、利用者の検証先が未準備のため未実施。全12課題による採用判断は未完了。未実施は失敗に数えない。

Windowsの完了数はQwen 3/4、LFM 2/4、GLM 2/4。GLMには誤った完了申告が1件あった。LFMは性能測定で生成速度とRAM余裕に利点が見られたが、この4課題では成功数が低かった。QwenはPS4の成果物を修復したものの、履歴の上限で最終回答に至らなかった。現在の情報だけで常用構成を確定しない。

## 固定した構成

| 項目 | 条件 |
|---|---|
| 実機 | ASUS TUF A15 FA507XI / Ryzen 9 7940HS（8C16T）/ RAM 32GiB |
| GPU / driver | RTX 4070 Laptop、8188MiB / 555.97 |
| OS / shell | Windows 11 Home build 26300 / PowerShell 7.6.5 / OpenSSH 9.5p2 |
| 電源 / 冷却 | AC、Windows Turbo。ASUS側は利用者によるとBIOS AUTOの可能性、未確認 |
| runtime | llama.cpp b11946、commit 8ca4060b7e30e76baaa5670ee1ec1b760b7f8552、公式CUDA 12.4配布 |
| 共通 | 16,384 context、F16 KV、np1、ngl all、b2048/ub512、FA auto、cache-ram0、fit off、context shift無効 |
| 制限 | 通常300秒、12 tool calls、1要求4096生成token。履歴は保持し、context不足時は停止 |

| 構成 | n_cpu_moe | t / tb | thinking | sampling（明示値） |
|---|---:|---|---|---|
| Qwen eval-v1 | 30 | 8 / 8 | on | temp .6、top_p .95、top_k 20、min_p 0、presence 0、repeat 1 |
| LFM eval-v1 | 24 | 6 / 8 | 常時thinking | temp .1、top_k 50、repeat 1.05。他はserver defaultsを保存 |
| GLM eval-v1 | 35 | 8 / 8 | on | temp .7、top_p 1、min_p .01、repeat 1 |

n_cpu_moeは先頭N層のMoE重みをCPUへ残す指定。expert個数ではない。各モデルの固定profile、GGUF全体hash・取得revision、runtime配布hashはmanifestに保存した。全モデルでCUDA0を使用し、起動時graphのFLASH_ATTN_EXTノードをtraceで確認した。起動trace単独はkernel実行の計測ではない。nglのoffloaded layer数だけから全重みがGPUにあるとは解釈しない。

## PowerShell課題の成績

同じfixture、共通executor、同じ上限を使った各1試行。モデルの最終回答とは別の採点処理で成果物と保護入力、PS4の追加5ケースを検証した。元の要求・応答・実行script・stdout/stderrと、その時点のsource ZIPを保存した。

| 構成 | 成功 / 実施4題 | 総秒（失敗含む） | 成功課題の中央値 秒 | 初回有効tool callの中央値 秒 | 誤完了申告 | 誤host | 人間の介入 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.6 UD-Q3_K_M | 3 / 4 | 502.99 | 95.55 | 9.65 | 0 | 0 | 0 |
| LFM2.5 QAD-Q4_0 | 2 / 4 | 325.55 | 48.60 | 10.24 | 0 | 0 | 0 |
| GLM-4.7-Flash Q4_K_M | 2 / 4 | 581.99 | 115.45 | 9.93 | 1 | 0 | 0 |

| 構成 / 課題 | 成否 | 秒 | 初回tool 秒 | model / tool calls | 生成token | 判定・失敗分類 |
|---|---|---:|---:|---|---:|---|
| [qwen / PS1](C:/LocalLLM/runs/PS1-qwen-20261028-152410.summary.json) | 合格 | 95.55 | 8.80 | 9 / 8 | 2641 | 合格。角括弧pathと変数展開のPowerShellエラー計3回から復旧 |
| [qwen / PS2](C:/LocalLLM/runs/PS2-qwen-20261028-152545.summary.json) | 合格 | 110.68 | 9.01 | 9 / 8 | 3220 | 合格。出力のBOMを検出して自身で除去 |
| [qwen / PS3](C:/LocalLLM/runs/PS3-qwen-20261028-152736.summary.json) | 合格 | 86.98 | 11.56 | 11 / 10 | 2345 | 合格。初期設定による失敗を再現しinput_fileのみ修復 |
| [qwen / PS4](C:/LocalLLM/runs/PS4-qwen-20261028-152903.summary.json) | 不合格 | 209.78 | 10.29 | 11 / 11 | 6304 | context上限で未完了（成果物の独立5ケースは合格、最終回答なし） |
| [lfm / PS1](C:/LocalLLM/runs/PS1-lfm-20261028-153449.summary.json) | 不合格 | 66.36 | 13.69 | 13 / 12 | 2351 | tool上限で未完了。input探索と角括弧pathの解釈から復旧できず |
| [lfm / PS2](C:/LocalLLM/runs/PS2-lfm-20261028-153556.summary.json) | 合格 | 40.97 | 7.59 | 5 / 4 | 1607 | 合格。CSVを読み計算した定数値をJSONへ保存 |
| [lfm / PS3](C:/LocalLLM/runs/PS3-lfm-20261028-153637.summary.json) | 合格 | 56.23 | 12.52 | 9 / 8 | 2118 | 合格。設定の参照先のみ修正して実行 |
| [lfm / PS4](C:/LocalLLM/runs/PS4-lfm-20261028-153733.summary.json) | 不合格 | 161.99 | 7.97 | 13 / 12 | 6016 | tool上限、修復未完了。JSON数値型と列不足の検証が不合格 |
| [glm / PS1](C:/LocalLLM/runs/PS1-glm-20261028-154127.summary.json) | 不合格 | 96.36 | 8.81 | 10 / 9 | 2204 | ファイル名sortが逆順。誤った完了申告あり |
| [glm / PS2](C:/LocalLLM/runs/PS2-glm-20261028-154303.summary.json) | 合格 | 157.78 | 10.21 | 9 / 8 | 3751 | 合格。Infinity出力を確認し数値型へ変換して修正 |
| [glm / PS3](C:/LocalLLM/runs/PS3-glm-20261028-154541.summary.json) | 合格 | 73.11 | 9.64 | 7 / 6 | 1742 | 合格。初期失敗を再現しconfigのみ修正 |
| [glm / PS4](C:/LocalLLM/runs/PS4-glm-20261028-154654.summary.json) | 不合格 | 254.74 | 11.20 | 11 / 11 | 5952 | context上限、修復未完了。status列をpaid列と取り違え |

task wall timeは初回指示から独立採点終了までで、失敗も総時間に含む。first valid tool callは完全なJSON引数をschema検査できた応答完了時刻を保守的に採用した。訂正は同一試行の上限内で許容。訂正回数の独立した定量値は未取得（null）。tool非0終了数は故障の再現や意図した負例も含み、成果物が誤っていても終了0になるので、訂正回数やモデル失敗数とは区別する。人間がtask実行中にヒントや成果物修正を行った試行はない。

## 入力長とprefix再利用の測定

同じログ本文3サイズを各モデルへ渡し、prefix未再利用と同prefixへの追記を各3回、計18要求/構成を測定。モデルロード済み、ダウンロードなし。OS file cacheは強制消去していない。cache-ram 0でもKVのprefix再利用は観測された。再利用数はserver実測値。warm要求は前応答を含むため総token数が変わる。

数値は中央値 [最小, 最大]。PP/TGはserverが報告した新規入力/生成tokenの処理速度。TTFTはclientの最初の非空SSE生成フィールド（thinking開始を含む）まで。異なるtokenizerのtoken/sやthinking量を一般的な品質順位に使わない。

| 構成 | 入力 | cache | 総入力token | 再利用token | PP token/s | TG token/s | TTFT 秒 | 応答全体 秒 |
|---|---|---|---|---|---|---|---|---|
| qwen | short | なし | 610 [610, 610] | 0 [0, 0] | 376.2 [317.5, 383.3] | 35.2 [35.1, 35.3] | 1.64 [1.60, 1.93] | 9.63 [9.59, 9.89] |
| qwen | short | 追記 | 918 [918, 918] | 891 [891, 891] | 84.3 [83.2, 86.9] | 35.2 [35.0, 35.2] | 0.33 [0.32, 0.33] | 7.01 [6.99, 7.04] |
| qwen | medium | なし | 4354 [4354, 4354] | 0 [0, 0] | 548.3 [548.2, 549.0] | 34.8 [34.7, 34.8] | 7.95 [7.94, 7.95] | 16.39 [16.38, 16.42] |
| qwen | medium | 追記 | 4675 [4675, 4675] | 4648 [4648, 4648] | 86.1 [84.3, 88.8] | 34.5 [34.5, 34.8] | 0.33 [0.31, 0.34] | 6.34 [6.30, 6.37] |
| qwen | long | なし | 8696 [8696, 8696] | 0 [0, 0] | 564.6 [563.8, 565.2] | 34.2 [34.2, 34.3] | 15.41 [15.40, 15.46] | 22.91 [22.90, 22.97] |
| qwen | long | 追記 | 8980 [8980, 8980] | 8953 [8953, 8953] | 86.7 [84.1, 86.9] | 34.2 [33.9, 34.2] | 0.32 [0.32, 0.33] | 5.85 [5.85, 5.90] |
| lfm | short | なし | 592 [592, 592] | 0 [0, 0] | 462.0 [374.4, 464.9] | 52.5 [52.3, 53.6] | 1.32 [1.32, 1.63] | 5.03 [4.96, 5.35] |
| lfm | short | 追記 | 816 [816, 816] | 789 [789, 789] | 132.6 [125.1, 141.6] | 48.9 [48.2, 49.6] | 0.24 [0.24, 0.25] | 1.41 [1.38, 1.42] |
| lfm | medium | なし | 4192 [4192, 4192] | 0 [0, 0] | 749.1 [746.1, 751.4] | 51.3 [51.0, 51.4] | 5.60 [5.59, 5.64] | 10.67 [10.64, 10.69] |
| lfm | medium | 追記 | 4479 [4479, 4479] | 4452 [4452, 4452] | 131.1 [126.1, 131.3] | 47.0 [46.6, 47.4] | 0.23 [0.23, 0.23] | 2.70 [2.68, 2.72] |
| lfm | long | なし | 8367 [8367, 8367] | 0 [0, 0] | 789.8 [786.9, 792.1] | 50.3 [50.0, 50.6] | 10.60 [10.57, 10.64] | 14.08 [14.07, 14.16] |
| lfm | long | 追記 | 8571 [8571, 8571] | 8544 [8544, 8544] | 136.2 [134.7, 137.6] | 48.0 [47.8, 48.8] | 0.21 [0.21, 0.24] | 1.34 [1.34, 1.35] |
| glm | short | なし | 518 [518, 518] | 0 [0, 0] | 393.3 [345.6, 401.7] | 30.5 [30.5, 30.8] | 1.33 [1.29, 1.52] | 8.90 [8.87, 9.02] |
| glm | short | 追記 | 769 [769, 769] | 749 [749, 749] | 108.9 [108.2, 110.1] | 26.9 [26.5, 26.9] | 0.20 [0.19, 0.20] | 7.35 [7.34, 7.44] |
| glm | medium | なし | 3686 [3686, 3686] | 0 [0, 0] | 408.6 [408.3, 410.0] | 28.7 [28.7, 29.1] | 9.03 [8.99, 9.03] | 19.85 [19.68, 19.86] |
| glm | medium | 追記 | 4017 [4017, 4017] | 3997 [3997, 3997] | 98.8 [97.4, 101.7] | 25.8 [25.7, 26.0] | 0.23 [0.20, 0.23] | 11.42 [11.34, 11.48] |
| glm | long | なし | 7393 [7393, 7393] | 0 [0, 0] | 419.3 [417.1, 420.2] | 27.1 [27.1, 27.2] | 17.64 [17.60, 17.74] | 31.49 [31.37, 31.56] |
| glm | long | 追記 | 7788 [7788, 7788] | 7768 [7768, 7768] | 93.4 [92.5, 94.5] | 25.8 [25.5, 25.9] | 0.22 [0.22, 0.23] | 7.90 [7.88, 7.99] |

モデルロード時間は性能測定前の起動1回で、Qwen 14.63秒、LFM 11.64秒、GLM 9.63秒。OS file cache未消去の単発値であり、cold diskからの起動や3回の中央値ではない。通常応答の測定値にロード時間は含めない。

初回のQwen/LFMスレッド探索時には背景ダウンロードが動いていたため、固定配置のままスレッド6/8/12/16を再測定した。coldとprefix再利用の各256生成token、2要求の合計秒はQwen 18.990/18.156/17.592/18.500、LFM 13.196/13.688/14.217/15.226。既知のmodel download processは各条件の前後で未検出。各条件1回かつ固定順で、OS cacheを消去せず他の通信も排除していないため、差の再現性は未確定。既存profileと主評価結果は変更していない。測定条件・結果・sourceはruns/threads-no-download-20261028-163531.jsonと同名source ZIPに保存した。

## 資源の観測

| 構成 | GPU全体ピーク MiB | process working set GiB | private GiB | 最低available RAM GiB | GPU最高温度 ℃ |
|---|---:|---:|---:|---:|---:|
| qwen | 6617 | 17.12 | 8.74 | 4.51 | 61 |
| lfm | 6751 | 13.21 | 6.99 | 8.44 | 57 |
| glm | 7105 | 17.47 | 7.44 | 4.03 | 63 |

性能測定と有効な課題試行の2秒周期サンプルの極値。GPU値はシステム全体で他processも含み、瞬間ピークを取り逃す可能性がある。working setはmmapページを含み、private memoryとは意味が異なる。shared GPU memoryと持続的pagingの直接測定は未取得。各model群の開始前にAC・CPU/GPU使用率・GPU温度の同じidle条件を確認した。ASUSの冷却設定は未確認なので、別環境や別日の再現時には設定差を記録する。

## 基盤の修正と除外記録

最初のPowerShell試行で、wrapperの明示exitが書式整形待ちのオブジェクト出力を失う問題を実測した。同じscriptの直接実行では一覧が表示された。Out-Defaultで書式pipelineを排出してから終了し、実行成功状態を別途保持する共通修正を行った。FileInfo、PSCustomObject、object出力後のexit 7を回帰試験に追加した。修正後のexecutor 20項目、参照課題6項目、中断時の実process停止6項目が合格した。

修正前バッチのQwen PS1（tool上限）、PS2（採点合格）、PS3（serverを止めて中断）を一貫して主表から除外し、3構成の全4課題を修正版で実施した。除外理由はevaluation-exclusions.json、元の進捗はruns/local-evaluation-aborted-object-output.json、元の全runは保持した。推論だけの性能測定はexecutorを通らないため再利用した。

Windows評価後、JSONの真偽値が数値0/1と同値と扱われる採点上の欠陥、実行期限後のタイムアウト分類、SSH先Pythonの最低版チェックを修正した。Windows評価時のsuite lock（56d344f8…）とsource ZIPを保存し、現在の改訂版は別のsuite lockを使う。保存済み12試行の静的採点と、保存スクリプトを隔離して再実行したPS4の15ケースでは合否が変わらなかった。元のPS4一時出力は残っていないため、再実行は保存スクリプトによる確認である。詳細はanalysis/json-draft/test-results.json、ps4-replay-results.jsonとruns/suite-revision.json。

また、POSIX groupへの停止シグナル後はworkerの終了記録とgroupの消滅が両方確認できた場合だけstop_verifiedとするよう修正し、模擬8ケースとWindows実executor20ケースを通した。stop前に終了記録が既にある場合はpoll結果を返すため、background子processまで終了したかは別途の確認が必要。Linuxの実信号配送は未検証。

続いてSSH準備を改善し、事前確認のpath境界・依存関係・既存workerの保護、通信異常時のjob ID保持、残り時間のSSH/SCP待機への反映、S2/S3/S4の操作履歴の採点を追加した。実SSHとモデルを使う2種類の疎通試験を準備し、通信を使わない模擬テストで確認した。Windowsの子processが出力pipeを継承すると親のtimeout後も待機が延びる合成例を再現したため、ローカル通信processを専用Jobで管理する方式へ変更し、実Windows processと接続なしのssh/scp起動で確認した。停止確認はローカル側に限り、遠隔jobと転送の状態は別に扱う。OS呼出しや他の採点処理を含む厳密な壁時計上限と実Linux接続は未確認。詳細はruns/owned-transport-revision.json。

Qwen PS4の別診断ではthinkingのみをoffにし、samplingを主評価のまま維持した。169.28秒、生成4613 token、tool 12回で上限に達して最終回答がなく、独立5ケース中4件が合格、空入力が不合格。thinking onの主試行は209.78秒、6304 tokenで成果物5ケースは合格したがcontext上限で未完了。各1試行であり一般的な優劣や原因は断定できない。off時のsamplingは公式non-thinking推奨設定ではなく、残るB4/S3/S4はSSH先未準備のため未実施。別診断は主表に含めない。設定・source・結果はruns/diagnostic-qwen-no-thinking-ps4.meta.jsonおよび同名provenance ZIPに保存した。

P5前の疎通では、コードをJSON文字列として再解釈する曖昧さをコードブロック形式へ統一した。GLMのjob試験では追加の読み取り確認を二重起動と数える検証を修正した。元の診断ログも保存し、主課題成績には含めない。CPUのみのQwen診断、疑似tool、合成snapshot試験も点数から除外した。

## 未完了と再開手順

Qwen PS4では修正成果物が独立5ケースに合格した一方、追加の確認を続けた後に入力12,676 token、残り3,708 tokenとなり、4096生成tokenの予約に足りず停止した。最終回答がないため、この固定履歴規則の構成では未完了とした。script修復能力の欠如やQ3量子化が原因とは判定しない。context管理の条件差を検討する場合も別profile/runとし、元の成績を置き換えない。

その後、上限だけを3584 tokenに下げた別診断で同じPS4を再試行した。入力12,819 token、残り3,565となり再びcontext上限で最終回答前に停止。修正成果物は独立5ケースのうち正常・小数・空の3件が不合格だった。この単発の追加診断は主表の12試行に含めず、設定・driver・sourceをruns/diagnostic-qwen-reserve3584.provenance.zipに保存した。上限変更だけで問題が解消するとは確認できなかった。

LFM PS1はinputサブディレクトリの探索と角括弧のwildcard解釈でtool上限に達した。PS4は空入力エラーを自身で修正したが、totalをJSON文字列で保存し、列不足の判定も不正なまま上限へ達した。QAD量子化の影響だけとは切り分けられていない。追加量子化を試す場合は、計画に従い別構成として固定課題を比較する。

GLM PS1はUTF-8 byte配列をSort-Objectのkeyに渡した結果、ファイル名が逆順になった。日本語/英語照合とordinal比較がいずれも採点の期待順と一致することを実機で確認した（runs/ps1-collation-review.json）。最終回答で昇順・完了を申告したため誤完了申告1件とした。PS4は提供data.csvを読まず、status列をpaid列としてテストを作り、通常入力で失敗するscriptのままcontext上限へ達した。

SSH検証先が未準備のため、B1～B4・S1～S4の24試行、実LinuxでのSSH executor・SCP・remote stop確認、全12課題の採用条件、必要時の接戦再試行と条件差比較は未完了。現在の4課題の差を12課題の成功率や一般的なモデル順位に拡張しない。

README.mdにCLI起動とSSH設定例を記載した。Linux側でBash/Python 3.10以上、既存認証、確認済みhost鍵、専用rootを用意してbootstrap.pyで検証する。その後modelなしとmodel経由の実SSH往復を確認し、同じprofileで残り8課題を実施する。SIGTERMを無視する子processを含めremote stopを実機で検証する。source/config変更時は新しいsuite lockとsource ZIPを保存する。常用モデルは全課題が揃ってから決定する。

## 証拠と再現性

- model-manifest.json / runtime-manifest.json / environment.json / profiles/*.json
- runs/local-evaluation-progress.json / results.csv / results-analysis.json / runs/adjudication.json
- runs/*.source.zip（script、profile、manifest、suite lock、実効server defaults）
- runs/*.jsonl、*.summary.json、*.memory.jsonl、logs/server-*.log
- runs/backend-trace-qwen.json、backend-trace-lfm.json、backend-trace-glm.json
- runs/final-local-audit-windows-eval-56d344f8.json: 元の12試行のsource ZIP、採点・手動判定、終了状態を評価時に確認した記録。

公式配布・仕様: [llama.cpp b11946](https://github.com/ggml-org/llama.cpp/releases/tag/b11946)、[固定buildのserver仕様](https://github.com/ggml-org/llama.cpp/blob/b11946/tools/server/README.md)、[Qwen公式](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)、[LFM公式GGUF](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B-GGUF)、[GLM公式](https://huggingface.co/zai-org/GLM-4.7-Flash)。実測値の根拠はローカルrun記録。
