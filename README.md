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

2. **高可靠多層容錯數據架構 (Data Engine)**：
   - **FinMind 官方 API 主力**：台股全面採用 FinMind 還原權息日 K，徹底解決除權息與歷史拆股崩跌失真問題。
   - **curl_cffi 偽裝與指數退避**：美股走 yfinance 搭配 `curl_cffi` 瀏覽器指紋模擬與 3 次 Exponential Backoff 重試，徹底解決雲端 IP 遭 429 速率限制問題。
   - **單一標的防崩潰隔離 (Fault Isolation)**：個別標的連線異常自動記錄警告並優雅跳過，不中斷整體生產排程；整合證交所 OpenAPI 與 Stooq 免費備援。

3. **Numba 加速、夏普動能與多空防禦 (Strategy & Numba Engine)**：
   - **Numba `@njit` 高速向量化**：將 KD 指標與動態迴圈計算大幅加速。
   - **波動率調整後夏普動能**：將動量除以波動率/ATR%，避免追逐暴漲妖股。
   - **量價結構識別**：內建階梯縮量洗盤（`is_shakeout_buy`）與高檔爆量出貨警訊（`is_distribution_warn`）。
   - **雙重風控架構**：8% 移動停利停損 + 30% 戰術絕對硬停損線（Hard Stop-Loss = -30%）。
   - **動態多空防禦**：市場轉弱時主動切換為現金避險模式，全市場跌破 50MA 則 100% 現金觀望。

4. **TradingAgents AI 多空對抗辯論引擎 (Multi-Agent Arena)**：
   - **Gemini 2.5 Flash 免費驅動**：每日自動擷取 Yahoo Finance RSS 即時新聞與技術面量化指標。
   - **三方專業角色攻防**：多頭動能狙擊手 (Bullish Sniper) vs 空頭風控審計官 (Bearish Auditor) vs 首席量化裁決官 (Chief Judge)。
   - **結構化決策與風控錨定**：生成 4 大 Verdict (`STRONG_BUY`, `CAUTIOUS_BUY`, `CASH_DEFENSE`, `SELL`)、-10% 階梯進場價與 -30% 戰術硬停損價。
   - **零依賴優雅降級**：未配置 `GEMINI_API_KEY` 時，自動由量化規則合成裁決，CI/CD 與排程永不中斷。

5. **永豐金證券 Shioaji API 與前端零股精算 (Trading & Portfolio)**：
   - **動態 Shioaji 整合**：採用可選相容架構，本地環境可一鍵連線永豐大戶投同步真實零股持倉至 `portfolio.json`。
   - **半自動安全防呆下單**：依單檔預算精算零股股數與手續費緩衝，終端機必須手動輸入 `CONFIRM` 始送出委託。
   - **前端風控精算面板**：儀表板支援動態預算精算、-10% 階梯價、-30% 硬停損價與 `portfolio.json` 一鍵匯入/匯出。
   - **Google Sheets 雙向同步**：支援環境變數 `PORTFOLIO_SHEET_URL`，在手機打開 Google 試算表 App 隨時調整持倉與成本，免改代碼、免動 Git。

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

6. **機構級樣本外檢驗與 PyBroker 截面驗證 (Institutional OOS & PyBroker Audit)**：
   - 內建 `oos_validation.py`，通過六大嚴苛檢驗標準：
     - **特徵因果檢驗**：未來數據放大 10 倍注入，過去 32 項指標絕對差異 0.000000（0 前瞻偷看 / Zero Lookahead Bias）。
     - **異常數據掃描**：全池 41 檔無拆股除權異常、0 筆成交量 $\le 0$ 幽靈 K 棒，日期與基準 100% 同步。
     - **四重機構門檻 (切分點 2025-06-30)**：
       - 夏普維持率 (OOS/IS $\ge 0.70$)：台股 **1.74** / 美股 **1.61**
       - 樣本外超額 Alpha ($> 0.0\%$)：台股 **+3.64%** / 美股 **+113.6%**
       - 回撤擴大比 (OOS/IS $\le 1.50$)：台股 **1.23** / 美股 **1.05**
       - 樣本外平倉勝率：台股 **51.9%** (79 筆) / 美股 **51.3%** (78 筆)
     - **多切分點步進**：Walk-Forward 測試所有切分點（2024-12-31, 2025-03-31, 2025-06-30）超額 Alpha 全數為正。
     - **隔日開盤成交抗性 (T+1 Open Execution)**：延遲至隔日開盤市價買賣，年化報酬仍高達台股 **+61.94%** (夏普 1.34)、美股 **+65.84%** (夏普 1.35)。
     - **PyBroker 截面輪動驗證**：整合 `lib-pybroker` 跨標的截面輪動架構，消除參數過度擬合（Anti-Overfitting）。

