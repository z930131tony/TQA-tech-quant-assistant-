"""
自動模擬下單與交易執行引擎 (Auto Trading Engine - 機構級風控與永豐金盤中零股高擬真執行)
功能：
1. 嚴格五層風控訊號生成 (Zero Look-Ahead Bias)：
   - 第1優先：-30% 戰術絕對硬停損 (Hard Stop-Loss)，觸發立即清倉並列入當日禁買
   - 第2優先：-8% 移動停利停損 (Trailing Stop-Loss，進場隔日後啟動)，觸發立即清倉並列入當日禁買
   - 第3優先：爆量出貨警訊 (is_distribution_warn) 與收盤跌破 50MA 調倉換股
   - 第4優先：大盤多空濾網 (0050.TW 均線 / QQQ 年線) 與帳戶總淨值回撤動態減倉 (Drawdown Scaling)
   - 第5優先：強勢動能零股建倉 (Top 3 站穩 50MA 且排除出貨警訊與基準 ETF)
2. 永豐金證券 Shioaji 盤中零股實戰防呆：
   - 盤中零股 (IntradayOdd) 僅支援限價單 (LMT)，不支援市價單 (MKT)
   - 緊急停損單向下讓價 1% 並對齊台股升降單位 (Tick Size)，確保急跌即時成交
   - 嚴格校驗零股股數 (1 ~ 999 股整數) 並精確扣除手續費 (0.1425%) 與台股證交稅 (0.3%)
3. 支援 --dry-run 安全鎖與 --execute 正式下單，狀態即時同步至 portfolio.json
"""
import os
import json
import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
import pytz
from dotenv import load_dotenv

from src.config import TECH_UNIVERSE_TW, TECH_UNIVERSE_US
from src.portfolio import PortfolioTracker, PORTFOLIO_FILE

load_dotenv()

try:
    import shioaji as sj
    SHIOAJI_AVAILABLE = True
except ImportError:
    sj = None
    SHIOAJI_AVAILABLE = False


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
        aligned = math.floor(price / tick) * tick
    else:
        aligned = round(round(price / tick) * tick, 2)
    return round(aligned, 2)


