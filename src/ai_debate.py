"""
TradingAgents 多空對抗辯論 AI 模組 (基於 Google Gemini 2.5 Flash 免費 API)
架構：
1. Bullish Analyst（多頭動能狙擊手）：基於動能評分、三大價量微結構因子 (KER/VCP/UD_Vol)、縮量洗盤買點與利多催化劑提出買進理由。
2. Bearish Risk Auditor（空頭風控審計官）：基於高檔振幅擴大、量能背離派發、爆量出貨警訊、高乖離率與潛在逆風進行反駁。
3. Chief Judge（首席裁決官）：整合多空雙方攻防，貫徹雙軌風控紀律 (-8% 移動停利停損與 -30% 戰術硬停損)，做出結構化決策。
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
    clean_sym = ticker.split(".")[0]
    feed_sym = ticker
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
        headlines = [f"（{clean_sym} 目前抓不到最新新聞標題）"]
    return headlines

def _compile_chip_evidence(tech_info: Dict) -> Dict:
    """
    語意化籌碼編譯器：將三大微結構因子 (KER, VCP, UD_Vol) 與量價極端訊號轉譯為明確的多空籌碼論據。
    防止 LLM 對原始浮點數產生幻覺，並統一支援 Fallback 模式與 LLM Prompt。
    """
    ker_20 = float(tech_info.get("ker_20", 0.0))
    vcp_ratio = float(tech_info.get("vcp_ratio", 1.0))
    is_vcp_squeeze = bool(tech_info.get("is_vcp_squeeze", False))
    ud_vol_ratio = float(tech_info.get("ud_vol_ratio", 1.0))
    shakeout = bool(tech_info.get("is_shakeout_buy", False))
    dist_warn = bool(tech_info.get("is_distribution_warn", False))
    dist_days = int(tech_info.get("dist_days_25d", 0))
    is_burst = bool(tech_info.get("is_momentum_burst", False))
    is_hammer = bool(tech_info.get("is_exhaustion_hammer", False))

    bull_ammo = []
    bear_ammo = []

    # 1. 考夫曼效率係數 (KER 20)：僅當 ker_20 >= 0.45 時多頭才能引述為平滑鎖碼優勢
    if ker_20 >= 0.45:
        bull_ammo.append(f"20日趨勢效率達 {ker_20:.2f}，價格沿均線平滑推升，屬機構演算法穩定鎖碼型態。")
    elif ker_20 < 0.35:
        bear_ammo.append(f"20日趨勢效率僅 {ker_20:.2f}，走勢頻繁上下刷洗、雜訊過高，籌碼呈現凌亂分歧。")

    # 2. VCP 波動率壓縮比 (vcp_ratio & is_vcp_squeeze)
    if is_vcp_squeeze or vcp_ratio < 0.80:
        bull_ammo.append(f"5日/20日波動壓縮比降至 {vcp_ratio:.2f}，浮額清洗完畢進入 VCP 收斂蓄勢，隨時具備突破爆發力。")
    elif vcp_ratio > 1.25:
        bear_ammo.append(f"短線波動壓縮比擴大至 {vcp_ratio:.2f}，高檔振幅劇烈放大，追價易觸發 -8% 移動停損。")

    # 3. 20日機構隱形吸籌量能比 (ud_vol_ratio)
    if ud_vol_ratio >= 1.25:
        bull_ammo.append(f"20日上漲/下跌日量能比達 {ud_vol_ratio:.2f} 倍，呈現標準『上漲放量、回檔縮量』之法人吃貨結構。")
    elif ud_vol_ratio < 0.85:
        bear_ammo.append(f"20日上漲/下跌日量能比僅 {ud_vol_ratio:.2f} 倍，上攻無量而下跌出量，隱含主力逢高派發跡象。")

    # 4. Stockbee 雙型態與 IBD 出貨日訊號
    if is_burst:
        bull_ammo.append("觸發 Stockbee 動能爆發突破（單日漲幅>=4%且量增>1.3x，強勢收高），主升段買點確立。")
    if is_hammer:
        bull_ammo.append("觸發 Stockbee 賣壓竭盡錘子線（波段回檔逾8%但爆量收長下影線），恐慌浮額清洗完畢。")
    if dist_days >= 5:
        bear_ammo.append(f"近 25 日密集出現 {dist_days} 次機構出貨日，主力籌碼派發警戒。")

    # 5. 量價極端訊號 (is_shakeout_buy / is_distribution_warn)
    if shakeout:
        bull_ammo.append("觸發 10%~30% 階梯縮量洗盤買點，近3日均量低於月均量70%，賣壓竭盡。")
    if dist_warn:
        bear_ammo.append("觸發爆量滯漲出貨警戒（量能逾月均量1.5倍但近5日滯漲），嚴防主力倒貨。")

    metrics_summary = (
        f"KER 趨勢平滑度: {ker_20:.2f} | "
        f"VCP 波動收斂比: {vcp_ratio:.2f} (收斂蓄勢: {'是' if is_vcp_squeeze else '否'}) | "
        f"UD_Vol 機構量能比: {ud_vol_ratio:.2f} | "
        f"量價型態: {'縮量洗盤買點' if shakeout else ('爆量出貨警戒' if dist_warn else '正常')}"
    )

    return {
        "bull_ammo": bull_ammo,
        "bear_ammo": bear_ammo,
        "metrics_summary": metrics_summary,
        "ker_20": ker_20,
        "vcp_ratio": vcp_ratio,
        "is_vcp_squeeze": is_vcp_squeeze,
        "ud_vol_ratio": ud_vol_ratio,
        "is_shakeout_buy": shakeout,
        "is_distribution_warn": dist_warn
    }

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
    trail_stop_8pct = round(price * 0.92, 2)

    # 1. 籌碼因子語意化轉譯
    evidence = _compile_chip_evidence(tech_info)
    bull_ammo = evidence["bull_ammo"]
    bear_ammo = evidence["bear_ammo"]
    ker_20 = evidence["ker_20"]
    vcp_ratio = evidence["vcp_ratio"]
    is_vcp_squeeze = evidence["is_vcp_squeeze"]
    ud_vol_ratio = evidence["ud_vol_ratio"]
    shakeout = evidence["is_shakeout_buy"]
    dist_warn = evidence["is_distribution_warn"]
    above_50 = tech_info.get("above_50sma", True)
    score = float(tech_info.get("score", 0.0))

    # 2. 本地量化規則合成 (Fallback 模式：無 GEMINI_API_KEY 時)
    # 多方論點
    bull_parts = [f"動能天梯評分達 {score:+.1f}，{'站穩 50MA 生命線' if above_50 else '處於技術整理區間'}。"]
    if bull_ammo:
        bull_parts.extend(bull_ammo)
    else:
        # 嚴禁在 ker_20 < 0.45 時拿 KER 硬誇！改為引用實際達標的均線位階、動能評分或量價結構
        if ker_20 >= 0.45:
            bull_parts.append(f"KER 趨勢平滑度 {ker_20:.2f}，走勢沿短期均線穩定推進。")
        elif above_50:
            bull_parts.append("股價站穩 50MA 生命線關鍵支撐，均線結構維持多頭排列。")
        elif score >= 20.0:
            bull_parts.append(f"多頭動能評分維持 {score:.1f}，具備波段動能跟隨機會。")
        else:
            bull_parts.append("短線處於區間震盪整理，靜待放量突破訊號。")
    fallback_bull = " ".join(bull_parts)

    # 空方論點
    bear_parts = []
    if bear_ammo:
        bear_parts.extend(bear_ammo)
    else:
        bear_parts.append(f"短線漲幅已高，VCP 波動比 {vcp_ratio:.2f}，須提防高檔獲利回吐與盤勢逆風。")
    fallback_bear = " ".join(bear_parts)

    # 裁決長判定 (依據量價微結構與雙軌風控防線)
    if dist_warn or (ud_vol_ratio < 0.85 and not shakeout and not is_vcp_squeeze):
        fallback_verdict = "CASH_DEFENSE" if above_50 else "SELL"
        fallback_bear_lead = "爆量滯漲" if dist_warn else "主力逢高派發量能背離"
        fallback_action = f"偵測到{fallback_bear_lead}警訊，嚴禁追高，持股啟動 -8% 移動停利 ({trail_stop_8pct:,.1f}) 或收攏現金防守。"
    elif shakeout:
        fallback_verdict = "STRONG_BUY"
        fallback_action = f"縮量洗盤買點確立且籌碼賣壓竭盡，建議於現價與 -10% 階梯價 ({step_buy_10pct:,.1f}) 分批佈局，硬停損嚴守 -30% ({hard_stop_30pct:,.1f})。"
    elif (ud_vol_ratio >= 1.25 and ker_20 >= 0.50) or is_vcp_squeeze:
        fallback_verdict = "STRONG_BUY"
        squeeze_tag = "VCP 波動收斂蓄勢完畢" if is_vcp_squeeze else f"法人吃貨吸籌比達 {ud_vol_ratio:.2f} 倍"
        fallback_action = f"{squeeze_tag}，具備向上突破動能，可採階梯式分批建倉，嚴守 -8% 移動停損 ({trail_stop_8pct:,.1f})。"
    elif above_50 and score >= 40.0:
        fallback_verdict = "CAUTIOUS_BUY"
        fallback_action = f"多頭動能穩健但籌碼未達極端共振，建議採階梯式分批建倉，嚴格守好 -8% 移動停損 ({trail_stop_8pct:,.1f}) 與 -30% 戰術硬停損 ({hard_stop_30pct:,.1f})。"
    else:
        fallback_verdict = "CASH_DEFENSE"
        fallback_action = f"動能趨緩或籌碼雜訊過高，暫停開立新倉，以現金防禦為主，嚴守 50MA 生命線防線。"

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
        "chip_metrics": {
            "ker_20": ker_20,
            "vcp_ratio": vcp_ratio,
            "is_vcp_squeeze": is_vcp_squeeze,
            "ud_vol_ratio": ud_vol_ratio,
            "is_shakeout_buy": shakeout,
            "is_distribution_warn": dist_warn
        },
        "ai_powered": False
    }

    if not api_key or not GOOGLE_GENAI_AVAILABLE:
        return default_result

    # 構造 Gemini 2.5 Flash 結構化 Prompt
    prompt = f"""
