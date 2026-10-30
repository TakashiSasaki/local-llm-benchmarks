"""Real-process Windows tests; no SSH/network or model is used."""
import json, pathlib, subprocess, sys, tempfile, time, unittest
from unittest.mock import patch
import bounded_windows
from bounded_windows import run_owned

class OwnedProcessTests(unittest.TestCase):
    def test_success_input_output_and_large_output(self):
        code="import sys; data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data); sys.stderr.buffer.write(b'error')"
        data=('日本語'*30000).encode()
        result=run_owned([sys.executable,'-c',code],input_bytes=data,timeout=8)
        self.assertEqual(result.returncode,0); self.assertEqual(result.stdout,data); self.assertEqual(result.stderr,b'error')
    def test_descendant_inherits_output_and_is_killed_on_timeout(self):
        with tempfile.TemporaryDirectory(prefix='owned-transport-') as temp:
            marker=pathlib.Path(temp)/'late.txt'; child="import pathlib,time; time.sleep(2); pathlib.Path("+repr(str(marker))+").write_text('late')"
            parent="import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c',"+repr(child)+"]); print(p.pid,flush=True); time.sleep(10)"
            start=time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                run_owned([sys.executable,'-c',parent],timeout=.5,cleanup_wait=2)
            elapsed=time.monotonic()-start
            self.assertTrue(caught.exception.cleanup_verified); self.assertLess(elapsed,2.5)
            time.sleep(2.2); self.assertFalse(marker.exists())
    def test_parent_exits_before_descendant_no_early_success(self):
        with tempfile.TemporaryDirectory(prefix='owned-transport-') as temp:
            marker=pathlib.Path(temp)/'late.txt'; child="import pathlib,time; time.sleep(2); pathlib.Path("+repr(str(marker))+").write_text('late')"
            parent="import subprocess,sys; subprocess.Popen([sys.executable,'-c',"+repr(child)+"])"
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                run_owned([sys.executable,'-c',parent],timeout=.6,cleanup_wait=2)
            self.assertTrue(caught.exception.cleanup_verified)
            time.sleep(2.2); self.assertFalse(marker.exists())
    def test_parent_exits_but_short_child_output_is_collected(self):
        child="import time; time.sleep(.2); print('child output',flush=True)"
        parent="import subprocess,sys; subprocess.Popen([sys.executable,'-c',"+repr(child)+"]); print('parent output',flush=True)"
        result=run_owned([sys.executable,'-c',parent],timeout=4)
        self.assertEqual(result.returncode,0); self.assertIn(b'parent output',result.stdout); self.assertIn(b'child output',result.stdout)
    def test_nonzero_exit_is_returned(self):
        self.assertEqual(run_owned([sys.executable,'-c','import sys; sys.exit(7)'],timeout=4).returncode,7)
    def test_arguments_and_empty_stdin_are_exact(self):
        args=['日本語 空白','x"y',"single'quote",'C:\\path with spaces\\end\\']
        code="import json,sys; sys.stdout.reconfigure(encoding='utf-8'); print(json.dumps({'args':sys.argv[1:],'input':sys.stdin.read()},ensure_ascii=False))"
        result=run_owned([sys.executable,'-c',code,*args],timeout=4)
        self.assertEqual(json.loads(result.stdout.decode('utf-8')),{'args':args,'input':''})
    def test_nonfinite_deadline_is_rejected(self):
        for value in [float('nan'),float('inf'),-1,0]:
            with self.subTest(value=value),self.assertRaises(ValueError): run_owned([sys.executable,'-c','pass'],timeout=value)
    def test_assignment_failure_never_resumes_child(self):
        with tempfile.TemporaryDirectory(prefix='owned-transport-') as temp:
            marker=pathlib.Path(temp)/'must-not-run.txt'
            command="import pathlib; pathlib.Path("+repr(str(marker))+").write_text('executed')"
            with patch.object(bounded_windows.kernel,'AssignProcessToJobObject',return_value=0):
                with self.assertRaises(OSError): run_owned([sys.executable,'-c',command],timeout=4)
            time.sleep(.5); self.assertFalse(marker.exists())
    def test_interrupt_terminates_owned_job(self):
        with tempfile.TemporaryDirectory(prefix='owned-transport-') as temp:
            marker=pathlib.Path(temp)/'late.txt'
            command="import pathlib,time; time.sleep(2); pathlib.Path("+repr(str(marker))+").write_text('late')"
            real_active=bounded_windows._active
            first=[True]
            def interrupted_once(job):
                if first[0]: first[0]=False; raise KeyboardInterrupt()
                return real_active(job)
            with patch.object(bounded_windows,'_active',side_effect=interrupted_once):
                with self.assertRaises(KeyboardInterrupt) as caught: run_owned([sys.executable,'-c',command],timeout=4)
            self.assertTrue(caught.exception.cleanup_verified)
            time.sleep(2.2); self.assertFalse(marker.exists())

    def test_exception_preserves_error_and_reports_cleanup(self):
        real_active=bounded_windows._active
        first=[True]
        def failed_once(job):
            if first[0]: first[0]=False; raise OSError('injected status failure')
            return real_active(job)
        with patch.object(bounded_windows,'_active',side_effect=failed_once):
            with self.assertRaisesRegex(OSError,'injected status failure') as caught:
                run_owned([sys.executable,'-c','import time; time.sleep(5)'],timeout=4)
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertIsNone(caught.exception.cleanup_error)

    def test_exception_reports_unverified_cleanup(self):
        with patch.object(bounded_windows,'_active',side_effect=OSError('injected status failure')):
            with self.assertRaisesRegex(OSError,'injected status failure') as caught:
                run_owned([sys.executable,'-c','import time; time.sleep(5)'],timeout=4)
        self.assertFalse(caught.exception.cleanup_verified)
        self.assertIn('injected status failure',caught.exception.cleanup_error)
    def test_unrelated_process_is_not_killed(self):
        with tempfile.TemporaryDirectory(prefix='owned-transport-') as temp:
            marker=pathlib.Path(temp)/'unrelated.txt'
            command="import pathlib,time; time.sleep(1); pathlib.Path("+repr(str(marker))+").write_text('ok')"
            other=subprocess.Popen([sys.executable,'-c',command],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_owned([sys.executable,'-c','import time; time.sleep(5)'],timeout=.4)
                self.assertEqual(other.wait(timeout=4),0); self.assertTrue(marker.exists())
            finally:
                if other.poll() is None: other.kill(); other.wait(timeout=4)

    def test_expired_during_assignment_never_resumes_command(self):
        with tempfile.TemporaryDirectory(prefix='owned-transport-') as temp:
            marker=pathlib.Path(temp)/'must-not-run.txt'
            command="import pathlib; pathlib.Path("+repr(str(marker))+").write_text('executed')"
            real_assign=bounded_windows.kernel.AssignProcessToJobObject
            def delayed_assign(*args):
                success=real_assign(*args)
                time.sleep(.25)
                return success
            with patch.object(bounded_windows.kernel,'AssignProcessToJobObject',side_effect=delayed_assign):
                with self.assertRaises(subprocess.TimeoutExpired) as caught:
                    run_owned([sys.executable,'-c',command],timeout=.15)
            self.assertTrue(caught.exception.cleanup_verified)
            time.sleep(.3); self.assertFalse(marker.exists())

    def test_completion_observed_after_deadline_is_not_success(self):
        real_active=bounded_windows._active
        first=[True]
        def delayed_active(job):
            if first[0]:
                first[0]=False
                time.sleep(.5)
            return real_active(job)
        with patch.object(bounded_windows,'_active',side_effect=delayed_active):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                run_owned([sys.executable,'-c','pass'],timeout=.3)
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertIsNone(caught.exception.output)
        self.assertIsNone(caught.exception.stderr)

    def test_output_limit_rejects_truncated_success(self):
        for stream in ('stdout','stderr'):
            with self.subTest(stream=stream):
                command=f"import sys; sys.{stream}.buffer.write(b'x'*65537)"
                with self.assertRaises(bounded_windows.TransportOutputLimitError):
                    run_owned([sys.executable,'-c',command],timeout=4,max_output_bytes=65536)

    def test_output_limit_stops_running_writer(self):
        with tempfile.TemporaryDirectory(prefix='owned-transport-') as temp:
            marker=pathlib.Path(temp)/'should-not-finish.txt'
            command=("import os,sys,time,pathlib\n"
                     "for i in range(1000):\n os.write(1,b'x'*1024); time.sleep(.003)\n"
                     "pathlib.Path("+repr(str(marker))+").write_text('finished')")
            with self.assertRaises(bounded_windows.TransportOutputLimitError) as caught:
                run_owned([sys.executable,'-c',command],timeout=4,max_output_bytes=4096)
            self.assertEqual(caught.exception.stream,'stdout')
            self.assertTrue(caught.exception.cleanup_verified)
            self.assertGreater(caught.exception.observed_bytes,caught.exception.limit)
            time.sleep(.3); self.assertFalse(marker.exists())

    def test_unverified_cleanup_is_reported_when_termination_fails(self):
        with patch.object(bounded_windows.kernel,'TerminateJobObject',return_value=0), \
             patch.object(bounded_windows,'_active',return_value=1):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                run_owned([sys.executable,'-c','import time; time.sleep(5)'],timeout=.3,cleanup_wait=0)
        self.assertFalse(caught.exception.cleanup_verified)
        self.assertIn('TerminateJobObject failed',caught.exception.cleanup_error)

if __name__=='__main__': unittest.main(verbosity=2)
