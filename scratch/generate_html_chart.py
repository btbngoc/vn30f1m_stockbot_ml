import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import json
import pandas as pd
import numpy as np

# Load trades
trades_df = pd.read_csv("results/all_trades_visualize.csv")
trades_df["entry_time"] = pd.to_datetime(trades_df["entry_time"])
trades_df["exit_time"] = pd.to_datetime(trades_df["exit_time"])

# Load features (1m candles)
features = pd.read_parquet("trading_engine/data/VN30F1M_features.parquet")
features["datetime"] = pd.to_datetime(features["datetime"])
features = features.sort_values("datetime").reset_index(drop=True)

print(f"Loaded {len(trades_df)} trades and {len(features)} 1-minute bars.")

# Chuẩn bị dữ liệu cho từng trade
trade_details = []
features_indexed = features.set_index("datetime")

for idx, tr in trades_df.iterrows():
    en_t = tr["entry_time"]
    ex_t = tr["exit_time"]
    
    # Lấy khoảng thời gian trước 20 nến và sau 15 nến
    sub_df = features[(features["datetime"] >= en_t - pd.Timedelta(minutes=30)) & 
                      (features["datetime"] <= ex_t + pd.Timedelta(minutes=25))].copy()
    
    # Nếu ít nến (ví dụ qua đêm), mở rộng
    if len(sub_df) < 20:
        sub_df = features[(features["datetime"] >= en_t - pd.Timedelta(hours=4)) & 
                          (features["datetime"] <= ex_t + pd.Timedelta(hours=4))].copy()

    # Chỉ giữ tối đa 150 nến quanh trade để file nhẹ và mượt
    if len(sub_df) > 160:
        en_idx = sub_df[sub_df["datetime"] >= en_t].index
        if len(en_idx) > 0:
            mid_idx = en_idx[0]
            start_i = max(0, mid_idx - 30)
            end_i = min(len(features), mid_idx + tr["bars_held"] + 25)
            sub_df = features.iloc[start_i:end_i].copy()

    candles = []
    for r in sub_df.itertuples():
        candles.append({
            "t": r.datetime.strftime("%Y-%m-%d %H:%M"),
            "o": float(r.Open),
            "h": float(r.High),
            "l": float(r.Low),
            "c": float(r.Close),
            "v": float(getattr(r, "Volume", 0))
        })
        
    trade_details.append({
        "id": int(tr["id"]),
        "fold": str(tr["fold"]),
        "type": str(tr["type"]),
        "entry_time": tr["entry_time"].strftime("%Y-%m-%d %H:%M"),
        "exit_time": tr["exit_time"].strftime("%Y-%m-%d %H:%M"),
        "entry_price": float(tr["entry_price"]),
        "exit_price": float(tr["exit_price"]),
        "initial_sl": float(tr["initial_sl"]),
        "hard_sl": float(tr["hard_sl"]),
        "exit_sl": float(tr["exit_sl"]),
        "points": float(tr["points"]),
        "net_pnl": float(tr["net_pnl"]),
        "reason": str(tr["reason"]),
        "is_overnight": bool(tr["is_overnight"]),
        "bars_held": int(tr["bars_held"]),
        "confidence": float(tr["confidence"]),
        "candles": candles
    })

print(f"Extracted candle windows for all {len(trade_details)} trades.")

# Equity curve
equity = 0.0
equity_curve = []
for tr in trade_details:
    equity += tr["net_pnl"]
    equity_curve.append({
        "id": tr["id"],
        "date": tr["exit_time"],
        "pnl": tr["net_pnl"],
        "equity": equity
    })

