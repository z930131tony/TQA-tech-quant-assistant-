"""
專業看盤級自適應儀表板生成模組 (全面除錯精修版)
全面修復：
1. 彈窗標題置頂鎖定 (position: sticky)，防止滾動時標題 (股票名稱/代碼) 被削掉
2. K線與KD徹底消除左右留白與懸空，利用 setVisibleLogicalRange 精確鎖定在 [0, totalBars - 1]
3. HUD 十字準星預設顯示最新收盤數值，滑鼠移開時自動歸位，不再卡在 5 月舊日期
4. 修正 Windows 國旗 Emoji 渲染為「TW/US」破字問題，改用高質感純 CSS 徽章 (Market Pill)
5. 介面層次重新優化：左側操作指引+績效，右側科技股評分排序，下方橫跨自訂庫存風控
6. 本地 file:// 協定安全保護，避免 fetch 拋出跨域例外
"""
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, Optional
from src.config import TECH_UNIVERSE_TW
from src.portfolio import PortfolioTracker
from src.mascot_data import MASCOT_BASE64

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
        
        .container { width: 100%; max-width: 1420px; margin: 0 auto; padding: 16px 20px; }
        
        header { position: sticky; top: 0; z-index: 30; background: #131b2e; border-bottom: 1px solid #1e293b; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
        .header-left { display: flex; align-items: center; gap: 12px; }
        .logo-tag { background: #2563eb; color: #fff; font-size: 12px; font-weight: bold; padding: 3px 8px; border-radius: 4px; font-family: monospace; }
        .title { font-size: 19px; font-weight: bold; color: #f8fafc; }
        .subtitle { font-size: 13px; color: #94a3b8; }
        .update-box { text-align: right; }
        .update-label { font-size: 11px; color: #64748b; }
        .update-time { font-size: 13px; font-family: monospace; color: #cbd5e1; }
        
        .tabs { display: flex; border-bottom: 1px solid #1e293b; margin: 16px 0 20px 0; gap: 8px; }
        .tab-btn { flex: 1; max-width: 240px; padding: 12px 16px; background: none; border: none; color: #64748b; font-size: 15px; font-weight: 600; cursor: pointer; text-align: center; border-bottom: 3px solid transparent; transition: all 0.15s; }
        .tab-btn.active { color: #38bdf8; border-bottom-color: #38bdf8; }
        
        .market-pill { font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px; margin-right: 6px; font-family: monospace; display: inline-block; vertical-align: middle; }
        .tw-pill { background: #064e3b; color: #34d399; border: 1px solid #059669; }
        .us-pill { background: #1e3a8a; color: #60a5fa; border: 1px solid #2563eb; }
        
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
        td { padding: 13px 10px; border-bottom: 1px solid #182238; white-space: nowrap; }
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
        
        /* 彈窗樣式 (完全防切頭、防遮蔽、大小適配所有螢幕) */
        .modal-overlay { position: fixed; inset: 0; z-index: 50; background: rgba(0, 0, 0, 0.85); display: none; align-items: flex-end; justify-content: center; }
        @media (min-width: 768px) { .modal-overlay { align-items: center; padding: 20px; } }
        .modal-box { 
            background: #131b2e; 
            border: 1px solid #2b3954; 
            border-radius: 20px 20px 0 0; 
            width: 100%; 
            max-width: 1060px; 
            padding: 0 20px 20px 20px; 
            max-height: 94vh; 
            overflow-y: auto; 
            position: relative;
        }
        @media (min-width: 768px) { .modal-box { border-radius: 16px; padding: 0 24px 24px 24px; } }
        
        /* 關鍵：標題置頂鎖定，永遠不被滾動吃掉 */
        .modal-header { 
            position: sticky; 
            top: 0; 
            z-index: 20; 
            background: #131b2e; 
            border-bottom: 1px solid #1e293b; 
            padding: 16px 0 12px 0; 
            margin-bottom: 12px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
        }
        .close-btn { background: #1e293b; border: none; color: #94a3b8; width: 36px; height: 36px; border-radius: 50%; cursor: pointer; font-size: 20px; display: flex; align-items: center; justify-content: center; }
        .close-btn:hover { background: #334155; color: #fff; }
        
        .chart-hud { background: #0b1220; border: 1px solid #243049; border-radius: 8px; padding: 10px 14px; font-family: monospace; font-size: 13px; display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
        .hud-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
        
        .chart-box { height: 280px; width: 100%; position: relative; background: #0b0f19; border-radius: 8px 8px 0 0; border: 1px solid #1e293b; border-bottom: none; overflow: hidden; }
        @media (min-width: 768px) { .chart-box { height: 340px; } }
        
        .kd-chart-box { height: 95px; width: 100%; position: relative; background: #0b0f19; border-radius: 0 0 8px 8px; border: 1px solid #1e293b; border-top: 1px dashed #1e293b; overflow: hidden; }
        @media (min-width: 768px) { .kd-chart-box { height: 110px; } }
        
        .factor-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 14px 0; text-align: center; font-family: monospace; }
        @media (min-width: 640px) { .factor-grid { grid-template-columns: repeat(6, 1fr); } }
        .factor-card { background: #182238; border: 1px solid #23304a; border-radius: 8px; padding: 10px 6px; }
        
        .btn-link { display: block; width: 100%; padding: 12px; background: #2563eb; color: #fff; text-decoration: none; text-align: center; border-radius: 8px; font-size: 14px; font-weight: 600; margin-top: 12px; transition: background 0.15s; }
        .btn-link:hover { background: #1d4ed8; }

        /* 🐣 吉祥物 (小黃雞桌寵) 視窗邊緣巡邏樣式 */
        .mascot-container {
            position: fixed;
            bottom: 12px;
            left: 10px;
            z-index: 45;
            pointer-events: none;
            user-select: none;
            transition: transform 0.08s linear;
        }
        .mascot-avatar {
            width: 58px;
            height: 63px;
            cursor: pointer;
            pointer-events: auto;
            filter: drop-shadow(0 6px 12px rgba(0, 0, 0, 0.45));
            transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
            display: block;
        }
        .mascot-avatar:hover {
            transform: scale(1.18) !important;
        }
        .mascot-avatar:active {
            transform: scale(0.9) !important;
        }
        .mascot-bubble {
            position: absolute;
            bottom: 70px;
            left: 50%;
            transform: translateX(-50%) scale(0);
            transform-origin: bottom center;
            background: #182238;
            border: 1px solid #38bdf8;
            color: #f8fafc;
            font-size: 12px;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 12px;
            white-space: nowrap;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
            opacity: 0;
            transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
            pointer-events: none;
            z-index: 46;
        }
        .mascot-bubble::after {
            content: '';
            position: absolute;
            bottom: -6px;
            left: 50%;
            transform: translateX(-50%);
            border-width: 6px 6px 0;
            border-style: solid;
            border-color: #38bdf8 transparent transparent transparent;
        }
        .mascot-bubble.show {
            transform: translateX(-50%) scale(1);
            opacity: 1;
        }
        @media (max-width: 640px) {
            .mascot-avatar { width: 48px; height: 52px; }
            .mascot-bubble { bottom: 58px; font-size: 11px; }
        }
        
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
            <div class="update-label">數據更新 <span style="color: #34d399; font-size: 10px;">● 自動同步中</span></div>
            <div class="update-time">__UPDATE_TIME__</div>
        </div>
    </header>

    <div class="container">
        <!-- 分頁切換 -->
        <div class="tabs">
            <button onclick="switchTab('tw')" id="tab-tw" class="tab-btn active">
                <span class="market-pill tw-pill">台股</span> 核心焦點 (20檔)
            </button>
            <button onclick="switchTab('us')" id="tab-us" class="tab-btn">
                <span class="market-pill us-pill">美股</span> 核心焦點 (21檔)
            </button>
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
                        <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 12px; margin: 10px 0 12px 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                            <div style="font-size: 13px; font-weight: 600; color: #cbd5e1; display: flex; align-items: center; gap: 6px;">
                                <span>🧮 大戶投零股預算試算</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <span style="font-size: 12px; color: #94a3b8;">單檔預算: NT$</span>
                                <input type="number" id="budget-tw-input" value="30000" min="1000" step="1000" oninput="updateBudgetCalc('tw')" style="background: #182238; border: 1px solid #334155; border-radius: 6px; color: #f8fafc; font-family: monospace; font-size: 13px; padding: 4px 8px; width: 95px; text-align: right; outline: none;">
                            </div>
                        </div>
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
                                <div class="grid-label">同期基準 (0050)</div>
                                <div class="grid-val red">__TW_BENCHMARK__</div>
                            </div>
                            <div class="grid-item">
                                <div class="grid-label">最大回撤 (MDD)</div>
                                <div class="grid-val red">__TW_MDD__</div>
                            </div>
                        </div>

                        <!-- 淨值走勢圖 (Equity Curve) -->
                        <div style="margin-top: 16px; border-top: 1px dashed #1e293b; padding-top: 14px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">資產淨值曲線 vs 基準 ($100k 起始)</span>
                                <div style="display: flex; align-items: center; gap: 12px; font-size: 11px; font-family: monospace;">
                                    <span style="display: flex; align-items: center; gap: 5px; color: #38bdf8;">
                                        <span style="display: inline-block; width: 10px; height: 10px; background: #38bdf8; border-radius: 2px;"></span> 策略淨值
                                    </span>
                                    <span style="display: flex; align-items: center; gap: 5px; color: #94a3b8;">
                                        <span style="display: inline-block; width: 12px; height: 2px; background: #94a3b8; border-top: 1px dashed #94a3b8;"></span> 0050基準
                                    </span>
                                </div>
                            </div>
                            <div id="tw-equity-hud" style="font-family: monospace; font-size: 11px; color: #94a3b8; margin-bottom: 6px; min-height: 18px;"></div>
                            <div id="tw-equity-chart" style="height: 190px; width: 100%; border-radius: 8px; overflow: hidden; background: #0b0f19; border: 1px solid #182238;"></div>
                        </div>
                    </div>
                </div>

                <div>
                    <!-- 標的綜合排序 -->
                    <div class="card">
                        <div class="card-title" style="margin-bottom: 10px;">科技股評分排序 (點擊列開啟專業圖表)</div>
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

            <!-- 個人持股風控監控 (全寬卡片，一覽無遺) -->
            <div class="card" style="margin-top: 4px;">
                <div class="card-header">
                    <span class="card-title">💼 我的台股庫存與風控 (8%停利停損 / 50MA生命線)</span>
                </div>
                <div class="data-date">自動比對買進成本、波段最高價回檔與生命線支撐</div>
                __TW_PORTFOLIO__
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
                        <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 12px; margin: 10px 0 12px 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                            <div style="font-size: 13px; font-weight: 600; color: #cbd5e1; display: flex; align-items: center; gap: 6px;">
                                <span>🧮 複委託預算試算</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 6px;">
                                <span style="font-size: 12px; color: #94a3b8;">單檔預算: USD $</span>
                                <input type="number" id="budget-us-input" value="1000" min="100" step="100" oninput="updateBudgetCalc('us')" style="background: #182238; border: 1px solid #334155; border-radius: 6px; color: #f8fafc; font-family: monospace; font-size: 13px; padding: 4px 8px; width: 85px; text-align: right; outline: none;">
                            </div>
                        </div>
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

                        <!-- 淨值走勢圖 (Equity Curve) -->
                        <div style="margin-top: 16px; border-top: 1px dashed #1e293b; padding-top: 14px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">資產淨值曲線 vs 基準 ($100k 起始)</span>
                                <div style="display: flex; align-items: center; gap: 12px; font-size: 11px; font-family: monospace;">
                                    <span style="display: flex; align-items: center; gap: 5px; color: #38bdf8;">
                                        <span style="display: inline-block; width: 10px; height: 10px; background: #38bdf8; border-radius: 2px;"></span> 策略淨值
                                    </span>
                                    <span style="display: flex; align-items: center; gap: 5px; color: #94a3b8;">
                                        <span style="display: inline-block; width: 12px; height: 2px; background: #94a3b8; border-top: 1px dashed #94a3b8;"></span> QQQ基準
                                    </span>
                                </div>
                            </div>
                            <div id="us-equity-hud" style="font-family: monospace; font-size: 11px; color: #94a3b8; margin-bottom: 6px; min-height: 18px;"></div>
                            <div id="us-equity-chart" style="height: 190px; width: 100%; border-radius: 8px; overflow: hidden; background: #0b0f19; border: 1px solid #182238;"></div>
                        </div>
                    </div>
                </div>

                <div>
                    <!-- 標的綜合排序 -->
                    <div class="card">
                        <div class="card-title" style="margin-bottom: 10px;">科技股評分排序 (點擊列開啟專業圖表)</div>
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

            <!-- 個人持股風控監控 (全寬卡片，一覽無遺) -->
            <div class="card" style="margin-top: 4px;">
                <div class="card-header">
                    <span class="card-title">💼 我的美股庫存與風控 (8%停利停損 / 50MA生命線)</span>
                </div>
                <div class="data-date">自動比對買進成本、波段最高價回檔與生命線支撐</div>
                __US_PORTFOLIO__
            </div>
        </div>

        <div style="text-align: center; font-size: 13px; color: #475569; margin-top: 28px;">
            數據來源: FinMind / Yahoo Finance • 風控規則: 跌破 50MA 或高點拉回 8% 出場
        </div>
    </div>

    <!-- ================= 專業看盤彈出視窗 (Modal) ================= -->
    <div id="stock-modal" class="modal-overlay" onclick="handleOverlayClick(event)">
        <div class="modal-box" onclick="event.stopPropagation()">
            <!-- 標題欄 (Sticky 頂部鎖定，保證任何滾動下標題名稱不被吃掉) -->
            <div class="modal-header">
                <div>
                    <div style="display: flex; align-items: baseline; gap: 8px;">
                        <span id="modal-name" style="font-size: 21px; font-weight: bold; color: #f8fafc;">-</span>
                        <span id="modal-symbol" style="font-size: 13px; color: #94a3b8; font-family: monospace;">-</span>
                    </div>
                    <div style="font-size: 13px; color: #94a3b8; margin-top: 4px;">
                        最新收盤: <span id="modal-price" style="font-weight: bold; color: #f1f5f9; font-family: monospace; font-size: 14px;">-</span>
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
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; font-size:12px; color:#64748b; margin-bottom:6px;">
                <span>日 K 棒 + 20MA(紫) + 50MA生命線(黃) • <span style="color:#34d399;">▲買進</span> <span style="color:#f87171;">▼出場</span></span>
                <span>長按拖曳回溯歷史 / 雙指或滾輪縮放</span>
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

    <!-- 🐣 吉祥物桌寵 (視窗邊緣巡邏伴讀) -->
    <div id="mascot-box" class="mascot-container">
        <div id="mascot-bubble" class="mascot-bubble">摸摸我！看多不追高 🐣</div>
        <img id="mascot-img" class="mascot-avatar" onclick="petMascot()" src="data:image/png;base64,__MASCOT_BASE64__" alt="TQA 吉祥物" title="點我摸摸！">
    </div>

    <script>
        const CURRENT_BUILD_TIME = "__UPDATE_TIME__";
        const STOCKS_DATABASE = __STOCKS_DATABASE_JSON__;
        const EQUITY_CURVE_TW = __EQUITY_CURVE_TW_JSON__;
        const EQUITY_CURVE_US = __EQUITY_CURVE_US_JSON__;

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

        let twEquityChart = null;
        let usEquityChart = null;
        let usEquityChartInitialized = false;

        function initEquityChart(containerId, hudId, curveData, isTw) {
            const container = document.getElementById(containerId);
            if (!container || !curveData || !curveData.strategy || curveData.strategy.length === 0) return null;

            const chart = LightweightCharts.createChart(container, {
                width: container.clientWidth || 380,
                height: 190,
                layout: {
                    background: { color: '#0b0f19' },
                    textColor: '#64748b',
                    fontSize: 10
                },
                grid: {
                    vertLines: { color: '#131d30' },
                    horzLines: { color: '#131d30' }
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: { color: 'rgba(148, 163, 184, 0.4)', width: 1, style: 2 },
                    horzLine: { color: 'rgba(148, 163, 184, 0.4)', width: 1, style: 2 }
                },
                rightPriceScale: {
                    borderColor: '#1e293b',
                    minimumWidth: 64,
                    scaleMargins: { top: 0.1, bottom: 0.08 }
                },
                timeScale: {
                    borderColor: '#1e293b',
                    timeVisible: false,
                    fixLeftEdge: true,
                    fixRightEdge: true
                }
            });

            const strategySeries = chart.addAreaSeries({
                lineColor: '#38bdf8',
                topColor: 'rgba(56, 189, 248, 0.28)',
                bottomColor: 'rgba(56, 189, 248, 0.01)',
                lineWidth: 2,
                priceFormat: {
                    type: 'custom',
                    formatter: price => '$' + Math.round(price).toLocaleString()
                }
            });
            strategySeries.setData(curveData.strategy);

            const benchSeries = chart.addLineSeries({
                color: '#94a3b8',
                lineWidth: 1.5,
                lineStyle: 2,
                priceFormat: {
                    type: 'custom',
                    formatter: price => '$' + Math.round(price).toLocaleString()
                }
            });
            benchSeries.setData(curveData.benchmark);

            chart.timeScale().fitContent();

            const stratMap = {};
            curveData.strategy.forEach(p => stratMap[p.time] = p.value);
            const benchMap = {};
            curveData.benchmark.forEach(p => benchMap[p.time] = p.value);

            const hudEl = document.getElementById(hudId);
            const benchName = isTw ? '0050' : 'QQQ';
            const updateHud = (timeStr) => {
                if (!hudEl) return;
                const sVal = stratMap[timeStr];
                const bVal = benchMap[timeStr];
                if (sVal !== undefined && bVal !== undefined) {
                    const sRet = ((sVal / 100000 - 1) * 100).toFixed(1);
                    const bRet = ((bVal / 100000 - 1) * 100).toFixed(1);
                    const sSign = sRet >= 0 ? '+' : '';
                    const bSign = bRet >= 0 ? '+' : '';
                    const sColor = sRet >= 0 ? '#34d399' : '#f87171';
                    const bColor = bRet >= 0 ? '#34d399' : '#f87171';
                    hudEl.innerHTML = `<span>📅 ${timeStr}</span> | 策略: <b style="color:#38bdf8;">$${Math.round(sVal).toLocaleString()}</b> (<span style="color:${sColor};">${sSign}${sRet}%</span>) | ${benchName}: <b style="color:#94a3b8;">$${Math.round(bVal).toLocaleString()}</b> (<span style="color:${bColor};">${bSign}${bRet}%</span>)`;
                }
            };

            const lastItem = curveData.strategy[curveData.strategy.length - 1];
            if (lastItem) updateHud(lastItem.time);

            chart.subscribeCrosshairMove(param => {
                if (param && param.time) {
                    updateHud(param.time);
                } else if (lastItem) {
                    updateHud(lastItem.time);
                }
            });

            return chart;
        }

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
                if (twEquityChart) {
                    const w = document.getElementById('tw-equity-chart').clientWidth;
                    if (w > 0) {
                        twEquityChart.applyOptions({ width: w });
                        twEquityChart.timeScale().fitContent();
                    }
                }
                updateBudgetCalc('tw');
            } else {
                tabUs.classList.add('active');
                tabTw.classList.remove('active');
                contentUs.classList.remove('hidden');
                contentTw.classList.add('hidden');
                
                requestAnimationFrame(() => {
                    if (!usEquityChartInitialized) {
                        usEquityChart = initEquityChart('us-equity-chart', 'us-equity-hud', EQUITY_CURVE_US, false);
                        usEquityChartInitialized = true;
                    } else if (usEquityChart) {
                        const w = document.getElementById('us-equity-chart').clientWidth;
                        if (w > 0) {
                            usEquityChart.applyOptions({ width: w });
                            usEquityChart.timeScale().fitContent();
                        }
                    }
                });
                updateBudgetCalc('us');
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

            // 預設 HUD 顯示最新最後一根 K 棒
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

            // 重置彈窗滾動條置頂，確保標題完美展現
            const modalBox = modal.querySelector('.modal-box');
            if (modalBox) modalBox.scrollTop = 0;

            // 確保 DOM 渲染並取得確切寬度後繪製
            requestAnimationFrame(() => {
                setTimeout(() => {
                    renderTradingViewCharts(data);
                }, 30);
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
            const mainHeight = isDesktop ? 340 : 280;
            const kdHeight = isDesktop ? 110 : 95;

            // 核心配置：鎖定邊界、消除任何無效留白
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
                    scaleMargins: { top: 0.08, bottom: 0.08 }
                },
                timeScale: {
                    borderColor: '#1e293b',
                    timeVisible: false,
                    rightOffset: 2,
                    fixLeftEdge: true,
                    fixRightEdge: true
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

            // 標註歷史回測買賣點訊號 (綠色買進 ▲ / 紅色出場或停損 ▼)
            if (data.markers && data.markers.length > 0) {
                candleSeries.setMarkers(data.markers);
            }

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
            volumeSeries.setData(data.candles.map(c => ({
                time: c.time,
                value: c.v,
                color: c.close >= c.open ? 'rgba(52, 211, 153, 0.35)' : 'rgba(248, 113, 113, 0.35)'
            })));

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

            // 4. 十字準星連動與 HUD (滑鼠移開自動還原最新收盤價)
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
                if (param && param.time) {
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
                } else {
                    const last = data.candles[data.candles.length - 1];
                    updateHUDByItem({
                        time: last.time,
                        open: last.open,
                        high: last.high,
                        low: last.low,
                        close: last.close,
                        sma20: data.sma20.length ? data.sma20[data.sma20.length - 1].value : null,
                        sma50: data.sma50.length ? data.sma50[data.sma50.length - 1].value : null,
                        k: data.kd_k.length ? data.kd_k[data.kd_k.length - 1].value : null,
                        d: data.kd_d.length ? data.kd_d[data.kd_d.length - 1].value : null
                    }, data.is_tw);
                }
            };

            mainChart.subscribeCrosshairMove(handleMove);
            kdChart.subscribeCrosshairMove(handleMove);

            // 預設視野聚焦最近 90 根 K 棒 (~4.5 個月)，視覺飽滿清晰，亦可隨意往左拖曳回溯全部歷史買賣點
            const totalBars = data.candles.length;
            const defaultBars = 90;
            const startBar = Math.max(0, totalBars - defaultBars);
            mainChart.timeScale().setVisibleLogicalRange({ from: startBar, to: totalBars - 1 });
        }

        window.addEventListener('resize', () => {
            if (mainChart && kdChart && currentStockData) {
                const w = document.getElementById('mainChartContainer').clientWidth;
                if (w > 0) {
                    mainChart.applyOptions({ width: w });
                    kdChart.applyOptions({ width: w });
                    const totalBars = currentStockData.candles.length;
                    const startBar = Math.max(0, totalBars - 90);
                    mainChart.timeScale().setVisibleLogicalRange({ from: startBar, to: totalBars - 1 });
                }
            }
            if (twEquityChart) {
                const w = document.getElementById('tw-equity-chart').clientWidth;
                if (w > 0) {
                    twEquityChart.applyOptions({ width: w });
                    twEquityChart.timeScale().fitContent();
                }
            }
            if (usEquityChart && usEquityChartInitialized) {
                const w = document.getElementById('us-equity-chart').clientWidth;
                if (w > 0) {
                    usEquityChart.applyOptions({ width: w });
                    usEquityChart.timeScale().fitContent();
                }
            }
        });

        // ================= 大戶投 / 複委託預算試算 (前端即時連動 localStorage) =================
        function updateBudgetCalc(market) {
            const inputId = 'budget-' + market + '-input';
            const inputEl = document.getElementById(inputId);
            if (!inputEl) return;
            let budget = parseFloat(inputEl.value);
            if (isNaN(budget) || budget <= 0) {
                budget = (market === 'tw') ? 30000 : 1000;
            }
            try {
                localStorage.setItem('tqa_budget_' + market, budget);
            } catch (e) {}

            const items = document.querySelectorAll('.stock-item[data-market="' + market + '"]');
            items.forEach(item => {
                const price = parseFloat(item.getAttribute('data-price') || '0');
                const sharesEl = item.querySelector('.calc-shares');
                if (sharesEl && price > 0) {
                    const shares = Math.max(1, Math.floor(budget / price));
                    sharesEl.innerText = shares.toLocaleString();
                }
            });
        }

        function initBudgetCalc() {
            ['tw', 'us'].forEach(market => {
                const inputId = 'budget-' + market + '-input';
                const inputEl = document.getElementById(inputId);
                if (inputEl) {
                    try {
                        const saved = localStorage.getItem('tqa_budget_' + market);
                        if (saved) {
                            inputEl.value = saved;
                        }
                    } catch (e) {}
                    updateBudgetCalc(market);
                }
            });
        }

        // 頁面載入時初始化台股淨值圖與預算試算
        window.addEventListener('DOMContentLoaded', () => {
            twEquityChart = initEquityChart('tw-equity-chart', 'tw-equity-hud', EQUITY_CURVE_TW, true);
            initBudgetCalc();
        });

        // ================= 自動熱更新機制 (背景定時檢查 + 喚醒比對) =================
        let isCheckingUpdate = false;
        async function checkCloudUpdates() {
            if (isCheckingUpdate) return;
            // 本地 file:// 協定略過 fetch 避免瀏覽器安全性報錯
            if (!window.location.protocol.startsWith('http')) return;
            
            isCheckingUpdate = true;
            try {
                const url = window.location.href.split('?')[0] + '?t=' + Date.now();
                const resp = await fetch(url, {
                    method: 'GET',
                    cache: 'no-cache',
                    headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
                });
                if (resp.ok) {
                    const text = await resp.text();
                    const match = text.match(/const CURRENT_BUILD_TIME = "([^"]+)";/);
                    if (match && match[1] && match[1] !== CURRENT_BUILD_TIME) {
                        console.log('[TQA] 偵測到雲端排程已發布新數據 (' + match[1] + ')，自動無縫刷新中...');
                        window.location.reload();
                    }
                }
            } catch (e) {
                // 網路中斷或離線時靜默略過
            } finally {
                isCheckingUpdate = false;
            }
        }

        // 1. 網頁開啟掛著時，每 3 分鐘背景自動檢查一次
        setInterval(checkCloudUpdates, 3 * 60 * 1000);

        // 2. 當手機解鎖、或電腦從其他分頁切換回來時，立刻喚醒檢查一次
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                checkCloudUpdates();
            }
        });

        // ================= 🐣 吉祥物 (小黃雞桌寵) 視窗邊緣巡邏邏輯 =================
        const mascotBox = document.getElementById('mascot-box');
        const mascotImg = document.getElementById('mascot-img');
        const mascotBubble = document.getElementById('mascot-bubble');

        let posX = 20;
        let speed = 1.0;
        let direction = 1; // 1: 向右, -1: 向左
        let isIdling = false;
        let bubbleTimer = null;
        let stepCount = 0;

        const MASCOT_QUOTES = [
            "跌破 50MA 絕不戀戰！",
            "自高點回檔 8% 移動停利停損！",
            "抱牢趨勢大波段，不被盤中洗掉 🐣",
            "今天你的自訂持股都在多頭軌道嗎？",
            "大戶投現貨 / 零股安心定錨！",
            "我是 TQA 守護小吉祥物，陪你看盤！",
            "看多不追高，拉回守均線 🚀",
            "摸摸我！祝你今天手上的股票漲不停 🎉"
        ];

        function wanderMascot() {
            if (!isIdling && mascotBox && mascotImg) {
                const maxX = window.innerWidth - (window.innerWidth < 640 ? 65 : 80);
                posX += speed * direction;
                stepCount++;

                // 碰到邊緣自動轉向
                if (posX >= maxX) {
                    posX = maxX;
                    direction = -1;
                    mascotImg.style.transform = 'scaleX(-1)';
                } else if (posX <= 15) {
                    posX = 15;
                    direction = 1;
                    mascotImg.style.transform = 'scaleX(1)';
                }

                // 隨機停下來休息發呆一下
                if (Math.random() < 0.003 && stepCount > 120) {
                    stepCount = 0;
                    isIdling = true;
                    mascotImg.style.transition = 'transform 0.4s ease';
                    mascotImg.style.transform = (direction === 1 ? 'scaleX(1)' : 'scaleX(-1)') + ' scale(1.06, 0.94)';
                    setTimeout(() => {
                        isIdling = false;
                        mascotImg.style.transform = (direction === 1 ? 'scaleX(1)' : 'scaleX(-1)');
                    }, 2200 + Math.random() * 2000);
                }

                // 走路微搖擺動畫 (Waddle)
                const waddle = Math.sin(Date.now() / 150) * 4.5;
                mascotBox.style.transform = `translateX(${posX}px)`;
                if (!isIdling) {
                    mascotImg.style.transform = (direction === 1 ? 'scaleX(1)' : 'scaleX(-1)') + ` rotate(${waddle}deg)`;
                }
            }

            requestAnimationFrame(wanderMascot);
        }

        // 點擊互動跳躍 + 說話
        function petMascot() {
            if (!mascotImg || !mascotBubble) return;
            mascotImg.style.transition = 'transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1)';
            mascotImg.style.transform = (direction === 1 ? 'scaleX(1)' : 'scaleX(-1)') + ' translateY(-26px) scale(1.22)';
            
            const quote = MASCOT_QUOTES[Math.floor(Math.random() * MASCOT_QUOTES.length)];
            mascotBubble.innerText = quote;
            mascotBubble.classList.add('show');

            setTimeout(() => {
                mascotImg.style.transform = (direction === 1 ? 'scaleX(1)' : 'scaleX(-1)');
            }, 300);

            clearTimeout(bubbleTimer);
            bubbleTimer = setTimeout(() => {
                mascotBubble.classList.remove('show');
            }, 3500);
        }

        // 啟動巡邏
        requestAnimationFrame(wanderMascot);
    </script>
</body>
</html>
"""

class WebDashboardGenerator:
    @classmethod
    def select_top_recommendations(cls, rank_df: pd.DataFrame) -> pd.DataFrame:
        """
        篩選 Top 3 推薦卡片標的：
        優先篩選 above_50sma == True 的健康多頭標的，並按 composite_score (score) 由高至低排序。
        若該市場符合條件之標的不滿 3 檔，取全部合格者，並由其餘標的按評分由高至低依序補足至 3 檔。
        """
        if rank_df is None or rank_df.empty:
            return pd.DataFrame()
            
        score_col = "score" if "score" in rank_df.columns else "composite_score"
        
        # 1. 優先篩選站上 50MA 的多頭標的，並按評分由高至低排序
        bullish = rank_df[rank_df["above_50sma"] == True].copy() if "above_50sma" in rank_df.columns else pd.DataFrame()
        if not bullish.empty and score_col in bullish.columns:
            bullish = bullish.sort_values(by=score_col, ascending=False)
        
        if len(bullish) >= 3:
            return bullish.head(3).reset_index(drop=True)
            
        # 2. 若不滿 3 檔，取所有合格標的，並由其餘標的 (按評分降序) 補足至 3 檔
        selected_tickers = set(bullish["ticker"]) if not bullish.empty else set()
        remaining = rank_df[~rank_df["ticker"].isin(selected_tickers)]
        if score_col in remaining.columns:
            remaining = remaining.sort_values(by=score_col, ascending=False)
        needed = 3 - len(bullish)
        fillers = remaining.head(needed)
        
        res = pd.concat([bullish, fillers], ignore_index=True)
        return res

    # 保持舊介面相容性
    select_recommendations = select_top_recommendations

    @staticmethod
    def build_recommendation_html(top_df: pd.DataFrame, is_tw: bool, is_market_bull: bool = True) -> str:
        items = []
        for idx, row in top_df.iterrows():
            ticker = row["ticker"]
            name = TECH_UNIVERSE_TW.get(ticker, ticker) if is_tw else ticker
            price = float(row.get("price", row.get("close", 0.0)))
            roc20 = float(row.get("roc_20d", row.get("roc_20", 0.0)))
            score = float(row.get("score", row.get("composite_score", 0.0)))
            above50 = bool(row.get("above_50sma", False))
            prefix = "NT$" if is_tw else "$"
            market_tag = "tw" if is_tw else "us"
            stop_price = price * 0.92
            stop_price_str = f"NT${stop_price:,.1f}" if is_tw else f"${stop_price:,.2f}"
            
            roc_color = "#34d399" if roc20 >= 0 else "#f87171"
            roc_sign = "+" if roc20 >= 0 else ""
            
            # 【關鍵修復】：若標的跌破 50MA，或大盤處於保守防禦且個股破線，加上醒目橘紅標籤
            warning_badge_html = ""
            if not above50:
                warning_badge_html = """
                <div style="margin-top: 4px;">
                    <span style="background: rgba(234, 88, 12, 0.18); border: 1px solid rgba(249, 115, 22, 0.7); color: #fb923c; font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 4px; display: inline-block;">⚠️ 跌破50MA・觀望勿追</span>
                </div>
                """
            
            item_html = f"""
            <div onclick="openStockModal('{ticker}')" class="stock-item" data-price="{price}" data-market="{market_tag}">
                <div class="stock-left">
                    <span class="rank-num">#{idx + 1}</span>
                    <div>
                        <div class="stock-name">{name}</div>
                        <div class="stock-sub">{ticker} • 綜合分: {score:.1f}</div>
                        <div style="margin-top: 4px; font-size: 11px; font-family: monospace; color: #94a3b8;">
                            建議買進: <span class="calc-shares" style="color: #38bdf8; font-weight: bold;">--</span> 股 • <span style="color: #cbd5e1;">-8%停損:</span> <span style="color: #f87171; font-weight: 600;">{stop_price_str}</span>
                        </div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: bold; font-family: monospace; font-size: 15px;">{prefix}{price:,.2f}</div>
                    <div style="color: {roc_color}; font-size: 13px; font-family: monospace;">{roc_sign}{roc20:.2f}%</div>
                    {warning_badge_html}
                </div>
            </div>
            """
            items.append(item_html)
        return "".join(items)

    @staticmethod
    def build_portfolio_html(evaluated_positions: list, market_type: str = "TW") -> str:
        """產生網頁儀表板中的持股卡片 HTML (美股支援小數點後兩位損益)"""
        filtered = [p for p in evaluated_positions if (p.get("is_tw", False) if market_type == "TW" else not p.get("is_tw", False))]
        if not filtered:
            return """
            <div style="background: #182238; border: 1px dashed #243049; border-radius: 10px; padding: 20px; text-align: center; color: #64748b;">
                目前尚未設定自訂持股。可透過 Google Sheets 雲端試算表或 <code>portfolio.json</code> 新增您的庫存標的。
            </div>
            """

        rows = []
        for p in filtered:
            is_tw = p.get("is_tw", False)
            prefix = "NT$" if is_tw else "$"
            ret_pct = p.get("return_pct", 0.0)
            ret_color = "#34d399" if ret_pct >= 0 else "#f87171"
            pnl_val = p.get("unrealized_pnl", 0.0)
            
            # 美股未實現損益金額保留小數點後兩位 (例如 +$13.14 / -$11.65)，台股維持整數顯示 (例如 +NT$5,000 / -NT$5,000)
            pnl_sign = "+" if pnl_val >= 0 else "-"
            if is_tw:
                pnl_str = f"({pnl_sign}NT${abs(pnl_val):,.0f})"
            else:
                pnl_str = f"({pnl_sign}${abs(pnl_val):,.2f})"
            
            # 股數格式化：整數顯示 int，非整數顯示有效位數 :g
            shares_val = p.get("shares", 0)
            shares_str = f"{int(shares_val)}" if float(shares_val).is_integer() else f"{shares_val:g}"

            badge_html = f'<span class="badge badge-bear" style="background:#450a0a; color:#f87171; border:1px solid #991b1b;">⚠️ {p.get("alert_text", "")}</span>' if p.get("has_alert") else '<span class="badge badge-bull">✅ 續抱中</span>'
            
            row = f"""
            <tr class="clickable" onclick="openStockModal('{p.get('ticker')}')">
                <td>
                    <div style="font-weight:bold; color:#f1f5f9;">{p.get('name')}</div>
                    <div style="font-size:12px; color:#64748b; font-family:monospace;">{p.get('ticker')} ({shares_str} 股)</div>
                </td>
                <td class="text-right font-mono">{prefix}{p.get('cost_price', 0.0):,.2f}</td>
                <td class="text-right font-mono" style="font-weight:bold;">{prefix}{p.get('curr_price', 0.0):,.2f}</td>
                <td class="text-right font-mono" style="color:{ret_color}; font-weight:bold;">
                    {'+' if ret_pct >= 0 else ''}{ret_pct:.2f}%<br>
                    <span style="font-size:11px; opacity:0.85;">{pnl_str}</span>
                </td>
                <td class="text-right font-mono desktop-only" style="color: {'#f87171' if p.get('drawdown_from_peak', 0.0) <= -8 else '#94a3b8'};">
                    {p.get('drawdown_from_peak', 0.0):.1f}%
                </td>
                <td class="text-center">{badge_html}</td>
            </tr>
            """
            rows.append(row)

        table_html = f"""
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>持股標的</th>
                        <th class="text-right">買進成本</th>
                        <th class="text-right">現價</th>
                        <th class="text-right">未實現損益</th>
                        <th class="text-right desktop-only">自高點回檔</th>
                        <th class="text-center">狀態 / 風控</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
        return table_html

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

    @staticmethod
    def build_equity_curve_data(perf_df: pd.DataFrame, dataset: Dict[str, pd.DataFrame], bench_ticker: str) -> dict:
        """生成策略資產淨值與對應基準 ETF (0050/QQQ) 之等權起點對比序列"""
        if perf_df.empty:
            return {"strategy": [], "benchmark": []}
        
        bench_df = dataset.get(bench_ticker)
        b_base = None
        if bench_df is not None and not bench_df.empty:
            sub_b = bench_df.loc[bench_df.index >= perf_df.index[0]]
            if not sub_b.empty:
                b_base = float(sub_b.iloc[0]["close"])
                
        strategy_series = []
        bench_series = []
        last_b_val = 100000.0

        for dt, row in perf_df.iterrows():
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            s_val = round(float(row["portfolio_value"]), 2)
            strategy_series.append({"time": date_str, "value": s_val})

            if bench_df is not None and dt in bench_df.index and b_base and b_base > 0:
                curr_b_price = float(bench_df.loc[dt, "close"])
                last_b_val = round(100000.0 * (curr_b_price / b_base), 2)
            bench_series.append({"time": date_str, "value": last_b_val})

        return {"strategy": strategy_series, "benchmark": bench_series}

    @classmethod
    def build_stocks_database_json(
        cls, 
        dataset: Dict[str, pd.DataFrame],
        tw_trades_df: Optional[pd.DataFrame] = None,
        us_trades_df: Optional[pd.DataFrame] = None
    ) -> str:
        """打包歷史數據與回測買賣點供 TradingView 渲染"""
        from src.features import TechFeatureEngine
        db = {}
        for ticker, raw_df in dataset.items():
            enriched = TechFeatureEngine.calculate_technical_features(raw_df)
            sub = enriched.iloc[60:] if len(enriched) > 60 else enriched
            
            latest = enriched.iloc[-1]
            is_tw = (".TW" in ticker) or (".TWO" in ticker)
            name = TECH_UNIVERSE_TW.get(ticker, ticker)
            
            curr_price = float(latest["close"])
            sma50_val = float(latest["sma_50"]) if not np.isnan(latest["sma_50"]) else curr_price
            bias_50 = ((curr_price - sma50_val) / sma50_val) * 100

            candles = []
            sma20_list = []
            sma50_list = []
            kd_k_list = []
            kd_d_list = []

            for d, row in sub.iterrows():
                o = round(float(row["open"]), 2)
                h = round(float(row["high"]), 2)
                l = round(float(row["low"]), 2)
                c = round(float(row["close"]), 2)
                v = int(row["volume"])

                # 【關鍵修復】：過濾掉 volume <= 0 或 close <= 0 的無效交易日 (防範幽靈 K 棒)
                if v <= 0 or c <= 0:
                    continue

                date_str = d.strftime("%Y-%m-%d")
                candles.append({"time": date_str, "open": o, "high": h, "low": l, "close": c, "v": v})

                if not np.isnan(row.get("sma_20", np.nan)):
                    sma20_list.append({"time": date_str, "value": round(float(row["sma_20"]), 2)})
                if not np.isnan(row.get("sma_50", np.nan)):
                    sma50_list.append({"time": date_str, "value": round(float(row["sma_50"]), 2)})
                if not np.isnan(row.get("k_9", np.nan)):
                    kd_k_list.append({"time": date_str, "value": round(float(row["k_9"]), 2)})
                if not np.isnan(row.get("d_9", np.nan)):
                    kd_d_list.append({"time": date_str, "value": round(float(row["d_9"]), 2)})

            # 提取該標的之歷史買賣點標註
            trades_df = tw_trades_df if is_tw else us_trades_df
            markers = []
            candle_times = set(c["time"] for c in candles)
            if trades_df is not None and not trades_df.empty and "ticker" in trades_df.columns:
                stock_trades = trades_df[trades_df["ticker"] == ticker]
                for _, tr in stock_trades.iterrows():
                    tr_date = tr["date"]
                    d_str = tr_date.strftime("%Y-%m-%d") if hasattr(tr_date, "strftime") else str(tr_date)[:10]
                    if d_str not in candle_times:
                        continue
                    
                    action = tr["action"]
                    px = tr["price"]
                    if action == "BUY":
                        markers.append({
                            "time": d_str,
                            "position": "belowBar",
                            "color": "#34d399",
                            "shape": "arrowUp",
                            "text": f"買 {px:,.1f}"
                        })
                    else:
                        pnl_str = tr.get("pnl_pct", "")
                        is_stop = "停損" in str(tr.get("reason", ""))
                        tag = "停損" if is_stop else "賣"
                        txt = f"{tag} {px:,.1f}"
                        if pnl_str:
                            txt += f" ({pnl_str})"
                        markers.append({
                            "time": d_str,
                            "position": "aboveBar",
                            "color": "#f87171",
                            "shape": "arrowDown",
                            "text": txt
                        })
            markers.sort(key=lambda m: m["time"])

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
                "sma20": sma20_list,
                "sma50": sma50_list,
                "kd_k": kd_k_list,
                "kd_d": kd_d_list,
                "markers": markers
            }

        return json.dumps(db, ensure_ascii=False)

    @classmethod
    def generate_html(cls, dataset: Dict[str, pd.DataFrame], tw_rank: pd.DataFrame, us_rank: pd.DataFrame, tw_backtest: dict, us_backtest: dict, output_path: str):
        import pytz
        tw_tz = pytz.timezone("Asia/Taipei")
        now_str = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M")
        tw_date = tw_rank.iloc[0].get("data_date", "-") if not tw_rank.empty else "-"
        us_date = us_rank.iloc[0].get("data_date", "-") if not us_rank.empty else "-"

        # 1. 操作指示卡與 Top 3 推薦卡片 (優先篩選 50MA 之上且動能 > 0 標的)
        tw_raw_top3 = tw_rank.head(3)
        tw_market_bull = (tw_raw_top3["above_50sma"].sum() >= 2) if not tw_raw_top3.empty else False
        tw_state_badge = "badge-bull" if tw_market_bull else "badge-bear"
        tw_state_text = "多頭攻擊：持股續抱 / 換股" if tw_market_bull else "保守防禦：留意停利 / 停損"
        tw_top3_candidates = cls.select_recommendations(tw_rank)
        tw_recom_html = cls.build_recommendation_html(tw_top3_candidates, is_tw=True, is_market_bull=tw_market_bull)

        us_raw_top3 = us_rank.head(3)
        us_bull_count = us_raw_top3["above_50sma"].sum() if not us_raw_top3.empty else 0
        qqq_df = dataset.get("QQQ")
        qqq_bull = True
        if qqq_df is not None and not qqq_df.empty:
            q_close = float(qqq_df["close"].iloc[-1])
            q_sma200 = float(qqq_df["close"].rolling(200).mean().iloc[-1])
            qqq_bull = (q_close >= q_sma200)
        us_market_bull = (us_bull_count >= 2 and qqq_bull)
        us_state_badge = "badge-bull" if us_market_bull else "badge-bear"
        us_state_text = "多頭攻擊：持股續抱 / 換股" if us_market_bull else "保守防禦：留意停利 / 停損"
        us_top3_candidates = cls.select_recommendations(us_rank)
        us_recom_html = cls.build_recommendation_html(us_top3_candidates, is_tw=False, is_market_bull=us_market_bull)

        # 2. 歷史回測數據
        tw_tot = f"{tw_backtest.get('total_return_pct', tw_backtest.get('total_return', 0.0)):+.2f}%"
        tw_cagr = f"{tw_backtest.get('cagr_pct', tw_backtest.get('cagr', 0.0)):+.2f}%"
        tw_bench = f"{tw_backtest.get('benchmark_return', 0.0):+.2f}%"
        tw_mdd = f"{tw_backtest.get('max_drawdown_pct', tw_backtest.get('max_drawdown', 0.0)):.2f}%"

        us_tot = f"{us_backtest.get('total_return_pct', us_backtest.get('total_return', 0.0)):+.2f}%"
        us_cagr = f"{us_backtest.get('cagr_pct', us_backtest.get('cagr', 0.0)):+.2f}%"
        us_bench = f"{us_backtest.get('benchmark_return', 0.0):+.2f}%"
        us_mdd = f"{us_backtest.get('max_drawdown_pct', us_backtest.get('max_drawdown', 0.0)):.2f}%"

        # 3. 排序表格
        tw_table_rows = cls.build_table_rows_html(tw_rank, is_tw=True)
        us_table_rows = cls.build_table_rows_html(us_rank, is_tw=False)

        # 4. 個人持股風控監控 (Portfolio & Risk Tracker)
        portfolio_positions = PortfolioTracker.evaluate_portfolio(dataset)
        tw_portfolio_html = cls.build_portfolio_html(portfolio_positions, "TW")
        us_portfolio_html = cls.build_portfolio_html(portfolio_positions, "US")

        # 5. 回測淨值曲線數據 (Area Chart vs Benchmark)
        tw_equity_curve = cls.build_equity_curve_data(tw_backtest.get("perf_df", pd.DataFrame()), dataset, "0050.TW")
        us_equity_curve = cls.build_equity_curve_data(us_backtest.get("perf_df", pd.DataFrame()), dataset, "QQQ")
        tw_equity_json = json.dumps(tw_equity_curve, ensure_ascii=False)
        us_equity_json = json.dumps(us_equity_curve, ensure_ascii=False)

        # 6. TradingView 交互數據 (含 K 線買賣點標註)
        stocks_db_json = cls.build_stocks_database_json(
            dataset,
            tw_trades_df=tw_backtest.get("trades_df"),
            us_trades_df=us_backtest.get("trades_df")
        )

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

        html = html.replace("__EQUITY_CURVE_TW_JSON__", tw_equity_json)
        html = html.replace("__EQUITY_CURVE_US_JSON__", us_equity_json)
        html = html.replace("__STOCKS_DATABASE_JSON__", stocks_db_json)
        html = html.replace("__MASCOT_BASE64__", MASCOT_BASE64)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[成功] 專業看盤儀表板生成完成：{output_path}")
