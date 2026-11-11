"""
每日定時排程主程式 (數據下載 -> 計算評分 -> LINE 推播 -> 網頁生成)
"""
import sys
import os
import io
import argparse
from datetime import datetime
import pytz

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.features import TechFeatureEngine
from src.backtester import TechBacktester
from src.trader import AutoTrader
from src.web_generator import WebDashboardGenerator
from src.notifier import LineNotifier
from src.portfolio import PortfolioTracker

def get_auto_market() -> str:
    tw_tz = pytz.timezone("Asia/Taipei")
    curr_hour = datetime.now(tw_tz).hour
    # 09:00 - 18:00 台灣時間為台股盤中與收盤結算時段 -> TW
    # 18:00 - 09:00 台灣時間為美股夜盤與美股收盤結算時段 -> US
    return "TW" if 9 <= curr_hour < 18 else "US"

def main():
    parser = argparse.ArgumentParser(description="TQA 定時運算與推播")
    parser.add_argument("--market", choices=["TW", "US", "AUTO"], default="AUTO")
    args = parser.parse_args()

    target_market = args.market
    if target_market == "AUTO":
        target_market = get_auto_market()

    print("=" * 50)
    print(f"啟動 TQA 定時排程 (目標市場: {target_market})...")
    print("=" * 50)

    # 1. 抓取數據
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data()

    # 2. 計算特徵與最新天梯
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)

    # 2.5 執行自動模擬交易與風控比對 (依照目標市場單獨執行，避免時區錯置)
    print(f"📈 執行【{target_market}】自動模擬交易與部位風控...")
    trader = AutoTrader(dataset=dataset)
    sim_logs, _ = trader.execute_daily_simulation(tw_rank, us_rank, target_market=target_market)

    # 3. 整理回測成績
    backtester = TechBacktester(dataset=dataset, initial_capital=100000.0)
    us_backtest = backtester.run(market="US")
    tw_backtest = backtester.run(market="TW")

    # 4. 生成 index.html
    output_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    WebDashboardGenerator.generate_html(
        dataset=dataset,
        tw_rank=tw_rank,
        us_rank=us_rank,
        tw_backtest=tw_backtest,
        us_backtest=us_backtest,
        output_path=output_html
    )

    # 5. 發送 LINE 推播
    notifier = LineNotifier()
    print(f"發送【{target_market}】市場 LINE 推播...")
    portfolio_positions = PortfolioTracker.evaluate_portfolio(dataset)
    portfolio_note = PortfolioTracker.format_line_notification(portfolio_positions, market_type=target_market)

    if target_market == "TW":
        msg = LineNotifier.format_tw_morning_message(tw_rank)
    else:
        msg = LineNotifier.format_us_evening_message(us_rank)

    if sim_logs:
        sim_summary = "🎯 【模擬下單執行紀錄】\n" + "\n".join(sim_logs) + "\n\n"
        msg = sim_summary + msg

    if portfolio_note:
        msg = portfolio_note + "\n" + msg

    notifier.send_message(msg)
    print("排程執行完畢。")

if __name__ == "__main__":
    main()
