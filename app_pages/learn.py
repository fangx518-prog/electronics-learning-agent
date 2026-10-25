import streamlit as st

from learning_core import QUESTIONS, SOURCE_MAP, TOPICS, summary

st.title("知识学习")
st.caption("V2.4 第四轮预览 · RC、直流、组合逻辑与信号采样 · 先理解概念，再做练习与实验")
topic_id = st.selectbox("选择学习主题", list(TOPICS),
                                format_func=lambda key: TOPICS[key]["title"],
                                key="study_lesson", persist_state="session", index=None)
if topic_id not in TOPICS:
    st.info("请选择一个学习主题。")
    st.stop()
topic = TOPICS[topic_id]
st.subheader(topic["title"])
st.write("学习目标：" + topic["goal"])
with st.container(border=True):
    st.markdown(topic["body"])
    st.markdown("**例子**")
    st.write(topic["example"])
st.info(topic["pitfall"], title="容易混淆的地方")
with st.expander("核对资料依据"):
    st.caption("本地整理的教学内容，可通过原始资料核对；不是实时联网检索。")
    for source_id in topic["sources"]:
        source = SOURCE_MAP[source_id]
        st.markdown(f"[{source_id}] {source['title']} · [{source['source']}]({source['url']}) · {source['section']}")
with st.container(horizontal=True):
    if st.button("练习这个主题", key="study_go_practice", type="primary"):
        st.session_state["study_practice_topic"] = topic_id
        st.session_state["study_practice_mode"] = "按主题练习"
        st.switch_page("app_pages/practice.py")
    if st.button("请助手进一步讲解", key="study_lesson_help"):
        domain = topic.get("domain", "rc")
        pending_key, target_page, subject = {
            "rc": ("study_pending_prompt", "app_pages/experiment.py", "一阶RC"),
            "dc": ("study_pending_dc_prompt", "app_pages/dc.py", "直流电路"),
            "logic": ("study_pending_logic_prompt", "app_pages/logic.py", "二值组合逻辑"),
            "sampling": ("study_pending_sampling_prompt", "app_pages/sampling.py", "信号与理想基带采样"),
        }[domain]
        st.session_state[pending_key] = (
            f"我刚学习了{subject}的“{topic['title']}”。请先检索相关资料，用分步提示讲解，"
            "指出一个常见误区，最后给一个不含答案的小问题。新的电路计算使用对应工具，不得补入未知元件值。")
        st.switch_page(target_page)
stats = summary(st.session_state.study_progress)
st.caption(f"已练习 {stats['answered']} / {len(QUESTIONS)} 题；待复习 {stats['wrong']} 题。学习记录可在“练习与复习”页导出。")
