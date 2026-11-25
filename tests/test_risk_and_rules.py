"""
停損與台股 Tick 邊界測試：py tests/test_risk_and_rules.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.market_rules import get_tw_tick_size, align_tw_price
from src.core.risk_engine import hard_stop_hit, trailing_stop_hit

# Tick 升降單位邊界
assert get_tw_tick_size(9.99) == 0.01 and get_tw_tick_size(10.0) == 0.05
assert get_tw_tick_size(49.95) == 0.05 and get_tw_tick_size(50.0) == 0.10
assert get_tw_tick_size(99.9) == 0.10 and get_tw_tick_size(100.0) == 0.50
assert get_tw_tick_size(499.5) == 0.50 and get_tw_tick_size(500.0) == 1.00
assert get_tw_tick_size(999.0) == 1.00 and get_tw_tick_size(1000.0) == 5.00

# 對齊：賣單往下取，買單四捨五入；已對齊的價格不變
assert align_tw_price(68.31, round_down=True) == 68.30
assert align_tw_price(1003.0, round_down=True) == 1000.0
assert align_tw_price(1003.0, round_down=False) == 1005.0
assert align_tw_price(68.30, round_down=True) == 68.30

# 硬停損 30%：剛好 -30% 觸發，-29.9% 不觸發
assert hard_stop_hit(100.0, 70.0)
assert not hard_stop_hit(100.0, 70.1)

# 移動停損 8%：自高點回檔 8% 觸發，7.9% 不觸發
assert trailing_stop_hit(100.0, 92.0)
assert not trailing_stop_hit(100.0, 92.1)

# 模擬交易現金記帳：賣出加回淨額、買進扣除成本 (不碰真實 portfolio.json)
from src.core.market_rules import TW_BROKER_FEE, TW_SELL_TAX, USD_TWD
from src.execution.trader import AutoTrader
from src.execution.portfolio import PortfolioTracker

saved = {}
PortfolioTracker.load_portfolio = classmethod(lambda cls, *a, **k: [{"ticker": "AAPL", "shares": 2}, {"ticker": "2330.TW", "shares": 10}])
PortfolioTracker.save_portfolio = classmethod(lambda cls, positions, *a, extra_state=None, **k: saved.update(positions=positions, **(extra_state or {})))
orders = [
    {"action": "SELL", "ticker": "AAPL", "is_tw": False, "shares": 2, "price": 300.0},
    {"action": "SELL", "ticker": "2330.TW", "is_tw": True, "shares": 10, "price": 2000.0},
    {"action": "BUY", "ticker": "NVDA", "is_tw": False, "shares": 1, "price": 200.0},
]
trader = AutoTrader(dataset={})
trader.generate_trade_orders = lambda *a, **k: (orders, {"cash": 10000.0, "stop_log": {}}, [])
trader.execute_daily_simulation(None, None)
# 手續費最低 1 元：AAPL 那筆 0.855 元以 1 元計
expected = 10000.0 + (600 - 1.0) * USD_TWD + (20000 - 20000 * TW_BROKER_FEE - 20000 * TW_SELL_TAX) - (200 + 1.0) * USD_TWD
assert abs(saved["cash"] - round(expected, 2)) < 0.01, saved["cash"]
assert [p["ticker"] for p in saved["positions"]] == ["NVDA"]

print("OK: risk and tick rules")
