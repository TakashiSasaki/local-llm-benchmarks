"""Add the official Q8_0 checkpoint without changing the QAD profile."""
import datetime
import json
import pathlib
import shutil
import urllib.request
from install_lfm3_runtime import ROOT, fetch_verified, save, sha256, utc

run = ROOT / "runs" / ("lfm3-q8-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
run.mkdir()
with urllib.request.urlopen("https://huggingface.co/api/models/LiquidAI/LFM3-1.7B-GGUF?blobs=true", timeout=40) as response:
    metadata = json.load(response)
save(run / "model-metadata.json", metadata)
file = next(f for f in metadata["siblings"] if f["rfilename"] == "LFM3-1.7B-Q8_0.gguf")
profile_path = ROOT / "profiles/lfm3-q8.json"
if profile_path.exists():
    raise RuntimeError("Q8 profile already exists; inspect before replacing")
paths = [ROOT / "runtime-manifest.json", ROOT / "runtime-current.json", ROOT / "model-manifest.json"]
paths += list((ROOT / "profiles").glob("*.json")) + list((ROOT / "hermes/profiles").glob("*.json"))
baseline = []
for path in paths:
    dest = run / "before" / path.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    baseline.append({"path": str(path), "sha256": sha256(path)})
save(run / "preserved-before.json", baseline)
model_path = ROOT / "models" / file["rfilename"]
url = f"https://huggingface.co/{metadata['id']}/resolve/{metadata['sha']}/{file['rfilename']}"
save(run / "download-plan.json", {"path": str(model_path), "url": url, "bytes": file["size"], "sha256": file["lfs"]["sha256"]})
print(json.dumps({"run_dir": str(run)}), flush=True)
fetch_verified({"path": str(model_path), "url": url, "bytes": file["size"], "sha256": file["lfs"]["sha256"]})
manifest_path = ROOT / "model-manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
model = dict(next(m for m in manifest if m["filename"] == "LFM3-1.7B-QAD-Q4_0.gguf"))
model.update(filename=file["rfilename"], repo=metadata["id"], revision=metadata["sha"], bytes=file["size"], sha256=file["lfs"]["sha256"], url=url, verified_utc=utc())
if any(m["filename"] == model["filename"] for m in manifest):
    raise RuntimeError("Q8 model already registered")
save(manifest_path, manifest + [model])
profile = json.loads((ROOT / "profiles/lfm3.json").read_text(encoding="utf-8"))
profile.update(profile_id="lfm3-1.7b-q8-64k", status="Installed; verification pending", model="models/" + model["filename"], model_hash=model["sha256"], parser="Embedded GGUF Jinja and b11960 parser; verification pending")
profile.pop("verification_record", None)
save(profile_path, profile)
save(run / "installation.json", {"model": model, "profile": str(profile_path), "run_dir": str(run), "runtime": "b11960-cuda12.4"})
print(json.dumps({"event": "installed", "run_dir": str(run), "profile": str(profile_path)}), flush=True)
