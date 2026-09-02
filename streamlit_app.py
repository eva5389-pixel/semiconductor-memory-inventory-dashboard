import streamlit as st


st.set_page_config(page_title="科技供應鏈循環儀表板", page_icon="💾", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/home.py", title="半導體與記憶體", icon=":material/memory:", default=True),
        st.Page("app_pages/high_end_pcb.py", title="高階 PCB", icon=":material/developer_board:", url_path="high_end_pcb"),
        st.Page("app_pages/silicon_wafer.py", title="矽晶圓", icon=":material/circle:", url_path="silicon_wafer"),
        st.Page("app_pages/optical.py", title="光通訊", icon=":material/hub:", url_path="optical"),
        st.Page("app_pages/hvdc.py", title="800V 直流電", icon=":material/electrical_services:", url_path="hvdc"),
        st.Page("app_pages/power_ai.py", title="電力循環與 AI", icon=":material/electric_bolt:", url_path="power_ai"),
        st.Page("app_pages/semiconductor.py", title="半導體舊網址", url_path="semiconductor", visibility="hidden"),
    ],
    position="top",
)
page.run()
