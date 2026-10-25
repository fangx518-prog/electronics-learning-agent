import streamlit as st

from learning_core import (QUESTIONS, QUESTION_MAP, SOURCE_MAP, TOPICS,
                           export_progress, import_progress, record_answer,
                           summary, tutor_prompt, wrong_ids)

st.title("练习与复习")
st.caption(f"{len(QUESTIONS)}道本地题库练习 · 固定标准答案与解析 · 不消耗模型调用额度")
st.caption("最近一次答对只表示该题本次作答正确，不代表已掌握全部知识。")
mode = st.segmented_control("练习方式", ["按主题练习", "错题复习"],
                            key="study_practice_mode", persist_state="session")
topic = st.selectbox("练习主题", ["all"] + list(TOPICS),
                     format_func=lambda key: "全部主题" if key == "all" else TOPICS[key]["title"],
                     key="study_practice_topic", persist_state="session", index=None)
if mode not in ("按主题练习", "错题复习") or topic not in {"all", *TOPICS}:
    st.info("请选择练习方式和主题。")
    st.stop()
pending = set(wrong_ids(st.session_state.study_progress))
pool = [item["id"] for item in QUESTIONS if (topic == "all" or item["topic"] == topic)
        and (mode != "错题复习" or item["id"] in pending)]

if not pool:
    st.success("当前范围没有待复习题目。可以切换主题，或回到按主题练习。")
else:
    # 不把跨题答案自动预选到新题中。导入记录后也使用新的控件标识。
    group_key = f"{mode}_{topic}_{st.session_state.study_revision}"
    qid = st.selectbox("选择题目", pool,
                       format_func=lambda key: f"{key} · {QUESTION_MAP[key]['stem']}",
                       key=f"study_question_{group_key}")
    item = QUESTION_MAP[qid]
    st.subheader(f"{qid} · {TOPICS[item['topic']]['title']}")
    st.write(item["stem"])
    with st.form(f"study_form_{qid}_{st.session_state.study_revision}"):
        selected = st.radio("请选择答案", list(range(len(item["options"]))), index=None,
                            format_func=lambda index: f"选项 {chr(65 + index)}：{item['options'][index].replace(' F', ' 法拉（F）')}",
                            key=f"study_answer_{qid}_{st.session_state.study_revision}")
        submitted = st.form_submit_button("提交答案", key="study_submit", type="primary")
    if submitted:
        if selected is None:
            st.warning("请先选择一个答案，再提交。")
        else:
            try:
                updated, correct = record_answer(st.session_state.study_progress, qid, selected)
                st.session_state.study_progress = updated
                st.session_state.study_feedback[qid] = correct
            except ValueError as exc:
                st.warning(str(exc))
    if qid in st.session_state.study_feedback:
        if st.session_state.study_feedback[qid]:
            st.success("本次回答正确。")
        else:
            st.warning("本次回答有误，已加入待复习题目。")
        st.markdown(f"**标准答案：{chr(65 + item['correct'])}. {item['options'][item['correct']]}**")
        st.write(item["explanation"])
        if mode == "错题复习" and st.session_state.study_feedback[qid]:
            st.caption("本题已移出待复习列表；下次刷新或切换题目时更新列表。")
        for source_id in item["sources"]:
            source = SOURCE_MAP[source_id]
            st.markdown(f"[{source_id}] [{source['title']}]({source['url']})")
    if st.button("把这道题带给助手讲解", key="study_tutor", icon=":material/chat:"):
        previous = st.session_state.study_progress["answers"].get(qid, [])
        domain = TOPICS[item["topic"]].get("domain", "rc")
        pending_key, target_page = {
            "rc": ("study_pending_prompt", "app_pages/experiment.py"),
            "dc": ("study_pending_dc_prompt", "app_pages/dc.py"),
            "logic": ("study_pending_logic_prompt", "app_pages/logic.py"),
            "sampling": ("study_pending_sampling_prompt", "app_pages/sampling.py"),
        }[domain]
        st.session_state[pending_key] = tutor_prompt(qid, previous[-1] if previous else None)
        st.switch_page(target_page)

st.divider()
stats = summary(st.session_state.study_progress)
with st.container(horizontal=True):
    st.metric("已练习题目", f"{stats['answered']} / {len(QUESTIONS)}")
    st.metric("首次答对", stats["first_correct"])
    st.metric("待复习", stats["wrong"])
st.caption(f"累计提交 {stats['attempts']} 次；最近一次答对 {stats['latest_correct']} 题。")
st.caption("学习记录保存在当前网页会话中。关闭或重启后可能丢失，请导出并保存在自己电脑上，下次可导入恢复。")
st.download_button("导出学习记录", data=export_progress(st.session_state.study_progress),
                   file_name="electronics_learning_progress.json", mime="application/json",
                   key="study_export", on_click="ignore", icon=":material/download:")
with st.expander("导入以前的学习记录"):
    st.caption("导入会替换当前学习记录，请先导出当前记录留存。")
    with st.form("study_import_form"):
        uploaded = st.file_uploader("选择本应用导出的JSON文件", type=["json"], key="study_import_file", max_upload_size=1)
        restore = st.form_submit_button("导入并替换当前记录", key="study_restore")
    if restore:
        if uploaded is None:
            st.warning("请先选择学习记录文件。")
        else:
            try:
                restored = import_progress(uploaded.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.study_progress = restored
                st.session_state.study_feedback = {}
                st.session_state.study_revision += 1
                st.session_state["study_restore_notice"] = True
                st.rerun()
if st.session_state.pop("study_restore_notice", False):
    st.success("学习记录已恢复。")
