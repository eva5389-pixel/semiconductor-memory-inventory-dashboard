from __future__ import annotations

from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from cycle_model import PHASE_META, build_cycle_history, latest_complete
from ccl_sources import TWSE_FINANCIALS_URL, fetch_ccl_dashboard
from data_sources import FRED_SERIES, TRENDFORCE_ARTICLES, TRENDFORCE_PRICE_URL, fetch_fred_bundle, fetch_trendforce_articles, fetch_trendforce_prices


@st.cache_data(ttl="6h", max_entries=3, show_spinner=False)
def load_fred(refresh: bool = False) -> tuple[pd.DataFrame, list[str], str]:
    snapshot = Path(__file__).parent / "data_snapshots" / "fred_bundle.csv"
    if not refresh and snapshot.exists():
        return pd.read_csv(snapshot, parse_dates=["Date"]), [], "FRED 備援快照"
    raw, errors = fetch_fred_bundle()
    if not raw.empty:
        return raw, errors, "FRED 即時資料"
    if snapshot.exists():
        return pd.read_csv(snapshot, parse_dates=["Date"]), errors, "FRED 備援快照"
    return raw, errors, "FRED 即時資料"


@st.cache_data(ttl="2h", max_entries=3, show_spinner=False)
def load_trendforce_prices(refresh: bool = False) -> tuple[pd.DataFrame, str]:
    snapshot_dir = Path(__file__).parent / "data_snapshots"
    if not refresh and (snapshot_dir / "trendforce_prices.csv").exists():
        update = (snapshot_dir / "trendforce_update.txt").read_text(encoding="utf-8").strip()
        return pd.read_csv(snapshot_dir / "trendforce_prices.csv"), update
    return fetch_trendforce_prices()


@st.cache_data(ttl="6h", max_entries=3, show_spinner=False)
def load_trendforce_articles(refresh: bool = False) -> tuple[pd.DataFrame, list[str]]:
    snapshot = Path(__file__).parent / "data_snapshots" / "trendforce_articles.csv"
    if not refresh and snapshot.exists():
        return pd.read_csv(snapshot), []
    return fetch_trendforce_articles()


