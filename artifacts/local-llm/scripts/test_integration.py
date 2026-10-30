"""Isolated tests for bounded Windows SSH/SCP adapter; no network or model."""
import json, pathlib, subprocess, sys, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
import agent, bootstrap, executor
from bounded_windows import run_owned
from client import Client
from test_transport_deadlines import FakeHTTP, FakeMonitor

ALIAS='fixture-peer'; JOB='a'*32

class TransportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='transport-integration-')
        self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name)
        self.e=object.__new__(executor.Executor)
        self.e.workspace=str(self.root); self.e.index=self.root/'index'; self.e.index.mkdir()
        self.e.registry=self.root/'registry.json'; self.e.started_jobs=set(); self.e.deadline=None
        self.e.config={'ssh':'ssh-fixture','scp':'scp-fixture','powershell':'powershell-fixture',
                       'ssh_hosts':{ALIAS:{'worker_path':'/dedicated/worker.py',
                         'state_root':'/dedicated/jobs','workspace_root':'/dedicated/work'}}}
        self.start={'host_alias':ALIAS,'cwd':'/dedicated/work/task','script':'sleep 90','timeout':0}
        self.source=self.root/'source.txt'; self.source.write_bytes(b'fixture')
        self.transfer={'host_alias':ALIAS,'direction':'upload','local_path':str(self.source),
                       'remote_path':'/dedicated/work/file.txt'}

    def test_ssh_timeout_preserves_job_and_local_cleanup_result(self):
        error=subprocess.TimeoutExpired('ssh',2); error.cleanup_verified=False
        error.cleanup_error='query failed'; error.pid=4321
        with patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)),patch('executor.run_owned',side_effect=error):
            result=self.e.execute('run_ssh_bash',self.start)
        self.assertEqual(result['job_id'],JOB); self.assertIn(JOB,self.e.started_jobs)
        self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_running'])
        self.assertFalse(result['local_transport_cleanup_verified']); self.assertEqual(result['local_transport_pid'],4321)
        self.assertEqual(result['local_transport_cleanup_error'],'query failed')

    def test_scp_timeout_or_other_error_remains_unknown_and_may_be_partial(self):
        for error in [subprocess.TimeoutExpired('scp',2),OSError('I/O failure'),RuntimeError('output limit')]:
            error.cleanup_verified=True; error.cleanup_error=None; error.pid=123
            with self.subTest(error=error),patch('executor.run_owned',side_effect=error):
                result=self.e.execute('transfer_file',self.transfer)
            self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_partial'])
            self.assertTrue(result['local_transport_cleanup_verified']); self.assertEqual(result['local_transport_pid'],123)
            self.assertIsNone(result['local_sha256']); self.assertIsNone(result['remote_sha256'])

    def test_scp_nonzero_return_is_not_a_completed_transfer(self):
        p=SimpleNamespace(returncode=1,stderr=b'scp failed',stdout=b'')
        with patch('executor.run_owned',return_value=p): result=self.e.execute('transfer_file',self.transfer)
        self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_partial'])
        self.assertEqual(result['exit_code'],1); self.assertTrue(result['real_execution'])

    def test_scp_success_then_local_hash_error_reports_unverified_transfer(self):
        p=SimpleNamespace(returncode=0,stderr=b'',stdout=b'')
        with patch('executor.run_owned',return_value=p),patch.object(pathlib.Path,'read_bytes',side_effect=OSError('hash I/O failure')):
            result=self.e.execute('transfer_file',self.transfer)
        self.assertEqual(result['status'],'unknown'); self.assertEqual(result['exit_code'],0)
        self.assertEqual(result['transfer_client_exit_code'],0); self.assertEqual(result['verification_status'],'incomplete')
        self.assertTrue(result['may_be_partial']); self.assertTrue(result['local_transport_cleanup_verified'])
        self.assertIsNone(result['local_sha256']); self.assertIn('hash I/O failure',result['error'])

    def test_scp_success_then_hash_interrupt_retains_transfer_state(self):
        p=SimpleNamespace(returncode=0,stderr=b'',stdout=b'')
        with patch('executor.run_owned',return_value=p),patch.object(pathlib.Path,'read_bytes',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt) as caught: self.e.execute('transfer_file',self.transfer)
        details=caught.exception.transport_details
        self.assertEqual(details['transfer_client_exit_code'],0); self.assertEqual(details['verification_status'],'incomplete')
        self.assertTrue(details['may_be_partial']); self.assertEqual(details['remote_status'],'unknown')
        self.assertTrue(details['local_transport_cleanup_verified'])

    def test_scp_success_without_local_file_is_not_verified(self):
        p=SimpleNamespace(returncode=0,stderr=b'',stdout=b'')
        self.source.unlink()
        with patch('executor.run_owned',return_value=p): result=self.e.execute('transfer_file',self.transfer)
        self.assertEqual(result['status'],'unknown'); self.assertEqual(result['transfer_client_exit_code'],0)
        self.assertEqual(result['verification_status'],'incomplete'); self.assertTrue(result['may_be_partial'])

    def test_real_local_transport_timeout_preserves_remote_uncertainty(self):
        def real_local_timeout(*args,**kwargs):
            return run_owned([sys.executable,'-c','import time; time.sleep(5)'],timeout=.3)
        with patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)),patch('executor.run_owned',side_effect=real_local_timeout):
            result=self.e.execute('run_ssh_bash',self.start)
        self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_running'])
        self.assertEqual(result['job_id'],JOB); self.assertTrue(result['local_transport_cleanup_verified'])

    def test_real_local_timeout_can_leave_partial_transfer(self):
        partial=self.root/'partial.txt'
        code="import pathlib,time; pathlib.Path("+repr(str(partial))+").write_bytes(b'partial'); time.sleep(5)"
        def real_local_timeout(*args,**kwargs):
            return run_owned([sys.executable,'-c',code],timeout=.4)
        with patch('executor.run_owned',side_effect=real_local_timeout):
            result=self.e.execute('transfer_file',self.transfer)
        self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_partial'])
        self.assertTrue(result['local_transport_cleanup_verified']); self.assertEqual(partial.read_bytes(),b'partial')

    def test_scp_interrupt_keeps_partial_and_cleanup_state(self):
        error=KeyboardInterrupt(); error.cleanup_verified=False; error.cleanup_error='not verified'; error.pid=7
        with patch('executor.run_owned',side_effect=error):
            with self.assertRaises(KeyboardInterrupt) as caught: self.e.execute('transfer_file',self.transfer)
        details=caught.exception.transport_details
        self.assertTrue(details['may_be_partial']); self.assertEqual(details['remote_status'],'unknown')
        self.assertFalse(details['local_transport_cleanup_verified']); self.assertEqual(details['local_transport_pid'],7)

    def test_bridge_uses_exact_stdin_and_timeout(self):
        b=object.__new__(bootstrap.Bridge); b.config=self.e.config; b.alias=ALIAS
        response=SimpleNamespace(returncode=0,stdout=b'answer',stderr=b'')
        with patch('bootstrap.run_owned',return_value=response) as invoke:
            self.assertEqual(b.ssh('python3 -c foo',b'\x00\xe6\x97\xa5',timeout=5),b'answer')
        self.assertEqual(invoke.call_args.kwargs['input_bytes'],b'\x00\xe6\x97\xa5')
        self.assertEqual(invoke.call_args.kwargs['timeout'],5)

    def test_agent_records_interrupt_transport_details_and_job(self):
        root=self.root
        for folder in ('runs','scripts','profiles','workspace'): (root/folder).mkdir()
        p={'profile_id':'dummy','runtime_executable':'bin/dummy','model':'model.gguf','port':8089,
           'server_args':[],'base_url':'http://127.0.0.1:8089','runtime_build':'b11946',
           'model_hash':'x','chat_template_kwargs':{},'sampling':{},'context_tokens':16384,'max_tokens':4096,'seed':42}
        args=[str(root/p['runtime_executable']),'-m',str(root/p['model']),'--host','127.0.0.1',
              '--port','8089','--alias','dummy']
        (root/'server-state.json').write_text(json.dumps({'ready':True,'profile':'qwen','args':args,'pid':1}))
        call={'id':'call1','function':{'name':'run_ssh_bash','arguments':json.dumps(self.start)}}
        class InterruptClient(Client):
            def chat(self,*args,**kwargs):
                return {'message':{'role':'assistant','content':None,'tool_calls':[call]},'finish_reason':'tool_calls',
                        'usage':{'completion_tokens':1},'timings':None}
        interruption=KeyboardInterrupt(); interruption.cleanup_verified=True
        interruption.cleanup_error=None; interruption.pid=987
        responses=[interruption,SimpleNamespace(returncode=0,stdout=b'{}',stderr=b''),
                   SimpleNamespace(returncode=0,stdout=b'{}',stderr=b'')]
        with patch.object(agent,'ROOT',root),patch.object(agent,'load_profile',return_value=p), \
             patch.object(agent,'get_json',return_value={'model_alias':'dummy','build_info':'b11946-test'}), \
             patch.object(agent,'Executor',return_value=self.e),patch.object(agent,'Monitor',FakeMonitor), \
             patch.object(agent,'Client',InterruptClient),patch('urllib.request.urlopen',side_effect=lambda request,timeout:FakeHTTP(request)), \
             patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)),patch('executor.run_owned',side_effect=responses):
            result=agent.run('qwen','synthetic',root/'workspace',task_id='interrupt-transport',limit=30)
        self.assertEqual(result['failure'],'user_interrupted')
        details=result['interrupt_transport_details']
        self.assertEqual(details['job_id'],JOB); self.assertTrue(details['may_be_running'])
        self.assertTrue(details['local_transport_cleanup_verified']); self.assertEqual(details['local_transport_pid'],987)
        self.assertIn(JOB,result['uncompleted_jobs'])
        log=next((root/'runs').glob('*.jsonl'))
        events=[json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
        recorded=next(e for e in events if e['event']=='interrupted')
        self.assertEqual(recorded['transport_details'],details)


if __name__=='__main__': unittest.main(verbosity=2)
