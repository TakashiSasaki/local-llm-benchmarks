"""Close a later period without moving or modifying its evidence.

Default: offline validation/dry run. --execute seals membership/evidence and updates
the registry. --verify validates an existing seal. Never handles period-001.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_llm_benchmarks.periods import validate_id
from local_llm_benchmarks.study import validate_run


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def record(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return {'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def folder_for(period, root):
    validate_id(period)
    if int(period[7:]) < 2:
        raise ValueError('period-001 uses its existing frozen closure; never rewrite it')
    return root / 'experiments' / period


def members(period, root):
    result = []
    for folder in sorted((root / 'runs').iterdir()):
        if not folder.is_dir():
            continue
        manifest = folder / 'manifest.json'
        if not manifest.exists():
            if folder.name.startswith(period + '-'):
                raise ValueError('Run folder lacks manifest: ' + folder.name)
            continue
        data = load(manifest)
        if data.get('period') != period and not folder.name.startswith(period + '-'):
            continue
        if data.get('period') != period or not folder.name.startswith(period + '-'):
            raise ValueError('Inconsistent period membership: ' + folder.name)
        if data.get('status') not in ('complete', 'failed'):
            raise ValueError('Nonterminal run: ' + folder.name)
        validate_run(folder)  # includes archived source hashes and membership
        result.append({'run_id': folder.name, 'status': data['status'],
                       'manifest_sha256': record(manifest)['sha256']})
    if not result:
        raise ValueError('Refuse to close an empty period')
    return result


def inventory(period, rows, root):
    folders = [folder_for(period, root)] + [root / 'runs' / row['run_id'] for row in rows]
    files = {}
    for folder in folders:
        for path in sorted(folder.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path == folder_for(period, root) / 'closure.json':
                continue
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Evidence resolves outside the repository: ' + str(path))
            files[path.relative_to(root).as_posix()] = record(path)
    return files


def close(period, execute=False, root=ROOT):
    folder = folder_for(period, root)
    registry_path = root / 'experiments/registry.json'
    original = registry_path.read_bytes()
    registry = json.loads(original)
    info = registry.get('periods', {}).get(period, {})
    if registry.get('active_period') != period or info.get('status') != 'open':
        raise ValueError('Only the active open period may be closed')
    seal_path = folder / 'closure.json'
    if seal_path.exists():
        raise ValueError('Closure already exists; never overwrite or silently retry a partial closure')
    rows = members(period, root)
    files = inventory(period, rows, root)
    # Root maintained source can evolve later; per-run source snapshots are sealed
    # above. These hashes record the current recipe without freezing future work.
    recipe = {}
    for name in ('benchmarks', 'src', 'scripts', 'tools', 'tests'):
        for path in sorted((root / name).rglob('*')):
            if path.is_file() and path.suffix in ('.py', '.ps1', '.json', '.txt') and '__pycache__' not in path.parts:
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Source resolves outside repository')
                recipe[path.relative_to(root).as_posix()] = record(path)
    seal = {'schema_version': 1, 'period': period, 'status': 'closed',
            'closed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'run_ids': [row['run_id'] for row in rows], 'runs': rows, 'files': files,
            'maintained_source_at_close': recipe,
            'scope': 'Immutable period-local records and member run evidence, including archived source snapshots. Root maintained source hashes are provenance only, not frozen future code.',
            'limitations': ['Terminal failed runs remain failed; closure does not certify benchmark success.',
                           'No inference, generated-code execution, external model hashing or runtime hashing performed.',
                           'Operator must stop all writers and finish reports before closure.']}
    if not execute:
        return {'dry_run': True, 'period': period, 'terminal_runs': len(rows), 'evidence_files': len(files)}
    # Recheck membership and every evidence byte immediately before sealing.
    if registry_path.read_bytes() != original or members(period, root) != rows or inventory(period, rows, root) != files:
        raise ValueError('Evidence or registry changed during validation; stop writers and retry')
    with seal_path.open('xb') as out:
        out.write(encode(seal))
    info.update(status='closed', closed_at_utc=seal['closed_at_utc'],
                run_index=seal_path.relative_to(root).as_posix(),
                closure_sha256=record(seal_path)['sha256'])
    registry['active_period'] = None
    temp = registry_path.with_name('registry.close-period.tmp')
    # An interruption may leave closure.json or this temp file. Refuse a blind retry.
    with temp.open('xb') as out:
        out.write(encode(registry))
    if registry_path.read_bytes() != original:
        raise ValueError('Registry changed before commit; closure saved but registry not changed. Inspect manually.')
    temp.replace(registry_path)
    return {'closed': True, 'period': period, 'terminal_runs': len(rows), 'evidence_files': len(files)}


def verify(period, root=ROOT):
    folder = folder_for(period, root)
    registry = load(root / 'experiments/registry.json')
    info = registry['periods'][period]
    path = folder / 'closure.json'
    if info.get('status') != 'closed' or record(path)['sha256'] != info.get('closure_sha256'):
        raise ValueError('Registry/closure state or closure hash differs')
    seal = load(path)
    if seal['period'] != period or seal['status'] != 'closed' or seal['run_ids'] != [r['run_id'] for r in seal['runs']]:
        raise ValueError('Invalid closure membership')
    if members(period, root) != seal['runs'] or inventory(period, seal['runs'], root) != seal['files']:
        raise ValueError('Sealed evidence or membership changed')
    return {'verified': True, 'period': period, 'terminal_runs': len(seal['runs']), 'evidence_files': len(seal['files']), 'inference_performed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--period', required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--execute', action='store_true')
    group.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.period) if args.verify else close(args.period, args.execute), indent=2))
