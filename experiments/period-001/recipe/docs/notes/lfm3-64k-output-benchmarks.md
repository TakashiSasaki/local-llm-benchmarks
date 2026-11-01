# LFM3 and Qwen: 64K context with a larger output allowance

Measured 2026-10-30 on the same Windows Ryzen 9 7940HS / 32 GiB RAM / RTX 4070 Laptop 8 GiB PC. This is separate from the historical [4,096-output-token comparison](lfm3-text-benchmarks.md). Recheck the saved artifacts before reuse.

The later [LFM2.5 / GLM addition](legacy-b11960-benchmarks.md) reuses these six saved configurations and adds two new b11960 measurements. This page's original results remain unchanged; the newer report compares all eight.

## Evidence and status

- Completed run: `C:\LocalLLM\runs\bench64k-output-20261030-141002`. Final `report.html`, `summary.json`, `results.json`, `validation.json`, per-case requests/responses, server props, memory logs and `sources.zip` preserve **720 scored generations across all six configurations**. The four-LFM subset also has `lfm3-stage-report.html`, `lfm3-stage-summary.json` and `lfm3-stage-validation.json`.
- Final validation passed: selected questions, original grader/worker hashes, sampling and question messages, served context/runtime/model, all 720 saved usage/budget records and summary counts. All original profiles/manifests/runtime metadata stayed unchanged. Both root and Hermes task-owned server states were removed, and an actual TCP probe confirmed endpoint closure.
- Runner: `C:\LocalLLM\scripts\benchmark_64k_output.py`. The run preserves `runner-started.py` for LFM and `runner-resumed.py` for Qwen, with hashes and scope in `results.json.runner_revisions`. Restarting skipped all completed LFM generations.
- Qwen 4B's verified model manifest is under `C:\LocalLLM\hermes`, not the root manifest. Its first preflight stopped before any Qwen generation. The resumed runner uses the existing lifecycle helper with the Hermes root and an absolute b11960 executable path. No existing manifests or daily/large profiles were changed. Test clones for LFM are under root `profiles`; Qwen clones are under `hermes\profiles`.
- `results-before-lifecycle-resume.json` preserves the preflight failure, and `unused-qwen-daily-preflight-profile.json` archives its unused root diagnostic profile. `sources.zip` includes both runner revisions, revision/interruption metadata, original base profiles and measured profile snapshots. This preflight failure is not a scored model response or a thinking/output interruption.

## What changed

Both the old and new LFM runs already used **65,536 total context tokens per slot**, one slot, b11960 CUDA 12.4, F16 KV and full GPU language-model placement. The previous issue was the **4,096-token output cap shared by thinking and the final answer**, not exhaustion of the total context.

Both Qwen configurations were freshly measured on that same b11960 runtime. Qwen 4B used full GPU language placement; Qwen 35B retained its first 30 MoE layers' expert weights on CPU. The old Qwen controls used b11946, so old/new Qwen differences also include a runtime change. VL retained its F16 projector but received text only.

The new request cap is `min(64000, 65536 - rendered_input_tokens - 32)`. Each input is template-rendered and tokenized before requesting generation; saved actual prompt usage plus reserved output fits 65,536. CLI `-n 64000`, `--reasoning-format deepseek`, `--reasoning-budget -1`, and API `max_tokens` are recorded. The inherited historical `protocol.human_eval.reasoning_format` description is not the effective launch evidence: use the explicit saved profile arguments and server props.

HumanEval retains the same 20 selected problems, Python 3.14.9, original restricted grader, ON/OFF order, temperature 0.6, top_p 0.95, top_k 20, penalties and seed 42. BFCL retains the same 80 selected problems, pinned AST checker, native tool calls, greedy sampling and thinking OFF; no functions execute. BFCL's output cap also rises from 1,024 to at most 64,000. The request timeout is now 3,600 seconds. Warmups are excluded.

The four-model stage validator compares **every old/new LFM request** after removing only model alias and output limit; all other fields match. The final six-model validator also checks the original dataset and grader hashes, prompt messages, served runtime/model/context, saved requests/responses and cleanup. Actual maximum input was **837 tokens**; every scored request received a 64,000-token output cap, and maximum actual input plus output was **64,182 tokens**.

**No inputs were padded to 64K.** This tests availability of a larger output allowance on short benchmark prompts, not long-context retrieval or reasoning over a 64K input history.

## Completed results, original restricted grader

| Configuration | HumanEval OFF /20 | HumanEval ON /20 | BFCL OFF /80 | Previous HE ON /20 |
| --- | --- | --- | --- | --- |
| Text QAD-Q4_0 | 15 | 19 | 70 | 16 |
| VL QAD-Q4_0 | 11 | 16 | 59 | 8 |
| Text Q8_0 | 17 | 17 | 69 | 14 |
| VL Q8_0 | 9 | 16 | 57 | 11 |
| Qwen3.5-4B Q4_K_M | 14 | 13 | 72 | 6 |
| Qwen3.6-35B-A3B UD-Q3_K_M | 17 | 20 | 72 | 19 |

