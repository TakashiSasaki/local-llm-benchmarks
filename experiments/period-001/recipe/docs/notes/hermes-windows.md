# Native Windows Hermes integration

Recorded 2026-10-28. Inspect current files and live server state before reuse.

## Installation and entry points

- Hermes Agent v0.22.5, source commit `bf0203a794a07aac3ff764972ab9087baa4e4f4e`, PM-managed Python 3.14.9. This release's lower Python requirement also supports old updater entry points; use PM's selected interpreter for the application.
- Integration root: `C:\LocalLLM\hermes`. Start with `installation.json`, `runs/verification.json`, `profiles/daily.json`, `profiles/large.json`, and `model-manifest.json`.
- `bin/hermes-local.cmd` starts the daily server and interactive CLI. `--status`, `--stop`, `--start-only`, `--continue`, and `--model large` are supported. `bin/hermes.cmd` delegates a bare `hermes` to this launcher and forwards subcommands to Hermes itself.
- The desktop shortcut is `Hermes - Local Qwen`. The working directory is `C:\LocalLLM\workspace\hermes`; that directory does not provide an OS sandbox.
- `server.py` reuses `C:\LocalLLM\scripts\server.py` with an isolated module root. Server state, manifests, profiles and logs live under the integration root. It does not replace the historical evaluation profiles or original model manifest. Inspect the shared helper if its implementation changes.
- The server stays running after the chat closes. Use the integration's stop command to release its RAM/GPU memory. It refuses to stop a differently selected profile, and the underlying helper checks process identity. Do not use an unrelated server's stop command.

In this packaged Codex session, writes to the logical `%LOCALAPPDATA%\hermes` resolved to `C:\Users\benchmark\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\hermes`. The actual source/home/launcher paths are recorded in `installation.json`. The supplied launchers use those paths and set `HERMES_HOME` explicitly. Inspect resolved paths and PATH exposure instead of assuming a logical AppData path is the external launcher location.

The command launcher reads its UTF-8 JSON through Windows PowerShell 5.1 with explicit `-Encoding UTF8`. Without it, the Japanese OneDrive desktop path in the manifest was misdecoded and JSON parsing failed. The corrected launcher was checked with machine/user PATH entries only, without Codex's extra process PATH.

## Daily model and limits

- Daily model: `Qwen3.5-4B-Q4_K_M.gguf`, 2,740,937,888 bytes, from `unsloth/Qwen3.5-4B-GGUF` revision `e87f176479d0855a907a41277aca2f8ee7a09523`.
- SHA-256: `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`. Download size and digest were checked. Apache-2.0 was verified against `Qwen/Qwen3.5-4B` revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- Existing llama.cpp CUDA 12.4 b11946, full GPU model placement, F16 KV, `--jinja`, one slot, context 65,536, configured server output limit 4,096. `/props` verified the model path, build, alias and per-slot context. The API is `http://127.0.0.1:8089/v1`.
- A post-run sample showed about 16 GiB available RAM and 5,226 MiB system GPU use. These are individual samples, not measured peaks or model-only allocation.
- The successful tool conversation used about 10K context. No 64K retrieval-quality test or extended autonomous workflow was established for this 4B profile.
- The optional large profile retains Qwen3.6-35B-A3B UD-Q3_K_M and the separately established 64K placement. An initial Hermes trial failed because Bash was missing; available RAM was observed around 1.29 GiB. No OOM was observed. Daily 4B was selected for headroom. A later successful 35B Hermes tool trial is recorded below; it does not establish long-workflow stability.

## Reusable installation findings

