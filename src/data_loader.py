"""
行情數據下載與標準化模組
"""
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import os

from src.config import config, TECH_UNIVERSE_US, TECH_UNIVERSE_TW

class TechDataLoader:
    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def fetch_finmind_taiwan_stock(self, ticker: str, days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        透過 FinMind 開放 API 抓取台股除權息還原之日 K 線資料 (防範 yfinance 假除權與 IP 封鎖)
        """
        clean_id = ticker.split(".")[0].strip()
        lookback = days if days else config.lookback_days
        start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")
        
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": clean_id,
            "start_date": start_date
        }
        
        try:
            resp = requests.get(url, params=params, timeout=12)
            if resp.status_code != 200:
                return None
            raw_data = resp.json().get("data", [])
            if not raw_data or len(raw_data) < 30:
                return None
                
            df = pd.DataFrame(raw_data)
            df = df.rename(columns={
                "date": "date",
                "open": "open",
                "max": "high",
                "min": "low",
                "close": "close",
                "Trading_Volume": "volume"
            })
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
            df["symbol"] = ticker
            
            numeric_cols = ["open", "high", "low", "close", "volume"]
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(subset=["close"])
            return df
        except Exception:
            return None

    def fetch_ticker_data(self, ticker: str, days: Optional[int] = None, force_refresh: bool = False, cache_only: bool = False) -> Optional[pd.DataFrame]:
        """
        下載單一標的歷史資料，支援本機當日快取 (避免每次重複連線等待)
        """
        cache_file = os.path.join(self.cache_dir, f"{ticker.replace('.', '_')}.csv")
        
        # 快取唯讀模式：若指定 cache_only 且檔案存在，直接讀取
        if cache_only and os.path.exists(cache_file):
            try:
                return pd.read_csv(cache_file, index_col="date", parse_dates=True)
            except Exception:
                pass

        # 快取檢查：若非強制刷新且快取為今天產生的，直接讀取本機快取 (0.01 秒)
        if not force_refresh and os.path.exists(cache_file):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if mtime.date() == datetime.now().date():
                    df = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                    return df
            except Exception:
                pass

        lookback = days if days else config.lookback_days
        min_rows = min(30, max(5, lookback // 3))
        start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")

        # 1. 若為台股標的，優先透過 FinMind 抓取乾淨還原日K (避免 yfinance 假除權與 IP 封鎖)
        is_tw = (".TW" in ticker) or (".TWO" in ticker)
        if is_tw:
            df_fm = self.fetch_finmind_taiwan_stock(ticker, days=lookback)
            if df_fm is not None and len(df_fm) >= min_rows:
                df_fm.to_csv(cache_file)
                return df_fm

        # 2. 美股標的，或台股 FinMind 失敗時，走 yfinance 備援
        try:
            df = yf.download(
                ticker, 
                start=start_date, 
                progress=False, 
                auto_adjust=True,
                multi_level_index=False
            )
            
            if df.empty or len(df) < min_rows:
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
            
            # 寫入本機快取
            df.to_csv(cache_file)
            return df
            
        except Exception as e:
            print(f"[錯誤] 下載 {ticker} 異常: {e}")
            return None

    def fetch_all_tech_data(self, force_refresh: bool = False, cache_only: bool = False) -> Dict[str, pd.DataFrame]:
        """
        批次下載台美股追蹤名單
        """
        dataset = {}
        
        # 1. 台股
        print("下載台股數據..." if not cache_only else "讀取台股快取數據...")
        for ticker, name in TECH_UNIVERSE_TW.items():
            df = self.fetch_ticker_data(ticker, force_refresh=force_refresh, cache_only=cache_only)
            if df is not None:
                dataset[ticker] = df

        # 2. 美股
        print("下載美股數據..." if not cache_only else "讀取美股快取數據...")
        for ticker in TECH_UNIVERSE_US:
            df = self.fetch_ticker_data(ticker, force_refresh=force_refresh, cache_only=cache_only)
            if df is not None:
                dataset[ticker] = df

        print(f"數據下載完成，共成功載入 {len(dataset)} 檔標的。")
        return dataset
