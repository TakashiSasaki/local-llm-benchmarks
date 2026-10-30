"""Install the pinned official LFM3 runtime alongside historical evaluation builds."""
import argparse
import concurrent.futures
import datetime
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = pathlib.Path(r"C:\LocalLLM")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    part = path.with_suffix(path.suffix + ".tmp")
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    part.replace(path)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fetch_verified(item):
    target = pathlib.Path(item["path"])
    if target.exists():
        if target.stat().st_size != item["bytes"] or sha256(target) != item["sha256"]:
            raise RuntimeError(f"Existing file differs from pinned source: {target}")
        print(json.dumps({"event": "reused_verified", "file": target.name}), flush=True)
        return item
    part = target.with_suffix(target.suffix + ".part")
    print(json.dumps({"event": "download_start", "file": target.name, "bytes": item["bytes"]}), flush=True)
    subprocess.run([
        "curl.exe", "--fail", "--location", "--silent", "--show-error",
        "--retry", "4", "--retry-delay", "3", "--connect-timeout", "30",
        "--continue-at", "-", "--output", str(part), item["url"],
    ], check=True)
    if part.stat().st_size != item["bytes"] or sha256(part) != item["sha256"]:
        raise RuntimeError(f"Size or SHA-256 mismatch: {part}")
    part.rename(target)
    print(json.dumps({"event": "verified", "file": target.name, "sha256": item["sha256"]}), flush=True)
    return item


