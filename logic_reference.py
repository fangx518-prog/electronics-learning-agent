"""基本组合逻辑笔记；公式性质由真值表核对。"""
REFERENCES = [
    {"id": "K13", "title": "与门AND", "tags": ["与门", "and", "与非", "真值表", "等价"],
     "summary": "二输入与门仅在两个输入均为1时输出1。理想模型记为A AND B。真值表按所有二值输入逐行求值；逻辑等价可通过相同输入下逐行比较输出核对。",
     "url": "https://www.ti.com/lit/ds/symlink/sn74hc08.pdf", "source": "Texas Instruments · SN74HC08", "section": "Description / Device Functional Modes"},
    {"id": "K14", "title": "或门OR", "tags": ["或门", "or", "或非", "真值表", "等价"],
     "summary": "二输入或门只要至少一个输入为1就输出1，包括两个输入都为1的情况。",
     "url": "https://www.ti.com/lit/ds/symlink/sn74hc32.pdf", "source": "Texas Instruments · SN74HC32", "section": "Description / Device Functional Modes"},
    {"id": "K15", "title": "非门NOT", "tags": ["非门", "not", "取反", "与非", "或非", "等价"],
     "summary": "非门将0变为1、将1变为0。NOT(A AND B)表示先求与再取反。表达式的括号决定运算分组。",
     "url": "https://www.ti.com/lit/ds/symlink/sn74hc04.pdf", "source": "Texas Instruments · SN74HC04", "section": "Description / Device Functional Modes"},
    {"id": "K16", "title": "二输入异或XOR", "tags": ["异或", "xor", "相同", "不同"],
     "summary": "二输入异或在输入不同时输出1，相同时输出0；因此1 XOR 1为0，区别于OR。",
     "url": "https://www.ti.com/lit/ds/symlink/sn74hc86.pdf", "source": "Texas Instruments · SN74HC86", "section": "Description / Device Functional Modes"},
]


def outside_scope(query):
    return any(word in query.lower() for word in ("天线", "wifi", "射频", "stm32", "电阻", "电容", "截止频率", "功率", "触发器", "时序", "verilog", "fpga", "电压阈值", "引脚"))


def search_references(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("请提供1到2000字的具体问题。")
    if outside_scope(query):
        return {"found": False, "entries": [], "coverage": "仅支持理想二值组合逻辑。"}
    text = query.lower()
    ranked = [(sum(tag in text for tag in item["tags"]), item) for item in REFERENCES]
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    entries = [{key: value for key, value in item.items() if key != "tags"} for score, item in ranked[:4] if score]
    return {"found": bool(entries), "entries": entries, "coverage": "本地整理笔记，非实时联网检索。"}


def build_report(question, answer, calculations, sources):
    from logic_core import result_text
    lines = ["# 数字逻辑学习与计算记录", "", "理想二值组合逻辑，不代表硬件测量或芯片电气验证。", "",
             "## 问题", "", question, "", "## 助手说明", "", answer, "", "## 本轮工具结果", ""]
    if not calculations:
        lines += ["本轮没有新的计算结果，未沿用其他轮次数据。", ""]
    for data in calculations:
        lines += [result_text(data), "", data["assumption"], ""]
        if data.get("rows"):
            columns = list(data["rows"][0])
            lines += ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
            lines.extend("| " + " | ".join(str(row[key]) for key in columns) + " |" for row in data["rows"])
            lines.append("")
    lines += ["## 本轮资料依据", ""]
    for item in sources:
        lines.append(f"- [{item['id']}] [{item['title']}]({item['url']}) · {item['section']}")
    if not sources:
        lines.append("本轮没有可展示的检索条目。")
    return "\n".join(lines)
