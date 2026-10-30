# Pinned BFCL support sources

`bfcl_eval/` and `handler_utils.py` are unmodified source snapshots from Gorilla commit 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8, under Apache-2.0; see ../../third_party/licenses/BFCL-Apache-2.0.txt.

`study_adapter_snapshot.py` preserves this study's original adapter (MIT, see ../../LICENSE). Only its grader wrapper definitions are extracted; importing or running its original entry point is unnecessary. A minimal runtime-only model registry is supplied by src/local_llm_benchmarks/bfcl.py, as in the measured adapter.
