from pathlib import Path

import streamlit as st
import altair as alt
import pandas as pd
from dotenv import dotenv_values
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from sampling_agent import SYSTEM_PROMPT, run_turn
from sampling_core import analyze_sine, check_sampling, analyze_alias, result_text, waveform_points
from sampling_reference import build_report

st.session_state.setdefault("sampling_history", [{"role": "system", "content": SYSTEM_PROMPT}])
st.session_state.setdefault("sampling_display", [])
st.session_state.setdefault("sampling_turns", 0)


def render_calculation(data):
    with st.container(border=True):
        st.write(result_text(data))
        st.caption(data["assumption"])
        points = waveform_points(data)
        if points:
            y_title = "电压（V）" if data['kind']=='sine' else "归一化幅值"
            chart = alt.Chart(pd.DataFrame(points['lines'])).mark_line().encode(
                x=alt.X('time_s:Q',title='时间（s）'), y=alt.Y('value:Q',title=y_title),
                color=alt.Color('series:N',title='理论波形'),
                tooltip=[alt.Tooltip('time_s:Q',format='.6g'),alt.Tooltip('value:Q',format='.6g'),'series:N'])
            if points['samples']:
                dots=alt.Chart(pd.DataFrame(points['samples'])).mark_point(color='#e8a13b',filled=True,size=65).encode(x='time_s:Q',y='value:Q')
                chart=chart+dots
            st.altair_chart(chart.properties(height=280),width='stretch',alt='理论正弦波形；混叠图同时展示折叠等价波形和均匀采样点。')
            st.caption('理论示意，初相为0；混叠图统一单位幅值，橙色点为理论采样点。不是实际采样数据。')
        elif data['kind']=='alias':
            st.info('当前频率比不适合在有限窗口清晰画图，仅展示数值结果；可用5kHz与8kSa/s查看示意。')
        if data.get("note"):
            st.caption(data["note"])


def render_extra(item, identity):
    for data in item.get("calculations", []):
        render_calculation(data)
    sources = item.get("sources", [])
    if sources:
        with st.expander("本轮信号参考资料", expanded=True):
            st.caption("本地整理笔记，非实时联网检索。")
            for source in sources:
                st.markdown(f"[{source['id']}] [{source['title']}]({source['url']})")
                st.write(source["summary"])
    if not item.get("error"):
        report = build_report(item["question"], item["content"], item.get("calculations", []), sources)
        st.download_button("下载本轮信号与采样学习记录", data=report.encode("utf-8"), file_name=f"sampling_report_{identity}.md",
                           mime="text/markdown", key=f"sampling_report_{identity}", on_click="ignore")


st.title("信号与采样助手")
st.caption("正弦波 · 基带采样条件 · 单频混叠")
with st.sidebar:
    st.subheader("对话管理")
    if st.button("新对话", key="sampling_reset", icon=":material/add:", width="stretch"):
        st.session_state.sampling_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.sampling_display = []
        st.session_state.sampling_turns = 0
        st.session_state.pop("study_pending_sampling_prompt", None)
        st.rerun()
    st.caption(f"本次对话已完成 {st.session_state.sampling_turns} / 20 轮。新对话会清空聊天参数。")
    st.divider()
    st.caption("内置4条信号笔记；与其他助手分别保存聊天参数。")
    st.subheader("手动计算")
    st.caption("表单输入先点击计算提交；已提交参数在当前会话跨页保留，不加入聊天。")
    mode=st.selectbox('计算类型',['正弦参数','采样条件','单频混叠'],key='sampling_manual_mode',persist_state='session')
    with st.form('sampling_manual_form'):
        if mode=='正弦参数':
            frequency=st.number_input('正弦频率（Hz）',min_value=0.000001,max_value=1e9,value=1000.0,key='sampling_frequency',persist_state='session',format='%.6g')
            peak=st.number_input('峰值（V，无直流偏置纯正弦）',min_value=0.0,max_value=1e6,value=2.0,key='sampling_peak',persist_state='session',format='%.6g')
        elif mode=='采样条件':
            frequency=st.number_input('基带最高频率（Hz）',min_value=0.000001,max_value=1e9,value=1000.0,key='sampling_max_frequency',persist_state='session',format='%.6g')
            rate=st.number_input('采样率（Sa/s）',min_value=0.000001,max_value=1e9,value=8000.0,key='sampling_check_rate',persist_state='session',format='%.6g')
        else:
            frequency=st.number_input('单频信号频率（Hz）',min_value=0.000001,max_value=1e9,value=5000.0,key='sampling_alias_frequency',persist_state='session',format='%.6g')
            rate=st.number_input('采样率（Sa/s）',min_value=0.000001,max_value=1e9,value=8000.0,key='sampling_alias_rate',persist_state='session',format='%.6g')
        calculate=st.form_submit_button('计算',key='sampling_manual_submit')
    if calculate:
        try:
            function={'正弦参数':analyze_sine,'采样条件':check_sampling,'单频混叠':analyze_alias}[mode]
            st.session_state.sampling_manual=function(frequency,peak if mode=='正弦参数' else rate)
        except ValueError as exc:
            st.error(str(exc))
    st.caption("仅支持理想入门模型；RMS不适用于任意波形，采样条件不等同于实际ADC选型。")

