"""
每日定時排程主程式 (數據下載 -> 計算評分 -> 模擬風控 -> AI辯論 -> 網頁生成 -> LINE推播)
強化版：具備全流程單模組故障隔離 (Fault Isolation)，確保外部 API 異常時不中斷儀表板生成與數據更新
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
from src.ai_debate import run_daily_ai_debate

def get_auto_market() -> str:
    tw_tz = pytz.timezone("Asia/Taipei")
    curr_hour = datetime.now(tw_tz).hour
    # 09:00 - 18:00 台灣時間為台股盤中與收盤結算時段 -> TW
    # 18:00 - 09:00 台灣時間為美股夜盤與美股收盤結算時段 -> US
    return "TW" if 9 <= curr_hour < 18 else "US"

def main():
    parser = argparse.ArgumentParser(description="TQA 定時運算與推播")
    parser.add_argument("--market", choices=["TW", "US", "AUTO"], default="AUTO")
    parser.add_argument("--skip-data", action="store_true", help="使用本機快取數據，略過網路下載")
    args = parser.parse_args()

    target_market = args.market
    if target_market == "AUTO":
        target_market = get_auto_market()

    print("=" * 50)
    print(f"啟動 TQA 定時排程 (目標市場: {target_market})...")
    print("=" * 50)

    # 1. 抓取數據
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data(cache_only=args.skip_data)

    # 2. 計算特徵與最新天梯
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)

    # 2.5 執行自動模擬交易與風控比對 (故障隔離)
    sim_logs = []
    try:
        print(f"📈 執行【{target_market}】自動模擬交易與部位風控...")
        if target_market in ["ALL", "TW"]:
            try:
                AutoTrader.sync_shioaji_positions()
            except Exception as e_shioaji:
                print(f"⚠️ Shioaji 庫存同步略過: {e_shioaji}")
        trader = AutoTrader(dataset=dataset)
        sim_logs, _ = trader.execute_daily_simulation(tw_rank, us_rank, target_market=target_market)
    except Exception as e_trade:
        print(f"⚠️ 模擬交易與風控執行異常 (已隔離): {e_trade}")

    # 2.8 評估持股部位與執行 TradingAgents AI 多空對抗辯論 (故障隔離)
    portfolio_positions = []
    try:
        portfolio_positions = PortfolioTracker.evaluate_portfolio(dataset)
    except Exception as e_port:
        print(f"⚠️ 持股評估異常 (已隔離): {e_port}")

    ai_debate_data = {"debates": []}
    try:
        ai_debate_data = run_daily_ai_debate(tw_rank, us_rank, target_market=target_market, positions=portfolio_positions)
    except Exception as e_ai:
        print(f"⚠️ AI 多空辯論執行異常 (已隔離，降級使用既有分析): {e_ai}")

    # 3. 整理回測成績
    us_backtest = {}
    tw_backtest = {}
    try:
        backtester = TechBacktester(dataset=dataset, initial_capital=100000.0)
        us_backtest = backtester.run(market="US")
        tw_backtest = backtester.run(market="TW")
    except Exception as e_bt:
        print(f"⚠️ 策略回測運算異常 (已隔離): {e_bt}")

    # 4. 生成 index.html (核心交付物，最高優先級)
    output_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    try:
        WebDashboardGenerator.generate_html(
            dataset=dataset,
            tw_rank=tw_rank,
            us_rank=us_rank,
            tw_backtest=tw_backtest,
            us_backtest=us_backtest,
            output_path=output_html,
            ai_debate_data=ai_debate_data
        )
        print(f"✅ 儀表板成功生成至: {output_html}")
    except Exception as e_html:
        print(f"❌ 網頁儀表板生成失敗: {e_html}")

    # 5. 發送 LINE 推播 (故障隔離，避免因推播網路失敗中斷整體工作流)
    try:
        notifier = LineNotifier()
        print(f"發送【{target_market}】市場 LINE 推播...")
        portfolio_note = PortfolioTracker.format_line_notification(portfolio_positions, market_type=target_market)
        debates_list = ai_debate_data.get("debates", [])

        if target_market == "TW":
            msg = LineNotifier.format_tw_morning_message(tw_rank, ai_debates=debates_list)
        else:
            msg = LineNotifier.format_us_evening_message(us_rank, ai_debates=debates_list)

        if sim_logs:
            sim_summary = "🎯 【模擬下單執行紀錄】\n" + "\n".join(sim_logs) + "\n\n"
            msg = sim_summary + msg

        if portfolio_note:
            msg = portfolio_note + "\n" + msg

        notifier.send_message(msg)
    except Exception as e_line:
        print(f"⚠️ LINE 推播異常 (已隔離): {e_line}")

    print("排程執行完畢。")

if __name__ == "__main__":
    main()
