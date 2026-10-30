"""Aggregate actual P5 trials only. Smoke/selftests/benchmarks are excluded."""
import csv, json, statistics
from server import ROOT

def summarize():
    rows=[]
    exclusions_path=ROOT/'evaluation-exclusions.json'
    excluded=json.loads(exclusions_path.read_text(encoding='utf-8')) if exclusions_path.exists() else {}
    adjudication_path=ROOT/'runs/adjudication.json'
    adjudications=json.loads(adjudication_path.read_text(encoding='utf-8')) if adjudication_path.exists() else {}
    for file in sorted((ROOT/'runs').glob('*.summary.json')):
        r=json.loads(file.read_text(encoding='utf-8'))
        if r.get('task_id') not in ['PS1','PS2','PS3','PS4','B1','B2','B3','B4','S1','S2','S3','S4'] or r.get('diagnostic_cpu_only'): continue
        if r['run_id'] in excluded: continue
        r.update({k:v for k,v in adjudications.get(r['run_id'],{}).items() if k in ['false_completion_claim','wrong_host_operation']})
        rows.append({k:r.get(k) for k in ['run_id','task_id','profile_id','success','wall_seconds','first_valid_tool_call_seconds','model_calls','tool_calls','generated_tokens','failure','intervention','false_completion_claim','wrong_host_operation']})
    with (ROOT/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['run_id','task_id','profile_id','success','wall_seconds','first_valid_tool_call_seconds','model_calls','tool_calls','generated_tokens','failure','intervention','false_completion_claim','wrong_host_operation']); writer.writeheader(); writer.writerows(rows)
    groups={}
    for row in rows: groups.setdefault(row['profile_id'],[]).append(row)
    summaries=[]
    for profile,trials in groups.items():
        successes=[r for r in trials if r['success']]
        summaries.append({'profile_id':profile,'trials':len(trials),'successes':len(successes),'distinct_tasks':len({r['task_id'] for r in trials}),'complete_twelve_task_coverage':len({r['task_id'] for r in trials})==12,'total_seconds_including_failures':sum(r['wall_seconds'] for r in trials),'median_success_seconds':statistics.median([r['wall_seconds'] for r in successes]) if successes else None,'manual_false_completion_adjudication_required':any(r['false_completion_claim'] is None for r in trials)})
    (ROOT/'results-summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'real_model_trials':len(rows),'configurations':summaries},ensure_ascii=False))

if __name__=='__main__': summarize()
