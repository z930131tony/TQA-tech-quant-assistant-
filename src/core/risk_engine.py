"""
雙軌停損：回測與實盤共用同一套判斷
"""

TRAILING_STOP_PCT = 0.08   # 自最高點回檔 8% 出場 (進場隔日後才啟動)
HARD_STOP_PCT = 0.30       # 自成本虧損 30% 絕對停損


def hard_stop_hit(cost: float, price: float, pct: float = HARD_STOP_PCT) -> bool:
    return (cost - price) / cost >= pct


def trailing_stop_hit(peak: float, price: float, pct: float = TRAILING_STOP_PCT) -> bool:
    return (peak - price) / peak >= pct
