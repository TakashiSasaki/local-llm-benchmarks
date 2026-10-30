# Qwen3.6-35B-A3B IQ3_M追加測定

2026-10-30夜から31日未明にかけて、このPCで新規に200回答を取得し、Hermesの実ツール往復を1件検証しました。[9構成・36条件の比較ページ](../reports/20261030-qwen36-iq3m-64k/index.html)と[実行結果](../runs/20261030-qwen36-iq3m-64k/summary.json)を参照できます。

## 主集計

| 量子化 | HumanEval OFF /20 | ON /20 | BFCL OFF /80 | ON /80 |
| --- | ---: | ---: | ---: | ---: |
| 既存Unsloth UD-Q3_K_M | 17 | 20 | 72 | 72 |
| Bartowski IQ3_M | 19 | 19 | 74 | 72 |

IQ3_Mの新規4条件は全てコンテキスト65,536、出力上限最大64,000、1スロット、b11960 / 8642541b2 / CUDA 12.4、F16 KV、先頭30 MoE層のexpertをCPU配置、8スレッドです。モデルのSHA256と、ランタイム関連19ファイルのSHA256を照合しました。HumanEvalは従来と同じ20問・温度0.6・Python 3.14.9の制限付き採点器、BFCLは同じ80問・温度0です。

IQ3_Mは全200回答で出力打ち切り0件。HumanEval ONは20/20件、BFCL ONは80/80件で実際のreasoning出力を観測し、OFFは両方0件でした。BFCLのスコアはツール名・引数・呼び出し抑制の採点で、外部関数を実行した成功率ではありません。

## 採点器の制限による差

IQ3_M ONのHumanEval/22は `return [x for x in values if type(x) is int]` を生成しました。主採点器は `type()` を許可しておらず、`NameError` で失敗しました。主集計の19/20は変更していません。

従来の6モデル比較でも使った同一の補助ポリシー（`type` と `operator.mul/add` を追加）で保存済みの失敗を再採点した結果です。新規推論ではありません。

| 量子化 | 主集計 OFF / ON | 補助採点 OFF / ON |
| --- | --- | --- |
| UD-Q3_K_M | 17 / 20 | 18 / 20 |
| IQ3_M | 19 / 19 | 19 / 20 |

[補助採点の条件・固定workerハッシュ・全記録](../runs/20261030-qwen36-iq3m-64k-he-policy-audit/summaries/results.json)を保存しています。IQ3_M OFFのHumanEval/62は補助採点でも失敗し、アルゴリズム上の境界条件の誤りが残りました。

## 応答時間

| 条件 | UD-Q3_K_M 応答中央値 | IQ3_M 応答中央値 | UD 合計 | IQ3_M 合計 |
| --- | ---: | ---: | ---: | ---: |
| HumanEval OFF | 5.64秒 | 5.77秒 | 134秒 | 159秒 |
| HumanEval ON | 53.69秒 | 60.75秒 | 1,163秒 | 1,284秒 |
| BFCL OFF | 3.19秒 | 3.39秒 | 360秒 | 367秒 |
| BFCL ON | 16.61秒 | 14.90秒 | 5,072秒（84.5分） | 1,377秒（23.0分） |

BFCL ON合計の大きな差には、従来の2件の64,000トークン打ち切りが今回なかったことが効いています。単純にデコード性能が数倍になったという結果ではありません。IQ3_Mの合計デコード速度は4条件とも約39.3〜39.5 tokens/sでした。

従来打ち切りになった問題のIQ3_Mでの結果:

- `simple_python_377`: 正解、219出力トークン、6.76秒、実際に解析された呼び出し1件。
- `irrelevance_8`: 正解、909出力トークン、24.18秒、呼び出し0件、最終回答398文字まで完了。

## Hermesでの実動作

Hermes v0.22.5 / bf0203a794a07aac3ff764972ab9087baa4e4f4eで、`read_file → terminal（echo）→ write_file` を実行し、次を独立に確認しました。

- 新しいticketを実際のread_file結果に確認。
- terminalの実出力と終了コード0を確認。
- write_fileの `verified=true` と、実際に生成されたticket/count/total/terminal_markerのJSONを照合。
- 入力ファイルのSHA256、対象セッションのモデルとローカルendpointを確認。

全チェック成功、約66.35秒でした。[Hermesの記録・入力・生成物](../reports/20261030-qwen36-iq3m-64k-hermes/index.html)と[対象セッションの実ツール結果](../runs/20261030-qwen36-iq3m-64k-hermes/raw/session-tools.json)を保存しています。短い会話1件の検証であり、長いHermes履歴や全機能の信頼性を測ったものではありません。Hermesの累積入力トークン数は、単一時点のコンテキスト使用量として扱いません。

全試験中のサンプル最小空きRAMは4.15 GiB、システム全体のGPU使用量最大は7,133 MiB。監視による中断・OOMはありませんでした。測定用サーバーと試験で起動したgatewayは終了し、Hermes設定と既存daily/largeプロファイルのハッシュは変更前と一致しました。

## 配布ファイルと比較の範囲

配布元は [bartowski/Qwen_Qwen3.6-35B-A3B-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3.6-35B-A3B-GGUF/tree/5c2410d71524f4f72b023ce8daf7a80528226d5f)。固定リビジョン、17,791,661,696 bytes、SHA256 `aedaa7010e09065d3a4129a624e45804ccfa1950838e67ee935b87d1e71a3d1f`。識別情報は [model manifest](../configs/models/qwen36-35b-iq3-m.json) にあります。重みはリポジトリ外の `C:\LocalLLM\models` に置いています。

これは配布されている量子化モデル同士の比較です。配布元、テンソルごとの精度、較正、テンプレートも異なり得るため、ビット数だけの効果を分離した実験ではありません。IQ3_MにはMTP用の追加レイヤ情報があり、b11960の今回の通常推論では該当する未使用テンソルを無視したログが残っています。MTPによる高速化の試験ではありません。

問題は固定した小さな部分集合、各条件1回答です。HumanEvalの旧測定は問題ごとにOFF/ONを交互実行し、今回はモード単位で実行しています。背景負荷・温度・実行順序も速度差に寄与します。64Kは設定容量であり、これらの問題の入力を64K近くまで埋めた試験ではありません。

公開時はHermesの2ファイルに含まれたWindowsユーザーパスを匿名化しました。元のバイト列はGit管理外の `.local/original-evidence/` に保存し、[変更前後のハッシュ](../publication/20261030-qwen36-iq3m-64k-redactions.json)を記録しています。
