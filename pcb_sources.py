from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf


PCB_COMPANIES = {
    "CCL 銅箔基板": {
        "2383.TW": "台光電",
        "6274.TWO": "台燿",
        "6213.TW": "聯茂",
    },
    "AI 伺服器 PCB": {
        "2368.TW": "金像電",
        "3044.TW": "健鼎",
        "8155.TWO": "博智",
    },
    "HDI／IC 載板": {
        "3037.TW": "欣興",
        "8046.TW": "南電",
        "4958.TW": "臻鼎-KY",
    },
    "關鍵材料與耗材": {
        "8358.TWO": "金居",
        "1815.TWO": "富喬",
        "8021.TW": "尖點",
    },
}


def _row(statement: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if not statement.empty and name in statement.index:
            return pd.to_numeric(statement.loc[name], errors="coerce").dropna().sort_index()
    return pd.Series(dtype=float)


def classify_pcb_cycle(revenue_yoy: float, inventory_days_change: float) -> tuple[str, str]:
    if pd.isna(revenue_yoy) or pd.isna(inventory_days_change):
        return "資料不足", "至少需要五季財報，才能同時計算營收年增與存貨天數季變。"
    if revenue_yoy >= 0 and inventory_days_change < 0:
        return "健康去化", "營收成長且存貨天數下降，需求吸收庫存的品質較佳。"
    if revenue_yoy >= 0 and inventory_days_change >= 0:
        return "擴張備貨", "營收成長且存貨天數增加，可能因擴產或旺季備貨，需觀察後續營收能否消化。"
    if revenue_yoy < 0 and inventory_days_change >= 0:
        return "庫存壓力", "營收衰退但存貨天數上升，屬較弱的被動累庫訊號。"
    return "收縮去化", "營收仍衰退但存貨天數下降，企業正在清理庫存。"


def fetch_pcb_company(ticker: str, name: str, segment: str) -> tuple[dict, pd.DataFrame]:
    stock = yf.Ticker(ticker)
    balance = stock.quarterly_balance_sheet
    income = stock.quarterly_income_stmt
    frequency = "季報"
    period_days = 90
    yoy_periods = 4
    inventory = _row(balance, "Inventory")
    revenue = _row(income, "Total Revenue", "Operating Revenue")
    cost = _row(income, "Cost Of Revenue")
    gross_profit = _row(income, "Gross Profit")
    common_dates = inventory.index.intersection(revenue.index).intersection(cost.index).sort_values()
    if len(common_dates) < 2:
        balance = stock.balance_sheet
        income = stock.income_stmt
        frequency = "年報"
        period_days = 365
        yoy_periods = 1
        inventory = _row(balance, "Inventory")
        revenue = _row(income, "Total Revenue", "Operating Revenue")
        cost = _row(income, "Cost Of Revenue")
        gross_profit = _row(income, "Gross Profit")
        common_dates = inventory.index.intersection(revenue.index).intersection(cost.index).sort_values()
    quarterly = pd.DataFrame({
        "Date": common_dates,
        "Inventory": inventory.reindex(common_dates).to_numpy(),
        "Revenue": revenue.reindex(common_dates).to_numpy(),
        "Cost": cost.reindex(common_dates).to_numpy(),
    })
    quarterly["GrossProfit"] = gross_profit.reindex(common_dates).to_numpy() if not gross_profit.empty else np.nan
    quarterly["InventoryDays"] = quarterly["Inventory"] / quarterly["Cost"].replace(0, np.nan) * period_days
    quarterly["InventoryYoY"] = quarterly["Inventory"].pct_change(yoy_periods, fill_method=None) * 100
    quarterly["RevenueYoY"] = quarterly["Revenue"].pct_change(yoy_periods, fill_method=None) * 100
    quarterly["GrossMargin"] = quarterly["GrossProfit"] / quarterly["Revenue"].replace(0, np.nan) * 100

    prices = stock.history(period="1y", auto_adjust=True)[["Close"]].dropna()
    latest_price = float(prices["Close"].iloc[-1]) if not prices.empty else np.nan
    return_3m = (latest_price / float(prices["Close"].iloc[-64]) - 1) * 100 if len(prices) >= 64 else np.nan
    latest = quarterly.iloc[-1] if not quarterly.empty else pd.Series(dtype=float)
    previous = quarterly.iloc[-2] if len(quarterly) >= 2 else pd.Series(dtype=float)
    days_change = latest.get("InventoryDays", np.nan) - previous.get("InventoryDays", np.nan)
    phase, note = classify_pcb_cycle(latest.get("RevenueYoY", np.nan), days_change)
    summary = {
        "板塊": segment,
        "公司": name,
        "代碼": ticker.split(".")[0],
        "財報日期": latest.get("Date", pd.NaT),
        "資料頻率": frequency,
        "存貨（億元）": latest.get("Inventory", np.nan) / 1e8,
        "營收（億元）": latest.get("Revenue", np.nan) / 1e8,
        "存貨天數": latest.get("InventoryDays", np.nan),
        "存貨天數季變": days_change,
        "存貨年增%": latest.get("InventoryYoY", np.nan),
        "營收年增%": latest.get("RevenueYoY", np.nan),
        "毛利率%": latest.get("GrossMargin", np.nan),
        "3個月股價%": return_3m,
        "循環階段": phase,
        "判讀": note,
    }
    quarterly["板塊"] = segment
    quarterly["公司"] = name
    return summary, quarterly


def fetch_pcb_dashboard() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    summaries: list[dict] = []
    histories: list[pd.DataFrame] = []
    errors: list[str] = []
    for segment, companies in PCB_COMPANIES.items():
        for ticker, name in companies.items():
            try:
                summary, history = fetch_pcb_company(ticker, name, segment)
                summaries.append(summary)
                histories.append(history)
            except Exception as exc:
                errors.append(f"{name}：{type(exc).__name__}")
    history = pd.concat(histories, ignore_index=True) if histories else pd.DataFrame()
    return pd.DataFrame(summaries), history, errors
