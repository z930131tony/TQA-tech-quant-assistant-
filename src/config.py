"""
台美科技股量化系統設定 (擴充版：41 檔台美科技全產業鏈)
"""
from dataclasses import dataclass
from typing import List, Dict

# 美股科技核心追蹤名單 (21 檔：七巨頭 + 半導體晶片 + 設備 + AI軟體/資安 + 指標ETF)
TECH_UNIVERSE_US: List[str] = [
    # 1. 科技七巨頭 (Magnificent 7)
    "NVDA",   # 輝達 (AI 算力晶片龍頭)
    "MSFT",   # 微軟 (企業 AI 與雲端)
    "AAPL",   # 蘋果 (消費科技與生態系)
    "GOOGL",  # 谷歌 (搜尋、雲端與多模態 AI)
    "AMZN",   # 亞馬遜 (AWS 雲端算力)
    "META",   # Meta (開源 AI 與數位廣告)
    "TSLA",   # 特斯拉 (自駕與機器人)
    
    # 2. 半導體晶片與網通龍頭
    "AVGO",   # 博通 (客製化 ASIC 與網通晶片)
    "AMD",    # 超微 (GPU/CPU 競爭者)
    "QCOM",   # 高通 (邊緣 AI 與手機晶片)
    "ARM",    # 安謀 (IP 架構壟斷者)
    "MU",     # 美光 (HBM 高頻寬記憶體)
    "TSM",    # 台積電 ADR (全球代工霸主)
    
    # 3. 半導體設備三巨頭
    "ASML",   # 艾司摩爾 (光刻機壟斷)
    "AMAT",   # 應用材料 (設備龍頭)
    "LRCX",   # 科林研發 (蝕刻設備)
    
    # 4. AI 企業應用、大數據與資安
    "PLTR",   # Palantir (AI 國防與企業大數據)
    "ORCL",   # 甲骨文 (AI 雲端資料中心)
    "CRWD",   # CrowdStrike (AI 端點資安)
    
    # 5. 基準與半導體 ETF
    "QQQ",    # 那斯達克 100 ETF
    "SMH",    # 費城半導體 ETF
]

# 台股科技核心追蹤名單 (20 檔：代工封測 + AI伺服器 + 散熱電源 + PCB + 矽智財 + ETF)
TECH_UNIVERSE_TW: Dict[str, str] = {
    # 1. 晶片與晶圓代工封測
    "2330.TW": "台積電",
    "2454.TW": "聯發科",
    "3711.TW": "日月光投控",
    
    # 2. AI 伺服器組裝與品牌
    "2317.TW": "鴻海",
    "2382.TW": "廣達",
    "3231.TW": "緯創",
    "6669.TW": "緯穎",
    "2357.TW": "華碩",
    
    # 3. AI 水冷散熱與電源
    "2308.TW": "台達電",
    "3017.TW": "奇鋐",
    "3324.TWO": "雙鴻",
    
    # 4. 高階 PCB / CCL / 載板
    "2383.TW": "台光電",
    "2368.TW": "金像電",
    "3037.TW": "欣興",
    
    # 5. 矽智財 (ASIC/IP) 與測試
    "3661.TW": "世芯-KY",
    "3443.TW": "創意",
    "6223.TWO": "旺矽",
    
    # 6. 科技與半導體 ETF
    "0052.TW": "富邦科技",
    "00881.TW": "國泰台灣5G+",
    "00935.TW": "野村創新科技50",
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
