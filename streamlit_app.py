import streamlit as st


st.set_page_config(page_title="科技供應鏈循環儀表板", page_icon="💾", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/semiconductor.py", title="半導體與記憶體", icon=":material/memory:"),
        st.Page("app_pages/high_end_pcb.py", title="高階 PCB", icon=":material/developer_board:"),
        st.Page("app_pages/power_ai.py", title="電力循環與 AI", icon=":material/electric_bolt:"),
    ],
    position="top",
)
page.run()
