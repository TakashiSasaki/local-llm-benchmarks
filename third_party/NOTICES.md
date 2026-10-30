# Third-party sources and licenses

The licenses below apply to their respective upstream components, not automatically to the independently authored study code. Copyright notices in source files are retained. Model weights and inference runtime binaries are not redistributed here.

| Component | Pinned source | License copy |
| --- | --- | --- |
| HumanEval data | [openai/human-eval, b9453e8](https://github.com/openai/human-eval/tree/b9453e8f1865df0a0057a1383767caa400acfbcf) | [MIT, copyright OpenAI](licenses/HumanEval-MIT.txt) |
| BFCL data, official AST checker, converter/support source snapshots | [ShishirPatil/gorilla, 6ea5797](https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8) | [Apache License 2.0](licenses/BFCL-Apache-2.0.txt) |
| llama.cpp-related historical source references, if present in archived source snapshots | [ggml-org/llama.cpp, 8642541](https://github.com/ggml-org/llama.cpp/tree/8642541b255bfb5dc39cd351a178be09013a55d6) | [MIT](licenses/llama.cpp-MIT.txt) |

No separate BFCL LICENSE or NOTICE was found under its subtree in the pinned Gorilla repository; the repository-root Apache 2.0 license is included. The official BFCL data files and HumanEval compressed dataset retain their original hashes. The publication verifier checks those hashes.

The study supplies a minimal local BFCL model-registry entry for native function-name normalization, and loads the official converter/checker definitions without provider SDKs. Source snapshots and original file hashes preserve what was used. Publication changes to other files are recorded in `publication/export-manifest.json`; they include local path redaction and removal of model-provided templates.

Model IDs, revisions, quantization names and SHA256 values are provenance, not model redistribution. Obtain the exact model files separately from the URLs in the manifests and follow the providers' licenses. Recorded model outputs are experimental evidence; this repository does not assert exclusive ownership of those outputs or endorsement by a model provider or benchmark author.
