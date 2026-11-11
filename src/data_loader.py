"""
行情數據下載與標準化模組
"""
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import os

from src.config import config, TECH_UNIVERSE_US, TECH_UNIVERSE_TW

class TechDataLoader:
    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _clean_data_frame(self, df_in: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        標準化資料清理函式：
        1. 強制過濾掉 volume <= 0 或 close <= 0 的無效交易日 (防範幽靈 K 棒)
        2. 依日期排序並去除重複列
        """
        if df_in is None or df_in.empty:
            return pd.DataFrame()
        
        df_cleaned = df_in.copy()
        numeric_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df_cleaned.columns]
        df_cleaned[numeric_cols] = df_cleaned[numeric_cols].apply(pd.to_numeric, errors="coerce")
        df_cleaned = df_cleaned.dropna(subset=["close", "volume"])
        df_cleaned = df_cleaned[(df_cleaned["volume"] > 0) & (df_cleaned["close"] > 0)]
        df_cleaned = df_cleaned[~df_cleaned.index.duplicated(keep="last")].sort_index()
        return df_cleaned

    def fetch_finmind_taiwan_stock(self, ticker: str, days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        透過 FinMind 開放 API 抓取台股除權息還原之日 K 線資料 (防範 yfinance 假除權與 IP 封鎖)
        """
        clean_id = ticker.split(".")[0].strip()
        lookback = days if days else config.lookback_days
        min_rows = min(30, max(5, lookback // 3))
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
            if not raw_data or len(raw_data) < min_rows:
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
            
            # 強制清洗幽靈 K 棒 (volume <= 0 或 close <= 0)
            df = self._clean_data_frame(df)
            if df.empty or len(df) < min_rows:
                return None
            return df
        except Exception:
            return None

    def fetch_ticker_data(
        self, 
        ticker: str, 
        days: Optional[int] = None, 
        force_refresh: bool = False, 
        cache_only: bool = False,
        benchmark_latest_date: Optional[pd.Timestamp] = None
    ) -> Optional[pd.DataFrame]:
        """
        下載單一標的歷史資料，支援本機當日快取與基準標的日期同步檢驗
        """
        cache_file = os.path.join(self.cache_dir, f"{ticker.replace('.', '_')}.csv")
        lookback = days if days else config.lookback_days
        min_rows = min(30, max(5, lookback // 3))
        start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")

        # 快取唯讀模式：若指定 cache_only 且檔案存在，直接讀取並清洗
        if cache_only and os.path.exists(cache_file):
            try:
                df = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                df = self._clean_data_frame(df)
                return df if len(df) >= min_rows else None
            except Exception:
                pass

        # 快取檢查：若非強制刷新且快取存在
        if not force_refresh and os.path.exists(cache_file):
            try:
                df_cache = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                df_cache = self._clean_data_frame(df_cache)
                
                # 檢查快取最新日期是否落後於同市場基準標的 (0050.TW 或 QQQ)
                cache_lagging = False
                if benchmark_latest_date is not None and not df_cache.empty:
                    if df_cache.index[-1].date() < benchmark_latest_date.date():
                        cache_lagging = True

                # 同日快取時效校驗：
                # 若為台股且當前台灣時間已過 13:40，但快取檔案修改時間早於當日 13:40，視為過期舊快取，強制重新向 API 下載
                tw_tz = timezone(timedelta(hours=8))
                now_tw = datetime.now(tw_tz)
                mtime_tw = datetime.fromtimestamp(os.path.getmtime(cache_file), tz=tw_tz)
                is_tw_ticker = (".TW" in ticker) or (".TWO" in ticker)
                if is_tw_ticker:
                    cutoff_tw = now_tw.replace(hour=13, minute=40, second=0, microsecond=0)
                    if now_tw >= cutoff_tw and mtime_tw < cutoff_tw:
                        cache_lagging = True

                # 只有在快取未落後且非過期、且為當日產生、資料行數足夠時，才允許命中快取
                if not cache_lagging and mtime_tw.date() == now_tw.date() and len(df_cache) >= min_rows:
                    return df_cache
            except Exception:
                pass

        # 1. 若為台股標的，優先透過 FinMind 抓取乾淨還原日K (避免 yfinance 假除權與 IP 封鎖)
        is_tw = (".TW" in ticker) or (".TWO" in ticker)
        if is_tw:
            df_fm = self.fetch_finmind_taiwan_stock(ticker, days=lookback)
            if df_fm is not None:
                df_fm = self._clean_data_frame(df_fm)
                # 檢查 FinMind 是否有未還原股票分割 (台股單日漲跌幅上限為 10%，跌幅 > 35% 必為未還原分割)
                has_unadjusted_split = (df_fm["close"].pct_change() < -0.35).any()
                if not has_unadjusted_split and len(df_fm) >= min_rows:
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
            
            if df.empty:
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
            
            # 強制清洗無效 K 棒 (volume <= 0 或 close <= 0)
            df = self._clean_data_frame(df)
            
            if df.empty or len(df) < min_rows:
                print(f"[警告] {ticker} 清洗後資料量不足 ({len(df)} < {min_rows})")
                return None

            # 寫入本機快取
            df.to_csv(cache_file)
            return df
            
        except Exception as e:
            print(f"[錯誤] 下載 {ticker} 異常: {e}")
            return None

    def fetch_all_tech_data(self, force_refresh: bool = False, cache_only: bool = False) -> Dict[str, pd.DataFrame]:
        """
        批次下載台美股追蹤名單，確保同市場標的最後一根 K 棒日期對齊一致
        """
        dataset = {}
        
        # 1. 台股
        print("下載台股數據..." if not cache_only else "讀取台股快取數據...")
        # 優先抓取台股基準 0050.TW 取得基準最新日期
        bench_tw = self.fetch_ticker_data("0050.TW", force_refresh=force_refresh, cache_only=cache_only)
        bench_tw_date = bench_tw.index[-1] if bench_tw is not None and not bench_tw.empty else None
        if bench_tw is not None:
            dataset["0050.TW"] = bench_tw

        # 批次下載其餘台股標的 (若快取日期落後於 0050.TW 則強制重拉)
        for ticker in TECH_UNIVERSE_TW.keys():
            if ticker == "0050.TW":
                continue
            df = self.fetch_ticker_data(
                ticker, 
                force_refresh=force_refresh, 
                cache_only=cache_only,
                benchmark_latest_date=bench_tw_date
            )
            if df is not None:
                dataset[ticker] = df

        # 【橫截面對齊二次校驗】：檢查台股中是否有任何標的日期高於基準或相互不同步
        if not cache_only:
            tw_tickers = [t for t in TECH_UNIVERSE_TW.keys() if t in dataset]
            if tw_tickers:
                max_tw_date = max(dataset[t].index[-1] for t in tw_tickers)
                for t in tw_tickers:
                    if dataset[t].index[-1].date() < max_tw_date.date():
                        print(f"🔄 偵測到 {t} 日期 ({dataset[t].index[-1].strftime('%Y-%m-%d')}) 落後最新日期 ({max_tw_date.strftime('%Y-%m-%d')})，強制重新拉取對齊...")
                        df_refreshed = self.fetch_ticker_data(
                            t, 
                            force_refresh=True, 
                            benchmark_latest_date=max_tw_date
                        )
                        if df_refreshed is not None:
                            dataset[t] = df_refreshed

        # 2. 美股
        print("下載美股數據..." if not cache_only else "讀取美股快取數據...")
        # 優先抓取美股基準 QQQ 取得基準最新日期
        bench_us = self.fetch_ticker_data("QQQ", force_refresh=force_refresh, cache_only=cache_only)
        bench_us_date = bench_us.index[-1] if bench_us is not None and not bench_us.empty else None
        if bench_us is not None:
            dataset["QQQ"] = bench_us

        for ticker in TECH_UNIVERSE_US:
            if ticker == "QQQ":
                continue
            df = self.fetch_ticker_data(
                ticker, 
                force_refresh=force_refresh, 
                cache_only=cache_only,
                benchmark_latest_date=bench_us_date
            )
            if df is not None:
                dataset[ticker] = df

        # 【橫截面對齊二次校驗】：檢查美股標的日期是否對齊
        if not cache_only:
            us_tickers = [t for t in TECH_UNIVERSE_US if t in dataset]
            if us_tickers:
                max_us_date = max(dataset[t].index[-1] for t in us_tickers)
                for t in us_tickers:
                    if dataset[t].index[-1].date() < max_us_date.date():
                        print(f"🔄 偵測到 {t} 日期 ({dataset[t].index[-1].strftime('%Y-%m-%d')}) 落後最新日期 ({max_us_date.strftime('%Y-%m-%d')})，強制重新拉取對齊...")
                        df_refreshed = self.fetch_ticker_data(
                            t, 
                            force_refresh=True, 
                            benchmark_latest_date=max_us_date
                        )
                        if df_refreshed is not None:
                            dataset[t] = df_refreshed

        print(f"數據下載完成，共成功載入 {len(dataset)} 檔標的。")
        return dataset
