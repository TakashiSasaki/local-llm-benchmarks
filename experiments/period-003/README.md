# Phase 3: Gemma, gpt-oss, Qwen3.8 and stock Bonsai first attempts

Period: `period-003`. New run IDs must start with `period-003-`. Record environment and comparability decisions before inference. Results remain in `runs/` with explicit period membership.

## First attempt

Gemma 4 E4B IT Q4_K_M was acquired and its full SHA256/byte count verified on
2026-11-12. The benchmark owner started at 04:42:09 UTC as
`period-003-gemma4-e4b-q4km-first-20261112`. Launch is not a completed result.
Read that run's manifest, logs, raw responses and cleanup record for actual state.

The other three candidates are recorded in `models/` but not downloaded or run.
Additional storage is needed while retaining the existing 32 GiB disk reserve.
No old model weights or download fragments were removed.

## Protocol and differences

- Same BFCL80 and seeded HumanEval20 inputs, primary graders, prompts and samplers.
- Same llama.cpp b11960 CUDA 12.4, verified across 56 distributed runtime files.
- Same 65,536 context tokens, F16 KV, one slot, eight threads and MTP off.
- New output limits: BFCL 4,096 and HumanEval 16,384 instead of 64,000.
- Native thinking OFF and ON are only accepted after observing the mode.
- Conservative Gemma placement: 28 GPU layers, no CPU MoE override.
- Windows build revision is now 26300.9974, previously 26300.9818.
- No automatic inference retry, failed-condition restart, fallback or repair.
- Memory guard retains 3 GiB physical RAM. GPU admission limit is 7,676 MiB.

The fixed-length speed probe is separate from the 200 requested capability
answers. Scores from the two periods must remain separate because model,
placement, OS revision and output budgets differ. The current GGUF predates an
upstream tokenizer fix; exact asset provenance is in its model manifest.

## Validation before launch

91 unit tests passed. Repository, publication and saved Hermes evidence checks
passed. No new Hermes execution was performed. Period-002 was sealed with its
supported closure tool, preserving 119 terminal runs and 11,912 evidence files.
No commit or push has been performed for this period.
