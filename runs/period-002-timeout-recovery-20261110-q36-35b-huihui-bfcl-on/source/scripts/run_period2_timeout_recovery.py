"""One-shot recovery of 647 missing answers, preserving 953 pinned answers.

Preparation/validation is offline. Collection is explicit and shares the original
orchestration lock. A failed recovery must be reconciled, never silently retried.
"""
import argparse
import copy
import gzip
import importlib.util
import json
import msvcrt
import os
from pathlib import Path
import re
import random
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from local_llm_benchmarks.study import ROOT, create_run, load, save, sha, snapshot_sources, now, validate_run
from local_llm_benchmarks.execution_window import require, ExecutionWindowDeferred

PLAN = 'experiments/period-002/configs/timeout-recovery-20261110.json'
PREVIOUS = 'period-002-resumption-20261110'
STAGE_A = 'period-002-stage-a-comparison-20261102'
VALIDATION = 'period-002-he-policy-validation-20261102'
SUBSET = 'experiments/period-002/configs/q35-9b-heretic-bfcl-on-continuation-20261110.json'
KEYS = ['q35-9b-heretic', 'q35-9b-defiant', 'q36-35b-base', 'q36-35b-huihui']
ALL_KEYS = ['q35-4b-base', 'q35-4b-abliterix', 'q35-9b-base', 'q35-9b-huihui'] + KEYS
TIMEOUT_ARGS = ['--api-timeout-seconds', '14400']


def check(condition, message):
    if not condition:
        raise ValueError(message)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def canonical(row):
    return row.get('id', row.get('task_id'))


def pinned_path(relative):
    path = (ROOT / relative).resolve()
    check(path.is_relative_to(ROOT.resolve()), 'Pin escapes repository')
    return path


def build_queue(plan):
    saved = set()
    for ref in plan['references']:
        for identity in ref['ids']:
            key = (ref['model'], ref['suite'], ref['thinking'], identity)
            check(key not in saved, 'Duplicate canonical saved answer: ' + str(key))
            saved.add(key)
    universe = {(key, suite, mode, identity) for key in ALL_KEYS
                for suite, ids in plan['canonical_ids'].items()
                for mode in ['off', 'on'] for identity in ids}
    check(len(plan['canonical_ids']['bfcl']) == 80 and len(set(plan['canonical_ids']['bfcl'])) == 80,
          'BFCL canonical selection must contain 80 unique IDs')
    check(len(plan['canonical_ids']['humaneval']) == 20 and len(set(plan['canonical_ids']['humaneval'])) == 20,
          'HumanEval canonical selection must contain 20 unique IDs')
    check(saved <= universe and len(saved) == 953 and len(universe) == 1600,
          'Checkpoint must cover exactly 953 canonical answers')
    pending = universe - saved
    queue = []
    for key in KEYS:
        for suite in ['bfcl', 'humaneval']:
            for mode in ['off', 'on']:
                ids = [i for i in plan['canonical_ids'][suite] if (key, suite, mode, i) in pending]
                if ids:
                    queue.append(dict(model=key, suite=suite, thinking=mode, ids=ids, count=len(ids)))
    check(sum(r['count'] for r in queue) == len(pending) == 647, 'Recovery queue must contain exactly 647 answers')
    check([r['count'] for r in queue if r['model'] == KEYS[0]] == [7, 20, 20], 'Heretic queue differs')
    check('irrelevance_139' in queue[0]['ids'] and queue[0]['suite'] == 'bfcl' and queue[0]['thinking'] == 'on',
          'Failed question is not in the pending BFCL ON subset')
    for key in KEYS[1:]:
        check(sum(r['count'] for r in queue if r['model'] == key) == 200, 'Full model queue differs')
    return queue


def validate_attempts(plan):
    """Reject any competing parent or unaccounted saved continuation evidence."""
    known = plan['attempts']
    for path in (ROOT / 'runs').glob('period-002-*/manifest.json'):
        name = path.parent.name
        record = load(path)
        if record.get('benchmark') == 'staged-capability-study':
            check(record['status'] != 'running', 'Existing parent is still running: ' + name)
            check(name in plan['historical_parents'], 'Unreconciled staged parent: ' + name)
            check(sha(path) == plan['historical_parents'][name], 'Historical parent changed: ' + name)
        if not any(tag in name for tag in ['resumption', 'timeout-recovery']):
            continue
        check(record['status'] != 'running', 'Existing attempt is still running: ' + name)
        raw = list((path.parent / 'raw').glob('*.json'))
        is_parent = record.get('benchmark') == 'staged-capability-study'
        if raw or is_parent:
            check(name in known, 'Unreconciled existing attempt: ' + name)
            check(sha(path) == known[name]['manifest_sha256'], 'Attempt manifest changed: ' + name)
            check({p.name: sha(p) for p in raw} == known[name]['raw_sha256'], 'Attempt raw set changed: ' + name)


