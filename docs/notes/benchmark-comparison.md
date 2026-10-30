# Local 4B / 35B comparison

The later LFM3 Text/VL comparison reuses these pinned selected questions and original graders; see [lfm3-text-benchmarks.md](lfm3-text-benchmarks.md). The original results below remain unchanged. Its limited secondary regrading is reported separately from original scores.

The completed [64K-context / larger-output rerun](lfm3-64k-output-benchmarks.md) raises the shared thinking/final-answer allowance and includes fresh Qwen measurements on b11960. It records Qwen 4B ON 13/20 with six remaining 64,000-token cap failures, and Qwen 35B ON 20/20 with no cap hits. Keep those larger-budget results separate from the historical tables below.

The subsequent [LFM2.5 / GLM addition](legacy-b11960-benchmarks.md) extends that b11960 comparison to eight configurations. Its two new rows reuse these same selected questions and original graders; their old custom-agent measurements are not old HumanEval/BFCL scores.

Measured 2026-10-29 on this user's native Windows ASUS TUF A15: Ryzen 9 7940HS, 32 GiB RAM, RTX 4070 Laptop 8,188 MiB. Recheck the live configuration before reuse. This is a comparison of two installed configurations, not a generic parameter-count ranking.

## Artifacts and runner

- Final report: `C:\LocalLLM\hermes\benchmarks\comparison-20261029-141429\report.html` and `results.json`.
- Original attempts: `C:\LocalLLM\hermes\benchmarks\comparison-20261029-140654`.
- Runner: `C:\LocalLLM\hermes\benchmarks\compare_models.py`; grader: `grade_worker.py`; reporting/routing verifier: `summarize_comparison.py`. Final results include source copies and their hashes. Run the parent runner, not the audit copies whose relative paths differ.
- Dataset: official HumanEval `data/HumanEval.jsonl.gz`, repository commit `b9453e8f1865df0a0057a1383767caa400acfbcf`. Its hash is in results.json. Sample 20 row indices using `random.Random(42).sample(range(164), 20)`, then sort the indices. The full benchmark is 164 tasks; these scores are not full official leaderboard results.

## Measured result

| Metric | Qwen3.5-4B Q4_K_M | Qwen3.6-35B-A3B UD-Q3_K_M |
|---|---:|---:|
| HumanEval selected tasks passed | 16/20 | 17/20 |
| Raw code-response median | 2.28 s | 5.66 s |
| Aggregate generation speed | 72.79 tokens/s | 36.66 tokens/s |
| Hermes custom tasks passed | 3/3 | 3/3 |
| Total of 3 Hermes task times | 62.17 s | 150.17 s |
| Sampled minimum available system RAM | 16.948 GiB | 4.178 GiB |
| Sampled maximum system GPU memory | 5,003 MiB | 7,359 MiB |

The 1/20-task accuracy difference is too small to establish general superiority. The short tested tasks favor 4B in speed and headroom; 35B still makes errors that 4B does not. Neither trial crashed or reached the memory-stop condition. Both model processes and the test-started gateways were stopped. Daily/large inference profiles and the user's Hermes config were unchanged by this comparison.

## Protocol and grading

Both servers used existing b11946 profiles, 65,536 context, one slot, F16 KV, eight threads. 4B was on GPU; 35B used the existing first-30-MoE-layers-on-CPU placement. Quantization and Qwen generation differ, so do not attribute all differences to model size.

HumanEval used the same English chat prompts, temperature 0, seed 42, top_p 1, top_k 0, min_p 0, repeat penalty 1, thinking disabled, 1,024 output-token cap, and one answer per task. Responses were deterministically normalized for code fences/full-module vs completion format and checked against the official task tests with a custom worker, not the original official evaluation CLI. All 20 canonical solutions passed before evaluation. The worker uses restricted pure-Python syntax/imports/builtins, a Windows job with 256 MiB per-process memory and one-process limit, and a six-second timeout. This is a restricted evaluator, not a claim of a general-purpose OS security sandbox. The one rejected 35B output was invalid syntax after reaching the output cap, not a valid solution excluded by the allowed-import policy. Both models reached the output cap on HumanEval/129. These historical results are thinking-OFF only; see the later matched-budget comparison below for ON/OFF.

Generation speed is total llama-server predicted tokens divided by total predicted milliseconds, excluding prefill; response latency is measured wall time. Hermes retained the same user's configuration with thinking enabled and 12 tool rounds maximum. Tests were JSON read/echo/write, CSV paid/refund aggregation, and an interval-merging bug fix using patch. Artifacts, required tools, actual terminal output/exit status, input preservation, and session model/local endpoint were independently checked against state.db.

The initial JSON/CSV prompts did not specify output key/value shapes precisely enough. Initial strict results were 2/3 for each model, with different schema failures despite correct arithmetic. The runner was corrected to provide explicit schemas, then **both models reran both affected tasks**. Final scores use those clarified attempts and the unchanged original repair/HumanEval attempts. The original results remain available; do not present the protocol correction as retries that estimate pass@k, or silently treat the ambiguous initial attempts as unambiguous model errors. Memory figures cover the worst sampled value across both runs.

