import pandas as pd

from cycle_model import build_cycle_history, classify_phase


def test_four_phases():
    assert classify_phase(1, -1) == "主動去庫存"
    assert classify_phase(1, 1) == "主動補庫存"
    assert classify_phase(-1, 1) == "被動補庫存"
    assert classify_phase(-1, -1) == "被動去庫存"


def test_history_calculates_yoy_and_ratio():
    dates = pd.date_range("2024-01-01", periods=18, freq="MS")
    frame = pd.DataFrame({"Date": dates, "new_orders": range(100, 118), "total_inventory": range(200, 218), "shipments": range(80, 98)})
    result = build_cycle_history(frame)
    assert "new_orders_yoy" in result
    assert "inventory_shipments_ratio" in result
    assert result["inventory_shipments_ratio"].notna().all()

