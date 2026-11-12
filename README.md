# 🚀 TQA: Tech Quant Assistant (台美純科技股量化交易系統)

<p align="center">
  <a href="#繁體中文"><b>繁體中文</b></a> | <a href="#english"><b>English</b></a>
</p>

---

<a id="繁體中文"></a>
## 🇹🇼 繁體中文

### 一、系統簡介

**TQA (Tech Quant Assistant)** 是專為**台美兩大市場頂尖科技龍頭（41 檔）**設計的專業級量化輪動與即時風控系統。

系統整合 **FinMind API 還原權息行情**、**多因子複合動能評分**、**大盤生命線多空濾網**、**手機 Google 試算表雲端持倉同步** 與 **全通路即時推播（LINE 官方通知 + TradingView 互動式儀表板）**。透過 GitHub Actions 每日定時無伺服器（Serverless）自動運算，達到零營運成本、高紀律性之波段獲利目標。

---

### 二、核心架構與亮點

1. **41 檔頂尖科技宇宙 (Tech Universe)**：
   - **台股科技領航 (20 檔)**：台積電 (2330)、聯發科 (2454)、鴻海 (2317)、廣達 (2382)、台達電 (2308)、奇鋐 (3017)、健策 (3653)、創意 (3443) 等 AI/半導體核心供應鏈，以元大台灣50 (0050.TW) 為基準。
   - **美股科技巨擘 (21 檔)**：NVDA、AAPL、MSFT、AMZN、GOOGL、META、TSLA、AVGO、AMD、ASML、PLTR 等巨頭，以 QQQ (那斯達克100) 與 SMH (半導體ETF) 為基準。

2. **高可靠雙引擎數據架構 (Data Engine)**：
   - **FinMind 官方 API 主力**：台股全面採用 FinMind 還原權息日 K，徹底解決除權息與歷史拆股崩跌失真問題。
   - **yfinance 智慧容錯備援**：美股走 yfinance，台股網路異常時自動優雅降級切換。

3. **多因子複合動能與大盤多空防禦 (Strategy & Regime Filter)**：
   - **複合動量評分**：結合 20日 (40%)、60日 (35%)、120日 (25%) 變動率 (ROC) 天梯排序。
   - **技術過濾**：50MA 生命線、200MA 長期年線支撐、20日創新高、ATR 波動度調適。
   - **動態多空防禦**：市場轉弱時主動切換為現金避險模式，全市場跌破 50MA 則 100% 現金觀望。

4. **雲端持倉同步與手機即時維護 (Cloud Portfolio)**：
   - **Google Sheets 雙向同步**：支援環境變數 `PORTFOLIO_SHEET_URL`，在手機打開 Google 試算表 App 隨時調整持倉與成本，免改代碼、免動 Git。
   - **雙軌架構**：支援 Supabase REST API 讀取，並具備本地 `portfolio.json` 離線平穩回退機制。
   - **8% 移動停利停損**：動態追蹤買進後波段最高價，自高點回檔滿 8% 即刻觸發平倉警報。

5. **全歷史實測回測績效 (Historical Backtest Performance)**：
   - **台股 (TW，2024-02-15 ~ 2026-11-11，基準 0050.TW)**：
     - 策略總報酬：**+325.58%** (年化 CAGR **+72.98%**)
     - 夏普比率 (Sharpe)：**1.49**，最大回撤 (MDD)：**-23.97%**
     - 超額報酬 (Alpha)：**+121.96%** (基準 0050 同期 +203.62%)
     - 已平倉交易：156 筆，勝率：**48.08%**
   - **美股 (US，2024-02-09 ~ 2026-11-11，基準 QQQ)**：
     - 策略總報酬：**+246.03%** (年化 CAGR **+57.15%**)
     - 夏普比率 (Sharpe)：**1.22**，最大回撤 (MDD)：**-42.66%**
     - 超額報酬 (Alpha)：**+184.74%** (基準 QQQ 同期 +61.29%)
     - 已平倉交易：150 筆，勝率：**50.00%**

6. **機構級樣本外檢驗 (Institutional OOS Audit)**：
   - 內建 `oos_validation.py`，通過五大嚴苛檢驗標準：
     - **特徵因果檢驗**：未來數據放大 10 倍注入，過去指標絕對差異 0.000000（0 前瞻偷看 / Zero Lookahead Bias）。
     - **異常數據掃描**：全池 41 檔無拆股除權異常、0 筆成交量 $\le 0$ 幽靈 K 棒，日期與基準 100% 同步。
     - **四重機構門檻 (切分點 2025-06-30)**：
       - 夏普維持率 (OOS/IS $\ge 0.70$)：台股 **2.26** / 美股 **1.85**
       - 樣本外超額 Alpha ($> 0.0\%$)：台股 **+25.82%** / 美股 **+129.83%**
       - 回撤擴大比 (OOS/IS $\le 1.50$)：台股 **1.10** / 美股 **1.05**
       - 樣本外平倉勝率：台股 **53.1%** (81 筆) / 美股 **51.3%** (78 筆)
     - **多切分點步進**：Walk-Forward 測試所有切分點（2024-12-31, 2025-03-31, 2025-06-30）超額 Alpha 全數為正。
     - **隔日開盤成交抗性 (T+1 Open Execution)**：延遲至隔日開盤市價買賣，年化報酬仍高達台股 **+58.68%** (夏普 1.29)、美股 **+63.61%** (夏普 1.31)。