1. Native Windows file tools need Bash, including `read_file` and `write_file`. A successful install and `hermes --version` did not prove shell readiness. `hermes pm install git` installed the managed Git for Windows/Bash and resolved `No shell found`. An ambient Git executable alone did not satisfy this run.
2. PM owns the dependency environment. The tested source route was an official tagged checkout, `python -m pm.cli install --without agent-browser --without cua-driver`, then `python -I -B -X utf8 hermes_cli/source_completion.py --source <checkout>`. These choices omitted the optional browser/computer-use packages. Prefer the existing installation for follow-up work; do not reinstall or run raw pip/uv into it as routine repair.
3. This CLI uses the local gateway transport. Although help listed `--run-budget`, the tested gateway path rejected it and directed configuration through `agent.run_budget_seconds`. A resumed session rejected a changed `--max-turns`; omitting that override resumed successfully with its original policy.
4. A noninteractive PowerShell `-Command` request was blocked by the default single-query approval policy. The client still returned exit code 0 and the model reported completion after writing a correct arithmetic result. Inspect tool results and artifacts independently; client exit status and plausible final text are insufficient.
5. In interactive resume, the correctly quoted, read-only PowerShell command was auto-approved by Hermes smart approval and actually returned output `89`, exit code 0. No global approval bypass was enabled. A stale-write guard then refused overwrite; the model read the current file and used `patch` successfully.

Verified basic flow: file read → local model structured tool call → PowerShell result → file update, plus persistence/resume of the same session. The final artifact matched the independently calculated expected JSON. The evidence is in `runs/verification.json` and the referenced test session in Hermes `state.db`. This establishes basic integration, not a general model success rate.

