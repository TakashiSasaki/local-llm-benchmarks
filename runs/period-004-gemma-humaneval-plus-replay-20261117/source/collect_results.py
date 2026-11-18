"""Validate and archive an EvalPlus replay from the offline VM serial log."""

import base64
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from local_llm_benchmarks import study


SOURCE_RUN = "period-004-gemma-humaneval-aggregate-20261112"
WINDOWS_SCORE_RUN = "period-004-gemma-humaneval-score-combined-20261112"
RUN_ID = "period-004-gemma-humaneval-plus-replay-20261117"
EVALPLUS_COMMIT = "e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2"


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def gzip_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return {row["task_id"]: row for row in map(json.loads, stream)}


def unpack(stage):
    _, = re.findall(rb"(?m)^HEP_EVAL_EXIT=0\r?$", stage)
    assert b"HEP_ISOLATION_OK net=lo" in stage
    assert b"HEP_CONTROLS_OK" in stage
    assert b"samples.jsonl: OK" in stage and b"dataset.jsonl.gz: OK" in stage
    payload, = re.findall(rb"(?ms)^HEP_RESULT_BEGIN\r?\n(.*?)^HEP_RESULT_END\r?$", stage)
    data = gzip.decompress(base64.b64decode(b"".join(payload.split()), validate=True))
    dependencies, = re.findall(rb"(?ms)^HEP_DEPENDENCIES_BEGIN\r?\n(.*?)^HEP_DEPENDENCIES_END\r?$", stage)
    python, = re.findall(rb"(?m)^Python ([0-9.]+)\r?$", stage)
    return data, dependencies.replace(b"\r\n", b"\n"), python.decode(), stage.replace(payload, b"[see raw/evalplus-results.json]\n")


def task_number(task_id):
    return int(task_id.split("/")[-1])


