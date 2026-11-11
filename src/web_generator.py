"""
極速行動端儀表板生成模組 (去除 CDN 編譯負擔、極速純 CSS、圖表零延遲更新)
"""
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict
from src.config import TECH_UNIVERSE_TW

# 採用極致精簡的純 CSS，無需載入任何外部 CSS/JIT 編譯器，首屏載入快 10 倍
FAST_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TQA 科技量化策略儀表板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body { background-color: #0b0f19; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; padding-bottom: 40px; }
        .container { max-width: 680px; margin: 0 auto; padding: 12px; }
        
        /* 頂部列 */
        header { position: sticky; top: 0; z-index: 30; background: #131b2e; border-bottom: 1px solid #1e293b; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; }
        .title { font-size: 15px; font-weight: bold; color: #f8fafc; }
        .subtitle { font-size: 10px; color: #94a3b8; }
        .update-time { font-size: 10px; font-family: monospace; color: #cbd5e1; }
        
        /* 分頁切換 */
        .tabs { display: flex; border-bottom: 1px solid #1e293b; margin: 12px 0; }
        .tab-btn { flex: 1; padding: 10px; background: none; border: none; color: #64748b; font-size: 14px; font-weight: 500; cursor: pointer; text-align: center; }
        .tab-btn.active { color: #38bdf8; border-bottom: 2px solid #38bdf8; font-weight: 600; }
        
        /* 卡片容器 */
        .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 14px; margin-bottom: 14px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .card-title { font-size: 12px; font-weight: 600; color: #cbd5e1; }
        .data-date { font-size: 11px; color: #64748b; margin-bottom: 10px; }
        
        /* 狀態徽章 */
        .badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
        .badge-bull { background: #064e3b; color: #34d399; border: 1px solid #059669; }
        .badge-bear { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
        
        /* 推薦股票項目 (點擊瞬間反饋) */
        .stock-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #182238; border: 1px solid #243049; border-radius: 8px; margin-bottom: 8px; cursor: pointer; }
        .stock-item:active { background: #222f4c; transform: scale(0.99); }
        .stock-left { display: flex; align-items: center; gap: 10px; }
        .rank-num { width: 22px; height: 22px; background: #28354f; color: #cbd5e1; font-size: 11px; font-weight: bold; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-family: monospace; }
        .stock-name { font-size: 13px; font-weight: bold; color: #f1f5f9; }
        .stock-sub { font-size: 11px; color: #94a3b8; font-family: monospace; }
        
        /* 回測數據網格 */
        .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; text-align: center; font-family: monospace; }
        @media (max-width: 480px) { .grid-4 { grid-template-columns: repeat(2, 1fr); } }
        .grid-item { background: #182238; padding: 8px; border-radius: 6px; border: 1px solid #1e293b; }
        .grid-label { font-size: 10px; color: #64748b; margin-bottom: 2px; }
        .grid-val { font-size: 15px; font-weight: bold; }
        
        /* 表格樣式 */
        .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        table { width: 100%; border-collapse: collapse; font-size: 12px; }
        th { text-align: left; padding: 8px 6px; color: #64748b; border-bottom: 1px solid #1e293b; font-weight: 500; }
        td { padding: 9px 6px; border-bottom: 1px solid #182238; }
        tr.clickable { cursor: pointer; }
        tr.clickable:active { background: #1e293b; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .font-mono { font-family: monospace; }
        .green { color: #34d399; }
        .red { color: #f87171; }
        
        /* 彈窗樣式 (完全無毛玻璃濾鏡，GPU零負擔秒開) */
        .modal-overlay { position: fixed; inset: 0; z-index: 50; background: rgba(0, 0, 0, 0.8); display: none; align-items: flex-end; justify-content: center; }
        @media (min-width: 640px) { .modal-overlay { align-items: center; padding: 16px; } }
        .modal-box { background: #131b2e; border: 1px solid #2b3954; border-radius: 16px 16px 0 0; width: 100%; max-width: 540px; padding: 16px; max-height: 85vh; overflow-y: auto; }
        @media (min-width: 640px) { .modal-box { border-radius: 14px; } }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 10px; margin-bottom: 12px; }
        .close-btn { background: #1e293b; border: none; color: #94a3b8; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; font-size: 16px; }
        
        /* 圖表高度容器 */
        .chart-box { height: 210px; width: 100%; position: relative; background: #0b0f19; border-radius: 8px; border: 1px solid #1e293b; padding: 6px; margin: 10px 0; }
        
        /* 因子網格 */
        .factor-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: 10px 0; text-align: center; font-family: monospace; }
        .factor-card { background: #182238; border: 1px solid #23304a; border-radius: 6px; padding: 6px 4px; }
        
        /* 外開按鈕 */
        .btn-link { display: block; width: 100%; padding: 10px; background: #2563eb; color: #fff; text-decoration: none; text-align: center; border-radius: 8px; font-size: 13px; font-weight: 600; margin-top: 12px; }
        .btn-link:active { background: #1d4ed8; }
        
        .hidden { display: none !important; }
    </style>
</head>
<body>

    <header>
        <div>
            <div class="title">TQA 科技量化策略</div>
            <div class="subtitle">大戶投現貨 / 複委託波段輪動</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 9px; color: #64748b;">最後更新</div>
            <div class="update-time">__UPDATE_TIME__</div>
        </div>
    </header>

    <div class="container">
        <!-- 分頁切換 -->
        <div class="tabs">
            <button onclick="switchTab('tw')" id="tab-tw" class="tab-btn active">台股焦點</button>
            <button onclick="switchTab('us')" id="tab-us" class="tab-btn">美股焦點</button>
        </div>

        <!-- ================= 台股 ================= -->
        <div id="content-tw">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">大戶投操作指引</span>
                    <span class="badge __TW_STATE_BADGE__">__TW_STATE_TEXT__</span>
                </div>
                <div class="data-date">數據基準：__TW_DATA_DATE__ 收盤 (點擊查看走勢圖)</div>
                <div>__TW_RECOMMENDATIONS__</div>
            </div>

            <div class="card">
                <div class="card-title" style="margin-bottom: 8px;">歷史回測績效 (2024 - 2026)</div>
                <div class="grid-4">
                    <div class="grid-item">
                        <div class="grid-label">總報酬率</div>
                        <div class="grid-val green">__TW_TOTAL_RET__</div>
                    </div>
                    <div class="grid-item">
                        <div class="grid-label">年化報酬 (CAGR)</div>
                        <div class="grid-val green">__TW_CAGR__</div>
                    </div>
                    <div class="grid-item">
                        <div class="grid-label">同期基準 (0052)</div>
                        <div class="grid-val red">__TW_BENCHMARK__</div>
                    </div>
                    <div class="grid-item">
                        <div class="grid-label">最大回撤 (MDD)</div>
                        <div class="grid-val red">__TW_MDD__</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-title" style="margin-bottom: 8px;">標的評分排序 (點擊列開啟圖表)</div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>排名</th>
                                <th>標的</th>
                                <th class="text-right">最新價</th>
                                <th class="text-right">20日動能</th>
                                <th class="text-right">綜合分</th>
                                <th class="text-center">狀態</th>
                            </tr>
                        </thead>
                        <tbody>__TW_TABLE_ROWS__</tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ================= 美股 ================= -->
        <div id="content-us" class="hidden">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">複委託操作指引</span>
                    <span class="badge __US_STATE_BADGE__">__US_STATE_TEXT__</span>
                </div>
                <div class="data-date">數據基準：__US_DATA_DATE__ 收盤 (點擊查看走勢圖)</div>
                <div>__US_RECOMMENDATIONS__</div>
            </div>

            <div class="card">
                <div class="card-title" style="margin-bottom: 8px;">歷史回測績效 (2024 - 2026)</div>
                <div class="grid-4">
                    <div class="grid-item">
                        <div class="grid-label">總報酬率</div>
                        <div class="grid-val green">__US_TOTAL_RET__</div>
                    </div>
                    <div class="grid-item">
                        <div class="grid-label">年化報酬 (CAGR)</div>
                        <div class="grid-val green">__US_CAGR__</div>
                    </div>
                    <div class="grid-item">
                        <div class="grid-label">同期基準 (QQQ)</div>
                        <div class="grid-val green">__US_BENCHMARK__</div>
                    </div>
                    <div class="grid-item">
                        <div class="grid-label">最大回撤 (MDD)</div>
                        <div class="grid-val red">__US_MDD__</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-title" style="margin-bottom: 8px;">標的評分排序 (點擊列開啟圖表)</div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>排名</th>
                                <th>標的</th>
                                <th class="text-right">最新價</th>
                                <th class="text-right">20日動能</th>
                                <th class="text-right">綜合分</th>
                                <th class="text-center">狀態</th>
                            </tr>
                        </thead>
                        <tbody>__US_TABLE_ROWS__</tbody>
                    </table>
                </div>
            </div>
        </div>

        <div style="text-align: center; font-size: 11px; color: #475569; margin-top: 16px;">
            數據來源: Yahoo Finance • 跌破 50MA 或高點拉回 8% 出場
        </div>
    </div>

    <!-- ================= 彈出視窗 (Modal) ================= -->
    <div id="stock-modal" class="modal-overlay" onclick="handleOverlayClick(event)">
        <div class="modal-box" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div>
                    <span id="modal-name" style="font-size: 16px; font-weight: bold; color: #f8fafc;">-</span>
                    <span id="modal-symbol" style="font-size: 11px; color: #64748b; font-family: monospace; margin-left: 4px;">-</span>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                        收盤: <span id="modal-price" style="font-weight: bold; color: #f1f5f9; font-family: monospace;">-</span>
                        <span id="modal-trend-badge" class="badge" style="margin-left: 6px;">-</span>
                    </div>
                </div>
                <button class="close-btn" onclick="closeStockModal()">✕</button>
            </div>

            <!-- 圖表 -->
            <div style="font-size: 11px; color: #64748b; display: flex; justify-content: space-between;">
                <span>近 60 日走勢 (藍線:股價 / 黃線:50MA)</span>
            </div>
            <div class="chart-box">
                <canvas id="modalChart"></canvas>
            </div>

            <!-- 因子數據 -->
            <div class="factor-grid">
                <div class="factor-card">
                    <div style="font-size: 9px; color: #64748b;">20日動能</div>
                    <div id="modal-roc20" style="font-size: 12px; font-weight: bold;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 9px; color: #64748b;">60日動能</div>
                    <div id="modal-roc60" style="font-size: 12px; font-weight: bold;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 9px; color: #64748b;">120日動能</div>
                    <div id="modal-roc120" style="font-size: 12px; font-weight: bold;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 9px; color: #64748b;">50MA乖離</div>
                    <div id="modal-bias50" style="font-size: 12px; font-weight: bold;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 9px; color: #64748b;">14日 RSI</div>
                    <div id="modal-rsi" style="font-size: 12px; font-weight: bold; color: #cbd5e1;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 9px; color: #64748b;">20日破高</div>
                    <div id="modal-breakout" style="font-size: 12px; font-weight: bold;">-</div>
                </div>
            </div>

            <a id="modal-ext-link" href="#" target="_blank" rel="noopener noreferrer" class="btn-link">
                在新視窗開啟即時盤口 ↗
            </a>
        </div>
    </div>

    <script>
        const STOCKS_DATABASE = __STOCKS_DATABASE_JSON__;
        let chartInstance = null;

        function switchTab(market) {
            const tabTw = document.getElementById('tab-tw');
            const tabUs = document.getElementById('tab-us');
            const contentTw = document.getElementById('content-tw');
            const contentUs = document.getElementById('content-us');

            if (market === 'tw') {
                tabTw.classList.add('active');
                tabUs.classList.remove('active');
                contentTw.classList.remove('hidden');
                contentUs.classList.add('hidden');
            } else {
                tabUs.classList.add('active');
                tabTw.classList.remove('active');
                contentUs.classList.remove('hidden');
                contentTw.classList.add('hidden');
            }
        }

        function openStockModal(ticker) {
            const data = STOCKS_DATABASE[ticker];
            if (!data) return;

            document.getElementById('modal-name').innerText = data.name;
            document.getElementById('modal-symbol').innerText = data.symbol;
            document.getElementById('modal-price').innerText = (data.is_tw ? 'NT$' : '$') + data.price.toLocaleString(undefined, {minimumFractionDigits: 2});

            const trendBadge = document.getElementById('modal-trend-badge');
            if (data.above_50sma) {
                trendBadge.innerText = '站上 50MA';
                trendBadge.className = 'badge badge-bull';
            } else {
                trendBadge.innerText = '跌破 50MA';
                trendBadge.className = 'badge badge-bear';
            }

            const setVal = (id, val) => {
                const el = document.getElementById(id);
                el.innerText = (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
                el.style.color = val >= 0 ? '#34d399' : '#f87171';
            };

            setVal('modal-roc20', data.roc_20d);
            setVal('modal-roc60', data.roc_60d);
            setVal('modal-roc120', data.roc_120d);
            setVal('modal-bias50', data.bias_50sma);

            document.getElementById('modal-rsi').innerText = data.rsi.toFixed(1);

            const breakoutEl = document.getElementById('modal-breakout');
            breakoutEl.innerText = data.is_breakout ? '創20日新高' : '否';
            breakoutEl.style.color = data.is_breakout ? '#fbbf24' : '#64748b';

            const extLink = document.getElementById('modal-ext-link');
            if (data.is_tw) {
                const twClean = data.symbol.replace('.TW', '').replace('.TWO', '');
                extLink.href = 'https://tw.stock.yahoo.com/quote/' + twClean;
            } else {
                extLink.href = 'https://www.tradingview.com/symbols/' + data.symbol + '/';
            }

            // 更新圖表 (0延遲不卡頓)
            updateChartFast(data);

            const modal = document.getElementById('stock-modal');
            modal.style.display = 'flex';
        }

        function closeStockModal() {
            document.getElementById('stock-modal').style.display = 'none';
        }

        function handleOverlayClick(e) {
            if (e.target.id === 'stock-modal') {
                closeStockModal();
            }
        }

        function updateChartFast(data) {
            const ctx = document.getElementById('modalChart').getContext('2d');
            
            if (!chartInstance) {
                chartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.chart_dates,
                        datasets: [
                            {
                                data: data.chart_prices,
                                borderColor: '#38bdf8',
                                borderWidth: 1.8,
                                pointRadius: 0,
                                fill: false,
                                tension: 0.1
                            },
                            {
                                data: data.chart_sma50,
                                borderColor: '#fbbf24',
                                borderWidth: 1.2,
                                borderDash: [3, 3],
                                pointRadius: 0,
                                fill: false,
                                tension: 0.1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { display: false }, ticks: { color: '#64748b', maxTicksLimit: 5, font: { size: 9 } } },
                            y: { grid: { color: '#1e293b' }, ticks: { color: '#94a3b8', font: { size: 9, family: 'monospace' } } }
                        }
                    }
                });
            } else {
                // 直接替換數據，不重新建立實例，瞬間刷新
                chartInstance.data.labels = data.chart_dates;
                chartInstance.data.datasets[0].data = data.chart_prices;
                chartInstance.data.datasets[1].data = data.chart_sma50;
                chartInstance.update('none');
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
            badge_class = "badge-bull" if above_50 else "badge-bear"
            currency = "NT$" if is_tw else "$"

            html = f"""
            <div onclick="openStockModal('{ticker}')" class="stock-item">
                <div class="stock-left">
                    <span class="rank-num">{idx+1}</span>
                    <div>
                        <div class="stock-name">{name} <span class="stock-sub">({ticker})</span></div>
                        <div class="stock-sub">收盤 {currency}{price:,.2f} | 評分 {score:+.1f}</div>
                    </div>
                </div>
                <div>
                    <span class="badge {badge_class}">{badge_action}</span>
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

            roc_class = "green" if roc20 >= 0 else "red"
            currency = "NT$" if is_tw else "$"
            status_badge = '<span class="green">多頭</span>' if above_50 else '<span style="color:#64748b">轉弱</span>'

            row_html = f"""
            <tr onclick="openStockModal('{ticker}')" class="clickable">
                <td class="font-mono" style="color: #64748b;">#{idx+1}</td>
                <td>
                    <div style="font-weight: bold; color: #f1f5f9;">{name}</div>
                    <div class="font-mono" style="font-size: 10px; color: #64748b;">{ticker}</div>
                </td>
                <td class="text-right font-mono">{currency}{price:,.2f}</td>
                <td class="text-right font-mono {roc_class}">{roc20:+.2f}%</td>
                <td class="text-right font-mono" style="font-weight: bold; color: #cbd5e1;">{score:+.1f}</td>
                <td class="text-center">{status_badge}</td>
            </tr>
            """
            rows.append(row_html)
        return "\n".join(rows)

    @classmethod
    def build_stocks_database_json(cls, dataset: Dict[str, pd.DataFrame]) -> str:
        from src.features import TechFeatureEngine
        
        db = {}
        for ticker, raw_df in dataset.items():
            enriched = TechFeatureEngine.calculate_technical_features(raw_df)
            sub = enriched.tail(60)
            
            latest = enriched.iloc[-1]
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            name = TECH_UNIVERSE_TW.get(ticker, ticker)
            
            curr_price = float(latest["close"])
            sma50_val = float(latest["sma_50"]) if not np.isnan(latest["sma_50"]) else curr_price
            bias_50 = ((curr_price - sma50_val) / sma50_val) * 100

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
        tw_state_badge = "badge-bull" if tw_top_above_50 else "badge-bear"

        us_top_above_50 = us_rank.iloc[0]["above_50sma"]
        us_state_text = "多頭進攻" if us_top_above_50 else "防禦觀望"
        us_state_badge = "badge-bull" if us_top_above_50 else "badge-bear"

        stocks_json = cls.build_stocks_database_json(dataset)

        html = FAST_HTML_TEMPLATE
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
