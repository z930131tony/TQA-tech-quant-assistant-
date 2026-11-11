"""
行動端響應式儀表板生成模組 (支援點擊彈窗、互動圖表與個股深度數據)
"""
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict
from src.config import TECH_UNIVERSE_TW

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TQA 科技量化策略儀表板</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card { background: #151d2f; border: 1px solid #232f48; }
        .tab-btn.active { border-bottom: 2px solid #3b82f6; color: #60a5fa; font-weight: 600; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .modal-bg { background-color: rgba(11, 15, 25, 0.85); backdrop-filter: blur(8px); }
    </style>
</head>
<body class="text-slate-100 min-h-screen pb-10">

    <header class="sticky top-0 z-40 card border-b px-4 py-3 flex items-center justify-between">
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
                <div class="text-[11px] text-slate-400 mb-3">數據基準日：__TW_DATA_DATE__ 收盤 (點擊查看圖表)</div>
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
                <h3 class="text-xs font-semibold text-slate-400 mb-2.5">標的評分排序 (點擊列開啟詳情)</h3>
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
                <div class="text-[11px] text-slate-400 mb-3">數據基準日：__US_DATA_DATE__ 收盤 (點擊查看圖表)</div>
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
                <h3 class="text-xs font-semibold text-slate-400 mb-2.5">標的評分排序 (點擊列開啟詳情)</h3>
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

    <!-- ================= 標的深度數據與走勢圖彈出視窗 (Modal) ================= -->
    <div id="stock-modal" class="fixed inset-0 z-50 modal-bg flex items-end sm:items-center justify-center p-0 sm:p-4 hidden transition-opacity">
        <div class="card w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl p-5 shadow-2xl space-y-4">
            
            <!-- 彈窗頂部 (標題與關閉按鈕) -->
            <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                <div>
                    <div class="flex items-center gap-2">
                        <h2 id="modal-name" class="font-bold text-lg text-slate-100">-</h2>
                        <span id="modal-symbol" class="text-xs text-slate-400 font-mono">-</span>
                    </div>
                    <div class="text-xs text-slate-400 mt-0.5">
                        最新收盤: <span id="modal-price" class="font-mono font-bold text-slate-100 text-sm">-</span>
                        <span id="modal-trend-badge" class="ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium">-</span>
                    </div>
                </div>
                <button onclick="closeStockModal()" class="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 flex items-center justify-center text-lg">
                    ✕
                </button>
            </div>

            <!-- 走勢圖表 (近 60 交易日 K 線走勢與 50MA) -->
            <div>
                <div class="flex items-center justify-between text-xs text-slate-400 mb-2">
                    <span>近 60 日股價走勢與 50MA 生命線</span>
                    <span class="flex items-center gap-3 text-[11px]">
                        <span class="flex items-center gap-1"><span class="w-2.5 h-0.5 bg-blue-400"></span> 收盤價</span>
                        <span class="flex items-center gap-1"><span class="w-2.5 h-0.5 bg-amber-400"></span> 50MA</span>
                    </span>
                </div>
                <div class="h-52 w-full bg-slate-900/60 rounded-xl p-2 border border-slate-800">
                    <canvas id="modalChart"></canvas>
                </div>
            </div>

            <!-- 各項技術因子指標矩陣 -->
            <div>
                <h3 class="text-xs font-semibold text-slate-400 mb-2">量化因子數據</h3>
                <div class="grid grid-cols-3 gap-2 text-center font-mono">
                    <div class="bg-slate-800/40 rounded-lg p-2 border border-slate-800">
                        <div class="text-[10px] text-slate-400">20日動能</div>
                        <div id="modal-roc20" class="text-xs font-bold mt-0.5">-</div>
                    </div>
                    <div class="bg-slate-800/40 rounded-lg p-2 border border-slate-800">
                        <div class="text-[10px] text-slate-400">60日動能</div>
                        <div id="modal-roc60" class="text-xs font-bold mt-0.5">-</div>
                    </div>
                    <div class="bg-slate-800/40 rounded-lg p-2 border border-slate-800">
                        <div class="text-[10px] text-slate-400">120日動能</div>
                        <div id="modal-roc120" class="text-xs font-bold mt-0.5">-</div>
                    </div>
                    <div class="bg-slate-800/40 rounded-lg p-2 border border-slate-800">
                        <div class="text-[10px] text-slate-400">50MA 乖離</div>
                        <div id="modal-bias50" class="text-xs font-bold mt-0.5">-</div>
                    </div>
                    <div class="bg-slate-800/40 rounded-lg p-2 border border-slate-800">
                        <div class="text-[10px] text-slate-400">14日 RSI</div>
                        <div id="modal-rsi" class="text-xs font-bold mt-0.5 text-slate-200">-</div>
                    </div>
                    <div class="bg-slate-800/40 rounded-lg p-2 border border-slate-800">
                        <div class="text-[10px] text-slate-400">20日破高</div>
                        <div id="modal-breakout" class="text-xs font-bold mt-0.5">-</div>
                    </div>
                </div>
            </div>

            <!-- 開啟外部即時看盤新視窗按鈕 -->
            <div class="pt-2 flex gap-2">
                <a id="modal-ext-link" href="#" target="_blank" rel="noopener noreferrer" class="flex-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs text-center transition-colors flex items-center justify-center gap-1.5">
                    在新視窗開啟即時盤口 ↗
                </a>
                <button onclick="closeStockModal()" class="px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition-colors">
                    關閉
                </button>
            </div>

        </div>
    </div>

    <!-- 標的詳細資料 JSON 載入點 -->
    <script>
        const STOCKS_DATABASE = __STOCKS_DATABASE_JSON__;
        let chartInstance = null;

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

        function openStockModal(ticker) {
            const data = STOCKS_DATABASE[ticker];
            if (!data) return;

            // 填寫基本資料
            document.getElementById('modal-name').innerText = data.name;
            document.getElementById('modal-symbol').innerText = data.symbol;
            document.getElementById('modal-price').innerText = (data.is_tw ? 'NT$' : '$') + data.price.toLocaleString(undefined, {minimumFractionDigits: 2});

            // 趨勢狀態徽章
            const trendBadge = document.getElementById('modal-trend-badge');
            if (data.above_50sma) {
                trendBadge.innerText = '站上 50MA (多頭)';
                trendBadge.className = 'ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-950 text-emerald-400 border border-emerald-800';
            } else {
                trendBadge.innerText = '跌破 50MA (弱勢)';
                trendBadge.className = 'ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-950 text-rose-400 border border-rose-800';
            }

            // 填寫各項動能因子
            const setPct = (elemId, val) => {
                const el = document.getElementById(elemId);
                el.innerText = (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
                el.className = 'text-xs font-bold mt-0.5 ' + (val >= 0 ? 'text-emerald-400' : 'text-rose-400');
            };

            setPct('modal-roc20', data.roc_20d);
            setPct('modal-roc60', data.roc_60d);
            setPct('modal-roc120', data.roc_120d);
            setPct('modal-bias50', data.bias_50sma);

            document.getElementById('modal-rsi').innerText = data.rsi.toFixed(1);

            const breakoutEl = document.getElementById('modal-breakout');
            breakoutEl.innerText = data.is_breakout ? '創20日新高' : '否';
            breakoutEl.className = 'text-xs font-bold mt-0.5 ' + (data.is_breakout ? 'text-amber-400' : 'text-slate-400');

            // 外部連結
            const extLink = document.getElementById('modal-ext-link');
            if (data.is_tw) {
                const twClean = data.symbol.replace('.TW', '').replace('.TWO', '');
                extLink.href = 'https://tw.stock.yahoo.com/quote/' + twClean;
            } else {
                extLink.href = 'https://www.tradingview.com/symbols/' + data.symbol + '/';
            }

            // 繪製或更新 Chart.js
            renderChart(data);

            // 顯示彈窗
            document.getElementById('stock-modal').classList.remove('hidden');
        }

        function closeStockModal() {
            document.getElementById('stock-modal').classList.add('hidden');
        }

        function renderChart(data) {
            const ctx = document.getElementById('modalChart').getContext('2d');
            if (chartInstance) {
                chartInstance.destroy();
            }

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.chart_dates,
                    datasets: [
                        {
                            label: '收盤價',
                            data: data.chart_prices,
                            borderColor: '#38bdf8',
                            backgroundColor: 'rgba(56, 189, 248, 0.05)',
                            borderWidth: 2,
                            tension: 0.1,
                            pointRadius: 0,
                            pointHoverRadius: 4,
                            fill: true
                        },
                        {
                            label: '50MA',
                            data: data.chart_sma50,
                            borderColor: '#fbbf24',
                            borderWidth: 1.5,
                            borderDash: [4, 4],
                            tension: 0.1,
                            pointRadius: 0,
                            fill: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: '#1e293b',
                            borderColor: '#334155',
                            borderWidth: 1,
                            titleColor: '#94a3b8',
                            bodyColor: '#f1f5f9',
                            bodyFont: { family: 'monospace' }
                        }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { color: '#64748b', maxTicksLimit: 6, font: { size: 10 } }
                        },
                        y: {
                            grid: { color: 'rgba(51, 65, 85, 0.4)' },
                            ticks: { color: '#94a3b8', font: { size: 10, family: 'monospace' } }
                        }
                    }
                }
            });
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
            <div onclick="openStockModal('{ticker}')" class="cursor-pointer active:scale-[0.99] transition-all flex items-center justify-between p-2.5 rounded-lg bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/50">
                <div class="flex items-center space-x-2.5">
                    <span class="w-6 h-6 rounded bg-slate-700 text-slate-300 font-mono text-xs flex items-center justify-center font-bold">
                        {idx+1}
                    </span>
                    <div>
                        <div class="font-bold text-slate-200 text-xs flex items-center gap-1.5">
                            {name} <span class="font-mono text-slate-400 font-normal">({ticker})</span>
                            <span class="text-[10px] text-blue-400">📊 看圖</span>
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
            <tr onclick="openStockModal('{ticker}')" class="cursor-pointer hover:bg-slate-800/60 active:bg-slate-800 transition-colors">
                <td class="py-2.5 text-slate-400 font-mono">#{idx+1}</td>
                <td class="font-medium text-slate-200">
                    <div class="flex items-center gap-1">{name} <span class="text-[10px] text-blue-400">📊</span></div>
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
    def build_stocks_database_json(cls, dataset: Dict[str, pd.DataFrame]) -> str:
        """
        為每檔標的提取近 60 日歷史價格、均線與技術數據，輸出為前端 JSON
        """
        from src.features import TechFeatureEngine
        
        db = {}
        for ticker, raw_df in dataset.items():
            enriched = TechFeatureEngine.calculate_technical_features(raw_df)
            sub = enriched.tail(60)
            
            latest = enriched.iloc[-1]
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            name = TECH_UNIVERSE_TW.get(ticker, ticker)
            
            # 計算 50MA 乖離率
            curr_price = float(latest["close"])
            sma50_val = float(latest["sma_50"]) if not np.isnan(latest["sma_50"]) else curr_price
            bias_50 = ((curr_price - sma50_val) / sma50_val) * 100

            # 日期標籤 (格式: MM-DD)
            dates = [d.strftime("%m-%d") for d in sub.index]
            prices = [round(float(p), 2) for p in sub["close"]]
            sma50_series = [round(float(m), 2) if not np.isnan(m) else None for m in sub["sma_50"]]

            db[ticker] = {
                "ticker": ticker,
                "name": name,
                "symbol": ticker,
                "is_tw": is_tw,
                "price": curr_price,
                "above_50sma": bool(latest["above_50sma"]),
                "roc_20d": round(float(latest["roc_20"]), 2) if not np.isnan(latest["roc_20"]) else 0.0,
                "roc_60d": round(float(latest["roc_60"]), 2) if not np.isnan(latest["roc_60"]) else 0.0,
                "roc_120d": round(float(latest["roc_120"]), 2) if not np.isnan(latest["roc_120"]) else 0.0,
                "bias_50sma": round(bias_50, 2),
                "rsi": round(float(latest["rsi_14"]), 1) if not np.isnan(latest["rsi_14"]) else 50.0,
                "is_breakout": bool(latest["is_new_high_20d"]),
                "chart_dates": dates,
                "chart_prices": prices,
                "chart_sma50": sma50_series
            }

        return json.dumps(db, ensure_ascii=False)

    @classmethod
    def generate_html(cls, dataset: Dict[str, pd.DataFrame], tw_rank: pd.DataFrame, us_rank: pd.DataFrame, tw_backtest: dict, us_backtest: dict, output_path: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        tw_date = tw_rank.iloc[0].get("data_date", "-")
        us_date = us_rank.iloc[0].get("data_date", "-")

        tw_top_above_50 = tw_rank.iloc[0]["above_50sma"]
        tw_state_text = "多頭進攻" if tw_top_above_50 else "防禦觀望"
        tw_state_badge = "bg-emerald-950 text-emerald-400 border border-emerald-800" if tw_top_above_50 else "bg-slate-800 text-slate-300 border border-slate-700"

        us_top_above_50 = us_rank.iloc[0]["above_50sma"]
        us_state_text = "多頭進攻" if us_top_above_50 else "防禦觀望"
        us_state_badge = "bg-emerald-950 text-emerald-400 border border-emerald-800" if us_top_above_50 else "bg-slate-800 text-slate-300 border border-slate-700"

        stocks_json = cls.build_stocks_database_json(dataset)

        html = HTML_TEMPLATE
        html = html.replace("__UPDATE_TIME__", now_str)
        html = html.replace("__STOCKS_DATABASE_JSON__", stocks_json)

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