def score(argv):
    eval_name, prep_name = argv
    eval_dir = HERE / eval_name
    prep_dir = HERE / prep_name
    stage = (eval_dir / "serial.log").read_bytes()
    data, dependencies, python, serial = unpack(stage)
    official = json.loads(data)
    dataset_path = HERE / "downloads" / "HumanEvalPlus-v0.1.10.jsonl.gz"
    original_dataset = ROOT / "datasets" / "humaneval" / "b9453e8" / "HumanEval.jsonl.gz"
    inputs = study.load(HERE / "inputs.json")
    original_path = ROOT / "runs" / SOURCE_RUN / "summaries" / "samples.jsonl"
    assert study.sha(original_path) == inputs["samples_original_sha256"]
    assert study.sha(original_dataset) == inputs["original_task_dataset_sha256"]
    assert study.sha(dataset_path) == inputs["humaneval_plus_dataset_sha256"]
    assert official["hash"] == hashlib.md5(dataset_path.read_bytes(), usedforsecurity=False).hexdigest()
    assert study.sha(HERE / "samples.jsonl") == inputs["evaluated_solution_file_sha256"]
    submission_rows = jsonl(HERE / "samples.jsonl")
    submission = {row["task_id"]: row["solution"] for row in submission_rows}
    expected_ids = {f"HumanEval/{index}" for index in range(164)}
    assert len(submission_rows) == len(submission) == inputs["source_samples"] == len(expected_ids)
    assert set(official["eval"]) == set(submission) == expected_ids
    original_prompts = gzip_jsonl(original_dataset)
    plus_tasks = gzip_jsonl(dataset_path)
    original_samples = jsonl(original_path)
    assert len(original_samples) == len(expected_ids)
    assert set(original_prompts) == set(plus_tasks) == expected_ids
    assert {row["task_id"]: original_prompts[row["task_id"]]["prompt"] + row["completion"]
            for row in original_samples} == submission
    old_dir = ROOT / "runs" / WINDOWS_SCORE_RUN
    old_rows = [study.load(path) for path in (old_dir / "raw").glob("HumanEval_*.json")]
    old_status = {row["task_id"]: row["passed"] for row in old_rows}
    assert set(old_status) == expected_ids and len(old_rows) == len(expected_ids)
    assert sum(old_status.values()) == study.load(old_dir / "summary.json")["passed"]
    by_task = {}
    for task_id in sorted(expected_ids, key=task_number):
        row, = official["eval"][task_id]
        assert row["task_id"] == task_id and row["solution"] == submission[task_id], task_id
        assert row["base_status"] in {"pass", "fail", "timeout", None}, task_id
        assert row["plus_status"] in {"pass", "fail", "timeout", None}, task_id
        by_task[task_id] = {"windows_humaneval_passed": old_status[task_id],
                            "base": row["base_status"], "additional": row["plus_status"],
                            "plus_passed": row["base_status"] == row["plus_status"] == "pass"}
    base = Counter(row["base"] or "unknown" for row in by_task.values())
    additional = Counter(row["additional"] or "unknown" for row in by_task.values())
    plus = sum(row["plus_passed"] for row in by_task.values())
    total = len(by_task)
    base_score = base["pass"] / total
    plus_score = plus / total
    reported_scores = re.findall(rb"pass@1:\s+([0-9.]+)", serial)
    assert reported_scores == [f"{score:.3f}".encode() for score in (base_score, plus_score)], reported_scores
    prep_launch = study.load(prep_dir / "launch.json")
    launch = study.load(eval_dir / "launch.json")
    assert launch["args"][launch["args"].index("-nic") + 1] == "none"
    assert "readonly=on" in " ".join(launch["args"])
    summary = {
        "outcome": "scored", "model": "Gemma 4 E4B IT Q4_K_M", "attempted": total,
        "source_run": SOURCE_RUN, "new_generations": 0, "excluded": 0,
        "humaneval_base": {"passed": base["pass"], "pass_at_1": base_score, "status_counts": dict(base),
                          "available_test_inputs": sum(len(row["base_input"]) for row in plus_tasks.values())},
        "humaneval_plus": {"passed": plus, "pass_at_1": plus_score, "not_passed": total - plus,
                          "additional_test_status_counts": dict(additional),
                          "available_extra_test_inputs": sum(len(row["plus_input"]) for row in plus_tasks.values())},
        "base_pass_plus_nonpass_ids": [task for task, row in by_task.items() if row["base"] == "pass" and not row["plus_passed"]],
        "windows_humaneval": {"passed": sum(old_status.values()), "run": WINDOWS_SCORE_RUN,
                             "old_only_pass_ids": [task for task, row in by_task.items() if old_status[task] and row["base"] != "pass"],
                             "evalplus_base_only_pass_ids": [task for task, row in by_task.items() if not old_status[task] and row["base"] == "pass"]},
        "unknown_base_statuses": base["unknown"], "unknown_additional_statuses": additional["unknown"],
        "evaluator": {"name": "EvalPlus", "version": "0.3.1", "commit": EVALPLUS_COMMIT,
                      "dataset": "HumanEvalPlus-v0.1.10", "dataset_internal_md5": official["hash"],
                      "os": "Debian GNU/Linux 12 amd64", "python": python, "workers": 2,
                      "min_time_limit_seconds": 1.0, "ground_truth_time_limit_factor": 4.0,
                      "test_details": False,
                      "guest_network": "No NIC; loopback verified", "evaluator_controls": ["known pass", "known fail"]},
        "inputs": inputs,
    }
    config = {"source_run": SOURCE_RUN, "samples_per_task": 1, "period": "period-004",
              "new_generations": 0, "submission": "Unchanged original HumanEval prompt + unchanged saved completion",
              "evaluator": summary["evaluator"]}
    path = study.create_run("Gemma 4 E4B saved HumanEval answers with EvalPlus", "humaneval-plus",
                            config=config, run_id=RUN_ID, kind="replay", root=ROOT)
    (path / "raw" / "evalplus-results.json").write_bytes(data)
    shutil.copyfile(HERE / "samples.jsonl", path / "raw" / "samples.jsonl")
    (path / "logs" / "offline-vm-serial.log").write_bytes(serial)
    (path / "configs" / "python-requirements.txt").write_bytes(dependencies)
    study.save(path / "summaries" / "per-task.json", by_task)
    study.save(path / "configs" / "inputs.json", inputs)
    for filename in ("run_vm.py", "prepare.yaml", "evaluate.yaml", "collect_results.py"):
        shutil.copyfile(HERE / filename, path / "source" / filename)
    download_names = ("evalplus-v0.3.1-source.tar.gz", "evalplus-0.3.1-py3-none-any.whl",
                      "HumanEvalPlus-v0.1.10.jsonl.gz", "debian-12-genericcloud-amd64.qcow2",
                      "qemu-w64-setup-20260729.exe", "pycdlib.whl")
    study.save(path / "configs" / "artifacts.json",
               {name: {"sha256": study.sha(HERE / "downloads" / name)} for name in download_names})
    study.save(path / "configs" / "vm-launch.json", {"prepare": prep_launch["args"], "evaluate": launch["args"]})
    study.save(path / "source-manifest.json", {
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "upstream_commit": EVALPLUS_COMMIT,
        "files": {file.name: study.sha(file) for file in (path / "source").iterdir()},
    })
    study.save(path / "summary.json", summary)
    manifest = study.load(path / "manifest.json")
    files = [original_path, original_dataset, old_dir / "summary.json", path / "raw" / "samples.jsonl",
             path / "raw" / "evalplus-results.json", path / "summaries" / "per-task.json", path / "summary.json"]
    manifest.update(status="complete", finished_at=study.now(), evidence=[
        {"path": file.relative_to(ROOT).as_posix(), "sha256": study.sha(file)} for file in files
    ])
    study.save(path / "manifest.json", manifest)
    study.validate_run(path)
    print(json.dumps(study.load(path / "summary.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    score(sys.argv[1:])
