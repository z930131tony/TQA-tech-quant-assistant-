"""
TradingAgents 多空對抗辯論 AI 模組 (基於 Google Gemini 2.5 Flash 免費 API)
架構：
1. Bullish Analyst（多頭動能狙擊手）：基於動能天梯評分、ROC、突破訊號與利多催化劑提出買進理由。
2. Bearish Risk Auditor（空頭風控審計官）：基於乖離率、爆量出貨警訊、高波動度與潛在逆風進行反駁。
3. Chief Judge（首席裁決官）：整合多空雙方攻防，做出結構化決策 (Verdict、操作指引、階梯加碼價與絕對硬停損價)。
"""
import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import pandas as pd

try:
    from google import genai
    from google.genai import types
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False

from src.config import TECH_UNIVERSE_TW

def fetch_yahoo_news(ticker: str, limit: int = 4) -> List[str]:
    """
    透過 Yahoo Finance RSS 免費抓取個股最新即時新聞標題
    """
    clean_sym = ticker.replace(".TW", "").replace(".TWO", "")
    feed_sym = f"{clean_sym}.TW" if (".TW" in ticker or ".TWO" in ticker) else ticker
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={feed_sym}&region=US&lang=en-US"
    headlines = []
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item")[:limit]:
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    clean_t = title_elem.text.strip()
                    if clean_t and clean_t not in headlines:
                        headlines.append(clean_t)
    except Exception:
        pass

    if not headlines:
        headlines = [f"市場焦點持續鎖定 {clean_sym} 在 AI 全產業鏈中的算力需求與技術領先地位。"]
    return headlines

def conduct_single_debate(
    ticker: str,
    name: str,
    price: float,
    tech_info: Dict,
    news_headlines: List[str],
    api_key: Optional[str] = None
) -> Dict:
    """
    執行單一標的之三方多空對抗辯論
    """
    step_buy_10pct = round(price * 0.90, 2)
    hard_stop_30pct = round(price * 0.70, 2)
    
    # 預設回退結果 (當未設定 GEMINI_API_KEY 時之演算法規則合成)
    shakeout = tech_info.get("is_shakeout_buy", False)
    dist_warn = tech_info.get("is_distribution_warn", False)
    above_50 = tech_info.get("above_50sma", True)
    score = tech_info.get("score", 0.0)

    fallback_verdict = "CAUTIOUS_BUY"
    fallback_bull = f"動能天梯評分達 {score:+.1f}，均線多頭結構穩固，站穩 50MA 生命線。"
    fallback_bear = "短線漲幅已高，須防範高檔獲利了結與市場波動率反撲。"
    fallback_action = "建議採階梯式分批建倉，嚴格守好 -8% 移動停利停損與 -30% 戰術硬停損。"

    if dist_warn:
        fallback_verdict = "CASH_DEFENSE"
        fallback_bear = "觸發爆量出貨警戒訊號，主力高檔換手滯漲，技術面有拉回風險。"
        fallback_action = "暫緩開新倉，嚴守 50MA 生命線防守。"
    elif shakeout:
        fallback_verdict = "STRONG_BUY"
        fallback_bull = "出現縮量洗盤黃金買點，高點回檔洗淨浮額，主力籌碼沉澱完畢。"
        fallback_action = "可於現價與 -10% 階梯價分批佈局強勢發動點。"

    default_result = {
        "ticker": ticker,
        "name": name,
        "price": price,
        "verdict": fallback_verdict,
        "bull_summary": fallback_bull,
        "bear_summary": fallback_bear,
        "tactical_action": fallback_action,
        "step_buy_10pct_price": step_buy_10pct,
        "hard_stop_30pct_price": hard_stop_30pct,
        "ai_powered": False
    }

    if not api_key or not GOOGLE_GENAI_AVAILABLE:
        return default_result

    # 構造 Gemini 2.5 Flash 結構化 Prompt
    prompt = f"""
你是由頂尖量化機構開發的【TradingAgents 多空對抗辯論 AI 決策核心】。
請針對以下科技股的即時量化特徵與最新新聞標題，模擬三方專業角色展開攻防辯論，並給出首席裁決：

【標的背景】
- 標的代號：{ticker} ({name})
- 當前收盤價：{price}
- 綜合動能評分：{score}
- 20日/60日變動率：{tech_info.get('roc_20d', 0)}% / {tech_info.get('roc_60d', 0)}%
- 均線狀態：{'站上50MA生命線' if above_50 else '跌破50MA生命線'}
- 量價訊號：{'縮量洗盤買點' if shakeout else '無洗盤'} | {'爆量出貨警訊' if dist_warn else '無出貨異常'}
- 最新市場新聞：
{chr(10).join(f'  • {h}' for h in news_headlines)}

【角色任務】
1. Bullish Analyst（多頭動能狙擊手）：用 1-2 句話精準指出買進催化劑（動能、洗盤縮量、突破）。
2. Bearish Risk Auditor（空頭風控審計官）：用 1-2 句話精準反駁風險點（出貨、乖離、總經逆風）。
3. Chief Judge（首席裁決官）：裁定最終行動方針，並只能選擇以下 4 種 Verdict 之一：
   "STRONG_BUY" (強烈看多買進), "CAUTIOUS_BUY" (謹慎分批佈局), "CASH_DEFENSE" (現金防禦觀望), "SELL" (建議停損減碼)。

請以純 JSON 格式輸出，不要包含任何額外 markdown 圍欄以外的閒聊字眼：
{{
  "ticker": "{ticker}",
  "name": "{name}",
  "verdict": "STRONG_BUY / CAUTIOUS_BUY / CASH_DEFENSE / SELL",
  "bull_summary": "多頭論點摘要（繁體中文，短句）",
  "bear_summary": "空頭風控反駁（繁體中文，短句）",
  "tactical_action": "今日操作指引與倉位建議（繁體中文，簡潔明確）",
  "step_buy_10pct_price": {step_buy_10pct},
  "hard_stop_30pct_price": {hard_stop_30pct}
}}
"""
    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        if resp.text:
            parsed = json.loads(resp.text)
            parsed["price"] = price
            parsed["ai_powered"] = True
            if "step_buy_10pct_price" not in parsed:
                parsed["step_buy_10pct_price"] = step_buy_10pct
            if "hard_stop_30pct_price" not in parsed:
                parsed["hard_stop_30pct_price"] = hard_stop_30pct
            return parsed
    except Exception as e:
        print(f"⚠️ {ticker} Gemini API 辯論呼叫失敗 ({e})，優雅降級為量化規則合成。")
    
    return default_result

