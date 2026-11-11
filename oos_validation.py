"""
================================================================================
TQA 量化策略防偷看與樣本外 (OOS) 專業檢驗工具 (Anti-Lookahead & OOS Validation Suite)
================================================================================
本模組提供四大嚴格量化檢驗：
1. 特徵計算未來數據因果性檢驗 (Feature Causality & Anti-Leakage Check)
2. 股票池異常分割與未還原資料掃描 (Data Split Anomaly Scanner)
3. 嚴格時間外樣本盲測 (In-Sample vs Out-of-Sample Walk-Forward Split)
4. 交易執行時延抗性測試 (Execution Lag Test: T+0 Close vs T+1 Open)
"""

import os
import sys
import io
import argparse
import numpy as np
import pandas as pd

# 強制 UTF-8 輸出，避免 Windows 終端編碼問題
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.features import TechFeatureEngine
from src.backtester import TechBacktester


def check_feature_causality(dataset: dict, test_symbol: str = "2330.TW") -> bool:
    """
    檢驗 1：特徵未來數據因果性 (Anti-Leakage Check)
    作法：將未來 50 天的價格人為放大 10 倍，比對前半段所有特徵值是否產生任何變化。
    若全部特徵最大差異均為 0.000000，則證明特徵完全因果，無未來偷看。
    """
    print("\n" + "=" * 70)
    print(f"【檢驗 1】特徵計算未來數據因果性檢驗 (測試標的: {test_symbol})")
    print("=" * 70)

    if test_symbol not in dataset:
        test_symbol = list(dataset.keys())[0]

    df_orig = dataset[test_symbol].copy()
    feat_orig = TechFeatureEngine.calculate_technical_features(df_orig)

    # 模擬篡改：未來 50 天價格暴增 10 倍
    df_tampered = df_orig.copy()
    tamper_idx = len(df_tampered) - 50
    df_tampered.iloc[tamper_idx:, df_tampered.columns.get_loc("close")] *= 10.0
    df_tampered.iloc[tamper_idx:, df_tampered.columns.get_loc("high")] *= 10.0
    df_tampered.iloc[tamper_idx:, df_tampered.columns.get_loc("low")] *= 10.0

    feat_tampered = TechFeatureEngine.calculate_technical_features(df_tampered)

    past_orig = feat_orig.iloc[:tamper_idx]
    past_tampered = feat_tampered.iloc[:tamper_idx]

    all_passed = True
    print(f"{'指標名稱':<20} {'最大絕對差異':<15} {'檢驗結果'}")
    print("-" * 50)
    for col in past_orig.columns:
        if col in ["symbol"]:
            continue
        s1 = past_orig[col].astype(float).fillna(0)
        s2 = past_tampered[col].astype(float).fillna(0)
        max_diff = float((s1 - s2).abs().max())
        passed = (max_diff == 0.0)
        if not passed:
            all_passed = False
        res_str = "✅ PASS (無偷看)" if passed else "❌ FAIL (有未來外洩)"
        print(f"{col:<20} {max_diff:<15.6f} {res_str}")

    print("-" * 50)
    if all_passed:
        print("🎉 結論：特徵計算 100% 嚴格向後回溯 (Causal)，無任何時間前瞻偷看！")
    else:
        print("⚠️ 警告：發現部分指標存在未來數據外洩，需即刻檢修！")
    return all_passed


def check_data_anomalies(dataset: dict, threshold_drop: float = -0.35) -> list:
    """
    檢驗 2：掃描未還原除權息或分割異常 (Data Anomaly Scanner)
    """
    print("\n" + "=" * 70)
    print("【檢驗 2】全股票池單日異常暴跌掃描 (防範未還原股票分割/除權問題)")
    print("=" * 70)

    anomalies = []
    for ticker, df in dataset.items():
        if df is None or df.empty or "close" not in df.columns:
            continue
        pct = df["close"].pct_change()
        min_pct = pct.min()
        if min_pct <= threshold_drop:
            worst_date = pct.idxmin()
            anomalies.append((ticker, str(worst_date)[:10], min_pct))

    if not anomalies:
        print(f"✅ 全股票池共 {len(dataset)} 檔標的，均無單日跌幅 > {abs(threshold_drop)*100:.0f}% 之未還原分割異常。")
    else:
        print(f"⚠️ 發現 {len(anomalies)} 檔標的可能存在未還原拆股：")
        for t, d, p in anomalies:
            print(f"   - {t}: 於 {d} 單日跌幅達 {p*100:.2f}%")
    return anomalies


