# Gemma 4 E4B BFCL multi-turn saved-evidence scoring

Pinned BFCL checkout: f7cf7359b7ac615a0b294831c5ba2bc95ee4a000. The isolated installed package matches all 108 checkout Python files after newline normalization; the four input datasets match as well. The saved raw responses and source records were cross-checked before replay; see `../configs/evidence-verification.json` and `independent-verification.json`. No inference was run.

| Category | Correct | Scored | Dataset |
| --- | ---: | ---: | ---: |
| Base | 50 | 194 | 200 |
| Long context | 45 | 200 | 200 |
| Miss function | 43 | 200 | 200 |
| Miss parameter | 36 | 200 | 200 |

The 800 distinct dataset IDs comprise 787 ordinarily terminated cases, seven context-limit failures and six guard-interrupted cases. Ordinary termination does not imply correctness. All seven context failures count as inference errors in long-context scoring. The old case 120 is represented by a derived error result supported by its historical server log: the prior adapter did not save the failed HTTP request or response body. The six interrupted base cases are omitted, not counted as wrong; hence no complete 800-case overall accuracy is asserted. Generated overall CSV values combine missing categories and are not valid overall scores.

The pinned evaluator runs with a guarded decoder and executor and per-case allowlists; this is an adaptation and not identical to an official unmodified execution environment. The GGUF llama.cpp prompt adapter and local resource/context limits likewise differ from official leaderboard configurations. Individual score files record error details; separate score files contain the category-specific totals.
