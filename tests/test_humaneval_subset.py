"""Continuation must preserve references, reject overlap, and respect the hold."""
import argparse,copy,gzip,importlib.util,json,pathlib,random,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.humaneval_subset import select,combined_score
from local_llm_benchmarks.execution_window import ExecutionWindowDeferred

class Continuation(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((ROOT/'experiments/period-002/configs/q35-9b-he-on-continuation.json').read_text())
        rows=[json.loads(s) for s in gzip.decompress((ROOT/'datasets/humaneval/b9453e8/HumanEval.jsonl.gz').read_bytes()).decode().splitlines()]
        self.problems=[rows[i] for i in sorted(random.Random(42).sample(range(164),20))]

    def test_exact_pending_order_and_referenced_eight(self):
        pending=select(self.problems,self.plan)
        self.assertEqual([p['task_id'] for p in pending],self.plan['pending_ids'])
        self.assertEqual(len(pending),12)
        self.assertFalse(set(self.plan['reference_saved_ids']) & set(self.plan['pending_ids']))

    def test_reject_overlap_reorder_missing_or_changed_reference(self):
        bad=[]
        plan=copy.deepcopy(self.plan);plan['pending_ids'][0]=plan['reference_saved_ids'][0];bad.append(plan)
        plan=copy.deepcopy(self.plan);plan['pending_ids'].reverse();bad.append(plan)
        plan=copy.deepcopy(self.plan);plan['pending_ids'].pop();bad.append(plan)
        plan=copy.deepcopy(self.plan);plan['reference_raw_sha256'][plan['reference_saved_ids'][0]]='0'*64;bad.append(plan)
        for plan in bad:
            with self.subTest(plan=plan),self.assertRaises(AssertionError):select(self.problems,plan)

    def test_combined_score_counts_originals_once_and_rejects_partial(self):
        # Synthetic passed values, used only in memory to check aggregation.
        entries=[{'task_id':cid,'passed':True} for cid in self.plan['pending_ids']]
        score=combined_score(self.problems,self.plan,entries)
        self.assertEqual((score['passed'],score['expected'],score['referenced_answers'],score['new_answers']),(19,20,8,12))
        with self.assertRaises(AssertionError):combined_score(self.problems,self.plan,entries[:-1])

    def test_hold_prevents_even_endpoint_contact(self):
        spec=importlib.util.spec_from_file_location('he_subset_driver',ROOT/'benchmarks/humaneval.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        with tempfile.TemporaryDirectory() as temp:
            run=pathlib.Path(temp);(run/'manifest.json').write_text('{"status":"planned","period":"period-002"}')
            args=argparse.Namespace(run='unused',model='unused',thinking='on',endpoint='http://127.0.0.1:8089',grader_policy='standard-windows-v1')
            with patch.object(driver,'resolve_run',return_value=run),patch.object(driver,'assert_run_writable'),patch.object(driver,'snapshot_sources'),patch.object(driver,'require',side_effect=ExecutionWindowDeferred('hold')),patch.object(driver.urllib.request,'urlopen') as api:
                with self.assertRaises(ExecutionWindowDeferred):driver.run(args)
                api.assert_not_called()

if __name__=='__main__':unittest.main()
