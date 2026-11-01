# 公開準備メモ

このフォルダーは `local-llm-benchmarks` リポジトリです。ローカルルートは `C:\LocalLLM\local-llm-benchmarks`、公開先は `https://github.com/TakashiSasaki/local-llm-benchmarks` です。公開準備とGitHub側への反映の状態は実際のGit履歴・remoteで確認してください。

## 対象

2026-10-30のLFM3 Text/VL・Qwen・LFM2.5・GLM比較、必要な2026-10-29のQwen基準測定、出力／コンテキスト打ち切り監査が参照する以前のPS4・容量診断をまとめました。途中で停止したrun、修正前のソース、採点制約の補助監査も履歴として含みます。未完了runを成功結果へ置き換えていません。

原PCのWindowsサービス監査、Office／スタートアップ調査、無関係なユーザーファイル、認証設定は対象外です。モデル重み、推論ランタイム、DLL、Python／Nodeの依存バイナリは含めていません。`bin/.../runtime-manifest.json` は実行ファイルではなく、使用版を特定するための記録です。

## 公開コピーで行った変更

- Windowsユーザー名、組織名を含むOneDriveパス、PCホスト名を匿名化。
- installation情報は測定の理解に必要なキーだけを残し、個人用ショートカット等を除外。
- モデル由来のチャットテンプレート本文とJinjaファイルはモデル資産として除外し、SHA256と入手元リビジョンを保持。
- ソースZIPの内部も同じ方針で検査・再梱包。モデル／ランタイム本体やキャッシュを除外。
- 原PCの測定ファイルは変更せず、変更前後のハッシュを別々に記録。JSON等の体裁も公開コピーで正規化しています。

判断の根拠は `publication/export-manifest.json`、個人パス・認証情報のパターン検査は `publication/privacy-scan.json`、スコアの照合は `publication/validation.json` にあります。個人の識別文字列自体は検査報告へ書き出していません。

## ライセンス

独自に作成したコードとドキュメントは、所有者の指定によりMITライセンスとしました。第三者由来のコード・データ・モデル出力の権利まで一括で置き換えるものではありません。第三者分は `third_party/` の原ライセンスを維持します。

## 新しいリポジトリへ置く

1. このフォルダーの内容を新しいリポジトリにコミットします。ZIPそのものを置くより、展開したファイルを置くと差分や生データを確認しやすくなります。
2. リポジトリ直下のREADMEと `index.html` が入口です。モデルやランタイムを後から追加しないよう、`.gitignore` を含めます。
3. GitHub Pagesで表示する場合は、公開リポジトリのSettings → Pagesから使用ブランチのrootを配信元に指定します。アプリのビルドや外部APIキーは不要です。
4. 後でREADME等を変更したら `python -B tools/make_checksums.py` で公開ファイルのチェックサムを更新します。過去の原測定のハッシュを現在の値へ書き換える操作とは異なります。

継続する実験の追加・検証・Gitへの反映は [WORKFLOW.md](WORKFLOW.md) を参照してください。

## Hermesの追加記録

Hermesとの接続・実ツール使用・MCP通信も実験範囲に含め、131ファイルを追加しました。`publication/hermes-export-manifest.json` に原本/公開コピーのハッシュを記録しています。Codex設定のバックアップ、config.yaml、全体のstate.dbは含めていません。過去6件の実験を共通の `runs/` に登録し、証拠ファイルへのハッシュ付き参照を保存しました。公開後の標準配置は `integrations/hermes/` と [WORKFLOW.md](WORKFLOW.md) を参照してください。
