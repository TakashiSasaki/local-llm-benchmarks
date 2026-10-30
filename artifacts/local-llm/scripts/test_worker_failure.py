"""Verify failures after shell launch never report a false completion."""
import json, pathlib, subprocess, tempfile, time, unittest
from unittest.mock import patch
import executor_worker as worker
from server import ROOT

class WorkerFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='worker-failure-'); self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name); self.job='a'*32; self.directory=self.root/self.job; self.directory.mkdir()
        config=json.loads((ROOT/'executor-config.json').read_text(encoding='utf-8-sig'))
        self.marker=self.root/'late-marker.txt'
        request={'job_id':self.job,'started_utc':worker.utc(),'host':'windows-local','cwd':str(self.root),
                 'powershell':config['powershell'],'script':"Start-Sleep -Seconds 2\n[IO.File]::WriteAllText('"+str(self.marker)+"','late')"}
        worker.put(self.directory/'request.json',request)
    def test_worker_error_is_unknown_not_completed(self):
        worker.record_worker_exception(self.directory,OSError('injected'))
        result=worker.poll(self.root,self.job)
        self.assertEqual(result['status'],'unknown'); self.assertIsNone(result['exit_code'])
        self.assertTrue(result['may_be_running']); self.assertEqual(result['executor_error'],'injected')
    def test_post_spawn_metadata_failure_stops_actual_child(self):
        original_put=worker.put; original_popen=subprocess.Popen; children=[]
        def fail_process_metadata(path,data):
            if path.name=='process.json': raise OSError('injected process metadata failure')
            return original_put(path,data)
        def capture_child(*args,**kwargs):
            p=original_popen(*args,**kwargs)
            if pathlib.Path(args[0][0]).name.lower()=='pwsh.exe': children.append(p)
            return p
        with patch.object(worker,'put',side_effect=fail_process_metadata),patch.object(worker.subprocess,'Popen',side_effect=capture_child):
            with self.assertRaisesRegex(OSError,'injected process metadata failure'): worker.work(self.directory)
        self.assertEqual(len(children),1); self.assertIsNotNone(children[0].poll())
        time.sleep(2.2)
        self.assertFalse(self.marker.exists())
    def test_unknown_status_still_attempts_to_stop_managed_child(self):
        request=worker.read(self.directory/'request.json')
        # Start the real worker in a separate fresh job directory.
        other=self.root/('b'*32); request.update(job_id='b'*32,state_root=str(self.root),workspace_root=str(self.root),timeout=0)
        result=worker.launch(request); deadline=time.monotonic()+8
        while not (other/'process.json').exists() and time.monotonic()<deadline: time.sleep(.05)
        self.assertTrue((other/'process.json').exists())
        worker.record_worker_exception(other,OSError('simulated unknown state'))
        result=worker.stop(self.root,'b'*32)
        self.assertIn(result['status'],['unknown','completed'])
        self.assertFalse(result['status']=='unknown' and result.get('stop_verified') is True)
        time.sleep(2.2)
        self.assertFalse(self.marker.exists())

if __name__=='__main__': unittest.main(verbosity=2)
