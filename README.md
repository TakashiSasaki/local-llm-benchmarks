# Local LLM benchmarks on an 8 GB laptop GPU

RTX 4070 Laptop GPU（8 GB VRAM）・Ryzen 9 7940HS・RAM 32 GiB の Windows PC で行ったローカルLLM比較の測定記録です。2026-10-30の最終比較では、8構成 × HumanEval / BFCL × 思考OFF / ON の **32条件・1,600回答**をまとめています。

**[測定一覧](index.html)** · **[2026-10-30の比較ダッシュボード](reports/2026-10-30-matrix/index.html)** · [集計CSV](artifacts/local-llm/runs/benchmark-matrix-20261030-194424/conditions.csv) · [出力打ち切り一覧](artifacts/local-llm/runs/benchmark-matrix-20261030-194424/truncations.csv)

This repository preserves a local Windows/CUDA benchmark study: scripts, pinned test data, raw model responses, graders, measurements, historical runs and an offline dashboard. Model weights and inference runtime binaries are deliberately not included. These are small, fixed subsets, not full official leaderboard scores.

## 最終結果

| モデル / 量子化 | HumanEval OFF /20 | ON /20 | BFCL OFF /80 | ON /80 |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.6-35B-A3B UD-Q3_K_M | 17 | 20 | 72 | 72 |
| Qwen3.5-4B Q4_K_M | 14 | 13 | 72 | 68 |
| LFM3 Text QAD-Q4_0 | 15 | 19 | 70 | 73 |
| LFM3 Text Q8_0 | 17 | 17 | 69 | 73 |
| LFM3 VL QAD-Q4_0 | 11 | 16 | 59 | 56 |
| LFM3 VL Q8_0 | 9 | 16 | 57 | 63 |
| LFM2.5-24B-A2B QAD-Q4_0 | 11 | 19 | 63 | 60 |
| GLM-4.7-Flash Q4_K_M | 12 | 19 | 70 | 72 |

最終比較は llama.cpp **b11960 / 8642541b2 / CUDA 12.4**、コンテキスト65,536、出力上限最大64,000、1スロット、F16 KVで測定しました。既存960回答に、未測定だったBFCL思考ONの640回答を追加しています。以前のb11946、出力1K/4K、動作確認・VL画像試験の記録も別フォルダーに残しています。

Qwen 35BのBFCLではOFF/ONとも72/80でしたが、ONの応答中央値は16.6秒（OFF 3.2秒）、80問合計は84.5分（OFF 6.0分）でした。ONの2問は64,000出力トークンで打ち切られました。そのうち1問は呼び出し0件なのでBFCL上は正解ですが、最終回答は空です。**採点上の正解・回答の完了・実際のツール実行を区別してください。**

## 今後の測定

Gitルートは `C:\LocalLLM\local-llm-benchmarks` です。編集する測定コードは `benchmarks/`、共通処理は `src/`、共有入力は `datasets/`、新しい実行結果は `runs/<run-id>/`、表示ページは `reports/` に置きます。作成・再開・コミット・プッシュの手順は[WORKFLOW.md](docs/WORKFLOW.md)にまとめています。過去の `artifacts/` は凍結した証拠として残します。

## 収録内容

```text
index.html                         継続的に追加する測定の一覧
benchmarks/                        今後編集・追加する測定コード
src/                               共通処理
scripts/                           実行管理・公開の補助
datasets/                          共有のバージョン固定データ
configs/                           公開する測定条件
runs/<run-id>/                     新しい実験ごとの条件・生応答・集計・ソース
reports/                           一覧と各実験の表示ページ
artifacts/local-llm/scripts/        測定・補助・採点・監査・描画スクリプト
artifacts/local-llm/runs/           新旧の測定結果、生応答、メモリ観測、ソースZIP
artifacts/local-llm/hermes/benchmarks/
                                   旧Qwen比較、HumanEval、固定版BFCLデータ・採点器
artifacts/local-llm/profiles/       実際の起動設定
artifacts/local-llm/hermes/profiles/ Hermes側の起動設定
data/dataset-manifest.json         データセットの出典・コミット・ハッシュ
docs/                             再現手順、公開時の変更点、測定メモ
third_party/                       第三者コンポーネントの出典とライセンス
publication/                       コピー前後のハッシュ、除外記録、検証結果
tools/                             モデルなしで行える照合用スクリプト
SHA256SUMS                         公開ファイルのチェックサム
```

