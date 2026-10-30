"""Simulate process-group stop outcomes without starting processes or contacting SSH.

These tests verify the Python state machine, not actual Linux signal delivery.
"""
import signal
import sys
import types
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
import executor_worker as worker


class Clock:
    def __init__(self): self.now=0.0
    def monotonic(self): return self.now
    def sleep(self,seconds): self.now+=seconds


class Entry:
    def __init__(self,directory,name): self.directory=directory; self.name=name
    def exists(self):
        return self.directory.completed if self.name=='status.json' else self.name=='process.json'


class Directory:
    def __init__(self): self.completed=False
    def __truediv__(self,name): return Entry(self,name)


class FakeGroups:
    name='posix'
    def __init__(self,directory,scenario):
        self.directory=directory; self.scenario=scenario; self.alive=True
        self.signals=[]; self.probes_after_kill=0; self.probes_total=0
    def killpg(self,pid,kind):
        if pid!=12345: raise AssertionError('unexpected group')
        if kind==15:
            self.signals.append(kind)
            if self.scenario=='permission_term': raise PermissionError('term denied')
            self.directory.completed=self.scenario!='missing_status'
            if self.scenario in ('vanish_term','missing_status','reused_id'): self.alive=False
            return
        if kind==9:
            self.signals.append(kind)
            if self.scenario=='permission_kill': raise PermissionError('kill denied')
            if self.scenario=='vanish_kill': self.alive=False
            return
        if kind!=0: raise AssertionError('unexpected signal')
        self.probes_total+=1
        if self.scenario=='permission_probe': raise PermissionError('probe denied')
        if self.scenario=='error_probe': raise OSError(5,'probe I/O error')
        if self.scenario=='reused_id' and self.probes_total>1: self.alive=True
        if self.scenario=='late_exit' and 9 in self.signals:
            self.probes_after_kill+=1
            if self.probes_after_kill>=4: self.alive=False
        if not self.alive: raise ProcessLookupError('group gone')


class StopVerificationTests(unittest.TestCase):
    def simulate(self,scenario):
        directory=Directory(); clock=Clock(); groups=FakeGroups(directory,scenario); writes=[]
        def fake_poll(root,job):
            return {'job_id':job,'status':'completed' if directory.completed else 'running',
                    'exit_code':-15 if directory.completed else None}
        fake_signal=types.SimpleNamespace(SIGTERM=15,SIGKILL=9)
        with patch.object(worker,'job_dir',return_value=directory), \
             patch.object(worker,'read',return_value={'pid':12345,'identity':'known'}), \
             patch.object(worker,'process_identity',return_value='known'), \
             patch.object(worker,'poll',side_effect=fake_poll), \
             patch.object(worker,'put',side_effect=lambda path,data: writes.append(data)), \
             patch.object(worker,'os',groups), patch.object(worker,'signal',fake_signal), \
             patch.object(worker,'time',clock):
            result=worker.stop('unused','a'*32)
        return result,groups,clock,writes

    def test_vanished_group_and_completed_worker_are_verified(self):
        result,groups,_,writes=self.simulate('vanish_term')
        self.assertTrue(result['stop_verified']); self.assertTrue(result['process_group_exited'])
        self.assertEqual(groups.signals,[15]); self.assertTrue(result['stopped'])
        self.assertEqual(len(writes),1)

    def test_group_survives_term_but_disappears_after_kill(self):
        result,groups,clock,_=self.simulate('vanish_kill')
        self.assertEqual(groups.signals,[15,9]); self.assertTrue(result['stop_verified'])
        self.assertGreaterEqual(clock.now,3); self.assertLess(clock.now,4)

    def test_waits_for_group_to_disappear_after_kill(self):
        result,groups,clock,_=self.simulate('late_exit')
        self.assertEqual(groups.signals,[15,9]); self.assertGreaterEqual(groups.probes_after_kill,4)
        self.assertTrue(result['stop_verified']); self.assertLess(clock.now,4)

    def test_completed_worker_but_live_group_is_unverified(self):
        result,groups,clock,writes=self.simulate('still_present')
        self.assertEqual(result['status'],'completed'); self.assertFalse(result['stop_verified'])
        self.assertIs(result['process_group_exited'],False); self.assertNotIn('stopped',result)
        self.assertEqual(groups.signals,[15,9]); self.assertEqual(writes,[])
        self.assertGreaterEqual(clock.now,13); self.assertLess(clock.now,13.2)

    def test_group_gone_but_worker_status_missing_is_unverified(self):
        result,groups,clock,writes=self.simulate('missing_status')
        self.assertEqual(result['status'],'running'); self.assertTrue(result['process_group_exited'])
        self.assertFalse(result['stop_verified']); self.assertEqual(groups.signals,[15])
        self.assertGreaterEqual(clock.now,10); self.assertLess(clock.now,10.2); self.assertEqual(writes,[])

    def test_permission_or_probe_error_stays_unverified(self):
        for scenario in ('permission_term','permission_kill','permission_probe','error_probe'):
            with self.subTest(scenario=scenario):
                result,_,clock,writes=self.simulate(scenario)
                self.assertFalse(result['stop_verified']); self.assertIsNone(result['process_group_exited'])
                self.assertIn('stop_error',result); self.assertNotIn('stopped',result)
                self.assertEqual(writes,[]); self.assertLess(clock.now,3.2)

    def test_reused_group_id_is_not_reported_as_gone(self):
        result,groups,clock,writes=self.simulate('reused_id')
        self.assertEqual(groups.signals,[15]); self.assertFalse(result['stop_verified'])
        self.assertIs(result['process_group_exited'],False); self.assertEqual(writes,[])
        self.assertGreaterEqual(clock.now,10); self.assertLess(clock.now,10.2)

    def test_windows_completion_behavior_is_unchanged(self):
        directory=Directory(); clock=Clock(); writes=[]; calls=[]
        def fake_run(args,**kwargs):
            calls.append(args); directory.completed=True
            return types.SimpleNamespace(returncode=0,stderr='')
        def fake_poll(root,job): return {'job_id':job,'status':'completed','exit_code':1}
        with patch.object(worker,'job_dir',return_value=directory), \
             patch.object(worker,'read',return_value={'pid':12345,'identity':'known'}), \
             patch.object(worker,'process_identity',return_value='known'), \
             patch.object(worker,'poll',side_effect=fake_poll), \
             patch.object(worker,'put',side_effect=lambda path,data: writes.append(data)), \
             patch.object(worker,'os',types.SimpleNamespace(name='nt')), \
             patch.object(worker,'time',clock), patch.object(worker.subprocess,'run',side_effect=fake_run):
            result=worker.stop('unused','a'*32)
        self.assertEqual(calls,[['taskkill','/PID','12345','/T','/F']])
        self.assertEqual(result['stop_scope'],'Windows process tree')
        self.assertTrue(result['stop_verified']); self.assertTrue(result['stopped']); self.assertEqual(len(writes),1)


if __name__=='__main__': unittest.main(verbosity=2)
