"""Model-free checks for cleanup reporting of managed jobs.

The fake HTTP and executor exercise the real agent.run control flow without a
model, a live server, or any Windows/SSH child processes. All run artefacts
are written under a temporary directory.
"""
import json, pathlib, tempfile, unittest
from unittest.mock import patch

import agent
from client import Client

JOB='a'*32

class FakeMonitor:
    def __init__(self,*args): pass
    def start(self): return self
    def stop(self): return {}

class FakeHTTP:
    def __init__(self,request): self.request=request
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self):
        body={'prompt':'rendered'} if self.request.full_url.endswith('/apply-template') else {'tokens':[1,2,3]}
        return json.dumps(body).encode()

class FakeClient(Client):
    def chat(self,*args,**kwargs):
        return {'message':{'role':'assistant','content':'finished'},'finish_reason':'stop',
                'usage':{'completion_tokens':1},'timings':None}

def run_with_stop(stop_result):
    with tempfile.TemporaryDirectory(prefix='llm-cleanup-test-') as t:
        root=pathlib.Path(t)
        for name in ['runs','scripts','profiles','workspace']: (root/name).mkdir()
        profile={'profile_id':'dummy-eval-v1','runtime_executable':'bin/dummy.exe','model':'model.gguf',
                 'port':8089,'server_args':[],'base_url':'http://127.0.0.1:8089',
                 'runtime_build':'b11946','model_hash':'testhash','chat_template_kwargs':{},
                 'sampling':{},'context_tokens':16384,'max_tokens':4096,'seed':42}
        args=[str(root/profile['runtime_executable']),'-m',str(root/profile['model']),
              '--host','127.0.0.1','--port','8089','--alias',profile['profile_id']]
        (root/'server-state.json').write_text(json.dumps({'ready':True,'profile':'qwen','args':args,'pid':999}),encoding='utf-8')
        class FakeExecutor:
            def __init__(self,*args):
                self.started_jobs={JOB}
                self.config={'powershell':'test-pwsh','ssh_hosts':{}}
            def execute(self,name,args):
                assert args['job_id']==JOB
                if name=='poll_process': return {'job_id':JOB,'status':'running','exit_code':None}
                assert name=='stop_process'
                if isinstance(stop_result,Exception): raise stop_result
                return {'job_id':JOB,**stop_result}
        with patch.object(agent,'ROOT',root), patch.object(agent,'load_profile',return_value=profile), \
             patch.object(agent,'get_json',return_value={'model_alias':profile['profile_id'],'build_info':'b11946-test'}), \
             patch.object(agent,'Executor',FakeExecutor), patch.object(agent,'Monitor',FakeMonitor), \
             patch.object(agent,'Client',FakeClient), \
             patch('urllib.request.urlopen',side_effect=lambda request,timeout:FakeHTTP(request)):
            return agent.run('qwen','synthetic only',root/'workspace',task_id='cleanup-control',limit=30)

class CleanupVerificationTests(unittest.TestCase):
    def test_explicitly_unverified_completion_is_preserved(self):
        r=run_with_stop({'status':'completed','stop_verified':False})
        self.assertEqual(r['jobs_unfinished_at_validation'],[JOB])
        self.assertEqual(r['uncompleted_jobs'],[JOB])
        self.assertFalse(r['cleanup_results'][0]['stop_verified'])
    def test_verified_completion_is_cleared(self):
        self.assertEqual(run_with_stop({'status':'completed','stop_verified':True})['uncompleted_jobs'],[])
    def test_completed_without_verification_field_keeps_legacy_behavior(self):
        self.assertEqual(run_with_stop({'status':'completed'})['uncompleted_jobs'],[])
    def test_running_even_with_verified_flag_is_preserved(self):
        self.assertEqual(run_with_stop({'status':'running','stop_verified':True})['uncompleted_jobs'],[JOB])
    def test_stop_error_is_preserved(self):
        self.assertEqual(run_with_stop(RuntimeError('stop failed'))['uncompleted_jobs'],[JOB])

if __name__=='__main__': unittest.main()
