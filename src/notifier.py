"""
LINE 推播發送模組 (使用 LINE Messaging API Push Message)
"""
import os
import requests
from typing import Optional, List
import pandas as pd
from dotenv import load_dotenv

# 載入 .env 環境變數
load_dotenv()

class LineNotifier:
    def __init__(self, channel_access_token: Optional[str] = None, user_id: Optional[str] = None):
        self.channel_access_token = channel_access_token or os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.user_id = user_id or os.getenv("LINE_USER_ID")
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send_message(self, text: str) -> bool:
        """
        發送單則純文字推播訊息至個人的 LINE
        """
        if not self.channel_access_token or not self.user_id:
            print("⚠️ [LINE 推播未啟用] 未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID。")
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
                print("✅ [LINE] 訊息已成功推播至您的手機！")
                return True
            else:
                print(f"❌ [LINE 推播失敗] 狀態碼: {resp.status_code}, 回應: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ [LINE 網路異常] {e}")
            return False

    @classmethod
    def format_tw_morning_message(cls, rank_df: pd.DataFrame) -> str:
        """
        格式化晨間台股推播訊息 (08:45 發送)
        """
        top_above_50 = rank_df.iloc[0]["above_50sma"]
        state_title = "🟢 積極進攻 (多頭格局)" if top_above_50 else "🛡️ 防禦避險 (觀望現金)"
        
        lines = [
            "🔔【TQA 科技量化秘書】台股晨間操作指引",
            f"📅 建議時間：開盤前 (09:00 前)",
            f"📊 市場狀態：{state_title}",
            "━━━━━━━━━━━━━━━━━━",
            "🎯【今日大戶投 (台股) 建議】:"
        ]
        
        top3 = rank_df.iloc[:3]
        for idx, row in top3.iterrows():
            ticker = row["ticker"].replace(".TW", "")
            name = row["name"]
            price = row["price"]
            score = row["score"]
            status = "🟢 建議配置 (盤中零股/整股)" if row["above_50sma"] else "⚪ 動能轉弱 (暫不開倉)"
            lines.append(f"#{idx+1} {name} ({ticker})")
            lines.append(f"   最新價: NT${price:,.1f} | 評分: {score:+.1f}")
            lines.append(f"   動作: {status}")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━",
            "💡 提示：請開啟「大戶投 APP ➔ 台股」依訊號檢視庫存。"
        ])
        return "\n".join(lines)

    @classmethod
    def format_us_evening_message(cls, rank_df: pd.DataFrame) -> str:
        """
        格式化晚間美股推播訊息 (21:10 發送)
        """
        top_above_50 = rank_df.iloc[0]["above_50sma"]
        state_title = "🟢 積極進攻 (多頭格局)" if top_above_50 else "🛡️ 防禦避險 (觀望現金)"
        
        lines = [
            "🔔【TQA 科技量化秘書】美股今晚操作指引",
            f"📅 建議時間：開盤前 (21:30 前)",
            f"📊 市場狀態：{state_title}",
            "━━━━━━━━━━━━━━━━━━",
            "🎯【今晚大戶投 (複委託) 建議】:"
        ]
        
        top3 = rank_df.iloc[:3]
        for idx, row in top3.iterrows():
            ticker = row["ticker"]
            name = row["name"]
            price = row["price"]
            score = row["score"]
            status = "🟢 建議配置 (複委託碎股)" if row["above_50sma"] else "⚪ 動能轉弱 (觀望/撤出)"
            lines.append(f"#{idx+1} {name} ({ticker})")
            lines.append(f"   最新價: ${price:,.2f} | 評分: {score:+.1f}")
            lines.append(f"   動作: {status}")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━",
            "💡 提示：請開啟「大戶投 APP ➔ 複委託」檢視部位。"
        ])
        return "\n".join(lines)
