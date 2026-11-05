"""Check real Windows execution, rather than mirroring the implementation."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.humaneval_standard_windows import grade,provenance

@unittest.skipUnless(sys.platform=='win32','Windows JobObject adapter')
class StandardGrader(unittest.TestCase):
    def test_normal_builtins_and_stdlib_do_not_create_false_failures(self):
        problem={'task_id':'control','prompt':'','entry_point':'f','test':'def check(candidate):\n    assert candidate([2,3,4]) == 24'}
        code='import operator\nfrom functools import reduce\ndef f(a):\n    assert type(a) is list\n    return reduce(operator.mul,a,1)'
        self.assertTrue(grade(code,problem)['passed'])
        self.assertFalse(grade('def f(a): return 0',problem)['passed'])
        self.assertEqual(provenance()['upstream']['revision'],'b9453e8f1865df0a0057a1383767caa400acfbcf')

if __name__=='__main__':unittest.main()
