"""Output budgets change without new inference or executing generated code."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('he_budget_driver', ROOT / 'benchmarks/humaneval.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class HumanEvalBudgets(unittest.TestCase):
    def collect(self, context=None, max_output=None):
        requests = []
        actual_context = context if context is not None else 65536
        def serve(req, timeout=None):
            route = req.full_url.rsplit('/', 1)[-1]
            payload = json.loads(req.data) if req.data else None
            if route == 'props':
                value = {'model_alias': 'fixture', 'total_slots': 1,
                         'default_generation_settings': {'n_ctx': actual_context},
                         'build_info': 'fixture-no-inference'}
            elif route == 'apply-template':
                value = {'prompt': 'fixture'}
            elif route == 'tokenize':
                value = {'tokens': [0] * 200}
            else:
                requests.append(payload)
                value = {'choices': [{'message': {'content': ''}, 'finish_reason': 'stop'}], 'usage': {}}
            return io.BytesIO(json.dumps(value).encode())
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'run'
            path.mkdir()
            driver.save(path / 'manifest.json', {'status': 'planned', 'config': {}})
            args = argparse.Namespace(run='fixture', model='fixture', thinking='off',
                                      endpoint='http://127.0.0.1:8089')
            if context is not None:
                args.context = context
            if max_output is not None:
                args.max_output = max_output
            fake_grade = lambda code, problem: {'passed': True, 'status': 'fixture'}
            with patch.object(driver, 'resolve_run', return_value=path), \
                    patch.object(driver, 'assert_run_writable'), \
                    patch.object(driver, 'snapshot_sources'), \
                    patch.object(driver, 'require'), \
                    patch.object(driver, 'grader', return_value=(fake_grade, lambda *a: '')), \
                    patch.object(driver.urllib.request, 'urlopen', side_effect=serve), \
                    contextlib.redirect_stdout(io.StringIO()):
                summary = driver.run(args)
            execution = driver.load(path / 'manifest.json')['execution']
        return requests, execution, summary

    def test_legacy_defaults_unchanged(self):
        requests, execution, summary = self.collect()
        self.assertEqual(len(requests), 20)
        self.assertEqual({r['max_tokens'] for r in requests}, {64000})
        self.assertEqual((execution['context'], execution['max_output']), (65536, 64000))
        self.assertEqual(summary['attempted'], 20)

    def test_phase3_output_cap(self):
        requests, execution, _ = self.collect(65536, 16384)
        self.assertEqual({r['max_tokens'] for r in requests}, {16384})
        self.assertEqual(execution['max_output'], 16384)

    def test_context_clips_output_and_reserves_margin(self):
        requests, _, _ = self.collect(1024, 16384)
        self.assertEqual({r['max_tokens'] for r in requests}, {792})

    def test_no_output_space_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No output space'):
            self.collect(100, 16384)


if __name__ == '__main__':
    unittest.main()
