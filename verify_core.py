"""离线逻辑检查：不读取密钥，不调用模型，不产生 API 费用。"""

import json
import math
import unittest
from types import SimpleNamespace as NS

import rc_agent as agent
from rc_core import calculate_rc_cutoff, design_rc_component, response_points
from rc_reference import REFERENCES, build_report, search_references


class FakeClient:
    def __init__(self, respond):
        self.respond = respond
        self.requests = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.respond(len(self.requests))


def completion(content=None, calls=None):
    return NS(choices=[NS(finish_reason="tool_calls" if calls else "stop",
                         message=NS(content=content, tool_calls=calls))])


class CoreChecks(unittest.TestCase):
    def test_01_known_cutoff(self):
        self.assertAlmostEqual(calculate_rc_cutoff(1000, 100)["cutoff_hz"], 1591.5494309189535)

    def test_02_inverse_resistor(self):
        self.assertAlmostEqual(design_rc_component(1000, "capacitor", 100)["r_ohm"], 1591.5494309189535)

    def test_03_inverse_capacitor(self):
        self.assertAlmostEqual(design_rc_component(2000, "resistor", 1000)["c_nf"], 79.57747154594767)

    def test_04_parameter_scaling(self):
        a = calculate_rc_cutoff(1000, 100)["cutoff_hz"]
        self.assertAlmostEqual(calculate_rc_cutoff(2000, 100)["cutoff_hz"], a / 2)
        self.assertAlmostEqual(calculate_rc_cutoff(1000, 200)["cutoff_hz"], a / 2)

    def test_05_invalid_resistor(self):
        for value in (0, -1, True, "1000", None):
            with self.assertRaises(ValueError):
                calculate_rc_cutoff(value, 100)

    def test_06_invalid_capacitor(self):
        for value in (0, -1, True, "100", None):
            with self.assertRaises(ValueError):
                calculate_rc_cutoff(1000, value)

    def test_07_nonfinite_values(self):
        for value in (float("nan"), float("inf"), 10 ** 500):
            with self.assertRaises(ValueError):
                calculate_rc_cutoff(value, 100)

    def test_08_numeric_extremes(self):
        for values in ((1e-300, 1e-300), (1e300, 1e300)):
            with self.assertRaises(ValueError):
                calculate_rc_cutoff(*values)

    def test_09_corner_gain(self):
        rows = response_points(1000, 100)
        middle = [row for row in rows if math.isclose(row["frequency_hz"], 1591.5494309189535)]
        self.assertEqual(len(middle), 2)
        for row in middle:
            self.assertAlmostEqual(row["gain_db"], -3.010299956639812)

    def test_10_curve_monotonicity(self):
        rows = response_points(1000, 100)
        low = [row["gain_db"] for row in rows if row["filter"] == "低通"]
        high = [row["gain_db"] for row in rows if row["filter"] == "高通"]
        self.assertTrue(all(a > b for a, b in zip(low, low[1:])))
        self.assertTrue(all(a < b for a, b in zip(high, high[1:])))

    def test_11_tool_allowlist(self):
        self.assertFalse(agent.execute_tool("unknown_function", "{}")["ok"])

    def test_12_tool_arguments(self):
        for value in ("[]", "bad json", "{}", '{"r_ohm":1000,"c_nf":100,"extra":1}'):
            self.assertFalse(agent.execute_tool("calculate_rc_cutoff", value)["ok"])

    def test_13_reference_match(self):
        self.assertEqual(search_references("低通高通的接线和输出位置")["entries"][0]["id"], "K2")

    def test_14_reference_no_match(self):
        for query in ("STM32的WiFi天线", "量子纠缠计算", "555芯片怎么接线"):
            self.assertFalse(search_references(query)["found"])

    def test_15_reference_arguments(self):
        for query in ("", None, "a" * 2001):
            with self.assertRaises(ValueError):
                search_references(query)

    def test_16_report_traceability(self):
        data = design_rc_component(1000, "capacitor", 100)
        report = build_report("设计", "工具结果", data, REFERENCES[:1])
        self.assertIn("1591.549431", report)
        self.assertIn("待测", report)
        self.assertIn("尚未录入实测数据", report)
        self.assertIn("## 本轮检索到的资料", report)
        self.assertIn("## 通用实验指导的参考资料", report)

    def test_17_report_has_no_stale_calculation(self):
        report = build_report("原理", "说明", None, [])
        self.assertIn("本轮未执行新的元件参数计算", report)
        self.assertNotIn("1591", report)

    def test_18_unknown_citation_rejected(self):
        client = FakeClient(lambda _: completion("资料[K99]"))
        answer, history = agent.run_turn(client, [{"role": "system", "content": agent.SYSTEM_PROMPT}], "原理", emit=lambda _: None)
        self.assertNotIn("K99", answer)
        self.assertIn("未通过核验", answer)
        self.assertEqual(len(client.requests), 2)
        self.assertFalse(any("K99" in str(item) for item in history))

    def test_19_loop_is_bounded(self):
        call = NS(id="calc", function=NS(name="calculate_rc_cutoff", arguments='{"r_ohm":1000,"c_nf":100}'))
        client = FakeClient(lambda _: completion(calls=[call]))
        history = [{"role": "system", "content": agent.SYSTEM_PROMPT}]
        with self.assertRaises(RuntimeError):
            agent.run_turn(client, history, "计算", emit=lambda _: None)
        self.assertEqual(len(client.requests), 6)
        self.assertEqual(len(history), 1)

    def test_20_calculation_and_reference_callbacks(self):
        calls = [NS(id="calc", function=NS(name="calculate_rc_cutoff", arguments='{"r_ohm":1000,"c_nf":100}')),
                 NS(id="ref", function=NS(name="search_references", arguments='{"query":"半功率 增益 0.707"}'))]
        client = FakeClient(lambda n: completion(calls=calls) if n == 1 else completion("约1591.55Hz；截止点幅值约0.707[K3]。"))
        results, sources = [], []
        answer, history = agent.run_turn(client, [{"role": "system", "content": agent.SYSTEM_PROMPT}], "计算并解释",
                                         emit=lambda _: None, on_result=results.append, on_sources=sources.extend)
        self.assertAlmostEqual(results[0]["cutoff_hz"], 1591.5494309189535)
        self.assertIn("K3", {item["id"] for item in sources})
        self.assertIn("1591.55", answer)
        self.assertEqual(history[-1]["role"], "assistant")
        self.assertEqual(client.requests[-1]["messages"][-1]["role"], "tool")

    def test_21_case26_first_attempt(self):
        client = FakeClient(lambda _: self.fail("越界问题不应调用模型"))
        answer, history = agent.run_turn(client, [], "STM32的WiFi天线怎么设计", emit=lambda _: None)
        self.assertIn("超出当前版本", answer)
        self.assertNotIn("AN5129", answer)
        self.assertNotIn("[K", answer)
        self.assertEqual(len(client.requests), 0)
        self.assertEqual(history[-1]["content"], answer)

    def test_22_case26_after_rc_conversation(self):
        client = FakeClient(lambda _: self.fail("越界问题不应调用模型"))
        original = [{"role": "user", "content": "R=1000Ω，C=100nF"},
                    {"role": "assistant", "content": "1591.55Hz"}]
        answer, history = agent.run_turn(client, original, "STM32的WiFi天线怎么设计", emit=lambda _: None)
        self.assertNotIn("1000", answer)
        self.assertNotIn("1591", answer)
        self.assertEqual(len(original), 2)
        self.assertEqual(len(history), 4)

    def test_23_mcu_rc_application_remains_supported(self):
        client = FakeClient(lambda _: completion("请提供电阻、电容值和单位。"))
        answer, _ = agent.run_turn(client, [], "STM32 ADC前端的一阶RC低通，计算截止频率", emit=lambda _: None)
        self.assertEqual(len(client.requests), 1)
        self.assertNotIn("超出", answer)
        self.assertTrue(search_references("STM32 ADC前端一阶RC低通的接线")["found"])

    def test_24_empty_retrieval_returns_insufficiency(self):
        call = NS(id="ref", function=NS(name="search_references", arguments=json.dumps({"query": "量子纠缠计算"})))
        client = FakeClient(lambda _: completion(calls=[call]))
        answer, history = agent.run_turn(client, [], "量子纠缠计算", emit=lambda _: None)
        self.assertIn("没有找到匹配条目", answer)
        self.assertNotIn("[K", answer)
        self.assertEqual(len(client.requests), 1)
        self.assertEqual(history[-2]["role"], "tool")

    def test_25_unknown_citation_can_be_repaired(self):
        call = NS(id="ref", function=NS(name="search_references", arguments=json.dumps({"query": "半功率 0.707"})))
        def respond(n):
            if n == 1:
                return completion("错误资料[K99]")
            if n == 2:
                return completion(calls=[call])
            return completion("截止点幅值比约0.707[K3]。")
        client = FakeClient(respond)
        answer, history = agent.run_turn(client, [], "截止点增益", emit=lambda _: None)
        self.assertIn("[K3]", answer)
        self.assertNotIn("K99", str(history))
        self.assertNotIn("上一份回答", str(history))
        self.assertEqual(len(client.requests), 3)

    def test_26_safe_fallback_preserves_only_current_calculation(self):
        call = NS(id="calc", function=NS(name="calculate_rc_cutoff", arguments='{"r_ohm":2000,"c_nf":100}'))
        client = FakeClient(lambda n: completion(calls=[call]) if n == 1 else completion("错误[K99]"))
        answer, _ = agent.run_turn(client, [{"role": "assistant", "content": "旧值R=1234"}], "计算并解释", emit=lambda _: None)
        self.assertIn("2000", answer)
        self.assertIn("795.77472", answer)
        self.assertNotIn("1234", answer)
        self.assertNotIn("K99", answer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