7. **靜態互動儀表板與零股/複委託預算試算 (Web Dashboard)**：
   - **大戶投零股 / 複委託預算試算**：內建純前端試算工具（台股預設 NT$ 30,000、美股預設 USD 1,000，連動 `localStorage`），即時計算建議進場股數與 -8% 移動停損價。
   - **TradingView 互動暗黑儀表板**：自動生成專業級 K 線技術圖表與動態天梯榜單。
   - **雙引擎資料來源透明標示**：頁尾清楚載明 `FinMind / Yahoo Finance` 數據來源。

8. **雙時區 GitHub Actions 排程 (100% 零成本)**：
   - 台股收盤排程：**14:30 TST (UTC 06:30)**，結算盤勢並推播操作建議。
   - 美股收盤排程：**05:15 TST (UTC 21:15)**，結算夜盤並推播夜報。
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
│   ├── trader.py               # 自動模擬下單邏輯與資金管理
│   ├── portfolio.py            # Google Sheets / Supabase 雲端持倉與 8% 風控追蹤
│   ├── notifier.py             # LINE Messaging API 圖文排程推播模組
│   ├── web_generator.py        # TradingView 互動式暗黑儀表板生成器
│   └── mascot_data.py          # 儀表板吉祥物桌寵互動模組
├── index.html                  # 靜態響應式看盤網站 (自動部署至 GitHub Pages)
├── portfolio.json              # 本地持股庫存與成本紀錄 (雲端斷線時之備援)
├── run_daily.py                # 每日定時自動化主程式 (--market TW/US/AUTO, --skip-data)
├── run_simulation.py           # 虛擬交易與個人庫存移動停損評估腳本 (--market, --skip-data)
├── run_backtest.py             # 全歷史回測執行腳本 (--skip-data)
├── oos_validation.py           # 機構級五大樣本外盲測與防偷看檢驗腳本 (--skip-data)
├── verify_step1.py             # 41 檔股票池動能評分與多空生命線快速檢驗腳本 (--skip-data)
├── generate_web.py             # 獨立生成靜態看盤網站儀表板腳本 (--skip-data)
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
- **執行全系統 6 大模組自動化驗收**：
  ```bash
  python test_full_system.py
  ```
- **執行機構級樣本外 (OOS) 盲測檢驗**（支援極速離線驗證）：
  ```bash
  python oos_validation.py --skip-data
  ```
- **執行歷史回測分析**：
  ```bash
  python run_backtest.py --skip-data
  ```
- **快速檢驗 41 檔科技池評分與多空狀態**：
  ```bash
  python verify_step1.py --skip-data
  ```
- **執行虛擬交易與個人部位風控評估**：
  ```bash
  python run_simulation.py --market AUTO --skip-data
  ```
- **生成靜態看盤網站 (index.html)**：
  ```bash
  python generate_web.py --skip-data
  ```
