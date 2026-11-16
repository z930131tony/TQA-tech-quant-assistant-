# TQA (Tech Quant Assistant) 專案規範

## 1. 量化嚴謹性與防偷看鐵律 (Anti-Lookahead & Causality)
- **嚴禁未來資訊**：嚴禁在 `src/features.py` 使用任何包含未來資訊的函數（如未 `.shift(1)` 的當日高低點突破比對、全樣本標準化 `z-score`、或跨日 `bfill()`）。
- **杜絕死代碼**：任何新增於 `src/features.py` 的技術或籌碼特徵，必須同步接線至 `src/backtester.py` 進行歷史回測驗證，禁止產生只顯示在前端 `index.html` 卻未經回測檢驗的死代碼（Dead Code）。
- **強制因果驗證**：每次修改 `src/features.py` 或 `src/backtester.py` 後，必須在終端機執行 `python oos_validation.py --skip-data`，確認【檢驗 1：未來數據篡改 10 倍因果測試】所有指標之 `max_diff == 0.000000`。本機 Windows 的 `python` 是商店捷徑、不會真的執行，請改用 `py oos_validation.py --skip-data`。

## 2. 實盤交易擬真規範 (Execution Realism)
- **隔日開盤執行**：回測引擎 (`src/backtester.py`) 預設執行模式必須維持 `execution_mode = "next_open"`（T 日收盤產生訊號，T+1 日開盤價成交）。
- **隔離基準標的**：基準標的（`0050.TW`、`QQQ`）僅作為 Market Regime Filter（大盤多空濾網）與 Benchmark 績效對照，嚴禁混入個股 `candidates` 選股池中買賣。
- **雙軌風控防線**：風險控制必須嚴格維持雙軌制：`-8%` 移動停利停損（`trailing_stop_pct = 0.08`，進場隔日後啟動）與 `-30%` 戰術絕對硬停損線（`hard_stop_pct = 0.30`）。

## 3. 嚴禁空殼測試 (No Dummy Stubs)
- **真實數學斷言**：嚴禁在驗證腳本（`oos_validation.py`、`test_full_system.py`）中撰寫無實質數學斷言卻直接回傳 `"status": "PASS"` 或 `True` 的空殼函數。
- **實盤下單防護**：整合永豐金 `shioaji` API (`run_shioaji.py` / `src/trader.py`) 時，所有下單邏輯必須包含完整的 `try-except` 異常攔截與零股最小交易單位校驗。
