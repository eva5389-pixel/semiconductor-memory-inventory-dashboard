# 半導體及記憶體庫存循環儀表板

以 FRED 官方月資料建立電子供應鏈需求／庫存循環，並讀取 TrendForce 公開價格頁與記憶體市場文章。

第二頁使用 EIA Electricity API 的商業售電量與電價，觀察電力循環及資料中心／AI 潛在用電壓力。

## 執行

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## 模型

- 需求：FRED `A34SNO` 電腦與電子產品新訂單年增率。
- 庫存：FRED `A34STI` 電腦與電子產品總庫存年增率。
- 動能：本月年增率減去三個月前的年增率。
- TrendForce：僅解析公開、無需登入的價格及新聞頁面；不繞過付費內容。
- EIA Electricity：`electricity/retail-sales` 月度 commercial sales 與 price；可在 Streamlit Secrets 設定 `EIA_API_KEY`，未設定時使用 `DEMO_KEY`。
- CCL：台光電、台燿、聯茂季度存貨、營收、銷貨成本與股價代理；正式申報數字需回查 TWSE／MOPS。
