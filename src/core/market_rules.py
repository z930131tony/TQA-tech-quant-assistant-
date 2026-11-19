"""
市場規則：回測與實盤共用，改這裡兩邊一起生效
"""
import math

# 基準標的與產業 ETF：只當大盤濾網與績效對照，不進選股池
BENCHMARK_TICKERS = ["0050.TW", "00935.TW", "00881.TW", "QQQ", "SMH"]

TW_SELL_TAX = 0.003        # 台股賣出證交稅 0.3%
TW_BROKER_FEE = 0.001425   # 台股券商手續費 0.1425% (未打折)
TW_ODD_LOT_MAX = 999       # 盤中零股每筆上限 1~999 股


def get_tw_tick_size(price: float) -> float:
    """依台灣證券交易所規範計算股價升降單位 (Tick Size)"""
    if price < 10.0:
        return 0.01
    elif price < 50.0:
        return 0.05
    elif price < 100.0:
        return 0.10
    elif price < 500.0:
        return 0.50
    elif price < 1000.0:
        return 1.00
    else:
        return 5.00


def align_tw_price(price: float, round_down: bool = True) -> float:
    """將價格對齊台股升降單位 (Tick Size)，round_down 用於賣單讓價防踩跌停"""
    tick = get_tw_tick_size(price)
    if round_down:
        aligned = math.floor(round(price / tick, 6)) * tick
    else:
        aligned = round(round(price / tick) * tick, 2)
    return round(aligned, 2)
