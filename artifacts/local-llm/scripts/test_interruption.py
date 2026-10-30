"""Inject Ctrl+C during a real managed job start; no model inference is used."""
import json, pathlib, uuid
from unittest.mock import patch
import agent, executor
from client import Client
from server import ROOT

def run():
    state=json.loads((ROOT/'server-state.json').read_text())
    model=state['profile']
    if model not in ['qwen','lfm','glm']: raise RuntimeError('A baseline/evaluation model server is required for formatting-only API checks')
    workspace=ROOT/'validation'/('interrupt-'+uuid.uuid4().hex[:10]); workspace.mkdir(parents=True)
    manager=executor.Executor(workspace)
    real_launch=executor.launch
    script="Start-Sleep -Seconds 90\nSet-Content -LiteralPath './must-not-exist.txt' -Value 'late'"
    class SyntheticClient(Client):
        def chat(self,*args,**kwargs):
            self.record('synthetic_control_response',model_inference=False)
            return {'message':{'role':'assistant','content':'','tool_calls':[{'id':'synthetic-interrupt','type':'function','function':{'name':'run_powershell','arguments':json.dumps({'script':script,'cwd':str(workspace),'timeout':30})}}]},'finish_reason':'tool_calls','usage':{'completion_tokens':0},'timings':None,'first_valid_tool_call_seconds':0}
    def interrupted_launch(request):
        request['timeout']=.2
        real_launch(request)
        raise KeyboardInterrupt
    with patch.object(agent,'Executor',return_value=manager),patch.object(agent,'Client',SyntheticClient),patch.object(executor,'launch',interrupted_launch):
        result=agent.run(model,'Synthetic interrupt cleanup test; no inference.',workspace,task_id='harness-interrupt-control',limit=30)
    ids=list(manager.started_jobs)
    status=json.loads((ROOT/'jobs'/ids[0]/'status.json').read_text()) if len(ids)==1 else {}
    checks={'interrupt_recorded':result['failure']=='user_interrupted','only_own_single_job':len(ids)==1,'job_completed_after_stop':status.get('status')=='completed','stop_verified':status.get('stopped') is True,'artifact_absent':not (workspace/'must-not-exist.txt').exists(),'no_jobs_left_running':not result['uncompleted_jobs']}
    report={'kind':'synthetic_control_with_real_local_process','model_inference':False,'checks':checks,'passed':all(checks.values()),'run_id':result['run_id']}
    (ROOT/'runs/interruption-selftest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    if not report['passed']: raise AssertionError('Interrupt cleanup failed')

if __name__=='__main__': run()
