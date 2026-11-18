# Large historical JSON archives

Five historical BFCL result JSON files are stored as adjacent `.json.xz` files to fit GitHub file limits. The original JSON files remain locally unchanged and are ignored by Git. Decompress each archive beside itself before tools that expect the JSON path are run. The SHA-256 below is for the decompressed original. Never overwrite an existing JSON; verify it matches first.

- `runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v7-score-20261113/workspace/combined-results/local-gemma4-f7-prompt/multi_turn/BFCL_v4_multi_turn_long_context_result.json`: `4e380fc7d08e47c7670fe42cb627d7908f29df988a9a721e6a0a7d8f7f569c92`
- `runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v7-score-20261113/workspace/combined-results/local-gemma4-f7-prompt/multi_turn/BFCL_v4_multi_turn_miss_func_result.json`: `b5d104bc29b9df7cba736bd44b316955e869a9b54857cae47ade55d5e8eb4051`
- `runs/period-004-bfcl-f7-gemma4-multi-turn-aggregate-v7-score-20261113/workspace/combined-results/local-gemma4-f7-prompt/multi_turn/BFCL_v4_multi_turn_miss_param_result.json`: `89b95c1c5f4b1641d59bb7501ea9ea980cff0b1490ca31a7f3e008702aac5737`
- `runs/period-004-bfcl-f7-gemma4-multi-turn-pending-v7-20261113/raw/bfcl-results/local-gemma4-f7-prompt/multi_turn/BFCL_v4_multi_turn_miss_func_result.json`: `84159279ec82db27dd75dfc1485573589ab21641e5ea45a0832cc265d0d3f86d`
- `runs/period-004-bfcl-f7-gemma4-multi-turn-pending-v7-20261113/raw/bfcl-results/local-gemma4-f7-prompt/multi_turn/BFCL_v4_multi_turn_miss_param_result.json`: `53d676539762e047ebc9d4f4c5f23c36d315542915cf4cbfe8b1c7531964fa9b`

Example (Python): `python -m lzma` is not a CLI; use `lzma.open(archive, "rb")` and stream to a new file opened with `"xb"`, then verify SHA-256.
