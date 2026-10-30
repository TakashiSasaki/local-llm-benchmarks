# Working in this repository

- Repository root on the original PC: `C:\LocalLLM\local-llm-benchmarks`. New maintained benchmark code belongs in `benchmarks/`, shared code in `src/local_llm_benchmarks/`, and maintenance commands in `scripts/` / `tools/`.
- Put each new experiment in a new `runs/<run-id>/` directory. Preserve manifest, configuration, raw responses, source snapshot/hashes and summaries. Never overwrite a completed run or relabel replayed responses as fresh inference.
- `artifacts/local-llm/` is the frozen, anonymized historical evidence. It includes original scripts and old results; do not edit it to make new experiments pass. Add new experiments under `runs/` instead. The original PC's old `C:\LocalLLM\scripts` and `runs` stay outside this Git repository as private originals.
- Shared test inputs belong in versioned `datasets/<benchmark>/<revision>/` folders with source, license and hashes. Keep pinned grader code in `vendor/`; do not silently replace a dataset or grader version.
- Models remain in `C:\LocalLLM\models`, llama.cpp in `C:\LocalLLM\bin`, and Hermes itself outside the repository. Never commit model weights, runtime binaries, credentials, personal machine configuration, `.local/`, or `.cache/`.
- Public experiment definitions go in `configs/`; private paths/settings go in ignored `.local/`. Record declared model/quantization/hash and actual served runtime/context in each run. Distinguish native thinking switches from runtime-forced OFF, and requested thinking from observed reasoning.
- Use `python -B scripts/new_run.py` to create a run. The maintained BFCL driver talks to an already running server; it does not start or replace the user's server. For LFM2.5, supply the correct external CLI budget and label `--mode-control runtime-forced` when appropriate.
- Validate with `python -B -m unittest discover -s tests -v`, `python -B scripts/check_repository.py`, and `python -B tools/verify_publication.py`. Refresh the catalog with `scripts/refresh_reports.py` and checksums with `tools/make_checksums.py`.
- `scripts/publish.ps1 -Message "..."` validates and commits. Add `-Push` when publishing the requested changes. Inspect the diff and keep unrelated user changes out of commits. No automatic periodic push is configured.
- Preserve `.gitattributes`: archived dataset/evidence bytes must not be changed by Git newline conversion.