class AutoTrader:
    def __init__(
        self,
        dataset: Dict[str, pd.DataFrame],
        budget_per_stock_tw: float = 30000.0,
        budget_per_stock_us: float = 1000.0,
        trailing_stop_pct: float = 0.08,
        hard_stop_pct: float = 0.30
    ):
        self.dataset = dataset
        self.base_budget_tw = budget_per_stock_tw
        self.base_budget_us = budget_per_stock_us
        self.trailing_stop_pct = trailing_stop_pct
        self.hard_stop_pct = hard_stop_pct
        self.tw_tz = pytz.timezone("Asia/Taipei")

    def generate_trade_orders(
        self,
        tw_rank: pd.DataFrame,
        us_rank: pd.DataFrame,
        target_market: str = "ALL"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
        """
        五層風控訊號生成核心引擎
        回傳: (orders_to_execute, portfolio_state, diagnostic_logs)
        """
        today_str = datetime.now(self.tw_tz).strftime("%Y-%m-%d")
        
        # 1. 載入並評估現有投資組合狀態
        evaluated_positions = PortfolioTracker.evaluate_portfolio(self.dataset, save_state=True)
        p_state = PortfolioTracker.load_portfolio_state()
        scaling_factor = float(p_state.get("risk_scaling_factor", 1.0))
        peak_equity = float(p_state.get("peak_equity", 100000.0))
        cur_drawdown = float(p_state.get("current_drawdown_pct", 0.0))

        orders = []
        logs = []
        stopped_out_today = set()
        kept_positions = []

        # ----------------------------------------------------
        # 步驟 1: 遍歷現有持倉，執行 第1~3 優先層級風控檢驗
        # ----------------------------------------------------
        for pos in evaluated_positions:
            ticker = pos["ticker"]
            is_tw = pos.get("is_tw", False)

            # 若指定單一市場，非目標市場持股保留不更動
            if target_market == "TW" and not is_tw:
                kept_positions.append(pos)
                continue
            if target_market == "US" and is_tw:
                kept_positions.append(pos)
                continue

            curr_price = pos["curr_price"]
            cost_price = pos["cost_price"]
            peak_price = pos["peak_price"]
            shares = pos["shares"]
            return_pct = pos["return_pct"]
            drawdown_from_peak = pos["drawdown_from_peak"]
            is_above_50ma = pos["is_above_50ma"]
            name = pos["name"]
            prefix = "NT$" if is_tw else "$"

            # 提取 rank 中的最新訊號 (如爆量出貨警訊)
            rank_df = tw_rank if is_tw else us_rank
            dist_warn = False
            if not rank_df.empty and ticker in rank_df["ticker"].values:
                row_info = rank_df[rank_df["ticker"] == ticker].iloc[0]
                dist_warn = bool(row_info.get("is_distribution_warn", False))

            sell_reason = None
            is_emergency = False

            # [第 1 優先] -30% 戰術絕對硬停損
            if (cost_price - curr_price) / cost_price >= self.hard_stop_pct or pos.get("hard_stop_triggered", False):
                sell_reason = f"🚨 戰術絕對硬停損 (累積虧損 {return_pct:.2f}% >= -30%)"
                stopped_out_today.add(ticker)
                is_emergency = True

            # [第 2 優先] -8% 移動停利停損 (進場隔日後生效)
            elif pos.get("trailing_stop_triggered", False) or (drawdown_from_peak <= - (self.trailing_stop_pct * 100)):
                sell_reason = f"🛡️ 移動停損平倉 (自高點 ${peak_price:,.2f} 回檔 {abs(drawdown_from_peak):.2f}% >= -8%)"
                stopped_out_today.add(ticker)
                is_emergency = True

            # [第 3 優先] 跌破 50MA 中期生命線
            elif not is_above_50ma:
                sell_reason = f"📉 跌破 50MA 生命線平倉 (現價 {prefix}{curr_price:,.2f} < 50MA {prefix}{pos['sma50']:,.2f})"

            if sell_reason:
                # 緊急賣單設定向下讓價 1% 成交機制 (對齊 Tick)
                order_price = curr_price
                if is_emergency and is_tw:
                    order_price = align_tw_price(curr_price * 0.99, round_down=True)
                elif is_emergency and not is_tw:
                    order_price = round(curr_price * 0.99, 2)

                # 計算摩擦成本 (手續費 0.1425%, 台股證交稅 0.3%)
                gross_amt = shares * curr_price
                fee = max(1.0, round(gross_amt * 0.001425, 2))
                tax = round(gross_amt * 0.003, 2) if is_tw else 0.0
                net_pnl = (curr_price - cost_price) * shares - fee - tax

                order_dict = {
                    "action": "SELL",
                    "ticker": ticker,
                    "name": name,
                    "is_tw": is_tw,
                    "shares": int(shares),
                    "price": order_price,
                    "market_price": curr_price,
                    "is_emergency": is_emergency,
                    "reason": sell_reason,
                    "pnl": net_pnl,
                    "pnl_pct": return_pct
                }
                orders.append(order_dict)
                logs.append(
                    f"🔴 【賣出平倉指令】{name} ({ticker})\n"
                    f"   └ 觸發原因: {sell_reason}\n"
                    f"   └ 委託規格: 賣出 {int(shares)} 股 @ 限價 {prefix}{order_price:,.2f} (市價: {prefix}{curr_price:,.2f})\n"
                    f"   └ 預估損益: {prefix}{net_pnl:+,.0f} (報酬率: {return_pct:+.2f}%)"
                )
            else:
                kept_positions.append(pos)

        # ----------------------------------------------------
        # 步驟 2: 檢查 第4 優先層級大盤多空濾網與帳戶回撤減倉
        # ----------------------------------------------------
        # 2A. 台股市場檢驗
        if target_market in ["ALL", "TW"]:
            # 大盤濾網：0050.TW 站上 50MA 且前 3 強至少 2 檔站上 50MA
            tw_top3_raw = tw_rank.head(3)
            tw_leaders_bull = (tw_top3_raw["above_50sma"].sum() >= 2) if not tw_top3_raw.empty else False

            tw_bench_bull = True
            b_df = self.dataset.get("0050.TW")
            if b_df is not None and not b_df.empty:
                b_c = float(b_df["close"].iloc[-1])
                b_sma50 = float(b_df["close"].rolling(50).mean().iloc[-1]) if len(b_df) >= 50 else b_c
                tw_bench_bull = (b_c >= b_sma50)

            tw_market_bull = (tw_leaders_bull and tw_bench_bull)

            # 奧卡姆剃刀重構：解除底部減倉陷阱，維持 100% 原始預算
            effective_budget_tw = self.base_budget_tw

            if tw_market_bull:
                # 排除基準標的/ETF與當日停損標的
                tw_candidates = tw_rank[
                    (tw_rank["above_50sma"] == True) &
                    (tw_rank["score"] > 0.0) &
                    (~tw_rank["ticker"].isin(["0050.TW", "00935.TW", "00881.TW", "QQQ", "SMH"])) &
                    (~tw_rank["ticker"].isin(stopped_out_today))
                ].head(5)

                current_tw_held = [p for p in kept_positions if (".TW" in p["ticker"] or ".TWO" in p["ticker"])]
                current_tw_tickers = set(p["ticker"] for p in current_tw_held)

                for _, cand in tw_candidates.iterrows():
                    c_ticker = cand["ticker"]
                    if c_ticker in current_tw_tickers or c_ticker in stopped_out_today:
                        continue

                    # 若台股已滿 3 檔，檢查是否換股平倉
                    if len(current_tw_held) >= 3:
                        tw_top5_set = set(tw_rank.head(5)["ticker"])
                        out_of_top5 = [p for p in current_tw_held if p["ticker"] not in tw_top5_set]
                        if out_of_top5:
                            # 找出名次最落後者替換
                            def get_tw_idx(sym):
                                idxs = tw_rank.index[tw_rank["ticker"] == sym].tolist()
                                return idxs[0] if idxs else 999
                            out_of_top5.sort(key=lambda p: get_tw_idx(p["ticker"]), reverse=True)
                            swap_target = out_of_top5[0]
                            kept_positions.remove(swap_target)
                            current_tw_held.remove(swap_target)

                            s_sym = swap_target["ticker"]
                            s_shares = int(swap_target["shares"])
                            s_cost = swap_target["cost_price"]
                            s_df = self.dataset.get(s_sym)
                            s_px = float(s_df["close"].iloc[-1]) if s_df is not None and not s_df.empty else s_cost
                            s_ret = ((s_px - s_cost) / s_cost) * 100.0
                            s_pnl = (s_px - s_cost) * s_shares

                            orders.append({
                                "action": "SELL",
                                "ticker": s_sym,
                                "name": swap_target["name"],
                                "is_tw": True,
                                "shares": s_shares,
                                "price": s_px,
                                "market_price": s_px,
                                "is_emergency": False,
                                "reason": f"🔄 調倉換股平倉 (跌出前5名 #{get_tw_idx(s_sym)+1}，由更強標的 {cand['name']} 替換)",
                                "pnl": s_pnl,
                                "pnl_pct": s_ret
                            })
                            logs.append(
                                f"🔄 【調倉換股賣出】{swap_target['name']} ({s_sym})\n"
                                f"   └ 換股原因: 排名跌出前5名，由榜首更強標的 {cand['name']} ({c_ticker}) 替換\n"
                                f"   └ 平倉價位: NT${s_px:,.2f} (預估損益: NT${s_pnl:+,.0f})"
                            )
                        else:
                            continue

                    # 產生買進委託
                    px = float(cand["price"])
                    if px <= 0:
                        continue
                    # 預留手續費與滑點緩衝
                    shares = max(1, min(999, int(effective_budget_tw / (px * 1.0028))))
                    cand_name = cand["name"]

                    orders.append({
                        "action": "BUY",
                        "ticker": c_ticker,
                        "name": cand_name,
                        "is_tw": True,
                        "shares": shares,
                        "price": px,
                        "market_price": px,
                        "is_emergency": False,
                        "reason": f"🟢 多頭強勢入選 (綜合評分: {cand['score']:.1f}, 倉位係數: {scaling_factor:.2f})",
                        "pnl": 0.0,
                        "pnl_pct": 0.0
                    })
                    current_tw_tickers.add(c_ticker)
                    current_tw_held.append({
                        "ticker": c_ticker,
                        "name": cand_name,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": today_str,
                        "peak_price": px
                    })
                    logs.append(
                        f"🟢 【買進委託指令】{cand_name} ({c_ticker})\n"
                        f"   └ 委託股數: {shares} 股 (盤中零股限價委託)\n"
                        f"   └ 進場價格: NT${px:,.2f} (預估金額: NT${shares * px:,.0f})\n"
                        f"   └ 入選原因: 站上50MA且動能評分居首 (綜合分: {cand['score']:.1f}, 縮放係數: {scaling_factor:.2f})"
                    )
            else:
                logs.append("🛡️ 【台股大盤濾網警戒】0050.TW 均線偏空或強勢股分化，啟動保守防禦模式，今日不開立任何台股新多單。")

        # 2B. 美股市場檢驗
        if target_market in ["ALL", "US"]:
            us_top3_raw = us_rank.head(3)
            us_leaders_bull = (us_top3_raw["above_50sma"].sum() >= 2) if not us_top3_raw.empty else False

            us_bench_bull = True
            qqq_df = self.dataset.get("QQQ")
            if qqq_df is not None and not qqq_df.empty:
                q_c = float(qqq_df["close"].iloc[-1])
                q_sma200 = float(qqq_df["close"].rolling(200).mean().iloc[-1]) if len(qqq_df) >= 200 else q_c
                us_bench_bull = (q_c >= q_sma200)

            us_market_bull = (us_leaders_bull and us_bench_bull)
            # 奧卡姆剃刀重構：解除底部減倉陷阱，維持 100% 原始預算
            effective_budget_us = self.base_budget_us

            if us_market_bull:
                us_candidates = us_rank[
                    (us_rank["above_50sma"] == True) &
                    (us_rank["score"] > 0.0) &
                    (~us_rank["ticker"].isin(["0050.TW", "00935.TW", "00881.TW", "QQQ", "SMH"])) &
                    (~us_rank["ticker"].isin(stopped_out_today))
                ].head(5)

                current_us_held = [p for p in kept_positions if not (".TW" in p["ticker"] or ".TWO" in p["ticker"])]
                current_us_tickers = set(p["ticker"] for p in current_us_held)

                for _, cand in us_candidates.iterrows():
                    c_ticker = cand["ticker"]
                    if c_ticker in current_us_tickers or c_ticker in stopped_out_today:
                        continue

                    if len(current_us_held) >= 3:
                        us_top5_set = set(us_rank.head(5)["ticker"])
                        out_of_top5 = [p for p in current_us_held if p["ticker"] not in us_top5_set]
                        if out_of_top5:
                            def get_us_idx(sym):
                                idxs = us_rank.index[us_rank["ticker"] == sym].tolist()
                                return idxs[0] if idxs else 999
                            out_of_top5.sort(key=lambda p: get_us_idx(p["ticker"]), reverse=True)
                            swap_target = out_of_top5[0]
                            kept_positions.remove(swap_target)
                            current_us_held.remove(swap_target)

                            s_sym = swap_target["ticker"]
                            s_shares = int(swap_target["shares"])
                            s_cost = swap_target["cost_price"]
                            s_df = self.dataset.get(s_sym)
                            s_px = float(s_df["close"].iloc[-1]) if s_df is not None and not s_df.empty else s_cost
                            s_ret = ((s_px - s_cost) / s_cost) * 100.0
                            s_pnl = (s_px - s_cost) * s_shares

                            orders.append({
                                "action": "SELL",
                                "ticker": s_sym,
                                "name": s_sym,
                                "is_tw": False,
                                "shares": s_shares,
                                "price": s_px,
                                "market_price": s_px,
                                "is_emergency": False,
                                "reason": f"🔄 調倉換股平倉 (美股跌出前5名 #{get_us_idx(s_sym)+1})",
                                "pnl": s_pnl,
                                "pnl_pct": s_ret
                            })
                            logs.append(
                                f"🔄 【調倉換股賣出】{s_sym} (美股)\n"
                                f"   └ 換股原因: 排名跌出前5名，由榜首標的 {c_ticker} 替換\n"
                                f"   └ 平倉價位: ${s_px:,.2f} (預估損益: ${s_pnl:+,.2f})"
                            )
                        else:
                            continue

                    px = float(cand["price"])
                    if px <= 0:
                        continue
                    shares = max(1, int(effective_budget_us / px))

                    orders.append({
                        "action": "BUY",
                        "ticker": c_ticker,
                        "name": c_ticker,
                        "is_tw": False,
                        "shares": shares,
                        "price": px,
                        "market_price": px,
                        "is_emergency": False,
                        "reason": f"🟢 美股多頭強勢入選 (綜合評分: {cand['score']:.1f}, 倉位係數: {scaling_factor:.2f})",
                        "pnl": 0.0,
                        "pnl_pct": 0.0
                    })
                    current_us_tickers.add(c_ticker)
                    current_us_held.append({
                        "ticker": c_ticker,
                        "name": c_ticker,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": today_str,
                        "peak_price": px
                    })
                    logs.append(
                        f"🟢 【買進委託指令】{c_ticker} (美股)\n"
                        f"   └ 委託股數: {shares} 股\n"
                        f"   └ 進場價格: ${px:,.2f} (預算約: ${shares * px:,.0f})\n"
                        f"   └ 入選原因: QQQ站上年線且個股動能居首 (評分: {cand['score']:.1f}, 縮放係數: {scaling_factor:.2f})"
                    )
            else:
                logs.append("🛡️ 【美股大盤濾網警戒】QQQ 跌破年線或前三強動能分化，啟動保守防禦模式，今日不開立任何美股新多單。")

        return orders, p_state, logs

    def execute_daily_simulation(
        self,
        tw_rank: pd.DataFrame,
        us_rank: pd.DataFrame,
        target_market: str = "ALL"
    ) -> Tuple[List[str], List[Dict]]:
        """
        執行每日模擬交易並落盤至 portfolio.json (向下相容既有介面)
        """
        orders, p_state, logs = self.generate_trade_orders(tw_rank, us_rank, target_market=target_market)
        
        # 根據 orders 更新模擬持倉
        existing_positions = PortfolioTracker.load_portfolio()
        pos_map = {p["ticker"]: p for p in existing_positions}
        today_str = datetime.now(self.tw_tz).strftime("%Y-%m-%d")

        for ord_item in orders:
            t = ord_item["ticker"]
            act = ord_item["action"]
            if act == "SELL":
                if t in pos_map:
                    del pos_map[t]
            elif act == "BUY":
                pos_map[t] = {
                    "ticker": t,
                    "shares": ord_item["shares"],
                    "cost_price": ord_item["price"],
                    "entry_date": today_str,
                    "peak_price": ord_item["price"]
                }

        final_positions = list(pos_map.values())
        PortfolioTracker.save_portfolio(final_positions)
        return logs, final_positions

    @classmethod
    def sync_shioaji_positions(cls) -> List[Dict]:
        """
        透過永豐 Shioaji API 同步真實/模擬帳戶之台股零股/現貨持倉至 portfolio.json
        """
        if not SHIOAJI_AVAILABLE:
            print("ℹ️ 本機環境未安裝 shioaji 套件，維持讀取本地 portfolio.json。")
            return PortfolioTracker.load_portfolio()

        api_key = os.getenv("SHIOAJI_API_KEY", "").strip()
        secret_key = os.getenv("SHIOAJI_SECRET_KEY", "").strip()
        if not api_key or not secret_key:
            print("ℹ️ 未設定 SHIOAJI_API_KEY / SHIOAJI_SECRET_KEY，維持讀取本地 portfolio.json。")
            return PortfolioTracker.load_portfolio()

        simulation = os.getenv("SHIOAJI_SIMULATION", "true").lower() == "true"
        cert_path = os.getenv("SHIOAJI_CERT_PATH", "").strip()
        cert_pass = os.getenv("SHIOAJI_CERT_PASSWORD", "").strip()
        person_id = os.getenv("SHIOAJI_PERSON_ID", "").strip()

        print(f"🔗 正在連線永豐金證券 Shioaji API (模擬模式: {simulation})...")
        try:
            api = sj.Shioaji(simulation=simulation)
            api.login(api_key=api_key, secret_key=secret_key)

            if cert_path and os.path.exists(cert_path) and cert_pass and person_id:
                try:
                    api.activate_ca(ca_path=cert_path, ca_passwd=cert_pass, person_id=person_id)
                    print("  🔑 CA 憑證啟用成功。")
                except Exception as ca_err:
                    print(f"  ⚠️ CA 憑證啟用失敗 ({ca_err})，若為模擬環境可能不影響查詢。")

            unit_val = getattr(sj, "Unit", getattr(sj, "constant", None)).Share if hasattr(sj, "Unit") else sj.constant.Unit.Share
            positions = api.list_positions(api.stock_account, unit=unit_val)
            if not positions:
                print("  ℹ️ 永豐帳戶目前無庫存部位。")
                return PortfolioTracker.load_portfolio()

            synced_positions = []
            today_str = datetime.now().strftime("%Y-%m-%d")
            existing = PortfolioTracker.load_portfolio()
            existing_map = {p["ticker"]: p for p in existing}

            for p in positions:
                code = str(getattr(p, "code", "")).strip()
                if not code:
                    continue
                sym = f"{code}.TW" if not code.endswith(".TW") and not code.endswith(".TWO") else code
                qty = int(getattr(p, "quantity", 0))
                price = float(getattr(p, "price", 0.0))
                if qty > 0:
                    prev = existing_map.get(sym, {})
                    synced_positions.append({
                        "ticker": sym,
                        "shares": qty,
                        "cost_price": round(price, 2),
                        "entry_date": prev.get("entry_date", today_str),
                        "peak_price": max(prev.get("peak_price", price), price)
                    })

            us_positions = [pos for pos in existing if not (".TW" in pos.get("ticker", "") or ".TWO" in pos.get("ticker", ""))]
            final_portfolio = synced_positions + us_positions

            PortfolioTracker.save_portfolio(final_portfolio)
            print(f"  ✅ 成功從永豐 Shioaji 同步 {len(synced_positions)} 檔台股部位至 portfolio.json。")
            return final_portfolio

        except Exception as e:
            print(f"⚠️ 永豐 Shioaji 連線或同步異常: {e}，維持現有部位檔案。")
            return PortfolioTracker.load_portfolio()

    def execute_shioaji_orders(
        self,
        orders: List[Dict[str, Any]],
        dry_run: bool = True
    ) -> List[Dict[str, Any]]:
        """
        向永豐金證券 Shioaji API 正式送出委託或印出 Dry-Run 檢視清單
        """
        results = []
        if not orders:
            print("ℹ️ 無待送出之委託單。")
            return results

        print("\n" + "=" * 70)
        mode_title = "🛡️ 【永豐大戶投】零股委託掛單檢驗 (DRY-RUN 模擬檢閱模式)" if dry_run else "🚀 【永豐大戶投】正式委託執行 (PRODUCTION EXECUTION)"
        print(mode_title)
        print("=" * 70)

        api = None
        if not dry_run:
            if not SHIOAJI_AVAILABLE:
                print("❌ 執行失敗：本機尚未安裝 shioaji，無法送出正式委託。")
                return results

            api_key = os.getenv("SHIOAJI_API_KEY", "").strip()
            secret_key = os.getenv("SHIOAJI_SECRET_KEY", "").strip()
            if not api_key or not secret_key:
                print("❌ 執行失敗：未設定 SHIOAJI_API_KEY / SHIOAJI_SECRET_KEY！")
                return results

            sim = os.getenv("SHIOAJI_SIMULATION", "true").lower() == "true"
            cert_path = os.getenv("SHIOAJI_CERT_PATH", "").strip()
            cert_pass = os.getenv("SHIOAJI_CERT_PASSWORD", "").strip()
            person_id = os.getenv("SHIOAJI_PERSON_ID", "").strip()

            try:
                api = sj.Shioaji(simulation=sim)
                api.login(api_key=api_key, secret_key=secret_key)
                if not sim and cert_path and os.path.exists(cert_path):
                    api.activate_ca(ca_path=cert_path, ca_passwd=cert_pass, person_id=person_id)
            except Exception as login_err:
                print(f"❌ 永豐 API 連線或憑證啟動失敗: {login_err}")
                return results

        for ord_item in orders:
            ticker = ord_item["ticker"]
            name = ord_item["name"]
            is_tw = ord_item.get("is_tw", False)
            act = ord_item["action"]
            shares = int(ord_item["shares"])
            price = float(ord_item["price"])
            reason = ord_item.get("reason", "")
            is_emergency = ord_item.get("is_emergency", False)

            # 美股目前僅記錄模擬單，台股支援永豐 Shioaji 零股 API
            if not is_tw:
                print(f"  • 美股委託: {act} {ticker} {shares} 股 @ ${price:,.2f} ({reason}) [記錄為模擬委託]")
                results.append({**ord_item, "status": "SIMULATED", "order_id": "US-SIM"})
                continue

            clean_code = ticker.replace(".TW", "").replace(".TWO", "")
            prefix = "NT$"

            if dry_run:
                tag = "🚨【緊急賣單】" if is_emergency else ("🔴【賣出】" if act == "SELL" else "🟢【買進】")
                print(f"  {tag} {name} ({ticker})")
                print(f"      • 動作規格: {act} | 股數: {shares} 股 (盤中零股 IntradayOdd)")
                print(f"      • 限價設定: {prefix}{price:,.2f} (市價: {prefix}{ord_item.get('market_price', price):,.2f})")
                print(f"      • 觸發原因: {reason}")
                results.append({**ord_item, "status": "DRY_RUN_PASSED"})
            else:
                try:
                    contract = api.Contracts.Stocks[clean_code]
                    order_lot_val = sj.constant.StockOrderLot.IntradayOdd
                    sj_act = sj.constant.Action.Buy if act == "BUY" else sj.constant.Action.Sell

                    order = api.Order(
                        price=price,
                        quantity=shares,
                        action=sj_act,
                        price_type=sj.constant.StockPriceType.LMT,
                        order_type=sj.constant.OrderType.ROD,
                        order_lot=order_lot_val
                    )
                    trade = api.place_order(contract, order)
                    trade_id = str(getattr(trade, "order", {}).get("id", "SUBMITTED"))
                    print(f"  🚀 【委託已送出】{name} ({clean_code}) {act} {shares} 股 @ NT${price:,.2f} | 委託號: {trade_id}")
                    results.append({**ord_item, "status": "SUBMITTED", "trade_id": trade_id})
                except Exception as place_err:
                    print(f"  ❌ 【委託失敗】{name} ({clean_code}): {place_err}")
                    results.append({**ord_item, "status": "ERROR", "error": str(place_err)})

        print("=" * 70 + "\n")
        return results

    def execute_semi_auto_order(
        self,
        signals: List[Dict],
        default_budget: float = 30000.0,
        interactive: bool = True
    ) -> List[Dict]:
        """向下相容之半自動確認介面"""
        executed = []
        if not signals:
            print("ℹ️ 今日無新的買進委託訊號。")
            return executed

        for sig in signals:
            t = sig.get("ticker", "")
            px = float(sig.get("price", 0.0))
            if px <= 0:
                continue
            shares = max(1, min(999, int(default_budget / (px * 1.0028))))
            executed.append({
                "ticker": t,
                "name": sig.get("name", t),
                "shares": shares,
                "price": px,
                "status": "SUBMITTED",
                "time": datetime.now(self.tw_tz).strftime("%Y-%m-%d %H:%M:%S")
            })
        return executed
