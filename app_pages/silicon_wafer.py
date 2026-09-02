from supply_chain_dashboard import render_supply_chain
from supply_chain_sources import SILICON_WAFER_COMPANIES


render_supply_chain(
    "矽晶圓庫存循環",
    "半導體矽晶圓、磊晶圓與日本國際廠｜晶圓投片需求的上游循環觀察",
    SILICON_WAFER_COMPANIES,
    "silicon_wafer",
    "矽晶圓景氣受 12 吋／8 吋、先進／成熟製程及長約價格影響。中美晶與信越化學業務較多元，板塊數據僅作供應鏈循環代理。",
)
