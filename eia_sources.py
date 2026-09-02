from __future__ import annotations

import os

import pandas as pd
import requests


EIA_RETAIL_SALES_URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"
EIA_BROWSER_URL = "https://www.eia.gov/electricity/data/browser/"
STATE_NAMES = {
    "US": "全美",
    "VA": "維吉尼亞",
    "TX": "德州",
    "CA": "加州",
    "AZ": "亞利桑那",
    "OH": "俄亥俄",
    "OR": "奧勒岡",
}


def fetch_eia_commercial_power(api_key: str | None = None, start: str = "2018-01") -> pd.DataFrame:
    """Load monthly commercial electricity sales and price from EIA API v2."""
    key = api_key or os.getenv("EIA_API_KEY") or "DEMO_KEY"
    params: list[tuple[str, str]] = [
        ("api_key", key),
        ("frequency", "monthly"),
        ("data[0]", "sales"),
        ("data[1]", "price"),
        ("facets[sectorid][]", "COM"),
        ("start", start),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
        ("length", "5000"),
    ]
    params.extend(("facets[stateid][]", state) for state in STATE_NAMES)
    response = requests.get(EIA_RETAIL_SALES_URL, params=params, timeout=45)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    frame = pd.DataFrame(payload.get("response", {}).get("data", []))
    if frame.empty:
        raise ValueError("EIA API 沒有回傳商業用電資料")
    frame["Date"] = pd.to_datetime(frame["period"], errors="coerce")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["地區"] = frame["stateid"].map(STATE_NAMES).fillna(frame["stateDescription"])
    frame = frame.dropna(subset=["Date", "sales", "price"]).sort_values(["stateid", "Date"])
    for column in ["sales", "price"]:
        frame[f"{column}_yoy"] = frame.groupby("stateid")[column].pct_change(12, fill_method=None) * 100
    frame["sales_3m_ma"] = frame.groupby("stateid")["sales_yoy"].transform(lambda values: values.rolling(3).mean())
    us_growth = frame.loc[frame["stateid"].eq("US"), ["Date", "sales_3m_ma"]].rename(columns={"sales_3m_ma": "us_sales_growth"})
    frame = frame.merge(us_growth, on="Date", how="left")
    frame["ai_power_proxy"] = frame["sales_3m_ma"] - frame["us_sales_growth"]
    return frame.reset_index(drop=True)


def power_cycle(demand_yoy: float, price_yoy: float) -> tuple[str, str]:
    if demand_yoy >= 0 and price_yoy >= 0:
        return "需求擴張／電網偏緊", "用電與電價同步上升，留意容量、輸配電與尖峰壓力。"
    if demand_yoy >= 0 and price_yoy < 0:
        return "需求擴張／供給改善", "用電增加但價格下降，供給、燃料成本或發電組合正在緩解壓力。"
    if demand_yoy < 0 and price_yoy >= 0:
        return "需求放緩／成本偏高", "需求轉弱但價格仍升，可能受燃料、輸配電或費率調整影響。"
    return "需求收縮／價格降溫", "用電與價格同步走弱，電力景氣處於降溫階段。"

