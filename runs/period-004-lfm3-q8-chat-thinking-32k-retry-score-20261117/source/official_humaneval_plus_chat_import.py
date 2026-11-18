"""Verify and archive a HumanEval+ chat replay from the offline VM."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
from statistics import median
import subprocess
import sys

from official_humaneval_plus_submit import GEMMA_SCORE, load_chat_inputs, load_retry_chat_inputs, study


def chat_metrics(collection, rows):
    all_rows = [study.load(collection / "raw" / (task.replace("/", "_") + ".json")) for task in rows]
    responses = [row["response"] for row in all_rows]
    choices = [response["choices"][0] for response in responses]
    rates = [response.get("timings", {}).get("predicted_per_second") for response in responses]
    rates = [rate for rate in rates if rate is not None]
    return {
        "median_request_seconds": median(row["seconds"] for row in all_rows),
        "sum_request_seconds": sum(row["seconds"] for row in all_rows),
        "median_output_tokens": median(row["usage"]["completion_tokens"] for row in responses),
        "median_decode_tokens_per_second": median(rates) if rates else None,
        "stops": dict(Counter(choice["finish_reason"] for choice in choices)),
        "reasoning_observed": sum(bool(choice["message"].get("reasoning_content") or choice["message"].get("reasoning"))
                                  for choice in choices),
        "empty_final_content": sum(not (choice["message"].get("content") or "").strip() for choice in choices),
    }


def retry_results(collection, plan, tasks, official, previous_scores):
    previous = study.resolve_run(plan["original_generation_run"])
    old_eval = study.load(previous_scores / "raw/evalplus-results.json")["eval"]
    cases = {}
    for task, outcome in tasks.items():
        old_row, = old_eval[task]
        new_row, = official["eval"][task]
        if task not in plan["cases"]:
            assert old_row["solution"] == new_row["solution"], task
            continue
        filename = task.replace("/", "_") + ".json"
        old = study.load(previous / "raw" / filename)["response"]
        new = study.load(collection / "raw" / filename)["response"]
        assert old["usage"]["prompt_tokens"] == new["usage"]["prompt_tokens"], task
        old_choice, = old["choices"]
        new_choice, = new["choices"]
        old_reasoning = old_choice["message"].get("reasoning_content") or ""
        new_reasoning = new_choice["message"].get("reasoning_content") or ""
        cases[task] = {
            "passed": outcome["plus_passed"],
            "base_passed": outcome["base"] == "pass",
            "previous_base_passed": old_row["base_status"] == "pass",
            "previous_finish_reason": old_choice["finish_reason"],
            "finish_reason": new_choice["finish_reason"],
            "previous_tokens": old["usage"]["completion_tokens"],
            "tokens": new["usage"]["completion_tokens"],
            "same_final_content": (old_choice["message"].get("content") or "") == (new_choice["message"].get("content") or ""),
            "same_sanitized_solution": old_row["solution"] == new_row["solution"],
            "original_reasoning_is_prefix": bool(old_reasoning) and new_reasoning.startswith(old_reasoning),
            "final_content_present": bool((new_choice["message"].get("content") or "").strip()),
        }
    capped = [row for row in cases.values() if row["previous_finish_reason"] == "length"]
    other = [row for row in cases.values() if row["previous_finish_reason"] != "length"]
    saved = len(tasks) - len(cases)
    assert saved == sum(row["base_status"] == row["plus_status"] == "pass" for entries in old_eval.values() for row in entries)
    passed = sum(row["passed"] for row in cases.values())
    return {
        "rerun_count": len(cases), "passed_on_retry": passed,
        "previously_capped": {"count": len(capped), "passed": sum(row["passed"] for row in capped)},
        "previously_not_capped": {"count": len(other), "passed": sum(row["passed"] for row in other)},
        "saved_prior_successes": saved, "combined_success_count": saved + passed,
        "combined_success_rate": (saved + passed) / len(tasks), "cases": cases,
        "replayed_prior_successes_with_changed_judgment": [task for task, row in tasks.items()
                                                            if task not in cases and not row["plus_passed"]],
    }


def import_result(collection, inputs, vm_dir, run_id, reference):
    vm_base = vm_dir.parent
    dataset = vm_base / "downloads/HumanEvalPlus-v0.1.10.jsonl.gz"
    gemma_score = study.resolve_run(GEMMA_SCORE)
    study.validate_run(gemma_score)
    sys.path.insert(0, str(gemma_score / "source"))
    from collect_results import unpack

    assert study.load(vm_dir / "exit.json")["returncode"] == 0
    assert study.load(collection / "configs/cleanup.json")["server_stopped"]
    launch = study.load(vm_dir / "launch.json")["args"]
    assert launch[launch.index("-nic") + 1] == "none"
    assert "readonly=on" in " ".join(launch)
    data, deps, python, serial = unpack((vm_dir / "serial.log").read_bytes())
    evaluator = study.load(gemma_score / "summary.json")["evaluator"]
    assert python == evaluator["python"] and deps == (gemma_score / "configs/python-requirements.txt").read_bytes()
    input_record = study.load(inputs / "inputs.json")
    retry = input_record["input_kind"] == "failed-only chat retry with saved successes"
    assert retry or input_record["input_kind"] == "final chat content"
    assert study.sha(dataset) == input_record["humaneval_plus_dataset_sha256"]
    assert study.sha(collection / "summaries/samples.jsonl") == input_record["samples_original_sha256"]
    assert study.sha(inputs / "samples.jsonl") == input_record["evaluated_solution_file_sha256"]
    if retry:
        final_outputs, plan = load_retry_chat_inputs(collection, dataset)
        assert input_record["original_score_run"] == plan["original_score_run"] == reference.name
        assert input_record["retry_task_ids"] == list(plan["cases"])
    else:
        final_outputs = load_chat_inputs(collection, dataset)
    with (inputs / "samples.jsonl").open(encoding="utf-8") as stream:
        assert list(map(json.loads, stream)) == final_outputs
    official = json.loads(data)
    assert official["hash"] == hashlib.md5(dataset.read_bytes(), usedforsecurity=False).hexdigest() == evaluator["dataset_internal_md5"]

    study.validate_run(reference)
    old = study.load(reference / "summary.json")
    old_tasks = study.load(reference / "summaries/per-task.json")
    total = len(final_outputs)
    assert total == 164 and set(official["eval"]) == set(old_tasks) == {row["task_id"] for row in final_outputs}
    tasks = {}
    code_lines = []
    for expected in final_outputs:
        task = expected["task_id"]
        row, = official["eval"][task]
        assert task == row["task_id"]
        code = row["solution"]
        if not expected["solution"].strip():
            assert not code.strip(), task
        base, extra = row["base_status"], row["plus_status"]
        assert base in {"pass", "fail", "timeout", None}
        assert extra in {"pass", "fail", "timeout", None}
        tasks[task] = {"base": base, "additional": extra, "plus_passed": base == extra == "pass",
                       "previous_plus_passed" if retry else "raw_prefix_plus_passed": old_tasks[task]["plus_passed"],
                       "sanitized_code_present": bool(code.strip())}
        code_lines.append(json.dumps({"task_id": task, "solution": code}, ensure_ascii=False) + "\n")
    sanitized = "".join(code_lines).encode()
    sanitized_hash, = re.findall(rb"(?m)^HEP_SANITIZED_SHA256 ([a-f0-9]{64})\r?$", serial)
    assert hashlib.sha256(sanitized).hexdigest() == sanitized_hash.decode()
    base_counts = Counter(row["base"] or "unknown" for row in tasks.values())
    extra_counts = Counter(row["additional"] or "unknown" for row in tasks.values())
    base = base_counts["pass"]
    plus = sum(row["plus_passed"] for row in tasks.values())
    printed_scores = re.findall(rb"pass@1:\s+([0-9.]+)", serial)
    assert printed_scores == [f"{count / total:.3f}".encode() for count in (base, plus)]
    newly_generated = plan["cases"] if retry else tasks
    comparison_key = "previous_plus_passed" if retry else "raw_prefix_plus_passed"
    summary = {
        "outcome": "scored", "model": study.load(collection / "manifest.json")["config"]["model"],
        "generation_format": "Liquid AI chat template with Thinking ON",
        "attempted": total, "excluded": 0, "source_run": collection.name,
        "new_generations_in_source_run": len(newly_generated), "new_generations_in_scoring": 0,
        "unknown_base_statuses": base_counts["unknown"], "unknown_additional_statuses": extra_counts["unknown"],
        "humaneval_base": {"passed": base, "pass_at_1": base / total, "statuses": dict(base_counts)},
        "humaneval_plus": {"passed": plus, "pass_at_1": plus / total, "statuses_for_additional_tests": dict(extra_counts)},
        "base_pass_plus_nonpass_ids": [task for task, row in tasks.items() if row["base"] == "pass" and not row["plus_passed"]],
        "generation_metrics": chat_metrics(collection, newly_generated),
        "memory": study.load(collection / "summaries/memory.json"),
        "evaluator": evaluator,
        "submission": {"policy": "EvalPlus v0.3.1 sanitize(final assistant content, entrypoint=task entry point)",
                       "sanitized_sha256": sanitized_hash.decode(), "input": input_record},
        "reference": {"score_run": reference.name, "source_run": old["source_run"],
                      "base_passed": old["humaneval_base"]["passed"], "plus_passed": old["humaneval_plus"]["passed"],
                      "generation_metrics": old["generation_metrics"] if retry else old["generation_metrics"]["lfm3"],
                      "only_chat_plus_pass_ids": [task for task, row in tasks.items() if row["plus_passed"] and not row[comparison_key]],
                      "only_raw_plus_pass_ids": [task for task, row in tasks.items() if row[comparison_key] and not row["plus_passed"]]},
    }
    if retry:
        summary["retry"] = retry_results(collection, plan, tasks, official, reference)
    result = study.create_run("LFM3 Q8_0 Thinking ON chat EvalPlus scoring", "humaneval-plus",
                              config={"source_run": collection.name, "evaluator": evaluator},
                              run_id=run_id, kind="replay", period="period-004")
    (result / "raw/evalplus-results.json").write_bytes(data)
    (result / "raw/samples.jsonl").write_bytes(sanitized)
    shutil.copyfile(inputs / "samples.jsonl", result / "raw/final-chat-content.jsonl")
    (result / "logs/offline-vm-serial.log").write_bytes(serial)
    (result / "configs/python-requirements.txt").write_bytes(deps)
    study.save(result / "configs/vm-launch.json", {"evaluate": launch})
    study.save(result / "summaries/per-task.json", tasks)
    study.save(result / "summary.json", summary)
    for source in (Path(__file__), Path(__file__).with_name("official_humaneval_plus_submit.py"),
                   Path(__file__).with_name("official_humaneval_prefix_validation.py"),
                   vm_base / "run_lfm3_vm.py", vm_base / "evaluate-chat.yaml"):
        shutil.copyfile(source, result / "source" / source.name)
    study.save(result / "source-manifest.json", {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=study.ROOT).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=study.ROOT)),
        "files": {file.name: study.sha(file) for file in (result / "source").iterdir()},
    })
    evidence = [collection / "manifest.json", collection / "summaries/samples.jsonl",
                reference / "summary.json", reference / "summaries/per-task.json",
                gemma_score / "source/collect_results.py", result / "summary.json",
                result / "summaries/per-task.json", *sorted((result / "raw").glob("*"))]
    manifest = study.load(result / "manifest.json")
    manifest.update(status="complete", finished_at=study.now(), evidence=[
        {"path": file.relative_to(study.ROOT).as_posix(), "sha256": study.sha(file)} for file in evidence
    ])
    study.save(result / "manifest.json", manifest)
    study.validate_run(result)
    print(json.dumps(study.load(result / "summary.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", required=True, type=study.resolve_run)
    parser.add_argument("--comparison-score-run", required=True, type=study.resolve_run)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--vm-dir", required=True, type=Path)
    parser.add_argument("--id", required=True)
    options = parser.parse_args()
    import_result(options.source_run, options.inputs, options.vm_dir, options.id, options.comparison_score_run)
