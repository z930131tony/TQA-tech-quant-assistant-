"""
回測執行主腳本：執行台股與美股科技天團歷史策略回測，並與大盤基準進行對比
"""
import sys
import os
import io
import argparse
import pandas as pd

# 強制輸出為 UTF-8，避免 Windows cp950 編碼問題
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.backtester import TechBacktester

def print_result_card(res: dict, benchmark_return: float, benchmark_name: str):
    total_ret = res.get("total_return_pct", res.get("total_return", 0.0))
    cagr = res.get("cagr_pct", res.get("cagr", 0.0))
    mdd = res.get("max_drawdown_pct", res.get("max_drawdown", 0.0))
    sharpe = res.get("sharpe_ratio", 0.0)
    win_rate = res.get("win_rate_pct", res.get("win_rate", 0.0))
    total_trades = res.get("total_trades", len(res.get("trades_df", [])))

    print("\n" + "=" * 65)
    print(f"📊 【{res.get('market', '')} 市場科技策略回測報告】")
    print("=" * 65)
    print(f"  📅 回測區間        : {res.get('start_date', '')} ~ {res.get('end_date', '')} (共 {res.get('total_trading_days', 0)} 交易日)")
    print(f"  💰 起始本金        : ${res.get('initial_capital', 100000.0):,.2f}")
    print(f"  💎 最終淨值        : ${res.get('final_value', 100000.0):,.2f}")
    print(f"  📈 策略總報酬率    : {total_ret:+.2f}%")
    print(f"  🎯 策略年化報酬 (CAGR): {cagr:+.2f}%")
    print(f"  🛡️ 最大回撤 (MDD)  : {mdd:.2f}%")
    print(f"  ⚡ 夏普比率 (Sharpe) : {sharpe:.2f}")
    print(f"  🔄 總交易筆數      : {total_trades} 筆")
    print(f"  🏆 交易勝率        : {win_rate:.2f}%")
    print("-" * 65)
    print(f"  📌 基準標的 ({benchmark_name}) 同期報酬 : {benchmark_return:+.2f}%")
    diff = total_ret - benchmark_return
    alpha_status = f"超額報酬 (Alpha): {diff:+.2f}% 🚀" if diff >= 0 else f"落後基準: {diff:+.2f}%"
    print(f"  ⭐ 策略超額表現    : {alpha_status}")
    print("=" * 65)

def calculate_benchmark_return(dataset: dict, ticker: str, start_date: str, end_date: str) -> float:
    if ticker in dataset:
        df = dataset[ticker]
        sub = df.loc[start_date:end_date]
        if not sub.empty:
            return float((sub["close"].iloc[-1] / sub["close"].iloc[0] - 1) * 100)
    return 0.0

def main():
    parser = argparse.ArgumentParser(description="TQA 歷史策略回測引擎")
    parser.add_argument("--skip-data", action="store_true", help="使用本機快取數據加速運算")
    args = parser.parse_args()

    print("=" * 65)
    print("🚀 【台美純科技量化回測引擎】開始運算歷史績效")
    print("=" * 65)
    
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data(cache_only=args.skip_data)
    
    backtester = TechBacktester(
        dataset=dataset,
        initial_capital=100000.0,
        fee_rate=0.001,          # 0.1% 手續費與滑價
        rebalance_freq=5,         # 每週 (5日) 檢查輪動一次
        top_n=3,                  # 重倉最強前 3 檔
        enable_50sma_filter=True, # 跌破 50MA 自動避險轉現金
        trailing_stop_pct=0.08    # 8% 追蹤停損
    )
    
    # 1. 美股回測
    print("\n🇺🇸 正在回測美股科技天團動態輪動策略...")
    us_res = backtester.run(market="US")
    qqq_calc = calculate_benchmark_return(dataset, "QQQ", us_res["start_date"], us_res["end_date"])
    qqq_return = us_res.get("benchmark_return", qqq_calc)
    print_result_card(us_res, qqq_return, "QQQ (那斯達克100)")
    
    # 印出美股近 8 筆精彩交易紀錄
    if not us_res["trades_df"].empty:
        print("\n📜 【美股近期交易紀錄範例】:")
        print(us_res["trades_df"].tail(8).to_string(index=False))

    # 2. 台股回測
    print("\n🇹🇼 正在回測台股科技天團動態輪動策略...")
    tw_res = backtester.run(market="TW")
    tw_calc = calculate_benchmark_return(dataset, "0050.TW", tw_res["start_date"], tw_res["end_date"])
    tw_bench = tw_res.get("benchmark_return", tw_calc)
    print_result_card(tw_res, tw_bench, "0050.TW (元大台灣50)")
    
    if not tw_res["trades_df"].empty:
        print("\n📜 【台股近期交易紀錄範例】:")
        print(tw_res["trades_df"].tail(8).to_string(index=False))

    print("\n🎉 回測引擎運算完成！")

if __name__ == "__main__":
    main()
