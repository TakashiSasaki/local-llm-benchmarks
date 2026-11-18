"""Verify saved Gemma 4 evidence without executing model completions."""
import gzip
import json
from collections import Counter
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'runs'
DATA = (ROOT / '.local/official-bfcl-f7cf735/berkeley-function-call-leaderboard'
        / 'bfcl_eval/data')
sys.path.insert(0, str(ROOT / 'src'))
from local_llm_benchmarks.study import create_run, load, now, save, sha


def rows(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def humaneval():
    aggregate = RUNS / 'period-004-gemma-humaneval-aggregate-20261112'
    score = RUNS / 'period-004-gemma-humaneval-score-combined-20261112'
    dataset = ROOT / '.local/official-humaneval-b9453e8/data/HumanEval.jsonl.gz'
    assert sha(dataset) == load(score / 'configs/scoring-policy.json')['dataset_sha256']
    with gzip.open(dataset, 'rt', encoding='utf-8') as stream:
        official = {item['task_id']: item['prompt'] for line in stream
                    if (item := json.loads(line))}
    samples_path = aggregate / 'summaries/samples.jsonl'
    samples = rows(samples_path)
    refs = load(aggregate / 'configs/source-references.json')['references']
    assert len(samples) == len(refs) == len(official) == 164
    assert {row['task_id'] for row in samples} == set(official)
    assert {path.stem for path in (score / 'raw').glob('HumanEval_*.json')} == {
        case.replace('/', '_') for case in official}
    source_counts = Counter()
    failure_counts = Counter()
    for sample, ref in zip(samples, refs):
        case = sample['task_id']
        assert set(sample) == {'task_id', 'completion'} and case == ref['task_id']
        filename = case.replace('/', '_') + '.json'
        response = RUNS / ref['run'] / 'raw' / filename
        assert sha(response) == ref['raw_sha256']
        original = load(response)
        assert original['task_id'] == case and original['request']['prompt'] == official[case]
        assert original['response']['content'] == sample['completion']
        outcome = load(score / 'raw' / filename)
        assert outcome['task_id'] == case
        if not outcome['passed']:
            failure_counts[outcome['result'].split(':', 1)[0]] += 1
        source_counts[ref['run']] += 1
    passed = 164 - sum(failure_counts.values())
    assert passed == load(score / 'summary.json')['passed'] == 132
    return {'passed': passed, 'failed': dict(failure_counts), 'total': 164,
            'source_counts': dict(source_counts), 'samples_sha256': sha(samples_path)}


def multiturn(run):
    score = RUNS / 'period-004-bfcl-f7-gemma4-multi-turn-aggregate-v7-score-20261113'
    pending = RUNS / 'period-004-bfcl-f7-gemma4-multi-turn-pending-v7-20261113'
    evidence = load(score / 'configs/evidence-verification.json')
    old_audit = load(score / 'summaries/independent-verification.json')
    prior = load(pending / 'configs/prior-evidence.json')
    categories = old_audit['categories']
    case_files = {category: DATA / f'BFCL_v4_multi_turn_{category}.json'
                  for category in categories}
    dataset = {item['id']: item for path in case_files.values() for item in rows(path)}
    assert len(dataset) == 800
    scored_ids = set(evidence['sources'])
    guards = set(evidence['excluded_guard_interrupted'])
    context = set(evidence['context_failures']) | {evidence['historical_context_failure']['case_id']}
    assert guards == set(prior['guard_interrupted_ids']) == set(old_audit['guard_interrupted'])
    assert context == set(old_audit['context_failures'])
    assert len(guards) == 6 and len(context) == 7 and not guards & scored_ids
    assert len(scored_ids) == 794 and context <= scored_ids and scored_ids | guards == set(dataset)
    for category, counts in categories.items():
        path, = (score / 'raw').rglob(f'*_multi_turn_{category}_score.json')
        header, *failures = rows(path)
        assert header['correct_count'] == counts['correct'] and header['total_count'] == counts['scored']
        assert len(failures) == len({f['id'] for f in failures}) == counts['errors']
        assert sha(path) == counts['score_sha256']
        if category == 'long_context':
            assert {f['id'] for f in failures if f['id'] in context} == context
    interrupted = {}
    for suffix, number, last, count in [('', 0, 5, 6), ('-remaining', 7, 82, 16),
                                         ('-pending', 23, 213, 4), ('-pending-v2', 26, 18, 1),
                                         ('-pending-v3', 55, 310, 1), ('-pending-v4', 90, 378, 1)]:
        source = RUNS / f'period-004-bfcl-f7-gemma4-multi-turn{suffix}-20261113'
        case = f'multi_turn_base_{number}'
        calls = {}
        for i in range(last - count + 1, last + 1):
            path = source / 'raw/http' / f'{i:08d}.json'
            assert sha(path) == prior['raw_sha256'][source.name][path.name]
            request = load(path)
            assert request['case_id'] == case
            calls[path.name] = sha(path)
        turns = dataset[case]['question']
        user_messages = [m['content'] for m in request['request']['messages'] if m['role'] == 'user']
        matched = [i for i, turn in enumerate(turns, start=1)
                   if all(any(q['content'] in saved for saved in user_messages) for q in turn)]
        assert matched == [1] and len(turns) > 1
        manifest = load(source / 'manifest.json')
        assert manifest['status'] == 'failed' and 'UnsupportedCall' in manifest['error']
        interrupted[case] = {'status': 'unscored', 'source_run': source.name,
                             'manifest_sha256': sha(source / 'manifest.json'),
                             'stop': manifest['error'], 'raw_http_sha256': calls,
                             'last_saved_response': request['response']['choices'][0]['message']['content'],
                             'planned_turns': len(turns), 'turns_present_in_last_request': matched}
    assert set(interrupted) == guards
    result = {'categories': categories, 'scored': len(scored_ids), 'normal_collection': 787,
              'context_overflow_scored_as_failure': sorted(context), 'guard_interrupted': interrupted,
              'dataset_file_sha256': {p.name: sha(p) for p in case_files.values()}}
    save(run / 'summaries/multi-turn-exclusions.json', result)
    return result


def single_or_format(score_id, expected_count):
    run = RUNS / score_id
    evidence = load(run / 'configs/evidence-verification.json')
    assert evidence['case_count'] == evidence['unique_ids'] == expected_count
    assert not evidence['missing'] and not evidence['duplicates']
    source = RUNS / evidence['source_run']
    assert load(source / 'manifest.json')['status'] == load(run / 'manifest.json')['status'] == 'complete'
    raw = {p.name for p in (source / 'raw/http').glob('*.json')}
    assert raw == set(evidence['raw_files']) and len(raw) == expected_count
    scores = {}
    for path in (run / 'raw/official-scores/local-gemma4-f7-prompt').rglob('*_score.json'):
        head, *failed = rows(path)
        assert head['total_count'] - head['correct_count'] == len(failed)
        assert len(failed) == len({item['id'] for item in failed})
        scores[path.name] = {**head, 'score_sha256': sha(path)}
    assert sum(s['total_count'] for s in scores.values()) == expected_count
    return scores


def main():
    run = create_run('Gemma 4 saved evaluation audit', 'humaneval-bfcl',
                     {'generation': False, 'candidate_code_execution': False}, kind='replay',
                     run_id=sys.argv[1], period='period-004')
    path = run / 'manifest.json'
    manifest = load(path)
    try:
        script = Path(__file__).resolve()
        relative = script.relative_to(ROOT)
        snapshot = run / 'source' / relative
        snapshot.parent.mkdir(parents=True)
        shutil.copyfile(script, snapshot)
        save(run / 'source-manifest.json', {'files': {relative.as_posix(): sha(snapshot)}})
        report = {'humaneval': humaneval(), 'multi_turn': multiturn(run),
                  'single_turn': single_or_format(
                      'period-004-bfcl-f7-gemma4-single-turn-score-20261112', 3641),
                  'format_sensitivity': single_or_format(
                      'period-004-bfcl-f7-gemma4-format-sensitivity-score-20261113', 5200)}
        save(run / 'summary.json', report)
        assert load(run / 'summary.json') == report
        manifest.update(status='complete', completed_at=now())
    except BaseException as exc:
        manifest.update(status='failed', failed_at=now(), error=repr(exc))
        raise
    finally:
        save(path, manifest)


if __name__ == '__main__':
    main()
