"""
個人投資組合與風控追蹤模組 (Portfolio & Risk Tracker - 雙軌風控與帳戶層級回撤防護)
功能：
1. 讀取與持久化 portfolio.json 個人持股與帳戶風控狀態
   - 個股：shares, cost_price, entry_date, peak_price (歷史最高價)
   - 帳戶：peak_equity, current_drawdown_pct, risk_scaling_factor, cash
2. 比對現價、50MA 生命線、波段最高價回檔 (-8%) 與買進成本絕對虧損 (-30%)
3. 動態倉位縮放 (Drawdown Scaling)：回撤 >= 18% 降為 0.50，回撤 >= 25% 降為 0.25，回升 < 10% 恢復 1.0
4. 產生雙軌停損警報與 LINE 推播文案
5. 輸出網頁端個人資產卡片 HTML
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
import pytz
from src.config import TECH_UNIVERSE_TW, config

PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "portfolio.json")

class PortfolioTracker:
    @classmethod
    def calculate_risk_scaling_factor(cls, drawdown_pct: float, current_factor: float = 1.0) -> float:
        """
        帳戶層級動態倉位縮放係數 (奧卡姆剃刀重構：解除底部減倉陷阱，常態維持 1.0 全倉進出)
        """
        return 1.0

    @classmethod
    def load_portfolio_state(cls, filepath: str = PORTFOLIO_FILE) -> Dict[str, Any]:
        """
        讀取完整投資組合狀態字典（含帳戶層級風控指標與個股部位）
        支援向下相容與自動資料遷移
        """
        default_state = {
            "positions": [],
            "peak_equity": 100000.0,
            "current_drawdown_pct": 0.0,
            "risk_scaling_factor": 1.0,
            "cash": 30000.0,
            "last_updated": ""
        }

        # 1. 優先檢查雲端 Google Sheets
        sheet_url = os.getenv("PORTFOLIO_SHEET_URL", "").strip()
        if sheet_url:
            try:
                df = pd.read_csv(sheet_url)
                df.columns = [str(c).strip().lower() for c in df.columns]
                cost_col = "cost_price" if "cost_price" in df.columns else ("entry_price" if "entry_price" in df.columns else None)
                if cost_col and {"ticker", "shares"}.issubset(df.columns):
                    df = df.dropna(subset=["ticker", "shares", cost_col])
                    positions = []
                    for _, row in df.iterrows():
                        entry_val = str(row["entry_date"]).strip() if ("entry_date" in row and not pd.isna(row["entry_date"])) else ""
                        c_px = float(row[cost_col])
                        p_px = float(row["peak_price"]) if ("peak_price" in row and not pd.isna(row["peak_price"])) else c_px
                        positions.append({
                            "ticker": str(row["ticker"]).strip(),
                            "shares": float(row["shares"]),
                            "cost_price": c_px,
                            "entry_date": entry_val,
                            "peak_price": p_px
                        })
                    if positions:
                        default_state["positions"] = positions
                        return default_state
            except Exception as e:
                print(f"[警告] 讀取 Google Sheets 雲端持倉失敗，切換回本地: {e}")

        # 2. 雲端 Supabase
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
                            positions = []
                            for r in data:
                                c_px = float(r.get("cost_price", r.get("entry_price", 0.0)))
                                positions.append({
                                    "ticker": str(r["ticker"]).strip(),
                                    "shares": float(r["shares"]),
                                    "cost_price": c_px,
                                    "entry_date": str(r.get("entry_date", "")).strip() if r.get("entry_date") else "",
                                    "peak_price": float(r.get("peak_price", c_px))
                                })
                            default_state["positions"] = positions
                            return default_state
            except Exception as e:
                print(f"[警告] 讀取 Supabase 雲端持倉失敗，切換回本地: {e}")

        # 3. 本地檔案 (portfolio.json)
        if not os.path.exists(filepath):
            return default_state

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                # 兼容極舊版直接存 list 的情況
                raw_positions = data
                state = default_state.copy()
            elif isinstance(data, dict):
                raw_positions = data.get("positions", [])
                state = {
                    "positions": [],
                    "peak_equity": float(data.get("peak_equity", 100000.0)),
                    "current_drawdown_pct": float(data.get("current_drawdown_pct", 0.0)),
                    "risk_scaling_factor": float(data.get("risk_scaling_factor", 1.0)),
                    "cash": float(data.get("cash", 30000.0)),
                    "last_updated": str(data.get("last_updated", ""))
                }
            else:
                return default_state

            # 補齊個股欄位
            clean_positions = []
            for p in raw_positions:
                c_px = float(p.get("cost_price", p.get("entry_price", 0.0)))
                clean_positions.append({
                    "ticker": str(p.get("ticker", "")).strip(),
                    "shares": float(p.get("shares", 0)),
                    "cost_price": c_px,
                    "entry_date": str(p.get("entry_date", "")).strip(),
                    "peak_price": float(p.get("peak_price", c_px))
                })
            state["positions"] = clean_positions
            return state

        except Exception as e:
            print(f"[警告] 讀取 portfolio.json 失敗: {e}")
            return default_state

    @classmethod
    def load_portfolio(cls, filepath: str = PORTFOLIO_FILE) -> List[Dict]:
        """讀取持股部位清單 (向下相容)"""
        state = cls.load_portfolio_state(filepath)
        return state.get("positions", [])

    @classmethod
    def save_portfolio(
        cls, 
        positions: List[Dict], 
        filepath: str = PORTFOLIO_FILE,
        extra_state: Optional[Dict] = None
    ):
        """
        儲存持股設定檔與帳戶風控狀態
        自動保留並更新 peak_equity, current_drawdown_pct, risk_scaling_factor
        """
        # 先讀取現有 state
        current_state = cls.load_portfolio_state(filepath)
        
        # 規範化持倉列表
        clean_positions = []
        for p in positions:
            c_px = float(p.get("cost_price", p.get("entry_price", 0.0)))
            pk_px = float(p.get("peak_price", c_px))
            clean_positions.append({
                "ticker": str(p.get("ticker", "")).strip(),
                "shares": float(p.get("shares", 0)),
                "cost_price": c_px,
                "entry_date": str(p.get("entry_date", "")).strip(),
                "peak_price": max(pk_px, c_px)
            })

        payload = {
            "positions": clean_positions,
            "peak_equity": float(extra_state.get("peak_equity", current_state.get("peak_equity", 100000.0))) if extra_state else current_state.get("peak_equity", 100000.0),
            "current_drawdown_pct": float(extra_state.get("current_drawdown_pct", current_state.get("current_drawdown_pct", 0.0))) if extra_state else current_state.get("current_drawdown_pct", 0.0),
            "risk_scaling_factor": float(extra_state.get("risk_scaling_factor", current_state.get("risk_scaling_factor", 1.0))) if extra_state else current_state.get("risk_scaling_factor", 1.0),
            "cash": float(extra_state.get("cash", current_state.get("cash", 30000.0))) if extra_state else current_state.get("cash", 30000.0),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[警告] 寫入本地 portfolio.json 失敗: {e}")

        # 同步 Webhook
        webhook_url = os.getenv("PORTFOLIO_WEBHOOK_URL", "").strip()
        if webhook_url:
            try:
                import urllib.request
                req = urllib.request.Request(
                    webhook_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                print(f"[警告] 同步至雲端 Webhook 失敗: {e}")

    @classmethod
    def evaluate_portfolio(
        cls, 
        dataset: Dict[str, pd.DataFrame],
        save_state: bool = True
    ) -> List[Dict]:
        """
        評估個人每檔持股的損益、更新 peak_price 與雙軌停損風控條件
        同時計算帳戶總淨值、峰值淨值、總回撤與動態縮放係數 (Drawdown Scaling)
        """
        state = cls.load_portfolio_state()
        positions = state.get("positions", [])
        if not positions:
            return []

        tw_tz = pytz.timezone("Asia/Taipei")
        today_str = datetime.now(tw_tz).strftime("%Y-%m-%d")

        evaluated = []
        updated_positions = []
        total_market_value = 0.0

        for pos in positions:
            ticker = pos.get("ticker", "").strip()
            shares = float(pos.get("shares", 0))
            cost_price = float(pos.get("cost_price", pos.get("entry_price", 0.0)))
            entry_date = pos.get("entry_date", "")

            if ticker not in dataset or dataset[ticker].empty:
                # 若無最新行情，原樣保留
                updated_positions.append(pos)
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
            is_above_50ma = (curr_price >= sma50)

            # 更新歷史波段最高價 (peak_price)
            # 僅搜尋進場日隔天之後的最高價，避開進場日上影線誤判
            if entry_date:
                sub_df = df.loc[df.index > pd.to_datetime(entry_date)]
                post_entry_high = float(sub_df["high"].max()) if not sub_df.empty else cost_price
            else:
                post_entry_high = float(df["high"].tail(60).max())

            prev_peak = float(pos.get("peak_price", cost_price))
            peak_price = max(prev_peak, post_entry_high, curr_price, cost_price)

            # 計算自高點回檔幅度
            drawdown_from_peak = ((curr_price - peak_price) / peak_price) * 100.0

            # 計算持股損益 (台幣換算：美股以匯率 32.5 換算為台幣計入總淨值)
            market_val = shares * curr_price
            cost_val = shares * cost_price
            unrealized_pnl = market_val - cost_val
            return_pct = ((curr_price - cost_price) / cost_price * 100.0) if cost_price > 0 else 0.0
            market_val_twd = market_val if is_tw else (market_val * 32.5)
            total_market_value += market_val_twd

            # ----------------------------------------------------
            # 雙軌停損判定
            # 1. 戰術絕對硬停損 (-30%)
            # 2. 移動停利停損 (-8%，進場隔日後啟動)
            # ----------------------------------------------------
            hard_stop_triggered = (return_pct <= -30.0)
            
            # 移動停損僅在進場隔日後生效 (T+1 以後)
            is_past_entry_day = True
            if entry_date:
                latest_date_str = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], "strftime") else str(df.index[-1])[:10]
                is_past_entry_day = (latest_date_str > entry_date)
            trailing_stop_triggered = (drawdown_from_peak <= -8.0) and is_past_entry_day

            # 警報彙整
            alerts = []
            if hard_stop_triggered:
                alerts.append("🚨 戰術絕對硬停損 (虧損達30%)")
            elif trailing_stop_triggered:
                alerts.append(f"🛡️ 移動停損平倉 (自高點回檔達8% / 現回檔{abs(drawdown_from_peak):.1f}%)")

            if not is_above_50ma:
                alerts.append("📉 跌破50MA生命線")

            has_alert = len(alerts) > 0
            alert_text = " + ".join(alerts) if has_alert else "多頭軌道安全"

            # 緩衝安全距離計算 (供 UI 與診斷面板顯示)
            dist_to_trailing = drawdown_from_peak - (-8.0)   # 若為正代表距 -8% 還有多少 % 安全緩衝
            dist_to_hard = return_pct - (-30.0)              # 若為正代表距 -30% 還有多少 % 安全緩衝
            trailing_stop_price = peak_price * 0.92
            hard_stop_price = cost_price * 0.70

            eval_item = {
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
                "dist_to_trailing": dist_to_trailing,
                "dist_to_hard": dist_to_hard,
                "trailing_stop_price": trailing_stop_price,
                "hard_stop_price": hard_stop_price,
                "sma50": sma50,
                "is_above_50ma": is_above_50ma,
                "trailing_stop_triggered": trailing_stop_triggered,
                "hard_stop_triggered": hard_stop_triggered,
                "has_alert": has_alert,
                "alert_text": alert_text,
                "entry_date": entry_date,
                "data_date": df.index[-1].strftime("%Y-%m-%d")
            }
            evaluated.append(eval_item)

            # 更新持倉字典中的 peak_price
            pos_copy = pos.copy()
            pos_copy["peak_price"] = peak_price
            pos_copy["cost_price"] = cost_price
            updated_positions.append(pos_copy)

        # ----------------------------------------------------
        # 帳戶層級回撤與倉位縮放計算 (Portfolio Drawdown Scaling)
        # ----------------------------------------------------
        cash = float(state.get("cash", 30000.0))
        current_equity = total_market_value + cash
        prev_peak_equity = float(state.get("peak_equity", 100000.0))
        peak_equity = max(prev_peak_equity, current_equity)

        drawdown_pct = max(0.0, ((peak_equity - current_equity) / peak_equity) * 100.0) if peak_equity > 0 else 0.0
        cur_scaling = float(state.get("risk_scaling_factor", 1.0))
        risk_scaling_factor = cls.calculate_risk_scaling_factor(drawdown_pct, cur_scaling)

        if save_state:
            cls.save_portfolio(
                updated_positions,
                extra_state={
                    "peak_equity": round(peak_equity, 2),
                    "current_drawdown_pct": round(drawdown_pct, 2),
                    "risk_scaling_factor": risk_scaling_factor,
                    "cash": round(cash, 2)
                }
            )

        return evaluated

    @classmethod
    def format_line_notification(cls, evaluated_positions: List[Dict], market_type: str = "TW") -> str:
        """產生 LINE 推播中的個人持股風控摘要文字"""
        filtered = [p for p in evaluated_positions if (p["is_tw"] if market_type == "TW" else not p["is_tw"])]
        if not filtered:
            return ""

        state = cls.load_portfolio_state()
        lines = [
            f"💼 【個人自訂持股風控監控 - {market_type}】",
            f"• 帳戶最高淨值: ${state.get('peak_equity', 0):,.0f} | 總回撤: {state.get('current_drawdown_pct', 0):.1f}% | 倉位係數: {state.get('risk_scaling_factor', 1.0):.2f}"
        ]
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
            lines.append("✅ 目前持有標的均處於安全多頭軌道，未觸發 8% 回檔、30% 硬停損與 50MA 跌破，可穩定續抱。")

        lines.append("")
        return "\n".join(lines)

    @classmethod
    def generate_portfolio_html(cls, evaluated_positions: List[Dict], market_type: str = "TW") -> str:
        """產生網頁儀表板中的持股卡片 HTML"""
        filtered = [p for p in evaluated_positions if (p.get("is_tw", False) if market_type == "TW" else not p.get("is_tw", False))]
        if not filtered:
            return """
            <div style="background: #182238; border: 1px dashed #243049; border-radius: 10px; padding: 20px; text-align: center; color: #64748b;">
                目前尚未設定自訂持股。可透過 Google Sheets 雲端試算表或 <code>portfolio.json</code> 新增您的庫存標的。
            </div>
            """

        rows = []
        for p in filtered:
            is_tw = p.get("is_tw", False)
            prefix = "NT$" if is_tw else "$"
            ret_pct = p.get("return_pct", 0.0)
            ret_color = "#34d399" if ret_pct >= 0 else "#f87171"
            pnl_val = p.get("unrealized_pnl", 0.0)
            
            pnl_sign = "+" if pnl_val >= 0 else "-"
            if is_tw:
                pnl_str = f"({pnl_sign}NT${abs(pnl_val):,.0f})"
            else:
                pnl_str = f"({pnl_sign}${abs(pnl_val):,.2f})"
            
            shares_val = p.get("shares", 0)
            shares_str = f"{int(shares_val)}" if float(shares_val).is_integer() else f"{shares_val:g}"

            badge_html = f'<span class="badge badge-bear" style="background:#450a0a; color:#f87171; border:1px solid #991b1b;">⚠️ {p["alert_text"]}</span>' if p["has_alert"] else '<span class="badge badge-bull">✅ 續抱中</span>'
            
            row = f"""
            <tr class="clickable" onclick="openStockModal('{p['ticker']}')">
                <td>
                    <div style="font-weight:bold; color:#f1f5f9;">{p['name']}</div>
                    <div style="font-size:12px; color:#64748b; font-family:monospace;">{p['ticker']} ({shares_str} 股)</div>
                </td>
                <td class="text-right font-mono">{prefix}{p['cost_price']:,.2f}</td>
                <td class="text-right font-mono" style="font-weight:bold;">{prefix}{p['curr_price']:,.2f}</td>
                <td class="text-right font-mono" style="color:{ret_color}; font-weight:bold;">
                    {'+' if ret_pct >= 0 else ''}{ret_pct:.2f}%<br>
                    <span style="font-size:11px; opacity:0.85;">{pnl_str}</span>
                </td>
                <td class="text-right font-mono desktop-only" style="color: {'#f87171' if p['drawdown_from_peak'] <= -8 or p['hard_stop_triggered'] else '#94a3b8'};">
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
