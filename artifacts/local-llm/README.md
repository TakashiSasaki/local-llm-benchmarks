# WindowsローカルLLM評価

VL版（LFM3-VL-2B）もQAD-Q4_0とQ8_0の両方を導入済み。共通のF16 vision projectorを使い、64K・1 slotで伝票OCRと図形・位置関係の2課題に両方正解した。起動例は次のとおり。停止は同じ選択に-Stopを付ける。省略時のText/QAD設定は保持。

```powershell
& 'C:\LocalLLM\run-lfm3.ps1' -Mode VL -Quantization QAD-Q4_0
& 'C:\LocalLLM\run-lfm3.ps1' -Mode VL -Quantization Q8_0
```

上記は一方を停止してから切り替える。簡易画像試験の生成速度（思考含む）は4bit約171〜177、8bit約111 token/s、観測したシステムGPU使用量は約2.75/3.49 GiB。記録はruns/lfm3-vl-20261030-131519/report.json。各2画像のみで、動画・長時間運用・日本語文字OCR・Hermes連携は未検証。

## LFM3用の更新環境（2026-10-30）

llama.cpp安定版v0.8.0（b11960、公式Windows CUDA 12.4版）と、公式のLFM3-1.7B-QAD-Q4_0を導入した。旧b11946と下記の3モデル比較用profileは再現用に保持している。新環境の参照先はruntime-current.json、LFM3の設定はprofiles/lfm3.json。

```powershell
& 'C:\LocalLLM\run-lfm3.ps1'
# Webチャット: http://127.0.0.1:8089
# OpenAI互換API: http://127.0.0.1:8089/v1
& 'C:\LocalLLM\run-lfm3.ps1' -Status
& 'C:\LocalLLM\run-lfm3.ps1' -Stop
```

Q8_0版も追加し、同じ64K・1 slotで短い日本語応答と実ファイルツールの往復を確認した。選択して起動・停止するには次を使用する。省略時は従来のQAD-Q4_0版を選ぶ。

```powershell
& 'C:\LocalLLM\run-lfm3.ps1' -Quantization Q8_0
& 'C:\LocalLLM\run-lfm3.ps1' -Quantization Q8_0 -Stop
```

Q8_0の短文生成は約111.65 token/s（思考含む）、観測GPU使用量はシステム全体で2,805 MiB。日本語の2文指定には1文で応答したため、この試験から指示追従や総合品質の向上は断定しない。取得hash・実行記録・比較値はruns/lfm3-q8-20261030-130924/report.json。

既存モデルをその起動元で停止してから起動する。コンテキスト65,536、1 slot、F16 KV、CUDA0へ25/25層を配置。短い日本語応答と実ファイル読取ツールの往復・集計結果を確認済み。生成は思考トークンを含め約170〜177 token/s、試験中の観測GPU使用量はシステム全体で2,045 MiB。64K近くまで入力を埋めた試験、長時間の安定性評価、Hermes連携は未実施。Hermesの既存daily/large設定は従来のruntimeを保持している。

取得revision・SHA-256・ログ・要求/応答・観測メモリと検証結果はruns/lfm3-setup-20261030-125557/に保存。最終結果は同フォルダーのreport.jsonを参照する。

計画は docs/goal-objective.md、比較報告は comparison.md。作業ルートは C:\LocalLLM。

指定の3 GGUFを固定revisionから取得し、全体のサイズとSHA-256を照合済み。同一の llama.cpp b11946（公式Windows CUDA 12.4配布）を使用する。主評価では同時に1モデルだけ起動する。

## 状態と記録

進行中の評価は runs/local-evaluation-progress.json、完了した実タスクの一覧は results.csv を参照する。PowerShellはPS1～PS4の4課題。Linux BashとSSH運用の8課題は、利用者のSSH検証先が未準備のため未実施。全12課題による採用判断は未完了。

ASUS側の冷却モードは未確認。AC接続、Windows Turbo電源プラン、試験中の実測温度を記録した。WindowsのDLL署名拒否は利用者がSmart App Controlをオフにした後に解消し、元のb11946でCUDA実行を確認した。

| profile | n_cpu_moe | t / tb | context / KV | thinking |
|---|---:|---|---|---|
| qwen-eval-v1 | 30 | 8 / 8 | 16384 / F16 | on |
| lfm-eval-v1 | 24 | 6 / 8 | 16384 / F16 | 常時thinking |
| glm-eval-v1 | 35 | 8 / 8 | 16384 / F16 | on |

