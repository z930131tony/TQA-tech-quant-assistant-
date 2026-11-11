"""
自動模擬下單與交易執行引擎 (Auto Trading Engine)
支援：
1. 永豐 Shioaji API 模擬環境掛單 (simulation=True)
2. 自動多空環境判斷 (Top 3 >= 2 站上 50MA 啟動買進)
3. 自動計算零股股數與每檔固定預算
4. 8% 追蹤停損與跌破 50MA 自動平倉機制
5. 自動同步至 portfolio.json 與 LINE 回報
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd
import pytz
from dotenv import load_dotenv

from src.config import TECH_UNIVERSE_TW, TECH_UNIVERSE_US
from src.portfolio import PortfolioTracker, PORTFOLIO_FILE

load_dotenv()

class AutoTrader:
    def __init__(
        self,
        dataset: Dict[str, pd.DataFrame],
        budget_per_stock_tw: float = 30000.0,  # 台股每檔預設約 3 萬台幣零股
        budget_per_stock_us: float = 1000.0,   # 美股每檔預設約 1,000 美元
        trailing_stop_pct: float = 8.0         # 8% 停利停損
    ):
        self.dataset = dataset
        self.budget_tw = budget_per_stock_tw
        self.budget_us = budget_per_stock_us
        self.trailing_stop_pct = trailing_stop_pct
        self.tw_tz = pytz.timezone("Asia/Taipei")

    def execute_daily_simulation(
        self, 
        tw_rank: pd.DataFrame, 
        us_rank: pd.DataFrame,
        target_market: str = "ALL"
    ) -> Tuple[List[str], List[Dict]]:
        """
        執行每日模擬下單流程：
        1. 檢查現有部位停損平倉 (依 target_market 篩選市場)
        2. 檢查多頭環境與買進新標的
        3. 儲存 portfolio.json
        回傳: (交易報告文字清單, 最終部位清單)
        """
        today_str = datetime.now(self.tw_tz).strftime("%Y-%m-%d")
        positions = PortfolioTracker.load_portfolio()
        current_tickers = {p["ticker"] for p in positions}
        
        trade_logs = []
        kept_positions = []

        # ----------------------------------------------------
        # 步驟 1: 檢查現有持股之出場訊號 (停損 8% 或跌破 50MA)
        # ----------------------------------------------------
        for pos in positions:
            ticker = pos["ticker"]
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            
            # 若指定單一市場，非目標市場持股直接保留不處理
            if target_market == "TW" and not is_tw:
                kept_positions.append(pos)
                continue
            if target_market == "US" and is_tw:
                kept_positions.append(pos)
                continue

            if ticker not in self.dataset or self.dataset[ticker].empty:
                kept_positions.append(pos)
                continue

            df = self.dataset[ticker]
            curr_price = float(df["close"].iloc[-1])
            cost_price = float(pos.get("cost_price", curr_price))
            shares = float(pos.get("shares", 1))
            entry_date = pos.get("entry_date", today_str)

            # 計算高點與回檔
            sub_df = df.loc[df.index >= pd.to_datetime(entry_date)]
            peak_price = float(sub_df["high"].max()) if not sub_df.empty else max(curr_price, cost_price)
            peak_price = max(peak_price, curr_price, cost_price)
            drawdown = ((curr_price - peak_price) / peak_price) * 100

            # 50MA
            sma50 = float(df["close"].rolling(50).mean().iloc[-1])
            prefix = "NT$" if is_tw else "$"
            name = TECH_UNIVERSE_TW.get(ticker, ticker)

            # 判斷是否觸發平倉
            exit_reason = None
            if drawdown <= -self.trailing_stop_pct:
                exit_reason = f"高點回檔 {abs(drawdown):.1f}% 觸發 8% 停利停損"
            elif curr_price < sma50:
                exit_reason = f"收盤價跌破 50MA 生命線 ({prefix}{sma50:,.1f})"

            if exit_reason:
                ret_pct = ((curr_price - cost_price) / cost_price) * 100
                pnl = (curr_price - cost_price) * shares
                log_msg = f"🔴 【模擬賣出平倉】{name} ({ticker})\n   └ 原因: {exit_reason}\n   └ 平倉價: {prefix}{curr_price:,.2f} (報酬率: {ret_pct:+.2f}%, 損益: {prefix}{pnl:+,.0f})"
                trade_logs.append(log_msg)
            else:
                kept_positions.append(pos)

        # ----------------------------------------------------
        # 步驟 2: 檢查市場環境與買進新標的 (Top 3 站上 50MA 強勢標的)
        # 限制單一市場最多持有 3 檔，若跌出前 5 名且有更強標的則自動換股
        # ----------------------------------------------------
        # 2A. 台股市場
        if target_market in ["ALL", "TW"]:
            tw_top3_raw = tw_rank.head(3)
            tw_bull_count = tw_top3_raw["above_50sma"].sum() if not tw_top3_raw.empty else 0
            if tw_bull_count >= 2:
                tw_candidates = tw_rank[tw_rank["above_50sma"] == True].head(3)
                tw_top5_tickers = set(tw_rank.head(5)["ticker"])
                
                for _, row in tw_candidates.iterrows():
                    t = row["ticker"]
                    current_held_tickers = set(p["ticker"] for p in kept_positions)
                    if t in current_held_tickers:
                        continue
                    
                    # 統計目前台股持倉
                    curr_tw_positions = [p for p in kept_positions if (".TW" in p["ticker"] or ".TWO" in p["ticker"])]
                    if len(curr_tw_positions) >= 3:
                        # 檢查是否有持股已跌出前 5 名
                        out_of_top5 = [p for p in curr_tw_positions if p["ticker"] not in tw_top5_tickers]
                        if out_of_top5:
                            # 挑選排名最落後的標的執行換股平倉
                            def get_tw_rank_idx(sym):
                                idxs = tw_rank.index[tw_rank["ticker"] == sym].tolist()
                                return idxs[0] if idxs else 999
                            out_of_top5.sort(key=lambda p: get_tw_rank_idx(p["ticker"]), reverse=True)
                            swap_out = out_of_top5[0]
                            kept_positions.remove(swap_out)
                            
                            s_ticker = swap_out["ticker"]
                            s_shares = swap_out["shares"]
                            s_cost = swap_out["cost_price"]
                            s_name = TECH_UNIVERSE_TW.get(s_ticker, s_ticker)
                            s_df = self.dataset.get(s_ticker)
                            s_px = float(s_df["close"].iloc[-1]) if s_df is not None and not s_df.empty else s_cost
                            s_ret = ((s_px - s_cost) / s_cost) * 100
                            s_pnl = (s_px - s_cost) * s_shares
                            
                            trade_logs.append(
                                f"🔄 【調倉換股平倉】{s_name} ({s_ticker})\n"
                                f"   └ 原因: 跌出動能前5名 (目前排名 #{get_tw_rank_idx(s_ticker)+1})，由更強標的 {TECH_UNIVERSE_TW.get(t, t)} ({t}) 替換\n"
                                f"   └ 平倉價: NT${s_px:,.2f} (報酬率: {s_ret:+.2f}%, 損益: NT${s_pnl:+,.0f})"
                            )
                        else:
                            # 現有 3 檔皆在前 5 強內，不強行換股
                            continue
                            
                    px = float(row["price"])
                    shares = max(1, int(self.budget_tw / px))
                    name = TECH_UNIVERSE_TW.get(t, t)
                    kept_positions.append({
                        "ticker": t,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": today_str
                    })
                    trade_logs.append(
                        f"🟢 【模擬買進委託】{name} ({t})\n"
                        f"   └ 股數: {shares} 股 (零股委託)\n"
                        f"   └ 進場價: NT${px:,.2f} (預算約 NT${shares * px:,.0f})\n"
                        f"   └ 依據: 站上50MA強勢入選 (評分: {row['score']:.1f})"
                    )
            else:
                trade_logs.append("🛡️ 【台股風控保護】目前台股前三強僅 1 檔站上 50MA，處於保守防禦模式，今日不開新倉。")

        # 2B. 美股市場
        if target_market in ["ALL", "US"]:
            us_top3_raw = us_rank.head(3)
            us_bull_count = us_top3_raw["above_50sma"].sum() if not us_top3_raw.empty else 0
            qqq_df = self.dataset.get("QQQ")
            qqq_bull = True
            if qqq_df is not None and not qqq_df.empty:
                q_close = float(qqq_df["close"].iloc[-1])
                q_sma200 = float(qqq_df["close"].rolling(200).mean().iloc[-1])
                qqq_bull = (q_close >= q_sma200)

            if us_bull_count >= 2 and qqq_bull:
                us_candidates = us_rank[us_rank["above_50sma"] == True].head(3)
                us_top5_tickers = set(us_rank.head(5)["ticker"])
                
                for _, row in us_candidates.iterrows():
                    t = row["ticker"]
                    current_held_tickers = set(p["ticker"] for p in kept_positions)
                    if t in current_held_tickers:
                        continue
                    
                    curr_us_positions = [p for p in kept_positions if not (".TW" in p["ticker"] or ".TWO" in p["ticker"])]
                    if len(curr_us_positions) >= 3:
                        out_of_top5 = [p for p in curr_us_positions if p["ticker"] not in us_top5_tickers]
                        if out_of_top5:
                            def get_us_rank_idx(sym):
                                idxs = us_rank.index[us_rank["ticker"] == sym].tolist()
                                return idxs[0] if idxs else 999
                            out_of_top5.sort(key=lambda p: get_us_rank_idx(p["ticker"]), reverse=True)
                            swap_out = out_of_top5[0]
                            kept_positions.remove(swap_out)
                            
                            s_ticker = swap_out["ticker"]
                            s_shares = swap_out["shares"]
                            s_cost = swap_out["cost_price"]
                            s_df = self.dataset.get(s_ticker)
                            s_px = float(s_df["close"].iloc[-1]) if s_df is not None and not s_df.empty else s_cost
                            s_ret = ((s_px - s_cost) / s_cost) * 100
                            s_pnl = (s_px - s_cost) * s_shares
                            
                            trade_logs.append(
                                f"🔄 【調倉換股平倉】{s_ticker} (美股)\n"
                                f"   └ 原因: 跌出動能前5名 (目前排名 #{get_us_rank_idx(s_ticker)+1})，由更強標的 {t} 替換\n"
                                f"   └ 平倉價: ${s_px:,.2f} (報酬率: {s_ret:+.2f}%, 損益: ${s_pnl:+,.2f})"
                            )
                        else:
                            continue
                            
                    px = float(row["price"])
                    shares = max(1, int(self.budget_us / px))
                    kept_positions.append({
                        "ticker": t,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": today_str
                    })
                    trade_logs.append(
                        f"🟢 【模擬買進委託】{t} (美股)\n"
                        f"   └ 股數: {shares} 股\n"
                        f"   └ 進場價: ${px:,.2f} (預算約 ${shares * px:,.0f})\n"
                        f"   └ 依據: 站上50MA強勢入選 (評分: {row['score']:.1f})"
                    )
            else:
                trade_logs.append("🛡️ 【美股風控保護】大盤 QQQ 年線轉弱或前三強分化，處於保守防禦模式，今日不開新倉。")

        # 儲存回 portfolio.json
        PortfolioTracker.save_portfolio(kept_positions)
        return trade_logs, kept_positions
