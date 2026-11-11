"""
LINE 推播快速測試腳本
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.notifier import LineNotifier

def main():
    print("=" * 60)
    print("📲 【LINE 推播測試程式】")
    print("=" * 60)

    notifier = LineNotifier()
    if not notifier.channel_access_token or not notifier.user_id:
        print("❌ 未偵測到 LINE 設定！")
        print("請在專案根目錄建立 .env 檔案，並填入：")
        print("LINE_CHANNEL_ACCESS_TOKEN=你的Token")
        print("LINE_USER_ID=你的UserID")
        return

    test_msg = (
        "🎉 恭喜！您的【TQA 科技量化秘書】已成功與 LINE 綁定！\n"
        "從現在起，每天早上 08:45 與晚上 21:10 都會在此接收「大戶投操作建議」！"
    )

    print("🚀 正在發送測試訊息至您的 LINE...")
    success = notifier.send_message(test_msg)
    if success:
        print("🎉 測試成功！請確認您的手機 LINE 是否已收到通知！")

if __name__ == "__main__":
    main()
