"""Inventory pinned external artifacts and stream-hash installed copies; no downloads."""
import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def capture(output, model_dir, runtime_dir):
    assert not output.exists(), 'Never overwrite an asset snapshot'
    manifests = [ROOT / 'artifacts/local-llm/model-manifest.json', ROOT / 'artifacts/local-llm/hermes/installation.json', *sorted((ROOT / 'configs/models').glob('*.json'))]
    models = {}
    for path in manifests:
        d = read(path)
        entries = d if isinstance(d, list) else [d['daily_model']] if 'daily_model' in d else [d]
        for m in entries:
            previous = models.get(m['filename'])
            if previous:
                assert previous['sha256'] == m['sha256']
                previous['sources'].append(path.relative_to(ROOT).as_posix())
            else:
                models[m['filename']] = {**m, 'sources': [path.relative_to(ROOT).as_posix()]}
    for m in models.values():
        p = model_dir / m['filename']
        result = {'present': p.is_file(), 'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if p.is_file():
            result.update(bytes=p.stat().st_size, sha256=sha(p))
            result['matches_pinned_artifact'] = result['bytes'] == m['bytes'] and result['sha256'] == m['sha256']
            assert result['matches_pinned_artifact'], m['filename']
        m['end_of_period_verification'] = result
        m['role'] = 'vision projector' if m['filename'].startswith('mmproj-') else 'not measured; acquisition preparation only' if m.get('quantization') in ['Q4_K_S', 'Q4_K_L'] else 'measured model' if 'quantization' in m else 'measured historical model'
        print(json.dumps({'verified_model': m['filename'], 'present': result['present']}), flush=True)
    runtimes = []
    for rel in ['artifacts/local-llm/runtime-manifest.json', 'artifacts/local-llm/bin/b11960-cuda12.4/runtime-manifest.json']:
        m = read(ROOT / rel)
        checked = []
        for entry in m['files']:
            p = runtime_dir.parent / pathlib.Path(entry['path'])
            assert p.is_file(), str(p)
            value = sha(p)
            assert value == entry['sha256'] and p.stat().st_size == entry['bytes'], p.name
            checked.append({'filename': p.name, 'bytes': p.stat().st_size, 'sha256': value})
        exe = runtime_dir / (m['build'] + '-cuda12.4') / 'llama-server.exe'
        v = subprocess.run([str(exe), '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        runtimes.append({'build': m['build'], 'commit': m['commit'], 'version': m.get('version'), 'source_manifest': rel, 'assets': m['assets'], 'installed_files_verified': checked, 'version_output': v.stdout + v.stderr})
        print(json.dumps({'verified_runtime': m['build'], 'files': len(checked)}), flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'captured_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'weights_or_binaries_included': False, 'models': list(models.values()), 'runtimes': runtimes}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=pathlib.Path, required=True)
    p.add_argument('--model-dir', type=pathlib.Path, required=True)
    p.add_argument('--runtime-dir', type=pathlib.Path, required=True)
    a = p.parse_args()
    capture(a.output, a.model_dir, a.runtime_dir)
