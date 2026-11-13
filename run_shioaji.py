"""
永豐金證券 Shioaji API 實盤/模擬交易執行器與風控診斷面板 (Rich_v2.0)
功能：
1. 支援 CLI 參數：
   --budget <float>: 指定本次可用總資金或單檔預算
   --dry-run: 預設啟用安全鎖 (計算特徵、更新峰值與印出委託明細，不送出 API)
   --execute: 解除安全鎖正式向券商送出委託
   --skip-data: 使用本地快取數據加速
   --test-conn: 僅執行帳號與行情連線檢測
2. 終端機格式化輸出結構化【Rich_v2.0 實盤風控診斷面板】:
   - 帳戶總淨值、歷史最高淨值 (peak_equity)、目前回撤幅度 (current_drawdown_pct)、倉位縮放係數 (risk_scaling_factor)
   - 每檔持倉距離 -8% 移動停損與 -30% 絕對硬停損的安全緩衝距離
   - 預計委託掛單明細表 (動作、股數、限價、讓價機制、原因)
"""
import os
import sys
import io
import argparse
from datetime import datetime
import pytz
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

load_dotenv()

from src.data_loader import TechDataLoader
from src.features import TechFeatureEngine
from src.portfolio import PortfolioTracker
from src.trader import AutoTrader, SHIOAJI_AVAILABLE, sj

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