7. **靜態互動儀表板、AI 戰情卡與零股風控精算 (Web Dashboard)**：
   - **TradingAgents AI 多空戰情卡片**：將三方攻防與首席量化裁決視覺化呈現於首頁。
   - **大戶投零股配置與風控精算面板**：純前端試算工具（連動 `localStorage`），即時計算建議進場股數、手續費、-10% 階梯價與 -30% 戰術硬停損價。
   - **持倉 JSON 匯入/匯出**：網頁端可一鍵下載或上傳 `portfolio.json`。
   - **TradingView 互動暗黑儀表板**：自動生成專業級 K 線技術圖表與動態天梯榜單。
   - **小黃雞吉祥物伴讀桌寵**：即時視窗巡邏陪伴，提醒紀律風控。

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
│   ├── data_loader.py          # FinMind 主力 + yfinance 備援 + curl_cffi 偽裝之數據下載引擎
│   ├── features.py             # Numba 向量化技術指標、夏普動量與量價結構
│   ├── backtester.py           # 向量化與 PyBroker 截面動能回測、雙重風控架構
│   ├── trader.py               # 永豐 Shioaji API 同步、半自動零股委託防呆下單
│   ├── portfolio.py            # Google Sheets 雲端持倉、-8% 移動停損與 -30% 戰術硬停損
│   ├── ai_debate.py            # TradingAgents AI 多空對抗辯論模組 (Gemini 2.5 Flash)
│   ├── notifier.py             # LINE Messaging API 圖文排程推播與 AI 裁決摘要
│   ├── web_generator.py        # TradingView 互動暗黑儀表板、AI 戰情室與零股精算面板
│   └── mascot_data.py          # 儀表板吉祥物小黃雞桌寵互動模組
├── index.html                  # 靜態響應式看盤網站 (自動部署至 GitHub Pages)
├── portfolio.json              # 本地持股庫存與成本紀錄 (雲端斷線時之備援)
├── run_daily.py                # 每日定時自動化主程式 (--market TW/US/AUTO, --skip-data)
├── run_simulation.py           # 虛擬交易與個人庫存移動停損評估腳本 (--market, --skip-data)
├── run_backtest.py             # 全歷史回測執行腳本 (--skip-data)
├── oos_validation.py           # 機構級六大樣本外盲測、PyBroker 截面驗證與防偷看檢驗腳本 (--skip-data)
├── verify_step1.py             # 41 檔股票池動能評分與多空生命線快速檢驗腳本 (--skip-data)
├── generate_web.py             # 獨立生成靜態看盤網站儀表板腳本 (--skip-data)
├── test_full_system.py         # 全系統 8 大模組自動化驗收測試腳本
├── requirements.txt            # Python 核心依賴清單
├── requirements-local.txt      # 永豐金證券 Shioaji 本地環境選用依賴
└── .env.example                # 環境變數設定範本 (LINE API、Shioaji、Gemini API)
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

2. **Resilient Multi-Tier Fault-Tolerant Data Architecture**:
   - **FinMind Official API (Primary)**: Clean, split- and dividend-adjusted daily bars for Taiwan equities, eliminating yfinance unadjusted split anomalies.
   - **curl_cffi Chrome Impersonation & Backoff**: Seamlessly bypasses Yahoo Finance cloud rate limits (429) using browser TLS fingerprinting and 3x exponential backoff.
   - **Single-Ticker Fault Isolation**: Individual network hiccups log warnings without halting the overall production pipeline, with free fallback to TWSE OpenAPI and Stooq.

3. **Numba High-Speed Features & PyBroker Cross-Sectional Engine**:
   - **Numba `@njit` Vectorization**: Accelerates KD oscillator loops and feature engineering.
   - **Volatility-Adjusted Momentum**: Normalizes ROC by period volatility/ATR% to avoid chasing low-liquidity parabolic spikes.
   - **Volume-Price Pattern Detection**: Flags 10% pullback volume contraction (`is_shakeout_buy`) and distribution warning signals (`is_distribution_warn`).
   - **Dual Risk Shield**: Combines -8% trailing stop with a -30% tactical hard stop-loss.

4. **TradingAgents AI Multi-Agent Debate Arena**:
   - **Gemini 2.5 Flash Free Tier**: Ingests technical summaries and real-time Yahoo Finance RSS news headlines.
   - **Tri-Agent Adversarial Debate**: Bullish Sniper vs. Bearish Risk Auditor vs. Chief Quant Judge.
   - **Structured Verdicts**: Outputs `STRONG_BUY`, `CAUTIOUS_BUY`, `CASH_DEFENSE`, or `SELL` with -10% step-buy and -30% hard stop price targets.
   - **Graceful Fallback**: Synthesizes quantitative verdicts automatically when `GEMINI_API_KEY` is not configured.

5. **SinoPac Shioaji API & Interactive Frontend Risk Panel**:
   - **Dynamic Shioaji Integration**: Synchronizes odd-lot portfolio holdings to `portfolio.json` locally.
   - **Semi-Automatic Order Lock**: Requires manual terminal `CONFIRM` input before submitting real or simulated odd-lot orders.
   - **Frontend Budget & Risk Panel**: Interactive budgeting calculator, fee buffer calculation, key risk levels, and one-click JSON import/export.
   - **Google Sheets Mobile Sync**: Maintains dual support for cloud position updates via mobile spreadsheet.

