# Empero Qwen3.8-35B-A3B-Distill IQ3_Mの測定

2026-10-31に新規200回答とHermesの実ツール往復を測定しました。[10構成・40条件・2,000回答の比較ページ](../reports/20261031-empero-qwen38-iq3m-64k/index.html)、[測定結果](../runs/20261031-empero-qwen38-iq3m-64k/summary.json)、[独立照合の結果](../runs/20261031-empero-qwen38-iq3m-64k/summaries/independent-verification.json)を保存しています。

## 主集計

| モデル・量子化 | HumanEval OFF /20 | ON /20 | BFCL OFF /80 | ON /80 |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.6-35B-A3B UD-Q3_K_M | 17 | 20 | 72 | 72 |
| Qwen3.6-35B-A3B IQ3_M | 19 | 19 | 74 | 72 |
| Empero Qwen3.8-35B-A3B-Distill IQ3_M | 18 | 20 | 72 | 72 |

全200回答で出力打ち切り0件でした。思考OFFはHumanEval/BFCLとも実際のreasoning出力0件、ONはそれぞれ20/20件・80/80件で観測しました。最初の[短いモード確認](../runs/20261031-empero-qwen38-iq3m-64k/configs/native-mode-checks.json)も保存しています。OFF/ONはネイティブの `enable_thinking` で切り替え、OFFだけCLIで思考を強制終了する方式は使っていません。

BFCLは全80問では72/80でした。ONのカテゴリー別は単一呼び出し20/20、候補選択18/20、並列呼び出し17/20、呼び出し抑制17/20です。OFFからONで改善した3問は `simple_python_216`、`simple_python_379`、`multiple_22`、悪化した3問は `multiple_26`、`parallel_173`、`irrelevance_188` でした。BFCLでは実際の外部関数は実行しません。

## 時間と出力量

| 条件 | Empero版の応答中央値 | Empero版の合計 | Qwen3.6 IQ3_Mの合計 |
| --- | ---: | ---: | ---: |
| HumanEval OFF | 5.07秒 | 109.72秒 | 159.49秒 |
| HumanEval ON | 10.97秒 | 327.36秒（5.46分） | 1,284.29秒（21.40分） |
| BFCL OFF | 3.58秒 | 367.38秒 | 367.48秒 |
| BFCL ON | 5.73秒 | 606.22秒（10.10分） | 1,377.03秒（22.95分） |

Empero版の合計デコード速度は各条件で約40.3〜40.6 tokens/sでした。Qwen3.6 IQ3_Mの約39.3〜39.5 tokens/sとの違いより、**生成したトークン数の違い**が大きく効いています。Empero版のHumanEval ONは全20問合計12,367出力トークン、BFCL ONは全80問合計19,778出力トークンでした。モデルの短い思考・回答による短縮と、計算カーネル自体の速度を区別してください。

## 採点器による影響

今回のHumanEval OFFで失敗したのはHumanEval/108（IndexError）とHumanEval/163（AssertionError）でした。従来の補助採点ポリシー（`type` と `operator.mul/add` を追加、Windowsの実行制限は維持）でもOFF18/20・ON20/20で、救済された問題はありませんでした。[補助採点の全記録](../runs/20261031-empero-qwen38-iq3m-64k-he-policy-audit/summaries/results.json)は新規推論と区別して `kind: replay` で保存しています。

比較表のQwen3.6 IQ3_M ON19/20には、従来の採点器が `type()` を許可しないことによる失点があります。補助採点では同条件も20/20です。主集計と補助採点を混ぜず、20問の単発試験だけで一般的な能力差とは断定しません。

## Hermesの実動作

Hermes v0.22.5 / bf0203a794a07aac3ff764972ab9087baa4e4f4eで、**read_file → terminalのecho → write_file** を実行しました。対象セッションのローカルendpointとモデル、読み取った新しいticket、実コマンドの終了コードと出力、書き込みのverified、生成JSONのticket/count/total/terminal_marker、入力ファイルのSHA256がすべて一致しました。