@st.cache_data(ttl="6h", max_entries=3, show_spinner=False)
def load_ccl(refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    snapshot_dir = Path(__file__).parent / "data_snapshots"
    summary_file = snapshot_dir / "ccl_summaries.csv"
    history_file = snapshot_dir / "ccl_history.csv"
    if not refresh and summary_file.exists() and history_file.exists():
        return (
            pd.read_csv(summary_file, parse_dates=["財報日期"]),
            pd.read_csv(history_file, parse_dates=["Date"]),
            [],
        )
    return fetch_ccl_dashboard()


st.title("半導體及記憶體庫存循環儀表板")
st.caption("FRED 官方月資料 × TrendForce 公開記憶體價格與市場訊息｜需求以電子產品新訂單衡量，庫存以電子產品總庫存衡量。")

with st.sidebar:
    st.header("檢視設定")
    years = st.segmented_control("歷史範圍", ["3 年", "5 年", "10 年"], default="5 年")
    if st.button("重新抓取資料", icon=":material/refresh:", width="stretch"):
        st.cache_data.clear()
        st.session_state["refresh_all_once"] = True
        st.rerun()
    st.divider()
    st.link_button("FRED 資料庫", "https://fred.stlouisfed.org/", width="stretch")
    st.link_button("TrendForce 價格頁", TRENDFORCE_PRICE_URL, width="stretch")

fred_slot = st.container()
refresh_all = bool(st.session_state.pop("refresh_all_once", False))
with fred_slot.skeleton():
    raw, fred_errors, fred_source = load_fred(refresh=refresh_all)
    cycle = build_cycle_history(raw)
    latest = latest_complete(cycle)

if latest is None:
    st.error("FRED 目前無法提供足夠的共同月份資料，請稍後重新抓取。")
    if fred_errors:
        st.caption("；".join(fred_errors))
    st.stop()

if fred_source == "FRED 備援快照":
    st.info("FRED 即時下載暫時受限，目前顯示最近一次成功更新的備援快照。")

phase = str(latest["phase"])
phase_text, business_stage, phase_color = PHASE_META[phase]
lookback = {"3 年": 36, "5 年": 60, "10 年": 120}[years]
view = cycle.tail(lookback).copy()

with st.container(horizontal=True):
    st.metric("目前庫存循環", phase, business_stage, border=True)
    st.metric("新訂單年增率", f"{latest['new_orders_yoy']:+.1f}%", f"3 個月動能 {latest['demand_momentum']:+.1f}ppt", border=True)
    st.metric("總庫存年增率", f"{latest['total_inventory_yoy']:+.1f}%", f"3 個月動能 {latest['inventory_momentum']:+.1f}ppt", border=True)
    ratio = latest.get("inventory_shipments_ratio", float("nan"))
    st.metric("庫存／出貨比", "—" if pd.isna(ratio) else f"{ratio:.2f}x", str(latest["Date"].date()), border=True)

st.info(f"**{phase}｜{phase_text}。** 這是美國電腦與電子產品供應鏈的月度代理指標，不等於全球晶片業者實際庫存天數。")

cycle_conclusions = {
    "主動去庫存": "半導體總體循環仍在修復初期；訂單動能改善而庫存下降，通常尚未走完一輪復甦。",
    "主動補庫存": "半導體循環處於擴張階段；需求與庫存同步增長，AI／伺服器與消費電子仍需分開觀察。",
    "被動補庫存": "總體電子供應鏈已出現後段訊號，但不能解讀成整個半導體循環結束；若訂單持續減速、庫存繼續上升，見頂風險才會提高。",
    "被動去庫存": "半導體循環處於收縮與清庫存階段；需等待訂單動能率先止跌，才能確認下一輪復甦。",
}
st.warning(f"**目前結論：** {cycle_conclusions[phase]} TrendForce 公開資料顯示 DRAM、HBM／伺服器記憶體與消費型 NAND 可能位於不同子循環，因此不可只用一個總體象限概括全部產品。")

with st.container(border=True):
    st.subheader("需求與庫存年增率")
    long = view[["Date", "new_orders_yoy", "total_inventory_yoy"]].rename(columns={"new_orders_yoy": "新訂單年增率", "total_inventory_yoy": "總庫存年增率"}).melt("Date", var_name="指標", value_name="年增率")
    chart = alt.Chart(long.dropna()).mark_line(strokeWidth=2.5).encode(
        x=alt.X("Date:T", title="日期"),
        y=alt.Y("年增率:Q", title="年增率（%）"),
        color=alt.Color("指標:N", scale=alt.Scale(domain=["新訂單年增率", "總庫存年增率"], range=["#38BDF8", "#F59E0B"])),
        tooltip=[alt.Tooltip("Date:T", format="%Y-%m"), "指標:N", alt.Tooltip("年增率:Q", format="+.2f")],
    ).interactive()
    st.altair_chart(chart, width="stretch")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("庫存循環四象限")
        points = view.dropna(subset=["demand_momentum", "inventory_momentum", "phase"]).tail(24).copy()
        points["最新"] = False
        points.loc[points.index[-1], "最新"] = True
        zero = pd.DataFrame({"zero": [0]})
        scatter = alt.Chart(points).mark_circle(opacity=.85).encode(
            x=alt.X("inventory_momentum:Q", title="庫存動能（3 個月變化）"),
            y=alt.Y("demand_momentum:Q", title="需求動能（3 個月變化）"),
            color=alt.Color("phase:N", title="循環", scale=alt.Scale(domain=list(PHASE_META), range=[PHASE_META[p][2] for p in PHASE_META])),
            size=alt.Size("最新:N", legend=None, scale=alt.Scale(domain=[False, True], range=[65, 260])),
            tooltip=[alt.Tooltip("Date:T", format="%Y-%m"), "phase:N", alt.Tooltip("demand_momentum:Q", format="+.2f"), alt.Tooltip("inventory_momentum:Q", format="+.2f")],
        )
        rules = alt.Chart(zero).mark_rule(color="#64748B", strokeDash=[4, 4])
        st.altair_chart((scatter + rules.encode(x="zero:Q") + rules.encode(y="zero:Q")).properties(height=360).interactive(), width="stretch")
        st.caption("右上主動補庫存、左上主動去庫存、右下被動補庫存、左下被動去庫存；大圓點為最新月份。")
with right:
    with st.container(border=True):
        st.subheader("半導體產出與價格")
        cols = [c for c in ["semiconductor_output_yoy", "semiconductor_ppi_yoy"] if c in view]
        labels = {"semiconductor_output_yoy": "半導體工業生產年增率", "semiconductor_ppi_yoy": "半導體 PPI 年增率"}
        semi = view[["Date", *cols]].rename(columns=labels).melt("Date", var_name="指標", value_name="年增率").dropna()
        st.altair_chart(alt.Chart(semi).mark_line(strokeWidth=2.5).encode(
            x=alt.X("Date:T", title="日期"), y=alt.Y("年增率:Q", title="年增率（%）"), color=alt.Color("指標:N", title=None),
            tooltip=[alt.Tooltip("Date:T", format="%Y-%m"), "指標:N", alt.Tooltip("年增率:Q", format="+.2f")],
        ).properties(height=360).interactive(), width="stretch")

st.header("TrendForce 記憶體市場")
price_col, news_col = st.columns([1.1, .9])
with price_col:
    with st.container(border=True):
        st.subheader("公開記憶體價格快照")
        try:
            prices, price_update = load_trendforce_prices(refresh=refresh_all)
            st.caption(f"TrendForce 更新：{price_update}")
            st.dataframe(prices, hide_index=True, width="stretch", column_config={"均價": st.column_config.NumberColumn(format="%.3f")})
        except Exception as exc:
            st.warning(f"TrendForce 公開價格頁暫時無法解析：{type(exc).__name__}")
            st.link_button("直接查看 TrendForce 價格", TRENDFORCE_PRICE_URL)
with news_col:
    with st.container(border=True):
        st.subheader("記憶體供需觀察")
        articles, article_errors = load_trendforce_articles(refresh=refresh_all)
        if articles.empty:
            st.warning("TrendForce 公開新聞目前無法讀取。")
            for url in TRENDFORCE_ARTICLES:
                st.link_button("開啟 TrendForce 報告", url, width="stretch")
        else:
            st.dataframe(articles, hide_index=True, width="stretch", column_config={"連結": st.column_config.LinkColumn("來源", display_text="開啟")})
        st.markdown("**判讀重點**：DRAM 與 NAND 可能處於不同循環，應同時看價格、供應充足率、供應商庫存及 PC／手機／伺服器終端需求。")

st.header("CCL 銅箔基板庫存與需求代理")
st.caption("核心觀察：台光電、台燿、聯茂。季度存貨與營收來自 Yahoo Finance 彙整財報，資料日期依各公司最新可得季度；月營收與正式申報可回查 TWSE／MOPS。")
with st.skeleton(height=220):
    ccl_summary, ccl_history, ccl_errors = load_ccl(refresh=refresh_all)
if ccl_summary.empty:
    st.warning("CCL 公司資料目前無法取得。")
else:
    ccl_cards = st.columns(min(3, len(ccl_summary)))
    for card, (_, company) in zip(ccl_cards, ccl_summary.iterrows()):
        with card:
            st.metric(
                company["公司"],
                f"{company['存貨天數']:.1f} 天" if pd.notna(company["存貨天數"]) else "—",
                f"季變 {company['存貨天數季變']:+.1f} 天" if pd.notna(company["存貨天數季變"]) else "資料不足",
                border=True,
                chart_data=ccl_history.loc[ccl_history["公司"].eq(company["公司"]), "InventoryDays"].dropna().tolist(),
                chart_type="line",
            )
    ccl_left, ccl_right = st.columns([1.1, .9])
    with ccl_left:
        with st.container(border=True):
            st.subheader("CCL 公司庫存天數")
            st.altair_chart(alt.Chart(ccl_history.dropna(subset=["InventoryDays"])).mark_line(point=True, strokeWidth=2.4).encode(
                x=alt.X("Date:T", title="財報季度"), y=alt.Y("InventoryDays:Q", title="估算存貨天數"), color=alt.Color("公司:N", title="公司"),
                tooltip=[alt.Tooltip("Date:T", format="%Y-%m-%d"), "公司:N", alt.Tooltip("InventoryDays:Q", format=".1f")],
            ).properties(height=340), width="stretch")
    with ccl_right:
        with st.container(border=True):
            st.subheader("最新 CCL 公司分析")
            display = ccl_summary[["公司", "財報日期", "存貨天數", "存貨天數季變", "營收年增%", "存貨年增%", "3個月漲跌%", "判讀"]]
            st.dataframe(display, hide_index=True, width="stretch", column_config={
                "財報日期": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "存貨天數": st.column_config.NumberColumn(format="%.1f"),
                "存貨天數季變": st.column_config.NumberColumn(format="%+.1f"),
                "營收年增%": st.column_config.NumberColumn(format="%+.1f%%"),
                "存貨年增%": st.column_config.NumberColumn(format="%+.1f%%"),
                "3個月漲跌%": st.column_config.NumberColumn(format="%+.1f%%"),
            })
            st.link_button("查核 TWSE／MOPS 正式財報", TWSE_FINANCIALS_URL, width="stretch")
if ccl_errors:
    st.caption("部分 CCL 資料失敗：" + "；".join(ccl_errors))
st.info("CCL 判讀方式：存貨天數上升且營收動能放慢，代表庫存壓力增加；存貨天數下降且營收成長，代表去化較健康。股價動能僅是市場預期代理，不能取代公司財報。")

with st.expander("資料來源與限制"):
    fred_table = pd.DataFrame([{"用途": key, "FRED ID": spec[0], "名稱": spec[1], "單位": spec[2], "來源": f"https://fred.stlouisfed.org/series/{spec[0]}"} for key, spec in FRED_SERIES.items()])
    st.write("TrendForce 僅讀取無需登入即可瀏覽的公開頁面；不繞過會員、付費牆或下載限制。網頁格式變更時會顯示錯誤與原始連結，不會捏造即時價格。")
    st.write("FRED 電子產品資料涵蓋電腦與電子產品，並非純記憶體產業；適合用作總體供應鏈代理指標。投資判斷仍應搭配公司財報庫存天數與法說會。")
    st.write("CCL 公司季度存貨由 Yahoo Finance 彙整財報取得，正式數值應以 TWSE／MOPS 財務報告為準；存貨天數以季度銷貨成本折算 90 天，屬比較用估算。")

st.caption(f"頁面產生時間：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