def run_daily_ai_debate(
    tw_rank: pd.DataFrame, 
    us_rank: pd.DataFrame, 
    target_market: str = "ALL", 
    positions: Optional[List[Dict]] = None
) -> Dict:
    """
    執行每日 AI 多空對抗辯論管線
    只針對當日動能前 3 強 (Top 3) 與當前庫存部位進行精準辯論
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    target_candidates = []

    # 1. 挑選目標市場的 Top 3 強勢標的
    if target_market in ["ALL", "TW"] and tw_rank is not None and not tw_rank.empty:
        for _, row in tw_rank.head(3).iterrows():
            target_candidates.append({
                "ticker": row["ticker"],
                "name": row.get("name", row["ticker"]),
                "price": float(row["price"]),
                "score": float(row["score"]),
                "roc_20d": float(row.get("roc_20d", 0.0)),
                "roc_60d": float(row.get("roc_60d", 0.0)),
                "above_50sma": bool(row.get("above_50sma", True)),
                "is_shakeout_buy": bool(row.get("is_shakeout_buy", False)),
                "is_distribution_warn": bool(row.get("is_distribution_warn", False)),
                "is_tw": True
            })

    if target_market in ["ALL", "US"] and us_rank is not None and not us_rank.empty:
        for _, row in us_rank.head(3).iterrows():
            target_candidates.append({
                "ticker": row["ticker"],
                "name": row.get("name", row["ticker"]),
                "price": float(row["price"]),
                "score": float(row["score"]),
                "roc_20d": float(row.get("roc_20d", 0.0)),
                "roc_60d": float(row.get("roc_60d", 0.0)),
                "above_50sma": bool(row.get("above_50sma", True)),
                "is_shakeout_buy": bool(row.get("is_shakeout_buy", False)),
                "is_distribution_warn": bool(row.get("is_distribution_warn", False)),
                "is_tw": False
            })

    # 2. 納入目前庫存部位 (若尚未包含在候選名單中)
    if positions:
        existing_syms = {c["ticker"] for c in target_candidates}
        for pos in positions:
            t = pos.get("ticker", "")
            if t and t not in existing_syms:
                is_tw = (".TW" in t) or (".TWO" in t)
                # 判斷是否為目標市場持股
                if (target_market == "TW" and not is_tw) or (target_market == "US" and is_tw):
                    continue
                rank_src = tw_rank if is_tw else us_rank
                px = float(pos.get("cost_price", 100.0))
                sc = 0.0
                above_50 = True
                shakeout = False
                dist_warn = False
                roc20 = 0.0
                roc60 = 0.0
                if rank_src is not None and not rank_src.empty and "ticker" in rank_src.columns:
                    match_row = rank_src[rank_src["ticker"] == t]
                    if not match_row.empty:
                        r = match_row.iloc[0]
                        px = float(r["price"])
                        sc = float(r["score"])
                        above_50 = bool(r.get("above_50sma", True))
                        shakeout = bool(r.get("is_shakeout_buy", False))
                        dist_warn = bool(r.get("is_distribution_warn", False))
                        roc20 = float(r.get("roc_20d", 0.0))
                        roc60 = float(r.get("roc_60d", 0.0))

                target_candidates.append({
                    "ticker": t,
                    "name": TECH_UNIVERSE_TW.get(t, t),
                    "price": px,
                    "score": sc,
                    "roc_20d": roc20,
                    "roc_60d": roc60,
                    "above_50sma": above_50,
                    "is_shakeout_buy": shakeout,
                    "is_distribution_warn": dist_warn,
                    "is_tw": is_tw
                })

    print(f"🤖 啟動 TradingAgents AI 多空辯論引擎 (共評估 {len(target_candidates)} 檔重點標的)...")
    debates = []
    for cand in target_candidates:
        sym = cand["ticker"]
        news = fetch_yahoo_news(sym, limit=3)
        res = conduct_single_debate(
            ticker=sym,
            name=cand["name"],
            price=cand["price"],
            tech_info=cand,
            news_headlines=news,
            api_key=api_key
        )
        res["is_tw"] = cand["is_tw"]
        debates.append(res)

    return {
        "status": "SUCCESS",
        "api_enabled": bool(api_key and GOOGLE_GENAI_AVAILABLE),
        "total_debates": len(debates),
        "debates": debates
    }
