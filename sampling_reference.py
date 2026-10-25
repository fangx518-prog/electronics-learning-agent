"""Locally curated teaching notes; examples are computed, not measured."""
REFERENCES=[
 {'id':'K17','title':'正弦、频率与周期','tags':['正弦','波形','频率','周期','sine'],
  'summary':'正弦用幅值和频率描述；周期T=1/f。此处画图选零初相，不能由频率推断实际幅值或相位。',
  'url':'https://openstax.org/books/university-physics-volume-2/pages/15-1-ac-sources','source':'OpenStax · University Physics Volume 2','section':'15.1 AC Sources，式15.1'},
 {'id':'K18','title':'纯正弦的峰值与有效值','tags':['峰值','峰峰','有效值','rms','幅值','正弦'],
  'summary':'无直流偏置纯正弦的峰峰值为2倍峰值；完整周期RMS为峰值除以√2。其他波形或带直流偏置时不能直接套用此RMS关系。',
  'url':'https://openstax.org/books/university-physics-volume-2/pages/15-4-power-in-an-ac-circuit','source':'OpenStax · University Physics Volume 2','section':'15.4 RMS定义与正弦有效值'},
 {'id':'K19','title':'基带采样条件','tags':['采样','奈奎斯特','nyquist','间隔','两倍','2倍','最高频率'],
  'summary':'基带信号的采样率应高于最高频率的2倍。恰在边界时可能丢失相位相关信息；实际系统还需要滤波过渡带等裕量。采样率与采样间隔互为倒数。',
  'url':'https://www.analog.com/media/en/training-seminars/tutorials/mt-002.pdf','source':'Analog Devices · MT-002','section':'第4—8页：Nyquist Criterion与Baseband Antialiasing Filters'},
 {'id':'K20','title':'单频混叠与采样前滤波','tags':['混叠','alias','折叠','滤波','抗混叠','恢复','单频'],
  'summary':'均匀采样会使相差采样率整数倍的频率难以区分，实信号常折回0到fs/2观察。采样前应抑制带外成分；混叠发生后，单靠后置数字滤波不能分离已经重叠的成分。',
  'url':'https://www.analog.com/media/en/training-seminars/tutorials/mt-002.pdf','source':'Analog Devices · MT-002','section':'第5—6页：频谱镜像、第一奈奎斯特区与基带滤波'},
]


def outside_scope(query):
    return any(word in query.lower() for word in ('天线','wifi','射频匹配','stm32引脚','fpga代码','fft实现','带通采样设计','adc选型','电阻分压','布尔表达式'))


def search_references(query):
    if not isinstance(query,str) or not query.strip() or len(query)>2000:
        raise ValueError('请提供1到2000字的具体问题。')
    if outside_scope(query):
        return {'found':False,'entries':[],'coverage':'仅支持纯正弦与理想基带均匀采样入门。'}
    ranked=sorted(((sum(tag in query.lower() for tag in item['tags']),item) for item in REFERENCES),key=lambda pair:(-pair[0],pair[1]['id']))
    entries=[{k:v for k,v in item.items() if k!='tags'} for score,item in ranked if score]
    return {'found':bool(entries),'entries':entries,'coverage':'本地整理笔记，非实时联网检索。'}


def build_report(question, answer, calculations, sources):
    from sampling_core import result_text, waveform_points
    lines=['# 信号与采样学习记录','','理想教学计算，非硬件实测或实际ADC验证。','','## 问题','',question,'','## 助手说明','',answer,'','## 本轮工具结果','']
    if not calculations:
        lines+=['本轮没有新的计算结果，不沿用其他轮数据。','']
    for data in calculations:
        lines += [result_text(data),'',data['assumption'],'',data['note'],'']
        points=waveform_points(data)
        if points and points['samples']:
            lines += ['图示为单位幅值、零初相正弦的理论采样点；不表示用户实际幅值。','','| 时间（s） | 归一化幅值 |','| --- | --- |']
            lines += [f"| {p['time_s']:.12g} | {p['value']:.12g} |" for p in points['samples']]
            lines += ['']
    lines+=['## 本轮资料依据','']
    lines += [f"- [{s['id']}] [{s['title']}]({s['url']}) · {s['section']}" for s in sources] or ['本轮没有可展示的检索条目。']
    return '\n'.join(lines)
