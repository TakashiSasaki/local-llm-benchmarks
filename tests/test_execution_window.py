import datetime,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from local_llm_benchmarks.execution_window import decide

class Window(unittest.TestCase):
    policy={'finish_by':'2026-11-03T04:00:00+09:00','save_reserve_seconds':1800}
    def test_finish_not_start_deadline(self):
        # A 4h task at midnight cannot finish with the reserve, despite starting before 04:00.
        self.assertFalse(decide(self.policy,'model',4*3600,datetime.datetime.fromisoformat('2026-11-03T00:00:00+09:00'))['allowed'])
        self.assertTrue(decide(self.policy,'model',4*3600,datetime.datetime.fromisoformat('2026-11-02T23:00:00+09:00'))['allowed'])
    def test_exact_margin_timezone_and_expiry(self):
        boundary=datetime.datetime.fromisoformat('2026-11-02T18:30:00+00:00')
        self.assertTrue(decide(self.policy,'short',0,boundary)['allowed'])
        self.assertFalse(decide(self.policy,'short',1,boundary)['allowed'])
        self.assertFalse(decide(self.policy,'short',0,datetime.datetime.fromisoformat('2026-11-03T04:00:00+09:00'))['allowed'])
    def test_unknown_duration_and_naive_time(self):
        self.assertFalse(decide(self.policy,'unknown',None,datetime.datetime.fromisoformat('2026-11-02T12:00:00+09:00'))['allowed'])
        with self.assertRaises(ValueError):decide(self.policy,'short',1,datetime.datetime(2026,11,2))
    def test_user_hold_blocks_even_short_work_inside_the_time_window(self):
        policy=dict(self.policy,stop_after_current_task=True)
        result=decide(policy,'next question',1,datetime.datetime.fromisoformat('2026-11-02T12:00:00+09:00'))
        self.assertFalse(result['allowed']);self.assertTrue(result['user_hold_active'])

if __name__=='__main__':unittest.main()
