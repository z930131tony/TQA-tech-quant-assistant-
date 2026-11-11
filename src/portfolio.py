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
    @classmethod
    def load_portfolio(cls, filepath: str = PORTFOLIO_FILE) -> List[Dict]:
        """
        讀取個人持股設定檔
        優先級：
        1. Google Sheets CSV (環境變數 PORTFOLIO_SHEET_URL)
        2. Supabase REST API (環境變數 SUPABASE_URL + SUPABASE_KEY)
        3. 本地檔案 (portfolio.json)
        """
        # 1. Google Sheets 雲端試算表讀取 (手機端隨時開 App 修改)
        sheet_url = os.getenv("PORTFOLIO_SHEET_URL", "").strip()
        if sheet_url:
            try:
                df = pd.read_csv(sheet_url)
                df.columns = [str(c).strip().lower() for c in df.columns]
                if {"ticker", "shares", "cost_price"}.issubset(df.columns):
                    df = df.dropna(subset=["ticker", "shares", "cost_price"])
                    positions = []
                    for _, row in df.iterrows():
                        entry_val = ""
                        if "entry_date" in row and not pd.isna(row["entry_date"]):
                            entry_val = str(row["entry_date"]).strip()
                        positions.append({
                            "ticker": str(row["ticker"]).strip(),
                            "shares": float(row["shares"]),
                            "cost_price": float(row["cost_price"]),
                            "entry_date": entry_val
                        })
                    if positions:
                        return positions
            except Exception as e:
                print(f"[警告] 讀取 Google Sheets 雲端持倉失敗，切換回本地: {e}")

        # 2. Supabase 雲端資料庫讀取
        supabase_url = os.getenv("SUPABASE_URL", "").strip()
        supabase_key = os.getenv("SUPABASE_KEY", "").strip()
        if supabase_url and supabase_key:
            try:
                import urllib.request
                endpoint = f"{supabase_url.rstrip('/')}/rest/v1/positions?select=*"
                req = urllib.request.Request(endpoint, headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}"
                })
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if isinstance(data, list) and len(data) > 0:
                            return [{
                                "ticker": str(r["ticker"]).strip(),
                                "shares": float(r["shares"]),
                                "cost_price": float(r["cost_price"]),
                                "entry_date": str(r.get("entry_date", "")).strip() if r.get("entry_date") else ""
                            } for r in data]
            except Exception as e:
                print(f"[警告] 讀取 Supabase 雲端持倉失敗，切換回本地: {e}")

        # 3. 本地回退 (portfolio.json)
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("positions", [])
        except Exception as e:
            print(f"[警告] 讀取 portfolio.json 失敗: {e}")
            return []

    @classmethod
    def save_portfolio(cls, positions: List[Dict], filepath: str = PORTFOLIO_FILE):
        """儲存個人持股設定檔 (同時寫入本地快取，若有 Webhook 則同步雲端)"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"positions": positions}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[警告] 寫入本地 portfolio.json 失敗: {e}")

        # 雲端 Webhook 同步 (選用，例如 Google Apps Script 或 自建 API)
        webhook_url = os.getenv("PORTFOLIO_WEBHOOK_URL", "").strip()
        if webhook_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    webhook_url,
                    data=json.dumps({"positions": positions}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                print(f"[警告] 同步至雲端 Webhook 失敗: {e}")

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
                目前尚未設定自訂持股。可透過 Google Sheets 雲端試算表或 <code>portfolio.json</code> 同步您的庫存標的。
            </div>
            """

        rows = []
        for p in filtered:
            is_tw = p.get("is_tw", False)
            prefix = "NT$" if is_tw else "$"
            ret_pct = p.get("return_pct", 0.0)
            ret_color = "#34d399" if ret_pct >= 0 else "#f87171"
            pnl_val = p.get("unrealized_pnl", 0.0)
            
            # 美股未實現損益金額保留小數點後兩位 (例如 +$13.14 / -$11.65)，台股維持整數顯示 (例如 +NT$5,000 / -NT$5,000)
            pnl_sign = "+" if pnl_val >= 0 else "-"
            if is_tw:
                pnl_str = f"({pnl_sign}NT${abs(pnl_val):,.0f})"
            else:
                pnl_str = f"({pnl_sign}${abs(pnl_val):,.2f})"
            
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
                    {'+' if ret_pct >= 0 else ''}{ret_pct:.2f}%<br>
                    <span style="font-size:11px; opacity:0.85;">{pnl_str}</span>
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
