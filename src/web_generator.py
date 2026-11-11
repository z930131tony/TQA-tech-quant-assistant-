"""
行動端響應式儀表板生成模組
"""
import os
from datetime import datetime
import pandas as pd

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TQA 科技量化策略儀表板</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card { background: #151d2f; border: 1px solid #232f48; }
        .tab-btn.active { border-bottom: 2px solid #3b82f6; color: #60a5fa; font-weight: 600; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="text-slate-100 min-h-screen pb-10">

    <header class="sticky top-0 z-50 card border-b px-4 py-3 flex items-center justify-between">
        <div>
            <h1 class="font-bold text-base text-slate-100">TQA 科技量化策略</h1>
            <p class="text-[11px] text-slate-400">大戶投現貨 / 複委託波段輪動</p>
        </div>
        <div class="text-right">
            <span class="text-[10px] text-slate-400">更新時間</span>
            <div class="text-[11px] font-mono text-slate-300">__UPDATE_TIME__</div>
        </div>
    </header>

    <main class="max-w-3xl mx-auto px-4 mt-4 space-y-4">

        <!-- 分頁切換 -->
        <div class="flex border-b border-slate-800 text-sm">
            <button onclick="switchTab('tw')" id="tab-tw" class="tab-btn active flex-1 py-2.5 text-center transition-colors">
                台股焦點
            </button>
            <button onclick="switchTab('us')" id="tab-us" class="tab-btn flex-1 py-2.5 text-center text-slate-400 hover:text-slate-200 transition-colors">
                美股焦點
            </button>
        </div>

        <!-- ================= 台股 ================= -->
        <div id="content-tw" class="space-y-4">
            <div class="card rounded-xl p-4">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-slate-300">大戶投操作指引</span>
                    <span class="text-xs px-2 py-0.5 rounded font-mono __TW_STATE_BADGE__">__TW_STATE_TEXT__</span>
                </div>
                <div class="text-[11px] text-slate-400 mb-3">數據基準日：__TW_DATA_DATE__ 收盤</div>
                <div class="space-y-2">
                    __TW_RECOMMENDATIONS__
                </div>
            </div>

            <div class="card rounded-xl p-4">
                <h3 class="text-xs font-semibold text-slate-400 mb-2.5">歷史回測績效 (2024 - 2026)</h3>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center font-mono">
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">總報酬率</div>
                        <div class="text-base font-bold text-emerald-400">__TW_TOTAL_RET__</div>
                    </div>
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">年化報酬 (CAGR)</div>
                        <div class="text-base font-bold text-emerald-400">__TW_CAGR__</div>
                    </div>
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">同期基準 (0052)</div>
                        <div class="text-base font-bold text-slate-300">__TW_BENCHMARK__</div>
                    </div>
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">最大回撤 (MDD)</div>
                        <div class="text-base font-bold text-rose-400">__TW_MDD__</div>
                    </div>
                </div>
            </div>

            <div class="card rounded-xl p-4 overflow-hidden">
                <h3 class="text-xs font-semibold text-slate-400 mb-2.5">標的評分排序</h3>
                <div class="overflow-x-auto no-scrollbar">
                    <table class="w-full text-left text-xs">
                        <thead>
                            <tr class="text-slate-400 border-b border-slate-800">
                                <th class="py-1.5">排名</th>
                                <th>標的</th>
                                <th class="text-right">最新價</th>
                                <th class="text-right">20日動能</th>
                                <th class="text-right">綜合分</th>
                                <th class="text-center">狀態</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/50">
                            __TW_TABLE_ROWS__
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= 美股 ================= -->
        <div id="content-us" class="space-y-4 hidden">
            <div class="card rounded-xl p-4">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-slate-300">複委託操作指引</span>
                    <span class="text-xs px-2 py-0.5 rounded font-mono __US_STATE_BADGE__">__US_STATE_TEXT__</span>
                </div>
                <div class="text-[11px] text-slate-400 mb-3">數據基準日：__US_DATA_DATE__ 收盤</div>
                <div class="space-y-2">
                    __US_RECOMMENDATIONS__
                </div>
            </div>

            <div class="card rounded-xl p-4">
                <h3 class="text-xs font-semibold text-slate-400 mb-2.5">歷史回測績效 (2024 - 2026)</h3>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center font-mono">
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">總報酬率</div>
                        <div class="text-base font-bold text-emerald-400">__US_TOTAL_RET__</div>
                    </div>
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">年化報酬 (CAGR)</div>
                        <div class="text-base font-bold text-emerald-400">__US_CAGR__</div>
                    </div>
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">同期基準 (QQQ)</div>
                        <div class="text-base font-bold text-slate-300">__US_BENCHMARK__</div>
                    </div>
                    <div class="bg-slate-800/50 rounded-lg p-2">
                        <div class="text-[10px] text-slate-400">最大回撤 (MDD)</div>
                        <div class="text-base font-bold text-rose-400">__US_MDD__</div>
                    </div>
                </div>
            </div>

            <div class="card rounded-xl p-4 overflow-hidden">
                <h3 class="text-xs font-semibold text-slate-400 mb-2.5">標的評分排序</h3>
                <div class="overflow-x-auto no-scrollbar">
                    <table class="w-full text-left text-xs">
                        <thead>
                            <tr class="text-slate-400 border-b border-slate-800">
                                <th class="py-1.5">排名</th>
                                <th>標的</th>
                                <th class="text-right">最新價</th>
                                <th class="text-right">20日動能</th>
                                <th class="text-right">綜合分</th>
                                <th class="text-center">狀態</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/50">
                            __US_TABLE_ROWS__
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <footer class="text-center text-[11px] text-slate-500 pt-4">
            數據來源: Yahoo Finance • 風控規則: 跌破 50MA 或高點拉回 8% 出場
        </footer>

    </main>

    <script>
        function switchTab(market) {
            const tabTw = document.getElementById('tab-tw');
            const tabUs = document.getElementById('tab-us');
            const contentTw = document.getElementById('content-tw');
            const contentUs = document.getElementById('content-us');

            if (market === 'tw') {
                tabTw.classList.add('active', 'text-blue-400');
                tabTw.classList.remove('text-slate-400');
                tabUs.classList.remove('active', 'text-blue-400');
                tabUs.classList.add('text-slate-400');
                contentTw.classList.remove('hidden');
                contentUs.classList.add('hidden');
            } else {
                tabUs.classList.add('active', 'text-blue-400');
                tabUs.classList.remove('text-slate-400');
                tabTw.classList.remove('active', 'text-blue-400');
                tabTw.classList.add('text-slate-400');
                contentUs.classList.remove('hidden');
                contentTw.classList.add('hidden');
            }
        }
    </script>
</body>
</html>
"""

class WebDashboardGenerator:
    @staticmethod
    def build_recommendation_html(top_df: pd.DataFrame, is_tw: bool) -> str:
        items = []
        for idx, row in top_df.iterrows():
            ticker = row["ticker"]
            name = row["name"]
            price = row["price"]
            score = row["score"]
            above_50 = row["above_50sma"]
            
            badge_action = "買進 / 續抱" if above_50 else "觀望 / 現金"
            badge_color = "bg-emerald-950 text-emerald-400 border border-emerald-800" if above_50 else "bg-slate-800 text-slate-400 border border-slate-700"
            currency = "NT$" if is_tw else "$"

            html = f"""
            <div class="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50">
                <div class="flex items-center space-x-2.5">
                    <span class="w-6 h-6 rounded bg-slate-700 text-slate-300 font-mono text-xs flex items-center justify-center font-bold">
                        {idx+1}
                    </span>
                    <div>
                        <div class="font-bold text-slate-200 text-xs">
                            {name} <span class="font-mono text-slate-400 font-normal">({ticker})</span>
                        </div>
                        <div class="text-[11px] text-slate-400 font-mono">
                            收盤 {currency}{price:,.2f} | 評分 {score:+.1f}
                        </div>
                    </div>
                </div>
                <div>
                    <span class="px-2 py-0.5 text-xs rounded font-medium {badge_color}">
                        {badge_action}
                    </span>
                </div>
            </div>
            """
            items.append(html)
        return "\n".join(items)

    @staticmethod
    def build_table_rows_html(rank_df: pd.DataFrame, is_tw: bool) -> str:
        rows = []
        for idx, row in rank_df.iterrows():
            ticker = row["ticker"]
            name = row["name"]
            price = row["price"]
            roc20 = row["roc_20d"]
            score = row["score"]
            above_50 = row["above_50sma"]

            roc_color = "text-emerald-400" if roc20 >= 0 else "text-rose-400"
            currency = "NT$" if is_tw else "$"
            status_badge = '<span class="text-emerald-400 font-medium">多頭</span>' if above_50 else '<span class="text-slate-400">轉弱</span>'

            row_html = f"""
            <tr class="hover:bg-slate-800/30">
                <td class="py-2 text-slate-400 font-mono">#{idx+1}</td>
                <td class="font-medium text-slate-200">
                    <div>{name}</div>
                    <div class="text-[10px] text-slate-500 font-mono">{ticker}</div>
                </td>
                <td class="text-right font-mono text-slate-200">{currency}{price:,.2f}</td>
                <td class="text-right font-mono {roc_color}">{roc20:+.2f}%</td>
                <td class="text-right font-mono text-slate-300 font-semibold">{score:+.1f}</td>
                <td class="text-center text-xs">{status_badge}</td>
            </tr>
            """
            rows.append(row_html)
        return "\n".join(rows)

    @classmethod
    def generate_html(cls, tw_rank: pd.DataFrame, us_rank: pd.DataFrame, tw_backtest: dict, us_backtest: dict, output_path: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        tw_date = tw_rank.iloc[0].get("data_date", "-")
        us_date = us_rank.iloc[0].get("data_date", "-")

        tw_top_above_50 = tw_rank.iloc[0]["above_50sma"]
        tw_state_text = "多頭進攻" if tw_top_above_50 else "防禦觀望"
        tw_state_badge = "bg-emerald-950 text-emerald-400 border border-emerald-800" if tw_top_above_50 else "bg-slate-800 text-slate-300 border border-slate-700"

        us_top_above_50 = us_rank.iloc[0]["above_50sma"]
        us_state_text = "多頭進攻" if us_top_above_50 else "防禦觀望"
        us_state_badge = "bg-emerald-950 text-emerald-400 border border-emerald-800" if us_top_above_50 else "bg-slate-800 text-slate-300 border border-slate-700"

        html = HTML_TEMPLATE
        html = html.replace("__UPDATE_TIME__", now_str)

        # 台股
        html = html.replace("__TW_STATE_TEXT__", tw_state_text)
        html = html.replace("__TW_STATE_BADGE__", tw_state_badge)
        html = html.replace("__TW_DATA_DATE__", tw_date)
        html = html.replace("__TW_RECOMMENDATIONS__", cls.build_recommendation_html(tw_rank.iloc[:3], is_tw=True))
        html = html.replace("__TW_TABLE_ROWS__", cls.build_table_rows_html(tw_rank, is_tw=True))
        html = html.replace("__TW_TOTAL_RET__", f"{tw_backtest.get('total_return_pct', 0):+.2f}%")
        html = html.replace("__TW_CAGR__", f"{tw_backtest.get('cagr_pct', 0):+.2f}%")
        html = html.replace("__TW_BENCHMARK__", "-56.88%")
        html = html.replace("__TW_MDD__", f"{tw_backtest.get('max_drawdown_pct', 0):.2f}%")

        # 美股
        html = html.replace("__US_STATE_TEXT__", us_state_text)
        html = html.replace("__US_STATE_BADGE__", us_state_badge)
        html = html.replace("__US_DATA_DATE__", us_date)
        html = html.replace("__US_RECOMMENDATIONS__", cls.build_recommendation_html(us_rank.iloc[:3], is_tw=False))
        html = html.replace("__US_TABLE_ROWS__", cls.build_table_rows_html(us_rank, is_tw=False))
        html = html.replace("__US_TOTAL_RET__", f"{us_backtest.get('total_return_pct', 0):+.2f}%")
        html = html.replace("__US_CAGR__", f"{us_backtest.get('cagr_pct', 0):+.2f}%")
        html = html.replace("__US_BENCHMARK__", "+56.63%")
        html = html.replace("__US_MDD__", f"{us_backtest.get('max_drawdown_pct', 0):.2f}%")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"網頁生成完成：{output_path}")
