"""
行情數據下載與標準化模組 (強化版：curl_cffi 瀏覽器指紋偽裝 + 指數退避重試 + 單標的故障隔離 + 免費多源備援)
"""
import time
import random
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import pandas as pd
import requests

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

import yfinance as yf
from src.config import config, TECH_UNIVERSE_US, TECH_UNIVERSE_TW

class TechDataLoader:
    def __init__(self, cache_dir: str = "data_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.curl_session = None
        if CURL_CFFI_AVAILABLE:
            try:
                self.curl_session = curl_requests.Session(impersonate="chrome")
            except Exception:
                self.curl_session = None

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
        具備 3 次指數退避重試機制
        """
        clean_id = ticker.split(".")[0].strip()
        lookback = days if days else config.lookback_days
        if lookback >= 365:
            min_rows = max(120, int(lookback * 0.45))
        else:
            min_rows = min(30, max(5, lookback // 3))
        start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")
        
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": clean_id,
            "start_date": start_date
        }
        
        for attempt in range(3):
            try:
                resp = requests.get(url, params=params, timeout=12)
                if resp.status_code != 200:
                    time.sleep(1.0 + attempt * 1.5)
                    continue
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
                
                df = self._clean_data_frame(df)
                if df.empty or len(df) < min_rows:
                    return None
                return df
            except Exception:
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        return None

    def fetch_twse_openapi_latest(self) -> Dict[str, Dict]:
        """
        備援：從臺灣證券交易所 OpenAPI 抓取所有上市公司當日最新收盤行情
        """
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return {}
            data = resp.json()
            result = {}
            for row in data:
                code = row.get("Code", "").strip()
                if not code:
                    continue
                try:
                    # 轉換民國年為西元年 '1151111' -> '2026-11-11'
                    raw_d = str(row.get("Date", "")).strip()
                    if len(raw_d) >= 7:
                        y = int(raw_d[:-4]) + 1911
                        m = int(raw_d[-4:-2])
                        d = int(raw_d[-2:])
                        dt = datetime(y, m, d)
                    else:
                        dt = datetime.now()
                    
                    c_px = float(str(row.get("ClosingPrice", "0")).replace(",", ""))
                    o_px = float(str(row.get("OpeningPrice", "0")).replace(",", ""))
                    h_px = float(str(row.get("HighestPrice", "0")).replace(",", ""))
                    l_px = float(str(row.get("LowestPrice", "0")).replace(",", ""))
                    vol = float(str(row.get("TradeVolume", "0")).replace(",", ""))
                    if c_px > 0 and vol > 0:
                        result[code] = {
                            "date": dt,
                            "open": o_px if o_px > 0 else c_px,
                            "high": h_px if h_px > 0 else c_px,
                            "low": l_px if l_px > 0 else c_px,
                            "close": c_px,
                            "volume": vol
                        }
                except Exception:
                    continue
            return result
        except Exception:
            return {}

    def fetch_stooq_fallback(self, ticker: str, days: int = 100) -> Optional[pd.DataFrame]:
        """
        備援：美股從 Stooq 抓取日 K 線 (當 yfinance 受阻時的第三層備援)
        """
        clean_sym = ticker.replace("-", ".").lower()
        url = f"https://stooq.com/q/d/l/?s={clean_sym}.us&i=d"
        try:
            req_func = self.curl_session.get if self.curl_session else requests.get
            resp = req_func(url, timeout=10)
            if resp.status_code == 200 and "Date" in resp.text and "<html" not in resp.text:
                import io
                df = pd.read_csv(io.StringIO(resp.text))
                if not df.empty and {"Date", "Open", "High", "Low", "Close", "Volume"}.issubset(df.columns):
                    df = df.rename(columns={
                        "Date": "date", "Open": "open", "High": "high",
                        "Low": "low", "Close": "close", "Volume": "volume"
                    })
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                    df["symbol"] = ticker
                    return self._clean_data_frame(df)
        except Exception:
            pass
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
        下載單一標的歷史資料，具備 curl_cffi 偽裝、指數退避重試與故障隔離保護
        """
        cache_file = os.path.join(self.cache_dir, f"{ticker.replace('.', '_')}.csv")
        lookback = days if days else config.lookback_days
        if lookback >= 365:
            min_rows = max(120, int(lookback * 0.45))
        else:
            min_rows = min(30, max(5, lookback // 3))
        start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")
        allow_save_cache = (days is None) or (days >= config.lookback_days)

        # 1. 快取唯讀模式
        if cache_only and os.path.exists(cache_file):
            try:
                df = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                df = self._clean_data_frame(df)
                return df if len(df) >= min_rows else None
            except Exception:
                pass

        # 2. 快取時效檢查
        if not force_refresh and os.path.exists(cache_file):
            try:
                df_cache = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                df_cache = self._clean_data_frame(df_cache)
                
                cache_lagging = False
                if benchmark_latest_date is not None and not df_cache.empty:
                    if df_cache.index[-1].date() < benchmark_latest_date.date():
                        cache_lagging = True

                tw_tz = timezone(timedelta(hours=8))
                now_tw = datetime.now(tw_tz)
                mtime_tw = datetime.fromtimestamp(os.path.getmtime(cache_file), tz=tw_tz)
                is_tw_ticker = (".TW" in ticker) or (".TWO" in ticker)
                if is_tw_ticker:
                    cutoff_tw = now_tw.replace(hour=13, minute=40, second=0, microsecond=0)
                    if now_tw >= cutoff_tw and mtime_tw < cutoff_tw:
                        cache_lagging = True

                if not cache_lagging and mtime_tw.date() == now_tw.date() and len(df_cache) >= min_rows:
                    return df_cache
            except Exception:
                pass

        # 3. 台股優先走 FinMind
        is_tw = (".TW" in ticker) or (".TWO" in ticker)
        df_fm = None
        has_unadjusted_split = False
        if is_tw:
            df_fm = self.fetch_finmind_taiwan_stock(ticker, days=lookback)
            if df_fm is not None:
                df_fm = self._clean_data_frame(df_fm)
                has_unadjusted_split = bool((df_fm["close"].pct_change() < -0.35).any())
                
                fm_lagging = False
                if benchmark_latest_date is not None and not df_fm.empty:
                    if df_fm.index[-1].date() < benchmark_latest_date.date():
                        fm_lagging = True

                if not fm_lagging and not has_unadjusted_split and len(df_fm) >= min_rows:
                    if allow_save_cache:
                        df_fm.to_csv(cache_file)
                    return df_fm

        # 4. 美股標的，或台股 FinMind 失敗/落後時，走 yfinance 搭配 curl_cffi 與指數退避 3 次重試
        df = None
        for attempt in range(3):
            try:
                # 優先使用 curl_cffi 偽裝的 Session，徹底繞過 GitHub Actions 雲端 IP 的 429 Rate Limit
                yf_session = self.curl_session if self.curl_session else None
                df = yf.download(
                    ticker, 
                    start=start_date, 
                    progress=False, 
                    auto_adjust=True,
                    multi_level_index=False,
                    session=yf_session
                )
                if df is not None and not df.empty:
                    break
            except Exception as e:
                # 指數退避等待 (1s, 2s, 4s + 隨機擾動)
                sleep_sec = (2 ** attempt) + random.uniform(0.5, 1.2)
                time.sleep(sleep_sec)

        # 5. yfinance 仍失敗時的美股備援 (Stooq)
        if (df is None or df.empty) and not is_tw:
            stooq_df = self.fetch_stooq_fallback(ticker, days=lookback)
            if stooq_df is not None and len(stooq_df) >= min_rows:
                df = stooq_df

        if df is None or df.empty:
            # 容錯回退：若網路抓取失敗但本機已有歷史快取，優先回傳既有快取避免斷頭
            if os.path.exists(cache_file):
                try:
                    fallback_cache = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                    fallback_cache = self._clean_data_frame(fallback_cache)
                    if len(fallback_cache) >= min_rows:
                        print(f"⚠️ {ticker} 網路下載受阻，使用本機既有快取平穩回退。")
                        return fallback_cache
                except Exception:
                    pass
            print(f"[警告] {ticker} 資料量不足或下載為空")
            return None

        # 欄位標準化與時區對齊
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df.index.name = "date"
        df["symbol"] = ticker
        df = self._clean_data_frame(df)
        
        # 若為台股且 FinMind 最新日期更即時，以 FinMind 補齊
        if is_tw and df_fm is not None and not df_fm.empty and not df.empty and not has_unadjusted_split:
            if df.index[-1] < df_fm.index[-1]:
                missing = df_fm[df_fm.index > df.index[-1]]
                if not missing.empty:
                    overlap_dates = df.index.intersection(df_fm.index)
                    can_stitch = False
                    if not overlap_dates.empty:
                        last_common = overlap_dates[-1]
                        yf_px = float(df.loc[last_common, "close"])
                        fm_px = float(df_fm.loc[last_common, "close"])
                        if yf_px > 0 and (abs(fm_px - yf_px) / yf_px) < 0.03:
                            can_stitch = True
                    
                    if can_stitch:
                        missing_clean = self._clean_data_frame(missing)
                        if not missing_clean.empty:
                            missing_clean["symbol"] = ticker
                            common_cols = [c for c in df.columns if c in missing_clean.columns]
                            df = pd.concat([df, missing_clean[common_cols]])
                            df = self._clean_data_frame(df)

        if df.empty or len(df) < min_rows:
            if os.path.exists(cache_file):
                try:
                    fallback_cache = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                    fallback_cache = self._clean_data_frame(fallback_cache)
                    if len(fallback_cache) >= min_rows:
                        return fallback_cache
                except Exception:
                    pass
            print(f"[警告] {ticker} 清洗後資料量不足 ({len(df)} < {min_rows})")
            return None

        if allow_save_cache:
            df.to_csv(cache_file)
        return df

    def fetch_all_tech_data(self, force_refresh: bool = False, cache_only: bool = False) -> Dict[str, pd.DataFrame]:
        """
        批次下載台美股追蹤名單，具備單標的故障隔離 (Fault Isolation)
        個別標的異常只記錄 Warning 並優雅跳過，嚴禁拋出例外中斷管線
        """
        dataset = {}
        
        # 1. 台股
        print("下載台股數據..." if not cache_only else "讀取台股快取數據...")
        # 基準標的 0050.TW (帶故障隔離保護)
        try:
            bench_tw = self.fetch_ticker_data("0050.TW", force_refresh=force_refresh, cache_only=cache_only)
            bench_tw_date = bench_tw.index[-1] if bench_tw is not None and not bench_tw.empty else None
            if bench_tw is not None and not bench_tw.empty:
                dataset["0050.TW"] = bench_tw
        except Exception as e:
            print(f"⚠️ 基準 0050.TW 下載異常 (已隔離): {e}")
            bench_tw_date = None

        # 批次下載台股成分股 (故障隔離)
        for ticker in TECH_UNIVERSE_TW.keys():
            if ticker == "0050.TW":
                continue
            try:
                df = self.fetch_ticker_data(
                    ticker, 
                    force_refresh=force_refresh, 
                    cache_only=cache_only,
                    benchmark_latest_date=bench_tw_date
                )
                if df is not None and not df.empty:
                    dataset[ticker] = df
            except Exception as e:
                print(f"⚠️ 個別標的 {ticker} 下載異常，已優雅跳過保護管線: {e}")

        # 橫截面最後日期一致性校驗 (台股)
        tw_tickers = [t for t in TECH_UNIVERSE_TW.keys() if t in dataset]
        if tw_tickers:
            if "0050.TW" in dataset and not dataset["0050.TW"].empty:
                target_tw_date = dataset["0050.TW"].index[-1].date()
            else:
                tw_dates_series = pd.Series([dataset[t].index[-1].date() for t in tw_tickers])
                target_tw_date = tw_dates_series.mode()[0]
            for t in tw_tickers:
                d = dataset[t]
                if not d.empty and d.index[-1].date() > target_tw_date:
                    dataset[t] = d[d.index.date <= target_tw_date]

        # 2. 美股
        print("下載美股數據..." if not cache_only else "讀取美股快取數據...")
        # 基準標的 QQQ (帶故障隔離保護)
        try:
            bench_us = self.fetch_ticker_data("QQQ", force_refresh=force_refresh, cache_only=cache_only)
            bench_us_date = bench_us.index[-1] if bench_us is not None and not bench_us.empty else None
            if bench_us is not None and not bench_us.empty:
                dataset["QQQ"] = bench_us
        except Exception as e:
            print(f"⚠️ 基準 QQQ 下載異常 (已隔離): {e}")
            bench_us_date = None

        # 批次下載美股成分股 (故障隔離)
        for ticker in TECH_UNIVERSE_US:
            if ticker == "QQQ":
                continue
            try:
                df = self.fetch_ticker_data(
                    ticker, 
                    force_refresh=force_refresh, 
                    cache_only=cache_only,
                    benchmark_latest_date=bench_us_date
                )
                if df is not None and not df.empty:
                    dataset[ticker] = df
            except Exception as e:
                print(f"⚠️ 個別標的 {ticker} 下載異常，已優雅跳過保護管線: {e}")

        # 橫截面最後日期一致性校驗 (美股)
        us_tickers = [t for t in TECH_UNIVERSE_US if t in dataset]
        if us_tickers:
            if "QQQ" in dataset and not dataset["QQQ"].empty:
                target_us_date = dataset["QQQ"].index[-1].date()
            else:
                us_dates_series = pd.Series([dataset[t].index[-1].date() for t in us_tickers])
                target_us_date = us_dates_series.mode()[0]
            for t in us_tickers:
                d = dataset[t]
                if not d.empty and d.index[-1].date() > target_us_date:
                    dataset[t] = d[d.index.date <= target_us_date]

        print(f"數據下載完成，共成功載入 {len(dataset)} 檔標的。")
        return dataset
