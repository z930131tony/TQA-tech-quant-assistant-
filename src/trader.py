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

try:
    import shioaji as sj
    SHIOAJI_AVAILABLE = True
except ImportError:
    sj = None
    SHIOAJI_AVAILABLE = False

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
        liquidated_today = set()

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

            # 計算高點與回檔 (僅搜尋進場日隔天之後的最高價，避開進場日上影線誤判)
            if entry_date:
                sub_df = df.loc[df.index > pd.to_datetime(entry_date)]
                post_entry_high = float(sub_df["high"].max()) if not sub_df.empty else cost_price
            else:
                post_entry_high = float(df["high"].tail(60).max())
            peak_price = max(post_entry_high, curr_price, cost_price)
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
                liquidated_today.add(ticker)
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
                tw_buys_count = 0
                
                for _, row in tw_candidates.iterrows():
                    t = row["ticker"]
                    current_held_tickers = set(p["ticker"] for p in kept_positions)
                    if t in current_held_tickers or t in liquidated_today:
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
                            liquidated_today.add(swap_out["ticker"])
                            
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
                    t_entry_date = self.dataset[t].index[-1].strftime("%Y-%m-%d") if (t in self.dataset and not self.dataset[t].empty) else today_str
                    kept_positions.append({
                        "ticker": t,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": t_entry_date
                    })
                    tw_buys_count += 1
                    trade_logs.append(
                        f"🟢 【模擬買進委託】{name} ({t})\n"
                        f"   └ 股數: {shares} 股 (零股委託)\n"
                        f"   └ 進場價: NT${px:,.2f} (預算約 NT${shares * px:,.0f})\n"
                        f"   └ 依據: 站上50MA強勢入選 (評分: {row['score']:.1f})"
                    )

                curr_tw_positions = [p for p in kept_positions if (".TW" in p["ticker"] or ".TWO" in p["ticker"])]
                if tw_buys_count == 0 and curr_tw_positions:
                    trade_logs.append("✅ 【多頭續抱】目前持有部位皆位居動能前段班且站穩 50MA，今日維持續抱。")
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
                us_buys_count = 0
                
                for _, row in us_candidates.iterrows():
                    t = row["ticker"]
                    current_held_tickers = set(p["ticker"] for p in kept_positions)
                    if t in current_held_tickers or t in liquidated_today:
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
                            liquidated_today.add(swap_out["ticker"])
                            
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
                    t_entry_date = self.dataset[t].index[-1].strftime("%Y-%m-%d") if (t in self.dataset and not self.dataset[t].empty) else today_str
                    kept_positions.append({
                        "ticker": t,
                        "shares": shares,
                        "cost_price": px,
                        "entry_date": t_entry_date
                    })
                    us_buys_count += 1
                    trade_logs.append(
                        f"🟢 【模擬買進委託】{t} (美股)\n"
                        f"   └ 股數: {shares} 股\n"
                        f"   └ 進場價: ${px:,.2f} (預算約 ${shares * px:,.0f})\n"
                        f"   └ 依據: 站上50MA強勢入選 (評分: {row['score']:.1f})"
                    )

                curr_us_positions = [p for p in kept_positions if not (".TW" in p["ticker"] or ".TWO" in p["ticker"])]
                if us_buys_count == 0 and curr_us_positions:
                    trade_logs.append("✅ 【多頭續抱】目前持有部位皆位居動能前段班且站穩 50MA，今日維持續抱。")
            else:
                trade_logs.append("🛡️ 【美股風控保護】大盤 QQQ 年線轉弱或前三強分化，處於保守防禦模式，今日不開新倉。")

        # 儲存回 portfolio.json
        PortfolioTracker.save_portfolio(kept_positions)
        return trade_logs, kept_positions

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

            # 抓取台股部位 (包含零股與整張)
            positions = api.list_positions(api.stock_account, unit=sj.constant.Unit.Share)
            if not positions:
                print("  ℹ️ 永豐帳戶目前無庫存部位。")
                return PortfolioTracker.load_portfolio()

            synced_positions = []
            today_str = datetime.now().strftime("%Y-%m-%d")
            for p in positions:
                code = str(getattr(p, "code", "")).strip()
                if not code:
                    continue
                sym = f"{code}.TW" if not code.endswith(".TW") and not code.endswith(".TWO") else code
                qty = int(getattr(p, "quantity", 0))
                price = float(getattr(p, "price", 0.0))
                if qty > 0:
                    synced_positions.append({
                        "ticker": sym,
                        "shares": qty,
                        "cost_price": round(price, 2),
                        "entry_date": today_str
                    })

            # 合併非台股部位 (保留美股部位)
            existing = PortfolioTracker.load_portfolio()
            us_positions = [pos for pos in existing if not (".TW" in pos.get("ticker", "") or ".TWO" in pos.get("ticker", ""))]
            final_portfolio = synced_positions + us_positions

            PortfolioTracker.save_portfolio(final_portfolio)
            print(f"  ✅ 成功從永豐 Shioaji 同步 {len(synced_positions)} 檔台股部位至 portfolio.json。")
            return final_portfolio

        except Exception as e:
            print(f"⚠️ 永豐 Shioaji 連線或同步異常: {e}，維持現有部位檔案。")
            return PortfolioTracker.load_portfolio()

    def execute_semi_auto_order(
        self,
        signals: List[Dict],
        default_budget: float = 3000.0,
        interactive: bool = True
    ) -> List[Dict]:
        """
        永豐大戶投零股半自動委託確認與下單：
        1. 計算單檔零股股數、手續費安全緩衝與風控關鍵位
        2. 終端機格式化輸出委託確認卡片
        3. 要求使用者手動輸入 'CONFIRM' 始送出委託 (安全防呆鎖)
        """
        executed_orders = []
        if not signals:
            print("ℹ️ 今日無新的買進委託訊號。")
            return executed_orders

        print("\n" + "=" * 65)
        print("📋 【永豐大戶投】零股委託掛單確認 (Semi-Auto Order Confirmation)")
        print("=" * 65)

        for sig in signals:
            ticker = sig.get("ticker", "")
            name = TECH_UNIVERSE_TW.get(ticker, sig.get("name", ticker))
            price = float(sig.get("price", 0.0))
            if price <= 0:
                continue

            # 零股股數計算 (含 0.1425% 手續費與滑點安全緩衝)
            shares = max(1, int(default_budget / (price * 1.0028)))
            est_cost = shares * price
            est_fee = max(1.0, round(est_cost * 0.001425, 1))
            total_est = est_cost + est_fee

            step_price = round(price * 0.90, 1)      # -10% 階梯加碼位
            stop_price = round(price * 0.92, 1)      # -8% 移動停損位
            hard_stop = round(price * 0.70, 1)       # -30% 戰術硬停損位

            print(f"\n標的名稱: {name} ({ticker})")
            print(f"  • 當前市價: NT$ {price:,.2f}")
            print(f"  • 單檔預算: NT$ {default_budget:,.0f}")
            print(f"  • 建議股數: {shares} 股 (預估金額: NT$ {est_cost:,.0f} + 手續費約 NT$ {est_fee:,.0f} = NT$ {total_est:,.0f})")
            print(f"  • 🛡️ 風控參考價位:")
            print(f"      -10% 階梯佈局價: NT$ {step_price:,.1f}")
            print(f"      -8%  移動停利停損: NT$ {stop_price:,.1f}")
            print(f"      -30% 戰術硬停損位: NT$ {hard_stop:,.1f}")

            user_action = "CONFIRM"
            if interactive:
                prompt_msg = f"  👉 是否送出【{name} ({ticker})】{shares} 股買進委託？輸入 'CONFIRM' 確認，其餘任意鍵跳過: "
                try:
                    user_action = input(prompt_msg).strip()
                except (EOFError, KeyboardInterrupt):
                    user_action = "SKIP"

            if user_action == "CONFIRM":
                order_record = {
                    "ticker": ticker,
                    "name": name,
                    "shares": shares,
                    "price": price,
                    "status": "SUBMITTED",
                    "time": datetime.now(self.tw_tz).strftime("%Y-%m-%d %H:%M:%S")
                }

                # 若具備 Shioaji 則可送出模擬/實盤掛單
                if SHIOAJI_AVAILABLE and os.getenv("SHIOAJI_API_KEY"):
                    try:
                        sim = os.getenv("SHIOAJI_SIMULATION", "true").lower() == "true"
                        api = sj.Shioaji(simulation=sim)
                        api.login(api_key=os.getenv("SHIOAJI_API_KEY"), secret_key=os.getenv("SHIOAJI_SECRET_KEY"))
                        clean_sym = ticker.replace(".TW", "").replace(".TWO", "")
                        contract = api.Contracts.Stocks[clean_sym]
                        order = api.Order(
                            price=price,
                            quantity=shares,
                            action=sj.constant.Action.Buy,
                            price_type=sj.constant.StockPriceType.LMT,
                            order_type=sj.constant.OrderType.ROD,
                            order_lot=sj.constant.StockOrderLot.IntradayOdd
                        )
                        trade = api.place_order(contract, order)
                        order_record["trade_id"] = str(getattr(trade, "order", {}).get("id", "SIM-1"))
                        print(f"  🚀 【下單成功】已送出永豐零股委託: {name} {shares} 股 @ NT${price:,.2f}")
                    except Exception as order_err:
                        print(f"  ⚠️ Shioaji 下單異常: {order_err}，轉為本地紀錄。")
                else:
                    print(f"  💡 【模擬確認】已記錄模擬買進委託: {name} {shares} 股 @ NT${price:,.2f}")

                executed_orders.append(order_record)
            else:
                print(f"  ⏸️ 使用者取消【{name}】委託。")

        print("=" * 65 + "\n")
        return executed_orders
