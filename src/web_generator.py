"""
專業看盤級自適應儀表板生成模組
特色：
1. 完整修復 TradingView Lightweight Charts 鋪滿與對齊問題 (無右側空白、不擠在左側、KD嚴格連動)
2. 響應式優化：手機窄螢幕與電腦寬螢幕皆具備大圖視角與清晰排版
3. 整合個人持股與 8% 移動停利停損風控追蹤模組 (Portfolio & Risk Tracker)
"""
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, Optional
from src.config import TECH_UNIVERSE_TW
from src.portfolio import PortfolioTracker

RESPONSIVE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TQA 科技量化策略儀表板</title>
    <!-- TradingView Lightweight Charts -->
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body { background-color: #0b0f19; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.5; padding-bottom: 60px; }
        
        .container { width: 100%; max-width: 1400px; margin: 0 auto; padding: 16px 20px; }
        
        header { position: sticky; top: 0; z-index: 30; background: #131b2e; border-bottom: 1px solid #1e293b; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
        .header-left { display: flex; align-items: center; gap: 12px; }
        .logo-tag { background: #2563eb; color: #fff; font-size: 12px; font-weight: bold; padding: 3px 8px; border-radius: 4px; font-family: monospace; }
        .title { font-size: 19px; font-weight: bold; color: #f8fafc; }
        .subtitle { font-size: 13px; color: #94a3b8; }
        .update-box { text-align: right; }
        .update-label { font-size: 11px; color: #64748b; }
        .update-time { font-size: 13px; font-family: monospace; color: #cbd5e1; }
        
        .tabs { display: flex; border-bottom: 1px solid #1e293b; margin: 16px 0 20px 0; }
        .tab-btn { flex: 1; max-width: 240px; padding: 14px; background: none; border: none; color: #64748b; font-size: 16px; font-weight: 500; cursor: pointer; text-align: center; }
        .tab-btn.active { color: #38bdf8; border-bottom: 3px solid #38bdf8; font-weight: bold; }
        
        .desktop-grid { display: flex; flex-direction: column; gap: 20px; }
        @media (min-width: 992px) {
            .desktop-grid { display: grid; grid-template-columns: 460px 1fr; gap: 24px; align-items: start; }
        }
        
        .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 14px; padding: 18px 20px; margin-bottom: 20px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .card-title { font-size: 15px; font-weight: bold; color: #cbd5e1; display: flex; align-items: center; gap: 8px; }
        .data-date { font-size: 12px; color: #64748b; margin-bottom: 14px; }
        
        .badge { font-size: 12px; padding: 4px 10px; border-radius: 5px; font-weight: 600; font-family: monospace; }
        .badge-bull { background: #064e3b; color: #34d399; border: 1px solid #059669; }
        .badge-bear { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
        
        .stock-item { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: #182238; border: 1px solid #243049; border-radius: 10px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s; }
        .stock-item:hover { background: #1f2b45; border-color: #38bdf8; }
        .stock-item:active { transform: scale(0.99); }
        .stock-left { display: flex; align-items: center; gap: 14px; }
        .rank-num { width: 30px; height: 30px; background: #28354f; color: #cbd5e1; font-size: 13px; font-weight: bold; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-family: monospace; }
        .stock-name { font-size: 15px; font-weight: bold; color: #f1f5f9; }
        .stock-sub { font-size: 13px; color: #94a3b8; font-family: monospace; margin-top: 2px; }
        
        .grid-4 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; text-align: center; font-family: monospace; }
        @media (min-width: 480px) and (max-width: 959px) { .grid-4 { grid-template-columns: repeat(4, 1fr); } }
        .grid-item { background: #182238; padding: 12px; border-radius: 8px; border: 1px solid #1e293b; }
        .grid-label { font-size: 11px; color: #64748b; margin-bottom: 4px; }
        .grid-val { font-size: 17px; font-weight: bold; }
        
        .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th { text-align: left; padding: 12px 10px; color: #64748b; border-bottom: 1px solid #1e293b; font-weight: 600; white-space: nowrap; }
        td { padding: 14px 10px; border-bottom: 1px solid #182238; white-space: nowrap; }
        tr.clickable { cursor: pointer; transition: background 0.1s; }
        tr.clickable:hover { background: #1a253c; }
        tr.clickable:active { background: #202e4a; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .font-mono { font-family: monospace; }
        .green { color: #34d399; }
        .red { color: #f87171; }
        
        .desktop-only { display: none; }
        @media (min-width: 768px) { .desktop-only { display: table-cell; } }
        
        /* 彈窗樣式 (大螢幕寬廣、手機滿版好滑) */
        .modal-overlay { position: fixed; inset: 0; z-index: 50; background: rgba(0, 0, 0, 0.85); display: none; align-items: flex-end; justify-content: center; }
        @media (min-width: 768px) { .modal-overlay { align-items: center; padding: 24px; } }
        .modal-box { background: #131b2e; border: 1px solid #2b3954; border-radius: 20px 20px 0 0; width: 100%; max-width: 1120px; padding: 20px 24px; max-height: 96vh; overflow-y: auto; }
        @media (min-width: 768px) { .modal-box { border-radius: 18px; padding: 24px 28px; } }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 12px; margin-bottom: 12px; }
        .close-btn { background: #1e293b; border: none; color: #94a3b8; width: 36px; height: 36px; border-radius: 50%; cursor: pointer; font-size: 20px; display: flex; align-items: center; justify-content: center; }
        .close-btn:hover { background: #334155; color: #fff; }
        
        .chart-hud { background: #0b1220; border: 1px solid #243049; border-radius: 8px; padding: 10px 14px; font-family: monospace; font-size: 13px; display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
        .hud-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
        
        .chart-box { height: 320px; width: 100%; position: relative; background: #0b0f19; border-radius: 8px 8px 0 0; border: 1px solid #1e293b; border-bottom: none; overflow: hidden; }
        @media (min-width: 768px) { .chart-box { height: 410px; } }
        
        .kd-chart-box { height: 115px; width: 100%; position: relative; background: #0b0f19; border-radius: 0 0 8px 8px; border: 1px solid #1e293b; border-top: 1px dashed #1e293b; overflow: hidden; }
        @media (min-width: 768px) { .kd-chart-box { height: 135px; } }
        
        .factor-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 14px 0; text-align: center; font-family: monospace; }
        @media (min-width: 640px) { .factor-grid { grid-template-columns: repeat(6, 1fr); } }
        .factor-card { background: #182238; border: 1px solid #23304a; border-radius: 8px; padding: 10px 6px; }
        
        .btn-link { display: block; width: 100%; padding: 14px; background: #2563eb; color: #fff; text-decoration: none; text-align: center; border-radius: 8px; font-size: 15px; font-weight: 600; margin-top: 14px; transition: background 0.15s; }
        .btn-link:hover { background: #1d4ed8; }
        
        .hidden { display: none !important; }
    </style>
</head>
<body>

    <header>
        <div class="header-left">
            <span class="logo-tag">QUANT</span>
            <div>
                <div class="title">TQA 科技量化策略</div>
                <div class="subtitle">大戶投現貨 / 複委託波段輪動 (41檔台美科技精選)</div>
            </div>
        </div>
        <div class="update-box">
            <div class="update-label">數據更新</div>
            <div class="update-time">__UPDATE_TIME__</div>
        </div>
    </header>

    <div class="container">
        <!-- 分頁切換 -->
        <div class="tabs">
            <button onclick="switchTab('tw')" id="tab-tw" class="tab-btn active">🇹🇼 台股焦點 (20檔)</button>
            <button onclick="switchTab('us')" id="tab-us" class="tab-btn">🇺🇸 美股焦點 (21檔)</button>
        </div>

        <!-- ================= 台股 ================= -->
        <div id="content-tw">
            <div class="desktop-grid">
                <div>
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">大戶投操作指引</span>
                            <span class="badge __TW_STATE_BADGE__">__TW_STATE_TEXT__</span>
                        </div>
                        <div class="data-date">數據基準：__TW_DATA_DATE__ 收盤 (點擊查看專業K線與KD)</div>
                        <div>__TW_RECOMMENDATIONS__</div>
                    </div>

                    <div class="card">
                        <div class="card-title" style="margin-bottom: 10px;">歷史回測績效 (2024 - 2026)</div>
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
                </div>

                <div>
                    <!-- 個人持股風控監控 -->
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">💼 我的台股庫存與風控 (8%停利停損 / 50MA)</span>
                        </div>
                        <div class="data-date">自動比對買進成本、波段最高價回檔與生命線支撐</div>
                        __TW_PORTFOLIO__
                    </div>

                    <!-- 標的綜合排序 -->
                    <div class="card">
                        <div class="card-title" style="margin-bottom: 10px;">科技股評分排序 (點擊列開啟圖表)</div>
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>排名</th>
                                        <th>標的名稱</th>
                                        <th class="text-right">最新價</th>
                                        <th class="text-right">20日動能</th>
                                        <th class="text-right desktop-only">60日動能</th>
                                        <th class="text-right desktop-only">KD (9,3)</th>
                                        <th class="text-right">綜合分</th>
                                        <th class="text-center">狀態</th>
                                    </tr>
                                </thead>
                                <tbody>__TW_TABLE_ROWS__</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ================= 美股 ================= -->
        <div id="content-us" class="hidden">
            <div class="desktop-grid">
                <div>
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">複委託操作指引</span>
                            <span class="badge __US_STATE_BADGE__">__US_STATE_TEXT__</span>
                        </div>
                        <div class="data-date">數據基準：__US_DATA_DATE__ 收盤 (點擊查看專業K線與KD)</div>
                        <div>__US_RECOMMENDATIONS__</div>
                    </div>

                    <div class="card">
                        <div class="card-title" style="margin-bottom: 10px;">歷史回測績效 (2024 - 2026)</div>
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
                </div>

                <div>
                    <!-- 個人持股風控監控 -->
                    <div class="card">
                        <div class="card-header">
                            <span class="card-title">💼 我的美股庫存與風控 (8%停利停損 / 50MA)</span>
                        </div>
                        <div class="data-date">自動比對買進成本、波段最高價回檔與生命線支撐</div>
                        __US_PORTFOLIO__
                    </div>

                    <!-- 標的綜合排序 -->
                    <div class="card">
                        <div class="card-title" style="margin-bottom: 10px;">科技股評分排序 (點擊列開啟圖表)</div>
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>排名</th>
                                        <th>標的名稱</th>
                                        <th class="text-right">最新價</th>
                                        <th class="text-right">20日動能</th>
                                        <th class="text-right desktop-only">60日動能</th>
                                        <th class="text-right desktop-only">KD (9,3)</th>
                                        <th class="text-right">綜合分</th>
                                        <th class="text-center">狀態</th>
                                    </tr>
                                </thead>
                                <tbody>__US_TABLE_ROWS__</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div style="text-align: center; font-size: 13px; color: #475569; margin-top: 28px;">
            數據來源: Yahoo Finance • 風控規則: 跌破 50MA 或高點拉回 8% 出場
        </div>
    </div>

    <!-- ================= 專業看盤彈出視窗 (Modal) ================= -->
    <div id="stock-modal" class="modal-overlay" onclick="handleOverlayClick(event)">
        <div class="modal-box" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div>
                    <span id="modal-name" style="font-size: 20px; font-weight: bold; color: #f8fafc;">-</span>
                    <span id="modal-symbol" style="font-size: 13px; color: #64748b; font-family: monospace; margin-left: 6px;">-</span>
                    <div style="font-size: 14px; color: #94a3b8; margin-top: 4px;">
                        最新收盤: <span id="modal-price" style="font-weight: bold; color: #f1f5f9; font-family: monospace;">-</span>
                        <span id="modal-trend-badge" class="badge" style="margin-left: 8px;">-</span>
                    </div>
                </div>
                <button class="close-btn" onclick="closeStockModal()">✕</button>
            </div>

            <!-- 即時 HUD -->
            <div id="chart-hud" class="chart-hud">
                <div class="hud-row">
                    <span id="hud-date" style="color: #cbd5e1; font-weight: bold;">📅 日期: --</span>
                    <span id="hud-ohlc" style="color: #cbd5e1;">開: -- 高: -- 低: -- 收: --</span>
                </div>
                <div class="hud-row" style="border-top: 1px dashed #1e293b; padding-top: 5px;">
                    <span id="hud-ma" style="color: #fbbf24;">20MA: -- | 50MA: --</span>
                    <span id="hud-kd" style="color: #38bdf8;">K: -- | D: --</span>
                </div>
            </div>

            <!-- K 線主圖 + KD 子圖 (完全零間隙嚴密對齊) -->
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#64748b; margin-bottom:6px;">
                <span>日 K 棒 + 20MA(紫) + 50MA生命線(黃)</span>
                <span>長按拖曳查閱數據 / 雙指或滾輪縮放</span>
            </div>
            
            <div id="mainChartContainer" class="chart-box"></div>
            <div id="kdChartContainer" class="kd-chart-box"></div>

            <!-- 六大因子數據卡片 -->
            <div class="factor-grid">
                <div class="factor-card">
                    <div style="font-size: 11px; color: #64748b;">20日動能</div>
                    <div id="modal-roc20" style="font-size: 14px; font-weight: bold;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 11px; color: #64748b;">60日動能</div>
                    <div id="modal-roc60" style="font-size: 14px; font-weight: bold;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 11px; color: #64748b;">50MA乖離</div>
                    <div id="modal-bias50" style="font-size: 14px; font-weight: bold;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 11px; color: #64748b;">RSI (14)</div>
                    <div id="modal-rsi" style="font-size: 14px; font-weight: bold; color: #cbd5e1;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 11px; color: #64748b;">K (9)</div>
                    <div id="modal-k9" style="font-size: 14px; font-weight: bold; color: #38bdf8;">-</div>
                </div>
                <div class="factor-card">
                    <div style="font-size: 11px; color: #64748b;">D (9)</div>
                    <div id="modal-d9" style="font-size: 14px; font-weight: bold; color: #f97316;">-</div>
                </div>
            </div>

            <a id="modal-ext-link" href="#" target="_blank" rel="noopener noreferrer" class="btn-link">
                開啟外部詳細報價 ↗
            </a>
        </div>
    </div>

    <script>
        const STOCKS_DATABASE = __STOCKS_DATABASE_JSON__;
        let mainChart = null;
        let kdChart = null;
        let candleSeries = null;
        let volumeSeries = null;
        let sma20Series = null;
        let sma50Series = null;
        let kSeries = null;
        let dSeries = null;
        let currentStockData = null;
        let isSyncingRange = false;

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

        function updateHUDByItem(item, isTw) {
            const prefix = isTw ? 'NT$' : '$';
            document.getElementById('hud-date').innerText = '📅 ' + (item.time || '--');
            
            const oStr = item.open !== undefined ? prefix + item.open.toFixed(2) : '--';
            const hStr = item.high !== undefined ? prefix + item.high.toFixed(2) : '--';
            const lStr = item.low !== undefined ? prefix + item.low.toFixed(2) : '--';
            const cStr = item.close !== undefined ? prefix + item.close.toFixed(2) : '--';
            
            const cColor = (item.close >= item.open) ? '#34d399' : '#f87171';
            document.getElementById('hud-ohlc').innerHTML = 
                '開: ' + oStr + ' 高: ' + hStr + ' 低: ' + lStr + ' 收: <span style="color:' + cColor + '; font-weight:bold;">' + cStr + '</span>';

            const sma20Val = item.sma20 ? prefix + item.sma20.toFixed(2) : '--';
            const sma50Val = item.sma50 ? prefix + item.sma50.toFixed(2) : '--';
            document.getElementById('hud-ma').innerHTML = 
                '<span style="color:#c084fc;">20MA: ' + sma20Val + '</span> | <span style="color:#fbbf24;">50MA: ' + sma50Val + '</span>';

            const kVal = item.k !== undefined && item.k !== null ? item.k.toFixed(1) : '--';
            const dVal = item.d !== undefined && item.d !== null ? item.d.toFixed(1) : '--';
            document.getElementById('hud-kd').innerHTML = 
                '<span style="color:#38bdf8;">K: ' + kVal + '</span> | <span style="color:#f97316;">D: ' + dVal + '</span>';
        }

        function openStockModal(ticker) {
            const data = STOCKS_DATABASE[ticker];
            if (!data) return;
            currentStockData = data;

            document.getElementById('modal-name').innerText = data.name;
            document.getElementById('modal-symbol').innerText = data.symbol;
            document.getElementById('modal-price').innerText = (data.is_tw ? 'NT$' : '$') + data.price.toLocaleString(undefined, {minimumFractionDigits: 2});

            const trendBadge = document.getElementById('modal-trend-badge');
            if (data.above_50sma) {
                trendBadge.innerText = '站上 50MA (多頭)';
                trendBadge.className = 'badge badge-bull';
            } else {
                trendBadge.innerText = '跌破 50MA (弱勢)';
                trendBadge.className = 'badge badge-bear';
            }

            const setVal = (id, val) => {
                const el = document.getElementById(id);
                el.innerText = (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
                el.style.color = val >= 0 ? '#34d399' : '#f87171';
            };

            setVal('modal-roc20', data.roc_20d);
            setVal('modal-roc60', data.roc_60d);
            setVal('modal-bias50', data.bias_50sma);
            document.getElementById('modal-rsi').innerText = data.rsi.toFixed(1);
            document.getElementById('modal-k9').innerText = data.latest_k.toFixed(1);
            document.getElementById('modal-d9').innerText = data.latest_d.toFixed(1);

            const extLink = document.getElementById('modal-ext-link');
            if (data.is_tw) {
                const twClean = data.symbol.replace('.TW', '').replace('.TWO', '');
                extLink.href = 'https://tw.stock.yahoo.com/quote/' + twClean;
            } else {
                extLink.href = 'https://www.tradingview.com/symbols/' + data.symbol + '/';
            }

            const lastCandle = data.candles[data.candles.length - 1];
            updateHUDByItem({
                time: lastCandle.time,
                open: lastCandle.open,
                high: lastCandle.high,
                low: lastCandle.low,
                close: lastCandle.close,
                sma20: data.sma20.length ? data.sma20[data.sma20.length - 1].value : null,
                sma50: data.sma50.length ? data.sma50[data.sma50.length - 1].value : null,
                k: data.kd_k.length ? data.kd_k[data.kd_k.length - 1].value : null,
                d: data.kd_d.length ? data.kd_d[data.kd_d.length - 1].value : null
            }, data.is_tw);

            const modal = document.getElementById('stock-modal');
            modal.style.display = 'flex';

            // 等待 DOM 展開完成後取得真實寬度渲染圖表
            requestAnimationFrame(() => {
                setTimeout(() => {
                    renderTradingViewCharts(data);
                }, 40);
            });
        }

        function closeStockModal() {
            document.getElementById('stock-modal').style.display = 'none';
        }

        function handleOverlayClick(e) {
            if (e.target.id === 'stock-modal') {
                closeStockModal();
            }
        }

        function renderTradingViewCharts(data) {
            const mainContainer = document.getElementById('mainChartContainer');
            const kdContainer = document.getElementById('kdChartContainer');

            mainContainer.innerHTML = '';
            kdContainer.innerHTML = '';

            const containerWidth = mainContainer.clientWidth || 600;
            const isDesktop = window.innerWidth >= 768;
            const mainHeight = isDesktop ? 410 : 320;
            const kdHeight = isDesktop ? 135 : 115;

            const commonOptions = {
                layout: {
                    background: { color: '#0b0f19' },
                    textColor: '#94a3b8',
                    fontSize: 11
                },
                grid: {
                    vertLines: { color: '#182238' },
                    horzLines: { color: '#182238' }
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: { color: 'rgba(148, 163, 184, 0.45)', width: 1, style: 2 },
                    horzLine: { color: 'rgba(148, 163, 184, 0.45)', width: 1, style: 2 }
                },
                rightPriceScale: {
                    borderColor: '#1e293b',
                    minimumWidth: 72,
                    scaleMargins: { top: 0.1, bottom: 0.1 }
                },
                timeScale: {
                    borderColor: '#1e293b',
                    timeVisible: false,
                    rightOffset: 3,
                    barSpacing: 8,
                    minBarSpacing: 3
                }
            };

            // 1. 建立 K 線主圖
            mainChart = LightweightCharts.createChart(mainContainer, {
                ...commonOptions,
                width: containerWidth,
                height: mainHeight
            });

            candleSeries = mainChart.addCandlestickSeries({
                upColor: '#34d399',
                downColor: '#f87171',
                borderVisible: false,
                wickUpColor: '#34d399',
                wickDownColor: '#f87171'
            });
            candleSeries.setData(data.candles);

            sma20Series = mainChart.addLineSeries({
                color: '#c084fc',
                lineWidth: 1.5,
                crosshairMarkerVisible: false
            });
            sma20Series.setData(data.sma20);

            sma50Series = mainChart.addLineSeries({
                color: '#fbbf24',
                lineWidth: 2,
                crosshairMarkerVisible: false
            });
            sma50Series.setData(data.sma50);

            volumeSeries = mainChart.addHistogramSeries({
                priceFormat: { type: 'volume' },
                priceScaleId: '',
                scaleMargins: { top: 0.82, bottom: 0 }
            });
            volumeSeries.setData(data.volume);

            // 2. 建立 KD 指標子圖
            kdChart = LightweightCharts.createChart(kdContainer, {
                ...commonOptions,
                width: containerWidth,
                height: kdHeight,
                timeScale: {
                    ...commonOptions.timeScale,
                    visible: false
                }
            });

            const upperRef = kdChart.addLineSeries({ color: 'rgba(148, 163, 184, 0.25)', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });
            const lowerRef = kdChart.addLineSeries({ color: 'rgba(148, 163, 184, 0.25)', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false });
            upperRef.setData(data.candles.map(c => ({ time: c.time, value: 80 })));
            lowerRef.setData(data.candles.map(c => ({ time: c.time, value: 20 })));

            kSeries = kdChart.addLineSeries({ color: '#38bdf8', lineWidth: 1.8, crosshairMarkerVisible: false });
            kSeries.setData(data.kd_k);

            dSeries = kdChart.addLineSeries({ color: '#f97316', lineWidth: 1.8, crosshairMarkerVisible: false });
            dSeries.setData(data.kd_d);

            // 3. 雙向同步鎖 (水平滾動/縮放 100% 嚴密對齊)
            mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                if (isSyncingRange || !range) return;
                isSyncingRange = true;
                kdChart.timeScale().setVisibleLogicalRange(range);
                isSyncingRange = false;
            });

            kdChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                if (isSyncingRange || !range) return;
                isSyncingRange = true;
                mainChart.timeScale().setVisibleLogicalRange(range);
                isSyncingRange = false;
            });

            // 4. 十字準星連動與 HUD
            const candleMap = {};
            data.candles.forEach(c => candleMap[c.time] = c);
            const sma20Map = {};
            data.sma20.forEach(s => sma20Map[s.time] = s.value);
            const sma50Map = {};
            data.sma50.forEach(s => sma50Map[s.time] = s.value);
            const kMap = {};
            data.kd_k.forEach(k => kMap[k.time] = k.value);
            const dMap = {};
            data.kd_d.forEach(d => dMap[d.time] = d.value);

            const handleMove = param => {
                if (param.time) {
                    const c = candleMap[param.time];
                    if (c) {
                        updateHUDByItem({
                            time: c.time,
                            open: c.open,
                            high: c.high,
                            low: c.low,
                            close: c.close,
                            sma20: sma20Map[param.time] || null,
                            sma50: sma50Map[param.time] || null,
                            k: kMap[param.time] || null,
                            d: dMap[param.time] || null
                        }, data.is_tw);
                    }
                }
            };

            mainChart.subscribeCrosshairMove(handleMove);
            kdChart.subscribeCrosshairMove(handleMove);

            // 關鍵：呼叫 fitContent() 讓近半年 K 棒自適應鋪滿畫面，不留右側黑洞！
            mainChart.timeScale().fitContent();
            kdChart.timeScale().fitContent();
        }

        window.addEventListener('resize', () => {
            if (mainChart && kdChart && currentStockData) {
                const w = document.getElementById('mainChartContainer').clientWidth;
                if (w > 0) {
                    mainChart.applyOptions({ width: w });
                    kdChart.applyOptions({ width: w });
                    mainChart.timeScale().fitContent();
                    kdChart.timeScale().fitContent();
                }
            }
        });
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
            name = TECH_UNIVERSE_TW.get(ticker, ticker) if is_tw else ticker
            price = row.get("price", row.get("close", 0.0))
            roc20 = row.get("roc_20d", row.get("roc_20", 0.0))
            score = row.get("score", row.get("composite_score", 0.0))
            prefix = "NT$" if is_tw else "$"
            
            roc_color = "#34d399" if roc20 >= 0 else "#f87171"
            roc_sign = "+" if roc20 >= 0 else ""
            
            item_html = f"""
            <div onclick="openStockModal('{ticker}')" class="stock-item">
                <div class="stock-left">
                    <span class="rank-num">#{idx + 1}</span>
                    <div>
                        <div class="stock-name">{name}</div>
                        <div class="stock-sub">{ticker} • 綜合分: {score:.1f}</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: bold; font-family: monospace; font-size: 15px;">{prefix}{price:,.2f}</div>
                    <div style="color: {roc_color}; font-size: 13px; font-family: monospace;">{roc_sign}{roc20:.2f}%</div>
                </div>
            </div>
            """
            items.append(item_html)
        return "".join(items)

    @staticmethod
    def build_table_rows_html(df: pd.DataFrame, is_tw: bool) -> str:
        rows = []
        for idx, row in df.iterrows():
            ticker = row["ticker"]
            name = TECH_UNIVERSE_TW.get(ticker, ticker) if is_tw else ticker
            price = row.get("price", row.get("close", 0.0))
            roc20 = row.get("roc_20d", row.get("roc_20", 0.0))
            roc60 = row.get("roc_60d", row.get("roc_60", 0.0))
            k9 = row.get("k9", row.get("k_9", 50.0))
            d9 = row.get("d9", row.get("d_9", 50.0))
            score = row.get("score", row.get("composite_score", 0.0))
            above50 = row["above_50sma"]
            prefix = "NT$" if is_tw else "$"

            roc20_color = "green" if roc20 >= 0 else "red"
            roc60_color = "green" if roc60 >= 0 else "red"
            badge_html = '<span class="badge badge-bull">站上50MA</span>' if above50 else '<span class="badge badge-bear">跌破50MA</span>'

            row_html = f"""
            <tr onclick="openStockModal('{ticker}')" class="clickable">
                <td class="font-mono text-center">#{idx + 1}</td>
                <td>
                    <span style="font-weight: bold; color: #f1f5f9;">{name}</span>
                    <span style="color: #64748b; font-size: 12px; margin-left: 4px; font-family: monospace;">{ticker}</span>
                </td>
                <td class="text-right font-mono" style="font-weight: bold;">{prefix}{price:,.2f}</td>
                <td class="text-right font-mono {roc20_color}">{(('+' if roc20 >= 0 else '') + f'{roc20:.2f}%')}</td>
                <td class="text-right font-mono desktop-only {roc60_color}">{(('+' if roc60 >= 0 else '') + f'{roc60:.2f}%')}</td>
                <td class="text-right font-mono desktop-only" style="color: #38bdf8;">{k9:.1f} / {d9:.1f}</td>
                <td class="text-right font-mono" style="font-weight: bold; color: #38bdf8;">{score:.1f}</td>
                <td class="text-center">{badge_html}</td>
            </tr>
            """
            rows.append(row_html)
        return "".join(rows)

    @classmethod
    def build_stocks_database_json(cls, dataset: Dict[str, pd.DataFrame]) -> str:
        """打包近 120 交易日 (約半年最適觀測窗口) 的歷史數據供 TradingView 渲染"""
        from src.features import TechFeatureEngine
        db = {}
        for ticker, raw_df in dataset.items():
            enriched = TechFeatureEngine.calculate_technical_features(raw_df)
            # 取近 120 交易日 (半年足量歷史數據，使 fitContent 鋪滿時 K 棒粗細舒適約 8px)
            sub = enriched.tail(120)
            
            latest = enriched.iloc[-1]
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            name = TECH_UNIVERSE_TW.get(ticker, ticker)
            
            curr_price = float(latest["close"])
            sma50_val = float(latest["sma_50"]) if not np.isnan(latest["sma_50"]) else curr_price
            bias_50 = ((curr_price - sma50_val) / sma50_val) * 100

            candles = []
            volumes = []
            sma20_list = []
            sma50_list = []
            kd_k_list = []
            kd_d_list = []

            for d, row in sub.iterrows():
                date_str = d.strftime("%Y-%m-%d")
                o = round(float(row["open"]), 2)
                h = round(float(row["high"]), 2)
                l = round(float(row["low"]), 2)
                c = round(float(row["close"]), 2)
                v = int(row["volume"])

                candles.append({"time": date_str, "open": o, "high": h, "low": l, "close": c})
                volumes.append({
                    "time": date_str,
                    "value": v,
                    "color": "rgba(52, 211, 153, 0.35)" if c >= o else "rgba(248, 113, 113, 0.35)"
                })

                if not np.isnan(row.get("sma_20", np.nan)):
                    sma20_list.append({"time": date_str, "value": round(float(row["sma_20"]), 2)})
                if not np.isnan(row.get("sma_50", np.nan)):
                    sma50_list.append({"time": date_str, "value": round(float(row["sma_50"]), 2)})
                if not np.isnan(row.get("k_9", np.nan)):
                    kd_k_list.append({"time": date_str, "value": round(float(row["k_9"]), 2)})
                if not np.isnan(row.get("d_9", np.nan)):
                    kd_d_list.append({"time": date_str, "value": round(float(row["d_9"]), 2)})

            db[ticker] = {
                "ticker": ticker,
                "name": name,
                "symbol": ticker,
                "is_tw": is_tw,
                "price": curr_price,
                "above_50sma": bool(latest["above_50sma"]),
                "roc_20d": round(float(latest["roc_20"]), 2) if not np.isnan(latest["roc_20"]) else 0.0,
                "roc_60d": round(float(latest["roc_60"]), 2) if not np.isnan(latest["roc_60"]) else 0.0,
                "bias_50sma": round(bias_50, 2),
                "rsi": round(float(latest["rsi_14"]), 1) if not np.isnan(latest["rsi_14"]) else 50.0,
                "latest_k": round(float(latest["k_9"]), 1) if not np.isnan(latest["k_9"]) else 50.0,
                "latest_d": round(float(latest["d_9"]), 1) if not np.isnan(latest["d_9"]) else 50.0,
                "candles": candles,
                "volume": volumes,
                "sma20": sma20_list,
                "sma50": sma50_list,
                "kd_k": kd_k_list,
                "kd_d": kd_d_list
            }

        return json.dumps(db, ensure_ascii=False)

    @classmethod
    def generate_html(cls, dataset: Dict[str, pd.DataFrame], tw_rank: pd.DataFrame, us_rank: pd.DataFrame, tw_backtest: dict, us_backtest: dict, output_path: str):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        tw_date = tw_rank.iloc[0].get("data_date", "-") if not tw_rank.empty else "-"
        us_date = us_rank.iloc[0].get("data_date", "-") if not us_rank.empty else "-"

        # 1. 操作指示卡
        tw_top3 = tw_rank.head(3)
        tw_market_bull = (tw_top3["above_50sma"].sum() >= 2)
        tw_state_badge = "badge-bull" if tw_market_bull else "badge-bear"
        tw_state_text = "多頭攻擊：持股續抱 / 換股" if tw_market_bull else "保守防禦：留意停利 / 停損"
        tw_recom_html = cls.build_recommendation_html(tw_top3, is_tw=True)

        us_top3 = us_rank.head(3)
        us_market_bull = (us_top3["above_50sma"].sum() >= 2)
        us_state_badge = "badge-bull" if us_market_bull else "badge-bear"
        us_state_text = "多頭攻擊：持股續抱 / 換股" if us_market_bull else "保守防禦：留意停利 / 停損"
        us_recom_html = cls.build_recommendation_html(us_top3, is_tw=False)

        # 2. 歷史回測數據
        tw_tot = f"{tw_backtest.get('total_return', 0.0):+.2f}%"
        tw_cagr = f"{tw_backtest.get('cagr', 0.0):+.2f}%"
        tw_bench = f"{tw_backtest.get('benchmark_return', 0.0):+.2f}%"
        tw_mdd = f"{tw_backtest.get('max_drawdown', 0.0):.2f}%"

        us_tot = f"{us_backtest.get('total_return', 0.0):+.2f}%"
        us_cagr = f"{us_backtest.get('cagr', 0.0):+.2f}%"
        us_bench = f"{us_backtest.get('benchmark_return', 0.0):+.2f}%"
        us_mdd = f"{us_backtest.get('max_drawdown', 0.0):.2f}%"

        # 3. 排序表格
        tw_table_rows = cls.build_table_rows_html(tw_rank, is_tw=True)
        us_table_rows = cls.build_table_rows_html(us_rank, is_tw=False)

        # 4. 個人持股風控監控 (Portfolio & Risk Tracker)
        portfolio_positions = PortfolioTracker.evaluate_portfolio(dataset)
        tw_portfolio_html = PortfolioTracker.generate_portfolio_html(portfolio_positions, "TW")
        us_portfolio_html = PortfolioTracker.generate_portfolio_html(portfolio_positions, "US")

        # 5. TradingView 交互數據
        stocks_db_json = cls.build_stocks_database_json(dataset)

        # 替換模板
        html = RESPONSIVE_HTML_TEMPLATE
        html = html.replace("__UPDATE_TIME__", now_str)
        html = html.replace("__TW_DATA_DATE__", str(tw_date))
        html = html.replace("__US_DATA_DATE__", str(us_date))
        html = html.replace("__TW_STATE_BADGE__", tw_state_badge)
        html = html.replace("__TW_STATE_TEXT__", tw_state_text)
        html = html.replace("__TW_RECOMMENDATIONS__", tw_recom_html)
        html = html.replace("__US_STATE_BADGE__", us_state_badge)
        html = html.replace("__US_STATE_TEXT__", us_state_text)
        html = html.replace("__US_RECOMMENDATIONS__", us_recom_html)

        html = html.replace("__TW_TOTAL_RET__", tw_tot)
        html = html.replace("__TW_CAGR__", tw_cagr)
        html = html.replace("__TW_BENCHMARK__", tw_bench)
        html = html.replace("__TW_MDD__", tw_mdd)

        html = html.replace("__US_TOTAL_RET__", us_tot)
        html = html.replace("__US_CAGR__", us_cagr)
        html = html.replace("__US_BENCHMARK__", us_bench)
        html = html.replace("__US_MDD__", us_mdd)

        html = html.replace("__TW_TABLE_ROWS__", tw_table_rows)
        html = html.replace("__US_TABLE_ROWS__", us_table_rows)

        html = html.replace("__TW_PORTFOLIO__", tw_portfolio_html)
        html = html.replace("__US_PORTFOLIO__", us_portfolio_html)

        html = html.replace("__STOCKS_DATABASE_JSON__", stocks_db_json)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[成功] 專業看盤儀表板生成完成：{output_path}")
