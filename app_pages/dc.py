from pathlib import Path

import streamlit as st
from dotenv import dotenv_values
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from dc_agent import SYSTEM_PROMPT, run_turn
from dc_core import calculate_ohm_law, calculate_dc_power, calculate_voltage_divider, result_text
from dc_reference import build_report

st.session_state.setdefault("dc_history", [{"role": "system", "content": SYSTEM_PROMPT}])
st.session_state.setdefault("dc_display", [])
st.session_state.setdefault("dc_turns", 0)


def render_calculation(data):
    with st.container(border=True):
        st.write(result_text(data))
        st.caption(data["assumption"])
        if data.get("note"):
            st.caption(data["note"])


def render_extra(item, identity):
    for data in item.get("calculations", []):
        render_calculation(data)
    sources = item.get("sources", [])
    if sources:
        with st.expander("本轮直流参考资料", expanded=True):
            st.caption("本地整理笔记，非实时联网检索。")
            for source in sources:
                st.markdown(f"[{source['id']}] [{source['title']}]({source['url']})")
                st.write(source["summary"])
    if not item.get("error"):
        report = build_report(item["question"], item["content"], item.get("calculations", []), sources)
        st.download_button("下载本轮直流学习记录", data=report.encode("utf-8"), file_name=f"dc_report_{identity}.md",
                           mime="text/markdown", key=f"dc_report_{identity}", on_click="ignore")


st.title("直流电路助手")
st.caption("欧姆定律 · 电阻分压及负载 · 理论耗散功率")
with st.sidebar:
    st.subheader("对话管理")
    if st.button("新对话", key="dc_reset", icon=":material/add:", width="stretch"):
        st.session_state.dc_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.dc_display = []
        st.session_state.dc_turns = 0
        st.session_state.pop("study_pending_dc_prompt", None)
        st.rerun()
    st.caption(f"本次对话已完成 {st.session_state.dc_turns} / 20 轮。新对话会清空聊天参数。")
    st.divider()
    st.caption("内置4条直流参考笔记，覆盖欧姆定律、分压、负载与功率。")

with st.sidebar:
    st.subheader("手动计算")
    st.caption("这里的参数用于独立核对；与助手对话时，请在消息中提供参数。本页与RC助手分别保存对话参数。")
    manual_mode = st.selectbox("计算类型", ["欧姆定律", "直流功率", "电阻分压"], key="dc_manual_mode", persist_state="session")
    if manual_mode == "电阻分压":
        st.caption("接线：输入 → 上臂R1 → 输出 → 下臂R2 → 参考地。RL接在输出与参考地之间。")
        with st.form("dc_divider_form"):
            vin = st.number_input("输入电压（V）", min_value=0.0, value=5.0, key="dc_manual_vin", persist_state="session")
            top = st.number_input("上臂R1（Ω）", min_value=0.001, value=10000.0, key="dc_manual_top", persist_state="session")
            bottom = st.number_input("下臂R2（Ω）", min_value=0.001, value=10000.0, key="dc_manual_bottom", persist_state="session")
            with_load = st.checkbox("接入电阻负载RL", key="dc_manual_with_load", persist_state="session")
            load = st.number_input("负载RL（Ω，仅勾选接入时生效）", min_value=0.001, value=10000.0, key="dc_manual_load", persist_state="session")
            calculate = st.form_submit_button("计算分压", key="dc_manual_submit")
        if calculate:
            try:
                st.session_state.dc_manual = calculate_voltage_divider(vin, top, bottom, load if with_load else None)
            except ValueError as exc:
                st.error(str(exc))
    else:
        pair = st.selectbox("已知哪两个量", ["电压与电阻", "电流与电阻", "电压与电流"], key="dc_manual_pair", persist_state="session")
        with st.form("dc_resistor_form"):
            voltage = st.number_input("电压（V，仅已知电压时使用）", min_value=0.0, value=5.0, key="dc_manual_voltage", persist_state="session")
            current_ma = st.number_input("电流（mA，仅已知电流时使用）", min_value=0.0, value=5.0, key="dc_manual_current_ma", persist_state="session")
            resistance = st.number_input("电阻（Ω，仅已知电阻时使用）", min_value=0.001, value=1000.0, key="dc_manual_resistance", persist_state="session")
            calculate = st.form_submit_button("计算", key="dc_manual_submit")
        if calculate:
            params = {"voltage_v": voltage if pair != "电流与电阻" else None,
                      "current_a": current_ma / 1000 if pair != "电压与电阻" else None,
                      "resistance_ohm": resistance if pair != "电压与电流" else None}
            try:
                function = calculate_dc_power if manual_mode == "直流功率" else calculate_ohm_law
                st.session_state.dc_manual = function(**params)
            except ValueError as exc:
                st.error(str(exc))
    if "dc_manual" in st.session_state:
        st.caption("最近一次成功的手动计算结果，参数见下方；修改输入后需重新点击计算。")
        render_calculation(st.session_state.dc_manual)
    st.caption("仅支持非负直流量和正电阻；理论计算尚未验证器件温升或完成额定功率选型。")

try:
    secret_key = st.secrets.get("DEEPSEEK_API_KEY", "")
except FileNotFoundError:
    secret_key = ""
local_key = dotenv_values(Path(__file__).resolve().parents[1] / ".env").get("DEEPSEEK_API_KEY", "")
api_key = str(secret_key or local_key or "").strip()
ready = bool(api_key) and "*" not in api_key
if not ready:
    st.warning("聊天讲解需要在项目根目录的.env中设置完整密钥。手动计算仍可使用。")
for index, item in enumerate(st.session_state.dc_display):
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
if not st.session_state.dc_display:
    st.info("例如：5V加在1kΩ的理想电阻两端，求电流。也可以询问空载分压或电阻耗散功率。")
limit = st.session_state.dc_turns >= 20
if limit:
    st.info("已达到20轮，请新建直流对话。")
question = st.chat_input("输入直流电路问题，请提供已知量和单位", disabled=not ready or limit,
                         max_chars=2000, key="dc_question", submit_mode="disable")
learning = st.session_state.get("study_pending_dc_prompt")
if learning:
    with st.container(border=True):
        st.write(learning)
        if st.button("发送给直流助手讲解", key="dc_study_send", disabled=not ready or limit, type="primary"):
            question = learning
            st.session_state.pop("study_pending_dc_prompt", None)
        if st.button("取消本次学习提问", key="dc_study_cancel"):
            st.session_state.pop("study_pending_dc_prompt", None)
            st.rerun()
if question and question.strip() and ready and not limit:
    question = question.strip()
    st.session_state.dc_display.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    events, calculations, sources = [], [], {}
    error, answer = None, None
    with st.chat_message("assistant"):
        with st.status("正在处理直流问题…", expanded=True) as status:
            def show_event(text):
                events.append(text)
                st.code(text, language="text")
            try:
                with OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=45, max_retries=0) as client:
                    answer, history = run_turn(client, st.session_state.dc_history, question, emit=show_event,
                                               on_result=calculations.append,
                                               on_sources=lambda entries: sources.update({entry["id"]: entry for entry in entries}))
                st.session_state.dc_history = history
                st.session_state.dc_turns += 1
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
            render_extra(item, len(st.session_state.dc_display))
        st.session_state.dc_display.append(item)
