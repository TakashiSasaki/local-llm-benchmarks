# LFM3 Text / VL text benchmarks on this PC

Measured 2026-10-30 on the existing Ryzen 9 7940HS / 32 GiB RAM / RTX 4070 Laptop 8 GiB Windows PC. Recheck current artifacts before reuse. Installation, model hashes, projector and launchers are in [lfm3-windows.md](lfm3-windows.md); the earlier Qwen methodology is in [benchmark-comparison.md](benchmark-comparison.md).

This page preserves the historical 4,096-output-token experiment. The later [64K-context / larger-output rerun](lfm3-64k-output-benchmarks.md) removed LFM truncation and substantially narrowed the Text/VL thinking-ON gap. Do not use this page's scores as unlimited-output model capability estimates.

## Evidence and protocol

- Report: `C:\LocalLLM\runs\lfm3-bench-20261030-132439\report.html`; raw `results.json`, concise `summary.json`, `validation.json`, per-case requests/responses, server props, memory logs and `sources.zip` in that directory.
- Runners: `C:\LocalLLM\scripts\benchmark_lfm3.py`, `report_lfm3_bench.py`, and `audit_lfm3_grading.py`. Inspect before reuse. The benchmark makes `bench-*` diagnostic profiles and starts one model at a time through the existing root lifecycle helper. Original model profiles, Hermes profiles, runtime metadata and model manifest hashes stayed unchanged. All test-owned model processes stopped; an actual TCP probe confirmed endpoint closure.
- Four installed variants: LFM3-1.7B Text QAD-Q4_0 / Q8_0; LFM3-VL-2B QAD-Q4_0 / Q8_0. All used b11960 CUDA 12.4, 65,536 context per slot, one slot, F16 KV and full GPU language placement. VL retained its shared F16 vision projector, but **all benchmark inputs were text only**. This is not a multimodal benchmark.
- HumanEval: same official cached dataset commit `b9453e8f1865df0a0057a1383767caa400acfbcf`, SHA-256 `b796127e635a67f93fb35c04f4cb03cf06f38c8072ee7cee8833d7bee06979ef`. Same 20 seed-42 selected tasks as the Qwen comparison. Original code normalizer and Windows job-limited worker were reused; their hashes matched the historical record. All 20 canonical solutions passed before generation. Python was the same PM-managed 3.14.9.
- HumanEval used one generation per task/mode: temperature 0.6, top_p 0.95, top_k 20, min_p 0, repeat/presence penalties 1/0, seed 42, cache_prompt false, **4,096 shared output tokens**, 240-second request timeout. OFF/ON order alternated by task. These match the earlier matched-budget Qwen comparison, not each model's optimized recommended sampling. The earlier greedy 1,024-token Qwen scores are a separate protocol.
- Thinking selection used `chat_template_kwargs.enable_thinking` and `--reasoning-format deepseek`. Every model returned reasoning fields in 20/20 ON cases and 0/20 OFF cases. OFF could still produce prose deliberation in final content; field separation does not prove absence of internal or prose reasoning. Grade only final content with the unchanged normalizer; never extract code from unfinished reasoning. Reaching the output cap is recorded separately and does not force a failure if already-emitted final code passes tests.
- BFCL: same pinned Gorilla commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, unchanged selected 80 IDs and file hashes, 20 each from simple_python / multiple / parallel / irrelevance. The unchanged official AST checker and schema converter were reused. Eighty golden and negative controls passed. Temperature 0, seed 42, 1,024 output tokens, thinking OFF, tool_choice auto, parallel_tool_calls true, original question messages and no system prompt. No functions were executed.
- Total: **480 scored generations** (4 models × 40 HumanEval ON/OFF + 80 BFCL), plus warmups. Fixed order Text QAD → VL QAD → Text Q8 → VL Q8. Memory was periodically sampled after model readiness and can miss startup/instantaneous peaks.

## Original restricted-grader results

