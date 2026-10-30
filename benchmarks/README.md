# Maintained benchmark drivers

Add new measurement programs here. Shared logic belongs in `src/local_llm_benchmarks/`; test data belong in versioned `datasets/`; outputs belong in new `runs/<run-id>/` directories. See `docs/WORKFLOW.md`.

`bfcl.py` preserves the pinned 80-case protocol and native API grading from the original study, but uses repository-relative data/source locations and an already running endpoint. It records the server metadata and actual reasoning, checks context, saves each raw response before grading, and supports resuming unchanged experiments. Its behavior is tested by replaying saved answers, not by silently running fresh model inference.

Older Windows/Hermes-specific runners remain available under `artifacts/local-llm/scripts/` and `artifacts/local-llm/hermes/benchmarks/` as frozen measurement evidence. They are not the default editing location for future experiments.

Actual Hermes tool roundtrips and MCP transport checks belong in `integrations/hermes/`; they use the same `runs/<run-id>/` result layout with an explicit experiment type and harness. BFCL scores do not by themselves establish agent compatibility.