def print_rich_diagnostics(
    state: dict,
    evaluated: list,
    orders: list,
    dry_run: bool
):
    """輸出 Rich_v2.0 實盤風控診斷面板"""
    peak_eq = state.get("peak_equity", 100000.0)
    dd_pct = state.get("current_drawdown_pct", 0.0)
    scaling = state.get("risk_scaling_factor", 1.0)
    cash = state.get("cash", 30000.0)
    
    # 計算目前總持股市值與總淨值 (美股以匯率 32.5 換算為台幣)
    total_market_val = sum((p.get("market_val", 0.0) if p.get("is_tw") else p.get("market_val", 0.0) * 32.5) for p in evaluated)
    total_equity = total_market_val + cash

    if RICH_AVAILABLE:
        # Panel 1: 帳戶總覽
        header_text = Text()
        header_text.append("📊 帳戶總淨值: ", style="bold white")
        header_text.append(f"NT$ {total_equity:,.0f}  ", style="bold green" if total_equity >= peak_eq else "bold yellow")
        header_text.append("│ 歷史最高淨值 (Peak): ", style="bold white")
        header_text.append(f"NT$ {peak_eq:,.0f}  ", style="bold cyan")
        header_text.append("│ 目前總回撤: ", style="bold white")
        header_text.append(f"-{dd_pct:.2f}%  ", style="bold green" if dd_pct < 10 else ("bold yellow" if dd_pct < 18 else "bold red"))
        header_text.append("│ 動態倉位係數: ", style="bold white")
        header_text.append(f"{scaling:.2f}x\n", style="bold green" if scaling == 1.0 else "bold red")
        
        mode_desc = "[安全鎖鎖定] 僅進行數據計算與風控模擬 (DRY-RUN)" if dry_run else "[正式執行模式] 委託將實時送達永豐主機 (EXECUTE)"
        panel = Panel(
            header_text,
            title=f"[bold cyan]🛡️ TQA 實盤風控戰情中心 v2.0 ({mode_desc})[/bold cyan]",
            border_style="cyan" if dry_run else "red"
        )
        console.print(panel)

        # Table 1: 持倉風控距離明細
        if evaluated:
            pos_table = Table(title="📦 現有庫存部位與雙軌停損安全距離", header_style="bold magenta", border_style="dim")
            pos_table.add_column("標的名稱", justify="left")
            pos_table.add_column("股數", justify="right")
            pos_table.add_column("成本價", justify="right")
            pos_table.add_column("最新價", justify="right")
            pos_table.add_column("未實現損益", justify="right")
            pos_table.add_column("高點回檔", justify="right")
            pos_table.add_column("距 -8% 移動停損", justify="right")
            pos_table.add_column("距 -30% 硬停損", justify="right")
            pos_table.add_column("狀態", justify="center")

            for p in evaluated:
                pnl = p["unrealized_pnl"]
                ret = p["return_pct"]
                pnl_style = "green" if pnl >= 0 else "red"
                prefix = "NT$" if p["is_tw"] else "$"
                
                dist_trail = p.get("dist_to_trailing", 0.0)
                dist_hard = p.get("dist_to_hard", 0.0)
                trail_style = "green" if dist_trail > 3.0 else ("yellow" if dist_trail > 0.0 else "bold red")
                hard_style = "green" if dist_hard > 10.0 else ("yellow" if dist_hard > 0.0 else "bold red")

                pos_table.add_row(
                    f"{p['name']} ({p['ticker']})",
                    f"{int(p['shares'])}",
                    f"{prefix}{p['cost_price']:,.2f}",
                    f"{prefix}{p['curr_price']:,.2f}",
                    f"[{pnl_style}]{prefix}{pnl:+,.0f} ({ret:+.2f}%)[/{pnl_style}]",
                    f"{p['drawdown_from_peak']:.2f}%",
                    f"[{trail_style}]{dist_trail:+.2f}% (價位:{prefix}{p['trailing_stop_price']:,.1f})[/{trail_style}]",
                    f"[{hard_style}]{dist_hard:+.2f}% (價位:{prefix}{p['hard_stop_price']:,.1f})[/{hard_style}]",
                    f"[red]{p['alert_text']}[/red]" if p["has_alert"] else "[green]安全續抱[/green]"
                )
            console.print(pos_table)
            console.print()

        # Table 2: 預計委託明細
        if orders:
            ord_table = Table(title="📋 本次調倉預計執行委託單 (Order List)", header_style="bold blue", border_style="blue")
            ord_table.add_column("動作", justify="center")
            ord_table.add_column("標的", justify="left")
            ord_table.add_column("股數", justify="right")
            ord_table.add_column("限價 (LMT)", justify="right")
            ord_table.add_column("市價", justify="right")
            ord_table.add_column("讓價保護", justify="center")
            ord_table.add_column("觸發原因", justify="left")

            for o in orders:
                act = o["action"]
                act_style = "bold red" if act == "SELL" else "bold green"
                is_emerg = o.get("is_emergency", False)
                prefix = "NT$" if o.get("is_tw", False) else "$"
                
                ord_table.add_row(
                    f"[{act_style}]{act}[/{act_style}]",
                    f"{o['name']} ({o['ticker']})",
                    f"{o['shares']} 股",
                    f"{prefix}{o['price']:,.2f}",
                    f"{prefix}{o.get('market_price', o['price']):,.2f}",
                    "[bold red]-1% 讓價撮合[/bold red]" if is_emerg else "--",
                    o.get("reason", "")
                )
            console.print(ord_table)
        else:
            console.print("[bold green]✅ 今日無任何需執行之買賣委託單，帳戶狀態平穩。[/bold green]")
        console.print()

    else:
        # ASCII Fallback
        print("=" * 70)
        print(f"📊 帳戶總淨值: NT$ {total_equity:,.0f} | 歷史峰值: NT$ {peak_eq:,.0f} | 總回撤: -{dd_pct:.2f}% | 倉位係數: {scaling:.2f}x")
        print("=" * 70)
        if orders:
            print("📋 預計執行委託單:")
            for o in orders:
                print(f"  • {o['action']} {o['name']} ({o['ticker']}) {o['shares']} 股 @ NT${o['price']:,.2f} - 原因: {o.get('reason')}")
        else:
            print("✅ 今日無任何需執行之買賣委託單。")


