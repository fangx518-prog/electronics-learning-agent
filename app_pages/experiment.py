"""运行：python -m streamlit run app.py

与 rc_core.py、rc_agent.py、rc_reference.py 和本地 .env 放在同一目录。
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import dotenv_values
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from rc_agent import SYSTEM_PROMPT, calculate_rc_cutoff, response_points, run_turn
from rc_reference import build_report



def render_result(data, identity):
    """只绘制计算工具返回的参数，模型文字不参与图表数值生成。"""
    st.caption(f"曲线参数：R = {data['r_ohm']:.6g} Ω，C = {data['c_nf']:.6g} nF；截止频率 {data['cutoff_hz']:.6g} Hz。")
    if data.get("note"):
        st.caption(data["note"])
    try:
        frame = pd.DataFrame(response_points(data["r_ohm"], data["c_nf"]))
        curve = alt.Chart(frame).mark_line().encode(
            x=alt.X("frequency_hz:Q", title="频率（Hz，对数刻度）", scale=alt.Scale(type="log")),
            y=alt.Y("gain_db:Q", title="电压增益（dB）"),
            color=alt.Color("filter:N", title="滤波类型"),
            tooltip=[alt.Tooltip("filter:N", title="类型"),
                     alt.Tooltip("frequency_hz:Q", title="频率 / Hz", format=".6g"),
                     alt.Tooltip("gain_db:Q", title="增益 / dB", format=".3f")],
        )
        marker = alt.Chart(pd.DataFrame({"frequency_hz": [data["cutoff_hz"]]})).mark_rule(
            color="#888888", strokeDash=[5, 5]
        ).encode(x="frequency_hz:Q")
        chart = (curve + marker).properties(height=290)
        st.altair_chart(chart, width="stretch", key=f"curve_{identity}",
                        alt="理想一阶 RC 低通和高通幅频响应；虚线为截止频率，两条曲线在此均约为负3.01分贝。")
        st.caption("理论曲线，忽略负载及元件误差；虚线标记截止频率。曲线不是实测数据。")
        st.caption("公式参考：[Analog Devices 滤波器教学实验](https://wiki.analog.com/university/courses/engineering_discovery/lab_5)")
    except ValueError:
        st.warning("当前数值范围不适合绘图，请检查参数数量级。")



def render_extras(item, identity):
    sources = item.get("sources", [])
    if sources:
        with st.expander("本轮参考资料", expanded=True):
            st.caption("本地整理笔记；可打开原始资料核对，非实时联网检索。")
            for source in sources:
                st.markdown(f"**[{source['id']}] {source['title']}** · [{source['source']}]({source['url']})")
                st.caption(f"原文位置：{source['section']}")
                st.markdown(source["summary"])
    if item.get("question") and not item.get("error"):
        report = build_report(item["question"], item["content"], item.get("result"), sources)
        st.download_button(
            "下载本轮设计与实验指导", data=report.encode("utf-8"),
            file_name=f"rc_report_{identity}.md", mime="text/markdown", key=f"report_{identity}",
            icon=":material/download:", on_click="ignore",
        )


st.session_state.setdefault("rc_history", [{"role": "system", "content": SYSTEM_PROMPT}])
st.session_state.setdefault("rc_display", [])
st.session_state.setdefault("rc_turns", 0)

st.title("RC 电路实验助手")
st.caption("一阶理想 RC 电路 · 参数设计 · 资料依据 · 实验指导")

with st.sidebar:
    st.subheader("对话管理")
    if st.button("新对话", key="rc_reset", icon=":material/add:", width="stretch"):
        st.session_state.rc_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.rc_display = []
        st.session_state.rc_turns = 0
        st.rerun()
    st.caption(f"本次对话已完成 {st.session_state.rc_turns} / 20 轮。新对话会清空聊天参数。")
    st.divider()
    st.caption("内置8条参考笔记，覆盖原理、接线、测量与误差。")
    st.subheader("手动计算")
    st.caption("这里的参数用于独立核对；与助手对话时，请在消息中提供参数。")
    resistance = st.number_input("电阻 R（Ω）", min_value=1.0, value=1000.0, key="rc_r", persist_state="session")
    capacitance = st.number_input("电容 C（nF）", min_value=0.001, value=100.0, key="rc_c", persist_state="session")
    try:
        manual = calculate_rc_cutoff(resistance, capacitance)
        st.metric("截止频率", f"{manual['cutoff_hz']:.2f} Hz")
    except ValueError as exc:
        st.error(str(exc))
    st.latex(r"f_c = \frac{1}{2\pi RC}")
    st.caption("理想元件，忽略负载影响。")

# 本地沿用已有 .env；部署时也支持 Streamlit secrets。
try:
    secret_key = st.secrets.get("DEEPSEEK_API_KEY", "")
except FileNotFoundError:
    secret_key = ""
local_key = dotenv_values(Path(__file__).resolve().parents[1] / ".env").get("DEEPSEEK_API_KEY", "")
api_key = str(secret_key or local_key or "").strip()
key_ready = bool(api_key) and "*" not in api_key

if not key_ready:
    st.warning("请在同目录的 .env 中保存完整 DEEPSEEK_API_KEY，再刷新页面。")

if not st.session_state.rc_display:
    st.info("试着输入：电阻是 1 kΩ，电容是 100 nF，请计算截止频率。")
    st.caption("也可以追问：把电阻改成 2 kΩ。也支持：截止频率要 1 kHz，已知电容 100 nF，帮我求电阻。")

for item_index, item in enumerate(st.session_state.rc_display):
    with st.chat_message(item["role"]):
        if item.get("events"):
            with st.expander("工具执行记录", expanded=False):
                st.code("\n".join(item["events"]), language="text")
        if item.get("error"):
            st.error(item["content"])
        else:
            st.markdown(item["content"])
            if item.get("result"):
                render_result(item["result"], item_index)
            render_extras(item, item_index)

at_limit = st.session_state.rc_turns >= 20
if at_limit:
    st.info("本次对话已达到 20 轮，请点击侧栏“新对话”后继续。")

question = st.chat_input(
    "输入设计需求，或询问原理、接线、测量与误差",
    key="rc_question",
    disabled=not key_ready or at_limit,
    max_chars=2000,
    submit_mode="disable",
)

learning_prompt = st.session_state.get("study_pending_prompt")
if learning_prompt:
    with st.container(border=True):
        st.markdown("**来自学习页面的问题**")
        st.write(learning_prompt)
        if st.button("发送给助手讲解", key="study_send_to_agent", disabled=not key_ready or at_limit,
                     type="primary"):
            question = learning_prompt
            st.session_state.pop("study_pending_prompt", None)
        if st.button("取消本次学习提问", key="study_cancel_to_agent"):
            st.session_state.pop("study_pending_prompt", None)
            st.rerun()

# 只有提交新消息才请求模型；调节手动计算器、页面重绘不会重复请求。
if question and question.strip() and key_ready and not at_limit:
    question = question.strip()
    st.session_state.rc_display.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    events = []
    results = []
    sources = {}
    answer = None
    error = None
    with st.chat_message("assistant"):
        with st.status("正在理解问题并处理…", expanded=True) as status:
            def show_event(text):
                events.append(text.strip())
                st.code(text.strip(), language="text")

            try:
                with OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com",
                    timeout=45.0,
                    max_retries=0,
                ) as client:
                    answer, updated = run_turn(
                        client, st.session_state.rc_history, question, emit=show_event, on_result=results.append,
                        on_sources=lambda entries: sources.update({entry["id"]: entry for entry in entries}),
                    )
                st.session_state.rc_history = updated
                st.session_state.rc_turns += 1
                status.update(label="处理完成", state="complete", expanded=False)
            except APITimeoutError:
                error = "请求超时，本轮未加入模型上下文。请稍后重新发送问题。"
            except APIConnectionError:
                error = "网络连接失败，本轮未加入模型上下文。请检查网络后重新发送。"
            except APIStatusError as exc:
                hints = {
                    401: "密钥认证失败，请检查 .env 中是否为平台生成的完整密钥。",
                    402: "API 余额不足，请在开放平台检查余额。",
                    429: "请求过于频繁，请稍后再试。",
                }
                error = f"API 错误 {exc.status_code}：{hints.get(exc.status_code, '接口返回错误，请稍后重试。')}"
            except RuntimeError as exc:
                error = str(exc)

            if error:
                status.update(label="本轮未完成", state="error", expanded=False)

        if error:
            st.error(error)
        else:
            st.markdown(answer)
            if results:
                render_result(results[-1], len(st.session_state.rc_display))
            render_extras({"question": question, "content": answer, "sources": list(sources.values()),
                           "result": results[-1] if results else None}, len(st.session_state.rc_display))

    st.session_state.rc_display.append({
        "role": "assistant",
        "content": error or answer,
        "events": events,
        "error": bool(error),
        "result": results[-1] if results and not error else None,
        "question": question,
        "sources": list(sources.values()) if not error else [],
    })
