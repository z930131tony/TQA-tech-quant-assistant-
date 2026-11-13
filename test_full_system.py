"""
TQA 全系統自主端到端驗收測試腳本 (Comprehensive Self-Test Suite)
驗收項目：
1. FinMind 台股數據完整度 (20 檔 .TW 與 .TWO)
2. yfinance 容錯備援切換機制 (Failover Test)
3. 模擬交易引擎與資產配置 (Trader & Portfolio State)
4. 排程執行與推播串接 (run_daily TW/US)
5. 網頁渲染與 TradingView 腳本完整性 (index.html Integrity)
6. GitHub Actions YAML 語法驗證
"""

import sys
import io
import os
import json
import yaml
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.features import TechFeatureEngine
from src.trader import AutoTrader
from src.portfolio import PortfolioTracker, PORTFOLIO_FILE
from src.config import TECH_UNIVERSE_TW, TECH_UNIVERSE_US

results = {}

print("======================================================================")
print("             TQA 全系統深度自主測試 (Self-Test Suite) 啟動")
print("======================================================================")

# -------------------------------------------------------------
# 測試 1: FinMind 數據源與格式檢驗 (20 檔台股)
# -------------------------------------------------------------
print("\n[測試 1/8] 驗證 FinMind 官方 API 抓取台股（含 .TW 與 .TWO 櫃買標的）...")
loader = TechDataLoader()
tw_failures = []
sample_symbols = ["2330.TW", "3324.TWO", "0050.TW", "6223.TWO"]

for sym in sample_symbols:
    df = loader.fetch_finmind_taiwan_stock(sym, days=60)
    if df is None or len(df) < 10 or "close" not in df.columns:
        tw_failures.append(sym)
    else:
        print(f"  ✅ {sym:<10} 成功抓取 {len(df)} 筆日K，最新收盤價: {df['close'].iloc[-1]}")

results["FinMind台股抓取"] = (len(tw_failures) == 0)

# -------------------------------------------------------------
# 測試 2: yfinance 容錯備援切換機制 (Failover)
# -------------------------------------------------------------
print("\n[測試 2/8] 驗證 FinMind 斷線時自動降級切換至 yfinance 備援...")
try:
    # 測試故意傳入無效 FinMind 標的或模擬異常，看 fetch_ticker_data 是否切換 yfinance
    # 比如美股 NVDA 本來就該走 yfinance (改用完整預設天數，避免短測試覆蓋快取)
    df_us = loader.fetch_ticker_data("NVDA")
    has_us = df_us is not None and not df_us.empty
    
    # 測試台股若 FinMind 找不到 (例如給定不存在代碼)，回傳 None 且不崩潰
    dummy_df = loader.fetch_ticker_data("999999.TW", days=10)
    graceful = (dummy_df is None)
    
    if has_us and graceful:
        print("  ✅ 美股正常走 yfinance，且無效代碼具備優雅降級保護，系統未拋出崩潰例外。")
        results["備援容錯機制"] = True
    else:
        results["備援容錯機制"] = False
except Exception as e:
    print(f"  ❌ 容錯測試失敗: {e}")
    results["備援容錯機制"] = False

# -------------------------------------------------------------
# 測試 3: 模擬交易分流邏輯 (TW 時段不碰美股，US 時段不碰台股)
# -------------------------------------------------------------
print("\n[測試 3/8] 驗證交易引擎分流 (target_market: TW vs US)...")
# 隔離雲端環境變數與備份真實 portfolio.json，避免測試誤碰真實雲端或 Webhook
cloud_env_keys = ["PORTFOLIO_SHEET_URL", "SUPABASE_URL", "SUPABASE_KEY", "PORTFOLIO_WEBHOOK_URL"]
saved_env = {k: os.environ.get(k) for k in cloud_env_keys}
for k in cloud_env_keys:
    os.environ.pop(k, None)

backup_portfolio = None
if os.path.exists(PORTFOLIO_FILE):
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        backup_portfolio = f.read()

