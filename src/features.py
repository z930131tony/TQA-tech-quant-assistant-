"""
技術特徵計算與排序評分引擎 (升級版：Numba 向量化加速 + 波動率調整夏普動能 + 縮量洗盤與爆量出貨量價判定)
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

from src.config import config, TECH_UNIVERSE_TW

if NUMBA_AVAILABLE:
    @njit(fastmath=True)
    def _numba_kd_calculator(rsv_arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        n = len(rsv_arr)
        k_arr = np.empty(n, dtype=np.float64)
        d_arr = np.empty(n, dtype=np.float64)
        k, d = 50.0, 50.0
        for i in range(n):
            val = rsv_arr[i]
            if np.isnan(val):
                val = 50.0
            k = (2.0 / 3.0) * k + (1.0 / 3.0) * val
            d = (2.0 / 3.0) * d + (1.0 / 3.0) * k
            k_arr[i] = round(k, 2)
            d_arr[i] = round(d, 2)
        return k_arr, d_arr
else:
    def _numba_kd_calculator(rsv_arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        k_list, d_list = [], []
        k, d = 50.0, 50.0
        for val in rsv_arr:
            v = 50.0 if np.isnan(val) else val
            k = (2.0 / 3.0) * k + (1.0 / 3.0) * v
            d = (2.0 / 3.0) * d + (1.0 / 3.0) * k
            k_list.append(round(k, 2))
            d_list.append(round(d, 2))
        return np.array(k_list), np.array(d_list)

class TechFeatureEngine:
    @staticmethod
    def calculate_technical_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        計算技術指標：動能 (ROC)、均線濾網 (SMA)、突破線、波動度 (ATR)、
        波動率調整夏普動能 (Volatility-Adjusted Momentum) 與量價結構訊號 (洗盤/出貨)
        """
        data = df.copy()
        if "volume" in data.columns and "close" in data.columns:
            numeric_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in data.columns]
            data[numeric_cols] = data[numeric_cols].apply(pd.to_numeric, errors="coerce")
            data = data.dropna(subset=["close", "volume"])
            data = data[(data["volume"] > 0) & (data["close"] > 0)]
        data = data[~data.index.duplicated(keep="last")].sort_index()

        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]
        
        # 1. 動能指標 (ROC - Rate of Change) 與真實單日漲跌幅 (ret_1d)
        data["ret_1d"] = close.pct_change(1) * 100
        data["chg_1d"] = data["ret_1d"]
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
        data["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))
        
        # 6. KD (9, 3, 3) 隨機指標計算 (由 Numba 高速向量化核心運算)
        low_9 = low.rolling(window=9).min()
        high_9 = high.rolling(window=9).max()
        rsv = ((close - low_9) / (high_9 - low_9).replace(0, np.nan)) * 100
        rsv_arr = rsv.fillna(50).to_numpy(dtype=np.float64)
        k_arr, d_arr = _numba_kd_calculator(rsv_arr)
        data["k_9"] = k_arr
        data["d_9"] = d_arr
        
        # 7. 20MA (月線) 與成交量均線
        data["sma_20"] = close.rolling(window=20).mean()
        data["vol_sma_3"] = volume.rolling(window=3).mean()
        data["vol_sma_20"] = volume.rolling(window=20).mean()

        # 8. 波動率調整後夏普動能 (Volatility-Adjusted Momentum)
        # 以年化波動率標準差作為分母，防止追高無實質基本面暴衝妖股
        daily_ret = close.pct_change()
        vol_20 = daily_ret.rolling(20).std() * np.sqrt(252) * 100
        vol_60 = daily_ret.rolling(60).std() * np.sqrt(252) * 100
        data["vol_adj_roc_20"] = data["roc_20"] / (vol_20.replace(0, np.nan).fillna(20.0) + 1.0)
        data["vol_adj_roc_60"] = data["roc_60"] / (vol_60.replace(0, np.nan).fillna(20.0) + 1.0)
        data["vol_adjusted_momentum"] = data["vol_adj_roc_20"] * 0.5 + data["vol_adj_roc_60"] * 0.5

        # 9. 量價結構布林訊號
        # 9A. is_shakeout_buy (10% 階梯縮量洗盤買點)：
        # 自近 20 日最高點回檔滿 10%~30%，且近 3 日均量 < 20 日均量的 70% (主力縮量洗盤確立)
        pullback_pct = ((data["high_20d"] - close) / data["high_20d"]) * 100
        data["is_shakeout_buy"] = (
            (pullback_pct >= 10.0) & 
            (pullback_pct <= 30.0) & 
            (data["vol_sma_3"] < data["vol_sma_20"] * 0.70)
        ).fillna(False)

        # 9B. is_distribution_warn (爆量出貨警訊)：
        # 近 5 日價格緩跌或滯漲 (5日報酬 <= 1.0%)，且成交量 > 20 日均量 1.5 倍
        # 排除「低檔恐慌爆量長下影線換手 (Panic Capitulation)」誤判：
        # 若收紅 K (close > open) 且下影線 (min(open, close) - low) 大於實體長度 1.5 倍，不列為出貨警告
        open_p = data["open"]
        lower_shadow = np.minimum(open_p, close) - low
        candle_body = (close - open_p).abs()
        is_panic_capitulation = (close > open_p) & (lower_shadow > candle_body * 1.5)

        ret_5d = close.pct_change(5) * 100
        raw_dist_warn = (ret_5d <= 1.0) & (volume > data["vol_sma_20"] * 1.50)
        data["is_distribution_warn"] = (raw_dist_warn & ~is_panic_capitulation).fillna(False)

        # 9C. 考夫曼效率係數 (KER - Kaufman Efficiency Ratio)
        # 衡量 20 日價格趨勢平滑度，過濾暴漲暴跌妖股
        net_change_20 = (close - close.shift(20)).abs()
        sum_abs_change_20 = close.diff().abs().rolling(window=20).sum()
        data["ker_20"] = (net_change_20 / (sum_abs_change_20.replace(0, np.nan) + 1e-9)).fillna(0.0)

        # 9D. VCP 波動率壓縮比 (Volatility Contraction Pattern)
        # 衡量突破前波動收斂蓄勢程度 (5日 ATR / 20日 ATR)
        atr_5 = tr.rolling(window=5).mean()
        data["vcp_ratio"] = (atr_5 / (data["atr_20"].replace(0, np.nan) + 1e-9)).fillna(1.0)
        data["is_vcp_squeeze"] = ((data["vcp_ratio"] < 0.80) & data["above_50sma"]).fillna(False)

        # 9E. 20 日機構隱形吸籌量能比 (Up/Down Volume Ratio)
        # 過去 20 日上漲日成交量總和 / 下跌日成交量總和，捕捉主力吃貨足跡
        up_vol = volume.where(delta > 0, 0.0).rolling(window=20).sum()
        down_vol = volume.where(delta < 0, 0.0).rolling(window=20).sum()
        data["ud_vol_ratio"] = (up_vol / (down_vol.replace(0, np.nan) + 1.0)).clip(upper=5.0).fillna(1.0)

        # 9F. IBD 機構出貨日計數 (Distribution Day Monitor)
        # 當日跌幅 <= -0.2% 且當日成交量大於前一日成交量，視為機構出貨日
        is_dist_day = ((daily_ret <= -0.002) & (volume > volume.shift(1))).astype(float)
        data["is_dist_day"] = is_dist_day
        data["dist_days_25d"] = is_dist_day.rolling(window=25, min_periods=1).sum().fillna(0.0)

        # 9G. Stockbee 賣壓竭盡錘子線 (Exhaustion Hammer)
        # 自 20 日高點回檔 >= 8%，下影線長且大於實體，量增 1.1 倍以上，代表恐慌賣壓竭盡
        drawdown_20d = (close - data["high_20d"]) / data["high_20d"].replace(0, np.nan)
        bar_range = (data["high"] - data["low"]).replace(0, np.nan)
        lower_shadow = np.minimum(data["open"], close) - data["low"]
        is_exhaustion_hammer = (
            (drawdown_20d <= -0.08) &
            (lower_shadow / bar_range >= 0.55) &
            ((close - data["low"]) / bar_range >= 0.50) &
            (volume >= data["vol_sma_20"] * 1.10)
        ).fillna(False)
        data["is_exhaustion_hammer"] = is_exhaustion_hammer

        # 當觸發 Stockbee 賣壓竭盡錘子線時，代表機構低接換手完成，強制豁免 is_distribution_warn
        data.loc[data["is_exhaustion_hammer"], "is_distribution_warn"] = False

        # 9H. Stockbee 動能爆發突破 (Momentum Burst)
        # 單日漲幅 >= 4%、成交量放大 1.3 倍以上、強勢收於全日高位 70% 之上且站穩 50MA
        is_momentum_burst = (
            (daily_ret >= 0.04) &
            (volume >= data["vol_sma_20"] * 1.30) &
            ((close - data["low"]) / bar_range >= 0.70) &
            data["above_50sma"]
        ).fillna(False)
        data["is_momentum_burst"] = is_momentum_burst

        # 10. 綜合動能評分 (純粹經典動能加權：ROC 20日 40% + 60日 35% + 120日 25%)
        # 遵循奧卡姆剃刀原則：移除過度約束加減分，恢復高爆發力純動能排序，微結構指標僅作唯讀診斷展示
        data["momentum_score"] = (
            data["roc_20"].fillna(0) * 0.40 +
            data["roc_60"].fillna(0) * 0.35 +
            data["roc_120"].fillna(0) * 0.25
        )
        
        return data

    @classmethod
    def evaluate_latest_ranking(cls, dataset: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        評估台美股最新動能排名、量價訊號與趨勢狀態
        """
        tw_records = []
        us_records = []
        
        for ticker, df in dataset.items():
            enriched_df = cls.calculate_technical_features(df)
            if enriched_df.empty:
                continue
            latest = enriched_df.iloc[-1]
            latest_date_str = enriched_df.index[-1].strftime("%Y-%m-%d")
            
            # 判斷洗盤買點、動能爆發與出貨警訊文字
            shakeout = bool(latest.get("is_shakeout_buy", False))
            dist_warn = bool(latest.get("is_distribution_warn", False))
            vcp_squeeze = bool(latest.get("is_vcp_squeeze", False))
            is_burst = bool(latest.get("is_momentum_burst", False))
            is_hammer = bool(latest.get("is_exhaustion_hammer", False))
            dist_days_25 = int(latest.get("dist_days_25d", 0))

            signal_tag = "正常"
            if is_burst:
                signal_tag = "🚀 動能爆發突破"
            elif is_hammer:
                signal_tag = "🔨 賣壓竭盡反轉"
            elif dist_warn:
                signal_tag = "⚠️ 爆量出貨警戒"
            elif vcp_squeeze:
                signal_tag = "🔥 VCP 突破蓄勢"
            elif shakeout:
                signal_tag = "💎 縮量洗盤買點"

            record = {
                "ticker": ticker,
                "name": TECH_UNIVERSE_TW.get(ticker, ticker),
                "price": round(float(latest["close"]), 2),
                "ret_1d": round(float(latest["ret_1d"]), 2) if not np.isnan(latest["ret_1d"]) else 0.0,
                "chg_1d": round(float(latest["ret_1d"]), 2) if not np.isnan(latest["ret_1d"]) else 0.0,
                "score": round(float(latest["momentum_score"]), 1),
                "roc_20d": round(float(latest["roc_20"]), 2) if not np.isnan(latest["roc_20"]) else 0.0,
                "roc_60d": round(float(latest["roc_60"]), 2) if not np.isnan(latest["roc_60"]) else 0.0,
                "roc_120d": round(float(latest["roc_120"]), 2) if not np.isnan(latest["roc_120"]) else 0.0,
                "vol_adj_momentum": round(float(latest["vol_adjusted_momentum"]), 2) if not np.isnan(latest["vol_adjusted_momentum"]) else 0.0,
                "ker_20": round(float(latest["ker_20"]), 2) if not np.isnan(latest["ker_20"]) else 0.0,
                "vcp_ratio": round(float(latest["vcp_ratio"]), 2) if not np.isnan(latest["vcp_ratio"]) else 1.0,
                "is_vcp_squeeze": vcp_squeeze,
                "ud_vol_ratio": round(float(latest["ud_vol_ratio"]), 2) if not np.isnan(latest["ud_vol_ratio"]) else 1.0,
                "dist_days_25d": dist_days_25,
                "is_exhaustion_hammer": is_hammer,
                "is_momentum_burst": is_burst,
                "above_50sma": bool(latest["above_50sma"]),
                "above_200sma": bool(latest["above_200sma"]),
                "is_new_high": bool(latest["is_new_high_20d"]),
                "is_shakeout_buy": shakeout,
                "is_distribution_warn": dist_warn,
                "signal_tag": signal_tag,
                "atr_pct": round(float(latest["atr_pct"]), 2) if not np.isnan(latest["atr_pct"]) else 0.0,
                "rsi_14": round(float(latest["rsi_14"]), 1) if not np.isnan(latest["rsi_14"]) else 50.0,
                "k_9": round(float(latest["k_9"]), 1) if not np.isnan(latest["k_9"]) else 50.0,
                "d_9": round(float(latest["d_9"]), 1) if not np.isnan(latest["d_9"]) else 50.0,
                "data_date": latest_date_str
            }
            
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            if is_tw:
                tw_records.append(record)
            else:
                us_records.append(record)
                
        # 排序：綜合評分由高到低
        tw_rank = pd.DataFrame(tw_records)
        if not tw_rank.empty:
            tw_rank = tw_rank.sort_values(by="score", ascending=False).reset_index(drop=True)
            
        us_rank = pd.DataFrame(us_records)
        if not us_rank.empty:
            us_rank = us_rank.sort_values(by="score", ascending=False).reset_index(drop=True)
            
        return tw_rank, us_rank
