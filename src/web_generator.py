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
        
        .container { width: 100%; max-width: 1440px; margin: 0 auto; padding: 16px 20px; }
        
        header { position: sticky; top: 0; z-index: 30; background: rgba(19, 27, 46, 0.92); backdrop-filter: blur(12px); border-bottom: 1px solid #1e293b; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
        .header-left { display: flex; align-items: center; gap: 12px; }
        .logo-tag { background: #2563eb; color: #fff; font-size: 12px; font-weight: bold; padding: 3px 8px; border-radius: 4px; font-family: monospace; letter-spacing: 0.5px; }
        .title { font-size: 19px; font-weight: bold; color: #f8fafc; }
        .subtitle { font-size: 13px; color: #94a3b8; }
        .update-box { text-align: right; }
        .update-label { font-size: 11px; color: #64748b; }
        .update-time { font-size: 13px; font-family: monospace; color: #cbd5e1; }
        
        /* 標籤導覽 (Tabs) */
        .tabs { display: flex; border-bottom: 1px solid #1e293b; margin: 16px 0 20px 0; gap: 8px; }
        .tab-btn { flex: 1; max-width: 260px; padding: 12px 18px; background: none; border: none; color: #64748b; font-size: 15px; font-weight: 600; cursor: pointer; text-align: center; border-bottom: 3px solid transparent; transition: all 0.15s; }
        .tab-btn.active { color: #38bdf8; border-bottom-color: #38bdf8; }
        
        .market-pill { font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 4px; margin-right: 6px; font-family: monospace; display: inline-block; vertical-align: middle; }
        .tw-pill { background: #064e3b; color: #34d399; border: 1px solid #059669; }
        .us-pill { background: #1e3a8a; color: #60a5fa; border: 1px solid #2563eb; }
        
        /* 頂部大盤狀態列 */
        .market-status-bar {
            background: linear-gradient(90deg, #131b2e 0%, #17233d 100%);
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            font-weight: 600;
        }
        .status-title { color: #94a3b8; }
        .status-date { font-size: 12px; color: #64748b; font-weight: normal; margin-left: 6px; }

        /* 策略四大績效指標卡片 */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        @media (min-width: 768px) {
            .kpi-grid {
                grid-template-columns: repeat(4, 1fr);
                gap: 16px;
            }
        }
        .kpi-card {
            background: #131b2e;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 14px 18px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.15s, border-color 0.15s;
        }
        .kpi-card:hover {
            border-color: #38bdf8;
            transform: translateY(-2px);
        }
        .kpi-label {
            font-size: 12px;
            color: #94a3b8;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .kpi-val {
            font-size: 22px;
            font-weight: bold;
            font-family: monospace;
            letter-spacing: -0.5px;
            margin-bottom: 2px;
        }
        .kpi-sub {
            font-size: 11px;
            color: #64748b;
        }

        /* 雙欄決策戰情室 (今日操作指引 + AI 多空對抗) */
        .decision-grid {
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (min-width: 992px) {
            .decision-grid {
                display: grid;
                grid-template-columns: 460px 1fr;
                gap: 24px;
                align-items: stretch;
            }
        }

        /* 雙欄深度行情與淨值 (排序總表 + 資產淨值走勢) */
        .deepdive-grid {
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (min-width: 992px) {
            .deepdive-grid {
                display: grid;
                grid-template-columns: 1.15fr 0.85fr;
                gap: 24px;
                align-items: stretch;
            }
        }

        /* 通用卡片容器 */
        .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 14px; padding: 18px 20px; margin-bottom: 20px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .card-title { font-size: 15px; font-weight: bold; color: #cbd5e1; display: flex; align-items: center; gap: 8px; }
        .data-date { font-size: 12px; color: #64748b; margin-bottom: 14px; }
        
        .badge { font-size: 12px; padding: 4px 10px; border-radius: 5px; font-weight: 600; font-family: monospace; }
        .badge-bull { background: #064e3b; color: #34d399; border: 1px solid #059669; }
        .badge-bear { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
        
        /* 推薦標的列表 */
        .stock-item { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: #182238; border: 1px solid #243049; border-radius: 10px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s; }
        .stock-item:hover { background: #1f2b45; border-color: #38bdf8; }
        .stock-item:active { transform: scale(0.99); }
        .stock-left { display: flex; align-items: center; gap: 14px; }
        .rank-num { width: 30px; height: 30px; background: #28354f; color: #cbd5e1; font-size: 13px; font-weight: bold; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-family: monospace; }
        .stock-name { font-size: 15px; font-weight: bold; color: #f1f5f9; }
        .stock-sub { font-size: 13px; color: #94a3b8; font-family: monospace; margin-top: 2px; }

        /* 表格搜尋與快篩工具列 */
        .table-toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 12px;
        }
        .search-box {
            position: relative;
            flex: 1;
            min-width: 180px;
            max-width: 280px;
        }
        .search-icon {
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 12px;
            color: #64748b;
            pointer-events: none;
        }
        .search-input {
            width: 100%;
            background: #182238;
            border: 1px solid #2d3b55;
            border-radius: 8px;
            padding: 7px 10px 7px 30px;
            font-size: 12px;
            color: #f1f5f9;
            outline: none;
            transition: border-color 0.15s;
        }
        .search-input:focus {
            border-color: #38bdf8;
            box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.15);
        }
        .filter-group {
            display: flex;
            gap: 6px;
        }
        .filter-btn {
            background: #182238;
            border: 1px solid #2d3b55;
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .filter-btn:hover {
            color: #f8fafc;
            border-color: #475569;
        }
        .filter-btn.active {
            background: #2563eb;
            color: #fff;
            border-color: #3b82f6;
        }

        /* 滾動鎖定表頭 (Sticky Table Header) */
        .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .table-scrollable {
            max-height: 520px;
            overflow-y: auto;
            border-radius: 8px;
            border: 1px solid #1e293b;
        }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th { text-align: left; padding: 12px 10px; color: #64748b; border-bottom: 1px solid #1e293b; font-weight: 600; white-space: nowrap; }
        .table-scrollable thead th {
            position: sticky;
            top: 0;
            z-index: 5;
            background: #151e33;
            box-shadow: 0 1px 0 #1e293b;
        }
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

        /* 策略淨值圖例與備註卡片 */
        .chart-legend {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 11px;
            font-family: monospace;
        }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .legend-strat { color: #38bdf8; }
        .legend-bench { color: #94a3b8; }
        .strat-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #38bdf8;
            border-radius: 2px;
        }
        .bench-line {
            display: inline-block;
            width: 12px;
            height: 2px;
            background: #94a3b8;
            border-top: 1px dashed #94a3b8;
        }
        .equity-hud-text {
            font-family: monospace;
            font-size: 11px;
            color: #94a3b8;
            margin-bottom: 6px;
            min-height: 18px;
        }
        .equity-chart-box {
            height: 230px;
            width: 100%;
            border-radius: 8px;
            overflow: hidden;
            background: #0b0f19;
            border: 1px solid #182238;
        }
        .strategy-notes {
            margin-top: 14px;
            border-top: 1px dashed #1e293b;
            padding-top: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .note-pill {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            background: #182238;
            border: 1px solid #23304a;
            border-radius: 8px;
            padding: 8px 10px;
            font-size: 12px;
            color: #cbd5e1;
            line-height: 1.4;
        }
        .note-icon {
            font-size: 14px;
            flex-shrink: 0;
            margin-top: 1px;
        }

        /* 🤖 TradingAgents AI 多空對抗辯論卡片 */
        .debate-card {
            background: #182238;
            border: 1px solid #28354f;
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 12px;
            transition: border-color 0.15s;
        }
        .debate-card:hover {
            border-color: #3b82f6;
        }
        .debate-card:last-child {
            margin-bottom: 0;
        }
        .debate-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: wrap;
            gap: 8px;
        }
        .debate-stock-title {
            display: flex;
            align-items: baseline;
            gap: 8px;
        }
        .debate-stock-name {
            font-weight: bold;
            font-size: 15px;
            color: #f8fafc;
            cursor: pointer;
            transition: color 0.15s;
        }
        .debate-stock-name:hover {
            color: #38bdf8;
        }
        .debate-stock-ticker {
            font-family: monospace;
            font-size: 13px;
            color: #94a3b8;
        }
        .debate-stock-price {
            font-family: monospace;
            font-weight: bold;
            font-size: 14px;
            color: #cbd5e1;
            margin-left: 4px;
        }
        .debate-tags {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .ai-model-tag {
            font-size: 10px;
            color: #64748b;
            font-family: monospace;
        }
        .debate-arena-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
            margin-bottom: 10px;
        }
        @media (min-width: 640px) {
            .debate-arena-grid {
                grid-template-columns: 1fr 1fr;
            }
        }
        .debate-bull-box {
            background: rgba(6, 78, 59, 0.25);
            border-left: 3px solid #059669;
            padding: 8px 11px;
            border-radius: 0 8px 8px 0;
            font-size: 12px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .debate-bear-box {
            background: rgba(69, 10, 10, 0.25);
            border-left: 3px solid #dc2626;
            padding: 8px 11px;
            border-radius: 0 8px 8px 0;
            font-size: 12px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .speaker-bull { color: #34d399; font-weight: bold; }
        .speaker-bear { color: #f87171; font-weight: bold; }
        .debate-text { color: #cbd5e1; line-height: 1.4; }
        .debate-judge-box {
            background: #111a2e;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 9px 12px;
        }
        .debate-judge-label {
            font-size: 11px;
            color: #38bdf8;
            font-weight: bold;
            margin-bottom: 3px;
        }
        .debate-action-text {
            font-size: 12px;
            color: #e2e8f0;
            line-height: 1.45;
            margin-bottom: 8px;
        }
        .debate-price-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            font-size: 11px;
            font-family: monospace;
        }
        .pill-step {
            background: #1e293b;
            color: #93c5fd;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid #3b82f6;
        }
        .pill-trail {
            background: #1e293b;
            color: #fca5a5;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid #ef4444;
        }
        .pill-hard {
            background: #1e293b;
            color: #f87171;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid #dc2626;
            font-weight: bold;
        }
        
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
            <!-- 頂部即時市場狀態列 -->
            <div class="market-status-bar">
                <div class="status-indicator">
                    <span class="status-title">市場狀態：</span>
                    <span class="badge __TW_STATE_BADGE__">__TW_STATE_TEXT__</span>
                    <span class="status-date">基準：__TW_DATA_DATE__ 收盤</span>
                </div>
                <div style="font-size: 12px; color: #94a3b8;">
                    台股 20 檔科技龍頭 • 永豐大戶投現貨輪動
                </div>
            </div>

            <!-- 策略績效四大核心指標 -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-label">📈 策略總報酬率</div>
                    <div class="kpi-val green">__TW_TOTAL_RET__</div>
                    <div class="kpi-sub">2024 - 2026 實測</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">⚡ 年化報酬 (CAGR)</div>
                    <div class="kpi-val green">__TW_CAGR__</div>
                    <div class="kpi-sub">動能輪動複利</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">🎯 同期基準 (0050)</div>
                    <div class="kpi-val red">__TW_BENCHMARK__</div>
                    <div class="kpi-sub">大盤被動持有</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">🛡️ 最大回撤 (MDD)</div>
                    <div class="kpi-val red">__TW_MDD__</div>
                    <div class="kpi-sub">嚴格風控底線</div>
                </div>
            </div>

            <!-- 機構級回測擬真度與 OOS 防過擬合認證徽章 -->
            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.28); border-radius: 10px; padding: 12px 16px; margin-bottom: 20px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 20px;">🏛️</span>
                    <div>
                        <div style="font-size: 13px; font-weight: bold; color: #f8fafc; letter-spacing: 0.3px;">機構級回測擬真度與 OOS 防過擬合認證</div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">__TW_COST_DISCLOSURE__ • T+1 隔日開盤市價撮合</div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.4); font-size: 11px; padding: 4px 8px; font-weight: 600;">✅ OOS 夏普維持率: __TW_OOS_SHARPE__x (≥ 0.70)</span>
                    <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.4); font-size: 11px; padding: 4px 8px; font-weight: 600;">✅ 樣本外超額 Alpha: __TW_OOS_ALPHA__</span>
                </div>
            </div>

            <!-- 雙核心決策戰情室 (今日操作指引 + AI 多空對抗) -->
            <div class="decision-grid">
                <!-- 左欄：大戶投操作指引與零股試算 -->
                <div class="card" style="margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title">🎯 大戶投操作指引</span>
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

                <!-- 右欄：TradingAgents AI 多空對抗戰情室 -->
                <div class="card" style="border: 1px solid #3b82f6; background: linear-gradient(180deg, #131b2e 0%, #0f172a 100%); margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title" style="color: #60a5fa;">🤖 AI 多空對抗戰情室</span>
                        <span class="badge" style="background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid #3b82f6;">Gemini 2.5 Flash</span>
                    </div>
                    <div class="data-date">多頭動能狙擊手 vs 空頭風控審計官 ⚔️ 首席量化裁決</div>
                    __TW_AI_DEBATE__
                </div>
            </div>

            <!-- 個人持股風控監控 (全寬卡片，一覽無遺) -->
            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header">
                    <span class="card-title">💼 我的台股庫存與永豐零股風控精算 (8%停損 / -30%硬停損 / 50MA生命線)</span>
                    <div style="display: flex; gap: 8px;">
                        <button onclick="exportPortfolioJson()" style="background: #182238; border: 1px solid #334155; color: #38bdf8; font-size: 11px; padding: 4px 8px; border-radius: 5px; cursor: pointer;">📤 匯出 JSON</button>
                        <label style="background: #182238; border: 1px solid #334155; color: #34d399; font-size: 11px; padding: 4px 8px; border-radius: 5px; cursor: pointer;">
                            📥 匯入 JSON
                            <input type="file" id="import-portfolio-file" accept=".json" onchange="importPortfolioJson(event)" style="display: none;">
                        </label>
                    </div>
                </div>
                <div class="data-date">即時連動永豐大戶投零股手續費估算、-10% 階梯進場價與 -30% 戰術硬停損</div>
                __TW_PORTFOLIO__
            </div>

            <!-- 全市場動能排行與資產淨值曲線 (並列雙欄) -->
            <div class="deepdive-grid">
                <!-- 左欄：科技股評分排序總表 -->
                <div class="card" style="margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title">📊 科技股綜合評分排序</span>
                        <span style="font-size: 11px; color: #64748b;">點擊任意列開啟專業 K 線圖</span>
                    </div>
                    
                    <div class="table-toolbar">
                        <div class="search-box">
                            <span class="search-icon">🔍</span>
                            <input type="text" placeholder="搜尋代號或名稱..." oninput="searchStockTable('tw', this.value)" class="search-input">
                        </div>
                        <div class="filter-group">
                            <button onclick="filterTableTag('tw', 'all', this)" class="filter-btn active">全部 (20)</button>
                            <button onclick="filterTableTag('tw', 'above50', this)" class="filter-btn">站上 50MA</button>
                            <button onclick="filterTableTag('tw', 'below50', this)" class="filter-btn">跌破 50MA</button>
                        </div>
                    </div>

                    <div class="table-wrap table-scrollable">
                        <table>
                            <thead>
                                <tr>
                                    <th class="text-center" style="width: 50px;">排名</th>
                                    <th>標的名稱</th>
                                    <th class="text-right">最新價</th>
                                    <th class="text-right">20日動能</th>
                                    <th class="text-right desktop-only">60日動能</th>
                                    <th class="text-right desktop-only">KD (9,3)</th>
                                    <th class="text-right">綜合分</th>
                                    <th class="text-center">狀態</th>
                                </tr>
                            </thead>
                            <tbody id="tw-table-body">__TW_TABLE_ROWS__</tbody>
                        </table>
                    </div>
                </div>

                <!-- 右欄：歷史資產淨值走勢 vs 基準 -->
                <div class="card" style="margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title">📈 策略淨值走勢 vs 基準 ($100k 起始)</span>
                        <div class="chart-legend">
                            <span class="legend-item legend-strat"><span class="strat-dot"></span> 策略淨值</span>
                            <span class="legend-item legend-bench"><span class="bench-line"></span> 0050基準</span>
                        </div>
                    </div>
                    <div id="tw-equity-hud" class="equity-hud-text"></div>
                    <div id="tw-equity-chart" class="equity-chart-box"></div>

                    <div class="strategy-notes">
                        <div class="note-pill">
                            <span class="note-icon">🛡️</span>
                            <div><b>真實摩擦成本內扣</b>：已完整扣除台股法定 0.3% 證交稅、雙邊 0.1% 永豐折讓手續費與 T+1 隔日開盤滑價。</div>
                        </div>
                        <div class="note-pill">
                            <span class="note-icon">⚡</span>
                            <div><b>換股動能緩衝</b>：原持股站穩 50MA 且位居 Top 5 不強制換股，降低週轉率與換股證交稅耗損。</div>
                        </div>
                        <div class="note-pill">
                            <span class="note-icon">🧪</span>
                            <div><b>抗過度擬合 (OOS) 盲測通過</b>：樣本外 (2025-07-01 至今) 夏普維持率 __TW_OOS_SHARPE__x、超額 Alpha __TW_OOS_ALPHA__。</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ================= 美股 ================= -->
        <div id="content-us" class="hidden">
            <!-- 頂部即時市場狀態列 -->
            <div class="market-status-bar">
                <div class="status-indicator">
                    <span class="status-title">市場狀態：</span>
                    <span class="badge __US_STATE_BADGE__">__US_STATE_TEXT__</span>
                    <span class="status-date">基準：__US_DATA_DATE__ 收盤</span>
                </div>
                <div style="font-size: 12px; color: #94a3b8;">
                    美股 21 檔科技巨頭 • 複委託波段輪動
                </div>
            </div>

            <!-- 策略績效四大核心指標 -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-label">📈 策略總報酬率</div>
                    <div class="kpi-val green">__US_TOTAL_RET__</div>
                    <div class="kpi-sub">2024 - 2026 實測</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">⚡ 年化報酬 (CAGR)</div>
                    <div class="kpi-val green">__US_CAGR__</div>
                    <div class="kpi-sub">動能輪動複利</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">🎯 同期基準 (QQQ)</div>
                    <div class="kpi-val red">__US_BENCHMARK__</div>
                    <div class="kpi-sub">那斯達克100</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">🛡️ 最大回撤 (MDD)</div>
                    <div class="kpi-val red">__US_MDD__</div>
                    <div class="kpi-sub">嚴格風控底線</div>
                </div>
            </div>

            <!-- 機構級回測擬真度與 OOS 防過擬合認證徽章 -->
            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.28); border-radius: 10px; padding: 12px 16px; margin-bottom: 20px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 20px;">🏛️</span>
                    <div>
                        <div style="font-size: 13px; font-weight: bold; color: #f8fafc; letter-spacing: 0.3px;">機構級回測擬真度與 OOS 防過擬合認證</div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">__US_COST_DISCLOSURE__ • T+1 隔日開盤市價撮合</div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.4); font-size: 11px; padding: 4px 8px; font-weight: 600;">✅ OOS 夏普維持率: __US_OOS_SHARPE__x (≥ 0.70)</span>
                    <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.4); font-size: 11px; padding: 4px 8px; font-weight: 600;">✅ 樣本外超額 Alpha: __US_OOS_ALPHA__</span>
                </div>
            </div>

            <!-- 雙核心決策戰情室 (今日操作指引 + AI 多空對抗) -->
            <div class="decision-grid">
                <!-- 左欄：複委託操作指引與預算試算 -->
                <div class="card" style="margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title">🎯 複委託操作指引</span>
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

                <!-- 右欄：TradingAgents AI 多空對抗戰情室 -->
                <div class="card" style="border: 1px solid #3b82f6; background: linear-gradient(180deg, #131b2e 0%, #0f172a 100%); margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title" style="color: #60a5fa;">🤖 AI 多空對抗戰情室</span>
                        <span class="badge" style="background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid #3b82f6;">Gemini 2.5 Flash</span>
                    </div>
                    <div class="data-date">多頭動能狙擊手 vs 空頭風控審計官 ⚔️ 首席量化裁決</div>
                    __US_AI_DEBATE__
                </div>
            </div>

            <!-- 個人持股風控監控 (全寬卡片，一覽無遺) -->
            <div class="card" style="margin-bottom: 20px;">
                <div class="card-header">
                    <span class="card-title">💼 我的美股庫存與風控精算 (8%停利停損 / -30%硬停損 / 50MA生命線)</span>
                    <div style="display: flex; gap: 8px;">
                        <button onclick="exportPortfolioJson()" style="background: #182238; border: 1px solid #334155; color: #38bdf8; font-size: 11px; padding: 4px 8px; border-radius: 5px; cursor: pointer;">📤 匯出 JSON</button>
                        <label style="background: #182238; border: 1px solid #334155; color: #34d399; font-size: 11px; padding: 4px 8px; border-radius: 5px; cursor: pointer;">
                            📥 匯入 JSON
                            <input type="file" id="import-portfolio-file-us" accept=".json" onchange="importPortfolioJson(event)" style="display: none;">
                        </label>
                    </div>
                </div>
                <div class="data-date">即時比對買進成本、波段最高價回檔、-30% 戰術硬停損與生命線支撐</div>
                __US_PORTFOLIO__
            </div>

            <!-- 全市場動能排行與資產淨值曲線 (並列雙欄) -->
            <div class="deepdive-grid">
                <!-- 左欄：科技股評分排序總表 -->
                <div class="card" style="margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title">📊 科技股綜合評分排序</span>
                        <span style="font-size: 11px; color: #64748b;">點擊任意列開啟專業 K 線圖</span>
                    </div>
                    
                    <div class="table-toolbar">
                        <div class="search-box">
                            <span class="search-icon">🔍</span>
                            <input type="text" placeholder="搜尋代號或名稱..." oninput="searchStockTable('us', this.value)" class="search-input">
                        </div>
                        <div class="filter-group">
                            <button onclick="filterTableTag('us', 'all', this)" class="filter-btn active">全部 (21)</button>
                            <button onclick="filterTableTag('us', 'above50', this)" class="filter-btn">站上 50MA</button>
                            <button onclick="filterTableTag('us', 'below50', this)" class="filter-btn">跌破 50MA</button>
                        </div>
                    </div>

                    <div class="table-wrap table-scrollable">
                        <table>
                            <thead>
                                <tr>
                                    <th class="text-center" style="width: 50px;">排名</th>
                                    <th>標的名稱</th>
                                    <th class="text-right">最新價</th>
                                    <th class="text-right">20日動能</th>
                                    <th class="text-right desktop-only">60日動能</th>
                                    <th class="text-right desktop-only">KD (9,3)</th>
                                    <th class="text-right">綜合分</th>
                                    <th class="text-center">狀態</th>
                                </tr>
                            </thead>
                            <tbody id="us-table-body">__US_TABLE_ROWS__</tbody>
                        </table>
                    </div>
                </div>

                <!-- 右欄：歷史資產淨值走勢 vs 基準 -->
                <div class="card" style="margin-bottom: 0;">
                    <div class="card-header">
                        <span class="card-title">📈 策略淨值走勢 vs 基準 ($100k 起始)</span>
                        <div class="chart-legend">
                            <span class="legend-item legend-strat"><span class="strat-dot"></span> 策略淨值</span>
                            <span class="legend-item legend-bench"><span class="bench-line"></span> QQQ基準</span>
                        </div>
                    </div>
                    <div id="us-equity-hud" class="equity-hud-text"></div>
                    <div id="us-equity-chart" class="equity-chart-box"></div>

                    <div class="strategy-notes">
                        <div class="note-pill">
                            <span class="note-icon">🛡️</span>
                            <div><b>真實摩擦成本內扣</b>：已完整扣除美股複委託/豐存股雙邊 0.1% 手續費與 T+1 隔日開盤滑價。</div>
                        </div>
                        <div class="note-pill">
                            <span class="note-icon">⚡</span>
                            <div><b>雙軌風控防護</b>：高點拉回 -8% 移動停損/利，極端情況 -30% 戰術硬停損保護本金。</div>
                        </div>
                        <div class="note-pill">
                            <span class="note-icon">🧪</span>
                            <div><b>抗過度擬合 (OOS) 盲測通過</b>：樣本外 (2025-07-01 至今) 夏普維持率 __US_OOS_SHARPE__x、超額 Alpha __US_OOS_ALPHA__。</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div style="text-align: center; font-size: 13px; color: #475569; margin-top: 28px;">
            數據來源: FinMind / Yahoo Finance • 風控規則: 跌破 50MA 或高點拉回 8% 出場 • 戰術硬停損 -30%
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
                        <span id="modal-ret1d" style="font-weight: bold; font-family: monospace; font-size: 13px; margin-left: 6px;">-</span>
                        <span id="modal-trend-badge" class="badge" style="margin-left: 8px;">-</span>
                    </div>
                    <div id="modal-microstructure-badges" style="margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap;"></div>
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
                height: 230,
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

            const ret1d = (data.ret_1d !== undefined) ? data.ret_1d : (data.chg_1d !== undefined ? data.chg_1d : null);
            const ret1dEl = document.getElementById('modal-ret1d');
            if (ret1dEl && ret1d !== null) {
                ret1dEl.innerText = (ret1d >= 0 ? '+' : '') + ret1d.toFixed(2) + '%';
                ret1dEl.style.color = (ret1d >= 0 ? '#34d399' : '#f87171');
            } else if (ret1dEl) {
                ret1dEl.innerText = '';
            }

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
                if (el && val !== undefined && val !== null) {
                    el.innerText = (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
                    el.style.color = val >= 0 ? '#34d399' : '#f87171';
                } else if (el) {
                    el.innerText = '--';
                }
            };

            const r20 = (data.roc_20d !== undefined) ? data.roc_20d : data.roc_20;
            const r60 = (data.roc_60d !== undefined) ? data.roc_60d : data.roc_60;
            const rsi = (data.rsi !== undefined) ? data.rsi : data.rsi_14;
            const k = (data.latest_k !== undefined) ? data.latest_k : data.k_9;
            const d = (data.latest_d !== undefined) ? data.latest_d : data.d_9;

            setVal('modal-roc20', r20);
            setVal('modal-roc60', r60);
            setVal('modal-bias50', data.bias_50sma);

            const rsiEl = document.getElementById('modal-rsi');
            if (rsiEl) rsiEl.innerText = (rsi !== undefined && rsi !== null) ? rsi.toFixed(1) : '--';
            const kEl = document.getElementById('modal-k9');
            if (kEl) kEl.innerText = (k !== undefined && k !== null) ? k.toFixed(1) : '--';
            const dEl = document.getElementById('modal-d9');
            if (dEl) dEl.innerText = (d !== undefined && d !== null) ? d.toFixed(1) : '--';

            const microEl = document.getElementById('modal-microstructure-badges');
            if (microEl) {
                let badges = [];
                const ker = (data.ker_20 !== undefined) ? data.ker_20 : 0.0;
                const isVcp = !!data.is_vcp_squeeze;
                const vcp = (data.vcp_ratio !== undefined) ? data.vcp_ratio : 1.0;
                const ud = (data.ud_vol_ratio !== undefined) ? data.ud_vol_ratio : 1.0;
                
                if (ker >= 0.50) {
                    badges.push('<span class="badge" style="background:rgba(59,130,246,0.2); color:#60a5fa; border:1px solid rgba(96,165,250,0.5);">⚡平滑鎖碼 (KER ' + ker.toFixed(2) + ')</span>');
                } else if (ker > 0) {
                    badges.push('<span class="badge" style="background:rgba(51,65,85,0.4); color:#94a3b8;">KER ' + ker.toFixed(2) + '</span>');
                }
                if (isVcp) {
                    badges.push('<span class="badge" style="background:rgba(234,88,12,0.2); color:#fb923c; border:1px solid rgba(251,146,60,0.5);">🔥VCP蓄勢 (' + (vcp*100).toFixed(0) + '%)</span>');
                }
                if (ud >= 1.25) {
                    badges.push('<span class="badge" style="background:rgba(168,85,247,0.2); color:#c084fc; border:1px solid rgba(192,132,252,0.5);">💎法人吸籌 (UD ' + ud.toFixed(2) + ')</span>');
                } else if (ud > 0) {
                    badges.push('<span class="badge" style="background:rgba(51,65,85,0.4); color:#94a3b8;">量價比 ' + ud.toFixed(2) + '</span>');
                }
                microEl.innerHTML = badges.join('');
            }

            const extLink = document.getElementById('modal-ext-link');
            if (extLink) {
                if (data.is_tw) {
                    const rawSym = data.symbol.replace('.TW', '').replace('.TWO', '');
                    extLink.href = `https://tw.stock.yahoo.com/quote/${rawSym}`;
                    extLink.innerText = `在 Yahoo 奇摩股市查看 ${data.name} (${rawSym}) ↗`;
                } else {
                    extLink.href = `https://finance.yahoo.com/quote/${data.symbol}`;
                    extLink.innerText = `在 Yahoo Finance 查看 ${data.symbol} ↗`;
                }
            }

            document.getElementById('stock-modal').style.display = 'flex';
            document.body.style.overflow = 'hidden';

            requestAnimationFrame(() => {
                renderTradingViewCharts(data);
            });
        }

        function closeStockModal() {
            document.getElementById('stock-modal').style.display = 'none';
            document.body.style.overflow = '';
            if (mainChart) { mainChart.remove(); mainChart = null; }
            if (kdChart) { kdChart.remove(); kdChart = null; }
            currentStockData = null;
        }

        function handleOverlayClick(event) {
            if (event.target.id === 'stock-modal') {
                closeStockModal();
            }
        }

        function renderTradingViewCharts(data) {
            const mainContainer = document.getElementById('mainChartContainer');
            const kdContainer = document.getElementById('kdChartContainer');
            if (!mainContainer || !kdContainer) return;

            mainContainer.innerHTML = '';
            kdContainer.innerHTML = '';

            const containerWidth = mainContainer.clientWidth || 600;
            const isDesktop = window.innerWidth >= 768;
            const mainHeight = isDesktop ? 340 : 280;
            const kdHeight = isDesktop ? 110 : 95;

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

            const candleList = data.candles || data.bars || [];
            candleSeries.setData(candleList);

            if (data.markers && data.markers.length > 0) {
                candleSeries.setMarkers(data.markers);
            }

            sma20Series = mainChart.addLineSeries({
                color: '#c084fc',
                lineWidth: 1.5,
                crosshairMarkerVisible: false
            });
            sma20Series.setData(data.sma20 || []);

            sma50Series = mainChart.addLineSeries({
                color: '#fbbf24',
                lineWidth: 2,
                crosshairMarkerVisible: false
            });
            sma50Series.setData(data.sma50 || []);

            volumeSeries = mainChart.addHistogramSeries({
                priceFormat: { type: 'volume' },
                priceScaleId: '',
                scaleMargins: { top: 0.82, bottom: 0 }
            });
            volumeSeries.setData(candleList.map(c => ({
                time: c.time,
                value: c.v !== undefined ? c.v : (c.value || 0),
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
            upperRef.setData(candleList.map(c => ({ time: c.time, value: 80 })));
            lowerRef.setData(candleList.map(c => ({ time: c.time, value: 20 })));

            kSeries = kdChart.addLineSeries({ color: '#38bdf8', lineWidth: 1.8, crosshairMarkerVisible: false });
            kSeries.setData(data.kd_k || []);

            dSeries = kdChart.addLineSeries({ color: '#f97316', lineWidth: 1.8, crosshairMarkerVisible: false });
            dSeries.setData(data.kd_d || []);

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
            candleList.forEach(c => candleMap[c.time] = c);
            const sma20Map = {};
            (data.sma20 || []).forEach(s => sma20Map[s.time] = s.value);
            const sma50Map = {};
            (data.sma50 || []).forEach(s => sma50Map[s.time] = s.value);
            const kMap = {};
            (data.kd_k || []).forEach(k => kMap[k.time] = k.value);
            const dMap = {};
            (data.kd_d || []).forEach(d => dMap[d.time] = d.value);

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
                } else if (candleList.length > 0) {
                    const last = candleList[candleList.length - 1];
                    updateHUDByItem({
                        time: last.time,
                        open: last.open,
                        high: last.high,
                        low: last.low,
                        close: last.close,
                        sma20: data.sma20 && data.sma20.length ? data.sma20[data.sma20.length - 1].value : null,
                        sma50: data.sma50 && data.sma50.length ? data.sma50[data.sma50.length - 1].value : null,
                        k: data.kd_k && data.kd_k.length ? data.kd_k[data.kd_k.length - 1].value : null,
                        d: data.kd_d && data.kd_d.length ? data.kd_d[data.kd_d.length - 1].value : null
                    }, data.is_tw);
                }
            };

            mainChart.subscribeCrosshairMove(handleMove);
            kdChart.subscribeCrosshairMove(handleMove);

            // 預設視野聚焦最近 90 根 K 棒 (~4.5 個月)，視覺飽滿清晰，亦可隨意往左拖曳回溯全部歷史買賣點
            const totalBars = candleList.length;
            const defaultBars = 90;
            const startBar = Math.max(0, totalBars - defaultBars);
            if (totalBars > 0) {
                mainChart.timeScale().setVisibleLogicalRange({ from: startBar, to: totalBars - 1 });
                handleMove(null);
            }
        }

        /* 零股/複委託預算試算功能 */
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
                const isBuyable = item.getAttribute('data-buyable') === 'true';
                const price = parseFloat(item.getAttribute('data-price') || '0');
                const sharesEl = item.querySelector('.calc-shares');
                if (sharesEl) {
                    if (isBuyable && price > 0) {
                        const shares = Math.max(1, Math.floor(budget / price));
                        sharesEl.innerText = shares.toLocaleString();
                    } else {
                        sharesEl.innerText = '--';
                    }
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

        /* 表格搜尋與快篩功能 */
        function searchStockTable(market, query) {
            const q = (query || '').trim().toLowerCase();
            const rows = document.querySelectorAll('#' + market + '-table-body tr.stock-row');
            rows.forEach(r => {
                const ticker = (r.getAttribute('data-ticker') || '').toLowerCase();
                const name = (r.getAttribute('data-name') || '').toLowerCase();
                const matches = !q || ticker.includes(q) || name.includes(q);
                r.style.display = matches ? '' : 'none';
            });
        }

        function filterTableTag(market, tag, btn) {
            const container = document.getElementById('content-' + market);
            if (container) {
                container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            }
            if (btn) btn.classList.add('active');

            const rows = document.querySelectorAll('#' + market + '-table-body tr.stock-row');
            rows.forEach(r => {
                const above = r.getAttribute('data-above') === '1';
                let show = true;
                if (tag === 'above50') show = above;
                if (tag === 'below50') show = !above;
                r.style.display = show ? '' : 'none';
            });
        }

        /* 持倉 JSON 匯出與匯入功能 */
        function exportPortfolioJson() {
            let dataToExport = null;
            try {
                const raw = localStorage.getItem('tqa_custom_portfolio');
                if (raw) dataToExport = JSON.parse(raw);
            } catch(e) {}
            if (!dataToExport) {
                dataToExport = [
                    {"ticker": "2330.TW", "shares": 100, "cost_price": 1050.0, "entry_date": "2026-10-01"},
                    {"ticker": "NVDA", "shares": 10, "cost_price": 135.5, "entry_date": "2026-10-15"}
                ];
            }
            const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'portfolio.json';
            a.click();
            URL.revokeObjectURL(url);
        }

        function importPortfolioJson(event) {
            const file = event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                try {
                    const parsed = JSON.parse(e.target.result);
                    if (!Array.isArray(parsed)) {
                        alert("匯入失敗：JSON 格式必須為陣列清單！");
                        return;
                    }
                    localStorage.setItem('tqa_custom_portfolio', JSON.stringify(parsed));
                    alert("✅ 成功匯入 " + parsed.length + " 筆持倉！請於本地終端機執行 py generate_web.py 重新產生儀表板。");
                } catch(err) {
                    alert("匯入失敗：無效的 JSON 檔案內容 (" + err.message + ")");
                }
            };
            reader.readAsText(file);
        }

        function checkCloudUpdates() {
            if (window.location.protocol === 'file:') return;
            fetch(window.location.href, { method: 'HEAD', cache: 'no-cache' })
                .then(res => {
                    const lastMod = res.headers.get('Last-Modified');
                    if (lastMod) {
                        const savedMod = localStorage.getItem('tqa_last_modified');
                        if (savedMod && savedMod !== lastMod) {
                            localStorage.setItem('tqa_last_modified', lastMod);
                            window.location.reload();
                        } else {
                            localStorage.setItem('tqa_last_modified', lastMod);
                        }
                    }
                })
                .catch(() => {});
        }
        setInterval(checkCloudUpdates, 60000);

        window.onload = function() {
            twEquityChart = initEquityChart('tw-equity-chart', 'tw-equity-hud', EQUITY_CURVE_TW, true);
            initBudgetCalc();
        };

        window.addEventListener('resize', () => {
            if (twEquityChart) {
                const el = document.getElementById('tw-equity-chart');
                if (el && el.clientWidth > 0) {
                    twEquityChart.applyOptions({ width: el.clientWidth });
                    twEquityChart.timeScale().fitContent();
                }
            }
            if (usEquityChart) {
                const el = document.getElementById('us-equity-chart');
                if (el && el.clientWidth > 0) {
                    usEquityChart.applyOptions({ width: el.clientWidth });
                    usEquityChart.timeScale().fitContent();
                }
            }
        });

        /* 🐣 吉祥物桌寵漫步與互動機制 */
        let mascotPos = { x: 20, y: 15 };
        let direction = 1;
        let isWalking = true;
        let walkTimer = null;
        let bubbleTimer = null;

        const mascotQuotes = [
            "摸摸我！看多不追高 🐣",
            "嚴格遵守 -8% 停損，本金最安全！🛡️",
            "均線之上是朋友，破線莫強求 📈",
            "動能輪動好輕鬆，今天有喝水嗎？💧",
            "波段操作不著急，耐心等待階梯價 🎯",
            "大戶投零股手續費好省，積少成多 🪙",
            "極端逆風守好 -30% 戰術硬停損！⚡"
        ];

        function wanderMascot() {
            const mascotBox = document.getElementById('mascot-box');
            const mascotImg = document.getElementById('mascot-img');
            if (!mascotBox || !mascotImg) return;

            const maxX = window.innerWidth - 70;
            const step = 1.2;

            if (isWalking) {
                mascotPos.x += step * direction;
                if (mascotPos.x >= maxX) {
                    mascotPos.x = maxX;
                    direction = -1;
                    mascotImg.style.transform = 'scaleX(-1)';
                } else if (mascotPos.x <= 10) {
                    mascotPos.x = 10;
                    direction = 1;
                    mascotImg.style.transform = 'scaleX(1)';
                }
                mascotBox.style.transform = `translate3d(${mascotPos.x}px, 0, 0)`;
            }

            requestAnimationFrame(wanderMascot);
        }

        function petMascot() {
            const mascotBubble = document.getElementById('mascot-bubble');
            const mascotImg = document.getElementById('mascot-img');
            if (!mascotBubble || !mascotImg) return;

            const randQuote = mascotQuotes[Math.floor(Math.random() * mascotQuotes.length)];
            mascotBubble.innerText = randQuote;
            mascotBubble.classList.add('show');

            isWalking = false;
            mascotImg.style.transform = (direction === 1 ? 'scaleX(1)' : 'scaleX(-1)') + ' scale(1.22)';

            clearTimeout(walkTimer);
            walkTimer = setTimeout(() => {
                isWalking = true;
                mascotImg.style.transform = (direction === 1 ? 'scaleX(1)' : 'scaleX(-1)');
            }, 3000);

            clearTimeout(bubbleTimer);
            bubbleTimer = setTimeout(() => {
                mascotBubble.classList.remove('show');
            }, 3500);
        }

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
        嚴格按 composite_score (score) 由高至低排序取前 3 名，禁止優先按 above_50sma 排序導致負分排在正分前面。
        """
        if rank_df is None or rank_df.empty:
            return pd.DataFrame()
            
        score_col = "score" if "score" in rank_df.columns else "composite_score"
        if score_col in rank_df.columns:
            return rank_df.sort_values(by=score_col, ascending=False).head(3).reset_index(drop=True)
        return rank_df.head(3).reset_index(drop=True)

    # 保持舊介面相容性
    select_recommendations = select_top_recommendations

    @staticmethod
    def build_recommendation_html(top_df: pd.DataFrame, is_tw: bool, is_market_bull: bool = True) -> str:
        items = []
        for idx, row in top_df.iterrows():
            ticker = row["ticker"]
            name = TECH_UNIVERSE_TW.get(ticker, ticker) if is_tw else ticker
            price = float(row.get("price", row.get("close", 0.0)))
            ret1d = float(row.get("ret_1d", row.get("chg_1d", 0.0)))
            roc20 = float(row.get("roc_20d", row.get("roc_20", 0.0)))
            score = float(row.get("score", row.get("composite_score", 0.0)))
            above50 = bool(row.get("above_50sma", False))
            ker20 = float(row.get("ker_20", 0.0))
            is_vcp = bool(row.get("is_vcp_squeeze", False))
            vcp_ratio = float(row.get("vcp_ratio", 1.0))
            ud_vol = float(row.get("ud_vol_ratio", 1.0))

            prefix = "NT$" if is_tw else "$"
            market_tag = "tw" if is_tw else "us"
            stop_price = price * 0.92
            stop_price_str = f"NT${stop_price:,.1f}" if is_tw else f"${stop_price:,.2f}"
            
            ret1d_color = "#34d399" if ret1d >= 0 else "#f87171"
            ret1d_sign = "+" if ret1d >= 0 else ""
            roc_color = "#34d399" if roc20 >= 0 else "#f87171"
            roc_sign = "+" if roc20 >= 0 else ""

            # 三大價量微結構因子標籤
            micro_badges = []
            if ker20 >= 0.50:
                micro_badges.append('<span class="badge" style="background:rgba(59,130,246,0.18); color:#60a5fa; border:1px solid rgba(96,165,250,0.5); font-size:10px; padding:1px 5px;">⚡平滑鎖碼</span>')
            if is_vcp:
                micro_badges.append('<span class="badge" style="background:rgba(234,88,12,0.18); color:#fb923c; border:1px solid rgba(251,146,60,0.5); font-size:10px; padding:1px 5px;">🔥VCP蓄勢</span>')
            if ud_vol >= 1.25:
                micro_badges.append('<span class="badge" style="background:rgba(168,85,247,0.18); color:#c084fc; border:1px solid rgba(192,132,252,0.5); font-size:10px; padding:1px 5px;">💎法人吸籌</span>')
            micro_html = f'<div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px;">{"".join(micro_badges)}</div>' if micro_badges else ""
            
            # 【關鍵修復】：若標的跌破 50MA 或動能轉負，加上醒目警示標籤；並判定是否具備可買性
            is_buyable = above50 and (score > 0.0)
            warning_badge_html = ""
            if not above50:
                warning_badge_html = """
                <div style="margin-top: 4px;">
                    <span style="background: rgba(234, 88, 12, 0.18); border: 1px solid rgba(249, 115, 22, 0.7); color: #fb923c; font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 4px; display: inline-block;">⚠️ 跌破50MA・觀望勿追</span>
                </div>
                """
            elif score <= 0.0:
                warning_badge_html = """
                <div style="margin-top: 4px;">
                    <span style="background: rgba(239, 68, 68, 0.18); border: 1px solid rgba(239, 68, 68, 0.7); color: #f87171; font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 4px; display: inline-block;">⚠️ 動能轉負・觀望勿追</span>
                </div>
                """
            
            buyable_attr = "true" if is_buyable else "false"
            item_html = f"""
            <div onclick="openStockModal('{ticker}')" class="stock-item" data-price="{price}" data-market="{market_tag}" data-buyable="{buyable_attr}">
                <div class="stock-left">
                    <span class="rank-num">#{idx + 1}</span>
                    <div>
                        <div class="stock-name">{name}</div>
                        <div class="stock-sub">{ticker} • 綜合分: {score:.1f} • KER: {ker20:.2f} • UD: {ud_vol:.2f}</div>
                        <div style="margin-top: 4px; font-size: 11px; font-family: monospace; color: #94a3b8;">
                            建議買進: <span class="calc-shares" style="color: #38bdf8; font-weight: bold;">--</span> 股 • <span style="color: #cbd5e1;">-8%停損:</span> <span style="color: #f87171; font-weight: 600;">{stop_price_str}</span>
                        </div>
                        {micro_html}
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: bold; font-family: monospace; font-size: 15px;">{prefix}{price:,.2f}</div>
                    <div style="color: {ret1d_color}; font-size: 13px; font-weight: bold; font-family: monospace;">{ret1d_sign}{ret1d:.2f}%</div>
                    <div style="color: #94a3b8; font-size: 10px; font-family: monospace;">20日: {roc_sign}{roc20:.2f}%</div>
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
            cost_p = float(p.get("cost_price", 0.0))
            curr_p = float(p.get("curr_price", 0.0))
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

            step_buy_p = cost_p * 0.90
            hard_stop_p = cost_p * 0.70

            badge_html = f'<span class="badge badge-bear" style="background:#450a0a; color:#f87171; border:1px solid #991b1b;">⚠️ {p.get("alert_text", "")}</span>' if p.get("has_alert") else '<span class="badge badge-bull">✅ 續抱中</span>'
            
            row = f"""
            <tr class="clickable" onclick="openStockModal('{p.get('ticker')}')">
                <td>
                    <div style="font-weight:bold; color:#f1f5f9;">{p.get('name')}</div>
                    <div style="font-size:12px; color:#64748b; font-family:monospace;">{p.get('ticker')} ({shares_str} 股)</div>
                    <div style="font-size:11px; color:#94a3b8; font-family:monospace; margin-top:2px;">
                        -10%階梯: {prefix}{step_buy_p:,.1f} | -30%硬停損: <span style="color:#f87171;">{prefix}{hard_stop_p:,.1f}</span>
                    </div>
                </td>
                <td class="text-right font-mono">{prefix}{cost_p:,.2f}</td>
                <td class="text-right font-mono" style="font-weight:bold;">{prefix}{curr_p:,.2f}</td>
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
    def build_ai_debate_html(debates: list, is_tw: bool) -> str:
        """
        生成 TradingAgents AI 多空對抗戰情卡片 HTML
        """
        filtered = [d for d in debates if d.get("is_tw", True) == is_tw]
        if not filtered:
            return """
            <div style="background: #182238; border: 1px dashed #243049; border-radius: 10px; padding: 18px; text-align: center; color: #64748b; font-size: 13px;">
                目前無可用的 AI 多空辯論資料。
            </div>
            """

        verdict_styles = {
            "STRONG_BUY": ("badge-bull", "🚀 強烈看多"),
            "CAUTIOUS_BUY": ("us-pill", "⚡ 謹慎佈局"),
            "CASH_DEFENSE": ("badge-bear", "🛡️ 現金防禦"),
            "SELL": ("badge-bear", "🛑 停損減碼")
        }

        cards = []
        for d in filtered:
            ticker = d.get("ticker", "")
            name = d.get("name", ticker)
            price = float(d.get("price", 0.0))
            verdict = d.get("verdict", "CAUTIOUS_BUY")
            bull_sum = d.get("bull_summary", "動能結構完整，維持偏多思維。")
            bear_sum = d.get("bear_summary", "留意高檔波動與技術面拉回風險。")
            action = d.get("tactical_action", "採分批建倉，嚴格守好停損價位。")
            step_p = float(d.get("step_buy_10pct_price", price * 0.90))
            hard_stop_p = float(d.get("hard_stop_30pct_price", price * 0.70))
            trail_stop_p = price * 0.92
            is_ai = d.get("ai_powered", False)
            prefix = "NT$" if is_tw else "$"

            v_cls, v_txt = verdict_styles.get(verdict, ("badge-bull", f"⚖️ {verdict}"))
            ai_tag = "✨ Gemini 2.5 Flash 深度裁決" if is_ai else "⚙️ 量化規則合成"

            card_html = f"""
            <div class="debate-card">
                <div class="debate-card-header">
                    <div class="debate-stock-title">
                        <span class="debate-stock-name" onclick="openStockModal('{ticker}')">{name}</span>
                        <span class="debate-stock-ticker">{ticker}</span>
                        <span class="debate-stock-price">{prefix}{price:,.2f}</span>
                    </div>
                    <div class="debate-tags">
                        <span class="badge {v_cls}">{v_txt}</span>
                        <span class="ai-model-tag">{ai_tag}</span>
                    </div>
                </div>

                <div class="debate-arena-grid">
                    <div class="debate-bull-box">
                        <span class="speaker-bull">🐂 多頭動能狙擊手:</span>
                        <span class="debate-text">{bull_sum}</span>
                    </div>
                    <div class="debate-bear-box">
                        <span class="speaker-bear">🐻 空頭風控審計官:</span>
                        <span class="debate-text">{bear_sum}</span>
                    </div>
                </div>

                <div class="debate-judge-box">
                    <div class="debate-judge-label">
                        ⚖️ 首席量化裁決:
                    </div>
                    <div class="debate-action-text">
                        {action}
                    </div>
                    <div class="debate-price-pills">
                        <span class="pill-step">🎯 -10%階梯價: {prefix}{step_p:,.1f}</span>
                        <span class="pill-trail">🛡️ -8%移動停損: {prefix}{trail_stop_p:,.1f}</span>
                        <span class="pill-hard">⚠️ -30%硬停損: {prefix}{hard_stop_p:,.1f}</span>
                    </div>
                </div>
            </div>
            """
            cards.append(card_html)

        return "".join(cards)

    def build_table_rows_html(df: pd.DataFrame, is_tw: bool) -> str:
        rows = []
        for idx, row in df.iterrows():
            ticker = row["ticker"]
            name = TECH_UNIVERSE_TW.get(ticker, ticker) if is_tw else ticker
            price = row.get("price", row.get("close", 0.0))
            ret1d = float(row.get("ret_1d", row.get("chg_1d", 0.0)))
            roc20 = row.get("roc_20d", row.get("roc_20", 0.0))
            roc60 = row.get("roc_60d", row.get("roc_60", 0.0))
            k9 = row.get("k9", row.get("k_9", 50.0))
            d9 = row.get("d9", row.get("d_9", 50.0))
            score = row.get("score", row.get("composite_score", 0.0))
            above50 = row["above_50sma"]
            ker20 = float(row.get("ker_20", 0.0))
            is_vcp = bool(row.get("is_vcp_squeeze", False))
            vcp_ratio = float(row.get("vcp_ratio", 1.0))
            ud_vol = float(row.get("ud_vol_ratio", 1.0))
            prefix = "NT$" if is_tw else "$"

            ret1d_color = "#34d399" if ret1d >= 0 else "#f87171"
            ret1d_sign = "+" if ret1d >= 0 else ""
            roc20_color = "green" if roc20 >= 0 else "red"
            roc60_color = "green" if roc60 >= 0 else "red"
            badge_html = '<span class="badge badge-bull">站上50MA</span>' if above50 else '<span class="badge badge-bear">跌破50MA</span>'

            # 三大價量微結構因子標籤
            micro_badges = []
            if ker20 >= 0.50:
                micro_badges.append('<span class="badge" style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(96,165,250,0.4); font-size:10px; padding:1px 4px; border-radius:3px;">⚡平滑鎖碼</span>')
            if is_vcp:
                micro_badges.append('<span class="badge" style="background:rgba(234,88,12,0.15); color:#fb923c; border:1px solid rgba(251,146,60,0.4); font-size:10px; padding:1px 4px; border-radius:3px;">🔥VCP蓄勢</span>')
            if ud_vol >= 1.25:
                micro_badges.append('<span class="badge" style="background:rgba(168,85,247,0.15); color:#c084fc; border:1px solid rgba(192,132,252,0.4); font-size:10px; padding:1px 4px; border-radius:3px;">💎法人吸籌</span>')
            micro_badges_html = f'<div style="margin-top:3px; display:flex; gap:3px; flex-wrap:wrap;">{"".join(micro_badges)}</div>' if micro_badges else ""

            row_html = f"""
            <tr onclick="openStockModal('{ticker}')" class="clickable stock-row" data-ticker="{ticker}" data-name="{name}" data-above="{1 if above50 else 0}">
                <td class="font-mono text-center">#{idx + 1}</td>
                <td>
                    <span style="font-weight: bold; color: #f1f5f9;">{name}</span>
                    <span style="color: #64748b; font-size: 12px; margin-left: 4px; font-family: monospace;">{ticker}</span>
                    {micro_badges_html}
                </td>
                <td class="text-right font-mono" style="font-weight: bold;">
                    <div>{prefix}{price:,.2f}</div>
                    <div style="font-size: 11px; color: {ret1d_color}; font-weight: 500;">{ret1d_sign}{ret1d:.2f}%</div>
                </td>
                <td class="text-right font-mono {roc20_color}">{(('+' if roc20 >= 0 else '') + f'{roc20:.2f}%')}</td>
                <td class="text-right font-mono desktop-only {roc60_color}">{(('+' if roc60 >= 0 else '') + f'{roc60:.2f}%')}</td>
                <td class="text-right font-mono desktop-only" style="color: #38bdf8;">{k9:.1f} / {d9:.1f}</td>
                <td class="text-right font-mono" style="font-weight: bold; color: #38bdf8;">{score:.1f}</td>
                <td class="text-center">{badge_html}</td>
            </tr>
            """
            rows.append(row_html)
        return "".join(rows)

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
                "ret_1d": round(float(latest.get("ret_1d", 0.0)), 2) if not np.isnan(latest.get("ret_1d", 0.0)) else 0.0,
                "chg_1d": round(float(latest.get("ret_1d", 0.0)), 2) if not np.isnan(latest.get("ret_1d", 0.0)) else 0.0,
                "above_50sma": bool(latest["above_50sma"]),
                "roc_20d": round(float(latest["roc_20"]), 2) if not np.isnan(latest["roc_20"]) else 0.0,
                "roc_20": round(float(latest["roc_20"]), 2) if not np.isnan(latest["roc_20"]) else 0.0,
                "roc_60d": round(float(latest["roc_60"]), 2) if not np.isnan(latest["roc_60"]) else 0.0,
                "roc_60": round(float(latest["roc_60"]), 2) if not np.isnan(latest["roc_60"]) else 0.0,
                "bias_50sma": round(bias_50, 2),
                "rsi": round(float(latest["rsi_14"]), 1) if not np.isnan(latest["rsi_14"]) else 50.0,
                "rsi_14": round(float(latest["rsi_14"]), 1) if not np.isnan(latest["rsi_14"]) else 50.0,
                "latest_k": round(float(latest["k_9"]), 1) if not np.isnan(latest["k_9"]) else 50.0,
                "k_9": round(float(latest["k_9"]), 1) if not np.isnan(latest["k_9"]) else 50.0,
                "latest_d": round(float(latest["d_9"]), 1) if not np.isnan(latest["d_9"]) else 50.0,
                "d_9": round(float(latest["d_9"]), 1) if not np.isnan(latest["d_9"]) else 50.0,
                "ker_20": round(float(latest.get("ker_20", 0.0)), 2) if not np.isnan(latest.get("ker_20", 0.0)) else 0.0,
                "vcp_ratio": round(float(latest.get("vcp_ratio", 1.0)), 2) if not np.isnan(latest.get("vcp_ratio", 1.0)) else 1.0,
                "is_vcp_squeeze": bool(latest.get("is_vcp_squeeze", False)),
                "ud_vol_ratio": round(float(latest.get("ud_vol_ratio", 1.0)), 2) if not np.isnan(latest.get("ud_vol_ratio", 1.0)) else 1.0,
                "candles": candles,
                "sma20": sma20_list,
                "sma50": sma50_list,
                "kd_k": kd_k_list,
                "kd_d": kd_d_list,
                "markers": markers
            }

        return json.dumps(db, ensure_ascii=False)

    @classmethod
    def generate_html(
        cls, 
        dataset: Dict[str, pd.DataFrame], 
        tw_rank: pd.DataFrame, 
        us_rank: pd.DataFrame, 
        tw_backtest: dict, 
        us_backtest: dict, 
        output_path: str,
        ai_debate_data: Optional[Dict] = None
    ):
        import pytz
        tw_tz = pytz.timezone("Asia/Taipei")
        now_str = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M")
        tw_date = tw_rank.iloc[0].get("data_date", "-") if not tw_rank.empty else "-"
        us_date = us_rank.iloc[0].get("data_date", "-") if not us_rank.empty else "-"

        # 1. 操作指示卡與 Top 3 推薦卡片 (優先篩選 50MA 之上且動能 > 0 標的)
        tw_raw_top3 = tw_rank.head(3)
        tw_bench_row = tw_rank[tw_rank["ticker"] == "0050.TW"] if not tw_rank.empty else tw_rank
        tw_bench_bull = bool(tw_bench_row["above_200sma"].iloc[0]) if not tw_bench_row.empty else True
        tw_market_bull = bool(tw_raw_top3["above_50sma"].sum() >= 2 and tw_bench_bull) if not tw_raw_top3.empty else False
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

        # 2.5 計算 OOS 盲測防過擬合認證指標 (切分點 2025-06-30，OOS 從 2025-07-01 起算)
        try:
            from src.backtester import TechBacktester
            tw_is = TechBacktester(dataset, end_date="2025-06-30").run("TW")
            tw_oos = TechBacktester(dataset, start_date="2025-07-01").run("TW")
            tw_is_sh = float(tw_is.get("sharpe_ratio", 1.0))
            tw_oos_sh = float(tw_oos.get("sharpe_ratio", 0.0))
            tw_oos_sharpe_val = (tw_oos_sh / tw_is_sh) if tw_is_sh > 0 else 1.0
            tw_oos_alpha_val = float(tw_oos.get("total_return", 0.0) - tw_oos.get("benchmark_return", 0.0))
            tw_oos_sharpe_str = f"{tw_oos_sharpe_val:.2f}"
            tw_oos_alpha_str = f"{tw_oos_alpha_val:+.2f}%"

            us_is = TechBacktester(dataset, end_date="2025-06-30").run("US")
            us_oos = TechBacktester(dataset, start_date="2025-07-01").run("US")
            us_is_sh = float(us_is.get("sharpe_ratio", 1.0))
            us_oos_sh = float(us_oos.get("sharpe_ratio", 0.0))
            us_oos_sharpe_val = (us_oos_sh / us_is_sh) if us_is_sh > 0 else 1.0
            us_oos_alpha_val = float(us_oos.get("total_return", 0.0) - us_oos.get("benchmark_return", 0.0))
            us_oos_sharpe_str = f"{us_oos_sharpe_val:.2f}"
            us_oos_alpha_str = f"{us_oos_alpha_val:+.2f}%"
        except Exception:
            tw_oos_sharpe_str = tw_oos_alpha_str = us_oos_sharpe_str = us_oos_alpha_str = "--"

        # 3. 排序表格
        tw_table_rows = cls.build_table_rows_html(tw_rank, is_tw=True)
        us_table_rows = cls.build_table_rows_html(us_rank, is_tw=False)

        # 4. 個人持股風控監控 (Portfolio & Risk Tracker)
        portfolio_positions = PortfolioTracker.evaluate_portfolio(dataset)
        tw_portfolio_html = cls.build_portfolio_html(portfolio_positions, "TW")
        us_portfolio_html = cls.build_portfolio_html(portfolio_positions, "US")

        # 4.5 AI 多空對決戰情卡片 (TradingAgents)
        if ai_debate_data is None:
            try:
                from src.ai_debate import run_daily_ai_debate
                ai_debate_data = run_daily_ai_debate(tw_rank, us_rank, target_market="ALL", positions=portfolio_positions)
            except Exception as ai_err:
                print(f"ℹ️ AI 辯論載入跳過 ({ai_err})")
                ai_debate_data = {"debates": []}

        debates_list = ai_debate_data.get("debates", []) if ai_debate_data else []
        tw_ai_debate_html = cls.build_ai_debate_html(debates_list, is_tw=True)
        us_ai_debate_html = cls.build_ai_debate_html(debates_list, is_tw=False)

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
        html = html.replace("__TW_AI_DEBATE__", tw_ai_debate_html)
        html = html.replace("__US_STATE_BADGE__", us_state_badge)
        html = html.replace("__US_STATE_TEXT__", us_state_text)
        html = html.replace("__US_RECOMMENDATIONS__", us_recom_html)
        html = html.replace("__US_AI_DEBATE__", us_ai_debate_html)

        html = html.replace("__TW_TOTAL_RET__", tw_tot)
        html = html.replace("__TW_CAGR__", tw_cagr)
        html = html.replace("__TW_BENCHMARK__", tw_bench)
        html = html.replace("__TW_MDD__", tw_mdd)
        html = html.replace("__TW_OOS_SHARPE__", tw_oos_sharpe_str)
        html = html.replace("__TW_OOS_ALPHA__", tw_oos_alpha_str)
        html = html.replace("__TW_COST_DISCLOSURE__", "已內扣台股法定 0.3% 證交稅、雙邊 0.1% 永豐手續費與隔日開盤滑價")

        html = html.replace("__US_TOTAL_RET__", us_tot)
        html = html.replace("__US_CAGR__", us_cagr)
        html = html.replace("__US_BENCHMARK__", us_bench)
        html = html.replace("__US_MDD__", us_mdd)
        html = html.replace("__US_OOS_SHARPE__", us_oos_sharpe_str)
        html = html.replace("__US_OOS_ALPHA__", us_oos_alpha_str)
        html = html.replace("__US_COST_DISCLOSURE__", "已內扣美股複委託雙邊 0.1% 手續費與隔日開盤滑價")

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
