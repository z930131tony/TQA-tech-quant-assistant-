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
from src.web_generator import WebDashboardGenerator
from src.notifier import LineNotifier
from src.portfolio import PortfolioTracker

def get_current_tw_hour() -> int:
    tw_tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tw_tz).hour

def main():
    parser = argparse.ArgumentParser(description="TQA 定時運算與推播")
    parser.add_argument("--market", choices=["TW", "US", "AUTO"], default="AUTO")
    args = parser.parse_args()

    print("=" * 50)
    print("啟動 TQA 定時排程...")
    print("=" * 50)

    # 1. 抓取數據
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data()

    # 2. 計算特徵與最新天梯
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)

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
    target_market = args.market

    if target_market == "AUTO":
        curr_hour = get_current_tw_hour()
        # 14:00 前發送台股晨間操作指引，14:00 後發送美股操作指引
        target_market = "TW" if curr_hour < 14 else "US"

    print(f"發送【{target_market}】市場 LINE 推播...")
    portfolio_positions = PortfolioTracker.evaluate_portfolio(dataset)
    portfolio_note = PortfolioTracker.format_line_notification(portfolio_positions, market_type=target_market)

    if target_market == "TW":
        msg = LineNotifier.format_tw_morning_message(tw_rank)
    else:
        msg = LineNotifier.format_us_evening_message(us_rank)

    if portfolio_note:
        msg = portfolio_note + "\n" + msg

    notifier.send_message(msg)
    print("排程執行完畢。")

if __name__ == "__main__":
    main()