你是由頂尖量化機構開發的【TradingAgents 多空對抗辯論 AI 決策核心】。
請針對以下科技股的即時量化特徵、三大價量微結構籌碼因子與最新新聞標題，模擬三方專業角色展開攻防辯論，並給出首席裁決：

【標的背景與量化特徵】
- 標的代號：{ticker} ({name})
- 當前收盤價：{price}
- 綜合動能評分：{score:+.1f}
- 20日/60日變動率：{tech_info.get('roc_20d', 0):+.2f}% / {tech_info.get('roc_60d', 0):+.2f}%
- 均線狀態：{'站上50MA生命線 (多頭排列)' if above_50 else '跌破50MA生命線 (走勢轉弱)'}
- 量價型態：{tech_info.get('signal_tag', '正常')} ({'縮量洗盤買點' if shakeout else '無洗盤'} | {'爆量出貨警訊' if dist_warn else '無出貨異常'})

【三大價量微結構籌碼因子 (量化數據)】
- 考夫曼效率係數 (KER_20): {ker_20:.2f} (衡量價格沿均線推升之平滑度，>=0.50 為穩定鎖碼，<0.30 為雜訊刷洗)
- VCP 波動壓縮比 (vcp_ratio): {vcp_ratio:.2f} (5日/20日波動比，<0.80 或 is_vcp_squeeze 為收斂蓄勢，>1.25 為高檔振幅擴大)
- 機構吸籌量能比 (ud_vol_ratio): {ud_vol_ratio:.2f} (20日上漲/下跌量能比，>=1.25 為法人吃貨，<0.85 為主力派發背離)

