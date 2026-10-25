"""小型本地参考资料库：关键词检索整理笔记，不在运行时联网。"""



LAB_URL = "https://wiki.analog.com/university/courses/engineering_discovery/lab_5"
GUIDE_URL = "https://www.analog.com/en/resources/technical-articles/a-beginners-guide-to-filter-topologies.html"

REFERENCES = [
    {"id": "K1", "title": "截止频率与参数反求", "tags": ["截止", "公式", "反求", "频率", "cutoff", "fc"],
     "summary": "理想一阶 RC 电路的截止频率为 fc=1/(2πRC)，R 用 Ω、C 用 F。反求元件时必须另有一个已知元件值。",
     "url": LAB_URL, "source": "Analog Devices：An Introduction to Electrical Filters", "section": "Theory"},
    {"id": "K2", "title": "低通与高通的输出位置", "tags": ["接线", "连接", "低通", "高通", "输出", "lowpass", "highpass"],
     "summary": "串联 RC 电路在电容两端取输出形成低通，在电阻两端取输出形成高通。二者输出端不能混用。",
     "url": LAB_URL, "source": "Analog Devices：An Introduction to Electrical Filters", "section": "Theory"},
    {"id": "K3", "title": "截止点增益", "tags": ["3db", "3 db", "分贝", "增益", "0.707", "70.7", "半功率", "幅值"],
     "summary": "截止点电压幅值比为 1/√2，约 0.707，对应约 -3.01 dB；幅值下降与功率下降不能混淆。",
     "url": LAB_URL, "source": "Analog Devices：An Introduction to Electrical Filters", "section": "Theory"},
    {"id": "K4", "title": "元件误差的影响", "tags": ["误差", "容差", "偏差", "不一致", "偏移", "tolerance"],
     "summary": "元件实际阻值与容值的偏差会改变截止频率。理论设计值应与实际元件值区分。",
     "url": GUIDE_URL, "source": "Analog Devices：A Beginner's Guide to Filter Topologies", "section": "Passive filter limitations"},
    {"id": "K5", "title": "负载对被动滤波器的影响", "tags": ["负载", "输入阻抗", "输出阻抗", "缓冲", "阻抗", "load"],
     "summary": "后级负载会影响被动滤波器的响应；本程序忽略负载。需要增益、缓冲或更陡滚降时，须另行设计适当电路。",
     "url": GUIDE_URL, "source": "Analog Devices：A Beginner's Guide to Filter Topologies", "section": "Passive filter limitations"},
    {"id": "K6", "title": "直流响应", "tags": ["直流", "隔直", "dc", "零频率"],
     "summary": "理想 RC 低通可以传递直流，高通阻断稳态直流。",
     "url": LAB_URL, "source": "Analog Devices：An Introduction to Electrical Filters", "section": "Observations and Conclusions"},
    {"id": "K7", "title": "一阶低通的滚降", "tags": ["滚降", "斜率", "20db", "20 db", "倍频", "十倍频", "衰减"],
     "summary": "一阶低通远高于截止频率时，幅频曲线渐近滚降约为每十倍频 -20 dB。这是渐近值。",
     "url": GUIDE_URL, "source": "Analog Devices：A Beginner's Guide to Filter Topologies", "section": "Single pole low-pass filter"},
    {"id": "K8", "title": "截止频率的实验验证", "tags": ["测量", "示波器", "信号源", "实验", "验证", "扫频", "测量步骤"],
     "summary": "改变输入频率并比较输入、输出幅值，可观察滤波响应及接近 0.707 幅值比的截止点。实验结果需实际记录。",
     "url": LAB_URL, "source": "Analog Devices：An Introduction to Electrical Filters", "section": "Procedure / Theory"},
]


def outside_scope(query):
    """仅识别当前版本明确不支持的主题，不把所有陌生问题都判为越界。"""
    query = query.lower()
    unsupported = ("555", "mosfet", "三极管", "运算放大器", "二阶", "巴特沃斯", "天线", "射频", "心电图诊断")
    if any(word in query for word in unsupported):
        return True
    # MCU 可以作为 RC 电路的应用背景；本版本不提供 MCU 自身的设计指导。
    rc_context = "rc" in query and any(word in query for word in ("一阶", "低通", "高通", "截止", "电阻", "电容"))
    return "stm32" in query and not rc_context