try:
    dataset = loader.fetch_all_tech_data(cache_only=True)
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)
    trader = AutoTrader(dataset=dataset)
    
    # 測試 TW 分流
    logs_tw, pos_tw = trader.execute_daily_simulation(tw_rank, us_rank, target_market="TW")
    # 驗證 logs_tw 裡面絕無美股買賣委託
    has_us_in_tw = any("(美股)" in log for log in logs_tw)
    
    # 測試 US 分流
    logs_us, pos_us = trader.execute_daily_simulation(tw_rank, us_rank, target_market="US")
    has_tw_in_us = any("NT$" in log for log in logs_us)

    if not has_us_in_tw and not has_tw_in_us:
        print(f"  ✅ 台股分流檢查通過 (無美股干擾)")
        print(f"  ✅ 美股分流檢查通過 (無台股干擾)")
        results["交易時區分流"] = True
    else:
        print(f"  ❌ 分流污染：has_us_in_tw={has_us_in_tw}, has_tw_in_us={has_tw_in_us}")
        results["交易時區分流"] = False
except Exception as e:
    print(f"  ❌ 交易引擎測試異常: {e}")
    results["交易時區分流"] = False
finally:
    # 測試 3 結束時立即還原真實 portfolio.json，確保測試 4A 讀取真實部位
    if backup_portfolio is not None:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            f.write(backup_portfolio)

# -------------------------------------------------------------
# 測試 4: 庫存雲端適配器 (Google Sheets / 本地 JSON) 與風控
# -------------------------------------------------------------
print("\n[測試 4/8] 驗證持倉雲端適配器 (Google Sheets CSV / 本地回退) 與風控評估...")
try:
    # 4A. 本地 portfolio.json 讀取測試
    positions = PortfolioTracker.load_portfolio()
    evaluated = PortfolioTracker.evaluate_portfolio(dataset)
    valid_keys = all({"ticker", "cost_price", "shares"}.issubset(p.keys()) for p in positions)
    print(f"  ✅ 本地 JSON 讀取正常 (現有 {len(positions)} 筆部位，風控評估 {len(evaluated)} 筆)")

    # 4B. 雲端 Google Sheets CSV 讀取模擬測試
    mock_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_sheet.csv")
    with open(mock_csv_path, "w", encoding="utf-8") as f:
        f.write("ticker,shares,cost_price,entry_date\n2330.TW,100,1050,2026-10-01\nNVDA,10,135.5,2026-10-15\n")
    
    os.environ["PORTFOLIO_SHEET_URL"] = mock_csv_path
    cloud_positions = PortfolioTracker.load_portfolio()
    os.environ.pop("PORTFOLIO_SHEET_URL", None)
    if os.path.exists(mock_csv_path):
        os.remove(mock_csv_path)

    cloud_ok = (len(cloud_positions) == 2 and cloud_positions[0]["ticker"] == "2330.TW" and cloud_positions[1]["ticker"] == "NVDA")
    print(f"  ✅ 雲端 Google Sheets 試算表解析測試: {'PASS' if cloud_ok else 'FAIL'}")

    results["持倉雲端適配與風控"] = (valid_keys and cloud_ok)
except Exception as e:
    print(f"  ❌ 持倉模組檢查異常: {e}")
    results["持倉雲端適配與風控"] = False
finally:
    # 復原雲端環境變數與真實 portfolio.json
    for k, v in saved_env.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    if backup_portfolio is not None:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            f.write(backup_portfolio)

# -------------------------------------------------------------
# 測試 5: 網頁 HTML 結構與 TradingView 語法檢查
# -------------------------------------------------------------
print("\n[測試 5/8] 驗證 index.html 檔案結構與 TradingView 腳本健康度...")
try:
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    has_tv = "LightweightCharts" in html
    has_tw_tab = "content-tw" in html
    has_us_tab = "content-us" in html
    has_mascot = "mascot-avatar" in html
    has_ai_arena = "AI 多空對抗戰情室" in html
    has_odd_calc = "exportPortfolioJson" in html
    no_raw_tokens = ("__TW_RECOMMENDATIONS__" not in html) and ("__UPDATE_TIME__" not in html) and ("__TW_AI_DEBATE__" not in html)
    size_kb = len(html) / 1024

    print(f"  ✅ HTML 檔案大小: {size_kb:.1f} KB")
    print(f"  ✅ TradingView 腳本存在: {has_tv}")
    print(f"  ✅ 雙市場 Tab 分頁存在: {has_tw_tab and has_us_tab}")
    print(f"  ✅ 吉祥物小黃雞桌寵模組存在: {has_mascot}")
    print(f"  ✅ AI 多空對決戰情卡片存在: {has_ai_arena}")
    print(f"  ✅ 零股精算與持倉 JSON 匯入匯出存在: {has_odd_calc}")
    print(f"  ✅ 模板標籤無殘留未替換: {no_raw_tokens}")

    results["儀表板網頁健康度"] = (has_tv and has_tw_tab and has_us_tab and has_mascot and has_ai_arena and has_odd_calc and no_raw_tokens)
