# LFM3 on this Windows PC

Recorded 2026-10-30 on the existing Ryzen 9 7940HS / 32 GiB RAM / RTX 4070 Laptop 8 GiB PC, NVIDIA driver 555.97. Recheck files and live server ownership before reuse. The original section describes QAD-Q4_0; the later Q8_0 trial is recorded below. Both cover short workloads.

## Installation and provenance

- Primary evidence: `C:\LocalLLM\runs\lfm3-setup-20261030-125557\report.json`. The final trace-confirmed test is `verification-trace/verification.json` in that directory; its saved requests/responses, server props/log, memory JSONL, fixture, tool-execution record, and source ZIP preserve the test conditions.
- Runtime: official Windows CUDA 12.4 llama.cpp **v0.8.0 / b11960**, commit `8642541b255bfb5dc39cd351a178be09013a55d6`, installed at `C:\LocalLLM\bin\b11960-cuda12.4`. Both downloaded archives matched GitHub's published SHA-256. Its `runtime-manifest.json` records archive and extracted-file hashes.
- Model: official `LiquidAI/LFM3-1.7B-GGUF`, revision `bad5729bba61d076fff20d2548e62526665af215`, file `LFM3-1.7B-QAD-Q4_0.gguf`, **1,049,615,680 bytes**, SHA-256 `43a7d09a0e9cba91b63eb7052488b9564569bddfd65754d2e426465e572a7452`. Size and whole-file digest were checked. The recorded license is `lfm1.0`; source-model revision is `ac2586a34f1a1c03329dbdcdefabd8b6478ddaa7`.
- Profile: `C:\LocalLLM\profiles\lfm3.json`, alias `lfm3-1.7b-qad-q4-64k`. Model-manifest entries for the earlier Qwen, LFM2.5, and GLM variants were preserved; the LFM3 entry was appended.
- `C:\LocalLLM\runtime-current.json` records this installation. It is metadata, not a global runtime override. The original `runtime-manifest.json`, evaluation profiles, and Hermes `daily`/`large` profiles retained b11946. Select the runtime through the actual profile; do not assume that all existing launchers were upgraded.

