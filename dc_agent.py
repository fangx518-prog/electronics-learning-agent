"""直流助手独立上下文与受限工具执行。"""
import json
import re

from dc_core import TOOLS as CALC_TOOLS, execute_tool as execute_calc, result_text
from dc_reference import outside_scope, search_references

SYSTEM_PROMPT = """你是中文直流电路学习助手，只支持理想欧姆电阻、两电阻分压和直流电阻耗散功率。
电压、电流使用非负大小，电阻必须为有限正数。先统一为V、A、Ω、W，1mA=0.001A。
新数值计算必须调用相应工具。V/I/R中仅有两个已知量时才能反求另一个；未知量传null，不得补入未知数。
分压需要输入电压、上臂和下臂电阻，输出跨下臂。若未说明负载，先确认是否按空载计算；明确空载时load_ohm传null。
接入负载时仅支持正电阻RL并联在下臂。后续追问可沿用本直流对话中已经明确的参数。
此页面不共享RC助手的参数；不得声称记得另一个页面中的电阻。单位或参数缺失时先追问。
解释原理、适用条件或接线前必须调用search_dc_references，只依据本轮返回的相关资料，引用格式如[K9]。
资料是本地整理笔记，不是实时联网搜索。没有匹配资料就说明不足，不得编造文档、编号或网址。
理论耗散功率不是额定功率选型，未验证器件温升；不要宣称硬件实测已完成。
不支持已知功率反求参数、复杂网络或其他未列出的功能。RC问题引导到“RC实验助手”。
学习讲解先给思路和单位关系，再解释题目；固定题库的正式评分由程序完成。
"""

TOOLS = list(CALC_TOOLS) + [{"type": "function", "function": {
    "name": "search_dc_references", "description": "检索本地欧姆定律、分压与负载、直流功率笔记。",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                   "required": ["query"], "additionalProperties": False}}}]


def execute_tool(name, arguments):
    if name != "search_dc_references":
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
        answer = "这个问题超出当前直流助手的范围。这里支持欧姆定律、两电阻直流分压和电阻耗散功率；RC计算请切换到RC实验助手，其他主题目前资料不足。"
        emit("范围检查：未调用模型。")
        return answer, messages + [{"role": "assistant", "content": answer}]
    sources = set()
    calculations = []
    tool_count = 0
    repair = None
    repaired = False

    def finish(answer):
        return answer, messages + [{"role": "assistant", "content": answer}]

    def fallback(reason):
        if calculations:
            reason += "\n\n仅保留本轮工具核实的理论结果：\n" + "\n".join(result_text(data) for data in calculations)
        return finish(reason)

    for index in range(6):
        request = list(messages)
        if repair:
            request.append({"role": "user", "content": repair})
            repair = None
        response = client.chat.completions.create(model="deepseek-flash", messages=request, tools=TOOLS,
                                                 max_tokens=1400, extra_body={"thinking": {"type": "disabled"}})
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError("回答达到长度上限，请拆分问题。")
        message = choice.message
        if not message.tool_calls:
            answer = (message.content or "").strip()
            if not answer:
                raise RuntimeError("模型未返回正文，请稍后重试。")
            cited = set(re.findall(r"\[(K\d+)\]", answer))
            if cited - sources:
                if repaired or index == 5:
                    emit("引用核验未通过，已隐藏未经核实的解释。")
                    return fallback("本轮解释的引用未通过核验，现有资料不足以提供可靠说明。")
                emit("引用核验：正在自动纠正一次。")
                repaired = True
                repair = (f"请重新回答原问题，只能引用本轮已检索的编号：{'、'.join(sorted(sources)) or '无'}。"
                          "先检索必要依据，无匹配则说明不足；不能只删掉引用编号后保留无依据的内容。")
                continue
            return finish(answer)
        if tool_count + len(message.tool_calls) > 6:
            raise RuntimeError("本轮工具调用达到上限，请分步提问。")
        messages.append(message)
        searched = False
        for call in message.tool_calls:
            tool_count += 1
            result = execute_tool(call.function.name, call.function.arguments)
            if result["ok"]:
                data = result["result"]
                if call.function.name == "search_dc_references":
                    searched = True
                    entries = data["entries"]
                    sources.update(item["id"] for item in entries)
                    emit("本地直流资料：" + ("、".join(item["id"] for item in entries) or "无匹配条目"))
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
            return fallback("本轮本地资料没有匹配条目，暂时无法提供有依据的解释。请补充具体的直流电阻问题。")
    raise RuntimeError("本轮模型请求达到上限，请拆分问题。")
