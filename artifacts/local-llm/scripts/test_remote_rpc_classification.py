"""Model-free SSH start-response and managed-job classification regressions.

Only the subprocess transport is mocked. These tests do not connect to Linux.
"""
import base64, copy, json, pathlib, subprocess, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
from executor import Executor,RemotePreStartRejected

JOB='a'*32
ALIAS='test-peer'

def worker_result(status='running'):
    def stream(name,data):
        return {name+'_base64':base64.b64encode(data).decode(),name+'_offset':0,
                name+'_next_offset':len(data),name+'_bytes':len(data),
                name+'_truncated':False,name+'_log':'/dedicated/jobs/'+JOB+'/'+name+'.bin'}
    return {'job_id':JOB,'status':status,'exit_code':None if status=='running' else 0,
            'host':ALIAS,'cwd':'/dedicated/work/task','started_utc':'2026-01-01T00:00:00Z',
            'ended_utc':None if status=='running' else '2026-01-01T00:00:01Z',
            'real_execution':True,**stream('stdout','日本語\n'.encode()),**stream('stderr',b'')}

class RemoteStartTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='llm-remote-rpc-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        self.e=object.__new__(Executor); self.e.workspace=str(self.root)
        self.e.index=self.root/'index'; self.e.index.mkdir()
        self.e.registry=self.root/'registry.json'; self.e.started_jobs=set()
        self.e.config={'ssh':'mock-ssh.exe','ssh_hosts':{ALIAS:{
            'worker_path':'/dedicated/executor_worker.py','state_root':'/dedicated/jobs',
            'workspace_root':'/dedicated/work'}}}
        self.request={'host_alias':ALIAS,'script':'sleep 90','cwd':'/dedicated/work/task','timeout':0}

    def invoke(self,response=None,error=None):
        with patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)), \
             patch('executor.run_owned',side_effect=error,return_value=response):
            return self.e.execute('run_ssh_bash',dict(self.request))

    def assert_unknown_managed(self,result):
        self.assertEqual(result['job_id'],JOB)
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(result['may_be_running'])
        self.assertIn(JOB,self.e.started_jobs)
        record=json.loads((self.e.index/(JOB+'.json')).read_text(encoding='utf-8'))
        self.assertEqual(record['host_alias'],ALIAS)
        self.assertNotEqual(record.get('state'),'not_started')

    def test_malformed_transport_output_keeps_managed_id(self):
        for output in (b'{not-json',b'',b'\xff',b'login banner\n{}',b'[]',b'null'):
            with self.subTest(output=output),tempfile.TemporaryDirectory() as temp:
                self.e.index=pathlib.Path(temp); self.e.started_jobs=set()
                result=self.invoke(SimpleNamespace(returncode=0,stdout=output,stderr=b''))
                self.assert_unknown_managed(result)

    def test_invalid_success_envelopes_keep_managed_id(self):
        cases=[]
        def invalid(mutator):
            value=worker_result(); mutator(value); cases.append(value)
        invalid(lambda v:v.pop('job_id'))
        invalid(lambda v:v.update(job_id='b'*32))
        invalid(lambda v:v.pop('status'))
        invalid(lambda v:v.update(status='garbage'))
        invalid(lambda v:v.update(host='wrong-host'))
        invalid(lambda v:v.update(real_execution=False))
        invalid(lambda v:v.pop('exit_code'))
        invalid(lambda v:v.update(exit_code=1))
        invalid(lambda v:v.update(status='completed',exit_code=None,executor_error='ambiguous worker failure'))
        invalid(lambda v:v.pop('stdout_base64'))
        invalid(lambda v:v.update(stdout_base64='!!not-base64!!'))
        invalid(lambda v:v.update(stdout_next_offset=999))
        invalid(lambda v:v.update(stderr_bytes=-1))
        invalid(lambda v:v.update(stderr_truncated=True))
        invalid(lambda v:v.pop('stderr_log'))
        for value in cases:
            with self.subTest(value=value),tempfile.TemporaryDirectory() as temp:
                self.e.index=pathlib.Path(temp); self.e.started_jobs=set()
                p=SimpleNamespace(returncode=0,stdout=json.dumps(value).encode(),stderr=b'')
                self.assert_unknown_managed(self.invoke(p))

    def test_generic_remote_value_error_is_not_prestart_proof(self):
        response={'type':'ValueError','error':'after spawning worker'}
        p=SimpleNamespace(returncode=1,stdout=json.dumps(response).encode(),stderr=b'')
        self.assert_unknown_managed(self.invoke(p))

    def test_transport_error_preserves_id(self):
        self.assert_unknown_managed(self.invoke(error=subprocess.TimeoutExpired('ssh',90)))

    def test_valid_running_and_completed_envelopes(self):
        for status in ('running','completed'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as temp:
                self.e.index=pathlib.Path(temp); self.e.started_jobs=set()
                p=SimpleNamespace(returncode=0,stdout=json.dumps(worker_result(status)).encode(),stderr=b'')
                result=self.invoke(p)
                self.assertEqual(result['status'],status)
                self.assertEqual(result['stdout'],'日本語\n')
                self.assertEqual(result['stderr'],'')
                self.assertEqual(result['job_id'],JOB)
                self.assertIn(JOB,self.e.started_jobs)

    def test_verified_prestart_rejection_only(self):
        # Current RPC never emits this guarantee; the typed exception is reserved
        # for a future explicitly verified pre-launch rejection protocol.
        with patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)), \
             patch.object(self.e,'remote',side_effect=RemotePreStartRejected('verified')):
            with self.assertRaises(RemotePreStartRejected):
                self.e.execute('run_ssh_bash',dict(self.request))
        record=json.loads((self.e.index/(JOB+'.json')).read_text())
        self.assertEqual(record['state'],'not_started')
        self.assertNotIn(JOB,self.e.started_jobs)

    def test_interruption_preserves_reserved_id_for_cleanup(self):
        with patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)), \
             patch.object(self.e,'remote',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.e.execute('run_ssh_bash',dict(self.request))
        self.assertIn(JOB,self.e.started_jobs)
        self.assertNotEqual(json.loads((self.e.index/(JOB+'.json')).read_text()).get('state'),'not_started')

    def test_unknown_alias_is_rejected_before_reservation(self):
        request={**self.request,'host_alias':'unknown'}
        with self.assertRaises(ValueError): self.e.execute('run_ssh_bash',request)
        self.assertFalse(self.e.started_jobs)
        self.assertFalse(list(self.e.index.iterdir()))

    def test_local_spawn_without_worker_metadata_remains_unknown(self):
        self.e.config['powershell']='mock-pwsh.exe'
        def failed_after_spawn(request):
            job=self.root/'jobs'/JOB; job.mkdir(parents=True)
            (job/'request.json').write_text(json.dumps(request),encoding='utf-8')
            raise OSError('simulated failure writing worker.json after Popen')
        with patch('executor.ROOT',self.root),patch('executor.check_cwd',return_value=str(self.root)), \
             patch('executor.uuid.uuid4',return_value=SimpleNamespace(hex=JOB)), \
             patch('executor.launch',side_effect=failed_after_spawn):
            result=self.e.execute('run_powershell',{'script':'Start-Sleep 90','cwd':str(self.root),'timeout':0})
        self.assertEqual(result['status'],'unknown')
        self.assertTrue(result['may_be_running'])
        self.assertIn(JOB,self.e.started_jobs)
        self.assertFalse((self.root/'jobs'/JOB/'worker.json').exists())
        record=json.loads((self.e.index/(JOB+'.json')).read_text())
        self.assertNotEqual(record.get('state'),'not_started')

if __name__=='__main__': unittest.main(verbosity=2)
