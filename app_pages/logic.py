from pathlib import Path

import streamlit as st
from dotenv import dotenv_values
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from logic_agent import SYSTEM_PROMPT, run_turn
from logic_core import truth_table, evaluate_logic, compare_logic, parse_expression, result_text
from logic_reference import build_report

st.session_state.setdefault("logic_history", [{"role": "system", "content": SYSTEM_PROMPT}])
st.session_state.setdefault("logic_display", [])
st.session_state.setdefault("logic_turns", 0)


def render_calculation(data):
    with st.container(border=True):
        st.write(result_text(data))
        st.caption(data["assumption"])
        if data.get("rows"):
            st.dataframe(data["rows"], hide_index=True, alt="计算工具逐行生成的组合逻辑真值表。")
        if data.get("note"):
            st.caption(data["note"])


def render_extra(item, identity):
    for data in item.get("calculations", []):
        render_calculation(data)
    sources = item.get("sources", [])
    if sources:
        with st.expander("本轮逻辑参考资料", expanded=True):
            st.caption("本地整理笔记，非实时联网检索。")
            for source in sources:
                st.markdown(f"[{source['id']}] [{source['title']}]({source['url']})")
                st.write(source["summary"])
    if not item.get("error"):
        report = build_report(item["question"], item["content"], item.get("calculations", []), sources)
        st.download_button("下载本轮数字逻辑学习记录", data=report.encode("utf-8"), file_name=f"logic_report_{identity}.md",
                           mime="text/markdown", key=f"logic_report_{identity}", on_click="ignore")


st.title("数字逻辑电路助手")
st.caption("基本逻辑门 · 布尔表达式 · 真值表与等价核对")
with st.sidebar:
    st.subheader("对话管理")
    if st.button("新对话", key="logic_reset", icon=":material/add:", width="stretch"):
        st.session_state.logic_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.logic_display = []
        st.session_state.logic_turns = 0
        st.session_state.pop("study_pending_logic_prompt", None)
        st.rerun()
    st.caption(f"本次对话已完成 {st.session_state.logic_turns} / 20 轮。新对话会清空聊天参数。")
    st.divider()
    st.caption("内置4条基本逻辑参考笔记；与RC、直流页面分别保存参数。")
    st.subheader("手动计算")
    st.caption("支持A～D、0/1、括号、AND/OR/NOT/XOR。优先级：NOT > AND > XOR > OR。")
    mode = st.selectbox("计算类型", ["真值表", "单次输出", "等价核对"], key="logic_manual_mode", persist_state="session")
    with st.form("logic_manual_form"):
        expression = st.text_input("表达式F", value="A AND B", max_chars=200, key="logic_expression", persist_state="session")
        second = None
        values = {}
        if mode == "等价核对":
            second = st.text_input("表达式G", value="B AND A", max_chars=200, key="logic_expression_g", persist_state="session")
        elif mode == "单次输出":
            st.caption("只需填写表达式中出现的变量；没有给出的输入不会默认为0。")
            for variable in "ABCD":
                values[variable] = st.selectbox(variable, [0, 1], index=None, key=f"logic_value_{variable}", persist_state="session")
        calculate = st.form_submit_button("计算", key="logic_manual_submit")
    if calculate:
        try:
            if mode == "真值表":
                result = truth_table(expression)
            elif mode == "等价核对":
                result = compare_logic(expression, second)
            else:
                _, names, _ = parse_expression(expression)
                result = evaluate_logic(expression, {key: values[key] for key in names})
            st.session_state.logic_manual = result
        except ValueError as exc:
            st.error(str(exc))
    st.caption("仅计算理想组合逻辑，不代表芯片电压、引脚或时序验证。")

