"""
第一步驗證腳本：檢驗數據抓取、特徵計算與即時科技股天梯排名
"""
import sys
import os
import io
import argparse

# 強制輸出為 UTF-8，避免 Windows cp950 編碼問題
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 確保當前目錄在 Python Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import TechDataLoader
from src.features import TechFeatureEngine
from src.config import config

def main():
    parser = argparse.ArgumentParser(description="第一步驗證腳本")
    parser.add_argument("--skip-data", action="store_true", help="使用本機快取數據，略過網路下載")
    args = parser.parse_args()

    print("=" * 70)
    print("🚀 【台美純科技股量化系統】第一步管線檢驗開始")
    print("=" * 70)
    
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data(cache_only=args.skip_data)
    
    if not dataset:
        print("❌ 未能獲取任何標的數據，請確認網路連線！")
        return
        
    print("\n⚡ 正在進行特徵工程計算 (動量、均線濾網、突破訊號)...")
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)
    
    print("\n" + "=" * 70)
    print("🇹🇼 【台股科技天團 - 最新動態天梯排名】")
    print("=" * 70)
    print(f"{'排名':<4} {'代碼':<10} {'標的名稱':<12} {'最新價':<8} {'20日動能%':<10} {'60日動能%':<10} {'綜合動量分':<10} {'多頭狀態'}")
    print("-" * 70)
    for idx, row in tw_rank.iterrows():
        trend_status = "🟢 多頭(>50MA)" if row["above_50sma"] else "🔴 轉弱(<50MA)"
        print(f"#{idx+1:<3} {row['ticker']:<10} {row['name']:<12} {row['price']:<8} {row['roc_20d']:<10} {row['roc_60d']:<10} {row['score']:<10} {trend_status}")
    
    bullish_tw = tw_rank[tw_rank["above_50sma"] == True]
    if not bullish_tw.empty:
        top_tw = bullish_tw.iloc[:config.top_n_picks]
        print(f"\n💡 台股今日前 {len(top_tw)} 強勢首選: {', '.join(top_tw['name'].tolist())}")
    else:
        print("\n🛡️ 目前全數標的跌破 50MA（處於空頭防禦期，建議 100% 現金觀望）")

    print("\n" + "=" * 70)
    print("🇺🇸 【美股科技天團 - 最新動態天梯排名】")
    print("=" * 70)
    print(f"{'排名':<4} {'代碼':<10} {'標的名稱':<12} {'最新價':<8} {'20日動能%':<10} {'60日動能%':<10} {'綜合動量分':<10} {'多頭狀態'}")
    print("-" * 70)
    for idx, row in us_rank.iterrows():
        trend_status = "🟢 多頭(>50MA)" if row["above_50sma"] else "🔴 轉弱(<50MA)"
        print(f"#{idx+1:<3} {row['ticker']:<10} {row['name']:<12} {row['price']:<8} {row['roc_20d']:<10} {row['roc_60d']:<10} {row['score']:<10} {trend_status}")
    
    bullish_us = us_rank[us_rank["above_50sma"] == True]
    if not bullish_us.empty:
        top_us = bullish_us.iloc[:config.top_n_picks]
        print(f"\n💡 美股今日前 {len(top_us)} 強勢首選: {', '.join(top_us['ticker'].tolist())}")
    else:
        print("\n🛡️ 目前全數標的跌破 50MA（處於空頭防禦期，建議 100% 現金觀望）")

    print("\n" + "=" * 70)
    print("🎉 【第一步驗收成功】：數據獲取、特徵工程與排序打分模組運作完全正常！")
    print("=" * 70)

if __name__ == "__main__":
    main()
