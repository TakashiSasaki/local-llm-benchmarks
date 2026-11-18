# Phase 3 preparation and launch status

## Update: period opened and acquisition delegated

The supported foreground execution mode completed the period-002 seal:
119 terminal runs and 11,912 evidence files, with original paths unchanged.
Period-003 opened at 2026-11-12T04:36:21Z. Its current definitions are under
`experiments/period-003/`. The user subsequently authorized only the Gemma
download to the existing local Codex task. Acquisition is in progress with one
connection and zero retries; this is not yet a verified model or inference.

The complete unit suite passed: 91 tests. Repository, publication and saved
Hermes evidence checks passed. All 56 distributed runtime files matched the
period-002 runtime hashes. Environment capture is saved; Windows build revision
changed from 26300.9818 to 26300.9974. No claim of identical speed across periods.

The Gemma first attempt uses 28 GPU layers, F16 KV and 65,536 context tokens.
BFCL uses 4,096 output tokens and HumanEval 16,384, retaining prior datasets,
samplers, seed and grader. This conservative placement is not a maximum-fit claim.

## Earlier preparation checkpoint

The user requested a third period with no automatic retries. Connectivity to
tufa15 was restored on 2026-11-12. No new model inference or model download has
started. The active registry is still period-002; period-003 is not yet open.

`configs/phase3-first-attempt-plan.json` records the four researched assets,
immutable revision candidates, exact sizes/hashes and current blockers.
Gemma 4 E4B Q4_K_M is the first candidate. Its pinned GGUF predates an upstream
tokenizer fix, which is disclosed rather than silently represented as current.

## Comparability and safety

- Preserve BFCL80 and seeded HumanEval20 datasets, existing prompts, sampler,
  seed and standard-windows-v1 HumanEval grader. Retain 65536 context tokens.
- Proposed output caps are BFCL4096 and HumanEval16384, different from period002.
  Report these conditions and output-cap hits explicitly; do not merge scores.
- `benchmarks/humaneval.py` now accepts `--context` and `--max-output`, retaining
  old defaults of65536 and64000. No old run or archived source was edited.
- Each condition gets a new run directory. No rerunning failed requests,
  automatic fallback, precision reduction, retry, or response repair.
- Observe native thinking switches before labeling on/off. Harmony reasoning
  for gpt-oss does not imply a genuine no-thinking mode.
- MTP stays off until model, GGUF and runtime support are independently verified.
- One owned server at a time; leave any existing server untouched. Preserve at
  least3GiB physical RAM and32GiB free disk, and target GPU use below7676MiB.
- Preserve all old weights, download fragments, records and unpushed commits.

## Blockers and resumption

1. Access to `huggingface.co:443` from the selected execution environment was
   explicitly denied by network policy during metadata verification. No alternate
   route was used. Resume only with permitted access or user-provided local files.
2. The supported period002 closure command did not leave a completed seal.
   Synchronous commands yielded, and later checks observed no running Python
   process, no closure file and an unchanged registry. Hidden background logs
   were empty. Outcome of process execution was not successfully captured.
   Recheck state before doing anything; do not manually bypass period closure.
3. Free space was46,043,574,272 bytes. Only the first4,977,171,584-byte Gemma
   download fits while preserving32GiB. Gemma plus Bonsai already exceeds that
   allowance. Additional storage is needed for the full comparison.

Once unblocked, verify pinned file metadata, available space and actual hashes,
seal period002 with its supported tool, open period003 with start_period.py,
capture current runtime/dependency hashes and hardware, then start one explicitly
recorded first-attempt run. The original downloader uses curl retry5, so it must
not be used unchanged under the new zero-retry policy.

No commit, push or publication has been performed for this preparation.