def test_connection_flow():
    """連線與庫存查詢模式"""
    print("=" * 65)
    print("🚀 【永豐金證券 Shioaji API 連線檢測】")
    print("=" * 65)
    if not SHIOAJI_AVAILABLE:
        print("❌ 尚未安裝 shioaji 套件，請先執行: py -m pip install -r requirements-local.txt")
        return

    api_key = os.getenv("SHIOAJI_API_KEY", "").strip()
    secret_key = os.getenv("SHIOAJI_SECRET_KEY", "").strip()
    cert_path = os.getenv("SHIOAJI_CERT_PATH", "").strip()
    cert_pass = os.getenv("SHIOAJI_CERT_PASSWORD", "").strip()
    person_id = os.getenv("SHIOAJI_PERSON_ID", "").strip()
    sim = os.getenv("SHIOAJI_SIMULATION", "true").lower() == "true"

    if not api_key or not secret_key:
        print("❌ 找不到 SHIOAJI_API_KEY 或 SHIOAJI_SECRET_KEY！")
        return

    api = sj.Shioaji(simulation=sim)
    try:
        accs = api.login(api_key=api_key, secret_key=secret_key)
        print(f"  ✅ 登入成功！模式: {'模擬' if sim else '正式'}")
        for acc in accs:
            print(f"    • 帳號: {acc.account_id} | 戶名: {getattr(acc, 'username', '--')}")
        
        if cert_path and os.path.exists(cert_path) and cert_pass and person_id:
            api.activate_ca(ca_path=cert_path, ca_passwd=cert_pass, person_id=person_id)
            print("  ✅ CA 憑證啟用成功！")
        else:
            print("  ℹ️ 未設定憑證，維持查詢模式。")
    except Exception as e:
        print(f"  ❌ 登入異常: {e}")


def main():
    parser = argparse.ArgumentParser(description="TQA 永豐金證券 Shioaji 交易與風控執行器")
    parser.add_argument("--budget", type=float, default=None, help="指定本次可用總資金或加碼預算 (預設讀取 portfolio.json 現金水位)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="啟用安全鎖 (預設)，僅計算特徵與印出委託明細，不送單")
    parser.add_argument("--execute", action="store_true", help="解除安全鎖，確認無誤後正式向券商送出 API 委託")
    parser.add_argument("--skip-data", action="store_true", help="使用本地快取數據加速")
    parser.add_argument("--test-conn", action="store_true", help="僅進行 API 連線與帳戶查詢檢測")
    args = parser.parse_args()

    # 若使用者明確指定 --execute，則關閉 dry_run
    is_dry_run = not args.execute

    if args.test_conn:
        test_connection_flow()
        return

    # 1. 抓取行情數據
    loader = TechDataLoader()
    dataset = loader.fetch_all_tech_data(cache_only=args.skip_data)

    # 2. 計算特徵與評分天梯
    tw_rank, us_rank = TechFeatureEngine.evaluate_latest_ranking(dataset)

    # 3. 讀取設定檔預算
    p_state = PortfolioTracker.load_portfolio_state()
    budget_tw = args.budget if args.budget is not None else float(p_state.get("cash", 30000.0))

    # 4. 產生五層風控訂單與診斷數據
    trader = AutoTrader(dataset=dataset, budget_per_stock_tw=budget_tw)
    orders, state, logs = trader.generate_trade_orders(tw_rank, us_rank, target_market="TW")
    evaluated_positions = PortfolioTracker.evaluate_portfolio(dataset, save_state=True)

    # 5. 輸出 Rich_v2.0 診斷面板
    print_rich_diagnostics(state, evaluated_positions, orders, dry_run=is_dry_run)

    # 6. 若解除安全鎖，正式送出委託
    if not is_dry_run:
        print("⚠️ 【警告】正在向永豐金證券送出真實/模擬委託單...")
        trader.execute_shioaji_orders(orders, dry_run=False)
        # 同步永豐持倉
        AutoTrader.sync_shioaji_positions()
    else:
        print("🔒 安全鎖保護中：以上為預估委託明細，未向券商送單。如欲正式下單，請附加參數: --execute")


if __name__ == "__main__":
    main()
