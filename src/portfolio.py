"""
個人投資組合與風控追蹤模組 (Portfolio & Risk Tracker)
功能：
1. 讀取 portfolio.json 個人持股 (股數、買進成本、進場日期)
2. 比對現價、50MA 生命線、波段最高價回檔
3. 產生 8% 移動停利停損警報與 LINE 推播文案
4. 輸出網頁端個人資產卡片 HTML
"""
import os
import json
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from src.config import TECH_UNIVERSE_TW, config

PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "portfolio.json")

class PortfolioTracker:
    @staticmethod
    def load_portfolio(filepath: str = PORTFOLIO_FILE) -> List[Dict]:
        """讀取個人持股設定檔"""
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("positions", [])
        except Exception as e:
            print(f"[警告] 讀取 portfolio.json 失敗: {e}")
            return []

    @staticmethod
    def save_portfolio(positions: List[Dict], filepath: str = PORTFOLIO_FILE):
        """儲存個人持股設定檔"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"positions": positions}, f, ensure_ascii=False, indent=2)

    @classmethod
    def evaluate_portfolio(cls, dataset: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        評估個人每檔持股的損益與出場風控條件
        風控規則：
        1. 跌破 50MA：中期生命線跌破，趨勢轉弱。
        2. 自買進後波段高點回檔 >= 8%：觸發移動停利/停損。
        """
        positions = cls.load_portfolio()
        if not positions:
            return []

        evaluated = []
        for pos in positions:
            ticker = pos.get("ticker", "").strip()
            shares = float(pos.get("shares", 0))
            cost_price = float(pos.get("cost_price", 0.0))
            entry_date = pos.get("entry_date", "")

            if ticker not in dataset or dataset[ticker].empty:
                continue

            df = dataset[ticker].copy()
            if "date" in df.columns:
                df = df.set_index("date")

            latest = df.iloc[-1]
            curr_price = float(latest["close"])
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            name = TECH_UNIVERSE_TW.get(ticker, ticker)

            # 計算 50MA
            sma50 = float(df["close"].rolling(50).mean().iloc[-1])
            is_above_50ma = curr_price >= sma50

            # 計算買進之後的波段最高價
            if entry_date:
                sub_df = df.loc[df.index >= pd.to_datetime(entry_date)]
                if not sub_df.empty:
                    peak_price = float(sub_df["high"].max())
                else:
                    peak_price = curr_price
            else:
                peak_price = float(df["high"].tail(60).max())

            peak_price = max(peak_price, curr_price, cost_price)
            drawdown_from_peak = ((curr_price - peak_price) / peak_price) * 100
            trailing_stop_triggered = (drawdown_from_peak <= -8.0)

            # 計算損益
            market_val = shares * curr_price
            cost_val = shares * cost_price
            unrealized_pnl = market_val - cost_val
            return_pct = ((curr_price - cost_price) / cost_price * 100) if cost_price > 0 else 0.0

            # 警報判斷
            alerts = []
            if not is_above_50ma:
                alerts.append("跌破50MA生命線")
            if trailing_stop_triggered:
                alerts.append(f"高點回檔已達 {abs(drawdown_from_peak):.1f}% (滿8%停利停損)")

            has_alert = len(alerts) > 0
            alert_text = " + ".join(alerts) if has_alert else "多頭軌道安全"

            evaluated.append({
                "ticker": ticker,
                "name": name,
                "is_tw": is_tw,
                "shares": shares,
                "cost_price": cost_price,
                "curr_price": curr_price,
                "market_val": market_val,
                "cost_val": cost_val,
                "unrealized_pnl": unrealized_pnl,
                "return_pct": return_pct,
                "peak_price": peak_price,
                "drawdown_from_peak": drawdown_from_peak,
                "sma50": sma50,
                "is_above_50ma": is_above_50ma,
                "trailing_stop_triggered": trailing_stop_triggered,
                "has_alert": has_alert,
                "alert_text": alert_text
            })

        return evaluated

    @classmethod
    def format_line_notification(cls, evaluated_positions: List[Dict], market_type: str = "TW") -> str:
        """
        產生 LINE 推播中的個人持股風控摘要文字
        market_type: 'TW' 或 'US'
        """
        filtered = [p for p in evaluated_positions if (p["is_tw"] if market_type == "TW" else not p["is_tw"])]
        if not filtered:
            return ""

        lines = ["💼 【個人自訂持股風控監控】"]
        alerts = [p for p in filtered if p["has_alert"]]
        
        if alerts:
            lines.append("⚠️ 出場警戒注意：")
            for p in alerts:
                curr_str = f"NT${p['curr_price']:,.2f}" if p["is_tw"] else f"${p['curr_price']:,.2f}"
                pnl_str = f"{'+' if p['return_pct'] >= 0 else ''}{p['return_pct']:.2f}%"
                lines.append(f"• {p['name']} ({p['ticker']}) {curr_str} (報酬: {pnl_str})")
                lines.append(f"  └ 警報原因: {p['alert_text']}")
                lines.append(f"  └ 建議動作: 請開啟大戶投/複委託考慮減碼或平倉！")
        else:
            lines.append("✅ 目前持有標的均處於安全多頭軌道，未觸發 8% 回檔與 50MA 跌破，可穩定續抱。")

        lines.append("")
        return "\n".join(lines)

    @classmethod
    def generate_portfolio_html(cls, evaluated_positions: List[Dict], market_type: str = "TW") -> str:
        """產生網頁儀表板中的持股卡片 HTML"""
        filtered = [p for p in evaluated_positions if (p["is_tw"] if market_type == "TW" else not p["is_tw"])]
        if not filtered:
            return """
            <div style="background: #182238; border: 1px dashed #243049; border-radius: 10px; padding: 20px; text-align: center; color: #64748b;">
                目前尚未設定自訂持股。可在 <code>portfolio.json</code> 新增您的庫存標的。
            </div>
            """

        rows = []
        for p in filtered:
            prefix = "NT$" if p["is_tw"] else "$"
            ret_color = "#34d399" if p["return_pct"] >= 0 else "#f87171"
            pnl_sign = "+" if p["unrealized_pnl"] >= 0 else ""
            
            badge_html = f'<span class="badge badge-bear" style="background:#450a0a; color:#f87171; border:1px solid #991b1b;">⚠️ {p["alert_text"]}</span>' if p["has_alert"] else '<span class="badge badge-bull">✅ 續抱中</span>'
            
            row = f"""
            <tr class="clickable" onclick="openStockModal('{p['ticker']}')">
                <td>
                    <div style="font-weight:bold; color:#f1f5f9;">{p['name']}</div>
                    <div style="font-size:12px; color:#64748b; font-family:monospace;">{p['ticker']} ({int(p['shares'])} 股)</div>
                </td>
                <td class="text-right font-mono">{prefix}{p['cost_price']:,.2f}</td>
                <td class="text-right font-mono" style="font-weight:bold;">{prefix}{p['curr_price']:,.2f}</td>
                <td class="text-right font-mono" style="color:{ret_color}; font-weight:bold;">
                    {pnl_sign}{p['return_pct']:.2f}%<br>
                    <span style="font-size:11px; opacity:0.85;">({prefix}{p['unrealized_pnl']:,.0f})</span>
                </td>
                <td class="text-right font-mono desktop-only" style="color: {'#f87171' if p['drawdown_from_peak'] <= -8 else '#94a3b8'};">
                    {p['drawdown_from_peak']:.1f}%
                </td>
                <td class="text-center">{badge_html}</td>
            </tr>
            """
            rows.append(row)

        table_html = f"""
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>持股標的</th>
                        <th class="text-right">買進成本</th>
                        <th class="text-right">現價</th>
                        <th class="text-right">未實現損益</th>
                        <th class="text-right desktop-only">自高點回檔</th>
                        <th class="text-center">狀態 / 風控</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
        return table_html
