"""Malformed SSH poll/stop responses must not imply successful completion."""
import base64, copy, json, pathlib, subprocess, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
from executor import Executor

JOB='a'*32; ALIAS='fixture-linux'
def envelope(status='running',exit_code=None,stdout=b'',stderr=b'',stdout_offset=0,stderr_offset=0,more=False):
    value={'job_id':JOB,'host':ALIAS,'cwd':'/home/test/work','status':status,'exit_code':exit_code,'real_execution':True}
    for name,data,offset in [('stdout',stdout,stdout_offset),('stderr',stderr,stderr_offset)]:
        end=offset+len(data); size=end+(1 if more and name=='stdout' else 0)
        value.update({name+'_base64':base64.b64encode(data).decode(),name+'_offset':offset,
                      name+'_next_offset':end,name+'_bytes':size,name+'_truncated':end<size,
                      name+'_log':'/home/test/jobs/'+JOB+'/'+name+'.bin'})
    return value

class RemotePollValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='remote-poll-test-'); self.addCleanup(self.tmp.cleanup)
        root=pathlib.Path(self.tmp.name)
        self.e=object.__new__(Executor); self.e.workspace=str(root); self.e.index=root/'index'; self.e.index.mkdir()
        self.e.registry=root/'registry.json'; self.e.started_jobs=set(); self.e.deadline=None
        self.e.config={'ssh':'mock','ssh_hosts':{ALIAS:{'worker_path':'/home/test/worker.py',
                        'state_root':'/home/test/jobs','workspace_root':'/home/test/work'}}}
        self.e.remember(JOB,ALIAS)
    def invoke(self,action,reply=None,error=None,args=None):
        body=reply if isinstance(reply,bytes) else json.dumps(reply).encode()
        p=SimpleNamespace(returncode=0,stdout=body,stderr=b'')
        with patch('executor.run_owned',side_effect=error,return_value=p):
            return self.e.execute(action,{'job_id':JOB,**(args or {})})
    def assert_unknown(self,result):
        self.assertEqual(result['job_id'],JOB); self.assertEqual(result['host'],ALIAS)
        self.assertEqual(result['status'],'unknown'); self.assertIsNone(result['exit_code'])
        self.assertTrue(result['may_be_running']); self.assertIn(JOB,self.e.started_jobs)
        self.assertNotEqual(self.e.job_info(JOB).get('state'),'not_started')
    def test_valid_running_and_completed_poll(self):
        for status,code in [('running',None),('completed',7)]:
            with self.subTest(status=status):
                result=self.invoke('poll_process',envelope(status,code,stdout='日本語\n'.encode()))
                self.assertEqual(result['status'],status); self.assertEqual(result['exit_code'],code)
                self.assertEqual(result['stdout'],'日本語\n')
    def test_valid_incremental_and_truncated_output_is_preserved(self):
        result=self.invoke('poll_process',envelope('running',None,stdout=b'xy',stdout_offset=2,more=True),args={'stdout_offset':2})
        self.assertEqual(result['status'],'running'); self.assertTrue(result['stdout_truncated'])
        self.assertEqual(result['stdout_offset'],2); self.assertEqual(result['stdout_next_offset'],4)
    def test_valid_remote_unknown_remains_uncertain(self):
        self.assert_unknown(self.invoke('poll_process',envelope('unknown',None)))
    def test_malformed_json_and_transport_errors_remain_uncertain(self):
        for body in [b'{"status":"completed"}',b'{broken',b'',b'\xff',b'[]']:
            with self.subTest(body=body): self.assert_unknown(self.invoke('poll_process',body))
        self.assert_unknown(self.invoke('poll_process',{},error=subprocess.TimeoutExpired('ssh',1)))
    def test_malformed_envelopes_are_not_completion(self):
        bad=[]
        def add(change):
            value=envelope('completed',0,stdout=b'abc'); change(value); bad.append(value)
        add(lambda v:v.update(job_id='b'*32)); add(lambda v:v.update(host='wrong'))
        add(lambda v:v.update(status='bad')); add(lambda v:v.update(exit_code=None))
        add(lambda v:v.update(exit_code=False)); add(lambda v:v.update(real_execution=False))
        add(lambda v:v.pop('cwd')); add(lambda v:v.update(stdout_base64='***'))
        add(lambda v:v.update(stdout_offset=1)); add(lambda v:v.update(stdout_next_offset=999))
        add(lambda v:v.update(stdout_truncated=True)); add(lambda v:v.pop('stderr_log'))
        for value in bad:
            with self.subTest(value=value): self.assert_unknown(self.invoke('poll_process',value))
    def test_stop_requires_explicit_verified_remote_group(self):
        for value in [envelope('completed',-9),{**envelope('completed',-9),'stop_verified':False,'process_group_exited':False}]:
            with self.subTest(value=value):
                result=self.invoke('stop_process',value); self.assert_unknown(result)
                self.assertEqual(result['worker_status'],'completed'); self.assertEqual(result['worker_exit_code'],-9)
                self.assertFalse(result['stop_verified'])
    def test_verified_stop_requires_group_and_stopped_evidence(self):
        value={**envelope('completed',-9),'stop_verified':True,'stopped':True,
               'process_group_exited':True,'stop_scope':'remote POSIX process group'}
        result=self.invoke('stop_process',value)
        self.assertEqual(result['status'],'completed'); self.assertTrue(result['stop_verified'])
        for key in ['stopped','process_group_exited','stop_scope']:
            with self.subTest(missing=key):
                wrong=copy.deepcopy(value); wrong.pop(key); self.assert_unknown(self.invoke('stop_process',wrong))
    def test_unverified_stop_is_persistent_across_polls_and_instances(self):
        result=self.invoke('stop_process',envelope('completed',-9)); self.assert_unknown(result)
        self.assertTrue(self.e.job_info(JOB)['stop_unverified'])
        self.assert_unknown(self.invoke('poll_process',envelope('completed',-9)))
        # A new controller using the same index must not lose the uncertainty.
        other=object.__new__(Executor); other.workspace=self.e.workspace; other.index=self.e.index
        other.registry=self.e.registry; other.started_jobs=set(); other.deadline=None; other.config=self.e.config
        p=SimpleNamespace(returncode=0,stdout=json.dumps(envelope('completed',-9)).encode(),stderr=b'')
        with patch('executor.run_owned',return_value=p): result=other.execute('poll_process',{'job_id':JOB})
        self.assertEqual(result['status'],'unknown'); self.assertTrue(result['may_be_running'])
    def test_verified_group_termination_clears_prior_uncertainty(self):
        self.assert_unknown(self.invoke('stop_process',b'{invalid'))
        self.assert_unknown(self.invoke('poll_process',envelope('completed',0)))
        verified={**envelope('completed',-9),'stop_verified':True,'stopped':True,
                  'process_group_exited':True,'stop_scope':'remote POSIX process group'}
        result=self.invoke('stop_process',verified)
        self.assertEqual(result['status'],'completed'); self.assertTrue(result['stop_verified'])
        self.assertNotIn('stop_unverified',self.e.job_info(JOB))
        self.assertEqual(self.invoke('poll_process',envelope('completed',0))['status'],'completed')
    def test_poll_does_not_clear_explicitly_unverified_stop(self):
        result=self.invoke('poll_process',{**envelope('completed',-9),'stop_verified':False})
        self.assert_unknown(result); self.assertTrue(self.e.job_info(JOB)['stop_unverified'])
    def test_keyboard_interrupt_is_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt): self.invoke('poll_process',{},error=KeyboardInterrupt())
        self.assertIn(JOB,self.e.started_jobs)

if __name__=='__main__': unittest.main(verbosity=2)
