# Hermes Agent：ローカルQwenでの使い方

Hermes Agent v0.22.5 と llama.cpp CUDA b11946 を接続しています。既定モデルは Qwen3.5-4B Q4_K_M、コンテキストは1枠65,536トークンです。

## 起動と停止

デスクトップの **Hermes - Local Qwen** を開いてください。モデルを準備してからチャット画面が開きます。

新しいターミナルでは次のコマンドも使えます。

```powershell
hermes
```

チャット画面の `/quit` で会話を閉じます。モデルは起動したままです。RAM・GPUメモリを解放するには、PowerShellから次を実行してください。

```powershell
& 'C:\LocalLLM\hermes\bin\hermes-local.cmd' --stop
```

状態確認と直前の会話の再開：

```powershell
& 'C:\LocalLLM\hermes\bin\hermes-local.cmd' --status
& 'C:\LocalLLM\hermes\bin\hermes-local.cmd' --continue
```

作業開始フォルダーは `C:\LocalLLM\workspace\hermes` です。例えば「このフォルダーのファイルを一覧にしてください」と依頼できます。

## 設定と記録

- `hermes model`：モデル・プロバイダー設定。
- `hermes tools`：有効なツール設定。初期状態ではファイル操作、ターミナル、記憶、スキルなどのローカル作業向け機能を選択しています。
- 接続先：`http://127.0.0.1:8089/v1`。クラウドLLMへの自動フォールバックは設定していません。
- 本体・設定の実際の保存先：`installation.json` の `hermes_source` と `hermes_home`。
- 動作確認の結果：`runs/verification.json`。ファイル読取、PowerShellでの合計計算、JSON更新、同じ会話の再開を確認しました。

既存のQwen3.6-35B-A3B用には `profiles/large.json` を用意しています。Hermes併用の試行で空きRAMが約1.3GiBまで減ったため、日常用には4Bを採用しました。35BのHermesツール連携は未検証です。検証時は先に日常モデルを停止し、RAMの空きを確認してから `hermes-local --model large` を使います。停止時も `--model large --stop` を指定します。

起動プログラムは別モデルの自動停止を行いません。同じポートに別モデルがあれば、その起動元で停止してから実行してください。

2026-10-28に基本動作を確認しました。約10Kの会話での確認であり、64K全体を使う検索品質や長時間の自律作業の評価ではありません。
