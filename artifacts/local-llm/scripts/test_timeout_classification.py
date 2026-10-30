"""Model-free regression for agent deadline classification.

Run against scripts/agent.py without an HTTP/model server. The deadline and
early-failure cases are injected with a monotonic fake clock. All generated
run files are in TemporaryDirectory, never in C:/LocalLLM.
"""
import importlib.util, json, os, pathlib, sys, tempfile, unittest, urllib.error
from unittest.mock import patch

sys.path.insert(0,r'C:\LocalLLM\scripts')
candidate=os.environ.get('LLM_AGENT_TIMEOUT_DRAFT')
if candidate:
    spec=importlib.util.spec_from_file_location('agent_timeout_candidate',candidate)
    agent=importlib.util.module_from_spec(spec); spec.loader.exec_module(agent)
else:
    import agent
from client import Client

class FakeMonitor:
    def __init__(self,*args): pass
    def start(self): return self
    def stop(self): return {}

class FakeExecutor:
    def __init__(self,*args):
        self.started_jobs=set()
        self.config={'powershell':'test-pwsh','ssh_hosts':{}}

class FakeHTTP:
    def __init__(self,request): self.request=request
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self):
        data={'prompt':'rendered'} if self.request.full_url.endswith('/apply-template') else {'tokens':[1,2,3]}
        return json.dumps(data).encode()

def synthetic_run(error,elapsed):
    with tempfile.TemporaryDirectory(prefix='llm-deadline-test-') as t:
        root=pathlib.Path(t)
        for folder in ['runs','scripts','profiles','workspace']: (root/folder).mkdir()
        profile={'profile_id':'dummy-eval-v1','runtime_executable':'bin/dummy.exe','model':'model.gguf',
                 'port':8089,'server_args':[],'base_url':'http://127.0.0.1:8089',
                 'runtime_build':'b11946','model_hash':'testhash','chat_template_kwargs':{},
                 'sampling':{},'context_tokens':16384,'max_tokens':4096,'seed':42}
        args=[str(root/profile['runtime_executable']),'-m',str(root/profile['model']),
              '--host','127.0.0.1','--port','8089','--alias',profile['profile_id']]
        (root/'server-state.json').write_text(json.dumps({'ready':True,'profile':'qwen','args':args,'pid':999}),encoding='utf-8')
        clock=[100.0]
        class FailingClient(Client):
            def chat(self,*args,**kwargs):
                clock[0]=100.0+elapsed
                raise error
        with patch.object(agent,'ROOT',root), patch.object(agent,'load_profile',return_value=profile), \
             patch.object(agent,'get_json',return_value={'model_alias':profile['profile_id'],'build_info':'b11946-test'}), \
             patch.object(agent,'Executor',FakeExecutor), patch.object(agent,'Monitor',FakeMonitor), \
             patch.object(agent,'Client',FailingClient), patch.object(agent.time,'perf_counter',side_effect=lambda:clock[0]), \
             patch('urllib.request.urlopen',side_effect=lambda request,timeout:FakeHTTP(request)):
            return agent.run('qwen','synthetic only',root/'workspace',task_id='timeout-control',limit=1)

class DeadlineTests(unittest.TestCase):
    def test_direct_timeout_at_deadline(self):
        self.assertEqual(synthetic_run(TimeoutError('stream deadline'),1.1)['failure'],'timeout')
    def test_wrapped_timeout_at_deadline(self):
        self.assertEqual(synthetic_run(urllib.error.URLError(TimeoutError('connect deadline')),1.1)['failure'],'timeout')
    def test_early_timeout_is_environment_error(self):
        self.assertEqual(synthetic_run(TimeoutError('socket closed early'),0.1)['failure'],'environment_or_protocol_error')
    def test_non_timeout_error_after_deadline_is_environment_error(self):
        self.assertEqual(synthetic_run(ConnectionRefusedError('refused'),1.1)['failure'],'environment_or_protocol_error')
    def test_interrupt_remains_interrupt(self):
        self.assertEqual(synthetic_run(KeyboardInterrupt(),0.1)['failure'],'user_interrupted')

if __name__=='__main__': unittest.main()
