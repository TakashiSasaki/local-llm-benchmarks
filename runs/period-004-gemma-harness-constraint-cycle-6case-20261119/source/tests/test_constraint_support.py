"""Offline tests for conservative question-condition warnings."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integrations/page_harness'))
from constraint_support import inspect_constraints


class ConstraintWarnings(unittest.TestCase):
    def test_saved_lake_failure_is_flagged_without_judging_correctness(self):
        run = ROOT / 'runs/period-004-gemma-harness-improvement-cycle-3case-20261118/raw/web_search_4/result.json'
        data = json.loads(run.read_text(encoding='utf-8'))
        question = "Authors' birthplaces can influence storytelling and natural landmarks. What is the largest lake in the author's birth state?"
        result = inspect_constraints(question, data['answer'])
        self.assertEqual([x['kind'] for x in result], ['possible_natural_only_narrowing'])
        hit = result[0]
        self.assertEqual(data['answer'][hit['candidate_offset']:hit['candidate_end']], hit['candidate_phrase'])
        self.assertIn('does not establish', hit['notice'])

    def test_saved_animated_vs_live_action_failure_is_flagged(self):
        run = ROOT / 'runs/period-004-gemma-harness-improvement-cycle-3case-20261118/raw/web_search_34/result.json'
        data = json.loads(run.read_text(encoding='utf-8'))
        result = inspect_constraints('Where did the animated movie first premiere?', data['answer'])
        self.assertEqual([x['kind'] for x in result], ['possible_live_action_for_animation'])
        self.assertIn('may discuss both', result[0]['notice'])

    def test_compatible_and_explicit_comparison_questions_are_not_flagged(self):
        self.assertEqual(inspect_constraints('What is the largest natural lake?', 'The largest natural lake is X.'), [])
        self.assertEqual(inspect_constraints('Compare the animated film and live-action version.', 'The live-action version premiered in X.'), [])
        self.assertEqual(inspect_constraints('What is the largest lake?', 'Lake X is the largest reservoir.'), [])
        self.assertEqual(inspect_constraints('Who won in 2024?', 'An animated film was discussed.'), [])

    def test_japanese_and_input_type(self):
        self.assertEqual(inspect_constraints('最大の湖は？', '最大の自然湖はXです。')[0]['kind'], 'possible_natural_only_narrowing')
        self.assertEqual(inspect_constraints('アニメ映画は？', '実写の公開日は2026年。')[0]['kind'], 'possible_live_action_for_animation')
        with self.assertRaises(TypeError):
            inspect_constraints(None, 'text')


if __name__ == '__main__':
    unittest.main()
