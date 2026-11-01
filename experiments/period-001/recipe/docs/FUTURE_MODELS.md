# 将来試したいモデル

## SC117 Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF

記録日: 2026-10-31。ユーザーから「もっとパワフルなマシンが手に入ったら試したい」と希望があったモデル。現在は保留とし、新しいマシンでの測定候補として残す。

- 配布先: [SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF)
- 調査時のrevision: `90a3350cd800ec1fe0d1660a38414ad9e985782f`。将来の取得時には、その時点の配布物・revision・ハッシュを改めて確認する。
- 現状: 配布情報とローカル環境の調査のみ。モデル本体の取得、起動、ベンチマーク、Hermes接続は未実施。既存の35B版の測定結果をこのモデルの結果として扱わない。

### 今回見送った理由

現在のPCはRAM 32 GiB、RTX 4070 Laptop GPUのVRAM約8 GiB。最小のQ2_0でも本体約38.02 GBとn-gram検索テーブル約28.80 GB、合計約66.82 GBの取得が必要になる。これはモデルカードの合計欄ではなく、[Q2_0の実ファイル](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF/tree/main/Q2_0)のサイズを合算した値（十進GB）。

検索テーブルは `mmap` と `lazy-mode` でSSD上に置けるが、本体の配置に加えてOS・実行用バッファ・KVキャッシュの余裕が必要となる。現PCではメモリ不足とSSDへの頻繁な退避による低速化が懸念され、実用的な動作は厳しいと見積もった。実測で起動不能を確認したわけではない。

調査時のllama.cpp b11960のバイナリには `qwen4exp` の識別文字列とlazy-modeのオプションがあったが、このモデルのロード成功を示すものではない。配布者が紹介するStrataの構成例はRAM 64 GB＋VRAM 12 GBで、必要最小構成や速度保証としては扱わない。

参考: [上流のメモリ要件](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF#memory-requirements)、[配布者の実行方法とStrataの説明](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF#running-it)。

### 新しいマシンを入手したら

当時のランタイム対応とRAM・VRAM・SSDの余裕を再確認し、短い入力での容量・生成確認から始める。動作が確認できたら、既存のHumanEval/BFCL、思考OFF/ON、MTPの比較候補に加え、Hermes接続は別試験として扱う。新しい実測は専用の `runs/<run-id>/` に保存する。
