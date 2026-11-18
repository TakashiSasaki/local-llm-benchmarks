"""Check Bonsai's 32K CUDA placement without consuming benchmark prompts."""

import json
from contextlib import closing
from pathlib import Path
import socket
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "benchmarks")]
from local_llm_benchmarks import memory_windows as memory
from local_llm_benchmarks.study import load, save
from official_humaneval_prefix_validation import api


def command(layers, keep_output_on_gpu):
    path = ROOT / "runs/period-004-lfm3-1p7b-q8-humaneval-chat-thinking-20261117/configs/server-command.json"
    args = load(path)["args"]
    replacements = {
        "-m": "C:/LocalLLM/models/Ternary-Bonsai-2-27B-Q2_0.gguf", "--port": "18091",
        "--alias": "period4-bonsai2-q20-chat", "-ngl": layers, "-c": "32768",
        "-ctk": "q4_0", "-ctv": "q4_0", "-b": "512", "-ub": "128", "-fa": "on",
        "--repeat-penalty": "1.0",
    }
    for flag, value in replacements.items():
        args[args.index(flag) + 1] = value
    args.extend(["-lv", "4"])
    if keep_output_on_gpu:
        args.extend(["--override-tensor", "output.weight=CUDA0"])
    return args


def probe(stage, args):
    work = HERE / stage
    work.mkdir()
    save(work / "command.json", {"args": args})
    port = int(args[args.index("--port") + 1])
    with closing(socket.socket()) as check:
        if check.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError("Probe port occupied")
    with (work / "server.log").open("xb") as log:
        child = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=Path(args[0]).parent,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(150):
            if child.poll() is not None:
                return {"outcome": "server-exit", "exit_code": child.returncode}
            try:
                if api("/health", timeout=2, port=port).get("status") == "ok":
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            return {"outcome": "readiness-timeout"}
        props = api("/props", timeout=15, port=port)
        assert props["default_generation_settings"]["n_ctx"] == 32768 and props["total_slots"] == 1
        save(work / "props.json", props)
        snapshot = memory.snapshot(child.pid)
        save(work / "admission.json", snapshot)
        used = snapshot["gpu_used_mib"]
        ram = snapshot["available_ram_bytes"]
        if used is None or used > 7676 or ram < 3 * 1024 ** 3:
            return {"outcome": "resource-admission", "gpu_used_mib": used, "available_ram_bytes": ram}
        messages = [{"role": "user", "content": "What is 12 times 13? Answer with the number."}]
        medium = {"enable_thinking": True, "reasoning_effort": "medium"}
        high = dict(medium, reasoning_effort="xhigh")
        prompts = {k: api("/apply-template", {"messages": messages, "chat_template_kwargs": v}, timeout=15, port=port)
                   for k, v in (("medium", medium), ("xhigh", high))}
        save(work / "template-probes.json", prompts)
        if not prompts["medium"]["prompt"].rstrip().endswith("<think>"):
            return {"outcome": "thinking-template-mismatch"}
        started = time.monotonic()
        answer = api("/v1/chat/completions", {
            "model": props["model_alias"], "messages": messages, "chat_template_kwargs": medium,
            "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05,
            "repeat_penalty": 1.0, "presence_penalty": 0.0, "seed": 42, "max_tokens": 1024, "cache_prompt": False,
        }, timeout=120, port=port)
        elapsed = time.monotonic() - started
        save(work / "answer.json", {"response": answer, "seconds": elapsed})
        measured = memory.snapshot(child.pid)
        save(work / "post-probe-memory.json", measured)
        choice, = answer["choices"]
        message = choice["message"]
        distinct_effort = prompts["medium"]["prompt"] != prompts["xhigh"]["prompt"]
        coherent = "156" in (message.get("content") or "")
        return {
            "outcome": "ready" if coherent and message.get("reasoning_content") else "generation-probe-failed",
            "gpu_used_mib": measured["gpu_used_mib"], "minutes": elapsed / 60,
            "tokens_per_second": answer.get("timings", {}).get("predicted_per_second"),
            "medium_and_xhigh_render_differently": distinct_effort,
        }
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=30)


if __name__ == "__main__":
    for name, layers, output_gpu in [("all-gpu-kv4", "all", False), ("partial-62-kv4", "62", True),
                                     ("partial-58-kv4", "58", True)]:
        args = command(layers, output_gpu)
        result = probe(name, args)
        save(HERE / name / "result.json", result)
        print(json.dumps({"stage": name, **result}), flush=True)
        if result["outcome"] == "ready":
            save(HERE / "benchmark-server-command.json", {"args": args, "probe": name, "outcome": result})
            break
        if result["outcome"] in {"thinking-template-mismatch", "generation-probe-failed"}:
            raise RuntimeError("Runtime or template probe requires diagnosis")
    else:
        raise RuntimeError("No stable 32K CUDA placement found")
