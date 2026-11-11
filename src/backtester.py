"""
台美純科技股量化回測引擎 (基於向量化與事件驅動的動量輪動與風控模型)
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from src.config import config
from src.features import TechFeatureEngine

class TechBacktester:
    def __init__(
        self, 
        dataset: Dict[str, pd.DataFrame], 
        initial_capital: float = 100000.0,
        fee_rate: float = 0.001,          # 單邊交易手續費 + 滑價 (0.1%)
        rebalance_freq: int = 5,           # 調倉頻率 (每 5 個交易日約一週)
        top_n: int = 3,                    # 持有前 N 強標的
        enable_50sma_filter: bool = True,  # 啟用 50MA 趨勢多空濾網
        trailing_stop_pct: float = 0.08    # 追蹤停損 8%
    ):
        self.dataset = dataset
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.rebalance_freq = rebalance_freq
        self.top_n = top_n
        self.enable_50sma_filter = enable_50sma_filter
        self.trailing_stop_pct = trailing_stop_pct

    def run(self, market: str = "US") -> Dict:
        """
        執行回測
        :param market: "US" 或 "TW"
        """
        # 1. 篩選對應市場的數據
        filtered_data = {}
        for ticker, df in self.dataset.items():
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            if (market == "TW" and is_tw) or (market == "US" and not is_tw):
                # 先計算特徵指標
                filtered_data[ticker] = TechFeatureEngine.calculate_technical_features(df)

        if not filtered_data:
            raise ValueError(f"市場 {market} 無有效數據！")

        # 2. 獲取公共交易日曆（取所有標的日期的交集或聯集排序）
        all_dates = sorted(list(set.union(*[set(df.index) for df in filtered_data.values()])))
        
        # 確保足夠長歷史以暖機均線（跳過前 60 天初始化特徵）
        start_idx = 60
        if len(all_dates) <= start_idx:
            raise ValueError("歷史資料天數過短，不足以完成指標預熱！")

        test_dates = all_dates[start_idx:]
        
        # 3. 準備回測狀態變數
        cash = self.initial_capital
        holdings = {}        # {ticker: shares}
        entry_prices = {}    # {ticker: entry_price}
        peak_prices = {}     # {ticker: peak_price}
        
        portfolio_values = []
        trade_logs = []
        
        # 4. 開始日線回測循環
        for day_idx, current_date in enumerate(test_dates):
            # A. 更新當前持倉的市值與最高價（用於追蹤停損）
            current_portfolio_value = cash
            liquidate_due_to_stop = []
            
            for ticker, shares in list(holdings.items()):
                df = filtered_data[ticker]
                if current_date in df.index:
                    curr_price = float(df.loc[current_date, "close"])
                    # 更新波段最高價
                    peak_prices[ticker] = max(peak_prices.get(ticker, curr_price), curr_price)
                    
                    # 檢查追蹤停損 (Trailing Stop)
                    drawdown_from_peak = (peak_prices[ticker] - curr_price) / peak_prices[ticker]
                    if drawdown_from_peak >= self.trailing_stop_pct:
                        liquidate_due_to_stop.append((ticker, curr_price, "停損平倉 (回檔達8%)"))
                    else:
                        current_portfolio_value += shares * curr_price
                else:
                    # 若當日無資料，以最後已知名稱暫估
                    pass

            # 執行停損平倉
            for ticker, exit_price, reason in liquidate_due_to_stop:
                shares = holdings.pop(ticker)
                sell_proceeds = shares * exit_price * (1 - self.fee_rate)
                cash += sell_proceeds
                pnl = sell_proceeds - (shares * entry_prices[ticker])
                pnl_pct = (exit_price / entry_prices[ticker] - 1) * 100
                trade_logs.append({
                    "date": current_date,
                    "ticker": ticker,
                    "action": "SELL",
                    "reason": reason,
                    "price": round(exit_price, 2),
                    "shares": round(shares, 4),
                    "pnl": round(pnl, 2),
                    "pnl_pct": f"{pnl_pct:+.2f}%"
                })
                entry_prices.pop(ticker, None)
                peak_prices.pop(ticker, None)

            # B. 週期性調倉 (Rebalancing)
            if day_idx % self.rebalance_freq == 0:
                # 評估當日所有候選股票的評分
                candidates = []
                for ticker, df in filtered_data.items():
                    if current_date in df.index:
                        row = df.loc[current_date]
                        score = float(row["momentum_score"]) if not np.isnan(row["momentum_score"]) else -999.0
                        above_50 = bool(row["above_50sma"])
                        
                        # 趨勢濾網：若啟用 50MA 濾網且股價低於 50MA，直接排除
                        if self.enable_50sma_filter and not above_50:
                            continue
                            
                        candidates.append((ticker, score, float(row["close"])))
                
                # 依分數排序，挑選前 N 強
                candidates.sort(key=lambda x: x[1], reverse=True)
                top_targets = candidates[:self.top_n]
                target_tickers = [x[0] for x in top_targets]

                # 大盤大空頭總避險濾網 (Market Regime Filter)
                # 台股：前三強需有至少 2 檔站上 50MA（領頭群健康發動）
                # 美股：QQQ 大盤指數需高於 200MA 年線（大趨勢多頭）
                is_market_bull = True
                if market == "TW":
                    all_scores = []
                    for t, d in filtered_data.items():
                        if current_date in d.index:
                            r = d.loc[current_date]
                            sc = float(r["momentum_score"]) if not np.isnan(r["momentum_score"]) else -999.0
                            all_scores.append((t, sc, bool(r["above_50sma"])))
                    all_scores.sort(key=lambda x: x[1], reverse=True)
                    top3_bull_count = sum(1 for x in all_scores[:3] if x[2])
                    is_market_bull = (top3_bull_count >= 2)
                elif market == "US" and "QQQ" in self.dataset:
                    q_df = filtered_data.get("QQQ", self.dataset.get("QQQ"))
                    if q_df is not None and current_date in q_df.index:
                        q_c = float(q_df.loc[current_date, "close"])
                        q_sma = float(q_df.loc[current_date, "sma_200"]) if "sma_200" in q_df.columns else float(q_df["close"].rolling(200).mean().loc[current_date])
                        is_market_bull = (q_c >= q_sma) if not np.isnan(q_sma) else True

                if not is_market_bull:
                    # 大盤轉入空頭防禦期：不開新倉，保留 100% 現金防禦
                    target_tickers = []
                    top_targets = []
                
                # 1. 賣出：平倉不在目標清單中的持股
                for ticker in list(holdings.keys()):
                    if ticker not in target_tickers:
                        df = filtered_data[ticker]
                        if current_date in df.index:
                            curr_price = float(df.loc[current_date, "close"])
                            shares = holdings.pop(ticker)
                            sell_proceeds = shares * curr_price * (1 - self.fee_rate)
                            cash += sell_proceeds
                            pnl = sell_proceeds - (shares * entry_prices[ticker])
                            pnl_pct = (curr_price / entry_prices[ticker] - 1) * 100
                            trade_logs.append({
                                "date": current_date,
                                "ticker": ticker,
                                "action": "SELL",
                                "reason": "調倉換股 (動能減弱/跌破50MA)",
                                "price": round(curr_price, 2),
                                "shares": round(shares, 4),
                                "pnl": round(pnl, 2),
                                "pnl_pct": f"{pnl_pct:+.2f}%"
                            })
                            entry_prices.pop(ticker, None)
                            peak_prices.pop(ticker, None)

                # 2. 買入 / 調倉：為目標清單中的標的配置資金
                # 每個標的目標配置比例為 1 / top_n
                if target_tickers:
                    # 重新計算當前可用總資產 (Cash + 現有持倉市值)
                    equity = cash
                    for t, s in holdings.items():
                        df = filtered_data[t]
                        if current_date in df.index:
                            equity += s * float(df.loc[current_date, "close"])
                    
                    target_alloc_per_ticker = equity / self.top_n
                    
                    for ticker, score, curr_price in top_targets:
                        current_shares = holdings.get(ticker, 0.0)
                        current_val = current_shares * curr_price
                        
                        # 若尚未達到目標倉位，進行加碼買入
                        if target_alloc_per_ticker > current_val:
                            budget = min(target_alloc_per_ticker - current_val, cash)
                            if budget > (equity * 0.02):  # 差異大於 2% 才調整，避免微額碎股頻繁交易
                                buy_cost_per_share = curr_price * (1 + self.fee_rate)
                                shares_to_buy = budget / buy_cost_per_share
                                cash -= shares_to_buy * buy_cost_per_share
                                
                                # 更新持倉與加權平均進場成本
                                if ticker in holdings:
                                    total_shares = current_shares + shares_to_buy
                                    avg_cost = (current_val + budget) / total_shares
                                    holdings[ticker] = total_shares
                                    entry_prices[ticker] = avg_cost
                                else:
                                    holdings[ticker] = shares_to_buy
                                    entry_prices[ticker] = curr_price
                                    peak_prices[ticker] = curr_price
                                    
                                trade_logs.append({
                                    "date": current_date,
                                    "ticker": ticker,
                                    "action": "BUY",
                                    "reason": f"動能入選 (評分: {score:.1f})",
                                    "price": round(curr_price, 2),
                                    "shares": round(shares_to_buy, 4),
                                    "pnl": 0.0,
                                    "pnl_pct": "0.00%"
                                })

            # 計算當日收盤最終總淨值 (現金 + 現有持倉市值)
            end_of_day_equity = cash
            for t, s in holdings.items():
                df = filtered_data[t]
                if current_date in df.index:
                    end_of_day_equity += s * float(df.loc[current_date, "close"])
                else:
                    # 若當日該標的休市或無成交，沿用前一交易日已知價格
                    past_prices = df.loc[df.index <= current_date, "close"]
                    if not past_prices.empty:
                        end_of_day_equity += s * float(past_prices.iloc[-1])

            portfolio_values.append({
                "date": current_date,
                "portfolio_value": round(end_of_day_equity, 2)
            })

        # 5. 計算績效統計
        perf_df = pd.DataFrame(portfolio_values).set_index("date")
        perf_df["daily_return"] = perf_df["portfolio_value"].pct_change().fillna(0)
        
        total_days = len(perf_df)
        years = total_days / 252.0
        start_val = self.initial_capital
        end_val = perf_df["portfolio_value"].iloc[-1]
        
        total_return = (end_val / start_val - 1) * 100
        cagr = ((end_val / start_val) ** (1 / max(years, 0.1)) - 1) * 100
        
        # 最大回撤 (MDD)
        cum_max = perf_df["portfolio_value"].cummax()
        drawdown = (perf_df["portfolio_value"] - cum_max) / cum_max
        max_drawdown = drawdown.min() * 100
        
        # 夏普比率 (Sharpe Ratio, 假設年化無風險利率 2%)
        mean_ret = perf_df["daily_return"].mean() * 252
        vol = perf_df["daily_return"].std() * np.sqrt(252)
        sharpe = (mean_ret - 0.02) / (vol + 1e-9)
        
        # 交易統計
        trades_df = pd.DataFrame(trade_logs)
        win_rate = 0.0
        if not trades_df.empty and "pnl" in trades_df.columns:
            profitable = (trades_df["pnl"] > 0).sum()
            win_rate = (profitable / len(trades_df)) * 100

        # 計算基準報酬 (台股 0052.TW，美股 QQQ)
        bench_ticker = "0052.TW" if market == "TW" else "QQQ"
        bench_return = 0.0
        if bench_ticker in self.dataset:
            b_df = self.dataset[bench_ticker]
            b_sub = b_df.loc[test_dates[0]:test_dates[-1]]
            if not b_sub.empty and len(b_sub) > 1:
                bench_return = float((b_sub["close"].iloc[-1] / b_sub["close"].iloc[0] - 1) * 100)

        return {
            "market": market,
            "start_date": test_dates[0].strftime("%Y-%m-%d"),
            "end_date": test_dates[-1].strftime("%Y-%m-%d"),
            "total_trading_days": total_days,
            "initial_capital": start_val,
            "final_value": round(end_val, 2),
            "total_return_pct": round(total_return, 2),
            "total_return": round(total_return, 2),
            "cagr_pct": round(cagr, 2),
            "cagr": round(cagr, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2),
            "benchmark_ticker": bench_ticker,
            "benchmark_return": round(bench_return, 2),
            "total_trades": len(trades_df),
            "win_rate_pct": round(win_rate, 2),
            "perf_df": perf_df,
            "trades_df": trades_df
        }
