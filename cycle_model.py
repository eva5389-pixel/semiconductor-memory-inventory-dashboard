from __future__ import annotations

import numpy as np
import pandas as pd


PHASE_META = {
    "主動去庫存": ("需求動能改善、庫存動能下降", "復甦初期", "#14B8A6"),
    "主動補庫存": ("需求動能改善、庫存動能上升", "擴張期", "#3B82F6"),
    "被動補庫存": ("需求動能轉弱、庫存動能上升", "景氣後期", "#F59E0B"),
    "被動去庫存": ("需求動能轉弱、庫存動能下降", "收縮期", "#EF4444"),
}


def classify_phase(demand_momentum: float, inventory_momentum: float) -> str:
    if demand_momentum >= 0 and inventory_momentum < 0:
        return "主動去庫存"
    if demand_momentum >= 0 and inventory_momentum >= 0:
        return "主動補庫存"
    if demand_momentum < 0 and inventory_momentum >= 0:
        return "被動補庫存"
    return "被動去庫存"


def build_cycle_history(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty or not {"Date", "new_orders", "total_inventory"}.issubset(raw.columns):
        return pd.DataFrame()
    out = raw.copy().sort_values("Date").reset_index(drop=True)
    for column in ["new_orders", "total_inventory", "finished_inventory", "shipments", "semiconductor_output", "semiconductor_ppi"]:
        if column in out:
            out[f"{column}_yoy"] = out[column].pct_change(12, fill_method=None) * 100
    out["demand_momentum"] = out["new_orders_yoy"].diff(3)
    out["inventory_momentum"] = out["total_inventory_yoy"].diff(3)
    out["inventory_shipments_ratio"] = out["total_inventory"] / out["shipments"] if "shipments" in out else np.nan
    out["phase"] = [
        classify_phase(demand, inventory) if pd.notna(demand) and pd.notna(inventory) else None
        for demand, inventory in zip(out["demand_momentum"], out["inventory_momentum"])
    ]
    return out


def latest_complete(frame: pd.DataFrame) -> pd.Series | None:
    required = ["new_orders_yoy", "total_inventory_yoy", "demand_momentum", "inventory_momentum", "phase"]
    valid = frame.dropna(subset=required) if not frame.empty else frame
    return None if valid.empty else valid.iloc[-1]