# Tạo file HTML hoàn chỉnh
html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>VN30F1M Backtest & Trade Visualizer</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --green: #10b981;
      --green-bg: rgba(16, 185, 129, 0.15);
      --red: #ef4444;
      --red-bg: rgba(239, 68, 68, 0.15);
      --blue: #38bdf8;
      --orange: #f59e0b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); padding: 20px; }}
    .container {{ max-width: 1440px; margin: 0 auto; }}
    
    header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 15px; }}
    h1 {{ font-size: 24px; font-weight: 700; color: #fff; }}
    .badge {{ background: #2563eb; color: #fff; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
    
    /* Stats Bar */
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .kpi-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }}
    .kpi-label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px; }}
    .kpi-val {{ font-size: 20px; font-weight: 700; }}
    .positive {{ color: var(--green); }}
    .negative {{ color: var(--red); }}
    
    /* Layout */
    .main-grid {{ display: grid; grid-template-columns: 360px 1fr; gap: 20px; }}
    
    /* Trade Selector Sidebar */
    .sidebar {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; max-height: 820px; }}
    .filter-group {{ display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }}
    .filter-btn {{ background: #334155; color: #cbd5e1; border: none; padding: 5px 10px; border-radius: 6px; font-size: 11px; cursor: pointer; }}
    .filter-btn.active {{ background: #2563eb; color: #fff; font-weight: 600; }}
    .trade-list {{ flex: 1; overflow-y: auto; margin-top: 10px; padding-right: 4px; }}
    .trade-item {{ padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 8px; cursor: pointer; transition: all 0.15s ease; background: rgba(15, 23, 42, 0.4); }}
    .trade-item:hover {{ border-color: #38bdf8; background: rgba(56, 189, 248, 0.05); }}
    .trade-item.active {{ border-color: #38bdf8; background: rgba(56, 189, 248, 0.15); box-shadow: 0 0 0 1px #38bdf8; }}
    .trade-item-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }}
    .trade-type {{ font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; }}
    .trade-type.LONG {{ background: var(--green-bg); color: var(--green); }}
    .trade-type.SHORT {{ background: var(--red-bg); color: var(--red); }}
    .trade-pnl {{ font-size: 13px; font-weight: 700; }}
    .trade-time {{ font-size: 11px; color: var(--muted); }}
    
    /* Viewer Section */
    .viewer {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; display: flex; flex-direction: column; }}
    .trade-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid var(--border); padding-bottom: 12px; }}
    .nav-btns {{ display: flex; gap: 8px; }}
    .nav-btn {{ background: #334155; color: #fff; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
    .nav-btn:hover {{ background: #475569; }}
    
    /* Chart Container */
    .chart-container {{ position: relative; width: 100%; height: 500px; background: #090d16; border-radius: 8px; border: 1px solid #1e293b; overflow: hidden; }}
    canvas {{ display: block; }}
    
    /* Trade Info Box */
    .trade-details-box {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; background: #0f172a; padding: 14px; border-radius: 8px; margin-top: 15px; border: 1px solid var(--border); }}
    .detail-item {{ font-size: 12px; }}
    .detail-label {{ color: var(--muted); margin-bottom: 3px; font-size: 11px; text-transform: uppercase; }}
    .detail-val {{ font-weight: 600; font-size: 14px; }}
    
    /* Equity Curve Section */
    .equity-section {{ margin-top: 30px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
    .equity-header {{ font-size: 16px; font-weight: 700; margin-bottom: 15px; }}
    .equity-chart-container {{ position: relative; width: 100%; height: 260px; background: #090d16; border-radius: 8px; border: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>VN30F1M Walk-Forward Trade Visualizer</h1>
        <p style="color: var(--muted); font-size: 13px; margin-top: 4px;">Kiểm tra trực quan từng điểm Vào (Entry) và Ra (Exit) trên nến 1-phút (2024–2026)</p>
      </div>
      <div>
        <span class="badge">Baseline Model C + ML</span>
      </div>
    </header>

    <!-- KPI Summary Bar -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Tổng số lệnh</div>
        <div class="kpi-val" id="kpi-trades">160</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Tổng Net PnL</div>
        <div class="kpi-val positive" id="kpi-pnl">+9,080,000 đ</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Tỷ lệ Thắng (WR)</div>
        <div class="kpi-val" id="kpi-wr">48.1%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Profit Factor</div>
        <div class="kpi-val positive" id="kpi-pf">1.21</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Kỳ vọng / Lệnh</div>
        <div class="kpi-val positive" id="kpi-exp">+56,750 đ</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Chi phí tính toán</div>
        <div class="kpi-val" style="font-size: 15px;">0.3 pt slip + 30k fee</div>
      </div>
    </div>

    <!-- Main Workspace -->
    <div class="main-grid">
      <!-- Sidebar -->
      <div class="sidebar">
        <div style="font-size: 13px; font-weight: 700; margin-bottom: 10px;">Danh sách Lệnh Giao dịch</div>
        <div class="filter-group">
          <button class="filter-btn active" onclick="setFilter('ALL')">Tất cả (160)</button>
          <button class="filter-btn" onclick="setFilter('WIN')">Thắng</button>
          <button class="filter-btn" onclick="setFilter('LOSS')">Thua</button>
          <button class="filter-btn" onclick="setFilter('OVERNIGHT')">Qua đêm</button>
          <button class="filter-btn" onclick="setFilter('LONG')">Long</button>
          <button class="filter-btn" onclick="setFilter('SHORT')">Short</button>
        </div>
        <div class="trade-list" id="tradeList"></div>
      </div>

      <!-- Viewer Section -->
      <div class="viewer">
        <div class="trade-header">
          <div>
            <span style="font-size: 18px; font-weight: 700;" id="currentTradeTitle">Lệnh #1: LONG VN30F1M</span>
            <span id="currentTradeBadge" style="margin-left: 8px;" class="trade-type LONG">LONG</span>
          </div>
          <div class="nav-btns">
            <button class="nav-btn" onclick="prevTrade()">◀ Lệnh Trước</button>
            <button class="nav-btn" onclick="nextTrade()">Lệnh Kế Tiếp ▶</button>
          </div>
        </div>

        <!-- Canvas Candlestick Chart -->
        <div class="chart-container" id="chartWrapper">
          <canvas id="candleChart"></canvas>
        </div>

        <!-- Trade Details Box -->
        <div class="trade-details-box" id="tradeDetails">
          <div class="detail-item">
            <div class="detail-label">Thời gian vào</div>
            <div class="detail-val" id="dt-entry-time">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Giá vào (Entry)</div>
            <div class="detail-val" id="dt-entry-price">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Thời gian ra</div>
            <div class="detail-val" id="dt-exit-time">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Giá ra (Exit)</div>
            <div class="detail-val" id="dt-exit-price">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Lợi nhuận (Điểm)</div>
            <div class="detail-val" id="dt-points">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Net PnL (VND)</div>
            <div class="detail-val" id="dt-pnl">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Lý do thoát</div>
            <div class="detail-val" id="dt-reason">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Số nến giữ</div>
            <div class="detail-val" id="dt-bars">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">Initial Stop Loss</div>
            <div class="detail-val" id="dt-sl">--</div>
          </div>
          <div class="detail-item">
            <div class="detail-label">ML Confidence</div>
            <div class="detail-val" id="dt-conf">--</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Equity Curve -->
    <div class="equity-section">
      <div class="equity-header">Đường cong Tăng trưởng Vốn (Equity Curve 160 Lệnh OOS 2024–2026)</div>
      <div class="equity-chart-container" id="equityWrapper">
        <canvas id="equityChart"></canvas>
      </div>
    </div>
  </div>

  <script>
    const TRADES = {json.dumps(trade_details, ensure_ascii=False)};
    const EQUITY = {json.dumps(equity_curve, ensure_ascii=False)};

    let currentTradeIndex = 0;
    let currentFilter = 'ALL';

    function init() {{
      renderTradeList();
      selectTrade(0);
      drawEquityCurve();
      window.addEventListener('resize', () => {{
        renderCurrentTradeChart();
        drawEquityCurve();
      }});
    }}

    function setFilter(flt) {{
      currentFilter = flt;
      document.querySelectorAll('.filter-btn').forEach(b => {{
        b.classList.toggle('active', b.textContent.includes(flt) || (flt === 'ALL' && b.textContent.includes('Tất cả')));
      }});
      renderTradeList();
    }}

    function renderTradeList() {{
      const listEl = document.getElementById('tradeList');
      listEl.innerHTML = '';

      TRADES.forEach((tr, idx) => {{
        if (currentFilter === 'WIN' && tr.net_pnl <= 0) return;
        if (currentFilter === 'LOSS' && tr.net_pnl > 0) return;
        if (currentFilter === 'OVERNIGHT' && !tr.is_overnight) return;
        if (currentFilter === 'LONG' && tr.type !== 'LONG') return;
        if (currentFilter === 'SHORT' && tr.type !== 'SHORT') return;

        const item = document.createElement('div');
        item.className = 'trade-item' + (idx === currentTradeIndex ? ' active' : '');
        item.onclick = () => selectTrade(idx);

        const pnlFormatted = (tr.net_pnl > 0 ? '+' : '') + tr.net_pnl.toLocaleString('vi-VN') + ' đ';
        const pnlClass = tr.net_pnl > 0 ? 'positive' : 'negative';

        item.innerHTML = `
          <div class="trade-item-header">
            <span class="trade-type ${{tr.type}}">${{tr.type}} #${{tr.id}}</span>
            <span class="trade-pnl ${{pnlClass}}">${{pnlFormatted}}</span>
          </div>
          <div class="trade-time">${{tr.entry_time.split(' ')[0]}} (${{tr.points > 0 ? '+' : ''}}${{tr.points}} pts) • ${{tr.reason}}</div>
        `;
        listEl.appendChild(item);
      }});
    }}

    function selectTrade(idx) {{
      if (idx < 0 || idx >= TRADES.length) return;
      currentTradeIndex = idx;
      const tr = TRADES[idx];

      document.getElementById('currentTradeTitle').textContent = `Lệnh #${{tr.id}}: ${{tr.type}} VN30F1M (${{tr.points > 0 ? '+' : ''}}${{tr.points}} điểm)`;
      const badge = document.getElementById('currentTradeBadge');
      badge.textContent = tr.type + (tr.is_overnight ? ' (QUA ĐÊM)' : '');
      badge.className = 'trade-type ' + tr.type;

      document.getElementById('dt-entry-time').textContent = tr.entry_time;
      document.getElementById('dt-entry-price').textContent = tr.entry_price.toFixed(1);
      document.getElementById('dt-exit-time').textContent = tr.exit_time;
      document.getElementById('dt-exit-price').textContent = tr.exit_price.toFixed(1);
      
      const ptsEl = document.getElementById('dt-points');
      ptsEl.textContent = (tr.points > 0 ? '+' : '') + tr.points.toFixed(1);
      ptsEl.className = 'detail-val ' + (tr.points > 0 ? 'positive' : 'negative');

      const pnlEl = document.getElementById('dt-pnl');
      pnlEl.textContent = (tr.net_pnl > 0 ? '+' : '') + tr.net_pnl.toLocaleString('vi-VN') + ' đ';
      pnlEl.className = 'detail-val ' + (tr.net_pnl > 0 ? 'positive' : 'negative');

      document.getElementById('dt-reason').textContent = tr.reason;
      document.getElementById('dt-bars').textContent = tr.bars_held + ' nến';
      document.getElementById('dt-sl').textContent = tr.initial_sl.toFixed(1);
      document.getElementById('dt-conf').textContent = (tr.confidence * 100).toFixed(1) + '%';

      renderTradeList();
      renderCurrentTradeChart();
    }}

    function prevTrade() {{
      if (currentTradeIndex > 0) selectTrade(currentTradeIndex - 1);
    }}

    function nextTrade() {{
      if (currentTradeIndex < TRADES.length - 1) selectTrade(currentTradeIndex + 1);
    }}

    // =========================================================================
    // VẼ BIỂU ĐỒ NẾN CHO LỆNH HIỆN TẠI
    // =========================================================================
    function renderCurrentTradeChart() {{
      const wrapper = document.getElementById('chartWrapper');
      const canvas = document.getElementById('candleChart');
      const ctx = canvas.getContext('2d');
      const dpr = window.devicePixelRatio || 1;

      const w = wrapper.clientWidth;
      const h = wrapper.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.scale(dpr, dpr);

      ctx.clearRect(0, 0, w, h);

      const tr = TRADES[currentTradeIndex];
      const candles = tr.candles;
      if (!candles || candles.length === 0) return;

      const paddingLeft = 30;
      const paddingRight = 70;
      const paddingTop = 30;
      const paddingBottom = 40;

      const plotW = w - paddingLeft - paddingRight;
      const plotH = h - paddingTop - paddingBottom;

      // Tìm min, max giá (bao gồm cả stop loss & entry/exit)
      let minP = Math.min(...candles.map(c => c.l), tr.initial_sl, tr.exit_sl, tr.entry_price, tr.exit_price);
      let maxP = Math.max(...candles.map(c => c.h), tr.initial_sl, tr.exit_sl, tr.entry_price, tr.exit_price);
      const spanP = (maxP - minP) || 1.0;
      minP -= spanP * 0.08;
      maxP += spanP * 0.08;

      function yCoord(p) {{
        return paddingTop + plotH * (1 - (p - minP) / (maxP - minP));
      }}

      // Vẽ lưới ngang
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      const stepP = (maxP - minP) / 6;
      ctx.fillStyle = '#64748b';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'left';

      for (let i = 0; i <= 6; i++) {{
        const p = minP + i * stepP;
        const y = yCoord(p);
        ctx.beginPath();
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(w - paddingRight, y);
        ctx.stroke();
        ctx.fillText(p.toFixed(1), w - paddingRight + 6, y + 4);
      }}

      // Vẽ nến
      const n = candles.length;
      const candleW = Math.max(2, Math.min(14, (plotW / n) * 0.7));
      const stepX = plotW / n;

      let entryX = null;
      let exitX = null;

      candles.forEach((c, i) => {{
        const x = paddingLeft + i * stepX + stepX / 2;
        const yO = yCoord(c.o);
        const yC = yCoord(c.c);
        const yH = yCoord(c.h);
        const yL = yCoord(c.l);

        const isUp = c.c >= c.o;
        ctx.strokeStyle = isUp ? '#10b981' : '#ef4444';
        ctx.fillStyle = isUp ? '#10b981' : '#ef4444';

        // Bóng nến (Wick)
        ctx.beginPath();
        ctx.moveTo(x, yH);
        ctx.lineTo(x, yL);
        ctx.stroke();

        // Thân nến (Body)
        const top = Math.min(yO, yC);
        const height = Math.max(2, Math.abs(yC - yO));
        ctx.fillRect(x - candleW / 2, top, candleW, height);

        // Đánh dấu mốc thời gian trục X
        if (i % Math.ceil(n / 8) === 0 || i === n - 1) {{
          ctx.fillStyle = '#64748b';
          ctx.textAlign = 'center';
          ctx.fillText(c.t.split(' ')[1], x, h - paddingBottom + 16);
          ctx.fillText(c.t.split(' ')[0].substring(5), x, h - paddingBottom + 28);
        }}

        // Tìm tọa độ X của Entry và Exit
        if (c.t === tr.entry_time) entryX = x;
        if (c.t === tr.exit_time) exitX = x;
      }});

      // Vẽ đường Stop Loss
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.5;
      const ySL = yCoord(tr.initial_sl);
      ctx.beginPath();
      ctx.moveTo(paddingLeft, ySL);
      ctx.lineTo(w - paddingRight, ySL);
      ctx.stroke();
      ctx.fillStyle = '#f59e0b';
      ctx.textAlign = 'right';
      ctx.fillText(`Init SL: ${{tr.initial_sl.toFixed(1)}}`, w - paddingRight - 10, ySL - 6);

      // Nếu có trailing SL khác Initial SL
      if (Math.abs(tr.exit_sl - tr.initial_sl) > 0.2) {{
        ctx.strokeStyle = '#38bdf8';
        const yExitSL = yCoord(tr.exit_sl);
        ctx.beginPath();
        ctx.moveTo(paddingLeft, yExitSL);
        ctx.lineTo(w - paddingRight, yExitSL);
        ctx.stroke();
        ctx.fillStyle = '#38bdf8';
        ctx.fillText(`Trailing SL: ${{tr.exit_sl.toFixed(1)}}`, w - paddingRight - 10, yExitSL - 6);
      }}
      ctx.setLineDash([]);

      // Vẽ Vị trí VÀO LỆNH (Entry Marker)
      if (entryX !== null) {{
        const yEnt = yCoord(tr.entry_price);
        const isLong = tr.type === 'LONG';
        
        ctx.fillStyle = isLong ? '#10b981' : '#ef4444';
        ctx.beginPath();
        if (isLong) {{
          ctx.moveTo(entryX, yEnt + 6);
          ctx.lineTo(entryX - 8, yEnt + 22);
          ctx.lineTo(entryX + 8, yEnt + 22);
        }} else {{
          ctx.moveTo(entryX, yEnt - 6);
          ctx.lineTo(entryX - 8, yEnt - 22);
          ctx.lineTo(entryX + 8, yEnt - 22);
        }}
        ctx.closePath();
        ctx.fill();

        ctx.font = 'bold 12px sans-serif';
        ctx.fillStyle = isLong ? '#10b981' : '#ef4444';
        ctx.textAlign = 'center';
        ctx.fillText(`ENTRY ${{tr.type}} @ ${{tr.entry_price.toFixed(1)}}`, entryX, isLong ? yEnt + 36 : yEnt - 28);
      }}

      // Vẽ Vị trí THOÁT LỆNH (Exit Marker)
      if (exitX !== null) {{
        const yExt = yCoord(tr.exit_price);
        ctx.fillStyle = '#e2e8f0';
        ctx.beginPath();
        ctx.arc(exitX, yExt, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#090d16';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.font = 'bold 12px sans-serif';
        ctx.fillStyle = tr.net_pnl > 0 ? '#10b981' : '#ef4444';
        ctx.textAlign = 'center';
        ctx.fillText(`EXIT (${{tr.reason}}) @ ${{tr.exit_price.toFixed(1)}}`, exitX, yExt - 14);
      }}

      // Nối đường Entry -> Exit
      if (entryX !== null && exitX !== null) {{
        ctx.strokeStyle = tr.net_pnl > 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)';
        ctx.lineWidth = 2;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(entryX, yCoord(tr.entry_price));
        ctx.lineTo(exitX, yCoord(tr.exit_price));
        ctx.stroke();
        ctx.setLineDash([]);
      }}
    }}

    // =========================================================================
    // VẼ ĐƯỜNG CONG TĂNG TRƯỞNG VỐN (EQUITY CURVE)
    // =========================================================================
    function drawEquityCurve() {{
      const wrapper = document.getElementById('equityWrapper');
      const canvas = document.getElementById('equityChart');
      const ctx = canvas.getContext('2d');
      const dpr = window.devicePixelRatio || 1;

      const w = wrapper.clientWidth;
      const h = wrapper.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.scale(dpr, dpr);

      ctx.clearRect(0, 0, w, h);

      const paddingLeft = 40;
      const paddingRight = 60;
      const paddingTop = 20;
      const paddingBottom = 30;

      const plotW = w - paddingLeft - paddingRight;
      const plotH = h - paddingTop - paddingBottom;

      const eqVals = EQUITY.map(e => e.equity);
      let minE = Math.min(0, ...eqVals);
      let maxE = Math.max(0, ...eqVals);
      const span = (maxE - minE) || 1.0;
      minE -= span * 0.1;
      maxE += span * 0.1;

      function yCoord(e) {{
        return paddingTop + plotH * (1 - (e - minE) / (maxE - minE));
      }}

      // Đường 0 PnL
      const yZero = yCoord(0);
      ctx.strokeStyle = '#334155';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(paddingLeft, yZero);
      ctx.lineTo(w - paddingRight, yZero);
      ctx.stroke();
      ctx.setLineDash([]);

      // Vẽ vùng diện tích Gradient
      const grad = ctx.createLinearGradient(0, paddingTop, 0, paddingTop + plotH);
      grad.addColorStop(0, 'rgba(56, 189, 248, 0.3)');
      grad.addColorStop(1, 'rgba(56, 189, 248, 0.0)');

      ctx.beginPath();
      EQUITY.forEach((e, i) => {{
        const x = paddingLeft + (i / (EQUITY.length - 1)) * plotW;
        const y = yCoord(e.equity);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }});
      ctx.lineTo(paddingLeft + plotW, yZero);
      ctx.lineTo(paddingLeft, yZero);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Vẽ đường Line
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      EQUITY.forEach((e, i) => {{
        const x = paddingLeft + (i / (EQUITY.length - 1)) * plotW;
        const y = yCoord(e.equity);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }});
      ctx.stroke();

      // Đánh dấu điểm lệnh hiện tại trên Equity Curve
      const curX = paddingLeft + (currentTradeIndex / (EQUITY.length - 1)) * plotW;
      const curY = yCoord(EQUITY[currentTradeIndex].equity);
      ctx.fillStyle = '#f59e0b';
      ctx.beginPath();
      ctx.arc(curX, curY, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Hiển thị giá trị đỉnh
      ctx.fillStyle = '#94a3b8';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText((maxE / 1000000).toFixed(1) + 'M', w - paddingRight + 8, paddingTop + 10);
      ctx.fillText('0.0M', w - paddingRight + 8, yZero + 4);
      ctx.fillText((minE / 1000000).toFixed(1) + 'M', w - paddingRight + 8, paddingTop + plotH);
    }}

    window.onload = init;
  </script>
</body>
</html>
"""

output_path = "results/vn30f1m_trade_visualizer.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Đã tạo thành công file biểu đồ tương tác tại: {output_path}")

