# 🚀 TQA: Tech Quant Assistant (台美純科技股量化交易系統)

<p align="center">
  <a href="#繁體中文"><b>繁體中文</b></a> | <a href="#english"><b>English</b></a>
</p>

---

<a id="繁體中文"></a>
## 🇹🇼 繁體中文

### 一、系統簡介

**TQA (Tech Quant Assistant)** 是一套專為**台美兩大市場頂尖科技龍頭（41 檔）**設計的專業級量化輪動與即時風控系統。

系統整合 **FinMind API 還原權息行情**、**多因子複合動能評分**、**大盤生命線多空濾網**、**手機 Google 試算表雲端持倉同步** 與 **全通路即時推播（LINE 官方通知 + TradingView 互動式儀表板）**。透過 GitHub Actions 每日定時無伺服器（Serverless）自動運算，達到零營運成本、高紀律性之波段獲利目標。

---

### 二、核心架構與亮點

1. **41 檔頂尖科技宇宙 (Tech Universe)**：
   - **台股科技領航 (20 檔)**：台積電 (2330)、聯發科 (2454)、鴻海 (2317)、廣達 (2382)、台達電 (2308)、奇鋐 (3017)、健策 (3653) 等高流動性 AI/半導體供應鏈 + 0050 基準。
   - **美股科技巨擘 (21 檔)**：NVDA、AAPL、MSFT、AMZN、GOOGL、META、TSLA、AVGO、AMD、ASML、PLTR 等巨頭 + SMH / QQQ 基準。

2. **高可靠數據引擎 (Data Engine)**：
   - **FinMind 官方 API 主力**：台股全面採用 FinMind 還原權息日K，徹底消除 yfinance 假除權、拆股崩跌失真（如 0052 拆股誤判）與 IP 頻率封鎖問題。
   - **yfinance 智慧容錯備援**：美股走 yfinance，台股網路異常時自動優雅降級切換。

3. **多因子複合動能與大盤多空防禦 (Strategy & Regime Filter)**：
   - **複合動量評分**：結合 20日 (40%)、60日 (35%)、120日 (25%) 變動率 (ROC) 天梯排序。
   - **技術過濾**：50MA 生命線、200MA 長期年線支撐、20日創波段新高、ATR 波動度調適。
   - **動態多空防禦**：市場轉弱時主動切換為現金避險模式，拒絕逆勢硬扛。

4. **雲端持倉同步與手機即時維護 (Cloud Portfolio)**：
   - **Google Sheets 雙向同步**：支援環境變數 `PORTFOLIO_SHEET_URL`，在手機打開 Google 試算表 App 隨時調整持倉與成本，免改代碼、免動 Git。
   - **雙軌架構**：支援 Supabase REST API 讀取，並具備本地 `portfolio.json` 離線平穩回退機制。
   - **8% 移動停利停損**：追蹤買進後波段最高價，回檔滿 8% 即刻觸發平倉警報。

5. **機構級樣本外檢驗 (Institutional OOS Audit)**：
   - 內建 `oos_validation.py`，通過五大嚴苛檢驗標準：
     - **特徵因果檢驗**：未來數據放大 10 倍注入，過去指標絕對差異 0.000000（0 前瞻偷看 / Zero Lookahead Bias）。
     - **異常數據掃描**：全池無未還原分割異常。
     - **四重機構門檻**：夏普維持率 $\ge 0.7$（實測 TW 2.14 / US 1.35）、超額 Alpha $> 0$、回撤擴大比 $\le 1.5$。
     - **多切分點步進**：跨多個歷史時點 Walk-Forward 測試，Alpha 全數為正。
     - **隔日開盤成交抗性 (T+1 Open)**：延遲至隔日市價成交，年化報酬仍維持 45% ~ 59%。

6. **雙時區 GitHub Actions 排程 (100% 零成本)**：
   - 台股收盤排程：**14:30 TST (UTC 06:30)**，結算盤勢與晨報推播。
   - 美股收盤排程：**05:15 / 06:15 TST (UTC 21:15 / 22:15)**，結算夜盤與夜報推播。
   - 移除 `on: push` 觸發，徹底杜絕 GitHub 雲端與本地衝突分岔。

---

### 三、專案結構

