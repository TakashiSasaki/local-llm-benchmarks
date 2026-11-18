"""Validate an offline EvalPlus result and compare it with the saved Gemma run."""

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

from official_humaneval_plus_submit import GEMMA_SCORE, ORIGINAL_DATASET, gemma_raw_paths, load_inputs, study


def summarize_generation(rows):
    responses = [row["response"] for row in rows]
    return {
        "samples": len(rows),
        "median_request_seconds": median(row["seconds"] for row in rows),
        "sum_request_seconds": sum(row["seconds"] for row in rows),
        "median_output_tokens": median(row["tokens_predicted"] for row in responses),
        "median_decode_tokens_per_second": median(
            row["timings"]["predicted_per_second"] for row in responses if row["tokens_predicted"]
        ),
        "stops": dict(Counter(row["stop_type"] for row in responses)),
    }


def compare_effective_settings(lfm_rows, gemma_rows):
    differences = {}
    for lfm, gemma in zip(lfm_rows, gemma_rows, strict=True):
        assert lfm["task_id"] == gemma["task_id"]
        a = lfm["response"]["generation_settings"]
        b = gemma["response"]["generation_settings"]
        for name in sorted(a.keys() | b.keys()):
            if a.get(name) != b.get(name):
                values = json.dumps({"lfm3": a.get(name), "gemma": b.get(name)}, sort_keys=True)
                differences.setdefault(name, Counter())[values] += 1
    return {
        name: [{"values": json.loads(value), "cases": count} for value, count in sorted(counts.items())]
        for name, counts in differences.items()
    }


def compare_reference(reference, tasks, rows):
    study.validate_run(reference)
    summary = study.load(reference / "summary.json")
    statuses = study.load(reference / "summaries/per-task.json")
    assert set(statuses) == set(tasks)
    reference_collection = study.resolve_run(summary["source_run"])
    study.validate_run(reference_collection)
    originals = [study.load(reference_collection / "raw" / (task.replace("/", "_") + ".json")) for task in tasks]
    assert all(new["request"] == original["request"] for new, original in zip(rows, originals, strict=True))
    settings = compare_effective_settings(rows, originals)
    for task_id, row in tasks.items():
        row["comparison_plus_passed"] = statuses[task_id]["plus_passed"]
    return {
        "score_run": reference.name, "collection_run": reference_collection.name, "model": summary["model"],
        "base_passed": summary["humaneval_base"]["passed"], "plus_passed": summary["humaneval_plus"]["passed"],
        "generation_metrics": summarize_generation(originals),
        "identical_request_payloads": True, "effective_request_setting_differences": settings,
        "only_new_plus_pass_ids": [task for task, row in tasks.items() if row["plus_passed"] and not row["comparison_plus_passed"]],
        "only_reference_plus_pass_ids": [task for task, row in tasks.items() if not row["plus_passed"] and row["comparison_plus_passed"]],
    }


