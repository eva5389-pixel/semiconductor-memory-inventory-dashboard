from supply_chain_dashboard import render_supply_chain
from supply_chain_sources import HVDC_COMPANIES


render_supply_chain(
    "800V 直流電供應鏈",
    "800V HVDC 電源、BBU 備援電池與電源測試／基礎設施｜AI 資料中心供電升級",
    HVDC_COMPANIES,
    "hvdc",
    "800V HVDC 仍在導入期；部分公司同時經營一般電源、電網或消費電子，現階段以供應鏈曝險觀察，不把全部營收歸因於 800V。",
)
