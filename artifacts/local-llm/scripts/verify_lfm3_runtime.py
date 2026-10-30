"""Real local CUDA chat and constrained file-tool smoke check; not a Hermes test."""
import argparse
import datetime
import json
import pathlib
import re
import secrets
import sys
import threading
import time
import urllib.request
import zipfile

import memory
import server
from client import Client
from install_lfm3_runtime import save, sha256

ROOT = pathlib.Path(r"C:\LocalLLM")


def get_json(path):
    with urllib.request.urlopen("http://127.0.0.1:8089" + path, timeout=5) as response:
        return json.load(response)


def run_probe(setup, run=None, profile_name="lfm3"):
    run = run or setup
    run.mkdir(parents=True, exist_ok=True)
    begin = datetime.datetime.now(datetime.timezone.utc)
    profile = server.load_profile(profile_name)
    samples = []
    stop_event = threading.Event()
    result = {"started_utc": begin.isoformat(), "profile_id": profile["profile_id"], "tests": {}, "hermes_tested": False}

    def owned_state():
        state = ROOT / "server-state.json"
        if not state.exists():
            return None
        item = json.loads(state.read_text(encoding="utf-8"))
        if item.get("profile") == profile_name and datetime.datetime.fromisoformat(item["started_utc"]) >= begin:
            return item
        return None

    def monitor():
        while not stop_event.is_set():
            try:
                state = owned_state()
                sample = memory.snapshot(state["pid"] if state else 0)
                sample["server_pid"] = state["pid"] if state else None
                samples.append(sample)
                with (run / "memory.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(sample) + "\n")
            except Exception as error:
                with (run / "monitor-errors.txt").open("a", encoding="utf-8") as stream:
                    stream.write(repr(error) + "\n")
            stop_event.wait(2)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        server.start(profile_name)
        state = owned_state()
        if not state:
            raise RuntimeError("Started server ownership was not established")
        result["server"] = state
        props = get_json("/props")
        save(run / "server-props.json", props)
        save(run / "server-slots.json", get_json("/slots"))
        save(run / "server-models.json", get_json("/v1/models"))
        served_context = props.get("default_generation_settings", {}).get("n_ctx")
        if served_context is None:
            served_context = props.get("default_generation_settings", {}).get("params", {}).get("n_ctx")
        result["served_context_per_slot"] = served_context
        result["tests"]["served_identity"] = props.get("model_alias") == profile["profile_id"] and "11960" in props.get("build_info", "")
        result["tests"]["context_65536"] = served_context == 65536
        client = Client(profile, run / "chat.jsonl")
        chat = client.chat([
            {"role": "system", "content": "あなたは日本語で簡潔に答えるアシスタントです。"},
            {"role": "user", "content": "パソコンの中で動くローカルAIの利点を、日本語で2文で説明してください。"},
        ], max_tokens=2048, request_timeout=180)
        save(run / "japanese-chat.json", chat)
        content = chat["message"].get("content", "")
        result["tests"]["japanese_response"] = chat["finish_reason"] == "stop" and bool(re.search(r"[ぁ-んァ-ン一-龯]", content))
        result["japanese_response"] = content
        result["japanese_chat_metrics"] = {k: chat[k] for k in ["wall_seconds", "ttft_seconds", "usage", "timings"]}
        print(json.dumps({"event": "japanese_chat", "passed": result["tests"]["japanese_response"], "content": content, "timings": chat["timings"]}, ensure_ascii=False), flush=True)
        fixture = {"ticket_id": "LFM3-" + secrets.token_hex(6), "amounts": [secrets.randbelow(400) + 1 for _ in range(4)], "note": "日本語の読み取り専用ファイル確認"}
        fixture_path = run / "probe-input.json"
        save(fixture_path, fixture)
        input_hash = sha256(fixture_path)
        tools = [{"type": "function", "function": {
            "name": "read_probe_file", "description": "指定されたローカル試験ファイルを読み取る。読み取り専用。",
            "parameters": {"type": "object", "properties": {"path": {"type": "string", "enum": ["probe-input.json"]}}, "required": ["path"], "additionalProperties": False},
        }}]
        messages = [
            {"role": "system", "content": "利用可能なツールを使い、取得した実データに基づいて回答してください。"},
            {"role": "user", "content": "read_probe_fileでprobe-input.jsonを読み取り、amountsの件数と合計を計算してください。最終回答はticket_id、count、totalの3キーだけのJSONオブジェクトにしてください。値を推測せず、必ずファイルを読んでください。"},
        ]
        first = client.chat(messages, tools, max_tokens=2048, request_timeout=180)
        save(run / "tool-first.json", first)
        calls = first["message"].get("tool_calls", [])
        correct_call = len(calls) == 1 and calls[0]["function"]["name"] == "read_probe_file"
        if correct_call:
            correct_call = json.loads(calls[0]["function"]["arguments"]) == {"path": "probe-input.json"}
        result["tests"]["structured_tool_call"] = correct_call
        if not correct_call:
            raise RuntimeError("Model did not return the expected parsed structured file-tool call")
        actual = json.loads(fixture_path.read_text(encoding="utf-8"))
        save(run / "tool-execution.json", {"tool_call_id": calls[0]["id"], "file": str(fixture_path), "read_only": True, "actual_result": actual, "input_sha256": input_hash})
        messages.extend([first["message"], {"role": "tool", "tool_call_id": calls[0]["id"], "content": json.dumps(actual, ensure_ascii=False)}])
        final = client.chat(messages, tools, max_tokens=2048, request_timeout=180)
        save(run / "tool-final.json", final)
        text = final["message"].get("content", "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        parsed = json.loads(text)
        expected = {"ticket_id": actual["ticket_id"], "count": len(actual["amounts"]), "total": sum(actual["amounts"])}
        result["tests"]["tool_result_correct"] = final["finish_reason"] == "stop" and not final["message"].get("tool_calls") and parsed == expected and type(parsed.get("count")) is int and type(parsed.get("total")) is int
        result["tests"]["input_unchanged"] = sha256(fixture_path) == input_hash
        result["tool_result"] = parsed
        result["tool_expected"] = expected
        print(json.dumps({"event": "file_tool_roundtrip", "passed": result["tests"]["tool_result_correct"], "result": parsed}, ensure_ascii=False), flush=True)
        log = pathlib.Path(state["log"]).read_text(encoding="utf-8", errors="replace")
        (run / "server.log").write_text(log, encoding="utf-8")
        result["gpu_placement_evidence"] = [line for line in log.splitlines() if any(s in line for s in ["offloaded", "CUDA0 model buffer", "CUDA0 KV buffer", "KV self size", "n_ctx_per_seq", "CUDA0 compute buffer", "n_ctx =", "swa"])][:60]
        result["tests"]["all_model_layers_on_gpu"] = bool(re.search(r"offloaded (\d+)/(\1) layers to GPU", log))
        before = json.loads((setup / "preserved-before.json").read_text(encoding="utf-8"))
        unchanged = [{**item, "unchanged": sha256(pathlib.Path(item["path"])) == item["sha256"]} for item in before if pathlib.Path(item["path"]).name != "model-manifest.json"]
        original_models = json.loads((setup / "before/model-manifest.json").read_text(encoding="utf-8"))
        current_models = json.loads((ROOT / "model-manifest.json").read_text(encoding="utf-8"))
        result["tests"]["historical_profiles_unchanged"] = all(item["unchanged"] for item in unchanged) and current_models[:len(original_models)] == original_models
        save(run / "preservation-check.json", unchanged)
    except Exception as error:
        result["error"] = repr(error)
        raise
    finally:
        try:
            if owned_state():
                server.stop()
                result["test_server_stopped"] = True
        finally:
            stop_event.set()
            thread.join(8)
            result["memory"] = {
                "sample_count": len(samples), "sample_interval_seconds": 2,
                "minimum_available_ram_gib": min((s["available_ram_bytes"] for s in samples), default=0) / (1024**3),
                "peak_system_gpu_mib": max((s["gpu_used_mib"] for s in samples if s["gpu_used_mib"] is not None), default=None),
                "peak_server_private_gib": max((s["process_private_bytes"] for s in samples if s["process_private_bytes"] is not None), default=0) / (1024**3),
                "limits": "Periodically sampled system GPU total; may miss instantaneous peaks. Not a long-context workload or sustained reliability test.",
            }
            result["passed"] = bool(result["tests"]) and all(result["tests"].values()) and "error" not in result
            result["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save(run / "verification.json", result)
            with zipfile.ZipFile(run / "verification-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                for path in [pathlib.Path(__file__), ROOT / "scripts/client.py", ROOT / "scripts/server.py", ROOT / "scripts/memory.py", ROOT / "profiles" / (profile_name + ".json"), ROOT / "model-manifest.json", ROOT / "bin/b11960-cuda12.4/runtime-manifest.json"]:
                    archive.write(path, str(path.relative_to(ROOT)))
            print(json.dumps({"event": "verification_complete", **result}, ensure_ascii=False), flush=True)
    return result["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", type=pathlib.Path)
    parser.add_argument("--profile", default="lfm3")
    args = parser.parse_args()
    sys.exit(0 if run_probe(args.run_dir, args.output_dir, args.profile) else 1)
