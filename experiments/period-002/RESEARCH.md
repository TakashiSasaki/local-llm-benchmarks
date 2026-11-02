# 無検閲モデルの候補調査

調査日: 2026-11-02。HF作者カード、公開config、Hub APIの実ファイル情報を照合しました。以下は**配布情報・作者評価・実機容量の見積もり**であり、当PCでの追加測定結果ではありません。

## 推奨する第1陣

容量は取得する1ファイルの**十進GB**です。RAM/VRAM消費量ではありません。通常版と改変版を別々に新規測定し、原応答を保存します。

| 優先・役割 | 候補 | Q4_K_M | 選ぶ理由と未確認事項 |
| --- | --- | ---: | --- |
| 能力上限の本命 | [Huihui Qwen3.6-35B-A3B](https://huggingface.co/huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated) / [GGUF](https://huggingface.co/mradermacher/Huihui-Qwen3.6-35B-A3B-abliterated-GGUF) | 21.167 GB | 第1期で同型35B MoEの動作実績がある。日本語・コード・ツールのベース能力を活かす候補。CPU MoE配置が前提で、改変後の一般能力保持はまだ未実証 |
| 利用実績のある9B | [Huihui Qwen3.5-9B](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-9B-abliterated) / [GGUF](https://huggingface.co/mradermacher/Huihui-Qwen3.5-9B-abliterated-GGUF) | 5.627 GB | 35Bより軽く、通常版と同配布者のQ4対照を用意できる。作者は概念実証と位置付け、幅広い能力の前後ベンチは未掲載 |
| 9Bの実用性能競争枠 | [DavidAU The Defiant Fable 9B](https://huggingface.co/DavidAU/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF) | 6.829 GB | 作者による一般ベンチ比較と利用の多さがある。Heretic後の追加学習・複数モデルのマージを含む。単純abliteration比較ではなく、コード/日本語/BFCLは当PCで検証する |
| 手法比較の9B | [darrellbest Heretic ARA 9B](https://huggingface.co/darrellbest/Qwen3.5-9B-Heretic) / [GGUF](https://huggingface.co/darrellbest/Qwen3.5-9B-Heretic-GGUF) | 5.780 GB | 方法と重みの復元来歴が明記される。作者は算術4問×10seedで通常/改変とも40/40と報告するが、広範な推論能力の維持やBFCLの証明ではない |
| 測定系と影響検出の先行確認 | [Wangzhang Abliterix Qwen3.5-4B](https://huggingface.co/wangzhang/Qwen3.5-4B-abliterated) / [GGUF](https://huggingface.co/mradermacher/Qwen3.5-4B-abliterated-GGUF) | 2.708 GB | 同配布者の通常版との比較を安価に始められる。小さいKLの自己報告だけではHumanEval/BFCL維持を証明しない。高性能候補の最終順位とは分ける |

対照は同配布者の[mradermacher通常4B](https://huggingface.co/mradermacher/Qwen3.5-4B-GGUF)、[通常9B](https://huggingface.co/mradermacher/Qwen3.5-9B-GGUF)、[通常35B](https://huggingface.co/mradermacher/Qwen3.6-35B-A3B-GGUF)です。Heretic/Defiantは別の変換・tensor構成を含み、同じ通常版を使っても改変だけの効果を切り分けた試験にはなりません。

### 「評判」の扱い

2026-11-02のHub API観測では、Defiant GGUFはlikes1,303・直近30日downloads1,965,614、Huihui9B GGUFは66・290,441、Huihui35B GGUFは15・95,947、Heretic9B GGUFは5・11,432でした。元のHuihui作者カードは9Bで164 likes、35Bで104 likesです。repo種別と集計範囲が違うため、数を合算したり品質順位に変換したりしません。利用の多さは調査の優先度を上げる根拠で、性能保持の証明ではありません。

Defiant作者の掲載値では、Instruct条件のARC-Cは通常9B MXFP8の0.571に対し、改変版MXFP4で0.640、MXFP8で0.647とされています。ただし作者内の評価で、今回のQ4_K_M・思考ON・日本語・コード・ツール採点と同じではありません。カード後半のQwen公式ベンチ表はベースモデルの値も含むため、改変版の測定値として転載しません。Q4でも出力tensorのF16化等があり、今回のファイルは通常9Bより約1.20 GB大きくなります。

## 第二陣・予備枠

| 候補 | 判断 |
| --- | --- |
| [0bserverx Qwen3.8-27B RVN multilingual](https://huggingface.co/0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF) | 高い絶対能力を狙う第二陣。通常版は[公式Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)の系統。採用候補は`RVN-Q4_K_M-multilingual.gguf` **16.547 GB**で、旧pre-RVNファイルとは別。作者のKL/拒否・ロード・加算ツールsmokeは一般能力全体の保持の証明ではない。dense27Bのため、35B-A3Bより重い計算・遅いCPU生成も想定する |
| [Dolphin-Mistral24B Venice](https://huggingface.co/dphn/Dolphin-Mistral-24B-Venice-Edition) | SFT系を加える予備枠。現カードはvision/131K/tool calling更新を含むv1.2で、[対応GGUF](https://huggingface.co/douganger/Dolphin-Mistral-24B-Venice-Edition-1.2-GGUF)のQ4は **14.334 GB（13.35 GiB）**。旧GGUFと混ぜない。初回に照会した末尾`-GGUF`だけのIDはAPI401となり、確認できたv1.2のIDを採用候補に訂正。元の正確な通常版revision/変換対照を確定するまでは主比較へ追加しない |
| [Huihui Gemma4 12B](https://huggingface.co/huihui-ai/Huihui-gemma-4-12B-it-abliterated) | 別系列の予備候補。Q4は **7.381 GB**。作者が初期ベース重みの問題・再アップロードを告知し、現baseとGGUFでarchitecture/context表記に差がある。ベースと変換の来歴を解決してから採否判断 |
| [NeuralDaredevil8B](https://huggingface.co/mlabonne/NeuralDaredevil-8B-abliterated) | DPO修復の歴史的比較に有用だが、2024年の評価を現在の最高性能としない。native8Kで、64K共通主比較へ無条件に入れない。実施するならDaredevil通常→abliterated→NeuralDaredevilの3者で、共通8Kの別系列 |
| [Dolphin3.0 Qwen2.5 3B](https://huggingface.co/dphn/Dolphin3.0-Qwen2.5-3b) | 軽量性の参考。native32K、ベースからのSFT、カードの評価欄は未整備。現在の高性能候補を優先する本計画では順位を下げる |
| [R1-Distill-Qwen14B abliterated v2](https://huggingface.co/huihui-ai/DeepSeek-R1-Distill-Qwen-14B-abliterated-v2) | 推論特化の別枠。カードにはthink出力や拒否の問題に対する例示誘導の注意が残り、安定保持を保証していない。ツール対応と長時間思考の費用を確認してから |

70B/72Bの標準Q4と671B級は、OS・KV・実行バッファを要するこのPCの第1陣には採用しません。極低ビットやSSD退避で理論的に起動できる構成まで否定した判断ではありませんが、速度と量子化による別要因が大きく、現在の調査目的には不向きです。

## 提示された予備調査への補足・訂正

1. [failspy v3の正しいrepo](https://huggingface.co/failspy/Meta-Llama-3-8B-Instruct-abliterated-v3)と、提示リンクの[mlabonne/Daredevil](https://huggingface.co/mlabonne/Daredevil-8B-abliterated)は別モデルです。51.34→51.21は**0.13ポイント、相対約0.253%低下**で、「0.1%未満」ではありません。
2. [NeuralDaredevil作者の比較](https://huggingface.co/mlabonne/NeuralDaredevil-8B-abliterated)は、Daredevil55.87→abliterated55.06→DPO後55.87という平均値を示します。マージやDPOの効果を含み、公式Llama3との得点差をabliteration単独の効果としません。
3. 「大規模なら損傷が僅か」「7–9Bが最も壊れやすい」「SFTなら論理回路が傷つかない」は、今回確認した資料から一般則として裏付けられません。大きさ・学習方式・宣伝文句ではなく実測で判断します。
4. [Heretic](https://github.com/p-e-w/heretic)は拒否とKL divergenceを最適化する設計ですが、KLが小さいことはHumanEval/BFCLで同じ正解率になることと同義ではありません。[元の拒否方向研究](https://arxiv.org/abs/2406.11717)も、全モデル・全能力が無影響であるという保証ではありません。
5. 「無検閲」は配布者の呼称です。今回の目的では、通常課題の能力と、正当な要求への過剰拒否を別に調べます。拒否が減っただけで説明の正しさやツール引数が改善したとは扱いません。

## 当PCでの実現性

開始時はWindows11 Home 26H2/26300.9818、NVIDIA555.97、VRAM8,188 MiB、空きRAM約21.8 GiB、空きディスク約146.1 GB（約136.1 GiB）。取得時や測定直前に変動を確認します。[開始時観測](environment/planning-20261102.json)を保存しました。

Qwen3.5-9Bの[公式config](https://huggingface.co/Qwen/Qwen3.5-9B/blob/c202236235762e1c871ad0ccb60c8ee5ba337b9a/config.json)から、64K/F16のfull-attention KVだけで概算**2 GiB**です。重み5.6〜6.8 GBにSSM状態・compute・画面利用等が加わるため、64Kで全GPUを保証しません。必要なら同一対照内で共通の部分CPU配置を選びます。35Bは第1期と同様CPU MoEオフロードを前提とします。

b11960固定commitの[architecture登録](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/src/llama-arch.cpp)にはqwen35/qwen35moe/gemma4がありますが、新しい個々のGGUF・テンプレート・パーサの成功は未確認です。まず既存runtimeでpreflightし、更新が必要なら固定版と通常版対照を新しい条件として扱います。

## 再取得可能な調査記録

- [主候補18 repoの観測](research/huggingface-20261102.json)と[補足11 repoの観測](research/huggingface-supplement-20261102.json)に、固定revision・LFS SHA-256・ファイル容量・人気指標・config/README digestを記録。
- 取得候補の個別manifestは[models/](models/)。ここへの登録は未取得・未測定の意味で、ローカルhash確認済みではありません。
- 収集コードは`../../scripts/collect_hf_research.py`。APIとconfig/READMEだけを取得し、ウェイトとリモートコードは実行・取得しません。モデル提供テンプレート本文は保存せずdigestだけを残します。
- Hubのrepo単位GGUFメタデータは選択ファイルの内容を保証しません。実際に選んだGGUFのヘッダー、テンプレートhash、MTP tensor、`/props`を実行前に確認します。
