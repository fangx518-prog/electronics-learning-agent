"""组合逻辑离线核对，无密钥、无API。"""
import unittest

import logic_agent as agent
from logic_core import truth_table, evaluate_logic, compare_logic, execute_tool
from logic_reference import build_report
from verify_core import FakeClient, NS, completion


class LogicChecks(unittest.TestCase):
    def test_01_basic_gates(self):
        for expression, expected in [("A AND B", [0, 0, 0, 1]), ("A OR B", [0, 1, 1, 1]),
                                     ("A XOR B", [0, 1, 1, 0]), ("NOT A", [1, 0])]:
            self.assertEqual([row["Y"] for row in truth_table(expression)["rows"]], expected)

    def test_02_nand(self):
        self.assertEqual([row["Y"] for row in truth_table("NOT(A AND B)")["rows"]], [1, 1, 1, 0])

    def test_03_assignment(self):
        self.assertEqual(evaluate_logic("A AND B", {"A": 1, "B": 0})["output"], 0)
        for values in [{"A": 1}, {"A": 1, "B": True}, {"A": 1, "B": 2}, {"A": 1, "B": 0, "C": 0}]:
            with self.assertRaises(ValueError):
                evaluate_logic("A AND B", values)

    def test_04_notation(self):
        expected = truth_table("~A ^ (B & C)")["rows"]
        for expression in ["not a xor (b and c)", "非A异或（B与C）", "!A ^ (B & C)"]:
            self.assertEqual(truth_table(expression)["rows"], expected)

    def test_05_precedence(self):
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    actual = evaluate_logic("NOT A OR B AND C", {"A": a, "B": b, "C": c})["output"]
                    self.assertEqual(actual, int((not a) or (b and c)))

    def test_06_equivalence(self):
        self.assertTrue(compare_logic("NOT(A AND B)", "(NOT A) OR (NOT B)")["equivalent"])
        self.assertTrue(compare_logic("A", "A AND (B OR NOT B)")["equivalent"])

    def test_07_counterexample(self):
        result = compare_logic("A OR B", "A XOR B")
        self.assertFalse(result["equivalent"])
        self.assertEqual(result["counterexample"], {"A": 1, "B": 1, "F": 1, "G": 0})

    def test_08_constant_and_maximum_rows(self):
        self.assertEqual(truth_table("1")["rows"], [{"Y": 1}])
        self.assertEqual(evaluate_logic("0", {})["output"], 0)
        self.assertEqual(len(truth_table("A XOR B XOR C XOR D")["rows"]), 16)

    def test_09_reject_unsupported_syntax(self):
        for text in ["E", "2", "True", "A+B", "A**B", "A[0]", "A.real", "[A]", "__import__('os')", "f'{A}'", "A and", ""]:
            with self.assertRaises(ValueError, msg=text):
                truth_table(text)

    def test_10_complexity_limits(self):
        for text in ["~" * 40 + "A", "A" * 201]:
            with self.assertRaises(ValueError):
                truth_table(text)

    def test_11_dispatch_validation(self):
        self.assertFalse(execute_tool("exec", "{}")["ok"])
        self.assertFalse(execute_tool("truth_table", '{"expression":"A","extra":1}')["ok"])
        self.assertTrue(execute_tool("truth_table", '{"expression":"A XOR B"}')["ok"])

    def test_12_agent_tables_and_sources(self):
        calls = [NS(id="calc", function=NS(name="truth_table", arguments='{"expression":"A XOR B"}')),
                 NS(id="ref", function=NS(name="search_logic_references", arguments='{"query":"异或XOR"}'))]
        client = FakeClient(lambda n: completion(calls=calls) if n == 1 else completion("异或在输入不同时输出1[K16]。"))
        results = []
        answer, _ = agent.run_turn(client, [], "异或真值表", emit=lambda _: None, on_result=results.append)
        self.assertIn("K16", answer)
        self.assertEqual(len(results[0]["rows"]), 4)

    def test_13_invalid_citation(self):
        client = FakeClient(lambda _: completion("错误[K99]"))
        answer, history = agent.run_turn(client, [], "原理", emit=lambda _: None)
        self.assertIn("未通过核验", answer)
        self.assertNotIn("K99", str(history))
        self.assertEqual(len(client.requests), 2)

    def test_14_scope_and_limits(self):
        client = FakeClient(lambda _: self.fail("超范围不应调用模型"))
        answer, _ = agent.run_turn(client, [], "设计WiFi天线", emit=lambda _: None)
        self.assertIn("超出", answer)
        call = NS(id="ref", function=NS(name="search_logic_references", arguments='{"query":"AND"}'))
        client = FakeClient(lambda _: completion(calls=[call]))
        with self.assertRaises(RuntimeError):
            agent.run_turn(client, [], "AND", emit=lambda _: None)
        self.assertEqual(len(client.requests), 6)

    def test_15_report(self):
        report = build_report("真值表", "说明", [truth_table("A XOR B")], [])
        self.assertIn("| A | B | Y |", report)
        self.assertIn("| 1 | 1 | 0 |", report)
        self.assertNotIn("截止频率", report)
        self.assertIn("没有新的计算结果", build_report("原理", "说明", [], []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
