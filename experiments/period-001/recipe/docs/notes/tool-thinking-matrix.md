# Eight-configuration code/tool thinking matrix

Completed 2026-10-30 on this Windows Ryzen 9 7940HS / nominal 32 GiB RAM / RTX 4070 Laptop 8 GiB PC. This is measured local evidence for specific model files, templates and placements, not a universal model ranking. Recheck the live artifacts before reuse.

## Artifacts and scope

- Dashboard: `C:\LocalLLM\runs\benchmark-matrix-20261030-194424\index.html`. It contains all eight configurations × HumanEval/BFCL × thinking OFF/ON: **32 conditions**. Views switch success rate, median response time, longest response, total response time, generation token/s and output-cap count. Per-model details show categories, changed cases, grading reasons, parsed arguments and raw-response links. Long call lists are truncated only in the page preview; original outputs remain intact.
- `matrix-data.json`, `conditions.csv`, `truncations.json` / `.csv`, `matrix-validation.json`, `ui-validation.json`, desktop/mobile screenshots and `dashboard-sources.zip` are in the same directory. The CSV uses UTF-8 BOM. Preserve the linked source run folders if moving the page: summary data are embedded, but raw-response links are relative to those folders.
- **640 newly scored BFCL ON generations**, 80 per configuration. The existing **960 answers** (320 HumanEval + 640 BFCL OFF) are reused without regeneration from `runs\bench64k-output-20261030-141002` and `runs\legacy-models-64k-20261030-180109`. Total: **1,600 answers**, including 1,280 BFCL answers. Do not describe all 1,600 as newly generated.
- Qwen 35B ON has its own run: `C:\LocalLLM\runs\qwen35-bfcl-thinking-20261030-194028`. The other seven ON runs are subdirectories named by model key under the dashboard directory. Each contains raw request/response JSON, `results.json`, `summary.json`, props, memory samples, selfchecks, a source ZIP and `independent-audit.json`.
- Main scripts under `C:\LocalLLM\scripts`: `benchmark_qwen_tool_thinking.py`, `benchmark_model_tool_thinking.py`, `run_tool_benchmark_matrix.py`, `audit_qwen_tool_thinking.py`, `build_benchmark_matrix.py`, `benchmark_matrix_template.html`, `validate_benchmark_matrix.py`, `check_benchmark_matrix_ui.cjs`. Inspect these dated runners before reuse: baselines are pinned to the above folders, and the orchestrator reuses the supplied completed Qwen run and already audited model runs rather than regenerating them.
- The user elected to retain **Qwen3.6-35B-A3B UD-Q3_K_M** because of RAM/VRAM constraints. No additional Qwen quantization was downloaded or measured. Qwen3.5-4B Q4_K_M is a different model/generation, not a Qwen 35B quantization control.

## Protocol and validation

Same b11960 / `8642541b2` CUDA 12.4 runtime, 65,536 context per slot, one slot, F16 KV, Flash Attention auto, no context shift or automatic fit. Preserve each model's historical CPU/GPU placement and thread counts. Qwen 35B keeps `--n-cpu-moe 30`, LFM2.5 24, GLM 35. Small LFM3 and Qwen 4B retain their existing GPU profiles. Original daily/evaluation profiles, runtime metadata, manifests and source responses were unchanged.

