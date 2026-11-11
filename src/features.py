"""
科技股特徵工程與量化評分引擎 (基於 NumPy 與 Pandas 高速計算)
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from src.config import config, TECH_UNIVERSE_TW

class TechFeatureEngine:
    @staticmethod
    def calculate_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        為單一標的計算動能、均線趨勢、波動度與破新高指標
        """
        data = df.copy()
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
        data["above_50sma"] = close > data["sma_50"]
        data["above_200sma"] = close > data["sma_200"]
        
        # 3. 20日最高價突破指標 (Donchian Channel)
        data["high_20d"] = high.rolling(window=20).max()
        data["is_new_high_20d"] = close >= data["high_20d"].shift(1)
        
        # 4. 波動度與 ATR (真實波動區間)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data["atr_20"] = tr.rolling(window=20).mean()
        data["atr_pct"] = (data["atr_20"] / close) * 100
        
        # 5. 14 日 RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        data["rsi_14"] = 100 - (100 / (1 + rs))
        
        # 6. 綜合動能打分 (Tech Momentum Score)
        # 加權公式：40% 的 20日爆發 + 40% 的 60日季線波段 + 20% 的半年趨勢
        data["momentum_score"] = (
            data["roc_20"] * 0.4 +
            data["roc_60"] * 0.4 +
            data["roc_120"] * 0.2
        )
        
        return data

    @classmethod
    def evaluate_latest_ranking(cls, dataset: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        評估台股與美股當前的最新排名與操作建議
        """
        tw_records = []
        us_records = []
        
        for ticker, df in dataset.items():
            enriched_df = cls.calculate_technical_features(df)
            latest = enriched_df.iloc[-1]
            
            record = {
                "ticker": ticker,
                "name": TECH_UNIVERSE_TW.get(ticker, ticker),
                "price": round(float(latest["close"]), 2),
                "roc_20d": round(float(latest["roc_20"]), 2) if not np.isnan(latest["roc_20"]) else 0.0,
                "roc_60d": round(float(latest["roc_60"]), 2) if not np.isnan(latest["roc_60"]) else 0.0,
                "score": round(float(latest["momentum_score"]), 2) if not np.isnan(latest["momentum_score"]) else 0.0,
                "above_50sma": bool(latest["above_50sma"]),
                "above_200sma": bool(latest["above_200sma"]),
                "rsi": round(float(latest["rsi_14"]), 1) if not np.isnan(latest["rsi_14"]) else 50.0,
                "is_breakout": bool(latest["is_new_high_20d"]),
            }
            
            if ".TW" in ticker or ".TWO" in ticker:
                tw_records.append(record)
            else:
                us_records.append(record)
                
        # 轉成 DataFrame 並依據綜合動量評分 (score) 降序排序
        tw_rank_df = pd.DataFrame(tw_records).sort_values(by="score", ascending=False).reset_index(drop=True)
        us_rank_df = pd.DataFrame(us_records).sort_values(by="score", ascending=False).reset_index(drop=True)
        
        return tw_rank_df, us_rank_df
