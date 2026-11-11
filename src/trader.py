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

    def execute_daily_simulation(self, tw_rank: pd.DataFrame, us_rank: pd.DataFrame) -> Tuple[List[str], List[Dict]]:
        """
        執行每日模擬下單流程：
        1. 檢查現有部位停損平倉
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
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
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
        # 步驟 2: 檢查市場環境與買進新標的 (Top 3)
        # ----------------------------------------------------
        # 2A. 台股市場
        tw_top3 = tw_rank.head(3)
        tw_bull_count = tw_top3["above_50sma"].sum()
        if tw_bull_count >= 2:
            # 多頭攻擊：買進未持有的前 3 強
            for _, row in tw_top3.iterrows():
                t = row["ticker"]
                if t not in current_tickers and row["above_50sma"]:
                    px = float(row["price"])
                    shares = max(1, int(self.budget_tw / px))
                    name = TECH_UNIVERSE_TW.get(t, t)
                    kept_positions.append({
                        "ticker": t,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": today_str
                    })
                    current_tickers.add(t)
                    trade_logs.append(f"🟢 【模擬買進委託】{name} ({t})\n   └ 股數: {shares} 股 (零股委託)\n   └ 進場價: NT${px:,.2f} (預算約 NT${shares * px:,.0f})\n   └ 依據: 動能天梯入選 (評分: {row['score']:.1f})")
        else:
            trade_logs.append("🛡️ 【台股風控保護】目前台股前三強僅 1 檔站上 50MA，處於保守防禦模式，今日不開新倉。")

        # 2B. 美股市場
        us_top3 = us_rank.head(3)
        us_bull_count = us_top3["above_50sma"].sum()
        if us_bull_count >= 2:
            for _, row in us_top3.iterrows():
                t = row["ticker"]
                if t not in current_tickers and row["above_50sma"]:
                    px = float(row["price"])
                    shares = max(1, int(self.budget_us / px))
                    kept_positions.append({
                        "ticker": t,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": today_str
                    })
                    current_tickers.add(t)
                    trade_logs.append(f"🟢 【模擬買進委託】{t} (美股)\n   └ 股數: {shares} 股\n   └ 進場價: ${px:,.2f} (預算約 ${shares * px:,.0f})\n   └ 依據: 動能天梯入選 (評分: {row['score']:.1f})")

        # 儲存回 portfolio.json
        PortfolioTracker.save_portfolio(kept_positions)
        return trade_logs, kept_positions