6. **Institutional Out-of-Sample (OOS) & PyBroker Validation**:
   - Validated via `oos_validation.py` against 6 institutional benchmarks:
     - **Causality & Lookahead Audit**: Multiplied future prices by 10x; verified 0.000000 indicator deviation across 32 features (Zero Lookahead Bias).
     - **Data Anomaly Verification**: Zero unadjusted split drops, zero volume $\le 0$ phantom bars, 100% synchronized benchmark dates.
     - **Four-Point OOS Criteria (Cutoff 2025-06-30)**:
       - Sharpe Retention Ratio (OOS/IS $\ge 0.70$): TW **1.74** / US **1.61**
       - Out-of-Sample Alpha ($> 0.0\%$): TW **+3.64%** / US **+113.6%**
       - MDD Expansion Ratio (OOS/IS $\le 1.50$): TW **1.23** / US **1.05**
       - OOS Closed Trade Win Rate: TW **51.9%** (79 trades) / US **51.3%** (78 trades)
     - **Multi-Split Walk-Forward**: Consistently positive Alpha across multiple historical cutoffs (2024-12-31, 2025-03-31, 2025-06-30).
     - **T+1 Execution Latency Resistance**: Validated under next-day market open fills, preserving **+61.94%** CAGR (Sharpe 1.34) in TW and **+65.84%** CAGR (Sharpe 1.35) in US.
     - **PyBroker Cross-Sectional Validation**: Validates multi-asset cross-sectional momentum ranking to eliminate overfitting.

7. **Interactive Web Dashboard & AI Debate Cards**:
   - **AI Multi-Agent Arena**: Visualizes Bullish vs Bearish debates and Chief Judge verdicts.
   - **Fractional Budgeting & Risk Panel**: Real-time position shares, fee estimates, and -10% / -30% risk anchor levels.
   - **Portfolio JSON Import/Export**: Directly upload or download `portfolio.json` from the browser.
   - **TradingView Dark Theme Charts**: Interactive technical charts with dynamic momentum ladder rankings.
   - **Mascot Companion**: Interactive wandering mascot promoting disciplined trading habits.

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
│   ├── data_loader.py          # Primary FinMind + secondary yfinance + curl_cffi engine
│   ├── features.py             # Numba vectorization, volatility-adjusted momentum & volume signals
│   ├── backtester.py           # Vectorized & PyBroker cross-sectional backtester with dual stops
│   ├── trader.py               # SinoPac Shioaji integration & semi-auto odd-lot execution lock
│   ├── portfolio.py            # Google Sheets cloud portfolio, -8% trailing & -30% hard stops
│   ├── ai_debate.py            # TradingAgents AI multi-agent debate module (Gemini 2.5 Flash)
│   ├── notifier.py             # LINE Messaging API push delivery with AI debate summary
│   ├── web_generator.py        # TradingView dashboard, AI debate arena & budgeting panel
│   └── mascot_data.py          # Interactive mascot companion module
├── index.html                  # Responsive dashboard deployed to GitHub Pages
├── portfolio.json              # Local fallback portfolio cache
├── run_daily.py                # Main automated execution runner (--market TW/US/AUTO, --skip-data)
├── run_simulation.py           # Virtual execution & trailing stop evaluator (--market, --skip-data)
├── run_backtest.py             # Full historical backtest runner (--skip-data)
├── oos_validation.py           # 6-in-1 institutional OOS & PyBroker validation suite (--skip-data)
├── verify_step1.py             # Quick universe scoring & market regime verification (--skip-data)
├── generate_web.py             # Standalone static web dashboard generator (--skip-data)
├── test_full_system.py         # 8-in-1 automated end-to-end self-test suite
├── requirements.txt            # Minimal Python core dependencies
├── requirements-local.txt      # Optional local SinoPac Shioaji dependencies
└── .env.example                # Environment variable configuration template
```

---

### 4. Getting Started

#### 1. Installation
```bash
git clone https://github.com/z930131tony/TQA-tech-quant-assistant-.git
cd TQA-tech-quant-assistant-
pip install -r requirements.txt
# Optional local SinoPac Shioaji API:
# pip install -r requirements-local.txt
```

#### 2. Configuration
Copy `.env.example` to `.env` and configure your credentials (optional):
```env
# LINE Push Notifications (Optional)
LINE_CHANNEL_ACCESS_TOKEN=your_token
LINE_USER_ID=your_id

# Google Sheets Mobile Portfolio Sync (Optional)
PORTFOLIO_SHEET_URL=https://docs.google.com/spreadsheets/d/e/.../pub?output=csv

# Google Gemini API (Optional for AI Debate, graceful fallback if empty)
GEMINI_API_KEY=your_gemini_api_key
```

#### 3. Core Commands
- **Run Full 8-in-1 System Self-Test**:
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
