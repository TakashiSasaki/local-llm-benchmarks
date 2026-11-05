import argparse,importlib.util,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks import execution_window
spec=importlib.util.spec_from_file_location('remaining_core',ROOT/'scripts/run_period2_remaining.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)

class FollowupDeadline(unittest.TestCase):
    def test_expired_window_starts_no_child_and_preserves_deferred_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);parent=root/'runs/period-002-followup-test'
            for folder in ['configs','logs','summaries']: (parent/folder).mkdir(parents=True,exist_ok=True)
            (parent/'manifest.json').write_text(json.dumps({'status':'planned','period':'period-002'}))
            stage=root/'runs/period-002-a';stage.mkdir();(stage/'manifest.json').write_text('{"status":"complete"}')
            config=root/'experiments/period-002/configs';config.mkdir(parents=True)
            (config/'execution-window.json').write_text(json.dumps({'enabled':True,'finish_by':'2000-01-01T04:00:00+09:00','save_reserve_seconds':1800,'conservative_estimates_seconds':{}}))
            (config/'q35-4b-base-preflight.json').write_text('{"server_args":[]}')
            models=root/'experiments/period-002/models';models.mkdir();(models/'q35-9b-base.json').write_text('{"bytes":100}')
            args=argparse.Namespace(id=parent.name,stage_a=stage.name,validation='validation',benchmark_python=pathlib.Path(sys.executable))
            fake=argparse.Namespace(ready_policy=lambda *a:{'test_only':True})
            with patch.object(driver,'ROOT',root),patch.object(execution_window,'ROOT',root),patch.object(driver,'create_run',return_value=parent),patch.object(driver,'snapshot_sources'),patch.object(driver,'validate_stage_a',return_value={'test_only':True}),patch.object(driver,'script_module',return_value=fake),patch.object(driver.subprocess,'Popen') as spawn:
                with self.assertRaises(execution_window.ExecutionWindowDeferred):driver.run(args)
                spawn.assert_not_called()
            manifest=json.loads((parent/'manifest.json').read_text());summary=json.loads((parent/'summary.json').read_text())
            self.assertEqual(manifest['stop_reason'],'execution_window_deferred');self.assertFalse(manifest['model_failure'])
            self.assertEqual(summary['outcome'],'deferred');self.assertEqual(summary['completed_model_answers'],0)
            self.assertEqual(len(summary['pending_models']),6)

if __name__=='__main__':unittest.main()
