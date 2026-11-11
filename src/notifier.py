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
        data_date = rank_df.iloc[0].get("data_date", "")
        top_above_50 = rank_df.iloc[0]["above_50sma"]
        
        lines = [
            f"【TQA 台股操作指引】",
            f"數據基準：{data_date} 收盤",
        ]

        if not top_above_50:
            lines.extend([
                "市場狀態：防禦觀望（追蹤標的均低於 50MA）",
                "操作建議：維持 100% 現金，暫不建倉。",
                "--- 觀察名單 ---"
            ])
            for idx, row in rank_df.iloc[:3].iterrows():
                ticker = row["ticker"].replace(".TW", "")
                name = row["name"]
                price = row["price"]
                score = row["score"]
                lines.append(f"{idx+1}. {name}({ticker}) {price:,.1f} | 評分 {score:+.1f}")
        else:
            lines.extend([
                "市場狀態：多頭攻擊（標的站上 50MA）",
                "操作建議（大戶投現貨/零股）："
            ])
            for idx, row in rank_df.iloc[:3].iterrows():
                ticker = row["ticker"].replace(".TW", "")
                name = row["name"]
                price = row["price"]
                score = row["score"]
                act = "買進/續抱" if row["above_50sma"] else "觀望"
                lines.append(f"{idx+1}. {name}({ticker}) {price:,.1f} | 評分 {score:+.1f} | {act}")

        lines.extend([
            "風控機制：跌破 50MA 或波段拉回 8% 執行出場。"
        ])
        return "\n".join(lines)

    @classmethod
    def format_us_evening_message(cls, rank_df: pd.DataFrame) -> str:
        """
        美股盤前操作指引 (21:00)
        """
        data_date = rank_df.iloc[0].get("data_date", "")
        top_above_50 = rank_df.iloc[0]["above_50sma"]

        lines = [
            f"【TQA 美股操作指引】",
            f"數據基準：{data_date} 收盤",
        ]

        if not top_above_50:
            lines.extend([
                "市場狀態：防禦觀望（主要標的跌破 50MA）",
                "操作建議：維持現金，暫不開倉。",
                "--- 觀察名單 ---"
            ])
            for idx, row in rank_df.iloc[:3].iterrows():
                ticker = row["ticker"]
                name = row["name"]
                price = row["price"]
                score = row["score"]
                lines.append(f"{idx+1}. {ticker} ${price:,.2f} | 評分 {score:+.1f}")
        else:
            lines.extend([
                "市場狀態：多頭攻擊（標的站穩 50MA）",
                "操作建議（大戶投複委託）："
            ])
            for idx, row in rank_df.iloc[:3].iterrows():
                ticker = row["ticker"]
                name = row["name"]
                price = row["price"]
                score = row["score"]
                act = "買進/續抱" if row["above_50sma"] else "觀望"
                lines.append(f"{idx+1}. {ticker} ${price:,.2f} | 評分 {score:+.1f} | {act}")

        lines.extend([
            "風控機制：跌破 50MA 或高點拉回 8% 執行出場。"
        ])
        return "\n".join(lines)
