"""Repeat the complete Windows task batch after the object-output wrapper fix.

Performance measurements do not use the executor and remain valid. Original
aborted batch logs and progress are retained; exclusions are explicit.
"""
import datetime, hashlib, json, traceback
from grading import freeze
from idle import wait_idle
from server import ROOT,get_json,load_profile,start,stop
from smoke import smoke
from smoke_real_executor import test as real_smoke
from trial import trial

STATE=ROOT/'runs/local-evaluation-progress.json'

def main():
    previous=json.loads((ROOT/'runs/local-evaluation-aborted-object-output.json').read_text(encoding='utf-8'))
    progress={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'powershell-evaluation','benchmarks':previous['benchmarks'],'trials':[],'ssh_tasks':'not run: user has no prepared SSH target','adoption':'not decided; all 12 tasks are required','harness_revision':'PowerShell formatting pipeline explicitly drained before exit; full task batch repeated','excluded_trials':'evaluation-exclusions.json','prior_progress':'runs/local-evaluation-aborted-object-output.json'}
    def update(**fields):
        progress.update(fields); progress['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        temp=STATE.with_suffix('.tmp'); temp.write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(STATE)
        print(json.dumps({'phase':progress['phase'],'model':progress.get('model'),'task':progress.get('task')},ensure_ascii=False),flush=True)
    stop(); freeze()
    progress['evaluation_suite_lock_sha256']=hashlib.sha256((ROOT/'validation/suite-lock.json').read_bytes()).hexdigest()
    try:
        for model in ['qwen','lfm','glm']:
            update(phase='corrected-executor-gates',model=model,task=None)
            try:
                start(model)
                if not wait_idle(): raise RuntimeError('Initial idle condition not met')
                if not smoke(model,thinking=True): raise RuntimeError(model+' protocol smoke failed')
                if not real_smoke(model)['success']: raise RuntimeError(model+' corrected real PowerShell smoke failed')
                if not wait_idle(): raise RuntimeError('Task-group idle condition not met')
                for task in ['PS1','PS2','PS3','PS4']:
                    update(phase='powershell-evaluation',task=task)
                    result=trial(model,task)
                    progress['trials'].append({'run_id':result['run_id'],'task_id':task,'profile_id':result['profile_id'],'success':result['success'],'failure':result['failure'],'wall_seconds':result['wall_seconds']})
                    update()
                if get_json(load_profile(model)['base_url']+'/health').get('status')!='ok': raise RuntimeError('Server not healthy after task group')
            finally: stop()
        update(phase='local-evaluation-complete',model=None,task=None)
    except Exception as e:
        update(phase='requires-investigation',error=str(e),traceback=traceback.format_exc()); raise
    finally: stop()

if __name__=='__main__': main()
