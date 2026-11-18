"""Capture Bonsai's admitted configuration and archive the preflight evidence."""

import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from local_llm_benchmarks import study


def prepare():
    admitted = study.load(HERE / "benchmark-server-command.json")
    asset = study.load(ROOT / "experiments/period-003/models/bonsai2-27b-stock-q20.json")
    verified = json.loads((HERE / "model-range-verification.json").read_text(encoding="utf-8").splitlines()[-1])
    assert verified["verified"] and verified["sha256"] == asset["sha256"] and verified["bytes"] == asset["bytes"]
    args = admitted["args"]
    props = study.load(HERE / admitted["probe"] / "props.json")
    context = props["default_generation_settings"]["n_ctx"]
    assert context == 32768
    effort_observed = admitted["outcome"]["medium_and_xhigh_render_differently"]
    request = {
        "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "presence_penalty": 0.0,
        "repeat_penalty": 1.0, "chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "medium"},
    }
    config = {
        "period": "period-004", "model": "Ternary Bonsai 2 27B Q2_0", "model_asset": dict(asset),
        "model_sha256": asset["sha256"], "runtime_sha256": "81f65c6681d66099e5d48757aa2c050ba958dc43816e584f0bb4181eb7c910d8",
        "dataset": "HumanEvalPlus v0.1.10, all 164 official problems",
        "dataset_sha256": "272720b90ac375502c8ed23cd791c2a93dfb22a911641a494da74a426c09f101",
        "thinking": "native Thinking ON, reasoning effort medium requested",
        "effort_changes_rendered_template": effort_observed,
        "generation": "llama.cpp /v1/chat/completions, embedded GGUF template, EvalPlus v0.3.1 OpenAI backend user prompt",
        "chat_request_options": request, "context": context, "max_output": 16384, "seed": 42,
        "samples_per_task": 1, "api_timeout_seconds": 7200, "automatic_retries": 0,
        "n_gpu_layers": args[args.index("-ngl") + 1], "kv": {"key": "q4_0", "value": "q4_0"},
        "expected_server_repeat_penalty": 1.0, "placement_probe": admitted["probe"], "vision": False,
        "scoring": "EvalPlus v0.3.1, HumanEval+ v0.1.10, offline Debian VM",
    }
    study.save(HERE / "benchmark-config.json", config)


def archive(run_id):
    run = study.resolve_run(run_id)
    validated = study.load(HERE / "benchmark-server-command.json")
    probes = run / "configs/gpu-probes"
    probes.mkdir()
    for stage in HERE.iterdir():
        if stage.is_dir() and (stage / "result.json").exists():
            shutil.copytree(stage, probes / stage.name)
    for name in ("benchmark-server-command.json", "model-range-verification.json"):
        shutil.copyfile(HERE / name, run / "configs" / name)
    files = [ROOT / "benchmarks/official_humaneval_prefix_validation.py",
             ROOT / "scripts/download_pinned_model.py", ROOT / "scripts/new_run.py"]
    files.extend(ROOT / "src/local_llm_benchmarks" / name for name in ("memory_windows.py", "study.py", "periods.py", "__init__.py"))
    files.extend((HERE / "probe_bonsai.py", Path(__file__)))
    records = {}
    for source in files:
        rel = source.relative_to(ROOT) if not source.is_relative_to(HERE) else Path(source.name)
        target = run / "source" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records[rel.as_posix()] = study.sha(target)
    study.save(run / "source-manifest.json", {
        "files": records, "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
    })
    assert (probes / validated["probe"] / "result.json").is_file()
    study.validate_run(run)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        prepare()
    else:
        archive(sys.argv[1])
