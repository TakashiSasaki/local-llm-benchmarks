# Period 002: API timeout recovery, 2026-11-10

The original plan explicitly configured a 7,200-second API wait in `configs/plan.json` and `PLAN.md`. This is a client waiting limit, separate from the 64,000-token output cap, 65,536-token context, grader timeout and the cancelled operational finish-by deadline.

At 18:27 JST on November 10, the Heretic 9B BFCL thinking-ON request `irrelevance_139` reached that waiting limit. The last server log observation was 63,041 generated tokens; there was no final API response for that attempt. The failed run and its logs remain unchanged. Resource guards did not trigger and the owned server was stopped.

The user explicitly requested extending the timeout and resuming that question and the remaining experiment. The recovery uses a 14,400-second API wait for the remaining 647 answers. It retains the pinned models/runtime, samplers, prompts, output/context limits, thinking modes, graders and matched placement rules. Defaults for unrelated driver invocations remain 7,200 seconds.

## Evidence and scope

- Original failed parent: `period-002-resumption-20261110`.
- Recovery parent: `period-002-timeout-recovery-20261110` (consult its manifest for actual execution status).
- Checkpoint: `configs/timeout-recovery-20261110.json`, with 953 saved answers referenced by hashes and canonical IDs.
- BFCL continuation: `configs/q35-9b-heretic-bfcl-on-continuation-20261110.json`. The 73 original BFCL ON answers remain in their source run. Only seven missing IDs are generated, beginning with `irrelevance_139`.
- Remaining queue: Heretic BFCL ON 7 + HumanEval OFF/ON 20 each, Defiant 200, ordinary 35B 200, Huihui 35B 200. Completed conditions are not repeated.

The 953 earlier answers were collected under the original waiting limit; the 647 recovery answers use the longer limit. Combined scores are explicitly references plus fresh responses, not a uniform new 4-hour rerun. Keep the timeout difference visible in comparisons, especially for answers completed beyond 7,200 seconds. An output-cap response with no final answer remains a failed/empty result; extending API wait does not remove the token cap.

The shared orchestration lock, one-server port guard, pinned-source checks, manual hold at admission boundaries, RAM/GPU checks, 32 GiB model-disk reserve, and owned-process cleanup remain. A new failure stops the queue without automatic inference retry. No OS shutdown is scheduled.
