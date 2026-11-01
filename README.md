# Local LLM benchmarks on an 8 GB laptop GPU

**[全測定の横断比較](reports/comprehensive/index.html)** · [全30行の比較表](reports/comprehensive/summary.md) · [条件別CSV](reports/comprehensive/conditions.csv) · [読み方](docs/COMPREHENSIVE_COMPARISON.md)。16モデル・量子化ペア、MTPを含む21組み合わせを、配置・再測定を区別した30行に集約。能力条件94件完了、保存応答4,776件で、未完了・未測定と旧条件も確認できます。

[Mage Q4/Q3・MTP非対応・GPU配置の結果](reports/20261031-mage-text-64k/index.html)（能力試験は途中終了、Q3のBFCL160件は完了） · [Q5とMTPの追加比較](docs/Q5_MTP.md)（新規1,200回答＋既存400回答参照）。失敗・未実施条件も保存しています。

RTX 4070 Laptop GPU（8 GB VRAM）・Ryzen 9 7940HS・RAM 32 GiB の Windows PC で行ったローカルLLM比較の測定記録です。2026-10-30の最終比較では、8構成 × HumanEval / BFCL × 思考OFF / ON の **32条件・1,600回答**をまとめています。

**[10構成比較](reports/20261031-empero-qwen38-iq3m-64k/index.html)** · **[IQ3_M追加後の9構成比較](reports/20261030-qwen36-iq3m-64k/index.html)** · **[測定一覧](index.html)** · **[2026-10-30の比較ダッシュボード](reports/2026-10-30-matrix/index.html)** · [集計CSV](artifacts/local-llm/runs/benchmark-matrix-20261030-194424/conditions.csv) · [出力打ち切り一覧](artifacts/local-llm/runs/benchmark-matrix-20261030-194424/truncations.csv)

This repository preserves a local Windows/CUDA benchmark study: scripts, pinned test data, raw model responses, graders, measurements, Hermes integration checks, historical runs and offline reports. Model weights and inference runtime binaries are deliberately not included. These are small, fixed subsets, not full official leaderboard scores.

[Empero 3bit / 4bit × MTPの比較](docs/EMPERO_MTP.md) · [得点・速度の集計表](reports/20261031-empero-mtp-load-none/summary.md) · [表示ページ](reports/20261031-empero-mtp-load-none/index.html)には、量子化・MTP・思考設定を分けた追加測定をまとめています。先の10構成比較とはCPU配置が異なるため、今回新しく取得した対照同士で速度を比較します。

[Qwen3.6 Q4_K_M × MTPの追加比較](docs/QWEN36_Q4_MTP.md) · [集計表](reports/20261031-qwen36-q4-mtp-64k/summary.md) · [表示ページ](reports/20261031-qwen36-q4-mtp-64k/index.html)も同じ64K・CPU MoE34層で測定しました。新規400回答と先行Emperoの参照結果を区別して保存しています。

[外部利用者のBFCL測定との比較（2026-10-31）](docs/EXTERNAL_BENCHMARKS_20261031.md)には、Empero版・Qwen3.6の公表値と、問題数・採点・思考設定の違いをまとめています。外部値はローカルのマトリックスとは別に扱います。

## Qwen3.6 Q4_K_MとMTP（2026-10-31）

BartowskiのQ4_K_Mを、以前のIQ3_Mと同じ配布revisionから取得し、64K・CPU MoE34層・load-mode noneで新規400回答を測定しました。

| MTP | BFCL 思考OFF /80 | ON /80 | HumanEval 思考OFF /20 | ON /20 | 固定長生成 tok/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| OFF | 75 | 73 | 18 | 19 | 36.64 |
| ON | 74 | 73 | 18 | 19 | 47.38 |

固定長生成はMTPで約29%速くなり、BFCL合計も思考OFF約23%・ON約26%短縮しました。400回答で打ち切りと、最終回答・ツール呼び出しが両方空の応答は0件です。HumanEval ONは既知の`type()`制限で両方19/20、別の補助採点では両方20/20でした。[時間・メモリ・問題別変化・比較条件](docs/QWEN36_Q4_MTP.md)を記録しています。以前のIQ3_MはCPU MoE30層なので、今回のMTPの速度対照には流用していません。

## Empero 3bit / 4bitとMTP（2026-10-31）

同じ64K・CPU MoE 34層で、量子化ごとにMTP OFF/ONを比較しました。速度は思考OFF・固定256トークンの9試行の中央値です。

| 量子化 | MTP | 生成速度 tok/s | BFCL 思考OFF /80 | 思考ON /80 |
| --- | --- | ---: | ---: | ---: |
| IQ3_M | OFF | 33.73 | 70 | 72 |
| IQ3_M | ON | 39.07 | 72 | 73 |
| Q4_K_M | OFF | 38.20 | 71 | 72 |
| Q4_K_M | ON | 46.47 | 71 | 71 |

固定長生成はMTPで3bit約16%、4bit約22%速くなりました。ただし4bit・MTP ON・思考ONのBFCL1問は64,000出力トークンで打ち切られ、最終回答が空でした。そのためBFCL ONの80問合計は約656秒から1,583秒へ増えました。**採点上は呼び出し0件で正解ですが、回答は未完了です。** 4bitは初回のRAM保護停止を受け、OFF/ONを両方 `--load-mode none` に揃えて再測定しています。[全条件・HumanEval・問題別変化](docs/EMPERO_MTP.md)を参照してください。

以前のCPU MoE 30層での3bit速度も別に測り、40.48→43.74 tok/s（約8%向上）でした。HumanEval思考ONの4bit主採点はMTP OFF19/20・ON17/20、既知の`type()`制限を補う別採点では20/20・19/20です。主比較800回答、補足速度18試行と補助採点を完了しています。