【籌碼攻防論據庫】
- 多方籌碼佐證庫：{bull_ammo if bull_ammo else ['量價中規中矩，動能穩定']}
- 空方風控警示庫：{bear_ammo if bear_ammo else ['短線波動尚可，提防獲利回吐']}

【最新市場新聞】
{chr(10).join(f'  • {h}' for h in news_headlines)}

【角色任務與發言規範】
1. Bullish Analyst（多頭動能狙擊手）：用 1-2 句話精準指出買進催化劑，可引用 KER 趨勢平滑度、VCP 波動壓縮比 或 UD_Vol 機構量能比 之具體數值作為買進佐證。注意：只有當 ker_20 >= 0.45 時才可引用 KER 作為平滑推進論據；若 ker_20 < 0.45，嚴禁引述 KER 為利多，改為引用均線位階、動能分數或 VCP/量能比 等其他實際達標的優勢指標。
2. Bearish Risk Auditor（空頭風控審計官）：用 1-2 句話精準反駁風險點，必須明確引用 VCP 波動比放大、UD_Vol 機構量能背離、出貨警訊 或 趨勢雜訊 之具體數值作為風控反駁佐證。
3. Chief Judge（首席裁決官）：整合攻防，做出結構化決策，只能選擇以下 4 種 Verdict 之一：
   "STRONG_BUY" (強烈看多買進), "CAUTIOUS_BUY" (謹慎分批佈局), "CASH_DEFENSE" (現金防禦觀望), "SELL" (建議停損減碼)。
   裁決紀律（強制執行）：
   - 若 ud_vol_ratio < 0.85 或觸發爆量出貨 (is_distribution_warn)，強制判定為 CASH_DEFENSE 或 SELL，發出「拉高減碼/嚴禁追高」指引。
   - 若同時具備 ud_vol_ratio >= 1.25 與 ker_20 >= 0.50（或 VCP 收斂蓄勢），給予 STRONG_BUY 評級。
   - 操作指引中必須貫徹雙軌風控：明確指示 -8% 移動停利停損 ({trail_stop_8pct:,.1f}) 與 -30% 戰術硬停損價位 ({hard_stop_30pct:,.1f})。

