# Previously evaluated LFM2.5 and GLM checkpoints on b11960

Completed 2026-10-30 on the same Windows Ryzen 9 7940HS / 32 GiB RAM / RTX 4070 Laptop 8 GiB PC. Recheck current artifacts before reuse. This extends the [six-configuration large-output comparison](lfm3-64k-output-benchmarks.md) to eight configurations; it does not replace historical evaluation results.

## Artifacts and validation

- Run: `C:\LocalLLM\runs\legacy-models-64k-20261030-180109`. `report.html` and `summary.json` compare eight configurations. `results.json`, `validation.json`, per-case requests/responses, phase-specific props/memory logs, model metadata and `sources.zip` preserve the added measurements.
- **240 new scored generations**: LFM2.5-24B-A2B QAD-Q4_0 and GLM-4.7-Flash Q4_K_M, each with 20 HumanEval OFF + 20 ON + 80 BFCL OFF. The six saved b11960 configurations contribute **720 reused generations**, not fresh reruns. Their source is `C:\LocalLLM\runs\bench64k-output-20261030-141002\results.json`; its SHA-256 stayed unchanged.
- Runners: `C:\LocalLLM\scripts\benchmark_legacy_models.py`, `audit_legacy_grading.py`, `report_legacy_models.py`, `validate_legacy_bench.py`. Inspect before reuse; run the parent scripts rather than archived source copies whose import paths differ.
- Validation passed: identical selected problems, cached official dataset and original grader/worker hashes, request fields matching the saved suite except model alias/output reservation, unchanged code normalizer output, served model/runtime/context, all saved usage/budget records, and summary counts. Original profiles, manifests and runtime metadata were unchanged. Task-owned servers stopped and an actual TCP probe confirmed port 8089 closure.
- The initial normalizer environment lacked `re` and stopped after saving the first response. Only the missing import and response-recovery/memory bookkeeping were fixed; the original normalizer and grader functions stayed unchanged. HumanEval/6 OFF reused its saved response, including its incorrect tool-call text; it was not regenerated or selectively replaced. Both runner versions and the interruption record are archived.

## Configuration and thinking controls

All added tests use b11960 CUDA 12.4, 65,536 context per slot, one slot, F16 KV, Flash Attention auto, no context shift and no automatic fit. Model files and hashes match the existing `lfm.json` / `glm.json` and root model manifest. The original b11946/16K profiles remain unchanged; separate `legacy64k-*` diagnostic profiles record the actual launches.

- LFM2.5 retains first-24-MoE-layer expert weights on CPU, six generation threads and eight batch threads. Its embedded template unconditionally starts `<think>` and **ignores `enable_thinking`**: both flags rendered identical prompts. OFF uses the documented CLI **`--reasoning-budget 0`** (immediate reasoning end); ON uses `-1`. OFF code and BFCL are measured first, then ON code on a separate server. This is runtime-imposed OFF, not evidence of a native template OFF switch.
- GLM retains first-35-MoE-layer expert weights on CPU and eight threads. It uses native `enable_thinking=false/true`, with CLI reasoning budget `-1` for both. OFF/ON task order alternates as in the saved six-model run.
- Warmups verified actual mode separation. Scored HumanEval reasoning fields were **0/20 OFF and 20/20 ON for each model**; BFCL reasoning fields were **0/80 each**. OFF may still deliberate in final content; empty reasoning fields do not establish absence of all reasoning.
- `/v1/models` recorded trained context 131,072 for LFM2.5 and 202,752 for GLM, both above the configured 65,536. The raw metadata snapshots are saved.

Same pinned HumanEval 20 problems, Python 3.14.9, temperature 0.6, top_p 0.95, top_k 20, seed 42 and original restricted Windows worker. Same BFCL 80 problems, schema converter and pinned AST checker, greedy sampling, native parsed tool calls and no function execution. Twenty canonical Python solutions and 80 golden/negative BFCL controls passed before generation. Per-request timeout was 3,600 seconds; warmups are excluded.

Output cap: `min(64000, 65536 - rendered_input_tokens - 32)`. Every added scored request received 64,000 output tokens. Actual maximum input was **723 tokens** and maximum actual total was **7,859 tokens**. No input padding was used: these are short-prompt code/tool tasks, not a near-64K-input quality or sustained-agent test.

## Added results, original restricted grader

| Configuration | HumanEval OFF /20 | HumanEval ON /20 | BFCL OFF /80 |
| --- | --- | --- | --- |
| LFM2.5-24B-A2B QAD-Q4_0 | 11 | 19 | 63 |
| GLM-4.7-Flash Q4_K_M | 12 | 19 | 70 |

**All 240 added generations ended without hitting the output cap.** LFM2.5's maximum output was 7,425 OFF / 6,496 ON tokens; GLM's was 316 OFF / 3,810 ON.

LFM2.5 OFF had nine syntax errors after the unchanged normalizer. For example, /6 returned `<|tool_call_start|>` text invoking the unprovided `write_todos` tool rather than the requested Python module. Treat its OFF result as behavior under the forced control, including instruction/output-format failures; do not attribute all of it to pure problem-solving ability. Native ON's only failure was /163.

GLM OFF had seven test/runtime failures and one guard rejection; ON's only failure was /108. Both models scored 19/20 ON but failed different questions. Counts alone do not establish uniform superiority.

BFCL categories, each /20, in single-function / candidate-selection / multiple-invocation / no-call order:

- LFM2.5: **19 / 19 / 15 / 10**.
- GLM: **20 / 17 / 17 / 16**.

The limited secondary worker added only `type()` and `operator.mul/add`, exactly matching the earlier six-model sensitivity worker. No generated answers changed, and **neither added model's score changed**. Original and secondary worker hashes and canonical checks are saved under `grader-sensitivity/`. This is not an unrestricted or full official evaluation.

## Speed and sampled memory

| Configuration | HE OFF median s | HE ON median s | BFCL median s | HE ON generated token/s | Peak system GPU MiB | Minimum available RAM GiB |
| --- | --- | --- | --- | --- | --- | --- |
| LFM2.5 | 3.42 | 40.26 | 1.28 | 46.72 | 7,499 | 8.64 |
| GLM | 8.19 | 67.78 | 7.06 | 20.35 | 7,937 | 2.09 |

These are this PC's configurations, not parameter-count or decoder-speed rankings. Quantization, tokenizers, CPU expert placement, phase order, output lengths and background/thermal state differ. Samples start after server readiness and may miss startup/instantaneous peaks. LFM2.5 memory aggregates OFF/ON and the initial pre-repair window. Shared GPU memory and sustained paging were not directly measured. A guard would stop only the task-owned server after available RAM stayed below 1 GiB for three observations; it did not trigger in this run.

## Comparison limits and reuse

- The report combines all eight b11960 configurations, explicitly marking the two new rows and six reused rows. LFM3/Qwen scores and their older archives stayed unchanged.
- These two checkpoints previously had b11946 custom-agent/log-speed measurements, **not matching HumanEval/BFCL baseline scores**. Do not invent old/new accuracy improvements or attribute these scores solely to the runtime upgrade.
- The earlier GLM near-64K-input capacity trial was operator-stopped for low RAM. This successful short-prompt benchmark does not retroactively turn that trial into a completed result or establish long-history retrieval quality.
- Preserve the distinction between native and forced thinking OFF. Do not change the original templates, recover answers from unfinished reasoning, or silently replace primary scores with policy/format repairs.
- These are fixed 20/80-case subsets with one answer per condition. They do not establish broad Japanese/language quality, vision quality, new Hermes integration, actual external-tool execution, optimized per-model sampling or statistical repeatability.
