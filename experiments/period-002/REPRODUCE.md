# Reproducing period 002

This recipe keeps models and runtime binaries **outside Git**. It distinguishes
offline evidence verification from fresh model inference. It does not restart the
historical continuation jobs, change their deadlines, or overwrite saved answers.

## 1. Offline inspection (no model download, no server, no inference)

From the repository root, with an explicit working Python executable:

```powershell
$Py = 'D:\tools\python312\python.exe' # replace with your maintenance interpreter
& $Py -B -X utf8 scripts/reproduce_period2.py
& $Py -B -X utf8 -m unittest discover -s tests -p test_period2_reproduction.py -v
```

The first command prints a JSON plan for one BFCL OFF condition. It reads only
versioned metadata and writes nothing. Commands inside that JSON are argument
arrays, not commands executed automatically. Omit `--execute` to remain offline.
`--verify-assets` additionally hashes already-installed assets without launching
them or contacting any service. Verification can take minutes for large GGUFs.

Use `tools/verify_period2_complete.py` for the saved 1,600-answer audit and read
`reports/completed.json` in this directory for its evidence references. That audit
is not a rerun of model inference or a fresh execution of generated Python code.

## 2. Obtain the exact assets separately

Use the eight manifests listed below under `models/`. Their `url` fields contain
immutable Hugging Face revisions, not `main`; `bytes` and `sha256` identify the
complete GGUF. Planning-time `status` fields are historical, not a statement of
current installation or a reason to substitute another artifact. The other three
manifests in this directory are optional models and are not part of the 1,600.
Review each model's license before acquisition/use.

For each of the eight model IDs, this explicit **network/download** command uses
the existing resumable, hash-checking Windows downloader (requires `curl.exe`):

```powershell
$Models = 'D:\benchmark-assets\models' # must be outside this Git repository
& $Py -B -X utf8 scripts/download_pinned_model.py --manifest experiments/period-002/models/q35-4b-base.json --model-dir $Models --connections 1
```

Do not run the download command when you only want to inspect saved results.
Allow enough storage for the GGUFs, download fragments and at least 32 GiB reserve.
A failed checksum is a stop condition, not permission to update the pin. Model
availability is not guaranteed indefinitely; no download was performed to prepare
this documentation.

Runtime: Windows x64 CUDA 12.4 **llama.cpp b11960**, commit
`8642541b255bfb5dc39cd351a178be09013a55d6`. Acquire these official release archives
and verify their SHA256 before extracting into an external directory:

- https://github.com/ggml-org/llama.cpp/releases/download/b11960/llama-b11960-bin-win-cuda-12.4-x64.zip
  - 279763224 bytes; SHA256 `8d9d819261de10cc2f03921b8b79c779c5c458e21edb60c170ee30a7d462d684`
- https://github.com/ggml-org/llama.cpp/releases/download/b11960/cudart-llama-bin-win-cuda-12.4-x64.zip
  - 391443627 bytes; SHA256 `8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6`

Sources: `../period-001/assets.json` and the original runtime manifest it points
to; `environment/handoff-20261106.json` records all installed file sizes/hashes.
The new verifier hashes the distributed files against that handoff, excluding
only `runtime-manifest.json` (local installation metadata). It does not change
the frozen first-period assets. The DLLs matter: matching only the small EXE
launcher is insufficient.

Python: maintenance used CPython **3.12.14**, collection/grading **3.14.9** on
Windows AMD64. `environment/planning-20261102.json` records benchmark executable
and DLL SHA256 plus package inventory (benchmark environment: only pip 26.2.2).
The direct benchmark and this planner use the standard library and vendored
graders; there is no requirement to install the maintenance environment's large
document-processing package inventory. Obtain Python from its official project
distribution, but note that the recorded build may not match another build of
the same version. Exact-mode verification requires those recorded binary hashes;
if unavailable, document a different-interpreter experiment separately rather
than weakening pins or claiming identical reproduction. No Python binaries are
redistributed here.

```powershell
$Runtime = 'D:\benchmark-assets\llama-b11960'
$BenchPy = 'D:\benchmark-assets\python314\python.exe'
$Common = @('--model-dir', $Models, '--runtime-dir', $Runtime, '--benchmark-python', $BenchPy)
& $Py -B -X utf8 scripts/reproduce_period2.py @Common --verify-assets
```

## 3. Fresh inference in a new period

This is an opt-in, operator-supervised recipe. It collects **one condition per
invocation**, using the maintained `benchmarks/bfcl.py` or `benchmarks/humaneval.py`
driver. It deliberately does not own the server, download assets, change system
settings, automatically select a different placement, resume an incomplete run,
or copy historical answers into the new score.