def run_oos_split_test(dataset: dict, split_date: str = "2025-06-30") -> bool:
    """
    檢驗 3：嚴格時間切分樣本外盲測 (In-Sample vs Out-of-Sample)
    說明：OOS 盲測期之移動均線 (50MA/200MA) 採用切分點前的真實歷史價格作為初始暖機窗口
          （符合實盤交易首日可查閱過去 50 天歷史走勢之真實場景，無未來數據外洩）。
    """
    print("\n" + "=" * 70)
    print(f"【檢驗 3】樣本外盲測 (OOS Walk-Forward Split，切分點: {split_date})")
    print("=" * 70)
    print("※ 備註：均線採用切分點前的真實歷史價格暖機，符合實盤首日具備歷史走勢之真實情境。")

    all_passed = True
    for market in ["TW", "US"]:
        m_name = "台股 (TW)" if market == "TW" else "美股 (US)"
        bench_ticker = "0050.TW" if market == "TW" else "QQQ"

        # 全樣本
        full = TechBacktester(dataset).run(market)
        # 樣本內 (IS, 訓練期)
        is_res = TechBacktester(dataset, end_date=split_date).run(market)
        # 樣本外 (OOS, 盲測期)：切分點隔天起算
        oos_start = (pd.to_datetime(split_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        oos_res = TechBacktester(dataset, start_date=oos_start).run(market)

        print(f"\n>>> 市場：{m_name} (基準 ETF: {bench_ticker})")
        print(f"全區間: {full['start_date']} ~ {full['end_date']} ({full['total_trading_days']} 交易日)")
        print(f"  策略總報酬: {full['total_return']:+.2f}% | CAGR: {full['cagr']:+.2f}% | MDD: {full['max_drawdown']:.2f}% | 夏普: {full['sharpe_ratio']:.2f}")
        print("-" * 65)
        print(f"1. 樣本內 (IS 訓練期: {is_res['start_date']} ~ {is_res['end_date']}, {is_res['total_trading_days']} 交易日):")
        print(f"   策略報酬: {is_res['total_return']:+.2f}% | 基準報酬: {is_res['benchmark_return']:+.2f}% | Alpha: {is_res['total_return'] - is_res['benchmark_return']:+.2f}%")
        print(f"   年化 CAGR: {is_res['cagr']:+.2f}% | MDD: {is_res['max_drawdown']:.2f}% | 夏普: {is_res['sharpe_ratio']:.2f}")
        print("-" * 65)
        print(f"2. 樣本外 (OOS 盲測期: {oos_res['start_date']} ~ {oos_res['end_date']}, {oos_res['total_trading_days']} 交易日):")
        print(f"   策略報酬: {oos_res['total_return']:+.2f}% | 基準報酬: {oos_res['benchmark_return']:+.2f}% | Alpha: {oos_res['total_return'] - oos_res['benchmark_return']:+.2f}%")
        print(f"   年化 CAGR: {oos_res['cagr']:+.2f}% | MDD: {oos_res['max_drawdown']:.2f}% | 夏普: {oos_res['sharpe_ratio']:.2f}")

        # 泛化係數
        ratio = (oos_res["sharpe_ratio"] / is_res["sharpe_ratio"]) if is_res["sharpe_ratio"] > 0 else 0.0
        print("-" * 65)
        print(f"📊 夏普泛化衰退係數 (OOS/IS): {ratio:.2f}")
        if ratio >= 0.7:
            print("✅ 泛化評級：【極優 Robust】無過度擬合 (Overfitting)，盲測表現穩健！")
        elif ratio >= 0.5:
            print("🟡 泛化評級：【良好 Acceptable】策略具備合理泛化能力。")
        else:
            all_passed = False
            print("⚠️ 泛化評級：【需警惕】樣本外衰退顯著，可能存在過度擬合。")

    return all_passed


def run_execution_lag_test(dataset: dict) -> bool:
    """
    檢驗 4：執行時延抗性檢驗 (T+0 Close vs T+1 Open)
    驗證策略是否依賴同根 K 棒收盤價即時成交偏差。
    """
    print("\n" + "=" * 70)
    print("【檢驗 4】執行時延抗性檢驗 (T+0 收盤價即時成交 vs T+1 隔日開盤成交)")
    print("=" * 70)

    all_passed = True
    for market in ["TW", "US"]:
        m_name = "台股 (TW)" if market == "TW" else "美股 (US)"
        # 1. T+0 Close (當日收盤成交)
        bt_close = TechBacktester(dataset, execution_mode="same_close")
        res_close = bt_close.run(market)

        # 2. T+1 Open (隔日開盤成交，徹底排除盤中前瞻)
        bt_open = TechBacktester(dataset, execution_mode="next_open")
        res_open = bt_open.run(market)

        ret_diff = res_open["total_return"] - res_close["total_return"]
        print(f"\n>>> 市場：{m_name}")
        print(f"  [T+0 當日收盤成交] 報酬: {res_close['total_return']:+.2f}% | MDD: {res_close['max_drawdown']:.2f}% | 夏普: {res_close['sharpe_ratio']:.2f}")
        print(f"  [T+1 隔日開盤成交] 報酬: {res_open['total_return']:+.2f}% | MDD: {res_open['max_drawdown']:.2f}% | 夏普: {res_open['sharpe_ratio']:.2f}")
        print(f"  └ 延遲影響差異: 總報酬差異 {ret_diff:+.2f}% (夏普: {res_close['sharpe_ratio']:.2f} -> {res_open['sharpe_ratio']:.2f})")
        
        if res_open["total_return"] > 50.0 and res_open["sharpe_ratio"] >= 1.0:
            print("  ✅ 驗證結論：策略在隔日開盤執行下依然保有高夏普與強勁正報酬，非偷看收盤價之虛假利潤！")
        else:
            all_passed = False
            print("  ⚠️ 驗證結論：策略對執行時延較為敏感，需留意滑價與隔夜跳空風險。")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="TQA 樣本外與防偷看檢驗工具")
    parser.add_argument("--split", type=str, default="2025-06-30", help="IS/OOS 切分日期 (預設 2025-06-30)")
    parser.add_argument("--skip-data", action="store_true", help="跳過線上行情下載 (直接使用本機快取 CSV)")
    args = parser.parse_args()

    print("======================================================================")
    print("      TQA 量化防偷看與樣本外 (OOS) 專業檢驗系統 啟動")
    print("======================================================================")

    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data(cache_only=args.skip_data)

    # 1. 因果性檢驗
    causality_ok = check_feature_causality(dataset)

    # 2. 數據除權異常掃描
    anomalies = check_data_anomalies(dataset)
    anomalies_ok = (len(anomalies) == 0)

    # 3. 樣本外切分測試
    oos_ok = run_oos_split_test(dataset, split_date=args.split)

    # 4. 隔日開盤執行時延檢驗
    lag_ok = run_execution_lag_test(dataset)

    print("\n" + "=" * 70)
    if causality_ok and anomalies_ok and oos_ok and lag_ok:
        print("🎉 總結：四大量化檢驗全數通過！無時間外洩、無除權異常、泛化強韌、隔日開盤獲利成立。")
    else:
        print("⚠️ 總結：部分檢驗項目未達最優標竿，請查閱上述詳細報告確認潛在風險。")
    print("======================================================================\n")


if __name__ == "__main__":
    main()
