"""数字逻辑助手独立上下文与受限工具执行。"""
import json
import re

from logic_core import TOOLS as CALC_TOOLS, execute_tool as execute_calc, result_text
from logic_reference import outside_scope, search_references

SYSTEM_PROMPT = """你是中文数字逻辑学习助手，仅支持理想二值组合逻辑。
变量为A～D，输入为整数0或1；支持括号及AND、OR、NOT、XOR，也支持&、|、~、!、^及中文与或非异或。
运算优先级为NOT最高，其次AND、XOR、OR。不清楚用户的运算顺序时先追问或要求括号。
求单次输出必须知道每个变量的值，缺失时追问，不能把未给出的输入当成0。
生成完整真值表不需要用户提供某一组输入，应调用truth_table。求指定输入的输出用evaluate_logic。
判断两个表达式是否等价必须调用compare_logic，核对所有输入；不等价时展示工具返回的反例。
所有新的逻辑输出、真值表和等价判断必须调用工具。仅解释概念时先查询search_logic_references。
只引用本轮检索到的资料编号，如[K13]；资料为本地笔记，不是联网搜索，不编造文档或编号。
教材中的逻辑0/1不是特定电压。当前不提供芯片引脚、阈值、传播延迟、时序或器件选型指导。
本页与RC和直流助手不共享参数。学习讲解采用分步提示，固定题目的正式判分由程序完成。
"""

TOOLS = list(CALC_TOOLS) + [{"type": "function", "function": {
    "name": "search_logic_references", "description": "检索本地与、或、非、异或笔记。",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                   "required": ["query"], "additionalProperties": False}}}]


def execute_tool(name, arguments):
    if name != "search_logic_references":
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
        answer = "这个问题超出当前数字逻辑助手的范围。这里支持基本组合逻辑、真值表和表达式等价核对；其他电路问题请切换相应页面。"
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
                if call.function.name == "search_logic_references":
                    searched = True
                    entries = data["entries"]
                    sources.update(item["id"] for item in entries)
                    emit("本地数字逻辑资料：" + ("、".join(item["id"] for item in entries) or "无匹配条目"))
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
            return fallback("本轮本地资料没有匹配条目，暂时无法提供有依据的解释。请补充具体的组合逻辑问题。")
    raise RuntimeError("本轮模型请求达到上限，请拆分问题。")
