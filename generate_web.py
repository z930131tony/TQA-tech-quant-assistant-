"""
網頁生成一鍵啟動腳本 (生成 index.html 供手機與電腦瀏覽，支援 --skip-data)
"""
import sys
import os
import io
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.features import TechFeatureEngine
from src.backtester import TechBacktester
from src.web_generator import WebDashboardGenerator

def main():
    parser = argparse.ArgumentParser(description="TQA 科技量化網頁生成器")
    parser.add_argument("--skip-data", action="store_true", help="使用本機快取數據加速生成網頁 (免重複下載)")
    parser.add_argument("--force", "--force-refresh", dest="force_refresh", action="store_true", help="強制重新下載最新市場數據，忽略快取")
    args = parser.parse_args()

    print("=" * 60)
    print("🌐 【TQA 科技量化網頁生成器】開始建立行動版網頁...")
    print("=" * 60)

    # 1. 下載最新數據 (若指定 --skip-data 則直接讀取本機快取，若指定 --force 則強制聯網更新)
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data(force_refresh=args.force_refresh, cache_only=args.skip_data)

    # 2. 特徵計算與即時天梯
    print("\n⚡ 正在評估最新台美動能評分...")
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)

    # 3. 執行回測以取得戰報摘要
    print("\n📊 正在整理回測成績單...")
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

    print("\n" + "=" * 60)
    print(f"🎉 網頁生成完畢！檔案路徑: {output_html}")
    print("📱 您可以直接雙擊 index.html 在電腦瀏覽，或透過 GitHub Pages 在手機上查看！")
    print("=" * 60)

if __name__ == "__main__":
    main()
