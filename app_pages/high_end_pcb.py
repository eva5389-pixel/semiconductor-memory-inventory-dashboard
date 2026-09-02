from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from pcb_sources import PCB_COMPANIES, fetch_pcb_dashboard


@st.cache_data(ttl="6h", max_entries=3, show_spinner=False)
def load_pcb_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    return fetch_pcb_dashboard()


st.title("高階 PCB 庫存循環")
st.caption("CCL、AI 伺服器 PCB、HDI／IC 載板與關鍵材料｜財報庫存 × 營收 × 股價動能")

with st.sidebar:
    st.header("PCB 設定")
    selected_segments = st.multiselect("板塊", list(PCB_COMPANIES), default=list(PCB_COMPANIES))
    st.caption("資料以季報為主；公司財報日不同，最新季度可能不完全一致。")

with st.skeleton(height=220):
    summaries, history, errors = load_pcb_data()

if summaries.empty:
    st.error("目前無法取得高階 PCB 公司資料，請稍後重新整理。")
    if errors:
        st.caption("；".join(errors))
    st.stop()

view = summaries.loc[summaries["板塊"].isin(selected_segments)].copy()
history_view = history.loc[history["板塊"].isin(selected_segments)].copy()
if view.empty:
    st.warning("請至少選擇一個板塊。")
    st.stop()

segment_summary = view.groupby("板塊", as_index=False).agg(
    公司數=("公司", "count"),
    營收年增中位數=("營收年增%", "median"),
    存貨天數季變中位數=("存貨天數季變", "median"),
    毛利率中位數=("毛利率%", "median"),
    股價3月中位數=("3個月股價%", "median"),
)

with st.container(horizontal=True):
    st.metric("追蹤公司", f"{len(view)} 家", border=True)
    st.metric("營收年增中位數", f"{view['營收年增%'].median():+.1f}%", border=True)
    st.metric("存貨天數季變中位數", f"{view['存貨天數季變'].median():+.1f} 天", border=True)
    pressure_count = int(view["循環階段"].eq("庫存壓力").sum())
    st.metric("庫存壓力公司", f"{pressure_count} 家", border=True)

cycle_order = ["健康去化", "擴張備貨", "收縮去化", "庫存壓力", "資料不足"]
cycle_colors = ["#00bfa5", "#3288ff", "#f6a000", "#ff4b4b", "#8a94a6"]

left, right = st.columns([1.15, 1])
with left:
    with st.container(border=True):
        st.subheader("公司循環定位")
        scatter_data = view.dropna(subset=["營收年增%", "存貨天數季變"])
        zero_x = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#7c8799", strokeDash=[5, 5]).encode(x="x:Q")
        zero_y = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#7c8799", strokeDash=[5, 5]).encode(y="y:Q")
        points = alt.Chart(scatter_data).mark_circle(size=150, opacity=0.9).encode(
            x=alt.X("存貨天數季變:Q", title="存貨天數季變（天）"),
            y=alt.Y("營收年增%:Q", title="營收年增率（%）"),
            color=alt.Color("循環階段:N", scale=alt.Scale(domain=cycle_order, range=cycle_colors), title="循環階段"),
            tooltip=["板塊:N", "公司:N", alt.Tooltip("營收年增%:Q", format="+.1f"), alt.Tooltip("存貨天數季變:Q", format="+.1f"), "循環階段:N"],
        )
        st.altair_chart((zero_x + zero_y + points).properties(height=420).interactive(), width="stretch")
with right:
    with st.container(border=True):
        st.subheader("板塊中位數")
        chart_data = segment_summary.melt(
            id_vars=["板塊"], value_vars=["營收年增中位數", "存貨天數季變中位數"], var_name="指標", value_name="數值"
        )
        st.altair_chart(alt.Chart(chart_data).mark_bar().encode(
            x=alt.X("數值:Q", title="百分點／天數"),
            y=alt.Y("板塊:N", title=None, sort=list(PCB_COMPANIES)),
            color=alt.Color("指標:N", title="指標"),
            row=alt.Row("指標:N", title=None, header=alt.Header(labels=False)),
            tooltip=["板塊:N", "指標:N", alt.Tooltip("數值:Q", format="+.1f")],
        ).properties(height=165).resolve_scale(x="independent"), width="stretch")

with st.container(border=True):
    st.subheader("公司明細")
    display_columns = ["板塊", "公司", "代碼", "財報日期", "循環階段", "營收年增%", "存貨年增%", "存貨天數", "存貨天數季變", "毛利率%", "3個月股價%", "判讀"]
    st.dataframe(view[display_columns].sort_values(["板塊", "營收年增%"], ascending=[True, False]), hide_index=True, width="stretch", column_config={
        "財報日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "營收年增%": st.column_config.NumberColumn(format="%+.1f%%"),
        "存貨年增%": st.column_config.NumberColumn(format="%+.1f%%"),
        "存貨天數": st.column_config.NumberColumn(format="%.1f"),
        "存貨天數季變": st.column_config.NumberColumn(format="%+.1f"),
        "毛利率%": st.column_config.NumberColumn(format="%.1f%%"),
        "3個月股價%": st.column_config.NumberColumn(format="%+.1f%%"),
    })

with st.container(border=True):
    st.subheader("存貨天數趨勢")
    st.altair_chart(alt.Chart(history_view.dropna(subset=["InventoryDays"])).mark_line(point=True).encode(
        x=alt.X("Date:T", title="財報季度"),
        y=alt.Y("InventoryDays:Q", title="存貨天數"),
        color=alt.Color("公司:N", title="公司"),
        strokeDash=alt.StrokeDash("板塊:N", title="板塊"),
        tooltip=[alt.Tooltip("Date:T", format="%Y-%m-%d"), "板塊:N", "公司:N", alt.Tooltip("InventoryDays:Q", format=".1f")],
    ).properties(height=390).interactive(), width="stretch")

if errors:
    st.warning("部分公司資料暫時未回傳：" + "；".join(errors))

with st.expander("判讀方式與限制"):
    st.write("四象限以營收年增率與存貨天數季變判讀：營收增、天數降＝健康去化；營收增、天數升＝擴張備貨；營收減、天數升＝庫存壓力；營收減、天數降＝收縮去化。")
    st.write("板塊數值採公司中位數，避免大型公司主導結果。Yahoo Finance 財報欄位可能延遲或缺漏，重大投資判斷仍應回查公司公告與公開資訊觀測站。")
