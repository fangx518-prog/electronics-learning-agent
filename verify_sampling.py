import json
import math
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

import sampling_agent as agent
from sampling_core import analyze_sine,check_sampling,analyze_alias,execute_tool,waveform_points
from sampling_reference import build_report,search_references
from learning_core import QUESTIONS,TOPICS,QUESTION_MAP,export_progress,import_progress,new_progress,record_answer,summary,tutor_prompt
from verify_core import FakeClient,completion


class SamplingChecks(unittest.TestCase):
    def test_01_sine_parameters(self):
        d=analyze_sine(1000,2)
        self.assertEqual(d['period_s'],.001)
        self.assertEqual(d['peak_to_peak_v'],4)
        self.assertAlmostEqual(d['rms_v'],math.sqrt(2))

    def test_02_zero_peak(self):
        self.assertEqual(analyze_sine(1000,0)['rms_v'],0)

    def test_03_invalid_values(self):
        for x in (0,-1,True,'1000',None,float('nan'),float('inf'),10**500,1e-7):
            for f in (lambda:analyze_sine(x,2),lambda:check_sampling(1000,x),lambda:analyze_alias(x,8000)):
                with self.assertRaises(ValueError):f()
        for x in (-1,True,float('nan'),float('inf'),1e7):
            with self.assertRaises(ValueError):analyze_sine(1000,x)

    def test_04_above(self):
        d=check_sampling(1000,8000)
        self.assertEqual(d['status'],'above')
        self.assertEqual(d['nyquist_hz'],4000)
        self.assertEqual(d['sample_interval_s'],.000125)

    def test_05_boundary(self):
        self.assertEqual(check_sampling(1000,2000)['status'],'boundary')
        self.assertIn('不能保证',check_sampling(1000,2000)['conclusion'])

    def test_06_below(self):
        self.assertEqual(check_sampling(5000,8000)['status'],'below')

    def test_07_alias(self):
        d=analyze_alias(5000,8000)
        self.assertEqual(d['alias_frequency_hz'],3000)
        self.assertEqual(d['signed_alias_hz'],-3000)

    def test_08_unfolded_multiple_and_edge(self):
        self.assertEqual(analyze_alias(1000,8000)['alias_frequency_hz'],1000)
        self.assertEqual(analyze_alias(8000,8000)['alias_frequency_hz'],0)
        self.assertTrue(analyze_alias(4000,8000)['at_boundary'])

    def test_09_periodicity(self):
        for f in (1,1234,4000,5678,100000):
            for k in (1,2,7):
                self.assertAlmostEqual(analyze_alias(f,8000)['alias_frequency_hz'],analyze_alias(f+k*8000,8000)['alias_frequency_hz'])

    def test_10_alias_plot_samples_match_signed_curve(self):
        d=analyze_alias(5000,8000)
        points=waveform_points(d)
        for p in points['samples']:
            self.assertAlmostEqual(p['value'],math.sin(2*math.pi*d['signed_alias_hz']*p['time_s']),places=10)
        self.assertLessEqual(len(points['lines']),2402)

    def test_11_plot_limits_and_sine(self):
        self.assertIsNone(waveform_points(analyze_alias(1e9,1)))
        self.assertIsNone(waveform_points(analyze_alias(1,1e9)))
        self.assertEqual(len(waveform_points(analyze_sine(1000,2))['lines']),1201)
        self.assertIsNone(waveform_points(check_sampling(1000,8000)))

    def test_12_dispatch(self):
        for name,args in [('exec','{}'),('analyze_alias','{}'),('analyze_alias','{"signal_frequency_hz":5000,"sample_rate_hz":8000,"extra":1}'),('analyze_sine','{"frequency_hz":1000,"peak_v":true}')]:
            self.assertFalse(execute_tool(name,args)['ok'])
        self.assertTrue(execute_tool('analyze_alias','{"signal_frequency_hz":5000,"sample_rate_hz":8000}')['ok'])

    def test_13_references(self):
        entries=search_references('混叠为什么需要采样前滤波')['entries']
        self.assertIn('K20',{s['id'] for s in entries})
        self.assertFalse(search_references('火星种植')['entries'])

    def test_14_agent_actual_tool_result(self):
        call=NS(id='alias',function=NS(name='analyze_alias',arguments='{"signal_frequency_hz":5000,"sample_rate_hz":8000}'))
        client=FakeClient(lambda n:completion(calls=[call]) if n==1 else completion('工具结果为3000Hz。'))
        data=[]
        answer,_=agent.run_turn(client,[],'5kHz以8kSa/s采样',emit=lambda _:None,on_result=data.append)
        self.assertEqual(data[0]['alias_frequency_hz'],3000)
        self.assertEqual(len(client.requests),2)

    def test_15_missing_parameter_does_not_execute(self):
        client=FakeClient(lambda n:completion('请提供采样率及单位。'))
        data=[]
        agent.run_turn(client,[],'输入5kHz，混叠是多少',emit=lambda _:None,on_result=data.append)
        self.assertFalse(data)

    def test_16_bad_citation_hidden(self):
        client=FakeClient(lambda n:completion('没有检索也引用[K99]。'))
        answer,_=agent.run_turn(client,[],'解释采样',emit=lambda _:None)
        self.assertIn('核验',answer)
        self.assertNotIn('[K99]',answer)

    def test_17_empty_search_and_scope(self):
        call=NS(id='ref',function=NS(name='search_sampling_references',arguments='{"query":"火星种植"}'))
        client=FakeClient(lambda n:completion(calls=[call]))
        answer,_=agent.run_turn(client,[],'请查资料',emit=lambda _:None)
        self.assertIn('没有匹配',answer)
        before=len(client.requests)
        agent.run_turn(client,[],'WiFi天线设计',emit=lambda _:None)
        self.assertEqual(before,len(client.requests))

    def test_18_reports(self):
        report=build_report('混叠','说明',[analyze_alias(5000,8000)],search_references('混叠')['entries'])
        self.assertIn('3000',report)
        self.assertIn('归一化幅值',report)
        self.assertIn('[K20]',report)
        self.assertNotIn('截止频率',report)

    def test_19_learning_integrity(self):
        self.assertEqual((len(TOPICS),len(QUESTIONS)),(13,39))
        for qid in [f'SG{i:02d}' for i in range(1,10)]:
            self.assertIn('信号与理想基带采样',tutor_prompt(qid))

    def test_20_wrong_review(self):
        p,_=record_answer(new_progress(),'SG01',0)
        self.assertEqual(summary(p)['wrong'],1)
        p,_=record_answer(p,'SG01',1)
        self.assertEqual(summary(p)['wrong'],0)
        self.assertEqual(summary(p)['first_correct'],0)
        self.assertEqual(import_progress(export_progress(p)),p)

    def test_21_previous_30_unchanged(self):
        path=Path(__file__).resolve().parent/'fixtures'/'v2_3_compatibility.json'
        baseline=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(baseline['questions'],QUESTIONS[:30])
        restored=import_progress(json.dumps(baseline['progress']).encode('utf-8'))
        self.assertEqual(restored,baseline['progress'])
        self.assertEqual(summary(restored),baseline['summary'])


if __name__=='__main__':unittest.main(verbosity=2)