Open a genuinely new period (003 below is an example; choose a later unused ID
if necessary). `scripts/start_period.py` refuses if another period is active.
Do not hand-edit the registry. If period-002 is still active, finish its reports
and offline audit, stop all collection/report writers, and close it explicitly:

```powershell
# Offline validation only; refuses any planned/running member run.
& $Py -B -X utf8 scripts/close_period.py --period period-002
# Only after reviewing the audit and final reports:
& $Py -B -X utf8 scripts/close_period.py --period period-002 --execute
& $Py -B -X utf8 scripts/close_period.py --period period-002 --verify
```

The closure command does not run inference or regrade code. It validates each
terminal run and archived source hashes, records all member run and period-local
evidence hashes in a new `closure.json`, then marks the registry closed and clears
the active period. It changes no existing run, raw answer, configuration, report
or period-001 file. Terminal failed attempts remain failed and are preserved.
Its dry-run default writes nothing. It refuses overwriting a closure. An
interruption can leave a seal or temporary registry file: inspect that state
manually rather than deleting/retrying blindly. Run this only with all writers
stopped; the final consistency check is not a cross-process writer lock.

After closure, do not regenerate period-local reports or add files there; put
later analysis in a new period. Root maintained code can evolve: its hashes at
closure are provenance, while member source snapshots remain immutable. This
later-period seal is verified with `scripts/close_period.py --verify`, not the
first-period-specific `tools/verify_period.py`. No closure is automatically
performed by the reproduction script. Execution requires the new period to be
active and open; period 001/002 are always rejected as reproduction destinations.

```powershell
& $Py -B -X utf8 scripts/start_period.py --id period-003 --title 'Fresh period 002 protocol reproduction'
$Cell = @('--period', 'period-003', '--id', 'period-003-q35-4b-base-bfcl-off-t7200', '--model', 'q35-4b-base', '--suite', 'bfcl', '--thinking', 'off', '--timeout', '7200')
$Plan = (& $Py -B -X utf8 scripts/reproduce_period2.py @Common @Cell | ConvertFrom-Json).plan
# Review the complete command. Run it in a separate terminal, keeping logs.
$ServerArgs = @($Plan.server_command | Select-Object -Skip 1)
& $Plan.server_command[0] @ServerArgs
# In the first terminal, after the server is ready:
& $Py -B -X utf8 scripts/reproduce_period2.py @Common @Cell --execute --confirm-server-command
```

The last command makes fresh requests only to `127.0.0.1:8089`. The confirmation
flag attests you started that exact model path and server command. The tool
verifies disk assets, served alias/build/context/slots/MTP, and admission memory;
API properties alone cannot prove the loaded model path or GPU placement.
**Do not reuse another person's running server** or blindly confirm the flag.
Save the server log and environment observations with the new experiment. Stop
your own server when finished; this wrapper never terminates it, even on failure.

Admission requires at least 3 GiB available physical RAM and GPU system total
no more than 7676 MiB. The original host was Ryzen 9 7940HS, 32 GiB RAM,
RTX 4070 Laptop GPU (8188 MiB), Windows 11, NVIDIA driver 555.97. These are not
universal safe placements. Monitor memory during collection; this narrow wrapper
checks admission but does **not** provide the historical orchestrator's ongoing
resource guard or capacity search. If memory pressure or an unexpected error
occurs, stop your collection/server and retain all evidence. Use a new run ID
after investigation. Do not silently fall back to a smaller context/quantization.

Repeat for every model, both suites and both thinking modes, with unique IDs:
8 models × (BFCL 80 + HumanEval 20) × OFF/ON = **1,600 new answers**. BFCL also
performs an unscored thinking-mode warmup. The old speed/preflight runs are separate
measurements and are not recreated by this capability-only wrapper.

**HumanEval security:** generated Python is executed. The Windows Job Object,
limits and reliability guard are not a security sandbox. Use a disposable,
unprivileged isolated Windows machine with no credentials/private files and
restricted outbound network. Even canonical controls execute code. Only after
preparing that environment add `--allow-generated-code` to a HumanEval execution.
The wrapper requires this explicit flag. `standard-windows-v1` is the primary
grader; the maintained driver also records a legacy replay comparison of the
same final code, not extra inference. Do not replace the grader to improve scores.

## 4. Protocol and timeout cohorts

- All eight artifacts: Q4_K_M, text-only, MTP OFF, 65536 context, F16 K/V,
  one slot, 64000 maximum output (capped to remaining context minus 32 tokens),
  batch/ubatch 2048/512, threads 8/8, no context shift, load mode `none`.
- 4B: GPU layers `all`, CPU MoE layers 0.
- 9B: GPU layers 24, CPU MoE layers 0, shared by all four models.
- 35B-A3B: GPU layers `all`, CPU MoE layers 34, shared by both models.
  These were the chosen safe shared candidates, not proven global maxima.