```
TQA/
├── .github/workflows/
│   └── daily_schedule.yml      # GitHub Actions 雙時區定時自動執行工作流
├── src/
│   ├── config.py               # 股票池定義、動量權重與風控參數
│   ├── data_loader.py          # FinMind 主力 + yfinance 備援之數據下載引擎
│   ├── features.py             # 多因子技術指標計算與動態天梯排序
│   ├── backtester.py           # 向量化回測引擎、基準對比與績效評估
│   ├── trader.py               # 自動模擬下單邏輯與零股資金管理
│   ├── portfolio.py            # Google Sheets / Supabase 雲端持倉與 8% 風控追蹤
│   ├── notifier.py             # LINE Messaging API 圖文排程推播模組
│   ├── web_generator.py        # TradingView 互動式暗黑儀表板生成器
│   └── mascot_data.py          # 儀表板小黃雞吉祥物桌寵互動模組
├── index.html                  # 靜態響應式看盤網站 (自動部署至 GitHub Pages)
├── portfolio.json              # 本地持股庫存與成本紀錄 (雲端斷線時之備援)
├── run_daily.py                # 每日定時自動化主程式 (--market TW/US/AUTO)
├── run_backtest.py             # 全歷史回測執行腳本
├── oos_validation.py           # 機構級五大樣本外盲測與防偷看檢驗腳本
├── test_full_system.py         # 全系統 6 大模組自動化驗收測試腳本
├── requirements.txt            # Python 依賴清單 (精簡無膨脹)
└── .env.example                # 環境變數設定範本 (LINE API、雲端試算表等)
```

---

### 四、快速上手

#### 1. 環境安裝
```bash
git clone https://github.com/z930131tony/TQA-tech-quant-assistant-.git
cd TQA-tech-quant-assistant-
pip install -r requirements.txt
```

#### 2. 設定環境變數
複製 `.env.example` 為 `.env`，填入個人設定（選用）：
```env
# LINE 推播 (選填)
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_USER_ID=your_id

# Google Sheets 雲端持倉 (選填，手機維護首選)
PORTFOLIO_SHEET_URL=https://docs.google.com/spreadsheets/d/e/.../pub?output=csv
```

#### 3. 核心指令操作
- **執行全系統 6 大模組自我測試**：
  ```bash
  python test_full_system.py
  ```
- **執行機構級樣本外 (OOS) 檢驗**：
  ```bash
  python oos_validation.py --skip-data
  ```
- **手動執行每日量化排程並生成網頁**：
  ```bash
  python run_daily.py --market AUTO
  ```
- **執行歷史回測分析**：
  ```bash
  python run_backtest.py
  ```

---

<a id="english"></a>
## 🌐 English

### 1. Overview

**TQA (Tech Quant Assistant)** is an institutional-grade quantitative momentum rotation and automated risk management system designed specifically for **41 elite technology leaders across Taiwan and US markets**.

Powered by **FinMind split/dividend-adjusted historical feeds**, **multi-factor composite momentum rankings**, **market breadth/moving-average regime filters**, **cloud portfolio synchronization via Google Sheets**, and **omnichannel notifications (LINE Messaging API + TradingView interactive web dashboard)**. TQA runs entirely serverless on GitHub Actions, achieving 100% free operation, zero Git conflicts, and disciplined execution.

---

### 2. Key Architectural Features

1. **Dual-Market Tech Universe (41 Equities)**:
   - **Taiwan Tech Giants (20 Equities)**: TSMC (2330.TW), MediaTek (2454.TW), Foxconn (2317.TW), Quanta (2382.TW), Delta (2308.TW), Auras (3324.TWO), Jentech (6223.TWO), etc., benchmarked against Taiwan 50 (0050.TW).
   - **US Tech Leaders (21 Equities)**: NVDA, AAPL, MSFT, AMZN, GOOGL, META, TSLA, AVGO, AMD, ASML, PLTR, etc., benchmarked against QQQ and SMH.

2. **Resilient Dual-Source Data Engine**:
   - **FinMind Official API (Primary)**: Clean, split- and dividend-adjusted daily bars for Taiwan equities, completely eliminating yfinance stock split anomalies (e.g. unadjusted 1:7 splits) and cloud IP rate limits.
   - **yfinance Smart Failover**: Handles US equities with automatic fallback protection if upstream feeds experience downtime.

3. **Multi-Factor Momentum & Dynamic Regime Filter**:
   - **Composite Momentum**: Weighted composite scoring across 20-day (40%), 60-day (35%), and 120-day (25%) Rate of Change (ROC).
   - **Technical Filters**: 50-day SMA trendline, 200-day long-term support, 20-day new-high breakouts, and ATR volatility scaling.
   - **Market Regime Protection**: Automatically shifts portfolio into 100% cash preservation mode when market breadth deteriorates.