## Empero Qwen3.8 Distillの追加測定（2026-10-31）

コミュニティの `empero-ai/Qwen3.8-35B-A3B-Distill` IQ3_Mを、同じ64K設定・問題・主採点基準で追加測定しました。比較は**10構成・40条件・2,000回答**です。

| モデル・量子化 | HumanEval OFF /20 | ON /20 | BFCL OFF /80 | ON /80 |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.6 UD-Q3_K_M | 17 | 20 | 72 | 72 |
| Qwen3.6 IQ3_M | 19 | 19 | 74 | 72 |
| Empero Qwen3.8 Distill IQ3_M | 18 | 20 | 72 | 72 |

Empero版は全200回答で打ち切り0件、Hermes実ツール往復も成功（約51秒）。ONの合計はHumanEval約5.5分、BFCL約10.1分で、Qwen3.6 IQ3_Mの約21.4分・23.0分より短い結果でした。今回の補助採点でも18/20・20/20で変わりません。[測定条件・時間・生成量・比較の範囲](docs/EMPERO_QWEN38.md)を参照してください。

## IQ3_Mの追加測定（2026-10-31）

Qwen3.6-35B-A3BのBartowski IQ3_Mを、同じ64K設定で新規200回答とHermes実ツール往復に追加しました。比較は**9構成・36条件・1,800回答**になりました。

| 量子化 | HumanEval OFF /20 | ON /20 | BFCL OFF /80 | ON /80 |
| --- | ---: | ---: | ---: | ---: |
| UD-Q3_K_M（既存） | 17 | 20 | 72 | 72 |
| IQ3_M（追加） | 19 | 19 | 74 | 72 |

IQ3_Mは打ち切り0件。BFCL ONの合計は約23分（既存84.5分）でした。Hermesの実read_file・terminal・write_file検証も成功しています。HumanEval ONの1件は採点器が `type()` を許可しないため失敗し、同じ補助採点ポリシーでは20/20です。主集計は変更せず、[条件・速度・補助採点と比較の限界](docs/IQ3_M.md)を記録しています。

## 2026-10-30の8構成比較

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

[将来試したいモデル](docs/FUTURE_MODELS.md)には、より強力なマシンを入手したら試す候補と、現在の環境で見送った理由を記録しています。

[小型abliteratedモデルの調査](docs/ABLITERATION_RESEARCH.md)には、このPC向けの候補、一般能力への影響に関する一次資料、通常版との比較計画をまとめています。追加モデルの実測結果とは区別しています。

[Mage-VL-Cowork Q4_K_Mのテキスト測定](docs/MAGE_VL_COWORK.md)は、画像入力を使わず、既存のHumanEval/BFCLと同じ64Kプロトコルで行う別試験です。公式の32K運用設定・GUI実行評価とは区別し、実際の収集状態はrunに記録します。

Gitルートは `C:\LocalLLM\local-llm-benchmarks` です。モデル単体の測定コードは `benchmarks/`、Hermes等の接続・実ツール動作検証は `integrations/<harness>/`、共通処理は `src/`、共有入力は `datasets/`、すべての実行結果は `runs/<run-id>/`、表示ページは `reports/` に置きます。作成・再開・コミット・プッシュの手順は[WORKFLOW.md](docs/WORKFLOW.md)にまとめています。過去の `artifacts/` は凍結した証拠として残します。

Hermesのネイティブ起動・接続、4B/35Bの実ツール往復、JSON/CSV/修正課題、64K容量と短いHermes会話、MCP接続を含む**過去6件の検証**も収録しています。MCPのアプリ側接続失敗や、初回課題の失敗も残しています。構成と手順は [Hermes検証](integrations/hermes/README.md) を参照してください。これらは当時のb11946等の記録で、最終b11960マトリックス全モデルのHermes対応を証明するものではありません。

## 収録内容

```text
index.html                         継続的に追加する測定の一覧
benchmarks/                        モデル単体の測定コード
integrations/hermes/scripts/        Hermesの接続・実ツール検証コード
integrations/hermes/fixtures/       Hermes用の合成テスト定義
configs/hermes/                    公開できるHermesの試験条件
src/                               共通処理
scripts/                           実行管理・公開の補助
datasets/                          共有のバージョン固定データ
configs/                           公開する測定条件
runs/<run-id>/                     全実験共通: 条件・生応答・実ツール結果・生成物・集計・ソース
reports/                           一覧と各実験の表示ページ
artifacts/local-llm/scripts/        測定・補助・採点・監査・描画スクリプト
artifacts/local-llm/runs/           新旧の測定結果、生応答、メモリ観測、ソースZIP
artifacts/local-llm/hermes/runs/     過去のHermes/MCP検証の実行記録
artifacts/local-llm/workspace/hermes/ テスト入力と実際の生成物
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
python -B integrations/hermes/scripts/verify_saved_evidence.py
python -B tools/verify_quantization_study.py --study 20261030-qwen36-iq3m-64k
python -B tools/verify_quantization_study.py --study 20261031-empero-qwen38-iq3m-64k
python -B tools/verify_mtp_study.py
python -B tools/verify_mtp_study.py --prefix 20261031-qwen36-q4-mtp-64k
python -B tools/make_checksums.py --check
```

1つ目は公開コピーとZIP内ファイルのハッシュ、公式データのハッシュ、32条件の整合性を確認し、**BFCLの1,280回答を固定版公式AST採点器で再採点**します。HumanEvalは320件の保存済み採点記録を照合しますが、生成コードの再実行はしません。公開準備時の結果は [publication/validation.json](publication/validation.json) にあります。Hermes用の照合は、追加131ファイル・6実験・4件の基本ファイル往復の保存記録を確認します。[照合結果](publication/hermes-validation.json)も保存しています。

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