全チェック成功、約51.29秒でした。[Hermes検証ページ](../reports/20261031-empero-qwen38-iq3m-64k-hermes/index.html)と[対象セッションの実ツール結果](../runs/20261031-empero-qwen38-iq3m-64k-hermes/raw/session-tools.json)を参照できます。短い会話1件の検証であり、長いエージェント履歴・全機能・反復時の成功率を測ったものではありません。

## 条件・リソース

- 同じWindows PC、RTX 4070 Laptop GPU 8 GiB、Ryzen 9 7940HS、RAM32 GiB。
- llama.cpp b11960 / 8642541b2 / CUDA12.4。関連19ファイルのハッシュも照合。
- 1スロット、コンテキスト65,536、出力上限最大64,000、F16 KV、先頭30 MoE層のexpertをCPU配置、8スレッド。
- HumanEvalは従来の固定20問、温度0.6、Python3.14.9の同じ制限付き採点器。BFCLは同じ固定80問・公式AST採点器・温度0。seed42。
- 全試験中のサンプル最小空きRAM5.51 GiB、システム全体GPU使用量最大6,391 MiB、GPU温度最大65°C。監視による中断・OOMはありませんでした。値はサンプルであり、常に確保できる余裕や瞬間ピークの保証ではありません。
- 測定用サーバーと試験で起動したgatewayは終了し、Hermes設定と既存daily/largeプロファイルのハッシュは変更前と一致しました。

プロファイルは [configs/qwen38-35b-distill-iq3m-64k.json](../configs/qwen38-35b-distill-iq3m-64k.json) にあります。64Kは設定容量であり、HumanEval/BFCLの入力を64K近くまで埋めた試験ではありません。各条件1回答で、背景負荷・温度・実行順序は完全には制御していません。

## モデルの識別と再現

配布元は [empero-ai/Qwen3.8-35B-A3B-Distill-GGUF](https://huggingface.co/empero-ai/Qwen3.8-35B-A3B-Distill-GGUF/tree/b1f9d1dcc3de8aa867669b0ab919384aeeb9b8d5)、ファイルは `Qwen3.8-35B-A3B-IQ3_M.gguf`、16,339,529,600 bytes、SHA256 `0ad7b253ecee6de7b38ecaf82ea5553d302c3f924961b7091b7088cc99a30f95` です。重みと実行環境はリポジトリ外です。[固定したmodel manifest](../configs/models/qwen38-35b-distill-iq3-m.json)を保存しています。

開発者はQwen3.6-35B-A3Bを土台にしたQwen3.8教師トレースの蒸留/SFTと説明しています。Qwen公式の3.8世代35Bとは区別しています。[開発者のモデルカード](https://huggingface.co/empero-ai/Qwen3.8-35B-A3B-Distill)は長い思考でサンプリングを勧めていますが、今回のBFCLは既存モデルとの比較のため温度0を維持しました。推奨サンプリングの最適化試験ではありません。

再現の基準は実際にダウンロードしたGGUFの固定リビジョンとSHA256です。metadataの `observed_upstream_revision` は調査時に観測した上流のheadであり、量子化配布者が使用した元の学習・変換コミットを独立に確認した値ではありません。

```powershell
python -B tools/verify_quantization_study.py --study 20261031-empero-qwen38-iq3m-64k
python -B scripts/report_model_study.py --study 20261031-empero-qwen38-iq3m-64k
python -B scripts/refresh_reports.py
```

照合は160件の保存済みBFCLを再採点し、40件のHumanEval採点記録とHermesの実行記録・生成物を確認します。新規にモデルをロードする処理ではありません。実測をやり直す際は、新しいrun IDを `scripts/run_quantization_study.py` に渡し、今回のmodel manifest・profile・手元のHermes installation情報を指定します。
