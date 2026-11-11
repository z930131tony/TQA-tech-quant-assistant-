# 🚀 台美純科技股量化交易系統 (Tech Quant Assistant)

基於 **PyBroker** 策略引擎與 **Yahoo Finance** 免費行情數據，打造的台美純科技股波段輪動與量化評分系統。搭配永豐金「大戶投」手機 APP，實現半自動（或全自動）雙時區投資管理。

---

## 🌟 核心特點

1. **台美雙時區覆蓋**：
   - ☀️ **晨間台股模式 (08:30)**：台積電、聯發科、鴻海、廣達、緯創、富邦科技等。
   - 🌙 **晚間美股模式 (21:00)**：NVDA、AAPL、MSFT、AMZN、GOOGL、META、TSLA、SMH、QQQ 等。
2. **多因子動量評分**：
   - 20日 / 60日 / 120日 複合動能指標。
   - 50MA / 200MA 趨勢多空濾網（自動避險現金防禦機制）。
   - 20日突破與波動度調適。
3. **100% 免費雲端排程 (GitHub Actions)**：
   - 透過內建 `.github/workflows/daily_schedule.yml`，無需維持 24 小時開機，雲端自動開機運算並推播。

---

## 📁 專案結構

```
ANTIGRAVITY/
├── .github/
│   └── workflows/
│       └── daily_schedule.yml    # GitHub Actions 免費排程
├── src/
│   ├── config.py                 # 標的名單、參數與閾值
│   ├── data_loader.py            # 數據下載與除權息自動調整
│   └── features.py               # 動能評分與趨勢濾網引擎
├── verify_step1.py               # 第一步管線驗證與天梯輸出
├── requirements.txt              # 依賴套件清單
└── README.md
```

---

## ⚡ 本地快速開始

1. **安裝依賴套件**：
   ```bash
   pip install -r requirements.txt
   ```

2. **執行第一步驗證與即時天梯排名**：
   ```bash
   python verify_step1.py
   ```
