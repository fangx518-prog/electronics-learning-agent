"""非负直流量、正电阻的理想电路计算，不涉及交流或非线性器件。"""
import json
import math


def finite(value, label, positive=False):
    if type(value) not in (int, float):
        raise ValueError(f"{label}必须为数值。")
    try:
        valid = math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{label}必须为有限{'正' if positive else '非负'}数。")
    return value


def solve_resistor(voltage_v=None, current_a=None, resistance_ohm=None):
    if sum(value is not None for value in (voltage_v, current_a, resistance_ohm)) != 2:
        raise ValueError("请恰好提供电压、电流、电阻中的两个已知量，并明确单位。")
    if voltage_v is not None:
        finite(voltage_v, "电压")
    if current_a is not None:
        finite(current_a, "电流")
    if resistance_ohm is not None:
        finite(resistance_ohm, "电阻", positive=True)
    try:
        if voltage_v is None:
            voltage_v = current_a * resistance_ohm
        elif current_a is None:
            current_a = voltage_v / resistance_ohm
        else:
            if current_a == 0:
                raise ValueError("已知电流为0时，不能用 V/I 唯一确定有限正电阻，请提供电阻值。")
            resistance_ohm = voltage_v / current_a
        power_w = voltage_v * current_a
        finite(voltage_v, "计算电压")
        finite(current_a, "计算电流")
        finite(resistance_ohm, "计算电阻", positive=True)
        finite(power_w, "计算功率")
        if (voltage_v == 0) != (current_a == 0) or (voltage_v > 0 and power_w == 0):
            raise ValueError("计算发生数值下溢，请检查数量级。")
    except (OverflowError, ZeroDivisionError):
        raise ValueError("参数超出数值范围，请检查数量级。") from None
    return {"voltage_v": voltage_v, "current_a": current_a, "resistance_ohm": resistance_ohm,
            "power_w": power_w, "assumption": "理想欧姆电阻的直流稳态；使用非负电压、电流大小；未实测。"}


def calculate_ohm_law(voltage_v=None, current_a=None, resistance_ohm=None):
    return {"kind": "ohm", **solve_resistor(voltage_v, current_a, resistance_ohm)}


def calculate_dc_power(voltage_v=None, current_a=None, resistance_ohm=None):
    return {"kind": "power", **solve_resistor(voltage_v, current_a, resistance_ohm),
            "note": "这是理论耗散功率，不代表已完成额定功率选型或温升验证。"}


def calculate_voltage_divider(vin_v, r_top_ohm, r_bottom_ohm, load_ohm=None):
    finite(vin_v, "输入电压")
    finite(r_top_ohm, "上臂电阻", positive=True)
    finite(r_bottom_ohm, "下臂电阻", positive=True)
    if load_ohm is not None:
        finite(load_ohm, "负载电阻", positive=True)
    try:
        bottom = r_bottom_ohm
        if load_ohm is not None:
            # 避免直接计算两个大电阻的乘积。
            smaller, larger = sorted((r_bottom_ohm, load_ohm))
            bottom = smaller / (1 + smaller / larger)
        def ratio(low, high):
            scale = max(low, high)
            return (low / scale) / (low / scale + high / scale)
        unloaded = vin_v * ratio(r_bottom_ohm, r_top_ohm)
        output = vin_v * ratio(bottom, r_top_ohm)
        finite(bottom, "下臂等效电阻", positive=True)
        finite(unloaded, "空载输出电压")
        finite(output, "输出电压")
        if vin_v > 0 and (unloaded == 0 or output == 0):
            raise ValueError("计算发生数值下溢，请检查数量级。")
    except (OverflowError, ZeroDivisionError):
        raise ValueError("参数超出数值范围，请检查数量级。") from None
    return {"kind": "divider", "vin_v": vin_v, "r_top_ohm": r_top_ohm,
            "r_bottom_ohm": r_bottom_ohm, "load_ohm": load_ohm,
            "effective_bottom_ohm": bottom, "unloaded_vout_v": unloaded, "vout_v": output,
            "assumption": "理想直流电压源；上臂连接输入与输出，下臂连接输出与参考地；负载并联在下臂；未实测。"}


PAIR_PROPERTIES = {
    "voltage_v": {"type": ["number", "null"], "description": "已知电压大小，V；未知则null"},
    "current_a": {"type": ["number", "null"], "description": "已知电流大小，A；未知则null，mA先换算为A"},
    "resistance_ohm": {"type": ["number", "null"], "description": "已知正电阻，Ω；未知则null"},
}
TOOLS = [{"type": "function", "function": {
    "name": name, "description": description,
    "parameters": {"type": "object", "properties": PAIR_PROPERTIES,
                   "required": list(PAIR_PROPERTIES), "additionalProperties": False}}}
    for name, description in (
        ("calculate_ohm_law", "理想直流电阻：V、I、R中恰好两个已知量，第三个必须null，求未知量。"),
        ("calculate_dc_power", "理想直流电阻耗散功率：V、I、R中恰好两个已知量，第三个必须null；不支持已知功率反求。"))]
TOOLS.append({"type": "function", "function": {
    "name": "calculate_voltage_divider", "description": "计算两个串联电阻的直流分压；输出跨下臂，负载并联下臂。不接负载时load_ohm必须null。",
    "parameters": {"type": "object", "properties": {
        "vin_v": {"type": "number", "description": "非负输入电压，V"},
        "r_top_ohm": {"type": "number", "description": "输入到输出的上臂电阻，Ω"},
        "r_bottom_ohm": {"type": "number", "description": "输出到地的下臂电阻，Ω"},
        "load_ohm": {"type": ["number", "null"], "description": "并联下臂的负载电阻，Ω；无负载null"}},
        "required": ["vin_v", "r_top_ohm", "r_bottom_ohm", "load_ohm"], "additionalProperties": False}}})


def execute_tool(name, arguments):
    functions = {"calculate_ohm_law": (calculate_ohm_law, set(PAIR_PROPERTIES)),
                 "calculate_dc_power": (calculate_dc_power, set(PAIR_PROPERTIES)),
                 "calculate_voltage_divider": (calculate_voltage_divider, {"vin_v", "r_top_ohm", "r_bottom_ohm", "load_ohm"})}
    if name not in functions:
        return {"ok": False, "error": "不支持此工具。"}
    try:
        params = json.loads(arguments)
        function, keys = functions[name]
        if not isinstance(params, dict) or set(params) != keys:
            raise ValueError("工具参数不完整或包含额外字段。")
        return {"ok": True, "result": function(**params)}
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        return {"ok": False, "error": str(exc) if isinstance(exc, ValueError) else "参数格式或数量级无效。"}


def result_text(data):
    if data["kind"] == "divider":
        load = "未接负载" if data["load_ohm"] is None else f"负载 {data['load_ohm']:.8g} Ω"
        return (f"输入 {data['vin_v']:.8g} V；上臂 {data['r_top_ohm']:.8g} Ω；下臂 {data['r_bottom_ohm']:.8g} Ω；{load}；"
                f"空载输出 {data['unloaded_vout_v']:.8g} V；当前输出 {data['vout_v']:.8g} V。")
    milli = data['current_a'] * 1000
    milli_text = f"（{milli:.8g} mA）" if math.isfinite(milli) else ""
    return (f"电压 {data['voltage_v']:.8g} V；电流 {data['current_a']:.8g} A{milli_text}；"
            f"电阻 {data['resistance_ohm']:.8g} Ω；理论功率 {data['power_w']:.8g} W。")
