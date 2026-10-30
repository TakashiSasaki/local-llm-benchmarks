"""Configure the new Hermes integration without changing evaluation artifacts."""
import copy
import datetime
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\LocalLLM")
WORK = ROOT / "hermes"

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

installation = json.loads((WORK / "installation.json").read_text(encoding="utf-8"))
for folder in ("profiles", "logs", "runs"):
    (WORK / folder).mkdir(exist_ok=True)
old_models = json.loads((ROOT / "model-manifest.json").read_text(encoding="utf-8"))
large_model = next(m for m in old_models if m["filename"] == "Qwen3.6-35B-A3B-UD-Q3_K_M.gguf")
daily_model = {
    "repo": "unsloth/Qwen3.5-4B-GGUF",
    "revision": "e87f176479d0855a907a41277aca2f8ee7a09523",
    "filename": "Qwen3.5-4B-Q4_K_M.gguf",
    "bytes": 2740937888,
    "sha256": "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4",
    "license": "apache-2.0",
    "license_source_repo": "Qwen/Qwen3.5-4B",
    "license_source_revision": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
    "url": "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf",
    "verified_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
model_path = ROOT / "models" / daily_model["filename"]
if model_path.stat().st_size != daily_model["bytes"]:
    raise RuntimeError("Daily model size does not match its pinned metadata")
with model_path.open("rb") as stream:
    actual = hashlib.file_digest(stream, "sha256").hexdigest()
if actual != daily_model["sha256"]:
    raise RuntimeError("Daily model SHA-256 does not match its pinned metadata")
save(WORK / "model-manifest.json", [daily_model, large_model])
large = json.loads((ROOT / "profiles/qwen-hermes-64k.json").read_text(encoding="utf-8"))
large["runtime_executable"] = str(ROOT / large["runtime_executable"])
large["model"] = str(ROOT / large["model"])
save(WORK / "profiles/large.json", large)
daily = copy.deepcopy(large)
daily.update(profile_id="qwen3.5-4b-hermes-64k", model=str(ROOT / "models" / daily_model["filename"]),
             model_hash=daily_model["sha256"], status="Hermes daily model; tool validation pending")
daily["server_args"] = ["--device", "CUDA0", "-ngl", "all", "-t", "8", "-tb", "8", "-np", "1",
                        "-c", "65536", "-ctk", "f16", "-ctv", "f16", "-b", "2048", "-ub", "512",
                        "-fa", "auto", "--cache-ram", "0", "--jinja", "--perf", "--fit", "off",
                        "--no-context-shift", "-n", "4096"]
save(WORK / "profiles/daily.json", daily)
installation.update(server_profile=str(WORK / "profiles/daily.json"), server_profile_name="daily",
                    advanced_server_profile=str(WORK / "profiles/large.json"),
                    server_driver=str(WORK / "server.py"), daily_model=daily_model,
                    model_sha256_reverified=daily_model["sha256"])
installation["selection_note"] = "35B trial observed about 1.29 GiB available RAM with Hermes. No OOM observed. Daily 4B selected; original evaluation artifacts remain intact."
save(WORK / "installation.json", installation)
repo = pathlib.Path(installation["hermes_source"])
sys.path.insert(0, str(repo))
from pm.environments import activate_dependencies
activate_dependencies(repo)
from hermes_cli.config import load_config, save_config
config = load_config()
config["model"]["default"] = daily["profile_id"]
config["providers"]["local-qwen"]["default_model"] = daily["profile_id"]
save_config(config)
print(json.dumps({"model": daily["profile_id"], "context": 65536, "isolated_state": str(WORK)}))
