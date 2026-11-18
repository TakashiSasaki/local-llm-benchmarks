"""Read-only, pinned continuation of the period-002 BFCL timeout."""
from .study import ROOT, load, sha, validate_run

SOURCE = 'period-002-resumption-20261110-q35-9b-heretic-bfcl-on'
PARENT = 'period-002-resumption-20261110-q35-9b-heretic'

def check(condition, message):
    if not condition:
        raise ValueError(message)

def positive_timeout(value):
    if isinstance(value, bool):
        raise ValueError('API timeout must be a positive integer')
    if not isinstance(value, (int, str)) or not str(value).isdigit() or int(value) <= 0:
        raise ValueError('API timeout must be a positive integer')
    return int(value)

def make_plan(policy_change, root=ROOT):
    """Build pins only; select() must validate before this plan is used."""
    source = root / 'runs' / SOURCE
    m = load(source / 'manifest.json')
    saved = load(source / 'summaries/bfcl-cases.json')
    cases = load(root / 'datasets/bfcl/6ea5797/selected-80.json')
    ids = [c['problem']['id'] for c in cases]
    refs = [e['id'] for e in saved]
    parent = root / 'runs' / PARENT
    return dict(schema_version=1, period='period-002', source_run=SOURCE, parent_run=PARENT,
                source_manifest_sha256=sha(source / 'manifest.json'),
                source_snapshot_sha256=sha(source / 'source-manifest.json'),
                source_cases_sha256=sha(source / 'summaries/bfcl-cases.json'),
                reference_raw_sha256={cid: sha(source / 'raw' / (cid + '.json')) for cid in refs},
                reference_saved_ids=refs, pending_ids=ids[len(refs):], referenced_answer_count=73,
                new_answer_count=7, combined_expected=80, model_sha256=m['config']['model']['sha256'],
                thinking='on', prior_api_timeout_seconds=7200, api_timeout_seconds=14400,
                timeout_policy_change=policy_change,
                parent_evidence_sha256={name: sha(parent / 'configs' / name) for name in
                    ('cleanup.json', 'server-command.json', 'runtime-file-verification.json')})

def reference_entries(plan, root=ROOT):
    check(plan['schema_version'] == 1 and plan['period'] == 'period-002', 'Invalid BFCL continuation schema/period')
    check(plan['source_run'] == SOURCE and plan['parent_run'] == PARENT, 'Unexpected timeout source')
    check(plan['thinking'] == 'on', 'Expected thinking on')
    check(plan['prior_api_timeout_seconds'] == 7200 and plan['api_timeout_seconds'] == 14400,
          'Only the explicit 7200 to 14400 second policy change is supported')
    policy = plan['timeout_policy_change']
    check(isinstance(policy, dict) and policy.get('reason') and policy.get('authorization'), 'Missing timeout policy provenance')
    source = root / 'runs' / SOURCE
    check(sha(source / 'manifest.json') == plan['source_manifest_sha256'], 'Source manifest changed')
    check(sha(source / 'source-manifest.json') == plan['source_snapshot_sha256'], 'Source snapshot manifest changed')
    m = validate_run(source)
    check(m['period'] == 'period-002' and m['status'] == 'failed' and m['error'] == "TimeoutError('timed out')", 'Not the failed timeout run')
    check(m['config']['parent_run'] == PARENT, 'Source parent changed')
    check(m['config']['model']['sha256'] == plan['model_sha256'], 'Model hash differs')
    e = m['execution']
    check(all(e[k] == v for k, v in dict(thinking='on', mode_control='native', context=65536,
          max_output=64000, temperature=0, seed=42, dataset='bfcl/6ea5797/selected-80.json').items()), 'Source protocol differs')
    check(e.get('api_timeout_seconds', 7200) == 7200, 'Source timeout differs')
    parent = root / 'runs' / PARENT
    expected = {'cleanup.json', 'server-command.json', 'runtime-file-verification.json'}
    check(set(plan['parent_evidence_sha256']) == expected, 'Missing parent evidence pins')
    for name, digest in plan['parent_evidence_sha256'].items():
        check(sha(parent / 'configs' / name) == digest, 'Parent evidence changed: ' + name)
    cleanup = load(parent / 'configs/cleanup.json')
    check(cleanup['server_stopped'] is True and cleanup['resource_guard'] == [] and SOURCE in cleanup['child_runs'], 'Source cleanup incomplete')
    check(sha(source / 'summaries/bfcl-cases.json') == plan['source_cases_sha256'], 'Source cases changed')
    saved = load(source / 'summaries/bfcl-cases.json')
    ids = [e['id'] for e in saved]
    check(ids == plan['reference_saved_ids'] and len(ids) == len(set(ids)) == 73, 'Invalid referenced IDs')
    check(set(plan['reference_raw_sha256']) == set(ids), 'Invalid raw pins')
    check({p.name for p in (source / 'raw').glob('*.json')} == {cid + '.json' for cid in ids}, 'Unexpected source raw files')
    for cid in ids:
        check(sha(source / 'raw' / (cid + '.json')) == plan['reference_raw_sha256'][cid], 'Source raw changed: ' + cid)
        check(load(source / 'raw' / (cid + '.json'))['id'] == cid, 'Raw ID differs')
    return saved

