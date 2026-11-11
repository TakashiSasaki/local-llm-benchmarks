"""Read-only validation of a continuation over the fixed HumanEval20 selection."""
from .study import ROOT,load,sha,validate_run

def select(problems,plan,root=ROOT):
    assert plan['schema_version']==1 and plan['period']=='period-002'
    assert plan['grader_policy']=='standard-windows-v1' and plan['thinking']=='on'
    source=root/'runs'/plan['source_run'];assert source.resolve().parent==(root/'runs').resolve()
    m=validate_run(source);assert m['period']=='period-002' and m['stop_reason']=='execution_window_deferred' and m['model_failure'] is False
    assert m['execution']['thinking']==plan['thinking'] and m['execution']['grader_policy']==plan['grader_policy']
    assert m['config']['model']['sha256']==plan['model_sha256']
    assert sha(source/'summaries/cases.json')==plan['source_cases_sha256']
    saved=load(source/'summaries/cases.json');ids=[p['task_id'] for p in problems];reference=[p['task_id'] for p in saved]
    assert reference==plan['reference_saved_ids'] and reference==ids[:len(reference)]
    assert set(plan['reference_raw_sha256'])==set(reference)
    for cid in reference:assert sha(source/'raw'/(cid.replace('/','_')+'.json'))==plan['reference_raw_sha256'][cid]
    pending=[cid for cid in ids if cid not in reference]
    assert pending==plan['pending_ids'] and len(pending)==plan['new_answer_count']
    assert len(reference)==plan['referenced_answer_count'] and len(ids)==plan['combined_expected']
    assert not set(reference).intersection(pending) and len(set(pending))==len(pending)
    return [p for p in problems if p['task_id'] in pending]

def combined_score(problems,plan,new_entries,root=ROOT):
    """Complete subset score plus referenced originals, counted once by task ID."""
    pending=select(problems,plan,root)
    assert [e['task_id'] for e in new_entries]==[p['task_id'] for p in pending]
    saved=load(root/'runs'/plan['source_run']/'summaries/cases.json')
    combined=saved+new_entries
    assert [e['task_id'] for e in combined]==[p['task_id'] for p in problems]
    return {'passed':sum(e['passed'] for e in combined),'expected':len(problems),'referenced_answers':len(saved),'new_answers':len(new_entries),'source_run':plan['source_run'],'scope':'Unique task IDs; original answers referenced, never counted as new inference'}