Official references to recheck for later versions: [Hermes providers](https://hermes-agent.nousresearch.com/docs/integrations/providers), [installation](https://hermes-agent.nousresearch.com/docs/getting-started/installation), [package management](https://hermes-agent.nousresearch.com/docs/reference/package-management), [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B).

## Hermes as an MCP server (2026-10-29)

In v0.22.5 this feature moved from `hermes mcp serve` to the official `mcp-serve` plugin. Installed and enabled via `hermes plugins install mcp-serve --yes-deps --enable`, pinned by the catalog to official-plugins commit `6389dd08c1e485db708688c69e42c2b7a7360f4e`, plugin version 1.0.0. [Official README](https://github.com/NousResearch/hermes-official-plugins/tree/main/mcp-serve).

The official server is stdio-only and exposes ten messaging-bridge tools: conversation listing/details, message reading/sending, attachments, event polling/waiting, channel listing, and approval listing/responding. Reading does not require the messaging gateway or an LLM; sending needs the gateway and configured platform connections. It does not expose a direct prompt/task delegation API to the Qwen agent. Optional `--tools` adds an allowlist of web/browser/media/skills tools, not terminal/file/kanban/delegation. Do not enable a gateway, model, or broad tool surface merely to read the MCP bridge.

Codex entry `[mcp_servers.hermes]` was added to `C:\Users\benchmark\.codex\config.toml`, using the actual `installation.json` Hermes launcher with args `["mcp-serve"]`, workspace cwd, and the actual `HERMES_HOME` plus UTF-8 environment settings. Existing settings were preserved and backed up under `C:\LocalLLM\hermes\runs`. `mcp_setup.py` performed a real stdio initialize, tools/list (ten exact bridge tools), and read-only conversations_list/channels_list calls; evidence is `runs/mcp-verification.json`. The PM-managed base interpreter alone has no `mcp` import; the normal Hermes launcher activates the selected dependency environment. Do not install packages into the base interpreter to test this server.

Local protocol success and Codex configuration acceptance are separate from the active conversation's tool transport. After registration, the tools appeared in the Codex tool inventory, but initial app-routed calls returned `tunnel_client_not_seen`; verify the live app call or report the remaining reconnect step rather than claiming end-to-end app success from the local test.

## Successful 35B Hermes trial (2026-10-29)

Evidence: `C:\LocalLLM\hermes\runs\large-hermes-20261029-133137\report.json`, memory JSONL, Hermes stdout/stderr, and saved session `local-cb4ed3549941d02ccf517cebb9d472e26b045d2341b45bf809019b56dd14d554`. The existing large profile used Qwen3.6-35B-A3B UD-Q3_K_M, b11946 CUDA 12.4, 65,536 context, F16 KV, one slot, first 30 MoE layers on CPU, and eight threads. Served identity/context and the session's local endpoint/model were checked.

One conversation successfully used `read_file` to read a fresh ticket and four numbers, `terminal` to run `echo HERMES35B_TERMINAL_OK` (actual output, exit 0), and `write_file` to write an independently checked JSON result with count 4 and total 520. All three actual tool results were verified in state.db; the input was unchanged. No approval bypass was enabled. Model load took 15.65 seconds; the Hermes command took 54.6 seconds. The maximum observed slot contained 9,026 tokens, including generation; this was not a 64K workload. Prompt-evaluation timing token counts exclude cached tokens and must not be reported as full context sizes.

Available RAM started at 20.456 GiB and reached a sampled minimum of 4.291 GiB; sampled maximum system GPU usage was 7,357 MiB out of 8,188 MiB. The monitor sampled about every two seconds (GPU probes could take longer) and would stop below 1 GiB for three consecutive samples. No guard interruption, OOM, or crash occurred. After stopping the model, available RAM was 20.544 GiB. The test-started gateway was also stopped. Daily 4B remains the default; only the large profile's descriptive status/parser metadata was updated. Launch large explicitly with `hermes-local --model large`; stop it with `hermes-local --model large --stop`.

This establishes a short native-Windows Hermes tool roundtrip with this exact 35B quantization and placement. It does not establish repeated-run reliability, large outputs, near-64K agent history, concurrent models, or stability with other memory-heavy apps. Recheck free RAM and server ownership on each new use.

## 64K profile capacity and fresh Hermes smoke checks (2026-10-29)

Evidence: `C:\LocalLLM\hermes\runs\context64k-20261029-195220\results.json` and `report.html`, saved API requests/responses, model props, Hermes stdout/stderr and memory JSONL. Reusable runners: `C:\LocalLLM\hermes\benchmarks\context64k_probe.py` and `context64k_report.py`. Both existing daily/large profiles actually served 65,536 context per slot with one slot; the Hermes configuration's context_length was also 65,536. No ordinary profiles or Hermes configuration changed (hashes checked).

| Measurement | Qwen3.5-4B Q4_K_M | Qwen3.6-35B-A3B UD-Q3_K_M |
|---|---:|---:|
| First raw chat input tokens | 63,779 | 63,779 |
| First raw request wall time | 22.32 s | 121.92 s |
| Correct markers at 10%, 50%, 90% | 3/3 | 3/3 |
| Follow-up input tokens | 63,873 | 63,873 |
| Follow-up wall time / answer | 0.14 s / OK | 0.35 s / OK |
| Separate short Hermes read/write smoke | passed, 23.02 s | passed, 42.03 s |
| Sampled minimum available RAM | 17.740 GiB | 5.011 GiB |
| Sampled maximum system GPU use | 5,001 MiB | 7,357 MiB |

The synthetic log includes three marker values among ordinary rows. The raw test uses thinking OFF, output caps 512 then 128, and a structured `record_markers` call followed by a deterministic local acknowledgement, with no external function execution. Actual rendered/tokenized prompt counts matched API usage.prompt_tokens exactly. The first response generated 68 tokens with no cached input; the follow-up generated 2 tokens and reported 63,846 cached input tokens. These follow-up times measure prefix reuse, not processing a fresh 64K input again. No input truncation was needed; leave room within context for output and tool messages instead of submitting a full 65,536-token input.

Hermes tests were separate short conversations with normal thinking-ON settings, not Hermes histories filled to 64K. Each read a unique ticket and four amounts with actual read_file, then wrote exact ticket/count=4/total=520 JSON with actual write_file. Artifacts, unchanged input, local session model/endpoint and state.db read/write results were verified; writes reported verified=true. Session IDs are in results.json. Both models and the test-started gateway were stopped; no guard interruption, OOM or crash occurred.

This establishes current 64K server capacity, one simple near-limit retrieval/tool continuation, and basic Hermes compatibility for both configurations. It does not establish sophisticated long-context reasoning, a sustained near-64K Hermes workflow, repeated reliability, or 64K generated output. The Hermes minimum is 64,000 context tokens, not an output-token requirement; ordinary 65,536-context / 4,096-output profiles already meet that configuration minimum. If a user asks to test "64K" after discussing output caps, distinguish total context from generation budget before choosing the test.

Both saved `/props.chat_template_caps` also reported supports_reasoning_effort=false and reasoning_effort_levels=[] for these exact GGUF templates. Do not present low/medium/high as distinct verified settings for these installed files. ON/OFF and a server thinking-token budget are separate mechanisms; the latter still needs its own behavioral check.
