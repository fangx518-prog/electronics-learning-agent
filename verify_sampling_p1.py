"""Regression checks for sampling tool loops; no network or credentials."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import sampling_agent as agent
from verify_core import FakeClient, completion


def call(name='analyze_alias', params=None, identity='calc'):
    if params is None:
        params = {'signal_frequency_hz': 5000, 'sample_rate_hz': 12000}
    return NS(id=identity, type='function', function=NS(name=name, arguments=json.dumps(params)))


class SamplingLoopChecks(unittest.TestCase):
    def run_agent(self, client, history=None):
        self.data, self.events = [], []
        return agent.run_turn(client, history or [], '保持输入信号不变，把采样率改为12kSa/s，重新计算',
                              emit=self.events.append, on_result=self.data.append)

    def test_01_citation_repair_consumes_tool_result(self):
        client = None
        def respond(n):
            last = client.requests[-1]['messages'][-1]
            if n == 1:
                return completion('解释依据[K99]。')
            if last['role'] == 'user':
                return completion(calls=[call('search_sampling_references', {'query': '单频混叠'}, f'ref{n}')])
            entries = json.loads(last['content'])['result']['entries']
            return completion(f"依据[{entries[0]['id']}]说明混叠。")
        client = FakeClient(respond)
        answer, _ = self.run_agent(client)
        self.assertEqual(len(client.requests), 3)
        self.assertEqual(client.requests[-1]['messages'][-1]['role'], 'tool')
        self.assertNotIn('[K99]', answer)
        self.assertIn('[K20]', answer)

    def test_02_repeated_success_is_reused_then_finalized(self):
        client = None
        def respond(n):
            if client.requests[-1].get('tool_choice') == 'none':
                return completion('输入5000 Hz，采样12000 Sa/s，折叠频率5000 Hz。')
            return completion(calls=[call(identity=f'calc{n}')])
        client = FakeClient(respond)
        with patch.object(agent, 'execute_tool', wraps=agent.execute_tool) as execute:
            answer, _ = self.run_agent(client)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(len(self.data), 1)
        self.assertEqual(len(client.requests), 3)
        self.assertEqual(client.requests[-1]['tool_choice'], 'none')
        self.assertIn('5000', answer)

    def test_03_sixth_request_is_reserved_for_answer(self):
        client = None
        def respond(n):
            if client.requests[-1].get('tool_choice') == 'none':
                return completion('以上各组计算已完成，见本轮工具结果。')
            return completion(calls=[call(params={'signal_frequency_hz': 5000, 'sample_rate_hz': 12000+n}, identity=str(n))])
        client = FakeClient(respond)
        self.run_agent(client)
        self.assertEqual(len(client.requests), 6)
        self.assertEqual(len(self.data), 5)
        self.assertEqual(client.requests[-1]['tool_choice'], 'none')

    def test_04_noncompliant_model_keeps_verified_result(self):
        client = FakeClient(lambda n: completion(calls=[call(identity=f'calc{n}')]))
        answer, history = self.run_agent(client)
        self.assertLessEqual(len(client.requests), 6)
        self.assertEqual(len(self.data), 1)
        self.assertIn('工具核实', answer)
        self.assertIn('12000', answer)
        self.assertEqual(history[-1]['role'], 'assistant')
        self.assertIsInstance(history[-1]['content'], str)
        # Every retained assistant tool call has a corresponding tool response.
        for i, message in enumerate(history):
            if not isinstance(message, dict):
                ids = {c.id for c in message.tool_calls}
                responses = {m['tool_call_id'] for m in history[i+1:i+1+len(ids)]}
                self.assertEqual(ids, responses)

    def test_05_bad_citation_after_calculation_never_leaks(self):
        client = FakeClient(lambda n: completion(calls=[call()]) if n == 1 else completion('依据[K99]结论。'))
        answer, _ = self.run_agent(client)
        self.assertIn('核验', answer)
        self.assertIn('12000', answer)
        self.assertNotIn('[K99]', answer)
        self.assertEqual(len(client.requests), 3)

    def test_06_successive_turn_recalculates_updated_rate(self):
        first = FakeClient(lambda n: completion(calls=[call(params={'signal_frequency_hz':5000,'sample_rate_hz':8000})])
                           if n == 1 else completion('5kHz输入以8kSa/s采样，折叠频率3kHz。'))
        _, history = agent.run_turn(first, [], '5kHz以8kSa/s采样，求混叠', emit=lambda _:None)
        second = FakeClient(lambda n: completion(calls=[call()]) if n == 1 else completion('采样率改为12kSa/s后，频率为5kHz。'))
        _, updated = self.run_agent(second, history)
        self.assertEqual(self.data[0]['signal_frequency_hz'], 5000)
        self.assertEqual(self.data[0]['sample_rate_hz'], 12000)
        self.assertEqual(self.data[0]['alias_frequency_hz'], 5000)
        self.assertIn(history[0], updated)

    def test_07_invalid_arguments_can_be_corrected(self):
        client = FakeClient(lambda n: completion(calls=[call(params={})]) if n == 1 else
                            completion(calls=[call()]) if n == 2 else completion('计算完成，折叠频率5kHz。'))
        self.run_agent(client)
        self.assertEqual(len(self.data), 1)
        self.assertEqual(len(client.requests), 3)

    def test_08_tool_budget_keeps_results_and_valid_history(self):
        client = FakeClient(lambda n: completion(calls=[call(params={'signal_frequency_hz':5000,'sample_rate_hz':12000+i}, identity=f'c{i}') for i in range(6)])
                            if n == 1 else completion('六组结果已核对。'))
        self.run_agent(client)
        self.assertEqual(len(self.data), 6)
        self.assertEqual(client.requests[-1]['tool_choice'], 'none')
        self.assertEqual(len(client.requests), 2)

    def test_09_bounded_failure_without_success_does_not_fabricate(self):
        client = FakeClient(lambda n: completion(calls=[call('unknown', {}, f'x{n}')]))
        answer, _ = self.run_agent(client)
        self.assertLessEqual(len(client.requests), 6)
        self.assertFalse(self.data)
        self.assertNotIn('工具核实的理论结果', answer)
        self.assertNotIn('折叠等效频率', answer)

    def test_10_explicit_recalculation_cannot_only_restate_history(self):
        first = FakeClient(lambda n: completion(calls=[call(params={'signal_frequency_hz':5000,'sample_rate_hz':8000})])
                           if n == 1 else completion('8kSa/s时折叠3kHz。'))
        _, history = agent.run_turn(first, [], '5kHz以8kSa/s采样', emit=lambda _:None)
        second = FakeClient(lambda n: completion('历史结论为5kHz。') if n == 1 else
                            completion(calls=[call()]) if n == 2 else completion('本轮已重新计算，结果5kHz。'))
        self.run_agent(second, history)
        self.assertEqual(len(second.requests), 3)
        self.assertEqual(self.data[0]['sample_rate_hz'], 12000)

    def test_11_repeated_refusal_to_recalculate_is_explicit(self):
        first = FakeClient(lambda n: completion(calls=[call()]) if n == 1 else completion('计算完成。'))
        _, history = agent.run_turn(first, [], '计算混叠', emit=lambda _:None)
        second = FakeClient(lambda n: completion('沿用历史结果，不再计算。'))
        answer, _ = self.run_agent(second, history)
        self.assertEqual(len(second.requests), 2)
        self.assertFalse(self.data)
        self.assertIn('未取得新的计算结果', answer)
        self.assertNotIn('沿用历史结果', answer)


if __name__ == '__main__':
    unittest.main(verbosity=2)