4. **Cloud-Native Portfolio & Mobile Management**:
   - **Google Sheets Integration**: Set `PORTFOLIO_SHEET_URL` to sync live positions. Update position shares or costs from the Google Sheets mobile app without touching code or Git.
   - **Dual-Adapter Design**: Supports Supabase REST API and graceful offline fallback to local `portfolio.json`.
   - **8% Trailing Stop & Profit Lock**: Tracks post-entry swing peaks, firing automated exit alerts when drawdown reaches 8%.

5. **Institutional Out-of-Sample (OOS) Validation**:
   - Validated via `oos_validation.py` against institutional benchmarks:
     - **Causality & Lookahead Audit**: Multiplies future prices by 10x; verified 0.000000 indicator deviation (Zero Lookahead Bias).
     - **Four-Point OOS Criteria**: Sharpe retention ratio $\ge 0.70$ (Observed: TW 2.14 / US 1.35), positive excess Alpha, MDD expansion $\le 1.50$.
     - **Multi-Split Walk-Forward**: Consistently positive Alpha across multiple historical cutoffs.
     - **T+1 Execution Latency Resistance**: Validated under next-day market open fills, preserving 45%–59% CAGR.

6. **Dual-Timezone GitHub Actions Scheduler (Serverless & Free)**:
   - Taiwan Market Close: **14:30 TST (UTC 06:30)**.
   - US Market Close: **05:15 / 06:15 TST (UTC 21:15 / 22:15)**.
   - Completely decouples `on: push` triggers to permanently prevent Git divergence loops.

---

### 3. Project Structure

```
TQA/
├── .github/workflows/
│   └── daily_schedule.yml      # Dual-timezone GitHub Actions automated workflow
├── src/
│   ├── config.py               # Stock universe, momentum weights & risk thresholds
│   ├── data_loader.py          # Primary FinMind + secondary yfinance data engine
│   ├── features.py             # Multi-factor technical computation & ranking
│   ├── backtester.py           # Vectorized backtester & performance analytics
│   ├── trader.py               # Simulation trading engine & fractional budgeting
│   ├── portfolio.py            # Google Sheets / Supabase cloud portfolio & trailing stops
│   ├── notifier.py             # LINE Messaging API push notification delivery
│   ├── web_generator.py        # TradingView interactive dark dashboard generator
│   └── mascot_data.py          # Interactive mascot companion module
├── index.html                  # Responsive dashboard deployed to GitHub Pages
├── portfolio.json              # Local fallback portfolio cache
├── run_daily.py                # Main automated execution runner (--market TW/US/AUTO)
├── run_backtest.py             # Full historical backtest runner
├── oos_validation.py           # Institutional OOS validation & causality audit suite
├── test_full_system.py         # 6-in-1 automated end-to-end self-test suite
├── requirements.txt            # Minimal Python dependencies
└── .env.example                # Environment variable configuration template
```

---

### 4. Getting Started

#### 1. Installation
```bash
git clone https://github.com/z930131tony/TQA-tech-quant-assistant-.git
cd TQA-tech-quant-assistant-
pip install -r requirements.txt
```

#### 2. Configuration
Copy `.env.example` to `.env` and configure your credentials (optional):
```env
# LINE Push Notifications (Optional)
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_USER_ID=your_id

# Google Sheets Mobile Portfolio Sync (Optional)
PORTFOLIO_SHEET_URL=https://docs.google.com/spreadsheets/d/e/.../pub?output=csv
```

#### 3. Core Commands
- **Run Full 6-in-1 System Self-Test**:
  ```bash
  python test_full_system.py
  ```
- **Run Institutional OOS Validation Audit**:
  ```bash
  python oos_validation.py --skip-data
  ```
- **Run Daily Production Pipeline**:
  ```bash
  python run_daily.py --market AUTO
  ```
- **Run Historical Backtest**:
  ```bash
  python run_backtest.py
  ```

---

### ⚖️ Disclaimer / 免責聲明

本專案僅供量化策略研究與教育用途，不構成任何形式的投資建議。使用者需自行承擔金融市場實際交易之所有損益與風險。  
*This repository is for research and educational purposes only. It does not constitute financial or investment advice.*
