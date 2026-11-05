# Pinned HumanEval execution

`execution.py` is unchanged from OpenAI HumanEval commit `b9453e8f1865df0a0057a1383767caa400acfbcf`, under its accompanying MIT license. SHA-256 values are in `manifest.json`.

Period 002 uses the unchanged official tests with full generated modules, Python builtins and standard library imports. The Windows adapter replaces the POSIX signal watchdog and multiprocessing manager with a parent wall timeout and Windows JobObject (6 seconds, 256 MiB, one process). It passes an empty prompt to upstream `unsafe_execute` because the saved extracted code already contains the full function/module, retaining the existing extractor and request protocol. Upstream IO capture and reliability guard are retained. The guard is not an OS security sandbox; JobObject supplies resource/descendant limits. This is a documented standard-test Windows adaptation, not EvalPlus or the exact official Linux environment.

The previous restricted AST/builtin worker stays available only as a separately labeled legacy replay for period-002 responses. No old scores or period-001 sources are replaced. Canonical controls, false-answer and timeout controls must pass in the actual benchmark Python before main collection. Every response retains final-code extraction, primary result and legacy replay separately.
