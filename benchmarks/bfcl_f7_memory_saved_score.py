"""Audit saved BFCL Memory responses and score them without inference."""
import copy
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
for candidate in Path(__file__).resolve().parents:
    if (candidate / 'experiments/registry.json').is_file():
        ROOT = candidate
        break

sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'benchmarks')]
from local_llm_benchmarks.study import create_run, load, now, save, sha

COMMIT = 'f7cf7359b7ac615a0b294831c5ba2bc95ee4a000'
MODEL = 'local-gemma4-f7-prompt'
CATEGORIES = ('memory_kv', 'memory_rec_sum', 'memory_vector')
SOURCE = ROOT / 'runs/period-004-bfcl-f7-gemma4-memory-v5-20261113'
CHECKOUT = ROOT / '.local/official-bfcl-f7cf735/berkeley-function-call-leaderboard'
VENV = ROOT / '.local/bfcl-f7-isolated-20261113'


def rows(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def normalized_file(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


def verify_sources(run):
    inventory = load(ROOT / 'experiments/period-004/configs/bfcl-f7cf735-source-inventory.json')
    assert inventory['commit'] == COMMIT
    package_root = VENV / 'Lib/site-packages'
    pinned = {rel: digest for rel, digest in inventory['files'].items()
              if rel.endswith('.py') or rel.startswith('bfcl_eval/data/')}
    installed_python = {(p.relative_to(package_root)).as_posix()
                        for p in (package_root / 'bfcl_eval').rglob('*.py')}
    assert installed_python == {rel for rel in pinned if rel.endswith('.py')}
    for relative, expected in pinned.items():
        upstream = CHECKOUT / relative
        assert sha(upstream) == expected, relative
        assert normalized_file(upstream) == normalized_file(package_root / relative), relative

    previous_hashes = load(SOURCE / 'source-manifest.json')['files']
    adapter_names = ('call_guard_v5', 'gemma4_adapter', 'gemma4_guarded_adapter_v5',
                     'guarded_decoder_v5', 'guarded_scoring_v5', 'safe_arithmetic')
    sources = [f'benchmarks/bfcl_f7_{name}.py' for name in adapter_names]
    files = {}
    for relative in [*sources, 'benchmarks/bfcl_f7_memory_saved_score.py',
                     'src/local_llm_benchmarks/study.py', 'src/local_llm_benchmarks/periods.py']:
        current = ROOT / relative
        if relative in sources:
            assert sha(current) == previous_hashes[relative], relative
        target = run / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(current, target)
        files[relative] = sha(target)
    save(run / 'source-manifest.json', {'files': files})
    save(run / 'configs/source-verification.json', {
        'commit': COMMIT, 'installed_package': str(package_root / 'bfcl_eval'),
        'matched_after_newline_normalization': len(pinned),
        'matched_python_files': len(installed_python),
        'python': sys.version, 'python_executable': str(sys.executable),
        'python_sha256': sha(Path(sys.executable)),
    })


def no_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto'}:
        raise RuntimeError(f'Network access during offline Memory scoring: {event}')


def audit(run, eval_runner):
    input_dir = SOURCE / 'raw/bfcl-results' / MODEL
    summary = load(SOURCE / 'summary.json')
    manifest = load(SOURCE / 'manifest.json')
    assert manifest['status'] == 'complete'
    assert summary['outcome'] == 'collected' and summary['context_failure_count'] == 0
    assert load(SOURCE / 'configs/cleanup.json')['server_stopped']
    plan = load(SOURCE / 'configs/case-plan.json')
    assert plan['count'] == summary['planned_cases'] == len(plan['ids']) == len(set(plan['ids'])) == 576
    assert not list((SOURCE / 'raw/context-failures').glob('*.json'))
    raw = defaultdict(list)
    hashes = {}

    def record(path):
        hashes[path.relative_to(SOURCE).as_posix()] = sha(path)

    http_paths = sorted((SOURCE / 'raw/http').glob('*.json'))
    for i, path in enumerate(http_paths):
        assert path.stem == f'{i:08d}'
        row = load(path)
        raw[row['case_id']].append((i, row))
        record(path)
    expected = {}
    observed = {}
    prerequisite = {}
    counts = {}
    result_paths = sorted(input_dir.rglob('*_result.json'))
    assert {p.relative_to(SOURCE).as_posix() for p in result_paths} == set(summary['result_files'])
    for path in result_paths:
        record(path)
        for row in rows(path):
            case = row['id']
            assert case not in observed
            observed[case] = row
    for category in CATEGORIES:
        entries = eval_runner.load_dataset_entry(category, include_prereq=True)
        prefix = f'{category}_prereq_'
        prereqs = {item['id']: item for item in entries if item['id'].startswith(prefix)}
        assert len(entries) == 192 and len(prereqs) == 37
        assert not set(expected).intersection(item['id'] for item in entries)
        expected.update((item['id'], item) for item in entries)
        snapshot = input_dir / 'agentic/memory' / category.removeprefix('memory_') / 'memory_snapshot'
        assert {p.stem for p in (snapshot / 'prereq_checkpoints').glob('*.json')} == set(prereqs)
        finals = {}
        counts[category] = Counter()

        for item in entries:
            case = item['id']
            row = observed[case]
            turns = row['result']
            calls = raw[case]
            assert calls and isinstance(turns, list) and all(isinstance(turn, list) and turn for turn in turns), case
            assert [step for turn in turns for step in turn] == [
                http['response']['choices'][0]['message']['content'] or '' for _, http in calls], case
            logged_steps = [step for turn in row['inference_log'] if isinstance(turn, dict)
                            for key, step in turn.items() if key.startswith('step_')]
            assert len(logged_steps) == len(calls), case
            for step, (_, http) in zip(logged_steps, calls):
                assert len([event for event in step if event['role'] == 'assistant']) == 1, case
                assert [event['content'] for event in step if event['role'] == 'inference_input'] == [
                    http['request']], case
                assert [event['content'] for event in step if event['role'] == 'assistant'] == [
                    http['response']['choices'][0]['message']['content'] or ''], case
            deps = item['depends_on']
            assert all(dep in prereqs and prereqs[dep]['scenario'] == item['scenario']
                       and raw[dep][-1][0] < calls[0][0] for dep in deps), case
            if case not in prereqs:
                assert set(deps) == {key for key, entry in prereqs.items()
                                     if entry['scenario'] == item['scenario']}, case
                continue
            assert set(deps) == {key for key, entry in prereqs.items()
                                 if entry['scenario'] == item['scenario']
                                 and raw[key][0][0] < calls[0][0]}, case
            checkpoint = snapshot / 'prereq_checkpoints' / f'{case}.json'
            state = load(checkpoint)
            record(checkpoint)
            previous_state = finals.get(item['scenario'])
            changed = (any(state.values()) if previous_state is None else state != load(previous_state))
            finals[item['scenario']] = checkpoint
            events = [event for step in logged_steps for event in step]
            tools = [event['content'] for event in events if event['role'] == 'tool']
            errors = []
            for response in tools:
                try:
                    body = json.loads(response)
                except json.JSONDecodeError:
                    if response.startswith('Error during execution:'):
                        errors.append(response)
                else:
                    if isinstance(body, dict) and 'error' in body:
                        errors.append(body['error'])
            incomplete_turns = len(turns) != len(item['question'])
            force_quit = any('has been forced to quit' in event['content'] for event in events
                             if event['role'] == 'handler_log')
            counts[category].update({
                'saved': 1, 'checkpoints': 1, 'state_changed': int(changed),
                'tool_calls': len(tools), 'tool_errors': len(errors),
                'conversations_with_tool_errors': int(bool(errors)),
                'forced_step_stop': int(force_quit), 'incomplete_turns': int(incomplete_turns),
            })
            prerequisite[case] = {
                'depends_on': deps, 'scenario': item['scenario'], 'observed_turns': len(turns),
                'expected_turns': len(item['question']), 'state_changed': changed,
                'checkpoint': checkpoint.relative_to(SOURCE).as_posix(),
                'tool_calls': len(tools), 'tool_errors': errors, 'forced_step_stop': force_quit,
            }
        assert len(finals) == 5
        for scenario, latest in finals.items():
            final = snapshot / f'{scenario}_final.json'
            assert load(final) == load(latest), (category, scenario)
            record(final)

    assert set(raw) == set(observed) == set(plan['ids']) == set(expected)
    assert len(prerequisite) == 111
    for filename in ('manifest.json', 'summary.json', 'configs/case-plan.json',
                     'configs/cleanup.json', 'logs/server.log', 'source-manifest.json'):
        record(SOURCE / filename)
    save(run / 'configs/evidence-verification.json', {
        'source_run': SOURCE.name, 'cases': len(observed), 'raw_http_responses': len(http_paths),
        'files_sha256': hashes, 'prerequisite_counts': counts, 'prerequisites': prerequisite,
        'scoring_dependencies': {key: entry['depends_on'] for key, entry in expected.items()
                                 if key not in prerequisite},
    })
    return observed, counts, len(http_paths)


def setup_scorer(eval_runner):
    from bfcl_f7_gemma4_guarded_adapter_v5 import GuardedGemma4
    from bfcl_f7_guarded_decoder_v5 import install_guarded_decoder
    from bfcl_f7_guarded_scoring_v5 import install_case_allowlists
    def reject_inference(*args, **kwargs):
        raise RuntimeError('Inference is disabled for saved-result scoring')

    install_guarded_decoder()
    install_case_allowlists(eval_runner)
    handler = GuardedGemma4('period4-bfcl-gemma4', 0, MODEL, False)
    handler._query_prompting = reject_inference
    return handler


def score(run, eval_runner, handler, observed):
    from bfcl_f7_call_guard_v5 import UnsupportedCall

    scores = {}
    for category in CATEGORIES:
        prompts = eval_runner.load_dataset_entry(
            category, include_prereq=False, include_language_specific_hint=False)
        ground = eval_runner.load_ground_truth_entry(category)
        assert len(prompts) == len(ground) == 155
        per_case = {}
        errors = []
        scored = []
        for prompt, truth in zip(prompts, ground):
            case = prompt['id']
            assert case.removeprefix(category) == truth['id'].removeprefix('memory'), case
            response = observed[case]
            try:
                outcome = eval_runner._evaluate_single_agentic_entry(
                    handler, case, response['result'], truth['ground_truth'], copy.deepcopy(prompt),
                    MODEL, category)
            except UnsupportedCall as exc:
                per_case[case] = {'status': 'unscored_guard', 'reason': str(exc)}
                continue
            scored.append(response)
            if outcome['valid']:
                per_case[case] = {'status': 'passed'}
            else:
                per_case[case] = {'status': 'failed', 'error_type': outcome['error']['error_type']}
                outcome['inference_log'] = response.get('inference_log', '')
                errors.append(outcome)
        passed = len(scored) - len(errors)
        folder = run / 'raw/category-scores'
        if scored:
            accuracy, total = eval_runner.save_eval_results(
                errors, passed, scored, category, MODEL, folder)
            expected_score, *failed = rows(next(folder.rglob(f'*_{category}_score.json')))
            assert expected_score == {'accuracy': accuracy, 'correct_count': passed, 'total_count': total}
            assert {row['id'] for row in failed} == {case for case, status in per_case.items()
                                                     if status['status'] == 'failed'}
        record = {'dataset': len(prompts), 'scored': len(scored), 'passed': passed,
                  'failed': len(scored) - passed, 'unscored': len(prompts) - len(scored)}
        destination = run / 'summaries' / f'{category}.json'
        payload = {'counts': record, 'cases': per_case}
        save(destination, payload)
        assert load(destination) == payload
        scores[category] = record
    return scores


def main():
    assert Path(sys.executable).resolve() == (VENV / 'Scripts/python.exe').resolve()
    run = create_run(
        'BFCL f7 Gemma4 Memory saved-response scoring', 'bfcl',
        {'official_commit': COMMIT, 'source_run': SOURCE.name, 'new_model_inference': False,
         'scorer': 'pinned upstream agentic evaluator and category writer with v5 decoder guard'},
        run_id=sys.argv[1], kind='replay', period='period-004')
    manifest_path = run / 'manifest.json'
    manifest = load(manifest_path)
    manifest.update(status='running', started_at=now())
    save(manifest_path, manifest)
    try:
        sys.addaudithook(no_network)
        verify_sources(run)
        print('Pinned source files and local adapter hashes verified.', flush=True)
        os.chdir(run / 'workspace')
        os.environ.update(BFCL_PROJECT_ROOT=str(run / 'workspace'), HF_HUB_OFFLINE='1',
                          TRANSFORMERS_OFFLINE='1', LOCAL_SERVER_ENDPOINT='127.0.0.1',
                          LOCAL_SERVER_PORT='8089', BFCL_RAW_HTTP_DIR=str(run / 'raw/http'))
        import bfcl_eval
        assert Path(bfcl_eval.__file__).resolve().is_relative_to(VENV)
        from bfcl_eval.eval_checker import eval_runner
        handler = setup_scorer(eval_runner)
        observed, prereqs, http_count = audit(run, eval_runner)
        print(f'Verified {len(observed)} cases and {http_count} saved HTTP responses.', flush=True)
        scores = score(run, eval_runner, handler, observed)
        summary = {'outcome': 'scored' if all(not v['unscored'] for v in scores.values()) else 'partial',
                   'categories': scores, 'prerequisite_counts': prereqs,
                   'raw_http_responses': http_count, 'new_model_inference': False}
        save(run / 'summary.json', summary)
        assert load(run / 'summary.json') == summary
        manifest.update(status='complete', completed_at=now())
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except BaseException as exc:
        manifest.update(status='failed', failed_at=now(), error=repr(exc))
        raise
    finally:
        save(manifest_path, manifest)


if __name__ == '__main__':
    main()
