"""
行動裝置響應式儀表板生成器 (產生支援手機閱讀的 HTML 網頁)
"""
import os
import json
from datetime import datetime
import pandas as pd
from typing import Dict

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>⚡ TQA 科技量化投資儀表板</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        darkBg: '#0f172a',
                        cardBg: '#1e293b',
                        cardBorder: '#334155',
                        bullGreen: '#10b981',
                        bearRed: '#ef4444',
                        accentBlue: '#3b82f6',
                        goldYellow: '#f59e0b'
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
        .glass-card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
        .tab-btn.active { border-bottom: 3px solid #3b82f6; color: #60a5fa; font-weight: bold; }
        /* 隱藏滾動條但保持滾動 */
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="text-slate-100 min-h-screen pb-12">

    <!-- 頂部導覽列 (適合手機單手滑動) -->
    <header class="sticky top-0 z-50 glass-card border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div class="flex items-center space-x-2">
            <span class="text-2xl">⚡</span>
            <div>
                <h1 class="font-extrabold text-base tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">TQA 科技量化助手</h1>
                <p class="text-[10px] text-slate-400">大戶投專屬 • 台美純科技輪動</p>
            </div>
        </div>
        <div class="text-right">
            <span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-950 text-emerald-400 border border-emerald-800">
                <span class="w-1.5 h-1.5 mr-1 bg-emerald-400 rounded-full animate-pulse"></span> 雲端在線
            </span>
            <div class="text-[10px] text-slate-400 mt-0.5" id="update-time">更新: __UPDATE_TIME__</div>
        </div>
    </header>

    <main class="max-w-4xl mx-auto px-4 mt-4 space-y-5">

        <!-- 市場切換分頁 (Tab) -->
        <div class="flex border-b border-slate-800 text-sm font-medium">
            <button onclick="switchTab('tw')" id="tab-tw" class="tab-btn active flex-1 py-3 text-center transition-colors">
                🇹🇼 台股科技天團
            </button>
            <button onclick="switchTab('us')" id="tab-us" class="tab-btn flex-1 py-3 text-center text-slate-400 hover:text-slate-200 transition-colors">
                🇺🇸 美股科技天團
            </button>
        </div>

        <!-- ================= 台股內容區塊 ================= -->
        <div id="content-tw" class="space-y-5">
            <!-- 推薦操作卡片 -->
            <div class="glass-card rounded-2xl p-4 border border-blue-500/20 shadow-lg shadow-blue-500/5">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-xs font-semibold uppercase tracking-wider text-blue-400 flex items-center gap-1">
                        🎯 大戶投晨間建議 (08:45 推播)
                    </span>
                    <span class="text-xs px-2 py-0.5 rounded-full __TW_STATE_BADGE__">__TW_STATE_TEXT__</span>
                </div>
                <div class="space-y-2">
                    __TW_RECOMMENDATIONS__
                </div>
            </div>

            <!-- 台股回測績效儀表板 -->
            <div class="glass-card rounded-2xl p-4">
                <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                    📊 策略歷史成績單 (vs 0052 富邦科技)
                </h3>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center">
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">總報酬率</div>
                        <div class="text-lg font-bold text-emerald-400 font-mono">__TW_TOTAL_RET__</div>
                    </div>
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">年化報酬 (CAGR)</div>
                        <div class="text-lg font-bold text-emerald-400 font-mono">__TW_CAGR__</div>
                    </div>
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">超額報酬 (Alpha)</div>
                        <div class="text-lg font-bold text-amber-400 font-mono">__TW_ALPHA__</div>
                    </div>
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">最大回撤 (MDD)</div>
                        <div class="text-lg font-bold text-rose-400 font-mono">__TW_MDD__</div>
                    </div>
                </div>
            </div>

            <!-- 台股動態評分天梯 (表格，手機橫滑友好) -->
            <div class="glass-card rounded-2xl p-4 overflow-hidden">
                <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    🏆 台股科技動能天梯排行
                </h3>
                <div class="overflow-x-auto no-scrollbar">
                    <table class="w-full text-left text-xs">
                        <thead>
                            <tr class="text-slate-400 border-b border-slate-800 pb-2">
                                <th class="py-2">排名</th>
                                <th>標的</th>
                                <th class="text-right">最新價</th>
                                <th class="text-right">20日動能</th>
                                <th class="text-right">綜合分</th>
                                <th class="text-center">狀態</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/60">
                            __TW_TABLE_ROWS__
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= 美股內容區塊 ================= -->
        <div id="content-us" class="space-y-5 hidden">
            <!-- 推薦操作卡片 -->
            <div class="glass-card rounded-2xl p-4 border border-blue-500/20 shadow-lg shadow-blue-500/5">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-xs font-semibold uppercase tracking-wider text-blue-400 flex items-center gap-1">
                        🎯 大戶投複委託建議 (21:10 推播)
                    </span>
                    <span class="text-xs px-2 py-0.5 rounded-full __US_STATE_BADGE__">__US_STATE_TEXT__</span>
                </div>
                <div class="space-y-2">
                    __US_RECOMMENDATIONS__
                </div>
            </div>

            <!-- 美股回測績效儀表板 -->
            <div class="glass-card rounded-2xl p-4">
                <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                    📊 策略歷史成績單 (vs QQQ 那斯達克100)
                </h3>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center">
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">總報酬率</div>
                        <div class="text-lg font-bold text-emerald-400 font-mono">__US_TOTAL_RET__</div>
                    </div>
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">年化報酬 (CAGR)</div>
                        <div class="text-lg font-bold text-emerald-400 font-mono">__US_CAGR__</div>
                    </div>
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">夏普比率 (Sharpe)</div>
                        <div class="text-lg font-bold text-amber-400 font-mono">__US_SHARPE__</div>
                    </div>
                    <div class="bg-slate-800/60 rounded-xl p-2.5 border border-slate-700/50">
                        <div class="text-[11px] text-slate-400">最大回撤 (MDD)</div>
                        <div class="text-lg font-bold text-rose-400 font-mono">__US_MDD__</div>
                    </div>
                </div>
            </div>

            <!-- 美股動態評分天梯 -->
            <div class="glass-card rounded-2xl p-4 overflow-hidden">
                <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    🏆 美股科技動能天梯排行
                </h3>
                <div class="overflow-x-auto no-scrollbar">
                    <table class="w-full text-left text-xs">
                        <thead>
                            <tr class="text-slate-400 border-b border-slate-800 pb-2">
                                <th class="py-2">排名</th>
                                <th>標的</th>
                                <th class="text-right">最新價</th>
                                <th class="text-right">20日動能</th>
                                <th class="text-right">綜合分</th>
                                <th class="text-center">狀態</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800/60">
                            __US_TABLE_ROWS__
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- 底部提示 -->
        <footer class="text-center text-xs text-slate-500 pt-6">
            <p>本儀表板專為個人量化策略輔助設計，數據源自 Yahoo Finance。</p>
            <p class="mt-1">由 GitHub Actions 自動於每日開盤前更新。</p>
        </footer>

    </main>

    <!-- Tab 切換腳本 -->
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
            
            badge_action = "🟢 建議買入/持有" if above_50 else "⚪ 防禦觀望"
            badge_color = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" if above_50 else "bg-slate-700/50 text-slate-400 border-slate-600/30"
            
            unit_hint = "盤中零股或整股" if is_tw else "大戶投複委託碎股"
            currency = "NT$" if is_tw else "$"

            html = f"""
            <div class="flex items-center justify-between p-3 rounded-xl bg-slate-800/40 border border-slate-700/40">
                <div class="flex items-center space-x-3">
                    <span class="flex items-center justify-center w-7 h-7 rounded-lg bg-blue-500/10 text-blue-400 font-bold text-xs">
                        #{idx+1}
                    </span>
                    <div>
                        <div class="font-bold text-slate-100 text-sm flex items-center gap-1.5">
                            {name}
                            <span class="text-[10px] text-slate-400 font-mono font-normal">({ticker})</span>
                        </div>
                        <div class="text-[11px] text-slate-400">
                            最新價: <span class="font-mono text-slate-200">{currency}{price:,.2f}</span> • 評分: <span class="text-blue-400 font-mono">{score:+.1f}</span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <span class="inline-block px-2.5 py-1 text-xs rounded-lg font-medium border {badge_color}">
                        {badge_action}
                    </span>
                    <div class="text-[10px] text-slate-500 mt-1">{unit_hint}</div>
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
            status_badge = '<span class="text-emerald-400 font-semibold">多頭</span>' if above_50 else '<span class="text-rose-400 font-semibold">轉弱</span>'

            row_html = f"""
            <tr class="hover:bg-slate-800/30 transition-colors">
                <td class="py-2.5 font-bold text-slate-400">#{idx+1}</td>
                <td class="font-medium text-slate-200">
                    <div>{name}</div>
                    <div class="text-[10px] text-slate-500 font-mono">{ticker}</div>
                </td>
                <td class="text-right font-mono font-medium text-slate-200">{currency}{price:,.2f}</td>
                <td class="text-right font-mono {roc_color}">{roc20:+.2f}%</td>
                <td class="text-right font-mono text-blue-400 font-semibold">{score:+.1f}</td>
                <td class="text-center text-xs">{status_badge}</td>
            </tr>
            """
            rows.append(row_html)
        return "\n".join(rows)

    @classmethod
    def generate_html(cls, tw_rank: pd.DataFrame, us_rank: pd.DataFrame, tw_backtest: dict, us_backtest: dict, output_path: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 台股操作狀態
        tw_top_above_50 = tw_rank.iloc[0]["above_50sma"]
        tw_state_text = "🟢 積極進攻" if tw_top_above_50 else "🛡️ 防禦避險 (觀望現金)"
        tw_state_badge = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" if tw_top_above_50 else "bg-amber-500/20 text-amber-300 border border-amber-500/30"

        # 美股操作狀態
        us_top_above_50 = us_rank.iloc[0]["above_50sma"]
        us_state_text = "🟢 積極進攻" if us_top_above_50 else "🛡️ 防禦避險 (觀望現金)"
        us_state_badge = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" if us_top_above_50 else "bg-amber-500/20 text-amber-300 border border-amber-500/30"

        html = HTML_TEMPLATE
        html = html.replace("__UPDATE_TIME__", now_str)

        # 替換台股資料
        html = html.replace("__TW_STATE_TEXT__", tw_state_text)
        html = html.replace("__TW_STATE_BADGE__", tw_state_badge)
        html = html.replace("__TW_RECOMMENDATIONS__", cls.build_recommendation_html(tw_rank.iloc[:3], is_tw=True))
        html = html.replace("__TW_TABLE_ROWS__", cls.build_table_rows_html(tw_rank, is_tw=True))
        html = html.replace("__TW_TOTAL_RET__", f"{tw_backtest.get('total_return_pct', 0):+.2f}%")
        html = html.replace("__TW_CAGR__", f"{tw_backtest.get('cagr_pct', 0):+.2f}%")
        diff_tw = tw_backtest.get('total_return_pct', 0) - (-56.88)
        html = html.replace("__TW_ALPHA__", f"{diff_tw:+.2f}%")
        html = html.replace("__TW_MDD__", f"{tw_backtest.get('max_drawdown_pct', 0):.2f}%")

        # 替換美股資料
        html = html.replace("__US_STATE_TEXT__", us_state_text)
        html = html.replace("__US_STATE_BADGE__", us_state_badge)
        html = html.replace("__US_RECOMMENDATIONS__", cls.build_recommendation_html(us_rank.iloc[:3], is_tw=False))
        html = html.replace("__US_TABLE_ROWS__", cls.build_table_rows_html(us_rank, is_tw=False))
        html = html.replace("__US_TOTAL_RET__", f"{us_backtest.get('total_return_pct', 0):+.2f}%")
        html = html.replace("__US_CAGR__", f"{us_backtest.get('cagr_pct', 0):+.2f}%")
        html = html.replace("__US_SHARPE__", f"{us_backtest.get('sharpe_ratio', 0):.2f}")
        html = html.replace("__US_MDD__", f"{us_backtest.get('max_drawdown_pct', 0):.2f}%")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 手機響應式網頁已成功生成：{output_path}")