実行ファイル・DLL・モデル重み・プロジェクター・Pythonキャッシュ・認証設定は含みません。モデル由来のチャットテンプレート本文もモデル資産として除き、ハッシュと使用モデルの正確なリビジョンを残しました。Windowsのユーザー名・組織名を含むパスは公開コピーで匿名化しています。**元のPC上の測定記録は変更していません。**

## モデルなしで照合する

Python 3.12以降の標準ライブラリだけで実行できます。ネットワークアクセス、モデル推論、生成されたPythonコードの実行は行いません。

```sh
python -B tools/verify_publication.py
python -B tools/make_checksums.py --check
```

1つ目は公開コピーとZIP内ファイルのハッシュ、公式データのハッシュ、32条件の整合性を確認し、**BFCLの1,280回答を固定版公式AST採点器で再採点**します。HumanEvalは320件の保存済み採点記録を照合しますが、生成コードの再実行はしません。公開準備時の結果は [publication/validation.json](publication/validation.json) にあります。

測定一覧は `index.html`、最終比較は `reports/2026-10-30-matrix/index.html` をブラウザーで開くだけで動きます。HTTPで確認する場合はこのフォルダーで次を実行し、`http://127.0.0.1:8000/` を開きます。

```sh
python -m http.server 8000 --bind 127.0.0.1
```

## 推論を再測定する場合

[再現手順と環境依存の説明](docs/REPRODUCIBILITY.md) を先に読んでください。保存した原測定スクリプトは当時のWindows配置 `C:\LocalLLM` やHermesのインストール情報に依存します。別PCでそのまま動く汎用パッケージに変更したものではありません。モデル・ランタイムを別途取得し、パス・起動設定を確認して使います。

## 読み方と限界

- HumanEvalは公式164問から固定した20問、温度0.6。従来と同じ制限付きWindows採点環境を使っています。BFCLはv4の4カテゴリー各20問、計80問、温度0。各条件1回答です。
- BFCLは解析されたツール名・引数・不要時の呼び出し抑制を採点します。外部の関数は実行しておらず、一般回答の正しさや完了も採点しません。
- LFM2.5のテンプレートは `enable_thinking` を無視するため、OFFはCLI思考予算0、ONは-1です。他のモデルはネイティブのOFF/ONを使っています。
- 64Kは設定した容量です。最終比較の入力は短い原問題のままで、64K近い履歴を埋めた品質試験ではありません。VLもこの表では画像を入れていません。
- CPU/GPU配置、トークナイザー、出力量、測定時刻・温度・背景負荷が異なります。結果はこのPCの構成での測定であり、パラメータ数・量子化ビット数・画像対応だけの効果を分離した研究ではありません。

## 出典とライセンス

HumanEvalは [OpenAIのMITライセンス](https://github.com/openai/human-eval/blob/b9453e8f1865df0a0057a1383767caa400acfbcf/LICENSE)、BFCLの使用版は [GorillaのApache 2.0ライセンス](https://github.com/ShishirPatil/gorilla/blob/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/LICENSE) に従います。本文と出典は [第三者コンポーネント一覧](third_party/NOTICES.md) にあります。

独自に作成したコードとドキュメントは[MITライセンス](LICENSE)です。第三者のデータ・コード、記録したモデル出力の権利まで一括で置き換えるものではありません。詳しくは[公開準備メモ](docs/PUBLICATION.md)を参照してください。