n_cpu_moeは先頭のN層のMoE重みをCPUへ残す指定。sampling等の完全な設定は profiles/*.json、実効defaultsは各実行のsource ZIP内のserver-propsに保存する。

## 起動とCLI

PowerShellから次を実行する。qwen、lfm、glmを切り替えられる。

```powershell
Set-Location -LiteralPath 'C:\LocalLLM'
$python='C:\Users\benchmark\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& .\run-lfm.ps1
& $python .\scripts\agent.py --profile lfm --workspace 'C:\LocalLLM\workspace\daily' --prompt 'この作業領域のファイルを調べて一覧を作ってください'
& .\run-lfm.ps1 -Stop
```

CLIは生成したコマンドを実行する。専用workspaceを指定する。通常の依頼には独立した正解採点がなく、回答の完了申告だけでは成果物の正しさを保証しない。評価課題は trial.py が別の採点処理で検証する。

Ctrl+Cはmodel streamを閉じ、そのCLIが開始したjobの停止を試み、確認結果をログへ保存する。終了コードは130。入力が16Kを超える場合は履歴を黙って削らず停止する。通常課題は300秒、長いSSH課題は480秒、最大12 tool calls、1要求4096生成token。

SSH/SCPの通信待機には課題の残り時間を設定し、Windowsの専用Jobで所有する通信processの停止を試みる。ローカルの合成processと接続なしのssh/scp起動で確認した。OS呼出しや他の処理は厳密に時間制限できず、実SSHでの挙動も未確認。時間超過は採点時に未完了とする。

## executorの契約

- run_powershell / run_ssh_bash: 呼び出しごとに新しいprocess。cwdとenvを毎回指定する。timeoutは0～60秒の待機時間であり、超過してもjobは続く。
- poll_process: job_idとbyte offsetで追記出力、終了状態、切り詰めの有無、全ログの保存先を得る。
- stop_process: 管理jobのWindows process treeまたはLinux process groupを停止する。Linux側は実機でgroup内の子processまで終了したかを検証する必要がある。
- transfer_file: 許可済みhostと専用workspace間のSCP。転送先のhash確認は別途行う。

モデルが生成するscriptの内容をOSの権限で実行する構成であり、workspace引数はOSレベルのサンドボックスではない。

SSHのpoll/stop応答はjob ID、host、状態、出力範囲を検証する。停止が未確認の場合はその状態を保存し、後続pollの完了表示だけで解除しない。通信を使わない回帰試験で確認済みだが、実SSHでは未検証。通信processのローカル停止確認と遠隔jobの終了は別に記録する。出力サイズの監視はポーリング方式で、検査間に上限を超えることがある。実SSHとProxyCommandの動作は未検証。

## SSH先の準備後

Linux側にBash、Python 3.10以上、専用作業ディレクトリ、既存OpenSSH認証と確認済みhost鍵が必要。秘密鍵・パスワードをmodelやprofileに渡さない。executor-config.jsonのssh_hostsに以下の形で登録する（値は実際の検証先に置き換える）。現在は空で、未登録hostは拒否する。

```json
{
  "test-linux": {
    "worker_path": "/home/USER/codex-llm-test/executor_worker.py",
    "workspace_root": "/home/USER/codex-llm-test/workspace",
    "state_root": "/home/USER/codex-llm-test/jobs"
  }
}
```

1. host登録後、作業ルートで `& $python .\scripts\grading.py` を実行し、更新したconfigと採点定義を固定する。
2. `& $python .\scripts\bootstrap.py test-linux` で実Linux、Bash、Python、専用領域とworkerを確認する。
3. `& $python .\scripts\smoke_ssh_contract.py test-linux` でモデルを使わず、SSHのstdout/stderr、終了コード、cwd/env、poll/stop、転送とhashを実機確認する。
4. 各modelを起動し、例えば `& $python .\scripts\smoke_real_ssh.py qwen --host test-linux` でモデル経由のSSH tool往復を確認する。modelごとに同じ確認を行い、同時に複数のserverを起動しない。
5. 同じprofileでB1～B4・S1～S4を各1回実施し、計24件を追加する。新runには新しいsource ZIPとsuite lockが保存される。既存Windows試行の記録は保存する。
6. 全36件を比較し、必要なら計画の接戦時再試行・条件差試験へ進む。

SSH経路と両方のsmokeは実Linux接続では未検証。smokeの停止確認にはSIGTERMを無視する子processも含み、子processの終了と遅延markerが作成されないことを独立して確認する。stop前にshellの終了記録が既にある場合、pollのcompletedだけでは残存するbackground子processの終了を証明しない。通信断によるjobのunknownや転送のmay_be_partialは成功と扱わず、保存されたIDと状態から確認する。bootstrap.py は既存workerが異なる内容なら上書きせず停止する。S2/S3のshell traceが静的に判別できない場合は手動確認フラグを残す。

## 再現用ファイル

- environment.json: 実機、OS、driver、電源条件。
- runtime-manifest.json / model-manifest.json: 配布元、固定revision、全体hash。
- profiles/*.json: 主評価の配置、sampling、thinking、予算。
- runs/*.jsonl: HTTP/SSE、tool引数と結果、時刻。
- runs/*.summary.json / *.memory.jsonl: 独立採点と資源記録。
- runs/*.source.zip: 各agent実行時のsource、profile、manifest、suite lock、実効server設定。
- results.csv / results-analysis.json: 主課題と性能測定の集計。疎通・CPU診断・合成テストは主課題の点数に含めない。

TTFTは最初の非空SSE生成フィールドの受信時刻で、thinking開始を含む。first valid tool callは完全なJSON引数を検査できた応答完了時刻を保守的に記録する。未取得の指標はnull。
