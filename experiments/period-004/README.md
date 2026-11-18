# Official HumanEval and BFCL study

2026-11-19追記：ページ再読・根拠台帳ハーネスによるWeb-search全100問と改善サイクルは、[100問の結果](GEMMA4_LEDGER_WEB100_20261118.md)、[部分表の改善と全件比較](GEMMA4_TABLE_GUIDANCE_CYCLE_20261119.md)、[条件・時点の改善サイクル](GEMMA4_CONSTRAINT_CYCLE_20261119.md)を参照。これらは公式BFCL総合スコアではない。以下の開始時点の記述は履歴として残す。

2026-11-18にGemma E4BとSearXNG・Crawl4AIをつなぐローカルのページ再読ハーネスを試した。[3問の試験と出典の課題](GEMMA4_PAGE_HARNESS_PILOT_20261118.md)

2026-11-18にGemma E4BをMTP ON・65,536コンテキスト・固定出力上限なしでHumanEval+全164問測定した。[結果とMTPなし全GPU比較](GEMMA4_MTP_FULLCTX_HUMANEVAL_PLUS_20261118.md)

2026-11-18にGemma 4 E4B公式assistantを使ったMTPの3問試験を実施した。[MTPの互換性・速度・VRAM](GEMMA4_MTP_SMALL_PROBE_20261118.md)

2026-11-18にGemma 4 E4Bの全モデル・KVをGPUに配置してHumanEval+を再測定した。[全GPUと28層GPUの比較](GEMMA4_ALLGPU_HUMANEVAL_PLUS_20261118.md)

2026-11-18にGemma 4 E4Bを英語チャット・Thinking ONで全164問測定した。[Gemmaのチャット形式 HumanEval+ と条件差](GEMMA4_CHAT_THINKING_HUMANEVAL_PLUS_20261118.md)

2026-11-18にTernary Bonsai 2 27B Q2_0を32,768コンテキストで全164問測定した。[BonsaiとLFM3・GemmaのHumanEval+比較](BONSAI2_Q20_32K_HUMANEVAL_PLUS_20261118.md)

2026-11-17にGemma 4 E4Bの保存済み164回答をEvalPlusで再採点し、LFM3-1.7B TextのQAD-Q4_0とQ8_0も各164問を実施した。[GemmaのHumanEval+](HUMANEVAL_PLUS_20261117.md) · [LFM3 QAD-Q4_0](LFM3_HUMANEVAL_PLUS_20261117.md) · [LFM3 Q8_0と比較](LFM3_Q8_HUMANEVAL_PLUS_20261117.md)

LFM3-1.7B Text Q8_0を公式チャット形式・Thinking ONでも全164問で測定し、不合格17問を出力上限32,768トークンで再試行した。[チャット形式・Thinking ON](LFM3_Q8_CHAT_THINKING_HUMANEVAL_PLUS_20261117.md) · [不合格17問の再試行](LFM3_Q8_CHAT_THINKING_32K_RETRY_20261117.md)

2026-11-15の保存証拠監査・Memory採点と今後の判断は、[TUFA15での Gemma 4 E4B 評価](GEMMA4_RESULTS_20261115.md)に記録。[SearXNGによるWeb-search](BFCL_FOLLOWUP_20261115.md)には、ツール呼び出しの修正、Thinking ON/OFFの比較、全GPUでの200件の追加測定、multi-turn補完の準備を記録した。以下は計画作成時の記述。

Period 004 is open separately while period 003 remains open. The execution plan, dated adapter validations, current run identifiers, official source revisions, BFCL case counts, explicit host-execution authorization and Windows scoring differences are documented in [OFFICIAL_EVALUATION.md](OFFICIAL_EVALUATION.md). HumanEval full 164 sample collection is in progress. BFCL official full evaluation remains to be set up.