| Configuration | HumanEval OFF /20 | HumanEval ON /20 | BFCL OFF /80 |
| --- | --- | --- | --- |
| LFM3 Text QAD-Q4_0 | 15 | 16 | 70 |
| LFM3 VL QAD-Q4_0 | 11 | 8 | 59 |
| LFM3 Text Q8_0 | 16 | 14 | 69 |
| LFM3 VL Q8_0 | 9 | 11 | 57 |
| Qwen3.5-4B Q4_K_M, historical | 14 | 6 | 72 |
| Qwen3.6-35B-A3B UD-Q3_K_M, historical | 17 | 19 | 72 |

Qwen numbers reuse the saved matched-budget HumanEval and BFCL results, not a new Qwen run. They used b11946, and 35B also used CPU-resident MoE experts; cross-model speed differences cannot be attributed solely to the checkpoint. LFM results use b11960 for all four configurations.

| Configuration | HE OFF median s | HE ON median s | HE ON output-cap hits /20 | BFCL median s |
| --- | --- | --- | --- | --- |
| Text QAD-Q4_0 | 1.04 | 8.52 | 3 | 0.31 |
| VL QAD-Q4_0 | 0.61 | 22.60 | 11 | 0.49 |
| Text Q8_0 | 15.81 | 13.77 | 4 | 0.46 |
| VL Q8_0 | 0.96 | 26.96 | 6 | 0.71 |

All 11 VL-QAD ON cap hits and all 6 VL-Q8 ON cap hits had no final code. Aggregate generation was about 182–186 token/s at QAD 4bit and 116–117 at Q8, reasoning included; longer latency can reflect longer generation rather than lower decoder speed. Tokenizers differ for the Qwen comparison. QAD also has quantization-aware distillation, so QAD/Q8 is not a pure bit-depth-only intervention.

BFCL categories (single / candidate selection / multiple invocations / no-call), each /20:

- Text QAD: **19 / 19 / 18 / 14**.
- VL QAD: **17 / 20 / 5 / 17**.
- Text Q8: **19 / 19 / 17 / 14**.
- VL Q8: **17 / 18 / 6 / 16**.

The largest VL loss was multiple invocations. For example, VL-QAD returned only factorial(5) for a request involving 5, 10 and 15. Both templates advertised parallel-tool support, but capability metadata does not prove correct generated call multiplicity. This evaluates the combined model/template/parser pipeline; BFCL AST matching is not semantic execution of alternate batching strategies.

## Limited grader-policy sensitivity

The fixed worker omitted `type()` and rejected conventional `operator.mul/add` implementations. Preserve the original scores above. A separate worker under `grader-sensitivity/` added only those operations, retained syntax/import and Windows job restrictions, and reran saved failures for **all six model conditions** without generating new answers. Canonical checks passed. This is a limited sensitivity analysis, not a fully unrestricted or official evaluator.

| Configuration | OFF original → secondary | ON original → secondary |
| --- | --- | --- |
| Text QAD | 15 → 16 | 16 → 16 |
| VL QAD | 11 → 11 | 8 → 9 |
| Text Q8 | 16 → 16 | 14 → 15 |
| VL Q8 | 9 → 9 | 11 → 12 |
| Qwen 4B | 14 → 14 | 6 → 6 |
| Qwen 35B | 17 → 18 | 19 → 19 |

Rescued LFM cases were HumanEval/22; the rescued Qwen-35B OFF case was /8. Full records and original/secondary worker hashes are in `grader-sensitivity/results.json`. Do not relabel these rescues as new generations or silently replace historical scores.

## Interpretation limits

In these six matched text-task comparisons (two quantizations × HumanEval OFF/ON and BFCL), Text scored higher than VL every time. Limited secondary regrading preserved that direction. This supports a practical preference for these Text checkpoints for the tested code/function-call workload on this PC; it does not establish a universal penalty from multimodality. The checkpoints have different post-training, and QAD variants have additional distillation.

These are 20/80-case subsets with one sample per condition, not full official leaderboard scores or broad intelligence rankings. They do not test general reading comprehension, Japanese language quality, image/video capability, sustained agency, Hermes integration or near-64K histories. VL did better on some individual cases/categories, including no-call judgments; it was not uniformly worse. Larger output budgets are recorded in the separate rerun above; optimized sampling and repeated statistical reliability remain untested.