請以純 JSON 格式輸出，不要包含任何額外 markdown 圍欄以外的閒聊字眼：
{{
  "ticker": "{ticker}",
  "name": "{name}",
  "verdict": "STRONG_BUY / CAUTIOUS_BUY / CASH_DEFENSE / SELL",
  "bull_summary": "多頭論點摘要（繁體中文短句，包含 KER/VCP/UD_Vol 數據）",
  "bear_summary": "空頭風控反駁（繁體中文短句，包含籌碼風控數據）",
  "tactical_action": "今日操作指引與倉位建議（繁體中文，包含 -8% 移動停損與 -30% 硬停損紀律）",
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
            parsed["chip_metrics"] = default_result["chip_metrics"]
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
                "name": row.get("name", TECH_UNIVERSE_TW.get(row["ticker"], row["ticker"])),
                "price": float(row["price"]),
                "score": float(row["score"]),
                "roc_20d": float(row.get("roc_20d", 0.0)),
                "roc_60d": float(row.get("roc_60d", 0.0)),
                "above_50sma": bool(row.get("above_50sma", True)),
                "is_shakeout_buy": bool(row.get("is_shakeout_buy", False)),
                "is_distribution_warn": bool(row.get("is_distribution_warn", False)),
                "ker_20": float(row.get("ker_20", 0.0)),
                "vcp_ratio": float(row.get("vcp_ratio", 1.0)),
                "is_vcp_squeeze": bool(row.get("is_vcp_squeeze", False)),
                "ud_vol_ratio": float(row.get("ud_vol_ratio", 1.0)),
                "signal_tag": str(row.get("signal_tag", "正常")),
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
                "ker_20": float(row.get("ker_20", 0.0)),
                "vcp_ratio": float(row.get("vcp_ratio", 1.0)),
                "is_vcp_squeeze": bool(row.get("is_vcp_squeeze", False)),
                "ud_vol_ratio": float(row.get("ud_vol_ratio", 1.0)),
                "signal_tag": str(row.get("signal_tag", "正常")),
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
                ker20 = 0.0
                vcp_r = 1.0
                vcp_sq = False
                ud_vol = 1.0
                sig_tag = "正常"

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
                        ker20 = float(r.get("ker_20", 0.0))
                        vcp_r = float(r.get("vcp_ratio", 1.0))
                        vcp_sq = bool(r.get("is_vcp_squeeze", False))
                        ud_vol = float(r.get("ud_vol_ratio", 1.0))
                        sig_tag = str(r.get("signal_tag", "正常"))

                nm = TECH_UNIVERSE_TW.get(t, t) if is_tw else t
                target_candidates.append({
                    "ticker": t,
                    "name": nm,
                    "price": px,
                    "score": sc,
                    "roc_20d": roc20,
                    "roc_60d": roc60,
                    "above_50sma": above_50,
                    "is_shakeout_buy": shakeout,
                    "is_distribution_warn": dist_warn,
                    "ker_20": ker20,
                    "vcp_ratio": vcp_r,
                    "is_vcp_squeeze": vcp_sq,
                    "ud_vol_ratio": ud_vol,
                    "signal_tag": sig_tag,
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
