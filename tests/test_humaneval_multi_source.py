"""Offline regression tests: preserve 8+7 answers and collect only the final five."""
import copy, gzip, importlib.util, json, pathlib, random, sys, tempfile, unittest
from unittest.mock import patch
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_llm_benchmarks.humaneval_subset import select, combined_score
spec = importlib.util.spec_from_file_location('multi_resume', ROOT / 'scripts/run_period2_remaining.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)

class MultiSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT / 'experiments/period-002/configs/q35-9b-he-on-continuation-20261110.json').read_text())
        rows = [json.loads(s) for s in gzip.decompress((ROOT / 'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
        cls.problems = [rows[i] for i in sorted(random.Random(42).sample(range(164), 20))]

    def test_exact_five_and_fifteen_saved(self):
        self.assertEqual([p['task_id'] for p in select(self.problems, self.plan)], ['HumanEval/139', 'HumanEval/143', 'HumanEval/151', 'HumanEval/154', 'HumanEval/163'])
        entries = [{'task_id': cid, 'passed': True} for cid in self.plan['pending_ids']]
        result = combined_score(self.problems, self.plan, entries)
        self.assertEqual((result['passed'], result['expected'], result['referenced_answers'], result['new_answers']), (18, 20, 15, 5))
        self.assertEqual(len(result['source_runs']), 2)
        with self.assertRaises(AssertionError): combined_score(self.problems, self.plan, entries[:-1])

    def test_reject_duplicate_source_missing_proof_changed_hash_or_order(self):
        bad = []
        p = copy.deepcopy(self.plan); p['references'].append(p['references'][0]); bad.append(p)
        p = copy.deepcopy(self.plan); p['references'][1]['operator_stop']['sha256'] = '0' * 64; bad.append(p)
        p = copy.deepcopy(self.plan); p['references'][1]['manifest_sha256'] = '0' * 64; bad.append(p)
        p = copy.deepcopy(self.plan); p['references'][1]['reference_raw_sha256']['HumanEval/55'] = '0' * 64; bad.append(p)
        p = copy.deepcopy(self.plan); p['references'][1].pop('operator_stop'); bad.append(p)
        p = copy.deepcopy(self.plan); p['pending_ids'].reverse(); bad.append(p)
        p = copy.deepcopy(self.plan); p['pending_ids'][0] = 'HumanEval/129'; bad.append(p)
        for plan in bad:
            with self.subTest(plan=plan), self.assertRaises((AssertionError, KeyError)):
                select(self.problems, plan)

    def test_saved_checkpoint(self):
        previous = ROOT / 'runs/period-002-core-followup-20261102'
        profile, plan, proofs = driver.checkpoint(previous, ROOT / 'experiments/period-002/configs/q35-9b-he-on-continuation-20261110.json')
        self.assertEqual(plan['new_answer_count'], 5)
        self.assertEqual(len(proofs), 4)
        self.assertEqual(profile['server_args'][profile['server_args'].index('-ngl') + 1], '24')

    def test_reject_unreconciled_attempt_and_unreferenced_raw_directory(self):
        from local_llm_benchmarks import humaneval_subset
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp); previous = root / 'runs/period-002-original'
            attempt = root / 'runs/period-002-attempt'; attempt.mkdir(parents=True)
            manifest = attempt / 'manifest.json'
            manifest.write_text(json.dumps({'status': 'failed', 'config': {'resume_from': previous.name}}))
            raw = root / 'runs/period-002-attempt-humaneval-on/raw'; raw.mkdir(parents=True)
            (raw / 'HumanEval_55.json').write_text('{}')
            dataset = root / 'datasets/humaneval/b9453e8'; dataset.mkdir(parents=True)
            (dataset / 'HumanEval.jsonl.gz').write_bytes((ROOT / 'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes())
            plan = copy.deepcopy(self.plan); plan['reconciled_parent_runs'] = {}
            with patch.object(driver, 'ROOT', root), patch.object(humaneval_subset, 'select'):
                with self.assertRaises(ValueError): driver.validate_reconciled_continuations(previous, plan)
                plan['reconciled_parent_runs'] = {attempt.name: {'manifest_sha256': driver.sha(manifest), 'source_runs': ['period-002-unrelated']}}
                with self.assertRaises(AssertionError): driver.validate_reconciled_continuations(previous, plan)
                manifest.write_text(json.dumps({'status': 'running', 'config': {'resume_from': previous.name}}))
                with self.assertRaises(ValueError): driver.validate_reconciled_continuations(previous, plan)

if __name__ == '__main__': unittest.main()
