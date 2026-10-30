"""Run local OpenSSH informational commands only; no network or host is used."""
import json
import pathlib
import unittest

from bounded_windows import run_owned

ROOT = pathlib.Path(r'C:\LocalLLM')


class WindowsOpenSSHLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / 'executor-config.json').read_text(encoding='utf-8-sig'))

    def test_ssh_version_stderr_and_success(self):
        result = run_owned([self.config['ssh'], '-V'], timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'OpenSSH_', result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_scp_usage_stderr_and_error(self):
        result = run_owned([self.config['scp'], '-?'], timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'usage: scp', result.stderr.lower())
        self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main(verbosity=2)
