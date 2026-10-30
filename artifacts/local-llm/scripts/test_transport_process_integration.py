"""Local child tests for error/interrupt diagnostics; no SSH connection."""
import signal, sys, unittest
from unittest.mock import patch
import bounded_windows


class ExceptionDiagnosticsTests(unittest.TestCase):
    def test_real_child_error_has_pid_and_cleanup_result(self):
        real_active=bounded_windows._active
        first=[True]
        def fail_once(job):
            if first[0]:
                first[0]=False
                raise OSError('injected real-child monitor error')
            return real_active(job)
        with patch.object(bounded_windows,'_active',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'real-child monitor') as caught:
                bounded_windows.run_owned([sys.executable,'-c','import time; time.sleep(5)'],timeout=4)
        self.assertIsInstance(caught.exception.pid,int)
        self.assertGreater(caught.exception.pid,0)
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertIsNone(caught.exception.cleanup_error)

    def test_signal_interrupt_has_pid_and_cleanup_result(self):
        real_active=bounded_windows._active
        previous=signal.signal(signal.SIGINT,signal.default_int_handler)
        self.addCleanup(signal.signal,signal.SIGINT,previous)
        first=[True]
        def interrupt_once(job):
            if first[0]:
                first[0]=False
                signal.raise_signal(signal.SIGINT)
            return real_active(job)
        with patch.object(bounded_windows,'_active',side_effect=interrupt_once):
            with self.assertRaises(KeyboardInterrupt) as caught:
                bounded_windows.run_owned([sys.executable,'-c','import time; time.sleep(5)'],timeout=4)
        self.assertIsInstance(caught.exception.pid,int)
        self.assertGreater(caught.exception.pid,0)
        self.assertTrue(caught.exception.cleanup_verified)
        self.assertIsNone(caught.exception.cleanup_error)


if __name__=='__main__': unittest.main(verbosity=2)