if "sampling_manual" in st.session_state:
    st.subheader("手动计算结果")
    st.caption("最近一次成功计算，参数见下方；修改输入后需要重新计算。手动参数不会加入聊天。")
    render_calculation(st.session_state.sampling_manual)
    manual_report = build_report("手动信号与采样计算", "以下结果来自本地计算工具。", [st.session_state.sampling_manual], [])
    st.download_button("下载手动计算记录", data=manual_report.encode("utf-8"), file_name="sampling_manual.md",
                       key="sampling_manual_export", on_click="ignore")

try:
    secret_key = st.secrets.get("DEEPSEEK_API_KEY", "")
except FileNotFoundError:
    secret_key = ""
local_key = dotenv_values(Path(__file__).resolve().parents[1] / ".env").get("DEEPSEEK_API_KEY", "")
api_key = str(secret_key or local_key or "").strip()
ready = bool(api_key) and "*" not in api_key
if not ready:
    st.warning("聊天讲解需要在项目根目录的.env中设置完整密钥。手动计算仍可使用。")
for index, item in enumerate(st.session_state.sampling_display):
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
if not st.session_state.sampling_display:
    st.info("例如：5kHz单频信号以8kSa/s采样，混叠频率是多少？或计算1kHz、峰值2V纯正弦的周期和RMS。")
limit = st.session_state.sampling_turns >= 20
if limit:
    st.info("已达到20轮，请新建信号与采样对话。")
question = st.chat_input("输入信号与采样问题，请提供已知量、单位及幅值定义", disabled=not ready or limit,
                         max_chars=2000, key="sampling_question", submit_mode="disable")
learning = st.session_state.get("study_pending_sampling_prompt")
if learning:
    with st.container(border=True):
        st.write(learning)
        if st.button("发送给信号与采样助手讲解", key="sampling_study_send", disabled=not ready or limit, type="primary"):
            question = learning
            st.session_state.pop("study_pending_sampling_prompt", None)
        if st.button("取消本次学习提问", key="sampling_study_cancel"):
            st.session_state.pop("study_pending_sampling_prompt", None)
            st.rerun()
if question and question.strip() and ready and not limit:
    question = question.strip()
    st.session_state.sampling_display.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    events, calculations, sources = [], [], {}
    error, answer = None, None
    with st.chat_message("assistant"):
        with st.status("正在处理信号与采样问题…", expanded=True) as status:
            def show_event(text):
                events.append(text)
                st.code(text, language="text")
            try:
                with OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=45, max_retries=0) as client:
                    answer, history = run_turn(client, st.session_state.sampling_history, question, emit=show_event,
                                               on_result=calculations.append,
                                               on_sources=lambda entries: sources.update({entry["id"]: entry for entry in entries}))
                st.session_state.sampling_history = history
                st.session_state.sampling_turns += 1
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
            render_extra(item, len(st.session_state.sampling_display))
        st.session_state.sampling_display.append(item)
