"""
台美純科技股量化配置系統 - 全局設定檔
"""
from dataclasses import dataclass, field
from typing import List, Dict

# 美股科技天團清單 (AI 七巨頭 + 半導體 + 科技基準)
TECH_UNIVERSE_US: List[str] = [
    "NVDA",   # 輝達 (AI 算力晶片總龍頭)
    "MSFT",   # 微軟 (企業 AI 與雲端)
    "AAPL",   # 蘋果 (消費生態與龐大現金流)
    "GOOGL",  # 谷歌 (搜尋、雲端與多模態 AI)
    "AMZN",   # 亞馬遜 (AWS 雲端與電商)
    "META",   # Meta (開源 AI 與數位廣告)
    "TSLA",   # 特斯拉 (自動駕駛與機器人)
    "AVGO",   # 博通 (客製化 ASIC 與網通晶片)
    "QQQ",    # 那斯達克 100 ETF (科技大盤基準)
    "SMH",    # 費城半導體 ETF (全球晶片龍頭組合)
]

# 台股科技天團清單 (護國神山 + AI 伺服器與散熱供應鏈)
# 注意：Yahoo Finance 上市加 .TW，上櫃加 .TWO
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
    # 回測歷史抓取天數 (預設抓 3 年日 K)
    lookback_days: int = 365 * 3
    
    # 動能計算週期
    short_momentum_window: int = 20    # 20日動能 (約 1 個月)
    medium_momentum_window: int = 60   # 60日動能 (約 1 季)
    long_momentum_window: int = 120    # 120日動能 (約半年)
    
    # 趨勢濾網均線
    trend_filter_sma: int = 50         # 50 日均線（生命線）
    long_term_sma: int = 200           # 200 日均線（年線 / 多空分水嶺）
    
    # 追蹤停損閾值 (最高點拉回百分比)
    trailing_stop_pct: float = 0.08    # 拉回 8% 觸發停損/獲利保護
    
    # 每次推薦持倉前 N 檔最強科技股
    top_n_picks: int = 3
    
    # 時區設定
    tz_taiwan: str = "Asia/Taipei"
    tz_us: str = "America/New_York"

config = StrategyConfig()
