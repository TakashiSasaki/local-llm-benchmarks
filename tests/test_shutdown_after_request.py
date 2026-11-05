import importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shutdown_watch',ROOT/'scripts/shutdown_after_request.py');watch=importlib.util.module_from_spec(spec);spec.loader.exec_module(watch)

class EvidenceGate(unittest.TestCase):
    def test_consumed_request_cannot_rearm_or_overwrite_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);state=root/'state.json';state.write_text('{"status":"shutdown_requested","shutdown_started":true}')
            config=root/'config.json';config.write_text(json.dumps({'repository':str(root),'state_file':str(state)}))
            original=state.read_bytes()
            with patch.object(watch.ctypes,'WinDLL') as kernel,patch.object(watch.subprocess,'run') as shutdown:
                with self.assertRaisesRegex(RuntimeError,'Consumed shutdown request'):watch.watch(config)
                kernel.assert_not_called();shutdown.assert_not_called()
            self.assertEqual(state.read_bytes(),original)

    def test_no_shutdown_before_terminal_cleanup_and_saved_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);cfg={'condition':'condition','model_run':'model','orchestrator':'parent','question':'HumanEval/35','raw_filename':'HumanEval_35.json','maximum_saved_cases':8}
            for name in ['condition','model','parent']:
                path=root/'runs'/name;path.mkdir(parents=True);(path/'manifest.json').write_text('{"status":"running"}')
            self.assertFalse(watch.evidence_ready(root,cfg)[0])
            for name in ['condition','model','parent']:(root/'runs'/name/'manifest.json').write_text('{"status":"failed"}')
            path=root/'runs/model/configs';path.mkdir();(path/'cleanup.json').write_text('{"server_stopped":false}')
            self.assertFalse(watch.evidence_ready(root,cfg)[0]);(path/'cleanup.json').write_text('{"server_stopped":true}')
            self.assertTrue(watch.evidence_ready(root,cfg)[0]) # Recorded timeout/failure can finish the task.
            cases=root/'runs/condition/summaries';cases.mkdir();(cases/'cases.json').write_text(json.dumps([{'task_id':'HumanEval/35'}]))
            with self.assertRaises(RuntimeError):watch.evidence_ready(root,cfg)
            raw=root/'runs/condition/raw';raw.mkdir();(raw/'HumanEval_35.json').write_text('{}')
            self.assertTrue(watch.evidence_ready(root,cfg)[0])
            (cases/'cases.json').write_text(json.dumps([{'task_id':'later'}]*9))
            with self.assertRaises(RuntimeError):watch.evidence_ready(root,cfg)

if __name__=='__main__':unittest.main()
