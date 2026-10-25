"""一阶理想 RC 的确定性计算、参数校验与理论曲线。"""

import json

import math



def calculate_rc_cutoff(r_ohm, c_nf):
    """Python 执行实际计算；这里不调用模型。"""
    for label, value in (("电阻", r_ohm), ("电容", c_nf)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label}必须是数值。")
        try:
            valid = math.isfinite(value) and value > 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"{label}必须是有限正数。")

    try:
        tau_s = r_ohm * (c_nf * 1e-9)
        cutoff_hz = 1 / (2 * math.pi * tau_s)
    except (OverflowError, ZeroDivisionError):
        raise ValueError("参数超出当前数值计算范围，请检查数量级。") from None
    if not math.isfinite(tau_s) or tau_s <= 0 or not math.isfinite(cutoff_hz) or cutoff_hz <= 0:
        raise ValueError("参数超出当前数值计算范围，请检查数量级。")

    return {
        "r_ohm": r_ohm,
        "c_nf": c_nf,
        "cutoff_hz": cutoff_hz,
        "time_constant_s": tau_s,
        "assumption": "理想一阶 RC 电路，忽略负载影响",
    }

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_rc_cutoff",
            "description": "已知电阻与电容，计算截止频率；实际元件值修改后也用此工具重新计算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "r_ohm": {"type": "number", "description": "已知电阻，Ω，有限正数"},
                    "c_nf": {"type": "number", "description": "已知电容，nF，有限正数"},
                },
                "required": ["r_ohm", "c_nf"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "design_rc_component",
            "description": "给定目标截止频率，以及已知的一个元件值，反求另一个元件的理论值。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_hz": {"type": "number", "description": "目标截止频率，Hz，有限正数"},
                    "known_component": {"type": "string", "enum": ["resistor", "capacitor"], "description": "已知的元件类型"},
                    "known_value": {"type": "number", "description": "已知电阻时单位 Ω；已知电容时单位 nF。有限正数"},
                },
                "required": ["target_hz", "known_component", "known_value"],
                "additionalProperties": False,
            },
        },
    },
]

def positive(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("参数必须为数值。")
    try:
        valid = math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("参数必须为有限正数。")
    return value

def design_rc_component(target_hz, known_component, known_value):
    positive(target_hz)
    positive(known_value)
    if known_component not in ("resistor", "capacitor"):
        raise ValueError("已知元件只能是 resistor 或 capacitor。")
    try:
        if known_component == "capacitor":
            c_nf = known_value
            r_ohm = 1 / (2 * math.pi * target_hz * (c_nf * 1e-9))
            solved = "resistor"
        else:
            r_ohm = known_value
            c_nf = (1 / (2 * math.pi * target_hz * r_ohm)) * 1e9
            solved = "capacitor"
        result = calculate_rc_cutoff(r_ohm, c_nf)
    except (OverflowError, ZeroDivisionError):
        raise ValueError("参数超出数值范围，请检查数量级。") from None
    result.update({"target_hz": target_hz, "solved_component": solved,
                   "note": "理论元件值；未进行标准系列选型。"})
    return result

def response_points(r_ohm, c_nf):
    """在截止频率前后两数量级内生成幅频曲线；结果来自解析公式。"""
    result = calculate_rc_cutoff(r_ohm, c_nf)
    fc = result["cutoff_hz"]
    rows = []
    for index in range(201):
        ratio = 10 ** (-2 + index / 50)
        frequency = fc * ratio
        if not math.isfinite(frequency) or frequency <= 0:
            raise ValueError("频率范围过大，无法绘图，请检查参数数量级。")
        denominator = math.hypot(1, ratio)
        for kind, gain in (("低通", 1 / denominator), ("高通", ratio / denominator)):
            rows.append({"frequency_hz": frequency, "gain_db": 20 * math.log10(gain), "filter": kind})
    return rows

def execute_tool(name, arguments):
    functions = {
        "calculate_rc_cutoff": (calculate_rc_cutoff, {"r_ohm", "c_nf"}),
        "design_rc_component": (design_rc_component, {"target_hz", "known_component", "known_value"}),
    }
    if name not in functions:
        return {"ok": False, "error": "工具不存在。"}
    try:
        params = json.loads(arguments)
        function, expected = functions[name]
        if not isinstance(params, dict) or set(params) != expected:
            raise ValueError("工具参数不完整或包含额外字段。")
        return {"ok": True, "result": function(**params)}
    except (ValueError, TypeError, OverflowError):
        return {"ok": False, "error": "参数无效，请检查单位、完整性和数值范围；所有数值必须为有限正数。"}