def search_references(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("请提供 1 到 2000 字的检索问题。")
    query = query.lower().replace("－", "-")
    if outside_scope(query):
        return {"found": False, "entries": [], "coverage": "资料库仅覆盖理想一阶 RC 基础。"}
    ranked = []
    for item in REFERENCES:
        score = sum(1 for tag in item["tags"] if tag in query)
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    entries = [{key: item[key] for key in ("id", "title", "summary", "url", "source", "section")}
               for _, item in ranked[:3]]
    return {"found": bool(entries), "entries": entries,
            "coverage": "本地整理笔记；仅覆盖理想一阶 RC 基础，非实时网页搜索。"}


def build_report(question, answer, calculation, sources):
    lines = ["# RC 电路设计与实验指导", "", "本文件包含理论计算和建议实验步骤，不代表已完成实测。", "",
             "## 用户需求", "", question, "", "## 助手说明", "", answer, "", "## 本轮计算结果", ""]
    if calculation:
        lines += [f"- 电阻：{calculation['r_ohm']:.10g} Ω", f"- 电容：{calculation['c_nf']:.10g} nF",
                  f"- 理论截止频率：{calculation['cutoff_hz']:.10g} Hz",
                  "- 模型假设：理想一阶 RC 电路，忽略负载与元件误差。"]
        if "target_hz" in calculation:
            lines.append(f"- 目标截止频率：{calculation['target_hz']:.10g} Hz；反求元件为理论值。")
        fc = calculation["cutoff_hz"]
        lines += ["", "## 建议实验步骤", "",
                  "1. 根据目标选择低通或高通接线：分别从电容或电阻两端取得输出。[K2]",
                  "2. 检查仪器连接，采用满足仪器与元件规格的小信号正弦输入。",
                  f"3. 可从 {fc * 0.1:.6g} Hz、{fc:.6g} Hz、{fc * 10:.6g} Hz 三点开始测量，并在截止点附近加密扫频。",
                  "4. 记录每个频率点的输入、输出幅值，使用相同的幅值定义，例如均用峰峰值。[K8]",
                  "5. 计算 Vout/Vin 与 20log10(Vout/Vin)，与理论曲线比较；截止点理论幅值比约为0.707。[K3]",
                  "6. 保留原始测量记录；若存在差异，逐项核对元件实际值、接线与负载。[K4][K5]",
                  "", "## 测量记录", "", "尚未录入实测数据，请自行测量填写。", "",
                  "| 频率 / Hz | 输入幅值 | 输出幅值 | 幅值比 | 增益 / dB |", "|---|---|---|---|---|"]
        for ratio in (0.1, 1, 10):
            lines.append(f"| {fc * ratio:.6g} | 待测 | 待测 | 待算 | 待算 |")
    else:
        lines.append("本轮未执行新的元件参数计算，未自动沿用其他回合的数据。")
    actual = {item["id"]: item for item in sources}
    lines += ["", "## 本轮检索到的资料", ""]
    if actual:
        for item in actual.values():
            lines.append(f"- [{item['id']}] {item['title']}；来源：[{item['source']}]({item['url']})；位置：{item['section']}。")
    else:
        lines.append("本轮未调用资料检索，未标注检索结果。")
    if calculation:
        lines += ["", "## 通用实验指导的参考资料", ""]
        for item in REFERENCES:
            if item["id"] in {"K2", "K3", "K4", "K5", "K8"}:
                lines.append(f"- [{item['id']}] {item['title']}：[原始资料]({item['url']})，{item['section']}。")
    lines += ["", "## 使用范围", "", "支持理想一阶 RC 低通、高通及元件参数反求；未进行硬件测量、数值电路仿真或标准元件选型。"]
    return "\n".join(lines) + "\n"
