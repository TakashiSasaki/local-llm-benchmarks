"""Verify a full raw-prefix HumanEval collection and stage it for EvalPlus."""

import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from local_llm_benchmarks import study


GEMMA_GENERATION = "period-004-gemma-humaneval-aggregate-20261112"
GEMMA_SCORE = "period-004-gemma-humaneval-plus-replay-20261117"
ORIGINAL_DATASET = study.ROOT / "datasets/humaneval/b9453e8/HumanEval.jsonl.gz"


def gemma_raw_paths():
    gemma_collection = study.resolve_run(GEMMA_GENERATION)
    rows = study.load(gemma_collection / "configs/source-references.json")["references"]
    result = {}
    for row in rows:
        task_id = row["task_id"]
        path = study.resolve_run(row["run"]) / "raw" / (task_id.replace("/", "_") + ".json")
        assert study.sha(path) == row["raw_sha256"], task_id
        result[task_id] = path
    assert len(result) == len(rows)
    return result


def load_inputs(run):
    manifest = study.validate_run(run)
    if manifest["status"] != "complete":
        raise ValueError(f"Collection did not complete: {run.name}")
    config = manifest["config"]
    if study.sha(ORIGINAL_DATASET) != config["dataset_sha256"]:
        raise ValueError("Original HumanEval dataset hash mismatch")
    with gzip.open(ORIGINAL_DATASET, "rt", encoding="utf-8") as stream:
        tasks = {row["task_id"]: row for row in map(json.loads, stream)}
    expected_ids = {f"HumanEval/{index}" for index in range(164)}
    assert set(tasks) == expected_ids
    lines = (run / "summaries/samples.jsonl").read_text(encoding="utf-8").splitlines()
    saved = {row["task_id"]: row["completion"] for row in map(json.loads, lines)}
    assert len(saved) == len(lines) == len(tasks) and set(saved) == set(tasks)
    gemma_sources = gemma_raw_paths()
    assert set(gemma_sources) == set(tasks)
    assert len(list((run / "raw").glob("HumanEval_*.json"))) == len(tasks)
    solutions = []
    for task_id, problem in tasks.items():
        filename = task_id.replace("/", "_") + ".json"
        row = study.load(run / "raw" / filename)
        reference = study.load(gemma_sources[task_id])
        assert row["task_id"] == task_id and row["response"]["content"] == saved[task_id], task_id
        assert row["request"] == reference["request"], task_id
        assert row["request"]["prompt"] == problem["prompt"], task_id
        solutions.append({"task_id": task_id, "solution": problem["prompt"] + saved[task_id]})
    return solutions


def load_chat_inputs(run, dataset):
    from official_humaneval_prefix_validation import chat_payload

    manifest = study.validate_run(run)
    assert manifest["status"] == "complete"
    assert study.sha(dataset) == manifest["config"]["dataset_sha256"]
    alias = study.load(run / "configs/served-properties.json")["model_alias"]
    with gzip.open(dataset, "rt", encoding="utf-8") as stream:
        tasks = {row["task_id"]: row for row in map(json.loads, stream)}
    expected_ids = {f"HumanEval/{index}" for index in range(164)}
    assert set(tasks) == expected_ids
    with (run / "summaries/samples.jsonl").open(encoding="utf-8") as stream:
        rows = list(map(json.loads, stream))
    saved = {row["task_id"]: row["completion"] for row in rows}
    assert len(rows) == len(saved) == len(expected_ids) and set(saved) == expected_ids
    assert len(list((run / "raw").glob("HumanEval_*.json"))) == len(expected_ids)
    for task, problem in tasks.items():
        raw = study.load(run / "raw" / (task.replace("/", "_") + ".json"))
        assert raw["task_id"] == task and raw["request"] == chat_payload(problem, alias)
        choice, = raw["response"]["choices"]
        assert (choice["message"].get("content") or "") == saved[task]
    return [{"task_id": task, "solution": saved[task]} for task in tasks]


def prepare(run, dataset, inputs, chat=False):
    solutions = load_chat_inputs(run, dataset) if chat else load_inputs(run)
    gemma_score = study.resolve_run(GEMMA_SCORE)
    gemma_summary = study.load(gemma_score / "summary.json")
    dataset_sha = study.sha(dataset)
    assert dataset_sha == gemma_summary["inputs"]["humaneval_plus_dataset_sha256"]
    with gzip.open(dataset, "rt", encoding="utf-8") as stream:
        plus_ids = {row["task_id"] for row in map(json.loads, stream)}
    assert plus_ids == {row["task_id"] for row in solutions}
    inputs.mkdir()
    submission = inputs / "samples.jsonl"
    with submission.open("x", encoding="utf-8", newline="\n") as stream:
        for row in solutions:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    submission_sha = study.sha(submission)
    with (inputs / "evaluation-sha256sums").open("x", encoding="ascii", newline="\n") as stream:
        stream.write(f"{submission_sha}  samples.jsonl\n{dataset_sha}  dataset.jsonl.gz\n")
    study.save(inputs / "inputs.json", {
        "source_run": run.name, "source_samples": len(solutions),
        "samples_original_sha256": study.sha(run / "summaries/samples.jsonl"),
        "original_task_dataset_sha256": study.sha(ORIGINAL_DATASET),
        "humaneval_plus_dataset_sha256": dataset_sha,
        "evaluated_solution_file_sha256": submission_sha,
        "input_kind": "final chat content" if chat else "original prompt plus completion",
        **({"all_generation_payloads_match_gemma": True} if not chat else {}),
    })
    print(f"Ready for offline EvalPlus: {len(solutions)} verified solutions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--chat", action="store_true")
    options = parser.parse_args()
    prepare(study.resolve_run(options.run), options.dataset, options.inputs, options.chat)
