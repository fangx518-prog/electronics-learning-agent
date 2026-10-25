"""RC 智能体：工具选择、受限执行、来源编号校验。"""

import json
import re

from rc_core import TOOLS as CORE_TOOLS, execute_tool as execute_core_tool
from rc_core import calculate_rc_cutoff, response_points
from rc_reference import outside_scope, search_references


SYSTEM_PROMPT = """你是中文 RC 电路实验助手，支持理想、忽略负载的一阶低通和高通。
截止频率、时间常数和元件参数反求的新计算必须调用对应工具。
单位换算可以解释换算关系，不得为调用工具擅自补入未知元件值。
电阻换算为 Ω，电容换算为 nF，频率换算为 Hz。
参数或单位缺失时先追问，不得擅自补齐。已有参数可在本次对话后续沿用。
按目标频率反求元件时，必须已有另一个元件值。结果是理论值，尚未标准系列选型。
用户改用实际元件值时重新调用截止频率工具，不得把理论值冒充实际选型。
回答原理、接线、公式依据、实验步骤或误差解释时，先调用 search_references。
检索是本地整理笔记，不是实时网页搜索。只根据本轮检索到的相关内容提供有依据的说明。
引用使用工具实际返回的编号，如[K2]，不得编造编号、文献或网址。
检索无匹配或问题超出一阶RC范围时，明确说明资料不足，不得借无关条目作答。
超范围问题不沿用此前的元件参数，不推荐本轮资料未提供的文档编号或网址。
给出实验步骤时区分建议步骤与已发生的实测；绝不编造实验数据。
成功计算后网页会自动生成理论幅频曲线。没有执行真实仿真或硬件测量。
回答简明：解释用户所需信息、单位和假设，并在相关说明后附上资料编号。
若仅需完成参数计算，可直接给出工具结果，不强制检索。
"""

TOOLS = list(CORE_TOOLS) + [{
    "type": "function",
    "function": {
        "name": "search_references",
        "description": "查询本地整理的一阶 RC 参考资料；解释原理、接线、实验验证、误差及负载时使用。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "具体资料问题，最多2000字"}},
            "required": ["query"], "additionalProperties": False,
        },
    },
}]


def execute_tool(name, arguments):
    if name != "search_references":
        return execute_core_tool(name, arguments)
    try:
        params = json.loads(arguments)
        if not isinstance(params, dict) or set(params) != {"query"}:
            raise ValueError("请提供具体检索问题。")
        return {"ok": True, "result": search_references(**params)}
    except (TypeError, ValueError):
        return {"ok": False, "error": "检索参数无效，请提供1到2000字的具体问题。"}


def run_turn(client, history, question, emit=print, on_result=None, on_sources=None):
    messages = list(history) + [{"role": "user", "content": question}]
    if outside_scope(question):
        emit("范围检查：超出当前版本支持范围，未调用模型。")
        answer = ("这个问题超出当前版本的支持范围。当前助手仅支持理想一阶 RC 低通、高通的计算、"
                  "元件参数反求和基础实验指导，本地资料无法为该问题提供依据。"
                  "你可以继续询问 RC 电路的截止频率、接线或测量方法。")
        messages.append({"role": "assistant", "content": answer})
        return answer, messages
    tool_count = 0
    source_ids = set()
    latest_calculation = None
    repair_instruction = None
    repaired = False

    def safe_answer(reason):
        answer = reason
        if latest_calculation is not None:
            data = latest_calculation
            answer += (f"\n\n本轮计算工具已核实的理论结果：R = {data['r_ohm']:.8g} Ω，"
                       f"C = {data['c_nf']:.8g} nF，截止频率 = {data['cutoff_hz']:.8g} Hz。"
                       "假设为理想一阶 RC，忽略负载；未进行实测。")
        messages.append({"role": "assistant", "content": answer})
        return answer, messages

    for request_index in range(6):
        request_messages = list(messages)
        if repair_instruction:
            request_messages.append({"role": "user", "content": repair_instruction})
            repair_instruction = None
        response = client.chat.completions.create(
            model="deepseek-flash", messages=request_messages, tools=TOOLS,
            max_tokens=1400, extra_body={"thinking": {"type": "disabled"}},
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError("回答达到长度上限，请将需求拆成较短的问题。")
        message = choice.message
        if not message.tool_calls:
            answer = (message.content or "").strip()
            if not answer:
                raise RuntimeError("模型未返回正文，请稍后重试。")
            cited = set(re.findall(r"\[(K\d+)\]", answer))
            if cited - source_ids:
                if repaired or request_index == 5:
                    emit("引用核验：自动纠正后仍未通过，已隐藏未经核实的解释。")
                    return safe_answer("本轮解释的引用未通过核验，因此没有展示该解释。现有资料不足以提供可靠说明。")
                emit("引用核验：发现未检索到的编号，正在自动纠正一次。")
                repaired = True
                allowed = "、".join(sorted(source_ids)) or "无"
                repair_instruction = (f"请重新回答原问题。上一份回答含有未检索到的引用，未向用户展示。"
                                      f"本轮已检索到的资料编号只有：{allowed}。"
                                      "需要依据时先检索；没有相关资料则说明资料不足。"
                                      "不得只删除编号而保留无依据的解释，不得编造外部文档编号或网址。")
                continue
            messages.append({"role": "assistant", "content": answer})
            return answer, messages

        if tool_count + len(message.tool_calls) > 6:
            raise RuntimeError("本轮工具调用达到上限，请分步提问。")
        messages.append(message)
        searched_this_batch = False
        for call in message.tool_calls:
            tool_count += 1
            result = execute_tool(call.function.name, call.function.arguments)
            if result["ok"]:
                data = result["result"]
                if call.function.name == "search_references":
                    searched_this_batch = True
                    entries = data["entries"]
                    source_ids.update(item["id"] for item in entries)
                    labels = "、".join(item["id"] for item in entries) or "无匹配条目"
                    emit(f"本地资料检索：命中 {len(entries)} 条（{labels}）")
                    if on_sources is not None:
                        on_sources(entries)
                else:
                    latest_calculation = data
                    emit(f"工具：{call.function.name}\nR = {data['r_ohm']:.8g} Ω\nC = {data['c_nf']:.8g} nF\n截止频率 = {data['cutoff_hz']:.8g} Hz")
                    if on_result is not None:
                        on_result(data)
            else:
                emit(f"工具拒绝执行：{result['error']}")
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False, allow_nan=False)})
        if searched_this_batch and not source_ids:
            return safe_answer("本轮本地资料检索没有找到匹配条目，现有资料不足以提供有依据的解释。"
                               "当前资料库仅覆盖理想一阶 RC 基础，请补充具体的 RC 问题或相关资料。")
    raise RuntimeError("本轮模型请求达到上限，请将任务拆开后重试。")