Official references to recheck when changing versions: [LFM3 GGUF card](https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF), [model card](https://huggingface.co/LiquidAI/LFM3-1.7B), [v0.8.0 release](https://github.com/ggml-org/llama.cpp/releases/tag/v0.8.0), [b11960 binaries](https://github.com/ggml-org/llama.cpp/releases/tag/b11960). The model card at installation required b11960/v0.8.0 or newer.

## Launch and configuration

PowerShell entry points, each checked for start/status/stop:

```powershell
& 'C:\LocalLLM\run-lfm3.ps1'
& 'C:\LocalLLM\run-lfm3.ps1' -Status
& 'C:\LocalLLM\run-lfm3.ps1' -Stop
```

The web UI is `http://127.0.0.1:8089`; the local OpenAI-compatible base URL is `http://127.0.0.1:8089/v1`. Start one model at a time. This launcher uses the original `C:\LocalLLM\scripts\server.py` and root `server-state.json`, separate from Hermes state. It refuses startup when a local model process exists and refuses to stop a different managed profile. The task's test-started servers were stopped and process inventory plus an actual TCP probe confirmed cleanup.

Verified configuration: **65,536 context per slot, one slot**, CUDA0, `-ngl all`, F16 K/V cache, `--jinja`, `--fit off`, Flash Attention auto, eight generation and batch threads, batch 2,048 / microbatch 512, `--cache-ram 0`, context shifting disabled. Sampling was temperature 0.1, top_k 50, repeat_penalty 1.1, seed 42. The profile/client output budget is 4,096; smoke requests explicitly used a 2,048-token cap. Consult the profile and actual server props rather than inferring an enforced server-wide output cap from that profile value.

Thinking was enabled, and the saved responses contained nonempty `reasoning_content`. The saved template caps reported `supports_reasoning_effort=false` and no effort levels; low/medium/high were not verified for this GGUF.

## What the final smoke test established

- `/props` confirmed the exact model path, alias, build, one slot, and 65,536 context per slot.
- A short Japanese question produced a Japanese answer. This was a basic response check, not a broad Japanese-quality evaluation.
- The model emitted one parsed `read_probe_file` call with the expected arguments. The test application actually read a fresh, fixed local JSON fixture and returned its contents. The model's final JSON matched the independently checked ticket, **count 4 / total 986**, with integer values; the input file was unchanged. This was a real read-only file-tool roundtrip through the local API, **not Hermes, shell execution, or autonomous filesystem access**.
- Trace logging confirmed **25/25 layers offloaded to GPU**. Reported CUDA buffers were model 993.13 MiB, non-SWA KV 768.00 MiB, SWA KV 7.50 MiB, and compute 125.82 MiB. These component sizes are not an aggregate physical-memory peak.

| Final trace-run measurement | Result |
| --- | --- |
| Model ready time | 1.59 s; one startup, OS file cache not cleared |
| Japanese request input / generated tokens | 49 / 281 |
| Japanese request wall time | 1.63 s |
| Generation speed for that request | 177.33 token/s, including reasoning |
| Tool-call / tool-result request generation | 172.45 / 172.96 token/s, including reasoning |
| Largest smoke request input / generated tokens | 340 / 283 |
| Sampled maximum system GPU use | 2,045 MiB |
| Sampled minimum available physical RAM | 20.10 GiB |
| Sampled maximum server private memory | 2.56 GiB |

Memory was sampled four times at about two-second intervals; GPU probes can take additional time and instantaneous peaks may be missed. GPU use is the system total. These brief requests are not directly comparable to the earlier larger-model benchmarks, which used different profiles, tokenizers, workloads, and memory placement.

## Reusable operational findings and limits

- At default log verbosity 3, b11960 did not print detailed tensor placement. The first trial passed Japanese chat and the real file-tool roundtrip, but its GPU-placement check lacked log evidence. A follow-up with **`-lv 4`** confirmed 25/25 layers and all recorded checks passed. Missing placement lines at default verbosity do not establish CPU fallback.
- Windows TCP inventory briefly retained a port-8089 entry with owner PID 0 after process exit. Verify the process identity and actual TCP reachability before treating such an entry as a surviving model server; do not stop unrelated processes to clear it.
- **64K was configured and served, but not filled with a near-64K input.** Long-context retrieval, sustained workflows, concurrency and repeated reliability remain untested. Later short-prompt text benchmarks with up to 64,000 output tokens are recorded in [lfm3-64k-output-benchmarks.md](lfm3-64k-output-benchmarks.md); keep them separate from these initial smoke checks. The short API file-tool test does not establish Hermes integration; existing Hermes defaults were unchanged.
- QAD-Q4_0 and the later Q8_0 trial below were run separately. **16-bit variants remain untested.** Do not transfer measured speed, memory, or correctness results to other quantizations, modalities, runtimes, or devices.
- Reusable task runners are `C:\LocalLLM\scripts\install_lfm3_runtime.py` and `verify_lfm3_runtime.py`. Inspect before reuse. The installer expects saved pinned metadata and refuses an existing LFM3 profile; the verifier starts and stops the task-owned server and writes fresh diagnostic artifacts. Reuse the installed launcher for ordinary operation rather than reinstalling.

## Q8_0 follow-up (2026-10-30)

Evidence: `C:\LocalLLM\runs\lfm3-q8-20261030-130924\report.json`, its `verification/` subdirectory and saved launcher status records. Official `LFM3-1.7B-Q8_0.gguf` at the same repository revision `bad5729bba61d076fff20d2548e62526665af215` is 1,846,238,496 bytes; whole-file SHA-256 matched `8f6b24182258205e9e01e21f1f24a1f208c1e8115578825d202ce39976af20b6`.

Separate profile `C:\LocalLLM\profiles\lfm3-q8.json`, alias `lfm3-1.7b-q8-64k`, uses the same b11960 CUDA 12.4 runtime, 65,536 context/one slot, F16 KV and sampling settings. The QAD profile and earlier model entries were preserved. `verify_lfm3_runtime.py --profile lfm3-q8` selects it; the verifier's default remains `lfm3`.

Launch with `& 'C:\LocalLLM\run-lfm3.ps1' -Quantization Q8_0`; add `-Status` or `-Stop` for that selection. Start/status/stop were checked for Q8 and the unchanged default QAD selection. Test servers were stopped. Q8 is not the default and Hermes profiles remain unchanged.

The short Japanese response and actual read-only file-tool roundtrip completed. Parsed arguments were correct; final count 4 / total 1004 and fresh ticket matched independently, with the input unchanged. All 25/25 layers were offloaded; CUDA model buffer was 1,752.84 MiB. The Japanese request used 49 input / 245 generated tokens, took 2.25 seconds wall time and generated at **111.65 token/s including reasoning**. Five memory samples at about two-second intervals observed **2,805 MiB maximum system GPU use**, **19.38 GiB minimum available RAM**, and **3.28 GiB maximum server private memory**. Compare with the earlier QAD Japanese request's 177.33 token/s and sampled 2,045 MiB system GPU use only as brief observations; output lengths differ and tool fixtures were different random inputs.

The Q8 Japanese answer used **one sentence despite a two-sentence instruction**. The smoke's Japanese check only establishes language presence and normal completion; it does not grade complete instruction adherence. Do not infer that Q8 improved Japanese quality or tool reliability over QAD. Near-64K inputs, long workflows, repeated reliability, 16-bit variants, and Hermes integration remain untested for Q8.

## VL image tests (2026-10-30)

Evidence: `C:\LocalLLM\runs\lfm3-vl-20261030-131519\report.json`, per-profile subdirectories with saved image API requests/responses, fixtures, hashes, logs, props, memory samples and source ZIPs. Both official language-weight files were tested with the same **F16 vision encoder/projector**; 4bit/8bit describes the language weights, not every component.

Repository `LiquidAI/LFM3-VL-2B-GGUF`, revision `b36554cfd35854b06429900131730cd80f092cdb`; verified whole-file SHA-256:

- `LFM3-VL-2B-QAD-Q4_0.gguf`, 1,049,615,648 bytes: `621c455376cb96a20891697deb9975c6fb47dd5ea98ed3ad1f3b7e8f24f0b1e6`.
- `LFM3-VL-2B-Q8_0.gguf`, 1,846,238,496 bytes: `e138e54189a751d90ea8c0b236360490613ecd465d28d68fa6094d3db7fa6727`.
- `mmproj-LFM3-VL-2B-F16.gguf`, 378,996,032 bytes: `1d8e6e58eefc093e09d6332f081516e1ddbd5b35cfca7f35463fb270db230b1e`.

Profiles `lfm3-vl-q4.json` / `lfm3-vl-q8.json` use b11960 CUDA 12.4, 65,536 context per slot, one slot, F16 KV, all 25/25 language layers on GPU, `--mmproj` with that shared file, `--mmproj-offload`, `--no-reasoning-preserve`, and trace verbosity 4. Sampling: temperature 0.1, top_p 1, top_k 50, min_p 0, repeat_penalty 1.1; seed 42. Vision logs confirmed real image decoding, 384 image tokens per 768x512 image, and CUDA vision compute allocation.

Use `& 'C:\LocalLLM\run-lfm3.ps1' -Mode VL -Quantization QAD-Q4_0` or `-Mode VL -Quantization Q8_0`; append `-Status` or `-Stop` with the same selection. Start/status/stop passed for both. The default remains Text/QAD; prior profiles and model entries were preserved, and the test-started servers were stopped.

Two shared synthetic image tasks were semantically correct for both variants: an invoice's fresh code B73C29, quantity 3 and total 582, and a red circle on the left / blue square in the middle / green triangle on the right. Questions were in Japanese; text in the invoice was English. QAD returned Markdown-fenced JSON despite JSON-only instructions; grading stripped optional fences, so semantic correctness does not establish strict raw-JSON adherence.

| Image trial | QAD-Q4_0 | Q8_0 |
| --- | --- | --- |
| Correct semantic answers | 2/2 | 2/2 |
| Generation, reasoning included | 171.49–177.47 token/s | 111.12–111.42 token/s |
| Response wall times, receipt / shapes | 1.42 / 1.12 s | 2.21 / 2.45 s |
| Sampled system GPU maximum | 2,813 MiB | 3,573 MiB |
| Memory samples after model ready | 2 | 3 |

These are brief single-image smoke checks, not a quality ranking. Startup/instantaneous memory peaks may be missed. No video, Japanese-character OCR, tool/Hermes integration, near-64K input, or sustained reliability was tested for VL. The task runner is `C:\LocalLLM\scripts\trial_lfm3_vl.py`; inspect before reuse because preparation refuses existing profiles/registered assets. Initial full-file transfers were stopped when slow; bounded HTTP ranges resumed partial files and final whole-file hashes matched. This does not establish that future downloads need that workaround.