def main(run):
    release = json.loads((run / "binary-release.json").read_text(encoding="utf-8-sig"))
    stable = json.loads((run / "stable-release.json").read_text(encoding="utf-8-sig"))
    metadata = json.loads((run / "model-metadata.json").read_text(encoding="utf-8-sig"))
    source = json.loads((run / "model-source.json").read_text(encoding="utf-8-sig"))
    if stable["tag_name"] != "v0.8.0" or release["tag_name"] != "b11960":
        raise RuntimeError("Unexpected pinned release")
    if stable["target_commitish"] != release["target_commitish"]:
        raise RuntimeError("Stable release and binary commit differ")
    assets = [a for a in release["assets"] if a["name"].endswith("win-cuda-12.4-x64.zip")]
    if len(assets) != 2 or any(not a.get("digest", "").startswith("sha256:") for a in assets):
        raise RuntimeError("Two official CUDA 12.4 assets with published digests are required")
    model_file = next(f for f in metadata["siblings"] if f["rfilename"] == "LFM3-1.7B-QAD-Q4_0.gguf")
    profile_path = ROOT / "profiles/lfm3.json"
    if profile_path.exists():
        raise RuntimeError("LFM3 profile already exists; inspect before replacing")
    preserved = [ROOT / "runtime-manifest.json", ROOT / "model-manifest.json"]
    preserved += list((ROOT / "profiles").glob("*.json"))
    preserved += list((ROOT / "hermes/profiles").glob("*.json"))
    backup = run / "before"
    backup.mkdir(exist_ok=True)
    baseline = []
    for path in preserved:
        relative = path.relative_to(ROOT)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        baseline.append({"path": str(path), "sha256": sha256(path)})
    save(run / "preserved-before.json", baseline)
    downloads = [{
        "path": str(ROOT / "downloads" / a["name"]), "url": a["browser_download_url"],
        "bytes": a["size"], "sha256": a["digest"].removeprefix("sha256:"),
    } for a in assets]
    model = {
        "repo": metadata["id"], "revision": metadata["sha"], "filename": model_file["rfilename"],
        "bytes": model_file["size"], "sha256": model_file["lfs"]["sha256"],
        "license": source.get("cardData", {}).get("license_name", source.get("cardData", {}).get("license")),
        "license_source_repo": source["id"], "license_source_revision": source["sha"],
        "url": f"https://huggingface.co/{metadata['id']}/resolve/{metadata['sha']}/{model_file['rfilename']}",
    }
    downloads.append({"path": str(ROOT / "models" / model["filename"]), **{k: model[k] for k in ["url", "bytes", "sha256"]}})
    save(run / "download-plan.json", downloads)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(fetch_verified, downloads))
    runtime_dir = ROOT / "bin/b11960-cuda12.4"
    runtime_dir.mkdir(exist_ok=True)
    for asset in downloads[:-1]:
        with zipfile.ZipFile(asset["path"]) as archive:
            for member in archive.infolist():
                destination = (runtime_dir / member.filename).resolve()
                if not destination.is_relative_to(runtime_dir.resolve()):
                    raise RuntimeError("Archive path escapes runtime directory")
            archive.extractall(runtime_dir)
    binary = runtime_dir / "llama-server.exe"
    probe = {}
    for name, args in [("version", ["--version"]), ("devices", ["--list-devices"])]:
        result = subprocess.run([str(binary), *args], cwd=runtime_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        (run / f"runtime-{name}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"Runtime preflight {name} failed: {result.returncode}")
        probe[name] = result.stdout + result.stderr
    if "11960" not in probe["version"] or "CUDA0" not in probe["devices"]:
        raise RuntimeError("Unexpected build or CUDA0 unavailable")
    runtime = {
        "version": "v0.8.0", "build": "b11960", "commit": release["target_commitish"],
        "url": release["html_url"], "stable_url": stable["html_url"],
        "directory": str(runtime_dir), "server_executable": str(binary),
        "assets": downloads[:-1], "installed_utc": utc(),
        "files": [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in runtime_dir.rglob("*") if p.is_file()],
    }
    save(runtime_dir / "runtime-manifest.json", runtime)
    for filename in ["README.md", "LICENSE"]:
        url = f"https://huggingface.co/{metadata['id']}/resolve/{metadata['sha']}/{filename}"
        with urllib.request.urlopen(url, timeout=40) as response:
            (run / ("model-" + filename)).write_bytes(response.read())
    manifest_path = ROOT / "model-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(m["filename"] == model["filename"] for m in manifest):
        raise RuntimeError("Model already registered; inspect before replacing")
    model["verified_utc"] = utc()
    save(manifest_path, manifest + [model])
    profile = {
        "profile_id": "lfm3-1.7b-qad-q4-64k", "status": "Installed; verification pending",
        "runtime_build": "b11960", "runtime_executable": "bin/b11960-cuda12.4/llama-server.exe",
        "model": "models/" + model["filename"], "model_hash": model["sha256"],
        "port": 8089, "base_url": "http://127.0.0.1:8089",
        "server_args": ["--device", "CUDA0", "-ngl", "all", "-t", "8", "-tb", "8", "-np", "1", "-c", "65536", "-ctk", "f16", "-ctv", "f16", "-b", "2048", "-ub", "512", "-fa", "auto", "--cache-ram", "0", "--jinja", "--perf", "--fit", "off", "--no-context-shift", "-n", "4096"],
        "sampling": {"temperature": 0.1, "top_k": 50, "repeat_penalty": 1.1},
        "chat_template_kwargs": {"enable_thinking": True},
        "parser": "Embedded GGUF Jinja and b11960 parser; verification pending",
        "max_tokens": 4096, "seed": 42, "context_tokens": 65536,
        "history_policy": "preserve all; stop before context overflow; no silent truncation",
        "limits": {"normal_seconds": 300, "long_seconds": 480, "tool_calls": 12},
        "metrics_unavailable": None,
    }
    save(profile_path, profile)
    save(run / "installation.json", {"runtime": runtime, "model": model, "profile": str(profile_path), "probe": probe, "installed_utc": utc()})
    print(json.dumps({"event": "installed", "runtime": str(binary), "profile": str(profile_path), "run_dir": str(run)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=pathlib.Path, required=True)
    main(parser.parse_args().run_dir)
