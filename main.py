"""
TQA 統一入口：py main.py <指令> [參數]
每個指令的參數照舊，例如 py main.py daily --market TW --skip-data
"""
import sys
import importlib

COMMANDS = {
    "daily": "src.commands.daily",        # 每日運算、推播、更新網頁
    "sim": "src.commands.sim",            # 模擬交易與持股停損評估
    "backtest": "src.commands.backtest",  # 全歷史回測
    "web": "src.commands.web",            # 只重新產生 index.html
    "trade": "src.commands.trade",        # 永豐 Shioaji 下單 (預設 dry-run)
    "validate": "tests.oos_validation",   # 防偷看與樣本外六大檢驗
}

if __name__ == "__main__":
    # 避免 Windows 終端中文亂碼
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("用法：py main.py <指令> [參數]，可用指令：" + ", ".join(COMMANDS))
        sys.exit(2)

    cmd = sys.argv.pop(1)
    sys.argv[0] = f"main.py {cmd}"  # 讓 argparse 的 --help 顯示正確指令
    importlib.import_module(COMMANDS[cmd]).main()
