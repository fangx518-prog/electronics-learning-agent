"""直流电路的人工整理笔记，运行时不联网。"""
REFERENCES = [
    {"id": "K9", "title": "欧姆定律与适用条件", "tags": ["欧姆", "电流", "电压", "电阻", "ohm", "v=ir"],
     "summary": "欧姆电阻满足V=IR，可由两个已知量求第三个；R使用Ω，I使用A。该关系不能直接当成所有非线性器件的固定电阻模型。",
     "url": "https://openstax.org/books/university-physics-volume-2/pages/9-4-ohms-law", "source": "OpenStax · University Physics Volume 2", "section": "9.4 Ohm's Law"},
    {"id": "K10", "title": "两个串联电阻的空载分压", "tags": ["分压", "上臂", "下臂", "空载", "divider"],
     "summary": "理想电源Vin接串联的R1和R2，R1为上臂、R2为下臂，输出跨R2且不接负载时，Vout=Vin×R2/(R1+R2)。电压均相对于同一参考地。",
     "url": "https://wiki.analog.com/university/courses/engineering_discovery/lab_13", "source": "Analog Devices · M1K Basics and Voltage/Current Dividers", "section": "Theory / Voltage divider rule"},
    {"id": "K11", "title": "电阻负载改变分压结果", "tags": ["负载", "并联", "接入", "加载", "等效", "load"],
     "summary": "输出到地的电阻负载RL与下臂R2并联，等效下臂为R2×RL/(R2+RL)。再按分压计算输出；有限正电阻负载会使正输入下的输出低于空载值。这是串并联电阻关系的推导应用。",
     "url": "https://openstax.org/books/university-physics-volume-2/pages/10-2-resistors-in-series-and-parallel", "source": "OpenStax · University Physics Volume 2", "section": "10.2 Resistors in Series and Parallel"},
    {"id": "K12", "title": "直流电阻的耗散功率", "tags": ["功率", "耗散", "瓦", "发热", "power", "p=", "额定"],
     "summary": "直流电阻的耗散功率P=VI=I²R=V²/R，单位W。本程序只计算理论耗散，不把计算值当成额定功率或实测温升。",
     "url": "https://openstax.org/books/university-physics-volume-2/pages/9-5-electrical-energy-and-power", "source": "OpenStax · University Physics Volume 2", "section": "9.5 Electrical Energy and Power"},
]


def outside_scope(query):
    text = query.lower()
    unsupported = ("天线", "wifi", "射频", "mosfet", "三极管", "二极管", "运算放大器", "555", "二阶", "巴特沃斯",
                   "交流", "阻抗", "相位", "瞬态", "截止频率", "rc滤波", "rc低通", "rc高通", "心电图诊断")
    return any(word in text for word in unsupported)


def search_references(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("请提供1到2000字的检索问题。")
    if outside_scope(query):
        return {"found": False, "entries": [], "coverage": "直流电路资料仅覆盖欧姆电阻、两电阻分压及耗散功率。"}
    text = query.lower()
    ranked = [(sum(tag in text for tag in item["tags"]), item) for item in REFERENCES]
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    entries = [{key: value for key, value in item.items() if key != "tags"} for score, item in ranked[:3] if score]
    return {"found": bool(entries), "entries": entries, "coverage": "本地整理的直流电路笔记，非实时联网检索。"}


def build_report(question, answer, calculations, sources):
    from dc_core import result_text
    lines = ["# 直流电路学习与计算记录", "", "仅包含理论计算与学习说明，未进行硬件实测。", "",
             "## 问题", "", question, "", "## 助手说明", "", answer, "", "## 本轮工具计算", ""]
    if calculations:
        for index, data in enumerate(calculations, 1):
            lines += [f"### 计算{index}", "", result_text(data), "", data["assumption"], ""]
            if data.get("note"):
                lines += [data["note"], ""]
    else:
        lines += ["本轮没有执行新的数值计算，未沿用其他轮次的结果。", ""]
    lines += ["## 本轮资料依据", ""]
    if sources:
        for item in sources:
            lines.append(f"- [{item['id']}] [{item['title']}]({item['url']}) · {item['source']} · {item['section']}")
    else:
        lines.append("本轮没有检索到可展示的资料条目。")
    lines += ["", "## 范围与限制", "", "仅支持非负直流量和有限正电阻的理想模型；不代表额定功率选型、温升验证或实际测量。"]
    return "\n".join(lines)
