"""最多4个布尔输入的组合逻辑：解析白名单语法，不执行输入代码。"""
import ast
import itertools
import json
import re


def parse_expression(expression):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 200:
        raise ValueError("表达式须为1到200个字符。")
    text = expression.upper().replace("（", "(").replace("）", ")")
    for word, symbol in [("异或", "^"), ("与", "&"), ("或", "|"), ("非", "~")]:
        text = text.replace(word, symbol)
    for word, symbol in [("AND", "&"), ("OR", "|"), ("NOT", "~"), ("XOR", "^")]:
        text = re.sub(r"\b" + word + r"\b", symbol, text)
    text = text.replace("!", "~").strip()
    try:
        node = ast.parse(text, mode="eval").body
    except (SyntaxError, RecursionError):
        raise ValueError("表达式格式无效。请使用A～D、0/1、括号及AND/OR/NOT/XOR。") from None
    names, count = set(), 0

    def validate(item, depth=0):
        nonlocal count
        count += 1
        if count > 100 or depth > 24:
            raise ValueError("表达式过于复杂，请拆成较短的问题。")
        if isinstance(item, ast.Name) and item.id in {"A", "B", "C", "D"}:
            names.add(item.id)
        elif isinstance(item, ast.Constant) and type(item.value) is int and item.value in (0, 1):
            pass
        elif isinstance(item, ast.BinOp) and isinstance(item.op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
            validate(item.left, depth + 1)
            validate(item.right, depth + 1)
        elif isinstance(item, ast.UnaryOp) and isinstance(item.op, ast.Invert):
            validate(item.operand, depth + 1)
        else:
            raise ValueError("仅支持A～D、0/1、括号和与/或/非/异或；不支持算术、函数或其他语法。")
    validate(node)
    return node, sorted(names), ast.unparse(node)


def evaluate_node(node, values):
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp):
        return 1 - evaluate_node(node.operand, values)
    left, right = evaluate_node(node.left, values), evaluate_node(node.right, values)
    if isinstance(node.op, ast.BitAnd):
        return left & right
    if isinstance(node.op, ast.BitOr):
        return left | right
    return left ^ right


ASSUMPTION = "理想二值组合逻辑；0/1是逻辑值，不代表特定电压；未验证芯片电气特性或时序。"


def truth_table(expression):
    node, names, normalized = parse_expression(expression)
    rows = []
    for combination in itertools.product((0, 1), repeat=len(names)):
        values = dict(zip(names, combination))
        rows.append({**values, "Y": evaluate_node(node, values)})
    return {"kind": "table", "expression": expression, "normalized": normalized, "variables": names,
            "rows": rows, "assumption": ASSUMPTION}


def evaluate_logic(expression, values):
    node, names, normalized = parse_expression(expression)
    if not isinstance(values, dict) or set(values) != set(names):
        raise ValueError("请提供且仅提供表达式中每个变量的0/1值，不得补入缺失输入。")
    if any(type(value) is not int or value not in (0, 1) for value in values.values()):
        raise ValueError("变量值只能是整数0或1。")
    return {"kind": "evaluation", "expression": expression, "normalized": normalized,
            "variables": names, "values": dict(values), "output": evaluate_node(node, values), "assumption": ASSUMPTION}


def compare_logic(expression_a, expression_b):
    first, first_names, _ = parse_expression(expression_a)
    second, second_names, _ = parse_expression(expression_b)
    names = sorted(set(first_names) | set(second_names))
    rows = []
    for combination in itertools.product((0, 1), repeat=len(names)):
        values = dict(zip(names, combination))
        rows.append({**values, "F": evaluate_node(first, values), "G": evaluate_node(second, values)})
    counterexample = next((row for row in rows if row["F"] != row["G"]), None)
    return {"kind": "comparison", "expression_a": expression_a, "expression_b": expression_b,
            "variables": names, "equivalent": counterexample is None, "counterexample": counterexample,
            "rows": rows, "assumption": ASSUMPTION}


FUNCTIONS = {"truth_table": (truth_table, {"expression"}),
             "evaluate_logic": (evaluate_logic, {"expression", "values"}),
             "compare_logic": (compare_logic, {"expression_a", "expression_b"})}
TOOLS = []
for name, description, properties in [
    ("truth_table", "列出组合逻辑表达式的完整真值表，最多A～D四个变量。", {"expression": {"type": "string"}}),
    ("evaluate_logic", "已知所有变量的0/1值，计算一次组合逻辑输出。缺少输入应先追问。",
     {"expression": {"type": "string"}, "values": {"type": "object", "properties": {key: {"type": "integer", "enum": [0, 1]} for key in "ABCD"}, "additionalProperties": False}}),
    ("compare_logic", "枚举所有输入判断两个表达式是否逻辑等价，不等价时返回反例。",
     {"expression_a": {"type": "string"}, "expression_b": {"type": "string"}}),
]:
    TOOLS.append({"type": "function", "function": {"name": name, "description": description,
                 "parameters": {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}}})


def execute_tool(name, arguments):
    if name not in FUNCTIONS:
        return {"ok": False, "error": "不支持此工具。"}
    try:
        values = json.loads(arguments)
        function, expected = FUNCTIONS[name]
        if not isinstance(values, dict) or set(values) != expected:
            raise ValueError("工具参数不完整或包含额外字段。")
        return {"ok": True, "result": function(**values)}
    except (ValueError, TypeError, RecursionError) as exc:
        return {"ok": False, "error": str(exc) if isinstance(exc, ValueError) else "表达式或参数格式无效。"}


def result_text(data):
    if data["kind"] == "evaluation":
        return f"表达式 {data['expression']}；输入 {data['values']}；输出 Y={data['output']}。"
    if data["kind"] == "comparison":
        return (f"比较 {data['expression_a']} 与 {data['expression_b']}："
                + ("所有输入下等价。" if data["equivalent"] else f"不等价，反例：{data['counterexample']}。"))
    return f"表达式 {data['expression']}；变量 {', '.join(data['variables']) or '无（常量）'}；完整真值表共{len(data['rows'])}行。"
