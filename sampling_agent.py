"""信号与采样助手独立上下文与受限工具执行。"""
import json
import re

from sampling_core import TOOLS as CALC_TOOLS, execute_tool as execute_calc, result_text
from sampling_reference import outside_scope, search_references

SYSTEM_PROMPT = """你是中文信号与采样学习助手，支持无直流偏置纯正弦、理想基带均匀采样条件与单频混叠。
新的数值计算必须调用analyze_sine、check_sampling或analyze_alias，不得口算替代工具。
analyze_sine需要频率Hz和明确的峰值V；用户仅说幅值时先确认峰值/峰峰值/RMS，不能擅自将它当峰值。
check_sampling需要基带信号最高频率Hz和采样率Sa/s。analyze_alias需要单频频率Hz和采样率Sa/s。
缺少参数或单位时先追问，不能用其他页面或手动计算的参数补齐。本页本次聊天已确认的参数可在后续沿用。
fs=2*fmax是临界边界，不保证恢复；fs>2*fmax也仅满足此处理想基带条件，不保证实际ADC系统性能。
正弦RMS=峰值/√2仅适用于无直流偏置纯正弦完整周期，不用于方波、直流偏置或短采样统计。
混叠频率大小落在0到fs/2；它不唯一确定原始频率。正弦图示会用有符号等效频率保留相位反转。
网页图由程序生成，图示初相为0；混叠图统一单位幅值，不代表用户真实幅值。没有进行硬件采样、仿真或联网搜索。
解释概念、学习题、抗混叠原因时先检索search_sampling_references，只引用本轮返回的[K17]等编号，不能编造来源。
仅支持入门内容，不提供带通欠采样设计、FFT实现、实际ADC选型、噪声/抖动性能、任意波形RMS或硬件接线指导。
回答尽量简短，以结论、必要步骤、适用条件为主；学习题给分步提示，判分由本地题库完成。
同一轮内不要重复调用相同工具和相同参数。已取得所需计算与依据后，直接给出最终回答；修改采样率时沿用本页聊天已确认的输入频率，重新计算一次即可。
"""

TOOLS = list(CALC_TOOLS) + [{"type": "function", "function": {
    "name": "search_sampling_references", "description": "检索本地正弦、RMS、基带采样与混叠笔记。",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                   "required": ["query"], "additionalProperties": False}}}]


def execute_tool(name, arguments):
    if name != "search_sampling_references":
        return execute_calc(name, arguments)
    try:
        params = json.loads(arguments)
        if not isinstance(params, dict) or set(params) != {"query"}:
            raise ValueError("检索参数无效。")
        return {"ok": True, "result": search_references(**params)}
    except (TypeError, ValueError, RecursionError):
        return {"ok": False, "error": "检索参数无效，请提供1到2000字的具体问题。"}


