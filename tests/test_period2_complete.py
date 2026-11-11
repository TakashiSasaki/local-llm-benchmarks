import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('period2_complete', pathlib.Path(__file__).resolve().parents[1] / 'tools/verify_period2_complete.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class CompletedAuditTests(unittest.TestCase):
    def response(self, finish='length', content='', tools=None):
        return {'choices': [{'finish_reason': finish, 'message': {'content': content, 'tool_calls': tools}}]}

    def test_capped_empty_pass_is_only_secondary_failure(self):
        self.assertFalse(audit.capped_no_final_aware_pass(True, self.response()))
        self.assertTrue(audit.capped_no_final(self.response(content='  ')))

    def test_legitimate_no_call_reply_is_preserved(self):
        self.assertTrue(audit.capped_no_final_aware_pass(True, self.response('stop', 'Cannot use those tools.')))
        self.assertTrue(audit.capped_no_final_aware_pass(True, self.response('stop')))

    def test_final_tool_calls_and_content_are_not_empty(self):
        self.assertFalse(audit.empty_final(self.response(tools=[{'function': {'name': 'x'}}])))
        self.assertTrue(audit.capped_no_final_aware_pass(True, self.response(content='Answer')))
        self.assertFalse(audit.capped_no_final_aware_pass(False, self.response(content='Answer')))

    def test_duplicate_identity_rejected(self):
        rows = {}
        identity = ('model', 'bfcl', 'on', 'irrelevance_139')
        audit.insert_unique(rows, identity, {'passed': True})
        with self.assertRaisesRegex(ValueError, 'Duplicate canonical'):
            audit.insert_unique(rows, identity, {'passed': False})


if __name__ == '__main__':
    unittest.main()
