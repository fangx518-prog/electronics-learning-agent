"""Citation repair regressions for three existing agents; no API or credentials."""
import importlib
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from verify_core import FakeClient, completion

CASES = {
    'rc_agent': ('search_references', '截止频率', '解释截止频率'),
    'dc_agent': ('search_dc_references', '欧姆定律', '解释欧姆定律'),
    'logic_agent': ('search_logic_references', '与门', '解释与门'),
}


class CitationRepairChecks(unittest.TestCase):
    def check_repair(self, module_name, final_bad=False):
        module = importlib.import_module(module_name)
        tool, query, question = CASES[module_name]
        client = None

        def respond(number):
            last = client.requests[-1]['messages'][-1]
            if number == 1:
                return completion('未经检索的解释[K999]。')
            if last['role'] == 'user':
                call = NS(id=f'ref{number}', function=NS(
                    name=tool, arguments=json.dumps({'query': query}, ensure_ascii=False)))
                return completion(calls=[call])
            entries = json.loads(last['content'])['result']['entries']
            return completion('仍错误地引用[K999]。' if final_bad else
                              f"本轮资料[{entries[0]['id']}]已核验。")

        client = FakeClient(respond)
        with patch.object(module, 'execute_tool', wraps=module.execute_tool) as execute:
            answer, history = module.run_turn(client, [], question, emit=lambda _: None)
        self.assertEqual(len(client.requests), 3)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual([r['messages'][-1]['role'] for r in client.requests], ['user', 'user', 'tool'])
        self.assertNotIn('[K999]', answer)
        self.assertEqual(history[-1]['content'], answer)
        if final_bad:
            self.assertIn('核验', answer)
            self.assertNotIn('仍错误地引用', answer)
        else:
            self.assertIn('已核验', answer)

    def test_rc_repair_reads_tool_result(self):
        self.check_repair('rc_agent')

    def test_rc_second_invalid_citation_is_hidden(self):
        self.check_repair('rc_agent', final_bad=True)

    def test_dc_repair_reads_tool_result(self):
        self.check_repair('dc_agent')

    def test_dc_second_invalid_citation_is_hidden(self):
        self.check_repair('dc_agent', final_bad=True)

    def test_logic_repair_reads_tool_result(self):
        self.check_repair('logic_agent')

    def test_logic_second_invalid_citation_is_hidden(self):
        self.check_repair('logic_agent', final_bad=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