def run_turn(client, history, question, emit=print, on_result=None, on_sources=None):
    messages = list(history) + [{"role": "user", "content": question}]
    if outside_scope(question):
        answer = "这个问题超出当前信号与采样助手的范围。这里支持纯正弦参数、基带采样条件与单频混叠；其他电路问题请切换相应页面。"
        emit("范围检查：未调用模型。")
        return answer, messages + [{"role": "assistant", "content": answer}]
    sources = set()
    calculations = []
    tool_count = 0
    repair = None
    repaired = False
    calculation_repaired = False
    recalculation_requested = bool(re.search(r"重新计算|重算|再算", question)) and any(
        isinstance(item, dict) and item.get("role") == "tool" for item in history)
    successful_tools = {}
    finalize = False

    def finish(answer):
        return answer, messages + [{"role": "assistant", "content": answer}]

    def fallback(reason):
        if calculations:
            reason += "\n\n仅保留本轮工具核实的理论结果：\n" + "\n".join(result_text(data) for data in calculations)
        return finish(reason)

    for index in range(6):
        request = list(messages)
        if repair:
            # Record this correction once, before its subsequent tool responses.
            # Re-appending it after each response hides the latest tool result.
            messages.append({"role": "user", "content": repair})
            request.append({"role": "user", "content": repair})
            repair = None
        final_request = finalize or tool_count >= 6 or index == 5
        options = {}
        if final_request:
            request.append({"role": "system", "content":
                            "本轮工具阶段结束，请直接回答原问题，不再调用工具。只使用已核实结果和本轮已检索依据；条件不足则追问，不能编造数值或来源。"})
            options["tool_choice"] = "none"
        response = client.chat.completions.create(model="deepseek-flash", messages=request, tools=TOOLS, **options,
                                                 max_tokens=1400, extra_body={"thinking": {"type": "disabled"}})
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError("回答达到长度上限，请拆分问题。")
        message = choice.message
        if not message.tool_calls:
            answer = (message.content or "").strip()
            if not answer:
                raise RuntimeError("模型未返回正文，请稍后重试。")
            if recalculation_requested and not calculations:
                if calculation_repaired or final_request:
                    return fallback("本轮未取得新的计算结果，不能把历史答案作为重新计算结果。请明确输入频率、采样率等条件后重试。")
                calculation_repaired = True
                emit("本轮要求重新计算，正在补充计算工具核对。")
                repair = ("原问题明确要求重新计算，请基于本页聊天已确认的参数和本轮修改值调用相应计算工具。"
                          "不能只复述历史结果；参数缺失或有歧义时明确追问，不得补造条件。")
                continue
            cited = set(re.findall(r"\[(K\d+)\]", answer))
            if cited - sources:
                if repaired or final_request:
                    emit("引用核验未通过，已隐藏未经核实的解释。")
                    return fallback("本轮解释的引用未通过核验，现有资料不足以提供可靠说明。")
                emit("引用核验：正在自动纠正一次。")
                repaired = True
                repair = (f"请重新回答原问题，只能引用本轮已检索的编号：{'、'.join(sorted(sources)) or '无'}。"
                          "先检索必要依据，无匹配则说明不足；不能只删掉引用编号后保留无依据的内容。")
                continue
            return finish(answer)
        if final_request:
            return fallback("模型未能完成最终讲解；请核对下方工具结果。需要进一步解释时可重新提问。"
                            if calculations else "模型未能完成最终讲解，本轮没有可核实的计算结果。请补充条件后重试。")
        if tool_count + len(message.tool_calls) > 6:
            return fallback("本轮工具调用达到上限，未执行超出限额的请求。请分步提问。")
        messages.append(message)
        searched = False
        for call in message.tool_calls:
            tool_count += 1
            try:
                cache_key = (call.function.name, json.dumps(json.loads(call.function.arguments), sort_keys=True, ensure_ascii=False))
            except (TypeError, ValueError, RecursionError):
                cache_key = None
            if cache_key in successful_tools:
                result = successful_tools[cache_key]
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, ensure_ascii=False, allow_nan=False)})
                emit("检测到重复工具请求，已复用本轮成功结果并转入最终回答。")
                finalize = True
                continue
            result = execute_tool(call.function.name, call.function.arguments)
            if result["ok"]:
                if cache_key is not None:
                    successful_tools[cache_key] = result
                data = result["result"]
                if call.function.name == "search_sampling_references":
                    searched = True
                    entries = data["entries"]
                    sources.update(item["id"] for item in entries)
                    emit("本地信号与采样资料：" + ("、".join(item["id"] for item in entries) or "无匹配条目"))
                    if on_sources:
                        on_sources(entries)
                else:
                    calculations.append(data)
                    emit(f"工具：{call.function.name}\n{result_text(data)}")
                    if on_result:
                        on_result(data)
            else:
                emit("工具拒绝执行：" + result["error"])
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False, allow_nan=False)})
        if searched and not sources:
            return fallback("本轮本地资料没有匹配条目，暂时无法提供有依据的解释。请补充具体的信号与采样问题。")
    return fallback("本轮讲解未能在请求限额内完成，请核对工具结果后分步提问。")