def import_result(collection, inputs, vm_dir, run_id, reference=None):
    vm_base = vm_dir.parent
    dataset = vm_base / "downloads/HumanEvalPlus-v0.1.10.jsonl.gz"
    gemma = study.resolve_run(GEMMA_SCORE)
    study.validate_run(gemma)
    gemma_summary = study.load(gemma / "summary.json")
    sys.path.insert(0, str(gemma / "source"))
    from collect_results import unpack

    assert study.load(vm_dir / "exit.json")["returncode"] == 0
    assert study.load(collection / "configs/cleanup.json")["server_stopped"]
    launch = study.load(vm_dir / "launch.json")["args"]
    assert launch[launch.index("-nic") + 1] == "none"
    assert "readonly=on" in " ".join(launch)
    data, deps, python, serial = unpack((vm_dir / "serial.log").read_bytes())
    evaluator = gemma_summary["evaluator"]
    assert python == evaluator["python"]
    assert deps == (gemma / "configs/python-requirements.txt").read_bytes()
    assert study.sha(vm_base / "evaluate.yaml") == study.sha(gemma / "source/evaluate.yaml")

    input_record = study.load(inputs / "inputs.json")
    assert study.sha(dataset) == input_record["humaneval_plus_dataset_sha256"]
    assert study.sha(inputs / "samples.jsonl") == input_record["evaluated_solution_file_sha256"]
    assert study.sha(collection / "summaries/samples.jsonl") == input_record["samples_original_sha256"]
    solutions = load_inputs(collection)
    assert [json.loads(line) for line in (inputs / "samples.jsonl").read_text(encoding="utf-8").splitlines()] == solutions
    official = json.loads(data)
    assert official["hash"] == hashlib.md5(dataset.read_bytes(), usedforsecurity=False).hexdigest() == evaluator["dataset_internal_md5"]
    submitted = {row["task_id"]: row["solution"] for row in solutions}
    gemma_tasks = study.load(gemma / "summaries/per-task.json")
    format_rows = study.load(collection / "summaries/format-validation.json")
    parses = {row["task_id"]: row["parses_when_appended"] for row in format_rows}
    total = len(submitted)
    assert total == 164 and len(format_rows) == total
    assert set(official["eval"]) == set(gemma_tasks) == set(submitted) == set(parses)
    tasks = {}
    for task_id, solution in submitted.items():
        row, = official["eval"][task_id]
        assert row["task_id"] == task_id and row["solution"] == solution
        base, extra = row["base_status"], row["plus_status"]
        assert base in {"pass", "fail", "timeout", None}
        assert extra in {"pass", "fail", "timeout", None}
        tasks[task_id] = {"base": base, "additional": extra, "plus_passed": base == extra == "pass",
                          "host_ast_parseable": parses[task_id],
                          "gemma_base": gemma_tasks[task_id]["base"], "gemma_plus_passed": gemma_tasks[task_id]["plus_passed"]}
    base_counts = Counter(row["base"] or "unknown" for row in tasks.values())
    extra_counts = Counter(row["additional"] or "unknown" for row in tasks.values())
    base = base_counts["pass"]
    plus = sum(row["plus_passed"] for row in tasks.values())
    official_scores = re.findall(rb"pass@1:\s+([0-9.]+)", serial)
    assert official_scores == [f"{score / total:.3f}".encode() for score in (base, plus)], official_scores

    paths = gemma_raw_paths()
    lfm_rows = [study.load(collection / "raw" / (task.replace("/", "_") + ".json")) for task in tasks]
    gemma_rows = [study.load(paths[task]) for task in tasks]
    lfm_timing = summarize_generation(lfm_rows)
    gemma_timing = summarize_generation(gemma_rows)
    model = study.load(collection / "manifest.json")["config"]["model"]
    summary = {
        "outcome": "scored", "model": model, "attempted": total, "excluded": 0,
        "unknown_base_statuses": base_counts["unknown"], "unknown_additional_statuses": extra_counts["unknown"],
        "source_run": collection.name, "new_generations_in_source_run": total,
        "new_generations_in_scoring": 0,
        "humaneval_base": {"passed": base, "pass_at_1": base / total, "statuses": dict(base_counts)},
        "humaneval_plus": {"passed": plus, "pass_at_1": plus / total, "statuses_for_additional_tests": dict(extra_counts)},
        "base_pass_plus_nonpass_ids": [task for task, row in tasks.items() if row["base"] == "pass" and not row["plus_passed"]],
        "gemma": {"score_run": gemma.name, "base_passed": gemma_summary["humaneval_base"]["passed"],
                  "plus_passed": gemma_summary["humaneval_plus"]["passed"],
                  "lfm_only_plus_passes": [task for task, row in tasks.items() if row["plus_passed"] and not row["gemma_plus_passed"]],
                  "gemma_only_plus_passes": [task for task, row in tasks.items() if not row["plus_passed"] and row["gemma_plus_passed"]]},
        "generation_metrics": {"lfm3": lfm_timing, "gemma": gemma_timing},
        "source_generation_memory": study.load(collection / "summaries/memory.json"),
        "host_ast_parseable": sum(parses.values()),
        "effective_request_setting_differences": compare_effective_settings(lfm_rows, gemma_rows),
        "evaluator": evaluator, "inputs": input_record,
    }
    if reference:
        summary["comparison"] = compare_reference(reference, tasks, lfm_rows)
    result = study.create_run(f"{model} HumanEval+ scoring", "humaneval-plus",
                              config={"source_run": collection.name, "evaluator": evaluator, "inputs": input_record},
                              run_id=run_id, kind="replay", period="period-004")
    (result / "raw/evalplus-results.json").write_bytes(data)
    shutil.copyfile(inputs / "samples.jsonl", result / "raw/samples.jsonl")
    (result / "logs/offline-vm-serial.log").write_bytes(serial)
    (result / "configs/python-requirements.txt").write_bytes(deps)
    study.save(result / "configs/vm-launch.json", {"evaluate": launch})
    study.save(result / "summaries/per-task.json", tasks)
    study.save(result / "summary.json", summary)
    for source in (Path(__file__), Path(__file__).with_name("official_humaneval_plus_submit.py"),
                   vm_base / "run_lfm3_vm.py", vm_base / "evaluate.yaml"):
        shutil.copyfile(source, result / "source" / source.name)
    study.save(result / "source-manifest.json", {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=study.ROOT).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=study.ROOT)),
        "files": {file.name: study.sha(file) for file in (result / "source").iterdir()},
    })
    evidence = [
        ORIGINAL_DATASET, collection / "manifest.json", collection / "summaries/samples.jsonl",
        collection / "summaries/format-validation.json", collection / "summaries/memory.json",
        gemma / "summary.json", gemma / "summaries/per-task.json", gemma / "source/collect_results.py",
        result / "raw/evalplus-results.json", result / "raw/samples.jsonl",
        result / "summaries/per-task.json", result / "summary.json",
    ]
    if reference:
        evidence.extend([reference / "summary.json", reference / "summaries/per-task.json"])
    manifest = study.load(result / "manifest.json")
    manifest.update(status="complete", finished_at=study.now(), evidence=[
        {"path": file.relative_to(study.ROOT).as_posix(), "sha256": study.sha(file)} for file in evidence
    ])
    study.save(result / "manifest.json", manifest)
    study.validate_run(result)
    print(json.dumps(study.load(result / "summary.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--vm-dir", required=True, type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--comparison-score-run", type=study.resolve_run)
    options = parser.parse_args()
    import_result(study.resolve_run(options.source_run), options.inputs, options.vm_dir, options.id, options.comparison_score_run)
