"""V2 学习模块离线逻辑检查，不读取密钥。"""
import json
import unittest

from learning_core import (QUESTIONS, QUESTION_MAP, SOURCE_MAP, TOPICS, export_progress,
                           import_progress, new_progress, record_answer, summary,
                           tutor_prompt, validate_progress, wrong_ids)
from rc_core import calculate_rc_cutoff
from rc_reference import outside_scope
from dc_reference import outside_scope as dc_outside_scope
from logic_reference import outside_scope as logic_outside_scope


class LearningChecks(unittest.TestCase):
    def test_01_question_bank_integrity(self):
        self.assertEqual(len(QUESTIONS), 39)
        self.assertEqual(len(QUESTION_MAP), 39)
        for item in QUESTIONS:
            self.assertIn(item["topic"], TOPICS)
            self.assertEqual(len(item["options"]), 4)
            self.assertEqual(len(set(item["options"])), 4)
            self.assertIn(item["correct"], range(4))
            self.assertTrue(item["explanation"])
            self.assertTrue(set(item["sources"]) <= set(SOURCE_MAP))
        for topic in TOPICS:
            self.assertEqual(sum(item["topic"] == topic for item in QUESTIONS), 3)

    def test_02_numeric_example_matches_tool(self):
        self.assertAlmostEqual(calculate_rc_cutoff(1000, 100)["cutoff_hz"], 1591.55, places=2)
        self.assertAlmostEqual(calculate_rc_cutoff(2000, 100)["cutoff_hz"], 795.77, places=2)
        self.assertIn("1591.55", QUESTION_MAP["RC03"]["options"][QUESTION_MAP["RC03"]["correct"]])

    def test_03_wrong_then_correct_preserves_first_attempt(self):
        original = new_progress()
        wrong, ok = record_answer(original, "RC01", 0)
        self.assertFalse(ok)
        self.assertEqual(wrong_ids(wrong), ["RC01"])
        right, ok = record_answer(wrong, "RC01", 1)
        self.assertTrue(ok)
        self.assertEqual(wrong_ids(right), [])
        self.assertEqual(summary(right), {"answered": 1, "first_correct": 0, "latest_correct": 1, "wrong": 0, "attempts": 2})
        self.assertEqual(original, new_progress())
        self.assertEqual(wrong["answers"]["RC01"], [0])

    def test_04_progress_roundtrip(self):
        progress, _ = record_answer(new_progress(), "RC12", 3)
        self.assertEqual(import_progress(export_progress(progress)), progress)
        self.assertEqual(import_progress(b"\xef\xbb\xbf" + export_progress(progress)), progress)

    def test_05_malformed_progress_rejected(self):
        invalid = [[], {}, {"version": True, "answers": {}}, {"version": 2, "answers": {}},
                   {"version": 1, "answers": {"RC99": [0]}},
                   {"version": 1, "answers": {"RC01": []}},
                   {"version": 1, "answers": {"RC01": [True]}},
                   {"version": 1, "answers": {"RC01": [4]}},
                   {"version": 1, "answers": {}, "extra": "ignored?"}]
        for data in invalid:
            with self.assertRaises(ValueError):
                import_progress(json.dumps(data).encode())
        for raw in [b"invalid", b"\xff", b"x" * 100_001, b"[" * 2000 + b"]" * 2000]:
            with self.assertRaises(ValueError):
                import_progress(raw)

    def test_06_invalid_answer_rejected(self):
        for qid, option in [("RC99", 0), ("RC01", None), ("RC01", True), ("RC01", -1), ("RC01", 4)]:
            with self.assertRaises(ValueError):
                record_answer(new_progress(), qid, option)

    def test_07_attempts_limit(self):
        progress = {"version": 1, "answers": {"RC01": [0] * 100}}
        with self.assertRaises(ValueError):
            record_answer(progress, "RC01", 1)
        self.assertEqual(summary(validate_progress(progress))["attempts"], 100)

    def test_08_tutor_receives_question_and_actual_choice(self):
        prompt = tutor_prompt("RC01", 0)
        self.assertIn(QUESTION_MAP["RC01"]["stem"], prompt)
        self.assertIn("我的选择：100 F", prompt)
        self.assertIn("题库标准答案：1×10⁻⁷ F", prompt)
        self.assertIn("我的选择：尚未选择", tutor_prompt("RC01"))

    def test_09_all_tutor_prompts_within_rc_scope(self):
        for item in QUESTIONS:
            for choice in range(len(item["options"])):
                guard = {"dc": dc_outside_scope, "logic": logic_outside_scope}.get(TOPICS[item["topic"]].get("domain"), outside_scope)
                self.assertFalse(guard(tutor_prompt(item["id"], choice)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
