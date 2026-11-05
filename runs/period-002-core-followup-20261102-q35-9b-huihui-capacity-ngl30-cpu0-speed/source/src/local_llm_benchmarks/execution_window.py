"""Period-specific finish-by admission; deadlines do not alter inference conditions."""
import datetime,json
from .study import ROOT,load,now

class ExecutionWindowDeferred(RuntimeError):
    pass

def decide(policy,task,estimated_seconds,at=None):
    at=at or datetime.datetime.now(datetime.timezone.utc)
    if at.tzinfo is None:raise ValueError('Admission time must be timezone-aware')
    deadline=datetime.datetime.fromisoformat(policy['finish_by'])
    if deadline.tzinfo is None:raise ValueError('Finish-by must include timezone')
    reserve=policy['save_reserve_seconds']
    allowed=estimated_seconds is not None and estimated_seconds>=0 and at+datetime.timedelta(seconds=estimated_seconds+reserve)<=deadline
    return {'at':at.isoformat(),'task':task,'allowed':allowed,'estimated_seconds':estimated_seconds,'finish_by':policy['finish_by'],'save_reserve_seconds':reserve,'reason':'Fits finish-by with saving reserve' if allowed else 'Deferred: insufficient finish-by margin or duration unknown'}

def require(run_or_period,task,kind,estimated_seconds=None):
    path=None if isinstance(run_or_period,str) else run_or_period
    period=run_or_period if path is None else load(path/'manifest.json').get('period')
    policyfile=ROOT/'experiments'/str(period)/'configs/execution-window.json'
    if not policyfile.exists():return None
    policy=load(policyfile)
    if not policy.get('enabled'):return None
    estimate=estimated_seconds if estimated_seconds is not None else policy['conservative_estimates_seconds'].get(kind)
    result=decide(policy,task,estimate);result['policy']=policyfile.relative_to(ROOT).as_posix()
    log=(path/'logs/execution-window.jsonl') if path is not None else ROOT/'.local/validation/execution-window.jsonl'
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('a',encoding='utf-8') as out:out.write(json.dumps(result)+'\n')
    if not result['allowed']:raise ExecutionWindowDeferred(result['reason']+'; '+task+'; finish-by '+policy['finish_by'])
    return result

def period_for_id(run_id):
    # Resolve only registered period prefixes; no global deadline for later periods.
    from .periods import registry
    for period in registry(ROOT)['periods']:
        if run_id.startswith(period+'-'):return period
    return None
