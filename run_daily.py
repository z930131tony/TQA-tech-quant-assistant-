"""
每日定時排程主程式 (抓取最新數據 -> 計算動量評分 -> 發送 LINE 推播 -> 更新網頁)
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
from src.config import config

def get_current_tw_hour() -> int:
    tw_tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tw_tz).hour

def main():
    parser = argparse.ArgumentParser(description="TQA 每日量化運算與推播排程")
    parser.add_argument("--market", choices=["TW", "US", "AUTO"], default="AUTO", help="推播市場 (TW=台股, US=美股, AUTO=依時間自動判斷)")
    args = parser.parse_args()

    print("=" * 65)
    print("🚀 【TQA 科技量化每日排程】啟動運算")
    print("=" * 65)

    # 1. 抓取台美股歷史數據
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data()

    # 2. 特徵計算與即時天梯排名
    print("\n⚡ 正在進行特徵工程計算...")
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)

    # 3. 執行回測整理戰報
    print("\n📊 整理最新策略成績單...")
    backtester = TechBacktester(dataset=dataset, initial_capital=100000.0)
    us_backtest = backtester.run(market="US")
    tw_backtest = backtester.run(market="TW")

    # 4. 更新本機與雲端網頁 index.html
    output_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    WebDashboardGenerator.generate_html(
        tw_rank=tw_rank,
        us_rank=us_rank,
        tw_backtest=tw_backtest,
        us_backtest=us_backtest,
        output_path=output_html
    )

    # 5. 發送 LINE 手機推播
    notifier = LineNotifier()
    target_market = args.market

    if target_market == "AUTO":
        curr_hour = get_current_tw_hour()
        # 台灣時間 00:00 ~ 14:00 判定為晨間台股模式，14:00 後判定為晚間美股模式
        if curr_hour < 14:
            target_market = "TW"
        else:
            target_market = "US"

    print(f"\n📲 正在準備發送【{target_market}】市場 LINE 推播通知...")
    if target_market == "TW":
        msg = LineNotifier.format_tw_morning_message(tw_rank)
    else:
        msg = LineNotifier.format_us_evening_message(us_rank)

    notifier.send_message(msg)

    print("\n" + "=" * 65)
    print("🎉 每日排程任務全數順利完成！")
    print("=" * 65)

if __name__ == "__main__":
    main()
