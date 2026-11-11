"""
TQA 自動模擬交易一鍵啟動腳本
執行流程：
1. 抓取最新台美股行情
2. 特徵計算與天梯排序
3. 執行模擬下單 (檢查停損平倉、多頭買進前三強)
4. 更新 portfolio.json
5. 生成最新 index.html 儀表板
6. 推播交易執行報告至 LINE
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.features import TechFeatureEngine
from src.backtester import TechBacktester
from src.trader import AutoTrader
from src.web_generator import WebDashboardGenerator
from src.notifier import LineNotifier

def main():
    print("=" * 60)
    print("🤖 【TQA 自動模擬交易系統】開始執行...")
    print("=" * 60)

    # 1. 抓取最新數據
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data()

    # 2. 計算特徵與評分天梯
    print("\n⚡ 評估最新台美股動能評分...")
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)

    # 3. 執行模擬下單
    print("\n📈 執行模擬下單與風控比對...")
    trader = AutoTrader(dataset=dataset, budget_per_stock_tw=30000.0, budget_per_stock_us=1000.0)
    trade_logs, positions = trader.execute_daily_simulation(tw_rank, us_rank)

    print("\n📋 【今日模擬交易紀錄】")
    for log in trade_logs:
        print(log)

    # 4. 重新生成網頁 (同步更新 我的庫存 卡片)
    print("\n🌐 重新生成網頁儀表板 (index.html)...")
    backtester = TechBacktester(dataset=dataset, initial_capital=100000.0)
    tw_backtest = backtester.run(market="TW")
    us_backtest = backtester.run(market="US")

    output_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    WebDashboardGenerator.generate_html(
        dataset=dataset,
        tw_rank=tw_rank,
        us_rank=us_rank,
        tw_backtest=tw_backtest,
        us_backtest=us_backtest,
        output_path=output_html
    )

    # 5. LINE 推播
    notifier = LineNotifier()
    if notifier.channel_access_token and notifier.user_id:
        msg_header = "🎯 【TQA 自動模擬交易每日報告】\n"
        msg_body = "\n\n".join(trade_logs)
        notifier.send_message(msg_header + "\n" + msg_body)
        print("\n📲 已將模擬交易執行報告發送至您的 LINE！")

    print("\n" + "=" * 60)
    print(f"🎉 模擬交易完成！目前持有 {len(positions)} 檔模擬標的。")
    print("📱 您可以在網頁下方的「我的持股庫存與風控」卡片隨時查看！")
    print("=" * 60)

if __name__ == "__main__":
    main()