BFCL retains the pinned v4 selected 80 cases, seed 42, 20 each of `simple_python`, `multiple`, `parallel`, `irrelevance`, and unchanged official schema conversion / AST checker. Gorilla commit: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`. All 80 golden and negative controls passed. Temperature 0, top_p 1, top_k 0, min_p 0, repeat_penalty 1, seed 42, cache_prompt false, tool_choice auto, parallel_tool_calls true, no added system message, unmodified official question[0]. **No functions were executed**. Malformed call arguments fail, including in irrelevance cases.

Every scored ON request received 64,000 output tokens, guarded by `min(64000, 65536 - rendered_input_tokens - 32)` after template rendering/tokenization. Requests matched their saved OFF payloads except native `enable_thinking=true`, plus LFM2.5's routing alias for its separate mode phases. Qwen's HTTP timeout was 3,600 seconds; the later seven runners allow 7,200 seconds so slow generation can reach the same token cap. This is a transport timeout, not a larger generation budget. CLI reasoning format is deepseek and ON budget is -1.

**LFM2.5 exception:** its template ignores `enable_thinking` and always begins thinking. OFF used CLI budget 0; ON uses native generation with budget -1 and a different alias. Label this runtime-imposed OFF rather than a native template switch. The other seven use native OFF/ON flags. Actual formal reasoning fields were **80/80 ON and 0/80 OFF for every configuration**. This does not establish absence of all implicit reasoning in OFF content.

Per-run audits regraded 160 saved BFCL responses and checked requests, case/data hashes, model/runtime/context, usage and unchanged originals. Global validation confirmed 32 conditions, 960 reused + 640 new answers, all raw links and CSV counts. Browser QA passed at 1400px and 390px, including metric switches, case filters, expansion and mode qualifications; no JS errors or page-level horizontal overflow. Both lifecycle roots had no server state and no `llama-server.exe` remained after cleanup.

The first LFM3 post-run audit stopped orchestration because its old-response path was still fixed to Qwen. The path was corrected to the model key; all saved LFM3 outputs were revalidated without regenerating scored answers. Original auditor/controller versions and the resume history are preserved. This was a validation-path bug, not a failed inference or rerolled sample.

## Primary scores

HumanEval retains the original restricted Windows worker, Python 3.14.9 and fixed 20-case subset. It is not the supplemental relaxed-worker score. HumanEval and BFCL use different sampling: HE temperature 0.6 versus BFCL 0.

| Configuration | HE OFF /20 | HE ON /20 | BFCL OFF /80 | BFCL ON /80 | BFCL ON caps |
| --- | --- | --- | --- | --- | --- |
| Qwen3.6-35B-A3B UD-Q3_K_M | 17 | 20 | 72 | 72 | 2 |
| Qwen3.5-4B Q4_K_M | 14 | 13 | 72 | 68 | 0 |
| LFM3 Text QAD-Q4_0 | 15 | 19 | 70 | 73 | 0 |
| LFM3 Text Q8_0 | 17 | 17 | 69 | 73 | 0 |
| LFM3 VL QAD-Q4_0 | 11 | 16 | 59 | 56 | 0 |
| LFM3 VL Q8_0 | 9 | 16 | 57 | 63 | 0 |
| LFM2.5-24B-A2B QAD-Q4_0 | 11 | 19 | 63 | 60 | 0 |
| GLM-4.7-Flash Q4_K_M | 12 | 19 | 70 | 72 | 0 |

BFCL ON's largest count was LFM3 Text's 73/80 for both quantizations. This is one more case than Qwen 35B or GLM ON, not proof of broad superiority. ON did not universally improve tool-call scores. The VL configurations also differ from Text in model architecture/parameter count; do not attribute the gap solely to multimodality or precision.

## BFCL timing and sampled memory

| Configuration | OFF median s | ON median s | ON total s | ON peak system GPU MiB | ON minimum available RAM GiB |
| --- | --- | --- | --- | --- | --- |
| Qwen 35B Q3 | 3.188 | 16.614 | 5071.93 | 7379 | 5.54 |
| Qwen 4B Q4 | 1.135 | 3.005 | 318.13 | 5003 | 18.72 |
| LFM3 Text Q4 | 0.336 | 1.221 | 125.65 | 2047 | 20.52 |
| LFM3 Text Q8 | 0.486 | 1.929 | 208.53 | 2809 | 19.71 |
| LFM3 VL Q4 | 0.518 | 1.185 | 140.24 | 2783 | 20.45 |
| LFM3 VL Q8 | 0.737 | 1.677 | 211.56 | 3545 | 19.73 |
| LFM2.5 Q4 | 1.279 | 3.850 | 465.76 | 7499 | 8.78 |
| GLM Q4 | 7.061 | 12.603 | 1167.71 | 7937 | 2.74 |

Times exclude loading/warmups. Qwen 35B OFF total was 360.48 seconds versus ON 5,071.93 seconds (about 6.0 versus 84.5 minutes); its median hides two roughly 30-minute outliers. OFF is reused from an earlier same-day run. Background load/thermal state and different tokenizers, output lengths and placements prevent treating token/s or latency as intrinsic model rankings. Memory samples start after readiness, include other apps and may miss instantaneous/startup peaks. Shared GPU memory and sustained paging were not measured. These figures do not establish full Hermes workflow memory needs.

## Qwen 35B ON changes and output limits

- Improved: `multiple_22`, `parallel_173`, `irrelevance_8`, `irrelevance_70`.
- Regressed: `simple_python_279`, `simple_python_377`, `multiple_151`, `irrelevance_188`.
- Failed both: `multiple_7`, `parallel_26`, `irrelevance_26`, `irrelevance_228`.
- Categories OFF → ON: single function 20→18, candidate selection 18→18, multiple calls 18→19, no-call 16→17; each /20.

Two output-cap cases:

1. `simple_python_377`, current time in Sydney: 64,000 completion + 361 prompt = **64,361 total**, 1,820.56 seconds. The API parsed **1,431 tool-call specifications**, including repeated `get_current_time` calls. Reasoning was 3,794 characters; final content was empty. Wrong call count caused failure. This was not 64K of thinking alone and no real time-service calls were executed.
2. `irrelevance_8`, integral of x^3 from 1 to 5 with only irrelevant `str_to_int` available: 64,000 completion + 294 prompt = **64,294 total**, 1,815.33 seconds. Zero parsed calls, 159,188 reasoning characters, empty final content. Repeated reasoning already contained the correct number 156, but no final answer was produced. **It passed BFCL's no-call criterion** because that criterion does not grade ordinary answer correctness or completion. Do not describe this as completed assistance or salvage the thought into a final answer.

Both totals are below 65,536: these were **output limits, not full-context exhaustion**. The complete current matrix has eight capped outputs: these two plus the six previously measured Qwen 4B HumanEval ON cases. The latter's BFCL ON had **zero** caps. Keep the earlier 16K reservation guards and near-64K-input operator stop separate; see [local-evidence.md](local-evidence.md) and the historical truncation audit.

This is a short-input, fixed-subset, one-answer-per-condition evaluation of code generation and parsed tool selection/arguments/abstention. It does not measure actual API execution, long-history retrieval, Japanese general quality, images or sustained multi-turn agent success. Keep score, response completion, token limits and observed reasoning separate.
