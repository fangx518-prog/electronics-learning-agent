"""本地教学与练习逻辑。评分使用固定答案，不调用模型。"""
import json
from copy import deepcopy

from rc_reference import REFERENCES


TOPICS = {
    "cutoff": {
        "title": "截止频率与单位",
        "goal": "能统一单位，计算截止频率，并判断 R、C 改变后的趋势。",
        "body": "理想一阶 RC 的截止频率为 fc = 1/(2πRC)。公式中 R 使用 Ω，C 使用 F，结果为 Hz。"
                "1 kΩ = 1000 Ω，100 nF = 100×10⁻⁹ F。固定电容时，电阻翻倍，截止频率减半；固定电阻时，电容翻倍也会使截止频率减半。",
        "example": "R=1 kΩ、C=100 nF 时，fc≈1591.55 Hz。把 R 改成2 kΩ且 C 不变，fc≈795.77 Hz。",
        "pitfall": "不要把 nF 数值直接当作 F 代入。反求 R 或 C 时，还需要知道另一个元件值。",
        "sources": ["K1"],
    },
    "wiring": {
        "title": "低通、高通与直流",
        "goal": "能根据输出位置区分一阶 RC 低通和高通。",
        "body": "在串联 RC 电路中，相对于输入信号的参考地，从电容两端取输出可形成低通；"
                "从电阻两端取输出可形成高通。理想低通可传递直流，高通阻断稳态直流。",
        "example": "低通的常见连接是：输入接电阻，电阻另一端连接电容上端，电容下端接参考地；输出取电阻与电容的连接点，相对于参考地测量。",
        "pitfall": "不能只交换软件中的低通、高通标签，实际输出位置也要对应。这里讨论理想电路，忽略后级负载。",
        "sources": ["K2", "K6"],
    },
    "gain": {
        "title": "截止点增益与幅频曲线",
        "goal": "区分幅值比、分贝和功率，理解一阶低通的渐近滚降。",
        "body": "在截止频率处，理想一阶 RC 低通、高通的电压幅值比均为 1/√2≈0.707。"
                "用 20log10(|Vout/Vin|) 换算约为 −3.01 dB。一阶低通远高于截止频率时，渐近滚降约为每十倍频 −20 dB。",
        "example": "若输入、输出均使用峰峰值描述，输入为2 Vpp，截止点的理想输出约为1.414 Vpp。",
        "pitfall": "−3 dB 不等于电压幅值减半。半功率对应的阻抗条件也需要明确，不应把电压幅值比与功率比混用。",
        "sources": ["K3", "K7"],
    },
    "measurement": {
        "title": "实验测量与误差",
        "goal": "能安排验证步骤，辨别理论计算、建议步骤和实际测量。",
        "body": "保持输入幅值稳定，改变输入频率，记录输入和输出的同一种幅值，例如都采用峰峰值。"
                "计算幅值比，观察接近0.707的位置，并在附近加密测量。元件容差、接线、仪器和负载都可能使结果偏离理想模型。",
        "example": "可在0.1fc、fc、10fc附近开始扫频。记录原始数据后，再与理论幅频曲线比较；这些频率只是建议测点。",
        "pitfall": "软件计算出的曲线不是实测曲线。没有测量的数据应标记为待测，不能填写成已完成的实验结果。",
        "sources": ["K4", "K5", "K8"],
    },
}


def question(qid, topic, stem, options, correct, explanation, sources):
    return {"id": qid, "topic": topic, "stem": stem, "options": options,
            "correct": correct, "explanation": explanation, "sources": sources}


