import importlib.util
import pathlib
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_llm_benchmarks.study import create_run,save,load,validate_run,assert_run_writable
from local_llm_benchmarks.periods import membership
spec=importlib.util.spec_from_file_location('start_period',ROOT/'scripts/start_period.py')
starter=importlib.util.module_from_spec(spec);spec.loader.exec_module(starter)


class Periods(unittest.TestCase):
    def fixture(self,root):
        old=create_run('Old evidence','test',run_id='old-id',root=root)
        save(root/'experiments/period-001/runs.json',{'run_ids':['old-id']})
        save(root/'experiments/registry.json',{'active_period':None,'periods':{'period-001':{'status':'closed','run_index':'experiments/period-001/runs.json'}}})
        return old

    def test_closed_period_blocks_creation_before_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);old=self.fixture(root)
            for requested in [None,'period-001','period-999']:
                with self.assertRaises(ValueError):create_run('New','test',run_id='new-id',root=root,period=requested)
            self.assertEqual([p.name for p in (root/'runs').iterdir()],['old-id'])
            self.assertEqual(membership(root,validate_run(old)),'period-001')
            m=load(old/'manifest.json');m['status']='failed';save(old/'manifest.json',m)
            with self.assertRaises(ValueError):assert_run_writable(old)

    def test_new_period_gets_distinct_run_prefix_and_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.fixture(root)
            starter.start('period-002','Next settings',root)
            with self.assertRaises(ValueError):create_run('New','test',run_id='old-looking-id',root=root)
            p=create_run('New','test',root=root)
            self.assertTrue(p.name.startswith('period-002-'))
            self.assertEqual(load(p/'manifest.json')['period'],'period-002')
            self.assertEqual(membership(root,validate_run(p)),'period-002')
            assert_run_writable(p)
            with self.assertRaises(ValueError):starter.start('period-001','Reuse',root)
            with self.assertRaises(ValueError):starter.start('../outside','Bad',root)

    def test_unassigned_later_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);self.fixture(root)
            with self.assertRaises(ValueError):membership(root,{'run_id':'unassigned'})
