"""
數據下載與標準化清洗模組 (支援台股與美股)
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

from src.config import config, TECH_UNIVERSE_US, TECH_UNIVERSE_TW

class TechDataLoader:
    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def fetch_ticker_data(self, ticker: str, days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        下載單一標的歷史資料，並自動完成除權息調整 (Adjusted Prices)
        """
        lookback = days if days else config.lookback_days
        start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")
        
        try:
            # yfinance 獲取數據 (auto_adjust=True 會自動還原除權息與分割)
            df = yf.download(
                ticker, 
                start=start_date, 
                progress=False, 
                auto_adjust=True,
                multi_level_index=False
            )
            
            if df.empty or len(df) < 50:
                print(f"⚠️ [警告] {ticker} 資料量不足或下載為空！")
                return None
            
            # 標準化欄位名稱
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })
            df.index.name = "date"
            df["symbol"] = ticker
            
            # 清除 NaN
            df = df.dropna()
            return df
            
        except Exception as e:
            print(f"❌ [錯誤] 下載 {ticker} 失敗: {e}")
            return None

    def fetch_all_tech_data(self) -> Dict[str, pd.DataFrame]:
        """
        批次下載台美股所有科技池歷史數據
        """
        dataset = {}
        
        # 1. 下載台股科技池
        print("\n📈 [1/2] 正在抓取台股科技天團數據...")
        for ticker, name in TECH_UNIVERSE_TW.items():
            print(f"  -> 抓取台股: {ticker} ({name})")
            df = self.fetch_ticker_data(ticker)
            if df is not None:
                dataset[ticker] = df

        # 2. 下載美股科技池
        print("\n🇺🇸 [2/2] 正在抓取美股科技天團數據...")
        for ticker in TECH_UNIVERSE_US:
            print(f"  -> 抓取美股: {ticker}")
            df = self.fetch_ticker_data(ticker)
            if df is not None:
                dataset[ticker] = df

        print(f"\n✅ 數據抓取完成！成功獲取 {len(dataset)} 檔標的歷史數據。")
        return dataset
