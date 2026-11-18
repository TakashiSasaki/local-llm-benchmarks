# LFM3-1.7B Text Q8_0のHumanEval+（2026年11月17日）

TUFA15でLFM3-1.7B Text Q8_0の全164問を各1回生成した。QAD-Q4_0版の保存済み結果と照合し、送信内容とサーバーが返した実効生成設定が全問で一致した。両版ともllama.cpp b11960 CUDA 12.4、全層GPU指定、コンテキスト65,536、最大出力16,384、seed 42のコード補完方式。繰り返しペナルティ1.1をQ8_0で明示した。採点は両版ともオフラインのDebian 12 VM上のEvalPlus v0.3.1、HumanEval+ v0.1.10。欠測・除外は0件。

| LFM3-1.7B Text | HumanEval基本 | HumanEval+ | API応答時間中央値 | 164問のAPI応答時間合計 |
| --- | ---: | ---: | ---: | ---: |
| QAD-Q4_0 | 50/164（30.49%） | 48/164（29.27%） | 0.58秒 | 6分47秒 |
| Q8_0 | 55/164（33.54%） | 52/164（31.71%） | 0.86秒 | 14分25秒 |

HumanEval+ではQ8_0だけが合格した問題が22問、QAD-Q4_0だけが合格した問題が18問あり、Q8_0が正味4問（2.44ポイント）上だった。Q8_0では基本テスト合格55問のうち、追加テストで3問が不合格。出力上限到達は0件。最長だったHumanEval/93は15,828トークンを生成し、154.84秒で応答した。[設問別結果](../../runs/period-004-lfm3-1p7b-q8-humaneval-plus-20261117/summaries/per-task.json)

API応答時間の合計は起動・採点を除いたクライアント計測。生成速度の中央値はQ8_0が108.35 tokens/s、QAD-Q4_0が167.55 tokens/s。専用VRAMのピークはシステム全体のサンプル値で、Q8_0が2,825 MiB、QAD-Q4_0が2,065 MiB。

[生成設定・生データ](../../runs/period-004-lfm3-1p7b-q8-humaneval-20261117/manifest.json) · [採点・比較集計](../../runs/period-004-lfm3-1p7b-q8-humaneval-plus-20261117/summary.json) · [QAD-Q4_0の評価報告](LFM3_HUMANEVAL_PLUS_20261117.md)
