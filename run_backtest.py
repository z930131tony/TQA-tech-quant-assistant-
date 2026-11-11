"""
回測執行主腳本：執行台股與美股科技天團歷史策略回測，並與大盤基準進行對比
"""
import sys
import os
import io

# 強制輸出為 UTF-8，避免 Windows cp950 編碼問題
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.backtester import TechBacktester
import pandas as pd

def print_result_card(res: dict, benchmark_return: float, benchmark_name: str):
    print("\n" + "=" * 65)
    print(f"📊 【{res['market']} 市場科技策略回測報告】")
    print("=" * 65)
    print(f"  📅 回測區間        : {res['start_date']} ~ {res['end_date']} (共 {res['total_trading_days']} 交易日)")
    print(f"  💰 起始本金        : ${res['initial_capital']:,.2f}")
    print(f"  💎 最終淨值        : ${res['final_value']:,.2f}")
    print(f"  📈 策略總報酬率    : {res['total_return_pct']:+.2f}%")
    print(f"  🎯 策略年化報酬 (CAGR): {res['cagr_pct']:+.2f}%")
    print(f"  🛡️ 最大回撤 (MDD)  : {res['max_drawdown_pct']:.2f}%")
    print(f"  ⚡ 夏普比率 (Sharpe) : {res['sharpe_ratio']:.2f}")
    print(f"  🔄 總交易筆數      : {res['total_trades']} 筆")
    print(f"  🏆 交易勝率        : {res['win_rate_pct']:.2f}%")
    print("-" * 65)
    print(f"  📌 基準標的 ({benchmark_name}) 同期報酬 : {benchmark_return:+.2f}%")
    diff = res['total_return_pct'] - benchmark_return
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
    print("=" * 65)
    print("🚀 【台美純科技量化回測引擎】開始運算歷史績效")
    print("=" * 65)
    
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data()
    
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
    qqq_return = calculate_benchmark_return(dataset, "QQQ", us_res["start_date"], us_res["end_date"])
    print_result_card(us_res, qqq_return, "QQQ (那斯達克100)")
    
    # 印出美股近 5 筆精彩交易紀錄
    if not us_res["trades_df"].empty:
        print("\n📜 【美股近期交易紀錄範例】:")
        print(us_res["trades_df"].tail(8).to_string(index=False))

    # 2. 台股回測
    print("\n🇹🇼 正在回測台股科技天團動態輪動策略...")
    tw_res = backtester.run(market="TW")
    tw_bench = calculate_benchmark_return(dataset, "0052.TW", tw_res["start_date"], tw_res["end_date"])
    print_result_card(tw_res, tw_bench, "0052.TW (富邦科技ETF)")
    
    if not tw_res["trades_df"].empty:
        print("\n📜 【台股近期交易紀錄範例】:")
        print(tw_res["trades_df"].tail(8).to_string(index=False))

    print("\n🎉 回測引擎運算完成！")

if __name__ == "__main__":
    main()