QUESTIONS = [
    question("RC01", "cutoff", "计算公式 fc=1/(2πRC) 中，100 nF 应写成多少 F？",
             ["100 F", "1×10⁻⁷ F", "1×10⁻⁴ F", "1×10⁷ F"], 1,
             "n 表示10⁻⁹，因此100 nF=100×10⁻⁹ F=10⁻⁷ F。", ["K1"]),
    question("RC02", "cutoff", "电容保持不变，电阻变成原来的2倍，截止频率怎样变化？",
             ["变成2倍", "不变", "变成原来的1/2", "变成原来的4倍"], 2,
             "fc 与 R 成反比。R 翻倍，RC 翻倍，fc 减半。", ["K1"]),
    question("RC03", "cutoff", "R=1 kΩ、C=100 nF 时，理想截止频率最接近哪一项？",
             ["1591.55 Hz", "15.92 Hz", "159.15 kHz", "100 Hz"], 0,
             "统一单位后，RC=1000×100×10⁻⁹=10⁻⁴ s，fc=1/(2π×10⁻⁴)≈1591.55 Hz。", ["K1"]),
    question("RC04", "wiring", "理想串联 RC 电路要形成低通，输出应取在哪里？",
             ["只取电阻两端", "只取输入端", "电源两端", "电容两端"], 3,
             "串联 RC 在电容两端取输出形成低通，在电阻两端取输出形成高通。", ["K2"]),
    question("RC05", "wiring", "理想串联 RC 电路在电阻两端取输出，对应哪种滤波器？",
             ["低通", "高通", "带通", "无法判断任何性质"], 1,
             "本题限定理想串联 RC、输入跨整个串联支路，在电阻两端取输出形成一阶高通。", ["K2"]),
    question("RC06", "wiring", "关于理想 RC 电路的稳态直流响应，哪项正确？",
             ["高通、低通都阻断直流", "高通、低通都放大直流", "低通可传递直流，高通阻断稳态直流", "高通传递直流，低通阻断直流"], 2,
             "理想低通的直流增益为1；理想高通的稳态直流增益为0。", ["K6"]),
    question("RC07", "gain", "一阶 RC 滤波器在截止频率处，电压幅值比约为多少？",
             ["0.5", "1", "2", "0.707"], 3,
             "截止点电压幅值比为1/√2≈0.707，约为−3.01 dB，而不是幅值减半。", ["K3"]),
    question("RC08", "gain", "输入2 Vpp，在理想截止频率处，输出最接近多少 Vpp？",
             ["1.414 Vpp", "0.5 Vpp", "2.828 Vpp", "2 Vpp"], 0,
             "输入输出采用相同的幅值定义，输出≈2×0.707=1.414 Vpp。", ["K3"]),
    question("RC09", "gain", "一阶低通在远高于截止频率的区域，渐近滚降约为多少？",
             ["每十倍频−3 dB", "每十倍频−20 dB", "每十倍频+20 dB", "所有频率都−20 dB"], 1,
             "一阶低通在高频端的渐近滚降为每十倍频−20 dB；不是所有频率点都固定衰减20 dB。", ["K7"]),
    question("RC10", "measurement", "实验报告没有实际测量数据时，应该怎样处理？",
             ["直接把理论值写成实测值", "让模型补齐合理数据", "保留待测标记，明确区分理论与实测", "删除实验条件后填写猜测值"], 2,
             "理论结果可作为比较基准，实际数据必须通过测量记录，不能把生成或计算的数据冒充实测。", ["K8"]),
    question("RC11", "measurement", "下列哪项可能使实测响应偏离本程序的理想 RC 模型？",
             ["元件容差与后级负载", "仅修改网页标题", "更改报告文件名", "把文字字号调大"], 0,
             "元件实际值改变RC乘积，后级负载也会影响响应；本程序的理论模型忽略负载和元件误差。", ["K4", "K5"]),
    question("RC12", "measurement", "计算实验幅值比 Vout/Vin 时，哪种做法合适？",
             ["输入用峰峰值、输出用有效值，直接相除", "只测输出，不测输入", "输入幅值随意变化但不记录", "输入输出均用峰峰值，并记录对应频率"], 3,
             "应统一幅值定义并记录对应频率，避免把峰值、峰峰值、有效值混用。", ["K8"]),
]

from dc_learning import TOPICS as DC_TOPICS, QUESTIONS as DC_QUESTIONS
from dc_reference import REFERENCES as DC_REFERENCES
from logic_learning import TOPICS as LOGIC_TOPICS, QUESTIONS as LOGIC_QUESTIONS
from logic_reference import REFERENCES as LOGIC_REFERENCES

