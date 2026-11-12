"""
技術特徵計算與排序評分引擎
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple
from src.config import config, TECH_UNIVERSE_TW

class TechFeatureEngine:
    @staticmethod
    def calculate_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        計算技術指標：動能 (ROC)、均線濾網 (SMA)、突破線與波動度 (ATR)
        """
        data = df.copy()
        # 強制過濾無效交易日 (volume <= 0 或 close <= 0) 並去重排序
        if "volume" in data.columns and "close" in data.columns:
            numeric_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in data.columns]
            data[numeric_cols] = data[numeric_cols].apply(pd.to_numeric, errors="coerce")
            data = data.dropna(subset=["close", "volume"])
            data = data[(data["volume"] > 0) & (data["close"] > 0)]
        data = data[~data.index.duplicated(keep="last")].sort_index()

        close = data["close"]
        high = data["high"]
        low = data["low"]
        
        # 1. 動能指標 (ROC - Rate of Change)
        data["roc_20"] = close.pct_change(config.short_momentum_window) * 100
        data["roc_60"] = close.pct_change(config.medium_momentum_window) * 100
        data["roc_120"] = close.pct_change(config.long_momentum_window) * 100
        
        # 2. 趨勢濾網均線 (SMA)
        data["sma_50"] = close.rolling(window=config.trend_filter_sma).mean()
        data["sma_200"] = close.rolling(window=config.long_term_sma).mean()
        data["above_50sma"] = close >= data["sma_50"]
        data["above_200sma"] = close >= data["sma_200"]
        
        # 3. 20日最高價突破指標 (Donchian Channel)
        data["high_20d"] = high.rolling(window=20).max()
        data["is_new_high_20d"] = close >= data["high_20d"].shift(1)
        
        # 4. ATR (真實波動區間)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data["atr_20"] = tr.rolling(window=20).mean()
        data["atr_pct"] = (data["atr_20"] / close.replace(0, np.nan)) * 100
        
        # 5. 14 日 RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(window=14).mean()
        loss = (-delta.clip(upper=0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        data["rsi_14"] = 100 - (100 / (1 + rs))
        
        # 6. KD (9, 3, 3) 隨機指標計算
        low_9 = low.rolling(window=9).min()
        high_9 = high.rolling(window=9).max()
        rsv = ((close - low_9) / (high_9 - low_9).replace(0, np.nan)) * 100
        rsv = rsv.fillna(50)
        
        k_list, d_list = [], []
        k, d = 50.0, 50.0
        for val in rsv:
            k = (2.0 / 3.0) * k + (1.0 / 3.0) * val
            d = (2.0 / 3.0) * d + (1.0 / 3.0) * k
            k_list.append(round(k, 2))
            d_list.append(round(d, 2))
            
        data["k_9"] = k_list
        data["d_9"] = d_list
        
        # 7. 20MA (月線)
        data["sma_20"] = close.rolling(window=20).mean()

        # 8. 綜合動能評分 (權重: 20日 40%, 60日 40%, 120日 20%)
        data["momentum_score"] = (
            data["roc_20"].fillna(0) * 0.4 +
            data["roc_60"].fillna(0) * 0.4 +
            data["roc_120"].fillna(0) * 0.2
        )
        
        return data

    @classmethod
    def evaluate_latest_ranking(cls, dataset: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        評估台美股最新動能排名與趨勢狀態
        """
        tw_records = []
        us_records = []
        
        for ticker, df in dataset.items():
            enriched_df = cls.calculate_technical_features(df)
            if enriched_df.empty:
                continue
            latest = enriched_df.iloc[-1]
            latest_date_str = enriched_df.index[-1].strftime("%Y-%m-%d")
            score_val = round(float(latest["momentum_score"]), 2) if not np.isnan(latest["momentum_score"]) else 0.0
            
            record = {
                "ticker": ticker,
                "name": TECH_UNIVERSE_TW.get(ticker, ticker),
                "data_date": latest_date_str,
                "price": round(float(latest["close"]), 2),
                "roc_20d": round(float(latest["roc_20"]), 2) if not np.isnan(latest["roc_20"]) else 0.0,
                "roc_60d": round(float(latest["roc_60"]), 2) if not np.isnan(latest["roc_60"]) else 0.0,
                "score": score_val,
                "composite_score": score_val,
                "above_50sma": bool(latest["above_50sma"]),
                "above_200sma": bool(latest["above_200sma"]),
                "rsi": round(float(latest["rsi_14"]), 1) if not np.isnan(latest["rsi_14"]) else 50.0,
                "k9": round(float(latest["k_9"]), 1) if not np.isnan(latest["k_9"]) else 50.0,
                "d9": round(float(latest["d_9"]), 1) if not np.isnan(latest["d_9"]) else 50.0,
                "is_breakout": bool(latest["is_new_high_20d"]),
            }
            
            if ".TW" in ticker or ".TWO" in ticker:
                tw_records.append(record)
            else:
                us_records.append(record)
                
        tw_rank_df = pd.DataFrame(tw_records).sort_values(by="score", ascending=False).reset_index(drop=True)
        us_rank_df = pd.DataFrame(us_records).sort_values(by="score", ascending=False).reset_index(drop=True)
        
        return tw_rank_df, us_rank_df
