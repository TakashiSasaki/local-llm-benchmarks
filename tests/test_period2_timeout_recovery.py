"""Offline recovery admission tests: never start a model, server or download."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('timeout_recovery', ROOT / 'scripts/run_period2_timeout_recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.plan = recovery.load(ROOT / recovery.PLAN)

    def test_exact_647_pending_and_953_saved(self):
        queue = recovery.build_queue(self.plan)
        self.assertEqual(sum(r['count'] for r in queue), 647)
        self.assertEqual(sum(len(r['ids']) for r in self.plan['references']), 953)
        self.assertEqual([(r['suite'], r['thinking'], r['count']) for r in queue[:3]],
                         [('bfcl', 'on', 7), ('humaneval', 'off', 20), ('humaneval', 'on', 20)])
        self.assertEqual(queue[0]['ids'], ['irrelevance_139', 'irrelevance_151', 'irrelevance_163',
                                         'irrelevance_173', 'irrelevance_188', 'irrelevance_189', 'irrelevance_228'])
        self.assertEqual({r['model'] for r in queue}, set(recovery.KEYS))

    def test_duplicate_canonical_reference_refused(self):
        self.plan['references'].append(copy.deepcopy(self.plan['references'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate canonical'):
            recovery.build_queue(self.plan)

    def test_missing_reference_refused(self):
        self.plan['references'][0]['ids'].pop()
        with self.assertRaisesRegex(ValueError, '953'):
            recovery.build_queue(self.plan)

    def test_timeout_only_profile_override(self):
        source = recovery.load(ROOT / 'runs' / recovery.PREVIOUS / 'configs/cohort-b-matched-profile.json')
        before = copy.deepcopy(source)
        changed = recovery.timeout_profile(source)
        self.assertEqual(source, before)
        self.assertEqual(changed['server_args'], source['server_args'])
        self.assertEqual(changed['benchmark_extra_args'], ['--api-timeout-seconds', '14400'])
        self.assertEqual((changed['max_tokens'], changed['context_tokens']), (64000, 65536))

    def test_unexpected_profile_override_refused(self):
        source = recovery.load(ROOT / 'runs' / recovery.PREVIOUS / 'configs/cohort-b-matched-profile.json')
        source['benchmark_extra_args'] = ['--temperature', '1']
        with self.assertRaisesRegex(ValueError, 'Unexpected benchmark'):
            recovery.timeout_profile(source)

    def test_pilot_omits_live_gpu_ceiling_but_main_retains_it(self):
        source = recovery.load(ROOT / 'runs' / recovery.PREVIOUS / 'configs/cohort-b-matched-profile.json')
        main = recovery.timeout_profile(source)
        pilot = recovery.timeout_profile(main, pilot=True)
        self.assertNotIn('maximum_gpu_used_mib', pilot)
        self.assertEqual(main['maximum_gpu_used_mib'], 7676)
        self.assertEqual(recovery.timeout_profile(pilot)['maximum_gpu_used_mib'], 7676)
        self.assertEqual(pilot['benchmark_extra_args'], ['--api-timeout-seconds', '14400'])
        self.assertEqual(pilot['minimum_available_ram_bytes'], 3 * 1024**3)

    def test_real_checkpoint_read_only(self):
        # Test immutable evidence independently of a later legitimate live run.
        # Attempt refusal has separate isolated tests below.
        with patch.object(recovery, 'validate_attempts'), patch.object(recovery.subprocess, 'Popen') as child:
            queue = recovery.validate_checkpoint(self.plan)
        self.assertEqual(sum(r['count'] for r in queue), 647)
        child.assert_not_called()

    def test_tampered_evidence_no_child_or_new_run(self):
        key = next(iter(self.plan['files']))
        self.plan['files'][key] = '0' * 64
        args = SimpleNamespace(plan=ROOT / recovery.PLAN)
        actual_load = recovery.load
        def read(path):
            return self.plan if path == args.plan else actual_load(path)
        with patch.object(recovery, 'validate_attempts'), patch.object(recovery, 'load', side_effect=read), patch.object(recovery, 'create_run') as create, \
             patch.object(recovery.subprocess, 'Popen') as child:
            with self.assertRaisesRegex(ValueError, 'Pinned evidence changed'):
                recovery.run(args)
        child.assert_not_called()
        create.assert_not_called()

    def test_hold_no_child_or_new_run(self):
        args = SimpleNamespace(plan=ROOT / recovery.PLAN)
        with patch.object(recovery, 'validate_attempts'), patch.object(recovery, 'require', side_effect=recovery.ExecutionWindowDeferred('held')), \
             patch.object(recovery, 'create_run') as create, patch.object(recovery.subprocess, 'Popen') as child:
            with self.assertRaises(recovery.ExecutionWindowDeferred):
                recovery.run(args)
        create.assert_not_called()
        child.assert_not_called()

    def test_running_parent_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / 'runs/period-002-timeout-recovery-other'
            run.mkdir(parents=True)
            (run / 'manifest.json').write_text(json.dumps(dict(status='running', benchmark='staged-capability-study')))
            with patch.object(recovery, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'still running'):
                    recovery.validate_attempts(self.plan)

    def test_unknown_saved_attempt_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / 'runs/period-002-timeout-recovery-other'
            (run / 'raw').mkdir(parents=True)
            (run / 'manifest.json').write_text(json.dumps(dict(status='failed', benchmark='bfcl')))
            (run / 'raw/irrelevance_139.json').write_text('{}')
            with patch.object(recovery, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Unreconciled'):
                    recovery.validate_attempts(self.plan)

    def test_untagged_terminal_staged_parent_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / 'runs/period-002-unrecognized-parent'
            run.mkdir(parents=True)
            (run / 'manifest.json').write_text(json.dumps(dict(status='failed', benchmark='staged-capability-study')))
            with patch.object(recovery, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Unreconciled staged parent'):
                    recovery.validate_attempts(self.plan)


if __name__ == '__main__':
    unittest.main()
