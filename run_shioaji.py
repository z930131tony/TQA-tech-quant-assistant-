"""
永豐金證券 Shioaji API 啟動與連線檢測腳本
功能：
1. 自動讀取 .env 中的 API Key、Secret Key、身分證字號與憑證
2. 連線登入永豐金證券 (支援模擬環境與正式環境切換)
3. 啟用 CA 憑證 (實盤下單與查詢專用)
4. 查詢證券帳戶基本資訊與即時庫存部位
5. 測試台積電 (2330) 即時五檔報價與盤中最新成交
"""
import os
import sys
import io
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

load_dotenv()

try:
    import shioaji as sj
except ImportError:
    print("❌ 尚未安裝 shioaji 套件，請先執行: py -m pip install -r requirements-local.txt")
    sys.exit(1)

def main():
    print("=" * 65)
    print("🚀 【永豐金證券 Shioaji API 啟動器】")
    print("=" * 65)

    api_key = os.getenv("SHIOAJI_API_KEY", "").strip()
    secret_key = os.getenv("SHIOAJI_SECRET_KEY", "").strip()
    person_id = os.getenv("SHIOAJI_PERSON_ID", "").strip()
    cert_path = os.getenv("SHIOAJI_CERT_PATH", "").strip()
    cert_pass = os.getenv("SHIOAJI_CERT_PASSWORD", "").strip()
    sim_str = os.getenv("SHIOAJI_SIMULATION", "true").lower()
    simulation = (sim_str == "true")

    if not api_key or not secret_key:
        print("❌ 找不到 SHIOAJI_API_KEY 或 SHIOAJI_SECRET_KEY，請確認 .env 檔案設定！")
        return

    mode_name = "🧪 模擬交易環境 (Simulation Mode)" if simulation else "💼 正式實盤環境 (Production Mode)"
    print(f"📡 連線模式: {mode_name}")
    print(f"🔑 API Key: {api_key[:6]}******")

    api = sj.Shioaji(simulation=simulation)

    print("\n[步驟 1/4] 正在進行 API 登入...")
    try:
        accounts = api.login(api_key=api_key, secret_key=secret_key)
        print("  ✅ 登入成功！已連線永豐金證券主機。")
        print("  📋 綁定帳號列表:")
        for acc in accounts:
            acc_type = getattr(acc.account_type, "name", str(acc.account_type))
            uname = getattr(acc, "username", "--")
            print(f"    • 帳號: {acc.account_id} ({acc_type}) | 戶名: {uname}")
    except Exception as e:
        print(f"  ❌ 登入失敗: {e}")
        return

    print("\n[步驟 2/4] 檢查 CA 下單憑證...")
    if cert_path and os.path.exists(cert_path) and cert_pass and person_id:
        try:
            api.activate_ca(ca_path=cert_path, ca_passwd=cert_pass, person_id=person_id)
            print("  ✅ CA 憑證啟用成功！具備委託下單權限。")
        except Exception as ca_err:
            print(f"  ⚠️ CA 憑證啟用失敗 ({ca_err})。在模擬模式下不影響一般查詢。")
    else:
        print("  ℹ️ 未設定或找不到憑證檔案 (sinopac.pfx)，維持唯讀查詢模式。")

    print("\n[步驟 3/4] 查詢現有台股庫存部位 (含零股與整張)...")
    try:
        unit_val = getattr(sj, "Unit", getattr(sj, "constant", None)).Share if hasattr(sj, "Unit") else sj.constant.Unit.Share
        positions = api.list_positions(api.stock_account, unit=unit_val)
        if positions:
            print(f"  📦 當前庫存部位共 {len(positions)} 檔:")
            for p in positions:
                code = getattr(p, "code", "--")
                qty = getattr(p, "quantity", 0)
                price = getattr(p, "price", 0.0)
                pnl = getattr(p, "pnl", 0.0)
                print(f"    • 代碼: {code:<8} | 股數: {qty:<6} | 成本價: NT$ {price:,.2f} | 損益: NT$ {pnl:+,.0f}")
        else:
            print("  ℹ️ 目前帳戶內無持倉部位。")
    except Exception as pos_err:
        print(f"  ⚠️ 查詢持倉異常: {pos_err}")

    print("\n[步驟 4/4] 測試即時行情串接 (台積電 2330)...")
    try:
        contract_2330 = api.Contracts.Stocks["2330"]
        snapshot = api.snapshots([contract_2330])
        if snapshot:
            snap = snapshot[0]
            close_px = getattr(snap, "close", 0.0)
            high_px = getattr(snap, "high", 0.0)
            low_px = getattr(snap, "low", 0.0)
            vol = getattr(snap, "volume", 0)
            print(f"  📊 台積電 (2330) 即時快照:")
            print(f"    • 最新成交價: NT$ {close_px:,.2f}")
            print(f"    • 今日最高/最低: NT$ {high_px:,.2f} / NT$ {low_px:,.2f}")
            print(f"    • 今日累積成交量: {vol:,} 股")
    except Exception as quote_err:
        print(f"  ℹ️ 即時報價串接測試略過 ({quote_err})")

    print("\n" + "=" * 65)
    print("🎉 Shioaji 連線啟動測試完畢！")
    print("💡 您可以隨時在終端機執行 `py run_shioaji.py` 進行連線或查詢！")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