- **手動執行每日完整生產排程**：
  ```bash
  python run_daily.py --market AUTO
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
   - **Taiwan Tech Leaders (20 Equities)**: TSMC (2330.TW), MediaTek (2454.TW), Foxconn (2317.TW), Quanta (2382.TW), Delta (2308.TW), Auras (3324.TWO), Jentech (6223.TWO), Creative (3443.TW), etc., benchmarked against Taiwan 50 (0050.TW).
   - **US Tech Giants (21 Equities)**: NVDA, AAPL, MSFT, AMZN, GOOGL, META, TSLA, AVGO, AMD, ASML, PLTR, etc., benchmarked against QQQ and SMH.

2. **Resilient Dual-Engine Data Architecture**:
   - **FinMind Official API (Primary)**: Clean, split- and dividend-adjusted daily bars for Taiwan equities, eliminating yfinance unadjusted split anomalies and IP rate limits.
   - **yfinance Smart Failover**: Handles US equities with automatic fallback protection if upstream feeds experience downtime.

3. **Multi-Factor Momentum & Dynamic Regime Filter**:
   - **Composite Momentum**: Weighted scoring across 20-day (40%), 60-day (35%), and 120-day (25%) Rate of Change (ROC).
   - **Technical Filters**: 50-day SMA trendline, 200-day long-term support, 20-day new-high breakouts, and ATR volatility scaling.
   - **Market Regime Protection**: Automatically shifts portfolio into 100% cash preservation mode when market breadth breaks below key thresholds.

4. **Cloud-Native Portfolio & Mobile Management**:
   - **Google Sheets Integration**: Set `PORTFOLIO_SHEET_URL` to sync live positions. Update position shares or costs from the Google Sheets mobile app without modifying code or Git.
   - **Dual-Adapter Design**: Supports Supabase REST API and graceful offline fallback to local `portfolio.json`.
   - **8% Trailing Stop & Profit Lock**: Tracks post-entry swing peaks, firing automated exit alerts when drawdown reaches 8%.

5. **Historical Backtest Performance (Full Horizon)**:
   - **Taiwan Market (TW, 2024-02-15 ~ 2026-11-11, Benchmark: 0050.TW)**:
     - Strategy Total Return: **+325.58%** (CAGR: **+72.98%**)
     - Sharpe Ratio: **1.49**, Max Drawdown (MDD): **-23.97%**
     - Excess Alpha: **+121.96%** (Benchmark 0050.TW: +203.62%)
     - Closed Trades: 156, Win Rate: **48.08%**
   - **US Market (US, 2024-02-09 ~ 2026-11-11, Benchmark: QQQ)**:
     - Strategy Total Return: **+246.03%** (CAGR: **+57.15%**)
     - Sharpe Ratio: **1.22**, Max Drawdown (MDD): **-42.66%**
     - Excess Alpha: **+184.74%** (Benchmark QQQ: +61.29%)
     - Closed Trades: 150, Win Rate: **50.00%**

6. **Institutional Out-of-Sample (OOS) Validation**:
   - Validated via `oos_validation.py` against institutional benchmarks:
     - **Causality & Lookahead Audit**: Multiplied future prices by 10x; verified 0.000000 indicator deviation (Zero Lookahead Bias).
     - **Data Anomaly Verification**: Zero unadjusted split drops, zero volume $\le 0$ phantom bars, 100% synchronized benchmark dates.
     - **Four-Point OOS Criteria (Cutoff 2025-06-30)**:
       - Sharpe Retention Ratio (OOS/IS $\ge 0.70$): TW **2.26** / US **1.85**
       - Out-of-Sample Alpha ($> 0.0\%$): TW **+25.82%** / US **+129.83%**
       - MDD Expansion Ratio (OOS/IS $\le 1.50$): TW **1.10** / US **1.05**
       - OOS Closed Trade Win Rate: TW **53.1%** (81 trades) / US **51.3%** (78 trades)
     - **Multi-Split Walk-Forward**: Consistently positive Alpha across multiple historical cutoffs (2024-12-31, 2025-03-31, 2025-06-30).
     - **T+1 Execution Latency Resistance**: Validated under next-day market open fills, preserving **+58.68%** CAGR (Sharpe 1.29) in TW and **+63.61%** CAGR (Sharpe 1.31) in US.

7. **Interactive Web Dashboard & Fractional Budgeting Calculator**:
   - **Fractional / Foreign Broker Budgeting**: Pure frontend interactive widget (TW default NT$ 30,000, US default USD 1,000, linked to `localStorage`), calculating suggested position shares and -8% trailing stop levels in real time.
   - **TradingView Dark Theme Charts**: Interactive technical charts with dynamic momentum ladder rankings.
   - **Data Attribution**: Clearly attributed to `FinMind / Yahoo Finance` dual engines.

8. **Dual-Timezone GitHub Actions Scheduler (Serverless & Free)**:
   - Taiwan Market Close: **14:30 TST (UTC 06:30)**.
   - US Market Close: **05:15 TST (UTC 21:15)**.
   - Decoupled `on: push` triggers to permanently eliminate Git branch divergence loops.

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
├── run_daily.py                # Main automated execution runner (--market TW/US/AUTO, --skip-data)
├── run_simulation.py           # Virtual execution & trailing stop evaluator (--market, --skip-data)
├── run_backtest.py             # Full historical backtest runner (--skip-data)
├── oos_validation.py           # Institutional OOS validation & causality audit suite (--skip-data)
├── verify_step1.py             # Quick universe scoring & market regime verification (--skip-data)
├── generate_web.py             # Standalone static web dashboard generator (--skip-data)
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
- **Run Institutional OOS Validation Audit** (Fast offline mode supported):
  ```bash
  python oos_validation.py --skip-data
  ```
- **Run Historical Backtest**:
  ```bash
  python run_backtest.py --skip-data
  ```
- **Quickly Verify Tech Universe Rankings & Regimes**:
  ```bash
  python verify_step1.py --skip-data
  ```
- **Run Simulated Trading & Trailing Stop Risk Audit**:
  ```bash
  python run_simulation.py --market AUTO --skip-data
  ```
- **Generate Static Web Dashboard (index.html)**:
  ```bash
  python generate_web.py --skip-data
  ```
- **Run Daily Production Pipeline**:
  ```bash
  python run_daily.py --market AUTO
  ```

---

### ⚖️ Disclaimer / 免責聲明

本專案僅供量化策略研究與教育用途，不構成任何形式的投資建議。使用者需自行承擔金融市場實際交易之所有損益與風險。  
*This repository is for research and educational purposes only. It does not constitute financial or investment advice.*
