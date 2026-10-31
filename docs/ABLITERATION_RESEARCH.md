# 小型abliteratedモデルと一般タスクへの影響

調査日: 2026-10-31。目的は、拒否を減らす改変によって、通常のコード生成・関数呼び出し・推論の品質にも変化が出るかを調べること。この文書は配布情報・既存研究の調査と比較計画であり、追加モデルの実測結果ではない。

## このPCで検討できる候補

容量はHugging Face APIで確認した実ファイルの十進GB。RAM・VRAM使用量ではなく、64Kでの実動作を保証しない。

| 元のモデル | 改変版GGUFの配布先 | Q4_K_M容量 | 位置付け |
| --- | --- | ---: | --- |
| Qwen3.5-0.8B | [xdchinza/Qwen3.5-0.8B-abliterated-GGUF](https://huggingface.co/xdchinza/Qwen3.5-0.8B-abliterated-GGUF) | 約0.542 GB | 小型例。難しい課題の元の得点が低い場合、低下を検出しにくい |
| Qwen3.5-2B | [mradermacher/Huihui-Qwen3.5-2B-abliterated-GGUF](https://huggingface.co/mradermacher/Huihui-Qwen3.5-2B-abliterated-GGUF) | 約1.271 GB | 軽量な別手法の候補 |
| Qwen3.5-4B | [mradermacher/Qwen3.5-4B-abliterated-GGUF](https://huggingface.co/mradermacher/Qwen3.5-4B-abliterated-GGUF) | 約2.708 GB | 最初の比較候補。同じ配布元の通常版と組にできる |
| Qwen3.6-35B-A3B | [mradermacher/Qwen3.6-35B-A3B-abliterated-GGUF](https://huggingface.co/mradermacher/Qwen3.6-35B-A3B-abliterated-GGUF) | 約21.167 GB | 現行35B測定につながる候補。CPU/GPU配置、MTP重みの有無等を別途確認 |

4Bの改変元は [wangzhang/Qwen3.5-4B-abliterated](https://huggingface.co/wangzhang/Qwen3.5-4B-abliterated)、通常版の元は `Qwen/Qwen3.5-4B`。配布者はAbliterixによる変更と、評価用プロンプトでのKL divergence 0.0065を報告しているが、この値はHumanEvalやBFCLの成績維持を証明しない。

35Bの同名改変版では、[配布者の方法説明](https://huggingface.co/wangzhang/Qwen3.6-35B-A3B-abliterated#method)に専門家の出力重みの変更だけでなくrouter suppressionもある。「abliterated」というラベルだけで同じ改変だと扱わない。追加学習・蒸留などを含むuncensoredモデルも、単純な改変前後比較から分ける。

## 一般性能に影響はあるか

原理上、改変は重みや内部表現に加わるため、通常の応答にも変化し得る。元の研究 [Refusal in Language Models Is Mediated by a Single Direction](https://arxiv.org/abs/2406.11717) は他の能力への影響を抑えた介入を示したが、あらゆるモデル・手法で無影響になるという保証ではない。

[Comparative Analysis of LLM Abliteration Methods, v2](https://arxiv.org/html/2512.13655v2#S4.SS2) は、一般能力の比較を一部の7B–14Bモデルで報告している。例としてGSM8KはMistral-7Bの通常版48.52%に対しHeretic版48.37%だった一方、Yi-1.5-9Bでは70.89%から52.08%へ低下し、別手法のDECCP版は72.40%だった。

これらはモデル・改変方法への依存を示す例で、Qwen3.5/3.6やMoE、今回のHumanEval/BFCLの予測値にはできない。論文は16モデルすべてで一般能力を比較したわけではなく、元の能力スコアが揃う比較は主に3モデルである。小さい得点差には評価誤差もある。

[Hereticの公式説明](https://github.com/p-e-w/heretic) は拒否率と元モデルからのKL divergenceを同時に小さくする設計を説明している。KLは評価プロンプトや集計方法に依存する分布の指標で、コードの実行正解率や正しい引数を出せる確率の代わりにはならない。

## まず4Bで行う比較案

通常版・改変版の両方を新しく取得して同条件で測る。既存の通常版は別の配布物なので、過去の得点をそのまま改変前の唯一の対照にしない。

- 同じ配布元の通常版と改変版、同じ量子化を使用する。Q4_K_M同士のほか、量子化による影響を小さくする確認用にはQ8_0同士（各約4.48 GB）が候補。Q8_0でも量子化誤差はゼロではない。
- llama.cpp、64Kコンテキスト、最大64,000出力、KV精度、CPU/GPU配置、ロード方式、入力テンプレート、sampler、seed、採点器を一致させる。最初はMTP OFFに固定して要因を増やさない。
- 通常版／改変版 × 思考OFF／ON × HumanEval20問・BFCL80問で、1量子化につき400回答。思考ON/OFFは実際のreasoning欄でも確認する。
- 得点に加え、問題ごとの改善・悪化、最終回答の空欄、反復、ツール名・引数・呼び出し数、生成トークン、出力上限、時間、メモリを比較する。BFCLはAST採点で、実ツール往復は別試験。
- HumanEvalは1問が5ポイント、BFCL80問は1問が1.25ポイントに相当する。差が小さい場合は全問版や複数seed・反復で確かめる。20問だけで能力の同等性を断定しない。

この設計で分かるのは、まず「この配布物同士の、固定した通常課題での差」。配布済みGGUFでは変換版や元チェックポイントrevisionの差が残る可能性がある。厳密に改変だけの影響を切り分ける段階では、同一の元revisionからの変更履歴を検証し、同じ変換・量子化ツールと条件で両方を生成する。

## 調査時に固定した4B候補の識別子

実際に測定する際は、以下のrevisionとハッシュを再照合し、別runに記録する。ここへの記載だけではダウンロードや測定開始を意味しない。

| 種類 | 通常版 | Abliterix版 |
| --- | --- | --- |
| 配布repo | `mradermacher/Qwen3.5-4B-GGUF` | `mradermacher/Qwen3.5-4B-abliterated-GGUF` |
| revision | `85aed52869ec5ef32259f80686311048bc260494` | `f3b61227dde75c72d12391c443efd6fa0229e0eb` |
| Q4_K_M bytes | 2708804800 | 2707514688 |
| Q4_K_M SHA256 | `51eafbc127f35598c8f1d2ec58b2520d6126c7d1195c4eca26832e63a2939d39` | `1ec0b30c75b49223c82542caf2635a7af4edcda80d8c89759cc000d3871bf48e` |
| Q8_0 bytes | 4482403520 | 4482403648 |
| Q8_0 SHA256 | `722af6f11b1f8052ae4854a82947e8f37102275f6b0edc402146144aefa840ab` | `a27f3cf0400aba7530e1e707f54edb464881bf3497ccf6a053f692dee426c003` |

Hugging Face APIに現れる両GGUFのchat templateのSHA256はともに `a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715`。実ロード時の `/props` と実際に使う入力でも改めて一致を確認する。
