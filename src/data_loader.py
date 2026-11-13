"""
行情數據下載與標準化模組 (強化版：時區精確校驗 + 智慧快取過期 + TWSE/FinMind備援補齊 + 橫截面前向填補)
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

    @staticmethod
    def get_taipei_now() -> pd.Timestamp:
        """取得當前台灣時區 (Asia/Taipei, UTC+8) 的時間"""
        return pd.Timestamp.now(tz="Asia/Taipei")

    @classmethod
    def get_expected_latest_close_date(cls, is_tw: bool) -> datetime.date:
        """
        市場最新應收盤日期計算 (Content-Date Aware)：
        - 台股 (Asia/Taipei):
          若平日在 13:35 (含) 之後，應收盤日即為當日；
          若平日在 13:35 之前，應為前一交易日；
          若週末 (週六/週日)，應為最近的週五。
        - 美股 (America/New_York):
          若美東時間平日在 16:10 (含) 之後，應收盤日即為當日；
          若美東時間平日在 16:10 之前，應為前一交易日；
          若週末 (週六/週日)，應為最近的週五。
        """
        if is_tw:
            now_tw = pd.Timestamp.now(tz="Asia/Taipei")
            if now_tw.weekday() < 5:
                target = now_tw if (now_tw.hour, now_tw.minute) >= (13, 35) else (now_tw - timedelta(days=1))
            else:
                target = now_tw
            while target.weekday() >= 5:
                target -= timedelta(days=1)
            return target.date()
        else:
            now_et = pd.Timestamp.now(tz="America/New_York")
            if now_et.weekday() < 5:
                target = now_et if (now_et.hour, now_et.minute) >= (16, 10) else (now_et - timedelta(days=1))
            else:
                target = now_et
            while target.weekday() >= 5:
                target -= timedelta(days=1)
            return target.date()

    def get_expected_latest_trading_date(self, is_tw: bool) -> datetime.date:
        """向下相容別名"""
        return self.get_expected_latest_close_date(is_tw)

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
        
        now_tw = self.get_taipei_now()
        start_date = (now_tw - timedelta(days=lookback)).strftime("%Y-%m-%d")
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": clean_id,
            "start_date": start_date
        }

        for attempt in range(3):
            try:
                res = requests.get(url, params=params, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("msg") == "success" and data.get("data"):
                        df = pd.DataFrame(data["data"])
                        if "date" in df.columns:
                            df["date"] = pd.to_datetime(df["date"])
                            df = df.set_index("date")
                            df = df.rename(columns={
                                "open": "open",
                                "max": "high",
                                "min": "low",
                                "close": "close",
                                "Trading_Volume": "volume"
                            })
                            df["symbol"] = ticker
                            df = self._clean_data_frame(df)
                            if len(df) >= min_rows:
                                return df
                time.sleep((2 ** attempt) + random.uniform(0.5, 1.0))
            except Exception:
                time.sleep((2 ** attempt) + random.uniform(0.5, 1.0))
        return None

    def fetch_twse_openapi_latest(self) -> Dict[str, dict]:
        """
        透過台灣證券交易所 OpenAPI 取得台股全市場當日收盤即時報價 (免費免金鑰官方備援)
        """
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                mapping = {}
                for item in data:
                    code = item.get("Code", "").strip()
                    try:
                        c_val = float(item.get("ClosingPrice", "0").replace(",", ""))
                        o_val = float(item.get("OpeningPrice", "0").replace(",", ""))
                        h_val = float(item.get("HighestPrice", "0").replace(",", ""))
                        l_val = float(item.get("LowestPrice", "0").replace(",", ""))
                        v_val = float(item.get("TradeVolume", "0").replace(",", ""))
                        if c_val > 0:
                            mapping[code] = {
                                "open": o_val if o_val > 0 else c_val,
                                "high": h_val if h_val > 0 else c_val,
                                "low": l_val if l_val > 0 else c_val,
                                "close": c_val,
                                "volume": v_val
                            }
                    except Exception:
                        continue
                return mapping
        except Exception:
            pass
        return {}

    def fetch_stooq_fallback(self, ticker: str, days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """
        美股 Stooq 開放行情下載備援 (免金鑰)
        """
        clean_ticker = ticker.lower()
        if not clean_ticker.endswith(".us"):
            clean_ticker = f"{clean_ticker}.us"
        url = f"https://stooq.com/q/d/l/?s={clean_ticker}&i=d"

        lookback = days if days else config.lookback_days
        min_rows = max(120, int(lookback * 0.45)) if lookback >= 365 else min(30, max(5, lookback // 3))
        
        now_tw = self.get_taipei_now()
        start_date = (now_tw - timedelta(days=lookback)).strftime("%Y-%m-%d")

        for attempt in range(3):
            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
                if res.status_code == 200 and "Date" in res.text:
                    import io
                    df = pd.read_csv(io.StringIO(res.text))
                    if not df.empty and "Date" in df.columns and "Close" in df.columns:
                        df["Date"] = pd.to_datetime(df["Date"])
                        df = df.set_index("Date").sort_index()
                        df = df.rename(columns={
                            "Open": "open",
                            "High": "high",
                            "Low": "low",
                            "Close": "close",
                            "Volume": "volume"
                        })
                        df = df[df.index >= start_date]
                        df["symbol"] = ticker
                        df = self._clean_data_frame(df)
                        if len(df) >= min_rows:
                            return df
                time.sleep((2 ** attempt) + random.uniform(0.5, 1.0))
            except Exception:
                time.sleep((2 ** attempt) + random.uniform(0.5, 1.0))
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
        強化型單一標的下載函式：
        1. 嚴格檢查快取時效 (對比最新預期交易日與基準日期)
        2. 台股 FinMind + TWSE 備援補齊
        3. 美股 yfinance (end+2日防截斷) + curl_cffi 偽裝 + Stooq 備援
        """
        is_tw = (".TW" in ticker) or (".TWO" in ticker)
        lookback = days if days else config.lookback_days
        if lookback >= 365:
            min_rows = max(120, int(lookback * 0.45))
        else:
            min_rows = min(30, max(5, lookback // 3))

        now_tw = self.get_taipei_now()
        start_date = (now_tw - timedelta(days=lookback)).strftime("%Y-%m-%d")
        end_date = (now_tw + timedelta(days=2)).strftime("%Y-%m-%d")
        cache_file = os.path.join(self.cache_dir, f"{ticker.replace(':', '_')}.csv")
        allow_save_cache = (days is None or days == config.lookback_days)

        # 1. 純快取模式
        if cache_only:
            if os.path.exists(cache_file):
                try:
                    df_cache = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                    df_cache = self._clean_data_frame(df_cache)
                    if len(df_cache) >= min_rows:
                        return df_cache
                except Exception:
                    pass
            return None

        # 2. 快取時效性精準檢查
        expected_date = self.get_expected_latest_trading_date(is_tw)
        if not force_refresh and os.path.exists(cache_file):
            try:
                df_cache = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                df_cache = self._clean_data_frame(df_cache)
                
                cache_lagging = False
                if not df_cache.empty:
                    last_cache_date = df_cache.index[-1].date()
                    # 若快取最新日期早於市場預期交易日，必須更新
                    if last_cache_date < expected_date:
                        cache_lagging = True
                    # 若有基準日期且快取落後於基準，必須更新
                    if benchmark_latest_date is not None and last_cache_date < benchmark_latest_date.date():
                        cache_lagging = True

                if not cache_lagging and len(df_cache) >= min_rows:
                    return df_cache
            except Exception:
                pass

        # 3. 台股優先嘗試 FinMind
        df_fm = None
        has_unadjusted_split = False
        if is_tw:
            df_fm = self.fetch_finmind_taiwan_stock(ticker, days=lookback)
            if df_fm is not None:
                df_fm = self._clean_data_frame(df_fm)
                has_unadjusted_split = bool((df_fm["close"].pct_change() < -0.35).any())
                
                fm_lagging = False
                if not df_fm.empty:
                    if df_fm.index[-1].date() < expected_date:
                        fm_lagging = True
                    if benchmark_latest_date is not None and df_fm.index[-1].date() < benchmark_latest_date.date():
                        fm_lagging = True

                # 若 FinMind 資料完整且無歷史假除權，直接採用
                if not fm_lagging and not has_unadjusted_split and len(df_fm) >= min_rows:
                    if allow_save_cache:
                        df_fm.to_csv(cache_file)
                    return df_fm

        # 4. yfinance 下載 (美股標的，或台股需取得完整調整後歷史)
        df = None
        for attempt in range(3):
            try:
                yf_session = self.curl_session if self.curl_session else None
                df = yf.download(
                    ticker, 
                    start=start_date,
                    end=end_date,
                    progress=False, 
                    auto_adjust=True,
                    multi_level_index=False,
                    session=yf_session
                )
                if df is None or df.empty:
                    df = yf.download(
                        ticker,
                        period="2y",
                        progress=False,
                        auto_adjust=True,
                        multi_level_index=False,
                        session=yf_session
                    )
                if df is not None and not df.empty:
                    break
            except Exception:
                time.sleep((2 ** attempt) + random.uniform(0.5, 1.2))

        # 5. 美股備援 (Stooq)
        if (df is None or df.empty) and not is_tw:
            stooq_df = self.fetch_stooq_fallback(ticker, days=lookback)
            if stooq_df is not None and len(stooq_df) >= min_rows:
                df = stooq_df

        # 若下載皆空，嘗試回退本機快取
        if df is None or df.empty:
            if os.path.exists(cache_file):
                try:
                    fallback_cache = pd.read_csv(cache_file, index_col="date", parse_dates=True)
                    fallback_cache = self._clean_data_frame(fallback_cache)
                    if len(fallback_cache) >= min_rows:
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

        # 6. 台股最新交易日拼接補齊 (FinMind 或 TWSE OpenAPI)
        if is_tw and not df.empty:
            # 優先以 FinMind 補足 yfinance 缺漏的最新幾根 K 棒
            if df_fm is not None and not df_fm.empty and df.index[-1] < df_fm.index[-1]:
                missing = df_fm[df_fm.index > df.index[-1]]
                if not missing.empty:
                    overlap_dates = df.index.intersection(df_fm.index)
                    can_stitch = False
                    if not overlap_dates.empty:
                        last_common = overlap_dates[-1]
                        yf_px = float(df.loc[last_common, "close"])
                        fm_px = float(df_fm.loc[last_common, "close"])
                        if yf_px > 0 and (abs(fm_px - yf_px) / yf_px) < 0.08:
                            can_stitch = True
                    else:
                        can_stitch = True

                    if can_stitch:
                        missing_clean = self._clean_data_frame(missing)
                        if not missing_clean.empty:
                            missing_clean["symbol"] = ticker
                            common_cols = [c for c in df.columns if c in missing_clean.columns]
                            df = pd.concat([df, missing_clean[common_cols]])
                            df = self._clean_data_frame(df)

            # 若仍落後於 expected_date，呼叫 TWSE OpenAPI 補入當日官方收盤
            if df.index[-1].date() < expected_date:
                clean_id = ticker.split(".")[0].strip()
                twse_all = self.fetch_twse_openapi_latest()
                if clean_id in twse_all:
                    item = twse_all[clean_id]
                    bar_dt = pd.Timestamp(expected_date)
                    new_row = pd.DataFrame([{
                        "open": item["open"],
                        "high": item["high"],
                        "low": item["low"],
                        "close": item["close"],
                        "volume": item["volume"],
                        "symbol": ticker
                    }], index=pd.DatetimeIndex([bar_dt], name="date"))
                    df = pd.concat([df, new_row])
                    df = self._clean_data_frame(df)

        # 幽靈 / 盤中未收盤 K 棒精確過濾：若包含晚於市場收盤預期日之數據，予以截斷保護
        if not df.empty and df.index[-1].date() > expected_date:
            df = df[df.index.date <= expected_date]

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
        批次下載台美股追蹤名單，具備單標的故障隔離 (Fault Isolation) 與橫截面無損對齊
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

        # 橫截面日期一致性校驗 (台股)：以全體最遠交易日為準，落後標的前向填補 (ffill)，絕不截斷最新交易日
        tw_tickers = [t for t in TECH_UNIVERSE_TW.keys() if t in dataset]
        if tw_tickers:
            max_tw_date = max(dataset[t].index[-1].date() for t in tw_tickers)
            for t in tw_tickers:
                d = dataset[t]
                if not d.empty and d.index[-1].date() < max_tw_date:
                    # 使用前向填補 (ffill) 延伸最後一筆數據至 max_tw_date，避免全域截斷
                    last_row = d.iloc[-1:].copy()
                    last_row.index = pd.DatetimeIndex([pd.Timestamp(max_tw_date)], name="date")
                    dataset[t] = pd.concat([d, last_row])
                    dataset[t] = dataset[t][~dataset[t].index.duplicated(keep="last")].sort_index()

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

        # 橫截面日期一致性校驗 (美股)：以全體最遠交易日為準，落後標的前向填補 (ffill)
        us_tickers = [t for t in TECH_UNIVERSE_US if t in dataset]
        if us_tickers:
            max_us_date = max(dataset[t].index[-1].date() for t in us_tickers)
            for t in us_tickers:
                d = dataset[t]
                if not d.empty and d.index[-1].date() < max_us_date:
                    last_row = d.iloc[-1:].copy()
                    last_row.index = pd.DatetimeIndex([pd.Timestamp(max_us_date)], name="date")
                    dataset[t] = pd.concat([d, last_row])
                    dataset[t] = dataset[t][~dataset[t].index.duplicated(keep="last")].sort_index()

        print(f"數據下載完成，共成功載入 {len(dataset)} 檔標的。")
        return dataset
