# 專案規範 (Project Rules)

## 1. 簡潔至上 (Code Simplicity & Anti-Bloat)
- **拒絕代碼膨脹**：嚴禁生成過度包裝、無實質效益的樣板程式碼（Boilerplate）或過度抽象的設計模式。
- **直觀可讀**：以最直接、簡短、清晰的方式解決問題，優先考慮現有語言特性與標準函式庫，不增加非必要的中間層或過度封裝。
- **精準實現**：只寫滿足當前需求所需的代碼，不預寫未經驗證的未來擴展邏輯。

## 2. 文案與對話規範 (Copywriting & Dialogue Standards)
- **自然對話感**：說明與 UI 文案必須具備對話感、親切且專業。
- **短句為主**：以短句為主，句子結構扁平清晰，避免複雜巢狀從句。
- **拒絕翻譯腔**：嚴禁歐化長句、生硬翻譯語法（如過多的「被進行」、「作為一個...」、「進行了一個...的動作」等）與機械化句型。

## 3. 思維與執行模式 (Thinking & Execution Mode)
- **直切核心**：規劃任務與回覆時直接指明問題關鍵、核心邏輯與可執行步驟。
- **摒棄贅言**：嚴禁撰寫冗長無用的寒暄、客套開場白、形式化自我吹捧與過度的自我誇飾。
- **結果導向**：聚焦於代碼產出、關鍵決策與具體驗證，溝通簡潔俐落。

---

# TQA (Tech Quant Assistant) — Workspace Rules

## 4. 量化嚴謹性與防偷看鐵律 (Anti-Lookahead & Causality)
- **嚴禁未來資訊**：嚴禁在 `src/features.py` 使用任何包含未來資訊的函數（如未 `.shift(1)` 的當日高低點突破比對、全樣本標準化 `z-score`、或跨日 `bfill()`）。
- **杜絕死代碼**：任何新增於 `src/features.py` 的技術或籌碼特徵，必須同步接線至 `src/backtester.py` 進行歷史回測驗證，禁止產生只顯示在前端 `index.html` 卻未經回測檢驗的死代碼（Dead Code）。
- **強制因果驗證**：每次修改 `src/features.py` 或 `src/backtester.py` 後，Agent 必須強制在終端機執行 `python oos_validation.py --skip-data`，確認【檢驗 1：未來數據篡改 10 倍因果測試】所有指標之 `max_diff == 0.000000`。

## 5. 實盤交易擬真規範 (Execution Realism)
- **隔日開盤執行**：回測引擎 (`src/backtester.py`) 預設執行模式必須維持 `execution_mode = "next_open"`（T 日收盤產生訊號，T+1 日開盤價成交）。
- **隔離基準標的**：基準標的（`0050.TW`、`QQQ`）僅作為 Market Regime Filter（大盤多空濾網）與 Benchmark 績效對照，嚴禁混入個股 `candidates` 選股池中買賣。
- **雙軌風控防線**：風險控制必須嚴格維持雙軌制：`-8%` 移動停利停損（`trailing_stop_pct = 0.08`，進場隔日後啟動）與 `-30%` 戰術絕對硬停損線（`hard_stop_pct = 0.30`）。

## 6. 嚴禁空殼測試 (No Dummy Stubs)
- **真實數學斷言**：嚴禁在驗證腳本（`oos_validation.py`、`verify_step1.py`、`test_full_system.py`）中撰寫無實質數學斷言卻直接回傳 `"status": "PASS"` 或 `True` 的空殼函數。
- **實盤下單防護**：整合永豐金 `shioaji` API (`run_shioaji.py` / `src/trader.py`) 時，所有下單邏輯必須包含完整的 `try-except` 異常攔截與零股最小交易單位校驗。