def validate_checkpoint(plan, require_subset=True):
    check(plan['referenced_answers'] == 953 and plan['planned_new_answers'] == 647, 'Incorrect declared totals')
    check(plan['api_timeout_seconds'] == 14400, 'Timeout policy differs')
    validate_attempts(plan)
    for relative, digest in plan['files'].items():
        check(sha(pinned_path(relative)) == digest, 'Pinned evidence changed: ' + relative)
    bfcl = load(ROOT / 'datasets/bfcl/6ea5797/selected-80.json')
    he = [json.loads(line) for line in gzip.decompress((ROOT / 'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
    check(plan['canonical_ids']['bfcl'] == [r['problem']['id'] for r in bfcl], 'BFCL canonical dataset differs')
    check(plan['canonical_ids']['humaneval'] == [he[i]['task_id'] for i in sorted(random.Random(42).sample(range(164), 20))],
          'HumanEval canonical dataset differs')
    for name in plan['validated_runs']:
        record = validate_run(ROOT / 'runs' / name)
        check(record['status'] in ['complete', 'failed'], 'Nonterminal source: ' + name)
    previous = load(ROOT / 'runs' / PREVIOUS / 'manifest.json')
    check(previous['status'] == 'failed' and previous['stop_reason'] == 'owned_step_failed', 'Wrong failed checkpoint')
    for relative in plan['cleanup_files']:
        check(load(ROOT / relative)['server_stopped'], 'Previous owned server not stopped: ' + relative)
    for key in ['q35-9b-base', 'q35-9b-huihui', 'q35-9b-heretic', 'q35-9b-defiant']:
        path = ROOT / 'runs' / ('period-002-core-followup-20261102-' + key + '-capacity-ngl24-cpu0')
        check(load(path / 'manifest.json')['status'] == 'complete', 'Capacity proof incomplete')
        check(load(path / 'summaries/tool-smoke.json')['transport_and_mode_checks_passed'], 'Capacity smoke failed')
        memory = load(path / 'summaries/memory.json')
        check(memory['peak_gpu_used_mib_system_total'] <= 7676 and memory['minimum_available_ram_bytes'] >= 3 * 1024**3,
              'Capacity evidence violates reserves')
    for ref in plan['references']:
        path = ROOT / 'runs' / ref['run']
        manifest = load(path / 'manifest.json')
        check(manifest['benchmark'] == ref['suite'] and manifest['config']['model']['id'] == ref['model']
              and manifest['execution']['thinking'] == ref['thinking'], 'Reference label differs from manifest')
        metadata = load(ROOT / 'experiments/period-002/models' / (ref['model'] + '.json'))
        check(manifest['config']['model']['sha256'] == metadata['sha256'], 'Reference model pin differs')
        execution = manifest['execution']
        check(all(execution[k] == v for k, v in dict(context=65536, max_output=64000, seed=42,
              temperature=0 if ref['suite'] == 'bfcl' else 0.6).items()), 'Reference sampler/context differs')
        rows = load(path / ref['cases'])
        ids = [canonical(r) for r in rows]
        check(ids == ref['ids'] and len(set(ids)) == len(ids), 'Cases differ: ' + ref['run'])
        raw = list((path / 'raw').glob('*.json'))
        check(len(raw) == len(ids), 'Raw count differs: ' + ref['run'])
        check({p.name for p in raw} == {identity.replace('/', '_') + '.json' for identity in ids}, 'Raw filenames differ')
        if ref['suite'] == 'bfcl':
            check({canonical(load(p)) for p in raw} == set(ids), 'Raw IDs differ: ' + ref['run'])
        check(all((p.relative_to(ROOT).as_posix() in plan['files']) for p in raw), 'Unpinned raw file')
        for relative in ['manifest.json', 'source-manifest.json', ref['cases']]:
            check((path / relative).relative_to(ROOT).as_posix() in plan['files'], 'Unpinned source evidence')
    queue = build_queue(plan)
    if require_subset:
        check(plan['bfcl_continuation']['path'] == SUBSET, 'Wrong subset plan')
        check(plan['bfcl_continuation'].get('sha256') == sha(ROOT / SUBSET), 'Subset plan must be pinned before collection')
        from local_llm_benchmarks.bfcl_subset import select
        selected = select(bfcl, load(ROOT / SUBSET), root=ROOT)
        check([r['problem']['id'] for r in selected] == queue[0]['ids'], 'BFCL subset and queue differ')
    return queue


def timeout_profile(original, pilot=False):
    profile = copy.deepcopy(original)
    check(profile['context_tokens'] == 65536 and profile['max_tokens'] == 64000, 'Output/context policy differs')
    check(not profile.get('benchmark_extra_args') or profile['benchmark_extra_args'] == TIMEOUT_ARGS,
          'Unexpected benchmark overrides')
    profile.update(benchmark_extra_args=TIMEOUT_ARGS[:])
    if pilot:
        # Capacity pilots must finish sampling so the orchestrator can reject
        # an unsafe GPU placement and try the next declared CPU candidate.
        profile.pop('maximum_gpu_used_mib', None)
    else:
        profile['maximum_gpu_used_mib'] = 7676
    return profile


def run(a):
    plan = load(a.plan)
    queue = validate_checkpoint(plan)
    require('period-002', 'timeout recovery admission', 'model-benchmark')
    check(a.id.startswith('period-002-timeout-recovery-'), 'Use a new timeout-recovery run ID')
    check(not (ROOT / 'runs' / a.id).exists(), 'Run ID already exists')
    processes = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -match 'run_period2_(remaining|timeout_recovery)\\.py' } | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
        capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    owners = json.loads(processes.stdout) if processes.stdout.strip() else []
    if isinstance(owners, dict):
        owners = [owners]
    check(not [p for p in owners if int(p['ProcessId']) != os.getpid()], 'Another orchestration process is active')
    with socket.socket() as sock:
        check(sock.connect_ex(('127.0.0.1', 8089)) != 0, 'Existing server must remain untouched')
    stage = module('recovery_stage_a', ROOT / 'scripts/run_period2_stage_a.py')
    policy = stage.ready_policy(ROOT / 'runs' / VALIDATION, a.benchmark_python)
    previous = ROOT / 'runs' / PREVIOUS
    matched = timeout_profile(load(previous / 'configs/cohort-b-matched-profile.json'))
    args = matched['server_args']
    check(args[args.index('-ngl') + 1] == '24' and args[args.index('--n-cpu-moe') + 1] == '0', '9B placement differs')
    runtime = load(ROOT / 'experiments/period-002/environment/handoff-20261106.json')['runtime']
    for artifact in runtime['installed_files_verified']:
        file = Path(matched['runtime_executable']).parent / artifact['filename']
        check(file.stat().st_size == artifact['bytes'] and sha(file) == artifact['sha256'], 'Runtime artifact differs: ' + file.name)
    parent = create_run('Period 002 timeout recovery', 'staged-capability-study', run_id=a.id,
                        config={'resume_from': PREVIOUS, 'planned_new_answers': 647, 'referenced_answers': 953,
                                'api_timeout_seconds': 14400, 'previous_api_timeout_seconds': 7200,
                                'timeout_change': 'Per-request waiting limit only; no grader, sampler or output changes',
                                'checkpoint_sha256': sha(a.plan), 'benchmark_python_verification': 'configs/grader-policy.json',
                                'placement_scope': 'First shared safe declared candidate; not an untested global maximum'})
    snapshot_sources(parent)
    manifest = load(parent / 'manifest.json')
    manifest.update(status='running', started_at=now(), owner_pid=os.getpid())
    save(parent / 'manifest.json', manifest)
    save(parent / 'configs/recovery-checkpoint.json', plan)
    save(parent / 'configs/pending-queue.json', queue)
    save(parent / 'configs/runtime-verification.json', runtime)
    save(parent / 'configs/grader-policy.json', policy)
    save(parent / 'configs/bfcl-continuation-plan.json', load(ROOT / SUBSET))
    completed, children = [], []

    def event(**data):
        row = dict(at=now(), **data)
        with (parent / 'logs/progress.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)

    def execute(command, name, guard_disk=False):
        with (parent / 'logs' / (name + '.log')).open('w', encoding='utf-8') as log:
            child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW,
                                     env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
            event(event='owned_child', step=name, pid=child.pid)
            try:
                while child.poll() is None:
                    if guard_disk:
                        check(shutil.disk_usage('C:/LocalLLM/models').free >= 32 * 1024**3, 'Disk reserve reached; retain fragment')
                    time.sleep(2)
            finally:
                if child.poll() is None:
                    subprocess.run(['taskkill.exe', '/PID', str(child.pid), '/T', '/F'], capture_output=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    child.wait()
        return child.returncode

    def cell(key, profile, run_id, pilot=False):
        require(parent, run_id, 'model-preflight' if pilot else 'model-benchmark')
        with socket.socket() as sock:
            check(sock.connect_ex(('127.0.0.1', 8089)) != 0, 'Existing server must remain untouched')
        profile = timeout_profile(profile, pilot=pilot)
        profile.update(tool_smoke=pilot, humaneval_grader_policy='standard-windows-v1')
        profilepath = parent / 'configs' / (run_id + '-profile.json')
        save(profilepath, profile)
        command = [sys.executable, '-B', '-X', 'utf8', str(ROOT / 'scripts/run_mtp_study.py'), '--id', run_id,
                   '--model-manifest', (parent / 'configs' / (key + '-model.json')).relative_to(ROOT).as_posix(),
                   '--profile', profilepath.relative_to(ROOT).as_posix(), '--mtp', 'off', '--cpu-moe',
                   profile['server_args'][profile['server_args'].index('--n-cpu-moe') + 1], '--load-mode', 'none',
                   '--benchmark-python', str(a.benchmark_python)]
        if pilot:
            command += ['--pilot']
        elif key == KEYS[0]:
            command += ['--bfcl-continuation-plan', str(parent / 'configs/bfcl-continuation-plan.json')]
        children.append(run_id)
        event(event='cell_start', run=run_id, pilot=pilot)
        code = execute(command, run_id)
        path = ROOT / 'runs' / run_id
        record = load(path / 'manifest.json') if (path / 'manifest.json').exists() else {}
        check((path / 'configs/cleanup.json').exists() and load(path / 'configs/cleanup.json')['server_stopped'],
              'Owned child cleanup unverified; stop')
        if record.get('stop_reason') == 'execution_window_deferred':
            raise ExecutionWindowDeferred('Child admission deferred: ' + run_id)
        if code:
            log = path / 'logs/llama-server.log'
            message = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
            if pilot and re.search(r'(cudaMalloc.*failed|CUDA.*out of memory|CUDA error: out of memory)', message, re.I):
                event(event='capacity_rejected', run=run_id, reason='Explicit CUDA allocation failure')
                return False
            raise RuntimeError('Owned cell failed; no automatic inference retry: ' + run_id)
        check(validate_run(path)['status'] == 'complete', 'Child not complete')
        memory = load(path / 'summaries/memory.json')
        check(memory['peak_gpu_used_mib_system_total'] is not None, 'GPU observation unavailable')
        check(memory['minimum_available_ram_bytes'] >= 3 * 1024**3, 'RAM reserve not met')
        if memory['peak_gpu_used_mib_system_total'] > 7676:
            check(pilot, 'Main cell exceeded GPU reserve')
            event(event='capacity_rejected', run=run_id, reason='GPU reserve exceeded', memory=memory)
            return False
        if pilot:
            check(load(path / 'summaries/tool-smoke.json')['transport_and_mode_checks_passed'], 'Tool smoke failed')
        event(event='cell_complete', run=run_id, pilot=pilot, memory=memory)
        return True

    try:
        for cohort, keys in [('b', KEYS[:2]), ('c', KEYS[2:])]:
            for key in keys:
                original = ROOT / 'experiments/period-002/models' / (key + '.json')
                metadata = load(original)
                if cohort == 'b':
                    metadata = load(previous / 'configs' / (key + '-model.json'))
                    pin = load(original)
                    check(all(metadata[f] == pin[f] for f in ['filename', 'bytes', 'sha256', 'revision', 'url']), 'Model metadata differs')
                else:
                    require(parent, 'download ' + key, 'download', int(metadata['bytes'] / (5 * 1024**2)) + 300)
                    check(shutil.disk_usage('C:/LocalLLM/models').free > metadata['bytes'] + 32 * 1024**3, 'Insufficient disk reserve')
                    code = execute([sys.executable, '-B', '-X', 'utf8', str(ROOT / 'scripts/download_pinned_model.py'),
                                    '--manifest', str(original), '--model-dir', 'C:/LocalLLM/models', '--connections', '1',
                                    '--download-query', 'download=true'], key + '-download', True)
                    check(code == 0, 'Pinned download failed; retain fragment and stop')
                    metadata.update(model='Qwen3.6-35B-A3B ' + ('ordinary' if key.endswith('base') else 'Huihui'))
                save(parent / 'configs' / (key + '-model.json'), metadata)
            chosen = matched if cohort == 'b' else None
            if chosen is None:
                for cpu in range(34, 41):
                    profile = timeout_profile(load(ROOT / 'experiments/period-002/configs/q35-4b-base-preflight.json'))
                    args = profile['server_args']
                    args[args.index('-ngl') + 1] = 'all'
                    args[args.index('--n-cpu-moe') + 1] = str(cpu)
                    profile['profile_id'] = 'period2-recovery-cohort-c-nglall-cpu' + str(cpu)
                    if all(cell(key, profile, a.id + '-' + key + '-capacity-nglall-cpu' + str(cpu), True) for key in keys):
                        chosen = profile
                        break
            check(chosen is not None, 'No shared safe placement; no capability collection')
            save(parent / 'configs' / ('cohort-' + cohort + '-matched-profile.json'), chosen)
            for key in keys:
                run_id = a.id + '-' + key
                cell(key, chosen, run_id)
                conditions = []
                for row in [r for r in queue if r['model'] == key]:
                    path = ROOT / 'runs' / (run_id + '-' + row['suite'] + '-' + row['thinking'])
                    check(validate_run(path)['status'] == 'complete', 'Condition not complete')
                    summary = load(path / 'summary.json')
                    cases = load(path / 'summaries' / ('bfcl-cases.json' if row['suite'] == 'bfcl' else 'cases.json'))
                    check(summary['attempted'] == row['count'] and {canonical(r) for r in cases} == set(row['ids']), 'Condition differs from missing queue')
                    conditions.append(dict(run=path.name, count=row['count'], summary=summary))
                completed.append(dict(model=key, new_answers=sum(c['count'] for c in conditions), conditions=conditions))
                save(parent / 'summaries/completed-models.json', completed)
        check(sum(c['new_answers'] for c in completed) == 647, 'Incomplete recovery')
        save(parent / 'summary.json', dict(outcome='passed', new_answers=647, referenced_answers=953,
                                          combined_answers=1600, completed_models=completed, child_runs=children,
                                          api_timeout_seconds=14400, reference_scope='Pinned saved answers, not new inference'))
        manifest.update(status='complete', completed_at=now())
        event(event='remaining_core_complete', new_answers=647, referenced_answers=953)
    except BaseException as error:
        deferred = isinstance(error, ExecutionWindowDeferred)
        manifest.update(status='failed', completed_at=now(), error=repr(error),
                        stop_reason='execution_window_deferred' if deferred else 'owned_step_failed',
                        model_failure=False if deferred else None)
        save(parent / 'summary.json', dict(outcome='deferred' if deferred else 'partial', referenced_answers=953,
                                          planned_new_answers=647, completed_model_answers=sum(c['new_answers'] for c in completed),
                                          completed_models=completed, child_runs=children, reason=str(error),
                                          partial_responses='Preserved in child raw directories; reconcile before any restart'))
        event(event='followup_deferred' if deferred else 'followup_failed', reason=str(error))
        raise
    finally:
        save(parent / 'manifest.json', manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--plan', type=Path, default=ROOT / PLAN)
    parser.add_argument('--benchmark-python', type=Path, required=True)
    parser.add_argument('--validate-only', action='store_true')
    a = parser.parse_args()
    lockpath = ROOT / '.local/locks/period2-remaining.lock'
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    with lockpath.open('a+b') as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        if a.validate_only:
            queue = validate_checkpoint(load(a.plan))
            print(json.dumps(dict(referenced_answers=953, pending_answers=sum(r['count'] for r in queue), queue=queue)))
        else:
            run(a)


if __name__ == '__main__':
    main()
