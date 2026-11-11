"""Read-only validation of continuations over the fixed HumanEval20 selection."""
from .study import ROOT, load, sha, validate_run


def reference_entries(plan, root=ROOT):
    """Verify each immutable source, including explicit operator-stop evidence."""
    assert plan['schema_version'] in (1, 2) and plan['period'] == 'period-002'
    assert plan['grader_policy'] == 'standard-windows-v1' and plan['thinking'] == 'on'
    references = plan['references'] if plan['schema_version'] == 2 else [plan]
    assert references and references[0]['source_run'] == plan['source_run']
    assert len({r['source_run'] for r in references}) == len(references)
    saved = []
    for ref in references:
        source = root / 'runs' / ref['source_run']
        assert source.resolve().parent == (root / 'runs').resolve()
        m = validate_run(source)
        assert m['period'] == 'period-002' and m['status'] == 'failed'
        if ref.get('operator_stop'):
            proof = ref['operator_stop']
            evidence = (root / proof['path']).resolve()
            assert evidence.is_relative_to((root / 'runs').resolve())
            assert sha(evidence) == proof['sha256']
            stopped = load(evidence)
            assert stopped['outcome'] == 'operator_stopped'
            assert stopped['child_run'] == source.name
            assert stopped['source_run'] == ref['parent_run']
            assert stopped['remaining_owned_processes'] == 0 and stopped['port_8089_listeners'] == 0
            assert stopped['hold_active'] is True
            assert stopped['observed_child_status'] == m['status']
            assert stopped['observed_child_error'] == m['error']
        else:
            assert m['stop_reason'] == 'execution_window_deferred' and m['model_failure'] is False
        assert m['execution']['thinking'] == plan['thinking']
        assert m['execution']['grader_policy'] == plan['grader_policy']
        assert m['config']['model']['sha256'] == plan['model_sha256']
        if plan['schema_version'] == 2:
            assert sha(source / 'manifest.json') == ref['manifest_sha256']
            assert m['execution']['context'] == 65536 and m['execution']['max_output'] == 64000
            assert m['execution']['temperature'] == 0.6 and m['execution']['seed'] == 42
            anchor = load(root / 'runs' / plan['source_run'] / 'manifest.json')
            original_parent = root / 'runs' / anchor['config']['parent_run']
            source_parent = root / 'runs' / m['config']['parent_run']
            assert source_parent.resolve().parent == (root / 'runs').resolve()
            assert original_parent.resolve().parent == (root / 'runs').resolve()
            assert load(source_parent / 'configs/server-command.json')['args'] == load(original_parent / 'configs/server-command.json')['args']
            assert load(source_parent / 'configs/runtime-file-verification.json')['sha256'] == load(original_parent / 'configs/runtime-file-verification.json')['sha256']
        assert sha(source / 'summaries/cases.json') == ref['source_cases_sha256']
        entries = load(source / 'summaries/cases.json')
        ids = [e['task_id'] for e in entries]
        assert ids == ref['reference_saved_ids'] and len(set(ids)) == len(ids)
        assert set(ref['reference_raw_sha256']) == set(ids)
        assert {f.name for f in (source / 'raw').glob('*.json')} == {cid.replace('/', '_') + '.json' for cid in ids}
        for cid in ids:
            assert sha(source / 'raw' / (cid.replace('/', '_') + '.json')) == ref['reference_raw_sha256'][cid]
        if ref.get('operator_stop'):
            assert stopped['resumed_raw_saved'] == len(entries) == stopped['resumed_graded']
        saved.extend(entries)
    return saved


def select(problems, plan, root=ROOT):
    saved = reference_entries(plan, root)
    ids = [p['task_id'] for p in problems]
    reference = [e['task_id'] for e in saved]
    assert len(set(ids)) == len(ids) and len(set(reference)) == len(reference)
    assert reference == plan['reference_saved_ids'] and reference == ids[:len(reference)]
    pending = [cid for cid in ids if cid not in reference]
    assert pending == plan['pending_ids'] and len(pending) == plan['new_answer_count']
    assert len(reference) == plan['referenced_answer_count'] and len(ids) == plan['combined_expected']
    assert not set(reference).intersection(pending) and len(set(pending)) == len(pending)
    return [p for p in problems if p['task_id'] in pending]


def combined_score(problems, plan, new_entries, root=ROOT):
    """Complete subset score plus referenced originals, counted once by task ID."""
    pending = select(problems, plan, root)
    assert [e['task_id'] for e in new_entries] == [p['task_id'] for p in pending]
    saved = reference_entries(plan, root)
    combined = saved + new_entries
    assert [e['task_id'] for e in combined] == [p['task_id'] for p in problems]
    result = {'passed': sum(e['passed'] for e in combined), 'expected': len(problems),
              'referenced_answers': len(saved), 'new_answers': len(new_entries),
              'source_run': plan['source_run'],
              'scope': 'Unique task IDs; original answers referenced, never counted as new inference'}
    if plan['schema_version'] == 2:
        result['source_runs'] = [r['source_run'] for r in plan['references']]
    return result
