from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf


CCL_COMPANIES = {
    "2383.TW": "台光電",
    "6274.TWO": "台燿",
    "6213.TW": "聯茂",
}
TWSE_FINANCIALS_URL = "https://openapi.twse.com.tw/"


def _row(statement: pd.DataFrame, name: str) -> pd.Series:
    if statement.empty or name not in statement.index:
        return pd.Series(dtype=float)
    return pd.to_numeric(statement.loc[name], errors="coerce").dropna().sort_index()


def fetch_ccl_company(ticker: str, name: str) -> tuple[dict, pd.DataFrame]:
    stock = yf.Ticker(ticker)
    balance = stock.quarterly_balance_sheet
    income = stock.quarterly_income_stmt
    inventory = _row(balance, "Inventory")
    revenue = _row(income, "Total Revenue")
    cost = _row(income, "Cost Of Revenue")
    common_dates = inventory.index.intersection(revenue.index).intersection(cost.index).sort_values()
    quarterly = pd.DataFrame({
        "Date": common_dates,
        "Inventory": inventory.reindex(common_dates).values,
        "Revenue": revenue.reindex(common_dates).values,
        "Cost": cost.reindex(common_dates).values,
    })
    quarterly["InventoryDays"] = quarterly["Inventory"] / quarterly["Cost"].replace(0, np.nan) * 90
    quarterly["InventoryYoY"] = quarterly["Inventory"].pct_change(4, fill_method=None) * 100
    quarterly["RevenueYoY"] = quarterly["Revenue"].pct_change(4, fill_method=None) * 100
    prices = stock.history(period="1y", auto_adjust=True)[["Close"]].dropna()
    latest_price = float(prices["Close"].iloc[-1]) if not prices.empty else np.nan
    return_3m = (latest_price / float(prices["Close"].iloc[-64]) - 1) * 100 if len(prices) >= 64 else np.nan
    latest = quarterly.iloc[-1] if not quarterly.empty else pd.Series(dtype=float)
    previous = quarterly.iloc[-2] if len(quarterly) >= 2 else pd.Series(dtype=float)
    inv_days_change = latest.get("InventoryDays", np.nan) - previous.get("InventoryDays", np.nan)
    pressure = "資料不足"
    if pd.notna(inv_days_change):
        pressure = "庫存壓力上升" if inv_days_change > 3 else "庫存壓力下降" if inv_days_change < -3 else "庫存大致穩定"
    summary = {
        "公司": name,
        "代碼": ticker.split(".")[0],
        "財報日期": latest.get("Date", pd.NaT),
        "存貨（億元）": latest.get("Inventory", np.nan) / 1e8,
        "營收（億元）": latest.get("Revenue", np.nan) / 1e8,
        "存貨天數": latest.get("InventoryDays", np.nan),
        "存貨天數季變": inv_days_change,
        "存貨年增%": latest.get("InventoryYoY", np.nan),
        "營收年增%": latest.get("RevenueYoY", np.nan),
        "股價": latest_price,
        "3個月漲跌%": return_3m,
        "判讀": pressure,
    }
    quarterly["公司"] = name
    return summary, quarterly


def fetch_ccl_dashboard() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    summaries, histories, errors = [], [], []
    for ticker, name in CCL_COMPANIES.items():
        try:
            summary, history = fetch_ccl_company(ticker, name)
            summaries.append(summary)
            histories.append(history)
        except Exception as exc:
            errors.append(f"{name}：{type(exc).__name__}")
    return pd.DataFrame(summaries), pd.concat(histories, ignore_index=True) if histories else pd.DataFrame(), errors