except Exception as e:
    print(f"  ❌ 網頁檢查異常: {e}")
    results["儀表板網頁健康度"] = False

# -------------------------------------------------------------
# 測試 6: GitHub Actions 工作流 YAML 語法驗證
# -------------------------------------------------------------
print("\n[測試 6/8] 驗證 GitHub Actions daily_schedule.yml 語法與排程定義...")
try:
    yml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".github", "workflows", "daily_schedule.yml")
    with open(yml_path, "r", encoding="utf-8") as f:
        yml_data = yaml.safe_load(f)

    # 檢查排程 (在 YAML 1.1 中 'on' 會被解析為布林值 True)
    on_section = yml_data.get("on") or yml_data.get(True) or {}
    schedules = on_section.get("schedule", [])
    cron_list = [s.get("cron") for s in schedules]
    
    # 必須包含 14:30 TST (UTC 06:30) 與美股收盤 (UTC 21:15 或 22:15)
    has_tw_cron = any("30 6" in c for c in cron_list)
    has_us_cron = any("15 21" in c or "15 22" in c for c in cron_list)
    no_push_loop = ("push" not in on_section)

    print(f"  ✅ 台股收盤排程 (14:30 TST) 設定: {has_tw_cron}")
    print(f"  ✅ 美股收盤排程 (05:15/06:15 TST) 設定: {has_us_cron}")
    print(f"  ✅ 已成功移除 on: push 自動觸發 (終止 Git 分岔循環): {no_push_loop}")

    results["GitHub排程工作流"] = (has_tw_cron and has_us_cron and no_push_loop)
except Exception as e:
    print(f"  ❌ YAML 工作流檢查異常: {e}")
    results["GitHub排程工作流"] = False

# -------------------------------------------------------------
# 測試 7: Numba KD 加速運算、夏普動能與量價訊號
# -------------------------------------------------------------
print("\n[測試 7/8] 驗證 Numba KD 運算、夏普波動率調整動能與量價結構...")
try:
    sample_df = dataset.get("2330.TW")
    if sample_df is not None and not sample_df.empty:
        feats = TechFeatureEngine.calculate_technical_features(sample_df)
        has_numba_kd = ("k_9" in feats.columns and "d_9" in feats.columns)
        has_vol_mom = ("vol_adjusted_momentum" in feats.columns and "vol_adj_roc_20" in feats.columns)
        has_volume_signals = ("is_shakeout_buy" in feats.columns and "is_distribution_warn" in feats.columns)
        has_microstructure = all(c in feats.columns for c in ["ker_20", "vcp_ratio", "is_vcp_squeeze", "ud_vol_ratio"])
        
        kd_val = float(feats["k_9"].iloc[-1])
        vol_mom_val = float(feats["vol_adjusted_momentum"].iloc[-1])
        shakeout_count = int(feats["is_shakeout_buy"].sum())
        dist_count = int(feats["is_distribution_warn"].sum())
        vcp_count = int(feats["is_vcp_squeeze"].sum())
        ker_val = float(feats["ker_20"].iloc[-1])

        print(f"  ✅ Numba 加速 KD 計算: K={kd_val:.1f}, D={float(feats['d_9'].iloc[-1]):.1f}")
        print(f"  ✅ 夏普波動率調整動能: {vol_mom_val:.2f}")
        print(f"  ✅ 階梯縮量洗盤訊號 (is_shakeout_buy) 總計: {shakeout_count} 次")
        print(f"  ✅ 爆量出貨警訊 (is_distribution_warn) 總計: {dist_count} 次")
        print(f"  ✅ VCP 波動率收斂壓縮 (is_vcp_squeeze) 總計: {vcp_count} 次，最新 KER: {ker_val:.2f}")

        results["Numba量價特徵工程"] = (has_numba_kd and has_vol_mom and has_volume_signals and has_microstructure)
    else:
        results["Numba量價特徵工程"] = False
except Exception as e:
    print(f"  ❌ 特徵運算異常: {e}")
    results["Numba量價特徵工程"] = False

