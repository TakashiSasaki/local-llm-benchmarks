"""Final local gates/timing repeats, then PS1-PS4 for three fixed profiles.

The eight SSH/Linux tasks remain pending until an actual test peer is supplied.
"""
import datetime, hashlib, json, pathlib, traceback
from benchmark import bench
from grading import freeze
from idle import wait_idle
from server import ROOT,get_json,load_profile,start,stop
from smoke import smoke
from smoke_real_executor import test as real_smoke
from trial import trial

MODELS=['qwen','lfm','glm']
STATE=ROOT/'runs/local-evaluation-progress.json'

def main():
    progress={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'final-gates','benchmarks':{},'trials':[],'ssh_tasks':'not run: user has no prepared SSH target','adoption':'not decided; all 12 tasks are required'}
    def update(**fields):
        progress.update(fields); progress['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        temp=STATE.with_suffix('.tmp'); temp.write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(STATE)
        print(json.dumps({'phase':progress['phase'],'model':progress.get('model'),'task':progress.get('task')},ensure_ascii=False),flush=True)
    stop()
    try:
        freeze()
        for model in MODELS:
            update(phase='final-gates',model=model,task=None)
            try:
                start(model)
                if not wait_idle(): raise RuntimeError('Initial idle condition not met')
                if not smoke(model,thinking=True): raise RuntimeError(model+' final protocol smoke failed')
                if not real_smoke(model)['success']: raise RuntimeError(model+' final real PowerShell smoke failed')
                if not wait_idle(): raise RuntimeError('Pre-benchmark idle condition not met')
                update(phase='three-repeat-performance',model=model)
                result=bench(model,3,purpose='performance',background_downloads=False)
                if len(result['measurements'])!=18 or any(r['finish_reason']!='stop' for r in result['measurements']): raise RuntimeError(model+' performance requests did not all complete')
                if result['memory']['peak_gpu_used_mib_system_total']>7168: raise RuntimeError(model+' exceeded the selected VRAM margin')
                if get_json(load_profile(model)['base_url']+'/health').get('status')!='ok': raise RuntimeError('Server not healthy after timings')
                progress['benchmarks'][model]={'run_id':result['run_id'],'profile_id':result['profile']['profile_id'],'memory':result['memory']}
                update()
            finally: stop()
        # Freeze once all configurations have passed, before observing task outcomes.
        for model in MODELS:
            path=ROOT/'profiles'/f'{model}.json'; profile=load_profile(model)
            profile['status']='fixed for initial task evaluation; Linux/SSH tasks pending'
            profile['parser']='embedded GGUF Jinja and runtime parser; CUDA API tool roundtrip verified'
            path.write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
        freeze()
        progress['evaluation_suite_lock_sha256']=hashlib.sha256((ROOT/'validation/suite-lock.json').read_bytes()).hexdigest()
        for model in MODELS:
            update(phase='powershell-evaluation',model=model,task=None)
            try:
                start(model)
                if not wait_idle(): raise RuntimeError('Task-group idle condition not met')
                for task in ['PS1','PS2','PS3','PS4']:
                    update(task=task)
                    result=trial(model,task)
                    progress['trials'].append({'run_id':result['run_id'],'task_id':task,'profile_id':result['profile_id'],'success':result['success'],'failure':result['failure'],'wall_seconds':result['wall_seconds']})
                    update()
                if get_json(load_profile(model)['base_url']+'/health').get('status')!='ok': raise RuntimeError('Server not healthy after task group')
            finally: stop()
        update(phase='local-evaluation-complete',model=None,task=None)
    except Exception as e:
        update(phase='requires-investigation',error=str(e),traceback=traceback.format_exc())
        raise
    finally: stop()

if __name__=='__main__': main()