from sampling_learning import TOPICS as SAMPLING_TOPICS, QUESTIONS as SAMPLING_QUESTIONS
from sampling_reference import REFERENCES as SAMPLING_REFERENCES

TOPICS.update(SAMPLING_TOPICS)
TOPICS.update(DC_TOPICS)
TOPICS.update(LOGIC_TOPICS)
QUESTIONS.extend(DC_QUESTIONS)
QUESTIONS.extend(LOGIC_QUESTIONS)
QUESTIONS.extend(SAMPLING_QUESTIONS)
QUESTION_MAP = {item["id"]: item for item in QUESTIONS}
SOURCE_MAP = {item["id"]: item for item in REFERENCES + DC_REFERENCES + LOGIC_REFERENCES + SAMPLING_REFERENCES}


def new_progress():
    return {"version": 1, "answers": {}}


def validate_progress(data):
    if not isinstance(data, dict) or set(data) != {"version", "answers"} or type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("不是本版本的学习记录。")
    answers = data["answers"]
    if not isinstance(answers, dict) or len(answers) > len(QUESTIONS):
        raise ValueError("学习记录格式无效。")
    for qid, choices in answers.items():
        if qid not in QUESTION_MAP or not isinstance(choices, list) or not 1 <= len(choices) <= 100:
            raise ValueError("学习记录包含未知题目或无效答题次数。")
        if any(type(value) is not int or not 0 <= value < len(QUESTION_MAP[qid]["options"]) for value in choices):
            raise ValueError("学习记录包含无效选项。")
    return deepcopy(data)


def record_answer(progress, qid, selected):
    result = validate_progress(progress)
    if qid not in QUESTION_MAP or type(selected) is not int or not 0 <= selected < len(QUESTION_MAP[qid]["options"]):
        raise ValueError("请选择本题的有效选项。")
    choices = result["answers"].setdefault(qid, [])
    if len(choices) >= 100:
        raise ValueError("本题已保存100次作答，请先导出记录，或重新开始一份练习记录。")
    choices.append(selected)
    return result, selected == QUESTION_MAP[qid]["correct"]


def wrong_ids(progress):
    data = validate_progress(progress)
    return [qid for qid, choices in data["answers"].items() if choices[-1] != QUESTION_MAP[qid]["correct"]]


def summary(progress):
    data = validate_progress(progress)
    answers = data["answers"]
    wrong = len(wrong_ids(data))
    return {"answered": len(answers), "first_correct": sum(choices[0] == QUESTION_MAP[qid]["correct"] for qid, choices in answers.items()),
            "latest_correct": len(answers) - wrong, "wrong": wrong,
            "attempts": sum(len(choices) for choices in answers.values())}


def export_progress(progress):
    return json.dumps(validate_progress(progress), ensure_ascii=False, indent=2).encode("utf-8")


def import_progress(raw):
    if not isinstance(raw, bytes) or len(raw) > 100_000:
        raise ValueError("请选择小于100KB的本应用学习记录。")
    try:
        return validate_progress(json.loads(raw.decode("utf-8-sig")))
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise ValueError("无法导入：文件格式或题目版本不匹配。") from exc


def tutor_prompt(qid, selected=None):
    item = QUESTION_MAP[qid]
    choice = item["options"][selected] if type(selected) is int and 0 <= selected < len(item["options"]) else "尚未选择"
    options = "；".join(f"{chr(65+i)}. {text}" for i, text in enumerate(item["options"]))
    domain = {"dc": "直流电阻电路", "logic": "理想二值组合逻辑", "sampling": "信号与理想基带采样"}.get(TOPICS[item["topic"]].get("domain"), "理想一阶RC电路")
    return (f"我正在学习{domain}。请先检索相关本地资料，再用分步提示讲解这道题，"
            "说明容易混淆的概念，不要编造实测数据。新的电路数值计算必须使用对应工具，不得补入未知元件值。\n"
            f"题目：{item['stem']}\n选项：{options}\n我的选择：{choice}\n"
            f"题库标准答案：{item['options'][item['correct']]}\n"
            f"讲解完成后，给我一个不含答案的相近小问题。")
