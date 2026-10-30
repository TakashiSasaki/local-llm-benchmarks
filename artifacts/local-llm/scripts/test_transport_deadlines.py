"""Deterministic task-budget and transport failure tests; no network used."""
import json, pathlib, subprocess, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
import agent, executor
from client import Client

ALIAS='fixture-peer'; JOB='a'*32

class TransportDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='llm-transport-budget-'); self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        self.e=object.__new__(executor.Executor); self.e.workspace=str(self.root)
        self.e.index=self.root/'index'; self.e.index.mkdir(); self.e.registry=self.root/'registry.json'
        self.e.started_jobs=set(); self.e.deadline=None
        self.e.config={'ssh':'mock-ssh','scp':'mock-scp','ssh_hosts':{ALIAS:{
            'worker_path':'/home/test/llm/worker.py','workspace_root':'/home/test/llm/workspace',
            'state_root':'/home/test/llm/jobs'}}}
        self.source=self.root/'日本語 source.txt'; self.source.write_bytes('日本語\r\n'.encode())
        self.transfer={'host_alias':ALIAS,'direction':'upload','local_path':str(self.source),
                       'remote_path':'/home/test/llm/workspace/日本語 copy.txt'}
        self.start={'host_alias':ALIAS,'script':'sleep 90','cwd':'/home/test/llm/workspace','timeout':0}
    def test_ssh_transport_is_capped_at_remaining_task_budget(self):
        self.e.deadline=110
        p=SimpleNamespace(returncode=0,stdout=b'{}',stderr=b'')
        with patch('executor.time.perf_counter',return_value=107),patch('executor.run_owned',return_value=p) as run:
            self.e.remote(ALIAS,{'action':'poll'})
        self.assertEqual(run.call_args.kwargs['timeout'],3)
    def test_ssh_timeout_preserves_unknown_job(self):
        self.e.deadline=110
        with patch('executor.time.perf_counter',return_value=108.5), \
             patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)), \
             patch('executor.run_owned',side_effect=subprocess.TimeoutExpired('ssh',1.5)) as run:
            result=self.e.execute('run_ssh_bash',self.start)
        self.assertEqual(run.call_args.kwargs['timeout'],1.5)
        self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_running'])
        self.assertEqual(result['job_id'],JOB); self.assertIn(JOB,self.e.started_jobs)
    def test_expired_deadline_starts_no_transport_but_retains_uncertain_id(self):
        self.e.deadline=110
        with patch('executor.time.perf_counter',return_value=110), \
             patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)), \
             patch('executor.run_owned') as run:
            result=self.e.execute('run_ssh_bash',self.start)
        run.assert_not_called(); self.assertEqual(result['status'],'unknown')
        self.assertTrue(result['may_be_running']); self.assertIn(JOB,self.e.started_jobs)
    def test_scp_timeout_is_unknown_and_may_be_partial(self):
        self.e.deadline=110
        with patch('executor.time.perf_counter',return_value=108), \
             patch('executor.run_owned',side_effect=subprocess.TimeoutExpired('scp',2)) as run:
            result=self.e.execute('transfer_file',self.transfer)
        self.assertEqual(run.call_args.kwargs['timeout'],2)
        self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_partial'])
        self.assertIsNone(result['exit_code']); self.assertIsNone(result['remote_sha256'])
    def test_expired_deadline_does_not_start_scp_or_claim_success(self):
        self.e.deadline=110
        with patch('executor.time.perf_counter',return_value=110),patch('executor.run_owned') as run:
            result=self.e.execute('transfer_file',self.transfer)
        run.assert_not_called(); self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_partial'])
    def test_unlimited_cleanup_uses_original_transport_limits(self):
        p=SimpleNamespace(returncode=0,stdout=b'{}',stderr=b'')
        with patch('executor.run_owned',return_value=p) as run:
            self.e.remote(ALIAS,{'action':'poll'})
        self.assertEqual(run.call_args.kwargs['timeout'],90)
        with patch('executor.run_owned',return_value=p) as run:
            result=self.e.execute('transfer_file',self.transfer)
        self.assertEqual(run.call_args.kwargs['timeout'],120); self.assertEqual(result['status'],'completed')

class FakeMonitor:
    def __init__(self,*args): pass
    def start(self): return self
    def stop(self): return {}
class FakeHTTP:
    def __init__(self,request): self.request=request
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self):
        return json.dumps({'prompt':'rendered'} if self.request.full_url.endswith('/apply-template') else {'tokens':[1]}).encode()
class FakeClient(Client):
    def chat(self,*args,**kwargs):
        return {'message':{'role':'assistant','content':'finished'},'finish_reason':'stop',
                'usage':{'completion_tokens':1},'timings':None}

class AgentDeadlineTests(unittest.TestCase):
    def test_task_deadline_applies_to_poll_and_is_cleared_for_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='llm-agent-budget-') as temp:
            root=pathlib.Path(temp)
            for folder in ('runs','scripts','profiles','workspace'): (root/folder).mkdir()
            p={'profile_id':'dummy','runtime_executable':'bin/dummy','model':'model.gguf','port':8089,
               'server_args':[],'base_url':'http://127.0.0.1:8089','runtime_build':'b11946',
               'model_hash':'x','chat_template_kwargs':{},'sampling':{},'context_tokens':16384,
               'max_tokens':4096,'seed':42}
            args=[str(root/p['runtime_executable']),'-m',str(root/p['model']),'--host','127.0.0.1',
                  '--port','8089','--alias','dummy']
            (root/'server-state.json').write_text(json.dumps({'ready':True,'profile':'qwen','args':args,'pid':1}))
            class FakeExecutor:
                def __init__(self):
                    self.started_jobs={JOB}; self.config={'powershell':'fake','ssh_hosts':{}}; self.deadline=None; self.seen=[]
                def execute(self,name,args):
                    self.seen.append((name,self.deadline))
                    if name=='poll_process': return {'status':'running','job_id':JOB}
                    return {'status':'completed','job_id':JOB,'stop_verified':True}
            fake=FakeExecutor()
            with patch.object(agent,'ROOT',root),patch.object(agent,'load_profile',return_value=p), \
                 patch.object(agent,'get_json',return_value={'model_alias':'dummy','build_info':'b11946-test'}), \
                 patch.object(agent,'Executor',return_value=fake),patch.object(agent,'Monitor',FakeMonitor), \
                 patch.object(agent,'Client',FakeClient),patch.object(agent.time,'perf_counter',return_value=100), \
                 patch('urllib.request.urlopen',side_effect=lambda request,timeout:FakeHTTP(request)):
                result=agent.run('qwen','synthetic',root/'workspace',task_id='deadline-control',limit=30)
            self.assertEqual(fake.seen,[('poll_process',130),('stop_process',None)])
            self.assertEqual(result['uncompleted_jobs'],[])

if __name__=='__main__': unittest.main(verbosity=2)
