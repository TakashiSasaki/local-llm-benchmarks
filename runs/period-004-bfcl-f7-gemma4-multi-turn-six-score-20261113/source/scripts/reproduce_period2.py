"""Offline recipe by default; opt-in collection against an operator-owned server.

Never downloads, starts/stops a server, changes a period, or resumes saved answers.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('experiments/period-002')
MODELS = ('q35-4b-base', 'q35-4b-abliterix', 'q35-9b-base',
          'q35-9b-huihui', 'q35-9b-heretic', 'q35-9b-defiant',
          'q36-35b-base', 'q36-35b-huihui')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def plan(a, root=ROOT):
    if not re.fullmatch(r'period-\d{3,}', a.period) or int(a.period[7:]) < 3:
        raise ValueError('Use a new period numbered 003 or later, never historical period-002')
    if not re.fullmatch(re.escape(a.period) + r'-[a-z0-9][a-z0-9-]*', a.id):
        raise ValueError('Run ID must begin with the new period and contain lowercase letters/digits/hyphens')
    if (root / 'runs' / a.id).exists():
        raise ValueError('Run already exists; no overwrite or resume is supported')
    metadata = read(root / SOURCE / 'models' / (a.model + '.json'))
    if metadata['revision'] not in metadata['url'] or Path(metadata['filename']).name != metadata['filename']:
        raise ValueError('Expected a pinned single-file model manifest')
    profile = read(root / SOURCE / 'configs/q35-4b-base-preflight.json')
    args = profile['server_args']
    ngl, cpu = ('all', '34') if a.model.startswith('q36-') else ('24', '0') if '-9b-' in a.model else ('all', '0')
    args[args.index('-ngl') + 1] = ngl
    args[args.index('--n-cpu-moe') + 1] = cpu
    alias = 'period2-reproduction-' + a.model
    model_dir = str(a.model_dir) if a.model_dir else '<EXTERNAL_MODEL_DIR>'
    runtime_dir = str(a.runtime_dir) if a.runtime_dir else '<EXTERNAL_RUNTIME_DIR>'
    python = str(a.benchmark_python) if a.benchmark_python else '<BENCHMARK_PYTHON>'
    command = [str(Path(runtime_dir) / 'llama-server.exe'), '-m', str(Path(model_dir) / metadata['filename']),
               '--host', '127.0.0.1', '--port', '8089', '--alias', alias] + args + ['--load-mode', 'none', '--spec-type', 'none']
    benchmark = [python, '-B', '-X', 'utf8', str(root / 'benchmarks' / (a.suite + '.py')),
                 '--run', a.id, '--model', alias, '--thinking', a.thinking,
                 '--api-timeout-seconds', str(a.timeout)]
    if a.suite == 'humaneval':
        benchmark += ['--grader-policy', 'standard-windows-v1']
    return {'scope': 'Fresh single condition, not replay or historical continuation',
            'period': a.period, 'run_id': a.id, 'model': metadata,
            'source_manifest': (SOURCE / 'models' / (a.model + '.json')).as_posix(),
            'source_manifest_sha256': digest(root / SOURCE / 'models' / (a.model + '.json')),
            'timeout_cohort': str(a.timeout) + '-seconds', 'expected_answers': 80 if a.suite == 'bfcl' else 20,
            'alias': alias, 'server_command': command, 'benchmark_command': benchmark,
            'placement': {'gpu_layers': ngl, 'cpu_moe_layers': int(cpu)},
            'download_command': [sys.executable, '-B', 'scripts/download_pinned_model.py', '--manifest',
                                 str(SOURCE / 'models' / (a.model + '.json')), '--model-dir', model_dir]}


def verify_assets(a, recipe, root=ROOT):
    if not all((a.model_dir, a.runtime_dir, a.benchmark_python)):
        raise ValueError('Supply --model-dir, --runtime-dir and --benchmark-python')
    for directory in (a.model_dir, a.runtime_dir):
        if directory.resolve().is_relative_to(root.resolve()):
            raise ValueError('Model and runtime directories must be outside the repository')
    checked = []
    runtime = read(root / SOURCE / 'environment/handoff-20261106.json')['runtime']
    records = [(a.model_dir / recipe['model']['filename'], recipe['model'])]
    # runtime-manifest.json is installation metadata, not a distributed binary.
    records += [(a.runtime_dir / item['filename'], item) for item in runtime['installed_files_verified']
                if item['filename'] != 'runtime-manifest.json']
    pins = read(root / SOURCE / 'environment/planning-20261102.json')['python']['benchmark']['binary_sha256']
    records += [(a.benchmark_python.parent / name, {'sha256': sha}) for name, sha in pins.items()]
    if a.benchmark_python.name.lower() != 'python.exe':
        raise ValueError('Use the recorded Windows python.exe interpreter')
    for path, expected in records:
        if not path.is_file() or ('bytes' in expected and path.stat().st_size != expected['bytes']):
            raise ValueError('Missing or incorrect size: ' + path.name)
        actual = digest(path)
        if actual != expected['sha256']:
            raise ValueError('SHA256 mismatch: ' + path.name)
        checked.append({'filename': path.name, 'sha256': actual})
    return checked


def execute(a, recipe):
    if os.name != 'nt':
        raise ValueError('Fresh collection uses the pinned Windows grader/runtime')
    if not a.confirm_server_command:
        raise ValueError('Start the printed server command yourself, then pass --confirm-server-command')
    if a.suite == 'humaneval' and not a.allow_generated_code:
        raise ValueError('HumanEval executes generated code; isolated machine and --allow-generated-code required')
    registry = read(ROOT / 'experiments/registry.json')
    if registry.get('active_period') != a.period or registry['periods'].get(a.period, {}).get('status') != 'open':
        raise ValueError('Explicitly open the new period with scripts/start_period.py first')
    verified = verify_assets(a, recipe)
    # No arbitrary endpoint option: avoid accidental upload of prompts to a remote service.
    with urllib.request.urlopen('http://127.0.0.1:8089/props', timeout=30) as response:
        props = json.load(response)
    settings = props['default_generation_settings']
    if (props['model_alias'] != recipe['alias'] or not props['build_info'].startswith('b11960-')
            or settings['n_ctx'] != 65536 or props['total_slots'] != 1
            or settings['params']['speculative.types'] not in ([], ['none'], 'none')):
        raise ValueError('Served alias/build/context/slots/MTP does not match recipe')
    sys.path.insert(0, str(ROOT / 'src'))
    from local_llm_benchmarks.study import create_run, snapshot_sources, save, load, now
    from local_llm_benchmarks.execution_window import require
    from local_llm_benchmarks import memory_windows
    require(a.period, 'fresh reproduction admission', 'condition')
    memory = memory_windows.snapshot(os.getpid())
    if memory['available_ram_bytes'] < 3 * 1024**3 or memory['gpu_used_mib'] is None or memory['gpu_used_mib'] > 7676:
        raise ValueError('Require 3 GiB available RAM and GPU total <= 7676 MiB before collection')
    run = create_run('Period 002 fresh reproduction ' + a.model, a.suite,
                     config={'period': a.period, 'model': recipe['model'], 'reproduction': recipe}, run_id=a.id, period=a.period)
    snapshot_sources(run)
    save(run / 'configs/asset-verification.json', verified)
    save(run / 'configs/reproduction-plan.json', recipe)
    save(run / 'configs/admission-memory.json', memory)
    save(run / 'configs/operator-attestation.json', {'exact_server_command_confirmed': True,
         'limitation': 'File hashes and props verified; operator confirms model path and placement. Server is operator-owned.'})
    try:
        with (run / 'logs/collection.log').open('w', encoding='utf-8') as log:
            subprocess.run(recipe['benchmark_command'], cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT,
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
    except BaseException as error:
        manifest = load(run / 'manifest.json')
        manifest.update(status='failed', error=repr(error), failed_at=now())
        save(run / 'manifest.json', manifest)
        raise
    return {'run_id': run.name, 'summary': load(run / 'summary.json'), 'server_cleanup': 'Operator must stop their server'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--period', default='period-003')
    p.add_argument('--id', default='period-003-reproduction-example')
    p.add_argument('--model', choices=MODELS, default=MODELS[0])
    p.add_argument('--suite', choices=['bfcl', 'humaneval'], default='bfcl')
    p.add_argument('--thinking', choices=['off', 'on'], default='off')
    p.add_argument('--timeout', type=int, choices=[7200, 14400], default=7200)
    for name in ('model-dir', 'runtime-dir', 'benchmark-python'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--verify-assets', action='store_true', help='Offline full-file hashing; no inference')
    p.add_argument('--execute', action='store_true', help='Fresh inference; never resumes a run')
    p.add_argument('--confirm-server-command', action='store_true')
    p.add_argument('--allow-generated-code', action='store_true')
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    recipe = plan(a)
    if a.execute:
        result = execute(a, recipe)
    elif a.verify_assets:
        result = {'offline': True, 'verified_files': verify_assets(a, recipe), 'plan': recipe}
    else:
        result = {'offline': True, 'assets_verified': False, 'plan': recipe}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
