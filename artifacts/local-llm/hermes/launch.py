"""Start the selected local model and the installed Hermes CLI."""
import argparse
import json
import os
import pathlib
import socket
import subprocess
import sys
import urllib.error
import urllib.request

WORK = pathlib.Path(__file__).resolve().parent

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    parser = argparse.ArgumentParser(description="Hermes with local Qwen")
    parser.add_argument("--model", choices=["daily", "large"], default="daily")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--stop", action="store_true")
    action.add_argument("--status", action="store_true")
    action.add_argument("--start-only", action="store_true")
    parser.add_argument("--continue", dest="resume", action="store_true")
    args = parser.parse_args()
    installation = load(WORK / "installation.json")
    profile = load(WORK / "profiles" / (args.model + ".json"))
    lock = load(pathlib.Path(installation["hermes_source"]) / "pm/lock.json")
    python = pathlib.Path(installation["hermes_home"]) / "tools" / (
        "python-" + lock["packages"]["python"]["version"] + "-win32-x64") / "python.exe"
    if not python.is_file():
        raise RuntimeError("Hermes のPythonが見つかりません。hermes pm install を実行してください。")
    env = dict(os.environ, HERMES_HOME=installation["hermes_home"], PYTHONIOENCODING="utf-8")

    def lifecycle(action):
        command = [str(python), str(WORK / "server.py"), action, args.model]
        result = subprocess.run(command, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip())
        if result.stdout.strip():
            print(result.stdout.strip(), flush=True)

    def props():
        try:
            with urllib.request.urlopen(profile["base_url"] + "/props", timeout=5) as response:
                return json.load(response)
        except (urllib.error.URLError, OSError):
            return None

    if args.stop:
        state_path = WORK / "server-state.json"
        if not state_path.exists():
            print("このHermes用モデルは停止しています。")
            return 0
        if load(state_path)["profile"] != args.model:
            raise RuntimeError("選択したモデルと起動中モデルが異なります。--model を確認してください。")
        lifecycle("stop")
        return 0

    current = props()
    if args.status:
        print(json.dumps({"running": current is not None,
                          "model": current.get("model_alias") if current else None,
                          "context_per_slot": current.get("default_generation_settings", {}).get("n_ctx") if current else None,
                          "slots": current.get("total_slots") if current else None}, ensure_ascii=False))
        return 0
    if current is None:
        try:
            with socket.create_connection(("127.0.0.1", profile["port"]), timeout=1):
                raise RuntimeError("同じポートのモデルが起動中です。準備完了を待つか、元の起動元を確認してください。")
        except (ConnectionRefusedError, TimeoutError):
            pass
        print("ローカルQwenを準備しています…", flush=True)
        lifecycle("start")
        current = props()
    if not current or current.get("model_alias") != profile["profile_id"]:
        raise RuntimeError("別のモデルが稼働しています。既存モデルをその起動元で停止してから実行してください。")
    if (current.get("total_slots") != 1 or
            current.get("default_generation_settings", {}).get("n_ctx", 0) < 64000 or
            pathlib.Path(current["model_path"]).resolve() != pathlib.Path(profile["model"]).resolve() or
            not current.get("build_info", "").startswith(profile["runtime_build"] + "-")):
        raise RuntimeError("モデル・コンテキスト・runtime の検証に失敗しました。")
    if args.start_only:
        return 0
    command = [installation["hermes_launcher"], "chat", "--cli", "--provider", "local-qwen",
               "--model", profile["profile_id"], "--in", installation["workspace"]]
    if args.resume:
        command.append("--continue")
    child = subprocess.Popen(command, env=env)
    while True:
        try:
            code = child.wait()
            break
        except KeyboardInterrupt:
            # The console also delivers Ctrl+C to Hermes; let it handle interruption.
            continue
    suffix = " --model large" if args.model == "large" else ""
    print("モデルを停止するコマンド: hermes-local" + suffix + " --stop", flush=True)
    return code

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, KeyError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