One trial per task, a small subset, fixed model order (4B then 35B), and uncontrolled app/thermal variation limit inference. These are short tasks, not near-64K histories, long reasoning, broad agent autonomy, or real Linux/SSH tests. Available RAM and system GPU usage are sampled, not model-only allocation or exact peaks.

## Benchmark choice

HumanEval is a classical coding indicator; its upstream repository was marked deprecated/unmaintained in October 2026. BFCL targets function calling; Terminal-Bench targets terminal-agent work using sandboxed task environments. Docker was not available on the inspected PATH, and no container runtime was installed just for this comparison. Choose the benchmark for the user's question rather than treating this small HumanEval subset or three custom tasks as a universal suite.

Primary references: [HumanEval](https://github.com/openai/human-eval), [BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html), [Terminal-Bench](https://github.com/harbor-framework/terminal-bench).

## BFCL tool-calling subset (2026-10-29)

Evidence: `C:\LocalLLM\hermes\benchmarks\bfcl\comparison-20261029-142528\results.json` and `report.html`; runner `C:\LocalLLM\hermes\benchmarks\bfcl\run_comparison.py`. Upstream Gorilla commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`. Official BFCL v4 datasets: simple_python, multiple, parallel, irrelevance; choose 20 row indices independently per category with `random.Random(42)`, sorted, for 80 identical cases per model. File hashes and selected IDs are saved.

| Metric | 4B Q4_K_M | 35B UD-Q3_K_M |
|---|---:|---:|
| Single tool | 20/20 | 20/20 |
| Selection among candidates | 19/20 | 18/20 |
| Multiple invocations (parallel category) | 16/20 | 18/20 |
| No-call / irrelevance | 17/20 | 16/20 |
| Overall selected cases | 72/80 | 72/80 |
| Median response | 1.10 s | 3.38 s |
| Total generation-request wall time | 152.67 s | 370.74 s |
| Aggregate generation speed | 72.38 tokens/s | 37.68 tokens/s |
| Sampled minimum available system RAM | 17.612 GiB | 4.810 GiB |
| Sampled maximum system GPU memory | 5,003 MiB | 7,401 MiB |

This comparison used native OpenAI-compatible tool_calls from llama-server, the original question messages, no additional system prompt, thinking off, temperature 0, seed 42, 1,024 output tokens, tool_choice auto and parallel_tool_calls true. Same established 64K runtime profiles as above; 4B then 35B. No tools were actually executed: this is not a Hermes agent workflow or external-action test. Both models stopped after evaluation and all original configuration hashes remained unchanged.

The pinned official Python AST checker is imported without scoring changes. The full upstream model registry imports numerous provider SDKs; the lightweight adapter supplies only a local registry entry with `underscore_to_dot=True`. It compiles the two unchanged official `_cast_to_openai_type` / `convert_to_tool` function definitions to perform the same OpenAI-schema conversion. This avoided installing the full BFCL dependency stack into Hermes. Eighty golden responses and negative controls passed before generation. Questions/ground truth align by row index, matching the upstream eval runner. Nested dictionary golden fixtures need their inner lists of acceptable values resolved to a representative value; don't send those option lists as actual argument values.

Irrelevance strictly requires zero emitted tool calls; malformed calls fail rather than being credited as abstention. Both models emitted zero malformed outputs, so that stricter rule did not affect this run. Each model hit the output cap once on an irrelevance item; the no-call score measures function abstention, not whether the plain-language response was complete. Python AST checks compare allowed function names/arguments and expected call multiplicity; they do not execute functions to establish semantic equivalence of alternate batching strategies.

These are stratified subset results using a local adapter, not the full official BFCL CLI/leaderboard score. Neither model is uniformly better: 35B improved parallel invocations but made different candidate-selection and abstention errors, with an overall tie. A simple concrete error in the 4B pipeline was turning the requested factorial inputs 5, 10, 15 into calls for 510 and 15; 35B got this case right. Avoid claiming all errors originate inside the model rather than the combined model/template/parser pipeline. No thinking-on, multi-turn, external execution, or statistical repeatability study was run.

## HumanEval matched-budget thinking ON/OFF (2026-10-29)

Evidence: `C:\LocalLLM\hermes\benchmarks\thinking-comparison-20261029-174343\results.json`, `report.html`, per-case raw responses and `memory.jsonl`. Runner: `thinking_comparison.py`; renderer: `render_thinking_report.py` in the same benchmarks root. This reuses the cached official dataset, identical seed-42 selected 20 tasks, prompt normalization and the existing Windows restricted grader. Twenty canonical solutions passed before generation.

| Configuration | OFF passed | ON passed | OFF median | ON median | ON cap hits / no final code |
|---|---:|---:|---:|---:|---:|
| Qwen3.5-4B Q4_K_M | 14/20 | 6/20 | 2.09 s | 56.79 s | 13 / 12 |
| Qwen3.6-35B-A3B UD-Q3_K_M | 17/20 | 19/20 | 5.55 s | 53.77 s | 1 / 1 |

Both modes and models used max_tokens 4096, a 240-second request timeout, temperature 0.6, top_p 0.95, top_k 20, min_p 0, presence_penalty 0, repeat_penalty 1 and seed 42. These are common precise-coding sampling values documented in the [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) and [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) cards, applied equally to ON and OFF rather than optimizing each mode separately. Existing daily/large 64K profiles were retained; model order was 4B then 35B, with OFF/ON order alternating per task. This is raw code generation, not a Hermes tool workflow.

Actual mode separation was verified for each model with warmups and scored responses: ON returned nonempty `reasoning_content` in all 20 cases, OFF in zero. For llama.cpp b11946, setting `LLAMA_ARG_THINK=deepseek` only in the launched process environment separates reasoning from final content; `chat_template_kwargs.enable_thinking` selects the mode. Inspect actual response fields rather than treating a requested switch as proof. Thinking consumes the shared output budget. Grade only final content: never salvage code from unfinished reasoning. API reasoning-token counts were absent throughout; retain null and do not infer them from character counts. API completion totals (OFF/ON) were 4,476/73,037 for 4B and 4,453/42,852 for 35B, including the total generated output rather than a separately measured reasoning count.

Failure categories: 4B OFF had five test failures and one guard rejection; ON had twelve exhausted-before-final-code, one syntax error after a cap hit and one test failure. 35B OFF had two test failures and one guard rejection; ON's only failure exhausted its output before final code (HumanEval/129). The OFF guard rejections were `import sys` on 4B /129 and `operator.mul, add` on 35B /8. The latter is a conventional sum/product implementation excluded by the fixed import allowlist, so the score includes evaluator-policy effects and is not pure semantic correctness. Preserve this category separately; do not silently expand the grader only for a favorable result. Paired counts (both-pass, ON-only, OFF-only, both-fail): 4B 5/1/9/5; 35B 16/3/1/0.

Aggregate predicted generation speeds OFF/ON: 4B 73.56/72.28 tokens/s, 35B 39.17/38.96 tokens/s. Request wall-time totals OFF/ON: 4B 62.77/1012.42 seconds; 35B 133.15/1119.06 seconds. Sampled minimum available RAM was 17.110/4.876 GiB and maximum system GPU usage 5,003/7,349 MiB for 4B/35B. No memory guard stop or crash occurred. All test-owned model processes were stopped; daily/large profile and Hermes config hashes stayed unchanged.

Protocol revision is recorded explicitly: greedy temperature-0 pilot `thinking-comparison-20261029-173548` was stopped after eight 4B ON cases, six with no final code at the cap. Its raw responses remain archived and are excluded from final scores. After consulting both model cards, the complete comparison restarted under the common sampling parameters above; this was not a selective per-task retry. The historical OFF-1024 results above remain unchanged but differ in both sampling and budget, so use the new OFF-4096 control when assessing ON.

Under this specific 4096-token budget, 35B ON improved measured restricted-grader success while 4B ON mostly consumed the budget before answering. This does not prove 4B reasoning is intrinsically worse: a larger output budget or explicit reasoning budget is an untested future experiment, not an observed remedy. Twenty tasks, one sample per condition, different generations/quantization/placement, fixed model order, sampled memory and the grader allowlist limit generalization. Do not present 19/20 as a full official HumanEval score.

### Thinking effort versus budget

Later saved `/props` from `context64k-20261029-195220` reported `supports_reasoning_effort=false` and an empty `reasoning_effort_levels` for both installed GGUF templates. For these files, do not advertise distinct low/medium/high settings. See [hermes-windows.md](hermes-windows.md) for that probe and the 64K capacity results.

Installed b11946 `llama-server.exe --help` confirms `--reasoning-budget N` / `LLAMA_ARG_THINK_BUDGET`: -1 unrestricted, 0 immediate end, positive N a thinking-token budget. This is separate from the total output cap. It also exposes `--reasoning-effort LEVEL`, but that passes the level to the chat template; flag acceptance does not establish distinct model behavior. The official server README describes `/props.chat_template_caps.reasoning_effort_levels` as levels that render distinctly, and API `reasoning_effort` other than `none` as a template input. Installed Hermes exposes `--reasoning LEVEL` and `/reasoning`, but those controls alone do not prove these particular Qwen GGUF templates implement graded low/medium/high effort. The ON/OFF benchmark above used the default unrestricted thinking budget inside max_tokens 4096; it did not choose or compare effort levels. Positive reasoning budgets on these Qwen models remain untested. Validate actual termination and final-answer production before advertising a budget as effective. Qwen3.5's official card also says `/think` and `/nothink` prompt soft switches are not officially supported; use the verified API switch instead.
