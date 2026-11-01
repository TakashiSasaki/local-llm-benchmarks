# 実験期ごとの記録

| 期 | 状態 | 固定した記録 | Gitタグ |
| --- | --- | --- | --- |
| period-001 | 2026-11-01終了 | [再現手順・環境・全結果](period-001/README.md) / [比較ページ](period-001/report.html) | `period-001-2026-11-01` |

`period-001/`は今回までの閉鎖記録です。`recipe/`に当時の維持管理コード・設定・手順を保存し、`models/`に固定revisionとSHA-256を持つ入手用manifestをまとめています。モデルウェイトとランタイムバイナリは含みません。

原応答・run内ソース・ログは元の`runs/<run-id>/`と`artifacts/`を保持し、[run索引](period-001/runs.json)と[inventory](period-001/inventory.json)から所属とバイト単位の同一性を確認します。既存runを書き換えて期を付与したり移動したりせず、参照関係も維持します。

次期の新しい定義・環境・レポートは`experiments/period-002/{configs,environment,reports}/`に置き、実行データは共通の`runs/period-002-<新しいID>/`へ保存します。次期はまだ開いていません。

```powershell
python -B scripts/start_period.py --id period-002 --title "第2期: 新しい実験"
python -B scripts/new_run.py --period period-002 --id period-002-example --name "Example" --benchmark bfcl --config experiments/period-002/configs/example.json
```

同じ設定を再現する場合も新期・新IDにし、前期との共通点と変更点を新期のREADMEに記録します。前期の得点を新しい推論としてコピーしません。既存結果を引用する場合は元の期・runを参照し、新規回答数と分けます。現在の`reports/comprehensive/`とその集計器は第1期専用です。

新期を開く前に、OS・GPUドライバー・ランタイム・モデルhash・Python・採点器・データ集合・sampler・seed・思考制御・MTP・配置・KV・出力上限・API timeout・メモリ保護・負荷/電源条件を比較します。設定が同じでも速度や生成文字列の完全一致は保証しません。
