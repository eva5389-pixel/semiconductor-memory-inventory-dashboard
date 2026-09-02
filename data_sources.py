from __future__ import annotations

from io import BytesIO, StringIO
import re
import zipfile

import pandas as pd
import requests
from bs4 import BeautifulSoup


FRED_SERIES = {
    "new_orders": ("A34SNO", "電子產品新訂單", "百萬美元"),
    "total_inventory": ("A34STI", "電子產品總庫存", "百萬美元"),
    "finished_inventory": ("A34SFI", "電子產品成品庫存", "百萬美元"),
    "shipments": ("A34SVS", "電子產品出貨", "百萬美元"),
    "semiconductor_output": ("IPG3344S", "半導體工業生產", "2017=100"),
    "semiconductor_ppi": ("PCU334413334413P", "半導體生產者價格", "指數"),
}

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
TRENDFORCE_PRICE_URL = "https://www.trendforce.com/price"
TRENDFORCE_ARTICLES = [
    "https://www.trendforce.com/presscenter/news/20260730-13158.html",
    "https://www.trendforce.com/presscenter/news/20260721-13148.html",
    "https://www.trendforce.com/presscenter/news/20260709-13140.html",
    "https://www.trendforce.com/presscenter/news/20260703-13134.html",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; semiconductor-cycle-dashboard/1.0)"}
FRED_HEADERS = {"User-Agent": "curl/8.7.1", "Accept-Encoding": "identity"}


def fetch_fred_series(series_id: str, timeout: int = 20) -> pd.DataFrame:
    response = requests.get(FRED_CSV.format(series_id=series_id), headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    frame.columns = ["Date", series_id]
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
    return frame.dropna().sort_values("Date")


def fetch_fred_bundle() -> tuple[pd.DataFrame, list[str]]:
    """Download all FRED series once; mixed monthly definitions arrive as a ZIP."""
    series_ids = ",".join(spec[0] for spec in FRED_SERIES.values())
    url = FRED_CSV.format(series_id=series_ids)
    try:
        response = requests.get(url, headers=FRED_HEADERS, timeout=60)
        response.raise_for_status()
        frames: list[pd.DataFrame] = []
        if response.content.startswith(b"PK"):
            with zipfile.ZipFile(BytesIO(response.content)) as archive:
                for name in archive.namelist():
                    if name.endswith(".csv"):
                        frames.append(pd.read_csv(archive.open(name)))
        else:
            frames.append(pd.read_csv(StringIO(response.text)))
        merged = None
        for frame in frames:
            frame = frame.rename(columns={frame.columns[0]: "Date"})
            frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
            merged = frame if merged is None else merged.merge(frame, on="Date", how="outer")
        rename_map = {spec[0]: key for key, spec in FRED_SERIES.items()}
        merged = merged.rename(columns=rename_map)
        for column in rename_map.values():
            if column in merged:
                merged[column] = pd.to_numeric(merged[column], errors="coerce")
        return merged.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True), []
    except Exception as exc:
        return pd.DataFrame(), [f"FRED 批次下載：{type(exc).__name__}"]


def fetch_trendforce_prices(timeout: int = 25) -> tuple[pd.DataFrame, str]:
    response = requests.get(TRENDFORCE_PRICE_URL, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    update_match = re.search(r"Last Update\s*([0-9-]+\s+[0-9:]+)", soup.get_text(" ", strip=True))
    update_note = update_match.group(1) if update_match else "頁面即時資料"
    rows: list[pd.DataFrame] = []
    for table in pd.read_html(StringIO(response.text)):
        table.columns = [str(column).strip() for column in table.columns]
        if "Item" not in table.columns:
            continue
        average = next((c for c in table.columns if "Average" in c), None)
        change = next((c for c in table.columns if "Change" in c), None)
        if average is None:
            continue
        selected = pd.DataFrame({
            "產品": table["Item"].astype(str),
            "均價": pd.to_numeric(table[average].astype(str).str.replace(",", "", regex=False), errors="coerce"),
            "變動": table[change].astype(str) if change else "—",
        }).dropna(subset=["均價"])
        rows.append(selected)
    if not rows:
        raise ValueError("TrendForce 公開價格表格式已改變")
    return pd.concat(rows, ignore_index=True).drop_duplicates("產品").head(30), update_note


def fetch_trendforce_articles(timeout: int = 20) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    errors = []
    for url in TRENDFORCE_ARTICLES:
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            social_title = soup.find("meta", attrs={"property": "og:title"})
            title = social_title.get("content") if social_title else (soup.title.string if soup.title else "TrendForce 記憶體市場更新")
            body = soup.find("article") or soup.find("main") or soup
            text = body.get_text(" ", strip=True)
            date_match = re.search(r"(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\s+[A-Za-z]+\s+(?:19|20)\d{2}", text)
            rows.append({"日期": date_match.group(0) if date_match else "", "標題": str(title).strip(), "連結": url})
        except Exception as exc:
            errors.append(f"{url}：{type(exc).__name__}")
    return pd.DataFrame(rows), errors
