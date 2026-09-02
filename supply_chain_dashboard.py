from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from supply_chain_sources import fetch_supply_chain


def render_supply_chain(title: str, caption: str, companies: dict[str, dict[str, str]], cache_key: str, caveat: str) -> None:
    @st.cache_data(ttl="6h", max_entries=3, show_spinner=False)
    def load(_companies: dict[str, dict[str, str]], _cache_key: str):
        summaries, history, errors = fetch_supply_chain(_companies)
        valid = int(summaries.get("財報日期", pd.Series(dtype=object)).notna().sum())
        if valid >= max(1, len(summaries) // 2):
            return summaries, history, errors, "即時資料"
        snapshot_dir = Path(__file__).parent / "data_snapshots"
        summary_file = snapshot_dir / f"{_cache_key}_summaries.csv"
        history_file = snapshot_dir / f"{_cache_key}_history.csv"
        if summary_file.exists() and history_file.exists():
            summaries = pd.read_csv(summary_file, parse_dates=["財報日期"])
            history = pd.read_csv(history_file, parse_dates=["Date"])
            return summaries, history, errors, "備援快照"
        return summaries, history, errors, "即時資料"

    st.title(title)
    st.caption(caption)
    with st.sidebar:
        st.header(f"{title}設定")
        selected = st.multiselect("板塊", list(companies), default=list(companies), key=f"{cache_key}_segments")
        st.caption("滑鼠移到圖中資料點可查看公司名稱，避免標籤遮住圖形。")

    with st.skeleton(height=220):
        summaries, history, errors, source = load(companies, cache_key)
    if source == "備援快照":
        st.info("即時來源暫時受限，目前顯示最近一次成功更新的備援快照。")
    if summaries.empty:
        st.error("目前無法取得資料，請稍後重新整理。")
        st.stop()
    view = summaries[summaries["板塊"].isin(selected)].copy()
    hist = history[history["板塊"].isin(selected)].copy()
    if view.empty:
        st.warning("請至少選擇一個板塊。")
        st.stop()

    with st.container(horizontal=True):
        st.metric("追蹤公司", f"{len(view)} 家", border=True)
        st.metric("營收年增中位數", f"{view['營收年增%'].median():+.1f}%", border=True)
        st.metric("存貨天數季變", f"{view['存貨天數季變'].median():+.1f} 天", border=True)
        st.metric("擴張備貨", f"{int(view['循環階段'].eq('擴張備貨').sum())} 家", border=True)

    colors = alt.Scale(
        domain=["健康去化", "擴張備貨", "收縮去化", "庫存壓力", "資料不足"],
        range=["#2DD4BF", "#60A5FA", "#FBBF24", "#FB7185", "#94A3B8"],
    )
    left, right = st.columns([1.25, 1])
    with left:
        with st.container(border=True):
            st.subheader("公司循環定位")
            scatter = view.dropna(subset=["營收年增%", "存貨天數季變"])
            rules_x = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#64748B", strokeDash=[5, 5]).encode(x="x:Q")
            rules_y = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#64748B", strokeDash=[5, 5]).encode(y="y:Q")
            points = alt.Chart(scatter).mark_circle(size=190, opacity=0.9, stroke="#FFFFFF", strokeWidth=1).encode(
                x=alt.X("存貨天數季變:Q", title="存貨天數季變（天）"),
                y=alt.Y("營收年增%:Q", title="營收年增率（%）"),
                color=alt.Color("循環階段:N", scale=colors, title="循環階段"),
                tooltip=["板塊:N", "公司:N", "代碼:N", alt.Tooltip("營收年增%:Q", format="+.1f"), alt.Tooltip("存貨天數季變:Q", format="+.1f"), "循環階段:N"],
            )
            st.altair_chart((rules_x + rules_y + points).properties(height=430).interactive(), width="stretch")
    with right:
        with st.container(border=True):
            st.subheader("各板塊營收與庫存")
            medians = view.groupby("板塊", as_index=False).agg(營收年增=("營收年增%", "median"), 存貨天數季變=("存貨天數季變", "median"))
            bars = medians.melt("板塊", var_name="指標", value_name="數值")
            st.altair_chart(alt.Chart(bars).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("數值:Q", title="百分點／天"), y=alt.Y("板塊:N", title=None), color=alt.Color("指標:N", title="指標"),
                row=alt.Row("指標:N", title=None, header=alt.Header(labels=False)), tooltip=["板塊:N", "指標:N", alt.Tooltip("數值:Q", format="+.1f")],
            ).properties(height=175).resolve_scale(x="independent"), width="stretch")

    with st.container(border=True):
        st.subheader("公司明細")
        cols = ["板塊", "公司", "代碼", "財報日期", "資料頻率", "循環階段", "營收年增%", "存貨年增%", "存貨天數", "存貨天數季變", "毛利率%", "3個月股價%", "判讀"]
        st.dataframe(view[cols], hide_index=True, width="stretch", column_config={
            "財報日期": st.column_config.DateColumn(format="YYYY-MM-DD"), "營收年增%": st.column_config.NumberColumn(format="%+.1f%%"),
            "存貨年增%": st.column_config.NumberColumn(format="%+.1f%%"), "存貨天數": st.column_config.NumberColumn(format="%.1f"),
            "存貨天數季變": st.column_config.NumberColumn(format="%+.1f"), "毛利率%": st.column_config.NumberColumn(format="%.1f%%"),
            "3個月股價%": st.column_config.NumberColumn(format="%+.1f%%"),
        })

    with st.container(border=True):
        st.subheader("存貨天數趨勢")
        st.altair_chart(alt.Chart(hist.dropna(subset=["InventoryDays"])).mark_line(point=True).encode(
            x=alt.X("Date:T", title="財報季度"), y=alt.Y("InventoryDays:Q", title="存貨天數"), color=alt.Color("公司:N", title="公司"),
            tooltip=[alt.Tooltip("Date:T", format="%Y-%m-%d"), "板塊:N", "公司:N", alt.Tooltip("InventoryDays:Q", format=".1f")],
        ).properties(height=390).interactive(), width="stretch")
    if errors:
        st.warning("部分公司資料暫時未回傳：" + "；".join(errors))
    with st.expander("板塊定義與限制"):
        st.write(caveat)
        st.write("板塊是供應鏈觀察名單，不代表公司營收全部來自該主題；財報資料可能延遲，投資判斷應回查公司公告。")
