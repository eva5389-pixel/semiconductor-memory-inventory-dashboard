from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from eia_sources import EIA_BROWSER_URL, STATE_NAMES, fetch_eia_commercial_power, power_cycle


@st.cache_data(ttl="6h", max_entries=3, show_spinner=False)
def load_eia_power() -> tuple[pd.DataFrame, str]:
    try:
        api_key = st.secrets.get("EIA_API_KEY", None)
    except Exception:
        api_key = None
    try:
        return fetch_eia_commercial_power(api_key=api_key), "EIA 即時資料"
    except Exception:
        snapshot = Path(__file__).resolve().parents[1] / "data_snapshots" / "eia_power.csv"
        if snapshot.exists():
            return pd.read_csv(snapshot, parse_dates=["Date"]), "EIA 備援快照"
        raise


st.title("電力循環與 AI 用電影響力")
st.caption("EIA Electricity 月度商業部門售電量與零售電價｜AI 指標衡量資料中心潛在用電壓力，不作因果認定。")

with st.sidebar:
    st.header("電力設定")
    selected_state = st.selectbox("觀察地區", [state for state in STATE_NAMES if state != "US"], format_func=STATE_NAMES.get)
    compare_states = st.multiselect("比較地區", list(STATE_NAMES), default=["US", selected_state], format_func=STATE_NAMES.get)
    years = st.segmented_control("歷史範圍", ["3 年", "5 年", "8 年"], default="5 年", key="power_years")
    st.link_button("EIA Electricity Data Browser", EIA_BROWSER_URL, width="stretch")

with st.skeleton(height=220):
    try:
        power, data_source = load_eia_power()
    except Exception as exc:
        st.error(f"EIA Electricity 暫時無法讀取：{type(exc).__name__}")
        st.write("可在 Streamlit Secrets 設定 `EIA_API_KEY`；未設定時程式使用 EIA 的 DEMO_KEY。")
        st.stop()

if data_source == "EIA 備援快照":
    st.info("EIA 即時 API 暫時無法連線，目前顯示最近一次成功更新的備援快照。")

latest_rows = power.dropna(subset=["sales_yoy", "price_yoy"]).sort_values("Date").groupby("stateid", as_index=False).tail(1)
selected = latest_rows.loc[latest_rows["stateid"].eq(selected_state)]
if selected.empty:
    st.warning("所選地區沒有足夠的同比資料。")
    st.stop()
latest = selected.iloc[0]
cycle_name, cycle_note = power_cycle(float(latest["sales_yoy"]), float(latest["price_yoy"]))

with st.container(horizontal=True):
    st.metric("電力循環", cycle_name, str(latest["Date"].date()), border=True)
    st.metric("商業售電量年增", f"{latest['sales_yoy']:+.1f}%", border=True)
    st.metric("商業電價年增", f"{latest['price_yoy']:+.1f}%", border=True)
    proxy = latest["ai_power_proxy"]
    st.metric("AI 用電壓力代理", "—" if pd.isna(proxy) else f"{proxy:+.1f}ppt", "相對全美3月均值", border=True)

st.info(f"**{STATE_NAMES[selected_state]}：{cycle_name}。** {cycle_note}")
st.warning("AI 用電壓力代理＝該州商業售電量年增率的3個月均值－全美同期均值。商業用電還包含辦公、零售與其他服務業，不能把差額全部歸因於 AI 或資料中心。")

months = {"3 年": 36, "5 年": 60, "8 年": 96}[years]
view = power.loc[power["stateid"].isin(compare_states)].sort_values("Date").groupby("stateid", group_keys=False).tail(months)

with st.container(border=True):
    st.subheader("商業用電成長比較")
    st.altair_chart(alt.Chart(view.dropna(subset=["sales_3m_ma"])).mark_line(strokeWidth=2.4).encode(
        x=alt.X("Date:T", title="日期"), y=alt.Y("sales_3m_ma:Q", title="售電量年增率・3月均值（%）"),
        color=alt.Color("地區:N", title="地區"),
        tooltip=[alt.Tooltip("Date:T", format="%Y-%m"), "地區:N", alt.Tooltip("sales_3m_ma:Q", title="用電年增", format="+.2f")],
    ).interactive(), width="stretch")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("AI 用電壓力代理")
        ai_view = view.loc[~view["stateid"].eq("US")].dropna(subset=["ai_power_proxy"])
        st.altair_chart(alt.Chart(ai_view).mark_line(strokeWidth=2.4).encode(
            x=alt.X("Date:T", title="日期"), y=alt.Y("ai_power_proxy:Q", title="相對全美超額成長（ppt）"), color=alt.Color("地區:N", title="地區"),
            tooltip=[alt.Tooltip("Date:T", format="%Y-%m"), "地區:N", alt.Tooltip("ai_power_proxy:Q", format="+.2f")],
        ).properties(height=340).interactive(), width="stretch")
with right:
    with st.container(border=True):
        st.subheader("商業零售電價年增")
        st.altair_chart(alt.Chart(view.dropna(subset=["price_yoy"])).mark_line(strokeWidth=2.4).encode(
            x=alt.X("Date:T", title="日期"), y=alt.Y("price_yoy:Q", title="電價年增率（%）"), color=alt.Color("地區:N", title="地區"),
            tooltip=[alt.Tooltip("Date:T", format="%Y-%m"), "地區:N", alt.Tooltip("price_yoy:Q", format="+.2f")],
        ).properties(height=340).interactive(), width="stretch")

with st.container(border=True):
    st.subheader("各地區最新電力壓力表")
    table = latest_rows[["地區", "Date", "sales_yoy", "price_yoy", "ai_power_proxy"]].rename(columns={"Date": "資料月份", "sales_yoy": "商業用電年增%", "price_yoy": "商業電價年增%", "ai_power_proxy": "AI用電壓力代理ppt"})
    st.dataframe(table.sort_values("AI用電壓力代理ppt", ascending=False), hide_index=True, width="stretch", column_config={
        "資料月份": st.column_config.DateColumn(format="YYYY-MM"),
        "商業用電年增%": st.column_config.NumberColumn(format="%+.2f%%"),
        "商業電價年增%": st.column_config.NumberColumn(format="%+.2f%%"),
        "AI用電壓力代理ppt": st.column_config.NumberColumn(format="%+.2f"),
    })

with st.expander("模型與資料限制"):
    st.write("EIA API 路徑：Electricity → Retail sales；部門選擇 Commercial，數值使用 sales 與 price。月資料通常有發布落差並可能修訂。")
    st.write("維吉尼亞、德州等地的商業用電超額成長可作為資料中心電力壓力的觀察線索，但不能排除人口、氣候、產業遷移、電價制度與一般商業活動等因素。")