| Configuration | HE ON maximum actual output tokens | HE ON output-cap hits /20 |
| --- | --- | --- |
| Text QAD-Q4_0 | 9,443 | 0 |
| VL QAD-Q4_0 | 25,391 | 0 |
| Text Q8_0 | 12,153 | 0 |
| VL Q8_0 | 14,225 | 0 |
| Qwen 4B | 64,000 | 6 |
| Qwen 35B | 5,803 | 0 |

All 480 LFM generations ended naturally (`stop` or native `tool_calls`), with no output-cap hit. Across all six models, all **120/120 ON** HumanEval cases returned reasoning fields and **0/120 OFF** cases did. Do not infer that OFF prevents deliberation in final content.

Across LFM HumanEval there were **20 newly correct cases and no regressions**. Every improvement had previously reached the output cap. All previously uncapped task outcomes stayed the same. Text Q8 OFF improved from 16 to 17; other OFF counts and all four BFCL counts stayed unchanged.

Qwen 4B ON improved from 6 to 13, but **HumanEval/7, /22, /28, /62, /151 and /163** each used all 64,000 output tokens with no final code. Each took about 1,143 seconds. Qwen 35B ON improved from 19 to 20: its formerly capped /129 finished correctly in 151.15 seconds. Neither Qwen OFF score changed, and BFCL scores stayed unchanged for all six models. Do not attribute Qwen's old/new changes solely to output allowance because the runtime changed too.

The VL deficit narrowed substantially in thinking ON: Text/VL is now 19/16 at QAD 4bit and 17/16 at Q8. Text still scored higher in all six tested Text/VL comparisons (two quantizations × HE OFF/ON and BFCL). This is a practical observation on these small code/tool subsets, not a general penalty caused by multimodality. Checkpoints have different post-training, and QAD adds distillation; neither comparison isolates one causal architectural/bit-depth factor.

VL was not uniformly worse: Q8 ON had one VL-only success and two Text-only successes. VL also scored higher on no-call judgments. Its BFCL multiple-invocation results remained weak: 5/20 and 6/20 for VL QAD/Q8, versus 18/20 and 17/20 for Text. Longer output allowance did not fix this difference.

## Speed and sampled memory

| Configuration | HE ON median seconds | HE ON aggregate generated token/s | Peak system GPU MiB | Minimum available RAM GiB |
| --- | --- | --- | --- | --- |
| Text QAD-Q4_0 | 8.56 | 180.8 | 2,047 | 19.80 |
| VL QAD-Q4_0 | 25.36 | 174.5 | 2,783 | 19.96 |
| Text Q8_0 | 13.77 | 114.4 | 2,809 | 19.07 |
| VL Q8_0 | 26.99 | 114.1 | 3,545 | 19.29 |
| Qwen 4B | 88.82 | 57.8 | 5,003 | 17.83 |
| Qwen 35B | 53.69 | 39.0 | 7,401 | 5.86 |

Qwen 4B's 20 ON calls totaled 7,748.9 seconds, versus 1,163.1 seconds for Qwen 35B: generating fewer tokens can outweigh lower decoder throughput. These are this PC's measured configurations; tokenizers, quantizations, placement, output lengths, fixed order and thermal/background variation differ. Memory is periodically sampled after readiness and may miss startup or instantaneous peaks.

## Limited grader-policy sensitivity

`grader-sensitivity/results.json` reruns saved failures for all six current model conditions, adding only `type()` and `operator.mul/add` support to the existing restricted worker. No answers were regenerated. Original scores above remain the main scores; canonical checks and worker hashes are saved.

| Configuration | OFF original → secondary | ON original → secondary |
| --- | --- | --- |
| Text QAD-Q4_0 | 15 → 16 | 19 → 19 |
| VL QAD-Q4_0 | 11 → 11 | 16 → 17 |
| Text Q8_0 | 17 → 17 | 17 → 18 |
| VL Q8_0 | 9 → 9 | 16 → 17 |
| Qwen 4B | 14 → 14 | 13 → 13 |
| Qwen 35B | 17 → 18 | 20 → 20 |

Rescued LFM cases were /22; Qwen 35B OFF was /8. The Text/VL comparison direction stayed the same. This is a limited sensitivity check, not a fully unrestricted or official full benchmark score.

## Reuse rules

- Distinguish total context, actual input, output allowance, generated tokens, thinking fields, final code and finish reason. A 64K context setting alone does not remove a 4K output cap.
- Grade final content only. Do not recover code from unfinished reasoning or silently replace original scores with supplemental grader-policy scores.
- Preserve historical 4K/1K results. A fresh comparison with larger output budgets is a new experiment. The earlier Qwen controls used b11946; any old/new Qwen delta can also include runtime differences.
- Keep existing daily/Hermes profiles unchanged; run one test model at a time and stop only the task-owned lifecycle state. Available RAM and GPU memory are periodically sampled, not guaranteed instantaneous peaks.
- These are one-sample selected code/tool subsets, not full leaderboard scores, broad Japanese/language quality rankings, image/video tests, optimized per-model sampling, repeated reliability or new Hermes integration checks.