def select(cases, plan, root=ROOT):
    saved = reference_entries(plan, root)
    ids = [c['problem']['id'] for c in cases]
    refs = [e['id'] for e in saved]
    check(len(ids) == len(set(ids)) == plan['combined_expected'] == 80, 'Invalid canonical selection')
    check(refs == ids[:73] and plan['referenced_answer_count'] == 73, 'Referenced IDs are not canonical prefix')
    pending = plan['pending_ids']
    check(pending == ids[73:] and len(pending) == len(set(pending)) == plan['new_answer_count'] == 7
          and pending[0] == 'irrelevance_139' and not set(refs).intersection(pending), 'Invalid pending order/IDs')
    return cases[73:]

def validate_target(plan, manifest, params, path, root=ROOT):
    check(path.name != SOURCE and manifest['period'] == 'period-002', 'Continuation requires a new period-002 run')
    source = load(root / 'runs' / SOURCE / 'manifest.json')
    check(manifest['config']['model']['sha256'] == plan['model_sha256'], 'Target model differs')
    original = source['execution']
    check(set(params) == set(original) | {'api_timeout_seconds', 'subset_plan_sha256'}, 'Unexpected protocol override')
    check(all(params[k] == original[k] for k in original if k != 'api_timeout_seconds'), 'Target protocol differs')
    check(params['api_timeout_seconds'] == plan['api_timeout_seconds'], 'Target timeout differs')
    parent_name = manifest['config'].get('parent_run')
    if parent_name:
        parent = root / 'runs' / parent_name
        check(parent.resolve().parent == (root / 'runs').resolve(), 'Invalid target parent')
        for name, key in [('server-command.json', 'args'), ('runtime-file-verification.json', 'sha256')]:
            check(load(parent / 'configs' / name)[key] == load(root / 'runs' / PARENT / 'configs' / name)[key], 'Target runtime/server command differs')
    profile = dict(manifest['config']['profile'])
    original_profile = dict(source['config']['profile'])
    if profile.get('benchmark_extra_args') != original_profile.get('benchmark_extra_args'):
        check(profile.pop('benchmark_extra_args', None) == ['--api-timeout-seconds', '14400']
              and not original_profile.pop('benchmark_extra_args', None), 'Unexpected benchmark overrides')
    if profile.get('api_timeout_seconds') != original_profile.get('api_timeout_seconds'):
        check(profile.pop('api_timeout_seconds', None) == 14400
              and original_profile.pop('api_timeout_seconds', 7200) == 7200, 'Unexpected timeout override')
    check(profile == original_profile, 'Target profile differs')

def combined_score(cases, plan, new_entries, root=ROOT):
    pending = select(cases, plan, root)
    check([e['id'] for e in new_entries] == [c['problem']['id'] for c in pending], 'Fresh IDs differ')
    saved = reference_entries(plan, root)
    combined = saved + new_entries
    return dict(passed=sum(e['passed'] for e in combined), expected=80, attempted=len(combined),
                referenced_answers=73, new_answers=7, source_run=SOURCE,
                categories={cat: {'passed': sum(e['passed'] for e in combined if e['category'] == cat),
                                  'attempted': sum(e['category'] == cat for e in combined)}
                            for cat in ['simple_python', 'multiple', 'parallel', 'irrelevance']},
                scope='Original 73 answers referenced, never copied or counted as fresh inference')
