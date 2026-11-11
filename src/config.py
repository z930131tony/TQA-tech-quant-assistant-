"""
台美科技股量化系統設定
"""
from dataclasses import dataclass
from typing import List, Dict

# 美股科技追蹤名單
TECH_UNIVERSE_US: List[str] = [
    "NVDA",
    "MSFT",
    "AAPL",
    "GOOGL",
    "AMZN",
    "META",
    "TSLA",
    "AVGO",
    "QQQ",
    "SMH",
]

# 台股科技追蹤名單 (上市加 .TW，上櫃加 .TWO)
TECH_UNIVERSE_TW: Dict[str, str] = {
    "2330.TW": "台積電",
    "2454.TW": "聯發科",
    "2317.TW": "鴻海",
    "2382.TW": "廣達",
    "3231.TW": "緯創",
    "2308.TW": "台達電",
    "00881.TW": "國泰台灣5G+",
    "0052.TW": "富邦科技",
}

@dataclass
class StrategyConfig:
    lookback_days: int = 365 * 3       # 歷史資料回溯天數 (3 年)
    short_momentum_window: int = 20    # 短期動能 (20日)
    medium_momentum_window: int = 60   # 中期動能 (60日)
    long_momentum_window: int = 120    # 長期動能 (120日)
    trend_filter_sma: int = 50         # 生命線濾網 (50MA)
    long_term_sma: int = 200           # 長期趨勢線 (200MA)
    trailing_stop_pct: float = 0.08    # 追蹤停損閾值 (最高點回檔 8%)
    top_n_picks: int = 3               # 持倉目標檔數
    tz_taiwan: str = "Asia/Taipei"
    tz_us: str = "America/New_York"

config = StrategyConfig()