if "logic_manual" in st.session_state:
    st.subheader("手动计算结果")
    st.caption("最近一次成功计算，表达式见下方；修改输入后需要重新计算。手动参数不会加入聊天。")
    render_calculation(st.session_state.logic_manual)
    manual_report = build_report("手动逻辑计算", "以下结果来自本地计算工具。", [st.session_state.logic_manual], [])
    st.download_button("下载手动计算记录", data=manual_report.encode("utf-8"), file_name="logic_manual.md",
                       key="logic_manual_export", on_click="ignore")

try:
    secret_key = st.secrets.get("DEEPSEEK_API_KEY", "")
except FileNotFoundError:
    secret_key = ""
local_key = dotenv_values(Path(__file__).resolve().parents[1] / ".env").get("DEEPSEEK_API_KEY", "")
api_key = str(secret_key or local_key or "").strip()
ready = bool(api_key) and "*" not in api_key
if not ready:
    st.warning("聊天讲解需要在项目根目录的.env中设置完整密钥。手动计算仍可使用。")
for index, item in enumerate(st.session_state.logic_display):
    with st.chat_message(item["role"]):
        if item["role"] == "user":
            st.write(item["content"])
            continue
        if item.get("events"):
            with st.expander("本轮工具记录"):
                st.code("\n".join(item["events"]), language="text")
        if item.get("error"):
            st.error(item["content"])
        else:
            st.markdown(item["content"])
            render_extra(item, index)
if not st.session_state.logic_display:
    st.info("例如：列出A XOR B的真值表；或比较NOT(A AND B)与(NOT A) OR (NOT B)是否等价。")
limit = st.session_state.logic_turns >= 20
if limit:
    st.info("已达到20轮，请新建数字逻辑对话。")
question = st.chat_input("输入逻辑表达式或学习问题；求单次输出时请给出各变量的0/1值", disabled=not ready or limit,
                         max_chars=2000, key="logic_question", submit_mode="disable")
learning = st.session_state.get("study_pending_logic_prompt")
if learning:
    with st.container(border=True):
        st.write(learning)
        if st.button("发送给数字逻辑助手讲解", key="logic_study_send", disabled=not ready or limit, type="primary"):
            question = learning
            st.session_state.pop("study_pending_logic_prompt", None)
        if st.button("取消本次学习提问", key="logic_study_cancel"):
            st.session_state.pop("study_pending_logic_prompt", None)
            st.rerun()
if question and question.strip() and ready and not limit:
    question = question.strip()
    st.session_state.logic_display.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    events, calculations, sources = [], [], {}
    error, answer = None, None
    with st.chat_message("assistant"):
        with st.status("正在处理数字逻辑问题…", expanded=True) as status:
            def show_event(text):
                events.append(text)
                st.code(text, language="text")
            try:
                with OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=45, max_retries=0) as client:
                    answer, history = run_turn(client, st.session_state.logic_history, question, emit=show_event,
                                               on_result=calculations.append,
                                               on_sources=lambda entries: sources.update({entry["id"]: entry for entry in entries}))
                st.session_state.logic_history = history
                st.session_state.logic_turns += 1
            except APITimeoutError:
                error = "请求超时，本轮未加入上下文，请稍后再试。"
            except APIConnectionError:
                error = "连接失败，本轮未加入上下文，请检查网络。"
            except APIStatusError as exc:
                hints = {401: "请检查完整密钥。", 402: "请检查API余额。", 429: "请求过于频繁，请稍后再试。"}
                error = f"API错误{exc.status_code}：{hints.get(exc.status_code, '请稍后再试。')}"
            except RuntimeError as exc:
                error = str(exc)
            status.update(label="本轮未完成" if error else "处理完成", state="error" if error else "complete", expanded=False)
        item = {"role": "assistant", "question": question, "content": error or answer, "error": bool(error),
                "events": events, "calculations": calculations if not error else [],
                "sources": list(sources.values()) if not error else []}
        if error:
            st.error(error)
        else:
            st.markdown(answer)
            render_extra(item, len(st.session_state.logic_display))
        st.session_state.logic_display.append(item)
