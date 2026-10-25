"""直流计算与智能体离线验证，不读取密钥，不请求真实模型。"""
import json
import math
import unittest

import dc_agent as agent
from dc_core import calculate_ohm_law, calculate_dc_power, calculate_voltage_divider, execute_tool, result_text
from dc_reference import build_report, search_references
from verify_core import FakeClient, NS, completion


class DCChecks(unittest.TestCase):
    def test_01_solve_current_voltage_resistance(self):
        self.assertAlmostEqual(calculate_ohm_law(5, None, 1000)["current_a"], .005)
        self.assertAlmostEqual(calculate_ohm_law(None, .002, 2000)["voltage_v"], 4)
        self.assertAlmostEqual(calculate_ohm_law(5, .005, None)["resistance_ohm"], 1000)

    def test_02_power_three_pairs(self):
        for params in [(5, None, 100), (5, .05, None), (None, .05, 100)]:
            self.assertAlmostEqual(calculate_dc_power(*params)["power_w"], .25)

    def test_03_zero_voltage_and_current(self):
        self.assertEqual(calculate_ohm_law(0, None, 1000)["current_a"], 0)
        self.assertEqual(calculate_ohm_law(None, 0, 1000)["power_w"], 0)
        with self.assertRaises(ValueError):
            calculate_ohm_law(0, 0, None)

    def test_04_invalid_count_and_values(self):
        for params in [(None, None, None), (5, None, None), (5, .005, 1000),
                       (-5, None, 1000), (5, None, 0), (True, None, 1000),
                       (5, 0, None), ("5", None, 1000), (math.inf, None, 1000)]:
            with self.assertRaises(ValueError):
                calculate_ohm_law(*params)

    def test_05_divider_unloaded(self):
        data = calculate_voltage_divider(12, 10000, 20000)
        self.assertAlmostEqual(data["vout_v"], 8)
        self.assertEqual(data["vout_v"], data["unloaded_vout_v"])

    def test_06_divider_loaded(self):
        data = calculate_voltage_divider(5, 10000, 10000, 10000)
        self.assertAlmostEqual(data["effective_bottom_ohm"], 5000)
        self.assertAlmostEqual(data["vout_v"], 5 / 3)
        self.assertAlmostEqual(data["unloaded_vout_v"], 2.5)

    def test_07_loading_trends(self):
        outputs = [calculate_voltage_divider(5, 10000, 10000, load)["vout_v"] for load in [100, 1000, 10000, 100000]]
        self.assertTrue(all(a < b for a, b in zip(outputs, outputs[1:])))
        self.assertTrue(all(0 < value < 2.5 for value in outputs))

    def test_08_divider_invalid_and_zero(self):
        self.assertEqual(calculate_voltage_divider(0, 1000, 1000)["vout_v"], 0)
        for params in [(5, 0, 1000), (5, 1000, -1), (5, 1000, 1000, 0), (float("nan"), 1000, 1000)]:
            with self.assertRaises(ValueError):
                calculate_voltage_divider(*params)

    def test_09_numeric_extremes(self):
        self.assertAlmostEqual(calculate_voltage_divider(5, 1e308, 1e308)["vout_v"], 2.5)
        self.assertAlmostEqual(calculate_voltage_divider(5, 1e308, 1e308, 1e308)["vout_v"], 5 / 3)
        for params in [(1e308, None, 1e-308), (1e-300, None, 1e300)]:
            with self.assertRaises(ValueError):
                calculate_ohm_law(*params)
        self.assertNotIn("inf", result_text(calculate_ohm_law(None, 1e308, 1e-308)))

    def test_10_dispatch_allowlist_and_arguments(self):
        for name, args in [("exec", "{}"), ("calculate_ohm_law", "{}"), ("calculate_ohm_law", "bad"),
                           ("calculate_ohm_law", '{"voltage_v":5,"current_a":null,"resistance_ohm":1000,"extra":0}')]:
            self.assertFalse(execute_tool(name, args)["ok"])
        self.assertTrue(execute_tool("calculate_ohm_law", '{"voltage_v":5,"current_a":null,"resistance_ohm":1000}')["ok"])

    def test_11_reference_matching(self):
        self.assertEqual(search_references("欧姆定律电流")["entries"][0]["id"], "K9")
        self.assertIn("K11", [item["id"] for item in search_references("分压负载并联等效")["entries"]])
        self.assertFalse(search_references("量子纠缠")["found"])

    def test_12_agent_tool_and_reference(self):
        calls = [NS(id="calc", function=NS(name="calculate_ohm_law", arguments='{"voltage_v":5,"current_a":null,"resistance_ohm":1000}')),
                 NS(id="ref", function=NS(name="search_dc_references", arguments='{"query":"欧姆定律电流"}'))]
        client = FakeClient(lambda n: completion(calls=calls) if n == 1 else completion("电流为5mA[K9]。"))
        results, sources = [], []
        answer, _ = agent.run_turn(client, [{"role": "system", "content": agent.SYSTEM_PROMPT}], "5V、1kΩ求电流",
                                    emit=lambda _: None, on_result=results.append, on_sources=sources.extend)
        self.assertAlmostEqual(results[0]["current_a"], .005)
        self.assertIn("5mA", answer)
        self.assertIn("K9", [item["id"] for item in sources])

    def test_13_invalid_citation_is_not_displayed(self):
        client = FakeClient(lambda _: completion("错误资料[K99]"))
        answer, history = agent.run_turn(client, [], "原理", emit=lambda _: None)
        self.assertIn("未通过核验", answer)
        self.assertNotIn("K99", str(history))
        self.assertEqual(len(client.requests), 2)

    def test_14_out_of_scope_before_model(self):
        client = FakeClient(lambda _: self.fail("不应请求模型"))
        answer, _ = agent.run_turn(client, [], "STM32的WiFi天线怎么设计", emit=lambda _: None)
        self.assertIn("超出", answer)
        self.assertEqual(len(client.requests), 0)

    def test_15_loop_limit(self):
        call = NS(id="ref", function=NS(name="search_dc_references", arguments='{"query":"电流"}'))
        client = FakeClient(lambda _: completion(calls=[call]))
        with self.assertRaises(RuntimeError):
            agent.run_turn(client, [], "电流", emit=lambda _: None)
        self.assertEqual(len(client.requests), 6)

    def test_16_report_contains_only_this_turn(self):
        report = build_report("求分压", "解释", [calculate_voltage_divider(5, 10000, 10000)], [])
        self.assertIn("2.5", report)
        self.assertNotIn("截止频率", report)
        self.assertNotIn("[K2]", report)
        empty = build_report("原理", "解释", [], [])
        self.assertIn("没有执行新的数值计算", empty)
        self.assertNotIn("10000", empty)


if __name__ == "__main__":
    unittest.main(verbosity=2)