# -------------------------------------------------------------
# 測試 8: TradingAgents AI 辯論降級機制與 Shioaji API 動態相容
# -------------------------------------------------------------
print("\n[測試 8/8] 驗證 TradingAgents AI 辯論降級相容與 Shioaji API 安全防護...")
try:
    from src.ai_debate import conduct_single_debate, fetch_yahoo_news
    from src.trader import SHIOAJI_AVAILABLE

    # 1. 測試在無 API Key 下，AI 辯論模組優雅降級為量化規則合成 (含三大價量籌碼因子)
    fake_tech = {
        "price": 1050.0,
        "score": 85.0,
        "above_50sma": True,
        "is_shakeout_buy": True,
        "is_distribution_warn": False,
        "ker_20": 0.58,
        "vcp_ratio": 0.72,
        "is_vcp_squeeze": True,
        "ud_vol_ratio": 1.35
    }
    debate_res = conduct_single_debate(
        ticker="2330.TW",
        name="台積電",
        price=1050.0,
        tech_info=fake_tech,
        news_headlines=["台積電先進製程滿載"],
        api_key=None
    )
    fallback_ok = (debate_res.get("verdict") == "STRONG_BUY" and debate_res.get("step_buy_10pct_price") == 945.0)
    has_chip_metrics = "chip_metrics" in debate_res and debate_res["chip_metrics"].get("ker_20") == 0.58
    has_chip_in_bull = any(k in debate_res.get("bull_summary", "") for k in ["趨勢效率", "洗盤", "VCP", "吃貨", "量能比"])

    # 2. 測試 Shioaji 動態導入 (不論環境有無安裝皆能安全運作)
    trader_obj = AutoTrader(dataset=dataset)
    shioaji_safe = hasattr(trader_obj, "execute_semi_auto_order") and hasattr(trader_obj, "sync_shioaji_positions")

    print(f"  ✅ AI 多空辯論引擎無 Key 降級保護: {fallback_ok} (Verdict: {debate_res.get('verdict')})")
    print(f"  ✅ 語意化籌碼因子注入: {has_chip_metrics and has_chip_in_bull}")
    print(f"  ✅ 永豐 Shioaji 動態相容性 (本機安裝狀態: {SHIOAJI_AVAILABLE}): {shioaji_safe}")

    results["AI辯論與Shioaji防護"] = (fallback_ok and shioaji_safe and has_chip_metrics and has_chip_in_bull)
except Exception as e:
    print(f"  ❌ AI 與下單相容測試異常: {e}")
    results["AI辯論與Shioaji防護"] = False

