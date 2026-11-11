"""
LINE 推播通知模組
"""
import os
import requests
from typing import Optional
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

class LineNotifier:
    def __init__(self, channel_access_token: Optional[str] = None, user_id: Optional[str] = None):
        self.channel_access_token = channel_access_token or os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.user_id = user_id or os.getenv("LINE_USER_ID")
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send_message(self, text: str) -> bool:
        if not self.channel_access_token or not self.user_id:
            print("[LINE] 未設定金鑰，略過發送。")
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}"
        }
        
        payload = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }

        try:
            resp = requests.post(self.api_url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                print("[LINE] 推播已送達手機。")
                return True
            else:
                print(f"[LINE] 發送失敗: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            print(f"[LINE] 發送異常: {e}")
            return False

    @classmethod
    def format_tw_morning_message(cls, rank_df: pd.DataFrame) -> str:
        """
        台股盤前操作指引 (08:30)
        """
        if rank_df is None or rank_df.empty:
            return "【TQA 台股操作指引】無可用的市場數據。"

        data_date = rank_df.iloc[0].get("data_date", "")
        # 前 3 名中至少 2 檔站上 50MA 視為多頭攻擊
        is_bull_attack = bool(rank_df.head(3)["above_50sma"].sum() >= 2) if "above_50sma" in rank_df.columns else False
        
        # 推薦列表優先顯示 above_50sma == True 的前 3 強
        bull_candidates = rank_df[rank_df["above_50sma"] == True] if "above_50sma" in rank_df.columns else pd.DataFrame()
        if len(bull_candidates) >= 3:
            display_df = bull_candidates.head(3)
        else:
            remaining = rank_df[~rank_df.index.isin(bull_candidates.index)] if "above_50sma" in rank_df.columns else rank_df
            display_df = pd.concat([bull_candidates, remaining]).head(3)
        
        lines = [
            f"【TQA 台股操作指引】",
            f"數據基準：{data_date} 收盤",
        ]

        if not is_bull_attack:
            lines.extend([
                "市場狀態：防禦觀望（多數標的未站上 50MA）",
                "操作建議：維持 100% 現金，暫不建倉。",
                "--- 觀察名單 ---"
            ])
            for rank_idx, (_, row) in enumerate(display_df.iterrows(), start=1):
                ticker = str(row["ticker"]).replace(".TW", "").replace(".TWO", "")
                name = row.get("name", ticker)
                price = row.get("price", 0.0)
                score = row.get("score", 0.0)
                status_str = " (⚠️ 跌破50MA)" if not row.get("above_50sma", False) else ""
                lines.append(f"{rank_idx}. {name}({ticker}) {price:,.1f} | 評分 {score:+.1f}{status_str}")
        else:
            lines.extend([
                "市場狀態：多頭攻擊（標的站上 50MA）",
                "操作建議（大戶投現貨/零股）："
            ])
            for rank_idx, (_, row) in enumerate(display_df.iterrows(), start=1):
                ticker = str(row["ticker"]).replace(".TW", "").replace(".TWO", "")
                name = row.get("name", ticker)
                price = row.get("price", 0.0)
                score = row.get("score", 0.0)
                act = "買進/續抱" if row.get("above_50sma", False) else "觀望"
                lines.append(f"{rank_idx}. {name}({ticker}) {price:,.1f} | 評分 {score:+.1f} | {act}")

        lines.extend([
            "風控機制：跌破 50MA 或波段拉回 8% 執行出場。"
        ])
        return "\n".join(lines)

    @classmethod
    def format_us_evening_message(cls, rank_df: pd.DataFrame) -> str:
        """
        美股盤前操作指引 (21:00)
        """
        if rank_df is None or rank_df.empty:
            return "【TQA 美股操作指引】無可用的市場數據。"

        data_date = rank_df.iloc[0].get("data_date", "")
        # 前 3 名中至少 2 檔站上 50MA 視為多頭攻擊
        is_bull_attack = bool(rank_df.head(3)["above_50sma"].sum() >= 2) if "above_50sma" in rank_df.columns else False

        # 推薦列表優先顯示 above_50sma == True 的前 3 強
        bull_candidates = rank_df[rank_df["above_50sma"] == True] if "above_50sma" in rank_df.columns else pd.DataFrame()
        if len(bull_candidates) >= 3:
            display_df = bull_candidates.head(3)
        else:
            remaining = rank_df[~rank_df.index.isin(bull_candidates.index)] if "above_50sma" in rank_df.columns else rank_df
            display_df = pd.concat([bull_candidates, remaining]).head(3)

        lines = [
            f"【TQA 美股操作指引】",
            f"數據基準：{data_date} 收盤",
        ]

        if not is_bull_attack:
            lines.extend([
                "市場狀態：防禦觀望（主要標的跌破 50MA）",
                "操作建議：維持現金，暫不開倉。",
                "--- 觀察名單 ---"
            ])
            for rank_idx, (_, row) in enumerate(display_df.iterrows(), start=1):
                ticker = row["ticker"]
                name = row.get("name", ticker)
                price = row.get("price", 0.0)
                score = row.get("score", 0.0)
                status_str = " (⚠️ 跌破50MA)" if not row.get("above_50sma", False) else ""
                lines.append(f"{rank_idx}. {ticker} ${price:,.2f} | 評分 {score:+.1f}{status_str}")
        else:
            lines.extend([
                "市場狀態：多頭攻擊（標的站穩 50MA）",
                "操作建議（大戶投複委託）："
            ])
            for rank_idx, (_, row) in enumerate(display_df.iterrows(), start=1):
                ticker = row["ticker"]
                name = row.get("name", ticker)
                price = row.get("price", 0.0)
                score = row.get("score", 0.0)
                act = "買進/續抱" if row.get("above_50sma", False) else "觀望"
                lines.append(f"{rank_idx}. {ticker} ${price:,.2f} | 評分 {score:+.1f} | {act}")

        lines.extend([
            "風控機制：跌破 50MA 或高點拉回 8% 執行出場。"
        ])
        return "\n".join(lines)
