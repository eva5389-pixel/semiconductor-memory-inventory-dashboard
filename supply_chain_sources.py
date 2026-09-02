from __future__ import annotations

import pandas as pd

from pcb_sources import fetch_pcb_company


OPTICAL_COMPANIES = {
    "光纖元件／FAU": {"3363.TWO": "上詮", "3163.TWO": "波若威", "6442.TW": "光聖"},
    "雷射／光收發模組": {"3081.TWO": "聯亞", "4979.TWO": "華星光", "3450.TW": "聯鈞"},
    "高速網通系統": {"2345.TW": "智邦", "3596.TW": "智易", "6285.TW": "啟碁"},
}

HVDC_COMPANIES = {
    "800V HVDC 電源": {"2308.TW": "台達電", "2301.TW": "光寶科", "6412.TW": "群電", "6282.TW": "康舒"},
    "BBU／備援電池": {"6781.TW": "AES-KY", "4931.TWO": "新盛力", "3211.TWO": "順達"},
    "電源測試／基礎設施": {"2360.TW": "致茂", "1519.TW": "華城", "1513.TW": "中興電"},
}


def fetch_supply_chain(companies: dict[str, dict[str, str]]) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    summaries: list[dict] = []
    histories: list[pd.DataFrame] = []
    errors: list[str] = []
    for segment, members in companies.items():
        for ticker, name in members.items():
            try:
                summary, history = fetch_pcb_company(ticker, name, segment)
                summaries.append(summary)
                histories.append(history)
            except Exception as exc:
                errors.append(f"{name}：{type(exc).__name__}")
    return (
        pd.DataFrame(summaries),
        pd.concat(histories, ignore_index=True) if histories else pd.DataFrame(),
        errors,
    )
