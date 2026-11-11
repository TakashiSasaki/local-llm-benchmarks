import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reproduction_recipe', ROOT / 'scripts/reproduce_period2.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)
close_spec = importlib.util.spec_from_file_location('close_later_period', ROOT / 'scripts/close_period.py')
closure = importlib.util.module_from_spec(close_spec)
close_spec.loader.exec_module(closure)


class ReproductionTests(unittest.TestCase):
    def test_default_is_offline_and_read_only(self):
        with patch.object(recipe.urllib.request, 'urlopen', side_effect=AssertionError('network')), \
                patch.object(recipe.subprocess, 'run', side_effect=AssertionError('process')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('write')), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            recipe.main([])
        self.assertTrue(json.loads(out.getvalue())['offline'])
        self.assertFalse(json.loads(out.getvalue())['assets_verified'])

    def test_eight_pins_and_placements(self):
        self.assertEqual(len(recipe.MODELS), 8)
        for model in recipe.MODELS:
            a = recipe.parser().parse_args(['--model', model])
            p = recipe.plan(a)
            self.assertIn(p['model']['revision'], p['model']['url'])
            self.assertEqual(len(p['model']['sha256']), 64)
            self.assertEqual(p['model']['quantization'], 'Q4_K_M')
            expected = ('all', 34) if model.startswith('q36-') else ('24', 0) if '-9b-' in model else ('all', 0)
            self.assertEqual((p['placement']['gpu_layers'], p['placement']['cpu_moe_layers']), expected)
            self.assertEqual(p['server_command'][-4:], ['--load-mode', 'none', '--spec-type', 'none'])

    def test_no_historical_period(self):
        for period in ('period-001', 'period-002', '../runs', 'period-x'):
            with self.assertRaises(ValueError):
                recipe.plan(recipe.parser().parse_args(['--period', period]))

    def test_no_existing_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'runs/period-003-reproduction-example').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                recipe.plan(recipe.parser().parse_args([]), root)

    def test_no_path_traversal(self):
        for name in ('period-003-../../oops', 'period-003/child', 'period-004-wrong'):
            with self.assertRaises(ValueError):
                recipe.plan(recipe.parser().parse_args(['--id', name]))

    def test_timeout_explicit_and_grader_standard(self):
        for timeout in (7200, 14400):
            p = recipe.plan(recipe.parser().parse_args(['--timeout', str(timeout), '--suite', 'humaneval']))
            self.assertEqual(p['timeout_cohort'], str(timeout) + '-seconds')
            self.assertEqual(p['expected_answers'], 20)
            self.assertEqual(p['benchmark_command'][-2:], ['--grader-policy', 'standard-windows-v1'])
            self.assertIn(str(timeout), p['benchmark_command'])

    def test_verification_requires_external_paths(self):
        a = recipe.parser().parse_args([])
        with self.assertRaisesRegex(ValueError, 'Supply'):
            recipe.verify_assets(a, recipe.plan(a))
        a.model_dir = ROOT / 'weights'
        a.runtime_dir = Path(tempfile.gettempdir())
        a.benchmark_python = Path(tempfile.gettempdir()) / 'python.exe'
        with self.assertRaisesRegex(ValueError, 'outside'):
            recipe.verify_assets(a, recipe.plan(a))

    def test_execution_requires_operator_attestation_before_network(self):
        a = recipe.parser().parse_args(['--execute'])
        with patch.object(recipe.os, 'name', 'nt'), \
                patch.object(recipe.urllib.request, 'urlopen', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(ValueError, 'confirm-server-command'):
                recipe.execute(a, {})
        a.confirm_server_command = True
        a.suite = 'humaneval'
        with patch.object(recipe.os, 'name', 'nt'):
            with self.assertRaisesRegex(ValueError, 'generated code'):
                recipe.execute(a, {})


class PeriodClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'experiments/period-002'
        self.folder.mkdir(parents=True)
        self.registry = self.root / 'experiments/registry.json'
        self.registry.write_text(json.dumps({'active_period': 'period-002', 'periods': {
            'period-001': {'status': 'closed', 'untouched': True},
            'period-002': {'status': 'open', 'directory': 'experiments/period-002'}}}), encoding='utf-8')
        self.run = self.root / 'runs/period-002-fixture'
        self.run.mkdir(parents=True)
        self.manifest = {'schema_version': 1, 'run_id': self.run.name, 'period': 'period-002',
                         'status': 'complete', 'kind': 'measurement', 'benchmark': 'bfcl',
                         'experiment_type': 'benchmark', 'config': {}}
        self.write_manifest()
        (self.run / 'summary.json').write_text('{}', encoding='utf-8')
        (self.run / 'raw').mkdir()
        (self.run / 'raw/answer.json').write_text('{"answer": 1}', encoding='utf-8')
        (self.folder / 'report.md').write_text('Final fixture report', encoding='utf-8')
        (self.folder / 'models').mkdir()
        (self.folder / 'models/pin.json').write_text('{"sha256": "fixture"}', encoding='utf-8')

    def write_manifest(self):
        (self.run / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_dry_run_does_not_write(self):
        before = self.registry.read_bytes()
        self.assertTrue(closure.close('period-002', root=self.root)['dry_run'])
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertFalse((self.folder / 'closure.json').exists())

    def test_close_verify_and_refuse_repeat(self):
        old_raw = (self.run / 'raw/answer.json').read_bytes()
        old_manifest = (self.run / 'manifest.json').read_bytes()
        closure.close('period-002', execute=True, root=self.root)
        self.assertTrue(closure.verify('period-002', root=self.root)['verified'])
        data = json.loads(self.registry.read_text(encoding='utf-8'))
        self.assertIsNone(data['active_period'])
        self.assertEqual(data['periods']['period-001'], {'status': 'closed', 'untouched': True})
        seal = json.loads((self.folder / 'closure.json').read_text(encoding='utf-8'))
        self.assertIn('experiments/period-002/models/pin.json', seal['files'])
        self.assertIn('experiments/period-002/report.md', seal['files'])
        self.assertEqual((self.run / 'raw/answer.json').read_bytes(), old_raw)
        self.assertEqual((self.run / 'manifest.json').read_bytes(), old_manifest)
        with self.assertRaises(ValueError):
            closure.close('period-002', execute=True, root=self.root)

    def test_nonterminal_and_first_period_rejected(self):
        for status in ('planned', 'running'):
            self.manifest['status'] = status
            self.write_manifest()
            with self.assertRaisesRegex(ValueError, 'Nonterminal'):
                closure.close('period-002', execute=True, root=self.root)
        with self.assertRaises(ValueError):
            closure.close('period-001', execute=True, root=self.root)

    def test_changed_evidence_detected(self):
        closure.close('period-002', execute=True, root=self.root)
        (self.run / 'raw/answer.json').write_text('{"answer": 2}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'evidence'):
            closure.verify('period-002', root=self.root)

    def test_failed_run_can_close_without_becoming_success(self):
        self.manifest['status'] = 'failed'
        self.write_manifest()
        closure.close('period-002', execute=True, root=self.root)
        self.assertEqual(json.loads((self.run / 'manifest.json').read_text())['status'], 'failed')
        self.assertTrue(closure.verify('period-002', root=self.root)['verified'])


if __name__ == '__main__':
    unittest.main()
