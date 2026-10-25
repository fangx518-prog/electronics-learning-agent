"""Bounded deterministic tools for ideal sine waves and baseband sampling."""
import json
import math

ASSUMPTION = '理想均匀采样的教学计算，未模拟ADC量化、噪声、抖动或实际硬件；不用于带通采样设计。'


def number(value, name, minimum=1e-6, maximum=1e9):
    if type(value) not in (int, float) or not minimum <= value <= maximum or not math.isfinite(value):
        raise ValueError(f'{name}必须为{minimum:g}到{maximum:g}之间的有限数值，不能是布尔值。')
    return float(value)


def analyze_sine(frequency_hz, peak_v):
    f = number(frequency_hz, '频率（Hz）')
    a = number(peak_v, '峰值（V）', 0, 1e6)
    return {'kind':'sine', 'frequency_hz':f, 'peak_v':a, 'period_s':1/f,
            'peak_to_peak_v':2*a, 'rms_v':a/math.sqrt(2), 'assumption':ASSUMPTION,
            'note':'仅适用于无直流偏置的纯正弦波；RMS是完整周期的理论值，非有限采样点的统计估计。图示初相为0。'}


def check_sampling(max_frequency_hz, sample_rate_hz):
    f = number(max_frequency_hz, '基带信号最高频率（Hz）')
    fs = number(sample_rate_hz, '采样率（Sa/s）')
    status = 'above' if fs > 2*f else 'boundary' if fs == 2*f else 'below'
    conclusion = {'above':'高于2倍最高频率，满足本工具的理想基带采样频率条件；仍需考虑抗混叠滤波和实际ADC性能。',
                  'boundary':'恰好等于2倍最高频率，属于临界边界，不能保证任意相位信号可恢复；建议增加采样率并留滤波裕量。',
                  'below':'低于2倍最高频率，不能保证该带宽内任意信号无混叠恢复。'}[status]
    return {'kind':'sampling', 'max_frequency_hz':f, 'sample_rate_hz':fs, 'sample_interval_s':1/fs,
            'nyquist_hz':fs/2, 'twice_max_hz':2*f, 'status':status, 'conclusion':conclusion,
            'assumption':ASSUMPTION, 'note':'按基带信号最高频率判断；不把等于2倍判为可靠通过，也不据此选择具体ADC。'}


def analyze_alias(signal_frequency_hz, sample_rate_hz):
    f = number(signal_frequency_hz, '单频信号频率（Hz）')
    fs = number(sample_rate_hz, '采样率（Sa/s）')
    signed = math.remainder(f, fs)
    return {'kind':'alias', 'signal_frequency_hz':f, 'sample_rate_hz':fs,
            'alias_frequency_hz':abs(signed), 'signed_alias_hz':signed, 'nyquist_hz':fs/2,
            'at_boundary':abs(signed)==fs/2, 'folded':f>fs/2, 'assumption':ASSUMPTION,
            'note':'输出是折回0到fs/2的等效频率大小，不能据采样点唯一推断原始频率。图示用单位幅值、零初相正弦；有符号频率保留必要的相位反转。'}


def waveform_points(data):
    """Finite drawing data derived only from validated tool parameters, never model prose."""
    if data['kind'] not in ('sine','alias'):
        return None
    f = data.get('frequency_hz',data.get('signal_frequency_hz'))
    a = data.get('peak_v',1.0)
    duration = 3/f
    lines = [{'time_s':duration*i/1200, 'value':a*math.sin(2*math.pi*3*i/1200), 'series':'原始正弦'} for i in range(1201)]
    samples = []
    if data['kind']=='alias':
        fs = data['sample_rate_hz']
        count = math.floor(duration*fs)+1
        if not 3 <= count <= 1000:
            return None
        signed=data['signed_alias_hz']
        lines += [{'time_s':duration*i/1200, 'value':math.sin(2*math.pi*signed*duration*i/1200), 'series':'折叠等价正弦'} for i in range(1201)]
        samples=[{'time_s':n/fs, 'value':math.sin(2*math.pi*f*n/fs)} for n in range(count)]
    return {'lines':lines,'samples':samples}


FUNCTIONS={'analyze_sine':(analyze_sine,{'frequency_hz','peak_v'}),
           'check_sampling':(check_sampling,{'max_frequency_hz','sample_rate_hz'}),
           'analyze_alias':(analyze_alias,{'signal_frequency_hz','sample_rate_hz'})}
TOOLS=[]
for name,description,properties in [
    ('analyze_sine','已知纯正弦频率Hz和峰值V，计算周期、峰峰值和完整周期RMS；不支持直流偏置或任意波形。',
     {'frequency_hz':{'type':'number'},'peak_v':{'type':'number'}}),
    ('check_sampling','已知基带信号最高频率Hz及采样率Sa/s，核对采样条件；等于2倍属于边界，不保证恢复。',
     {'max_frequency_hz':{'type':'number'},'sample_rate_hz':{'type':'number'}}),
    ('analyze_alias','已知单一频率Hz及均匀采样率Sa/s，计算折回0到fs/2的等效频率。',
     {'signal_frequency_hz':{'type':'number'},'sample_rate_hz':{'type':'number'}}),
]:
    TOOLS.append({'type':'function','function':{'name':name,'description':description,
                  'parameters':{'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}}})


def execute_tool(name, arguments):
    if name not in FUNCTIONS:
        return {'ok':False,'error':'不支持此工具。'}
    try:
        params=json.loads(arguments)
        function,expected=FUNCTIONS[name]
        if not isinstance(params,dict) or set(params)!=expected:
            raise ValueError('工具参数不完整或包含额外字段。')
        return {'ok':True,'result':function(**params)}
    except (TypeError,ValueError,OverflowError,RecursionError) as exc:
        return {'ok':False,'error':str(exc) if isinstance(exc,ValueError) else '参数格式无效。'}


def result_text(data):
    if data['kind']=='sine':
        return f"正弦频率 {data['frequency_hz']:.8g} Hz；峰值 {data['peak_v']:.8g} V；周期 {data['period_s']:.8g} s；峰峰值 {data['peak_to_peak_v']:.8g} V；RMS {data['rms_v']:.8g} V。"
    if data['kind']=='sampling':
        return f"基带最高频率 {data['max_frequency_hz']:.8g} Hz；采样率 {data['sample_rate_hz']:.8g} Sa/s；采样间隔 {data['sample_interval_s']:.8g} s；奈奎斯特频率 {data['nyquist_hz']:.8g} Hz。{data['conclusion']}"
    return f"单频输入 {data['signal_frequency_hz']:.8g} Hz，以 {data['sample_rate_hz']:.8g} Sa/s 采样；折叠等效频率 {data['alias_frequency_hz']:.8g} Hz。"
