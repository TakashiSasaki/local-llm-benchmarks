# Gemma 4 E4B native MTP support check

Checked on tufa15 on 2026-11-12. No inference or ON/OFF benchmark was started.

The installed file is gemma-4-E4B-it-Q4_K_M.gguf, 4,977,171,584 bytes. The first 15,826,723 bytes were read again and their SHA256 matched the saved complete GGUF header inventory: 5b853e77ce867da84d0d7ee6f1748eadd3633e29564212cac5241fd14217ea31.

The header declares architecture gemma4, 42 blocks and 720 tensors. All block indices are 0 through 41. There are no metadata keys or tensor names matching MTP, nextn or draft. The six non-block tensors are output_norm.weight, per_layer_model_proj.weight, per_layer_proj_norm.weight, per_layer_token_embd.weight, rope_freqs.weight and token_embd.weight.

The installed llama.cpp b11960 help advertises draft-mtp as a general speculative-decoding option. A generic option is not evidence of support for this architecture or of MTP weights in this file. Consequently there is insufficient support evidence to run a genuine native MTP ON comparison with this asset. The observed 25.82 token/s OFF speed must not be labeled an ON/OFF effect.

An attempt to read the pinned upstream gemma4.cpp source was blocked by network policy. No alternate route was used. Runtime architecture-specific support and current upstream model documentation therefore remain unverified. Do not generalize this finding to all Gemma models or future releases. Separate draft-model or n-gram speculation is not native MTP and would require a separately labeled study.

Evidence: runs/period-003-gemma4-e4b-q4km-first-20261112/configs/gguf-header.json and the installed executable's --help. Historical run evidence was not edited.
