"""
行情數據下載與標準化模組
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import os

from src.config import config, TECH_UNIVERSE_US, TECH_UNIVERSE_TW

class TechDataLoader:
    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def fetch_ticker_data(self, ticker: str, days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        下載單一標的歷史資料，自動進行除權息與分割調整 (Adjusted Prices)
        """
        lookback = days if days else config.lookback_days
        start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")
        
        try:
            df = yf.download(
                ticker, 
                start=start_date, 
                progress=False, 
                auto_adjust=True,
                multi_level_index=False
            )
            
            if df.empty or len(df) < 30:
                print(f"[警告] {ticker} 資料量不足或下載為空")
                return None

            # 處理多層欄位防禦
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # 標準化欄位名稱
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })
            
            # 時區處理：統一移除時區以利對齊
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            df.index.name = "date"
            df["symbol"] = ticker
            
            # 確保數值型別正確
            numeric_cols = ["open", "high", "low", "close", "volume"]
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(subset=["close"])
            
            return df
            
        except Exception as e:
            print(f"[錯誤] 下載 {ticker} 異常: {e}")
            return None

    def fetch_all_tech_data(self) -> Dict[str, pd.DataFrame]:
        """
        批次下載台美股追蹤名單
        """
        dataset = {}
        
        # 1. 台股
        print("下載台股數據...")
        for ticker, name in TECH_UNIVERSE_TW.items():
            df = self.fetch_ticker_data(ticker)
            if df is not None:
                dataset[ticker] = df

        # 2. 美股
        print("下載美股數據...")
        for ticker in TECH_UNIVERSE_US:
            df = self.fetch_ticker_data(ticker)
            if df is not None:
                dataset[ticker] = df

        print(f"數據下載完成，共成功載入 {len(dataset)} 檔標的。")
        return dataset