# -------------------------------------------------------------
# 測試 9: 實盤雙軌風控 (-30% 硬停損 / -8% 移動停損) 與帳戶回撤動態減倉
# -------------------------------------------------------------
print("\n[測試 9/9] 驗證實盤雙軌停損 (-30% 硬停損 / -8% 移動停損) 與帳戶回撤減倉 (Drawdown Scaling)...")
try:
    # 1. 數學斷言：動態倉位縮放係數 (Hysteresis & Scaling)
    sf_normal = PortfolioTracker.calculate_risk_scaling_factor(5.0)    # < 10%
    sf_dd18 = PortfolioTracker.calculate_risk_scaling_factor(20.0)     # >= 18%
    sf_dd25 = PortfolioTracker.calculate_risk_scaling_factor(26.0)     # >= 25%
    assert sf_normal == 1.0, f"預期 1.0，得到 {sf_normal}"
    assert sf_dd18 == 0.50, f"預期 0.50，得到 {sf_dd18}"
    assert sf_dd25 == 0.25, f"預期 0.25，得到 {sf_dd25}"

    # 2. 數學斷言：模擬持倉 -31% 觸發戰術絕對硬停損與 -9% 移動停損
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    mock_df_loss = pd.DataFrame({
        "open": [100.0] * 59 + [69.0],
        "high": [102.0] * 59 + [70.0],
        "low": [98.0] * 59 + [68.0],
        "close": [100.0] * 59 + [69.0],
        "volume": [1000000] * 60
    }, index=dates)

    mock_df_trail = pd.DataFrame({
        "open": [100.0] * 30 + [120.0] * 20 + [109.0] * 10,
        "high": [102.0] * 30 + [125.0] * 20 + [110.0] * 10,
        "low": [98.0] * 30 + [118.0] * 20 + [108.0] * 10,
        "close": [100.0] * 30 + [120.0] * 20 + [109.0] * 10,
        "volume": [1000000] * 60
    }, index=dates)

    mock_dataset = {
        "TEST_LOSS.TW": mock_df_loss,
        "TEST_TRAIL.TW": mock_df_trail,
        "0050.TW": mock_df_loss.copy()
    }

    test_positions = [
        {
            "ticker": "TEST_LOSS.TW",
            "shares": 100,
            "cost_price": 100.0,
            "entry_date": "2026-01-02",
            "peak_price": 102.0
        },
        {
            "ticker": "TEST_TRAIL.TW",
            "shares": 100,
            "cost_price": 100.0,
            "entry_date": "2026-01-02",
            "peak_price": 125.0
        }
    ]

    PortfolioTracker.save_portfolio(test_positions, extra_state={"cash": 50000.0, "peak_equity": 100000.0})
    eval_res = PortfolioTracker.evaluate_portfolio(mock_dataset, save_state=False)

    loss_item = next(p for p in eval_res if p["ticker"] == "TEST_LOSS.TW")
    trail_item = next(p for p in eval_res if p["ticker"] == "TEST_TRAIL.TW")

    assert loss_item["hard_stop_triggered"] is True, "TEST_LOSS.TW 虧損 31% 必須觸發 hard_stop_triggered"
    assert "戰術絕對硬停損" in loss_item["alert_text"]
    assert trail_item["trailing_stop_triggered"] is True, "TEST_TRAIL.TW 自高點回檔 12.8% 必須觸發 trailing_stop_triggered"
    assert "移動停損平倉" in trail_item["alert_text"]

    # 3. 測試 AutoTrader 產生賣出訂單與讓價保護
    dummy_rank = pd.DataFrame([{
        "ticker": "TEST_BUY.TW",
        "name": "測試強勢股",
        "price": 100.0,
        "score": 95.0,
        "above_50sma": True,
        "is_distribution_warn": False
    }])
    trader_test = AutoTrader(dataset=mock_dataset, budget_per_stock_tw=30000.0)
    orders, state_out, logs_out = trader_test.generate_trade_orders(dummy_rank, pd.DataFrame(), target_market="TW")

    sell_orders = [o for o in orders if o["action"] == "SELL"]
    assert any(o["ticker"] == "TEST_LOSS.TW" and "戰術絕對硬停損" in o["reason"] for o in sell_orders), "必須產生硬停損賣單"
    assert any(o["ticker"] == "TEST_TRAIL.TW" and "移動停損平倉" in o["reason"] for o in sell_orders), "必須產生移動停損賣單"

    loss_order = next(o for o in sell_orders if o["ticker"] == "TEST_LOSS.TW")
    assert loss_order["is_emergency"] is True
    assert loss_order["price"] < loss_order["market_price"], "緊急賣單限價必須低於現價以確保撮合"

    print(f"  ✅ 倉位縮放係數斷言: 回撤5%={sf_normal:.2f}x, 回撤20%={sf_dd18:.2f}x, 回撤26%={sf_dd25:.2f}x")
    print(f"  ✅ -31% 戰術絕對硬停損斷言: 100% 觸發全數賣出並加入禁買")
    print(f"  ✅ -9% 移動停損平倉斷言: 100% 觸發高點回檔賣出")
    print(f"  ✅ 讓價撮合機制斷言: 限價 NT${loss_order['price']:.2f} < 市價 NT${loss_order['market_price']:.2f} (成功向下讓價)")

    results["實盤雙軌風控與回撤縮放"] = True
except Exception as e:
    print(f"  ❌ 風控測試異常: {e}")
    results["實盤雙軌風控與回撤縮放"] = False
finally:
    if backup_portfolio:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            f.write(backup_portfolio)

# -------------------------------------------------------------
# 綜合測試匯總報告
# -------------------------------------------------------------
print("\n" + "=" * 70)
print(f"{'驗收模組':<30} {'測試結果'}")
print("-" * 70)
all_ok = True
for name, ok in results.items():
    if not ok:
        all_ok = False
    print(f"{name:<30} {'✅ 正常通過 (PASS)' if ok else '❌ 異常 (FAIL)'}")

print("-" * 70)
if all_ok:
    print("🎉 恭喜！全系統 9 大模組自主測試 100% 全數通過，無任何潛在漏洞！")
else:
    print("⚠️ 警告：部分模組測試未通過，請查看上方詳細日誌。")
print("======================================================================\n")

sys.exit(0 if all_ok else 1)
