"""V2 第三轮独立预览版入口。"""
import streamlit as st

from learning_core import new_progress

st.set_page_config(page_title="电子信息学习助手 · V2.4", layout="centered")
# Streamlit 暂无原生的页面语言参数。仅运行此固定脚本，不拼接用户内容。
# 标准标记覆盖后续各页面和动态选项；翻译工具仍可能忽略作者的标记。
st.html("""<script>
(() => {
    const root = document.documentElement;
    root.setAttribute("lang", "zh-CN");
    root.setAttribute("translate", "no");
    if (document.body) document.body.setAttribute("translate", "no");
})();
</script>""", width="content", unsafe_allow_javascript=True)
st.session_state.setdefault("study_progress", new_progress())
st.session_state.setdefault("study_revision", 0)
st.session_state.setdefault("study_feedback", {})
st.session_state.setdefault("study_lesson", "cutoff")
st.session_state.setdefault("study_practice_topic", "all")
st.session_state.setdefault("study_practice_mode", "按主题练习")

page = st.navigation([
    st.Page("app_pages/learn.py", title="知识学习", icon=":material/school:", default=True),
    st.Page("app_pages/practice.py", title="练习与复习", icon=":material/quiz:"),
    st.Page("app_pages/experiment.py", title="RC 实验助手", icon=":material/science:"),
    st.Page("app_pages/dc.py", title="直流电路助手", icon=":material/electric_bolt:"),
    st.Page("app_pages/logic.py", title="数字逻辑助手", icon=":material/device_hub:"),
    st.Page("app_pages/sampling.py", title="信号与采样助手", icon=":material/waves:"),
], position="top")
page.run()