- BFCL: selected-80 from `datasets/bfcl/6ea5797/selected-80.json`, temperature 0,
  seed 42, top-p 1, top-k 0, min-p 0, repetition penalty 1, parallel tool calls.
- HumanEval: 20 of 164 tasks, Python `random.Random(42).sample` sorted by index,
  pinned `datasets/humaneval/b9453e8/HumanEval.jsonl.gz`; temperature 0.6,
  seed 42, top-p .95, top-k 20, min-p 0, presence penalty 0, repetition penalty 1.
- Both request native `chat_template_kwargs.enable_thinking` OFF/ON and disable
  prompt caching. The recipe retains full reasoning budget and the recorded
  `deepseek` reasoning format. Requested thinking and observed reasoning are
  distinct fields; do not infer reasoning quality solely from the switch.

The saved period-002 total combines **7200-second original requests** with
**14400-second recovery requests**, using pinned per-case references. Recovery
includes selectively reattempted pending/failed cases, not a second complete
1,600-answer test. Consult `TIMEOUT-RECOVERY-20261110.md`,
`configs/timeout-recovery-20261110.json` and the completed audit for the exact
lineage. Counts should be reconciled by unique question IDs, never by summing all
attempts or selecting the best response.

For a clean prospective comparison, choose `--timeout 7200` for all cells or
`--timeout 14400` for all cells and record that cohort in run IDs. Neither is
identical to the mixed historical selection. If comparing both timeout policies,
use entirely separate runs and disclose differences. The recipe records the
timeout and does not automatically retry or continue parser errors. Historical
deadline/shutdown controls are intentionally not imported into a new period.
Set a new execution-window policy explicitly if needed; the drivers honor it.

This recipe has offline unit tests; it was **not inference-tested** while preparing
the publication. Matching files and configuration does not guarantee identical
scores or speed across hardware, drivers, thermals or nondeterministic GPU math.

## Exact core model pins

Each linked JSON contains its full acquisition URL, byte size, license and source
metadata reference. The table below is a convenience copy; the manifests are the
machine-readable acquisition authority.

| Manifest | Hugging Face repository | Revision | GGUF SHA256 |
|---|---|---|---|
| [q35-4b-base](models/q35-4b-base.json) | mradermacher/Qwen3.5-4B-GGUF | `85aed52869ec5ef32259f80686311048bc260494` | `51eafbc127f35598c8f1d2ec58b2520d6126c7d1195c4eca26832e63a2939d39` |
| [q35-4b-abliterix](models/q35-4b-abliterix.json) | mradermacher/Qwen3.5-4B-abliterated-GGUF | `f3b61227dde75c72d12391c443efd6fa0229e0eb` | `1ec0b30c75b49223c82542caf2635a7af4edcda80d8c89759cc000d3871bf48e` |
| [q35-9b-base](models/q35-9b-base.json) | mradermacher/Qwen3.5-9B-GGUF | `9345434ae3c14ecb7b5021df007518f70b2a5231` | `9fa52e37c8293ee02cf277634f8d3a392dc3239b8ccef2315b4c8c9ef223e7fb` |
| [q35-9b-huihui](models/q35-9b-huihui.json) | mradermacher/Huihui-Qwen3.5-9B-abliterated-GGUF | `419ca34f424adbd9276c09e0271cb6b718e8da1d` | `ea1858ef4dc4b648b8dbb44612962a0333e945060dd0545ac0f28d7c4416e4b3` |
| [q35-9b-heretic](models/q35-9b-heretic.json) | darrellbest/Qwen3.5-9B-Heretic-GGUF | `e3b3d721343f3bedb938adea3c22ca8363cb3d6c` | `fd964015ec41401cfed42bf4126e0e26669a5b401c13420b771b67bddc8cd2c8` |
| [q35-9b-defiant](models/q35-9b-defiant.json) | DavidAU/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF | `d5f3139249b7ee2535c20ab81125c9a6ab0c4915` | `d33db5e583b9c9251402e876443791bc979f12af934bfb0630eadfb456279f84` |
| [q36-35b-base](models/q36-35b-base.json) | mradermacher/Qwen3.6-35B-A3B-GGUF | `ac96549d2e8b902f1a772083a33d13b5ee01fe3c` | `1f05a92890b796172f69171ac8d84d1334f1453034d712757bea4b8184a96bac` |
| [q36-35b-huihui](models/q36-35b-huihui.json) | mradermacher/Huihui-Qwen3.6-35B-A3B-abliterated-GGUF | `0693fc2b47f66380f4b568b01e05195d22edd3a2` | `fbaa4eb3e2365abffd495c5efa7df88c2b2a5088ba32cd2895973d130991e92b` |
