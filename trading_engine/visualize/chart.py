import os
import argparse
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .logging_config import logger

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Load the unified feature parquet (candles + indicators)
FEATURES_PATH = os.path.join(BASE_DIR, "trading_engine", "data", "VN30F1M_features.parquet")
TRADES_PATH = os.path.join(BASE_DIR, "trading_engine", "data", "backtest_trades.csv")

def load_data():
    if not os.path.exists(FEATURES_PATH):
        raise FileNotFoundError(f"Features parquet not found at {FEATURES_PATH}.")
    df = pd.read_parquet(FEATURES_PATH)
    
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
        else:
            df.index = pd.to_datetime(df.index)
            
    if not os.path.exists(TRADES_PATH):
        raise FileNotFoundError(f"Backtest trades not found at {TRADES_PATH}. Run backtest first.")
    trades = pd.read_csv(TRADES_PATH)
    # Normalize column names from backtest engine to expected ones
    col_map = {
        'Entry Date': 'entry_time',
        'Exit Date': 'exit_time',
        'Entry': 'entry_price',
        'Exit': 'exit_price',
        'PnL': 'pnl',
        'Type': 'direction'
    }
    trades.rename(columns=col_map, inplace=True)
    # Convert direction to numeric signal: LONG=1, SHORT=-1
    trades['direction'] = trades['direction'].apply(lambda x: 1 if x == 'LONG' else -1)
    # Ensure datetime conversion
    trades['entry_time'] = pd.to_datetime(trades['entry_time'])
    trades['exit_time'] = pd.to_datetime(trades['exit_time'])
    
    return df, trades

def filter_data(df, trades, args):
    if args.session:
        session_date = pd.to_datetime(args.session).date()
        df = df[df.index.date == session_date]
    elif args.from_date or args.to_date:
        if args.from_date:
            df = df[df.index >= pd.to_datetime(args.from_date)]
        if args.to_date:
            df = df[df.index <= pd.to_datetime(args.to_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    elif args.days:
        unique_dates = pd.Series(df.index.date).unique()
        if len(unique_dates) > args.days:
            start_date = unique_dates[-args.days]
            df = df[df.index.date >= start_date]
    elif args.bars:
        df = df.iloc[-args.bars:]
    else:
        # Default to 5000 bars
        df = df.iloc[-5000:]
        
    trades = trades[trades['entry_time'].isin(df.index)]
    trades = trades[trades.get('Confidence', 1) >= args.min_conf].copy()
    
    return df, trades

def calc_dashboard_metrics(trades):
    if len(trades) == 0:
        return {"Trades": 0, "Winrate": "0%", "PF": 0, "Net Profit": 0, "Avg Profit": 0, "Avg Loss": 0, "Expectancy": 0, "Sharpe": 0, "Recovery Factor": 0, "Avg Hold": "0m", "Max DD": 0}
        
    # Basic trade counts
    trades_count = len(trades)
    if trades_count == 0:
        return {"Trades": 0, "Winrate": "0%", "PF": 0, "Net Profit": 0, "Avg Profit": 0, "Avg Loss": 0, "Expectancy": 0, "Sharpe": 0, "Recovery Factor": 0, "Avg Hold": "0m", "Max DD": 0}

    wins = trades[trades['pnl'] > 0]
    losses = trades[trades['pnl'] <= 0]
    winrate = len(wins) / trades_count * 100

    # Profit Factor
    gross_profit = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_profit = trades['pnl'].sum()

    # Average profit/loss
    avg_profit = wins['pnl'].mean() if not wins.empty else 0
    avg_loss = losses['pnl'].mean() if not losses.empty else 0

    # Expectancy (per trade)
    expectancy = (avg_profit * (winrate / 100)) + (avg_loss * (1 - winrate / 100))

    # Sharpe (using PnL returns normalized by initial capital, assume initial capital 100M)
    initial_capital = 100000000.0
    returns = trades['pnl'] / initial_capital
    sharpe = (returns.mean() / returns.std()) if returns.std() != 0 else 0

    # Recovery Factor
    # Compute max drawdown from cumulative PnL
    cum_profit = trades['pnl'].cumsum()
    peak = cum_profit.cummax()
    drawdown = peak - cum_profit
    max_dd = drawdown.max()
    recovery_factor = net_profit / max_dd if max_dd != 0 else float('inf')

    # Avg hold time (minutes)
    trades['exit_time'] = pd.to_datetime(trades['exit_time'])
    hold_times = (trades['exit_time'] - trades['entry_time']).dt.total_seconds() / 60
    avg_hold = hold_times.mean()

    return {
        "Trades": trades_count,
        "Winrate": f"{winrate:.1f}%",
        "PF": f"{pf:.2f}",
        "Net Profit": f"{net_profit:.1f} pts",
        "Avg Profit": f"{avg_profit:.2f}",
        "Avg Loss": f"{avg_loss:.2f}",
        "Expectancy": f"{expectancy:.2f}",
        "Sharpe": f"{sharpe:.2f}",
        "Recovery Factor": f"{recovery_factor:.2f}",
        "Avg Hold": f"{avg_hold:.0f} min",
        "Max DD": f"{max_dd:.1f} pts"
    }

import pandas_ta as ta

def get_color(conf, signal):
    # Colors: Dark Green/Red (>90%), Light Green/Red (75-90%), Grey (<75%)
    if conf >= 0.90:
        return 'rgba(0, 128, 0, 1)' if signal == 1 else 'rgba(255, 0, 0, 1)'
    elif conf >= 0.75:
        return 'rgba(0, 255, 0, 0.8)' if signal == 1 else 'rgba(255, 100, 100, 0.8)'
    else:
        return 'rgba(128, 128, 128, 0.6)'

def create_chart(df, trades, metrics):
    # Calculate missing indicators for UI dynamically
    # MAs: MA10, MA20, MA50, MA100, MA150, MA200 (Using SMA)
    # Indicators are pre‑computed in the parquet; no runtime SMA generation needed.
    # Ichimoku Cloud
    ichimoku, _ = ta.ichimoku(df['High'], df['Low'], df['Close'])
    # ichimoku returns columns like ISA_9, ISB_26, ITS_9, IKS_26, ICS_26
    # Let's dynamically find the exact column names
    if ichimoku is not None:
        isa_col = [c for c in ichimoku.columns if c.startswith('ISA')][0]
        isb_col = [c for c in ichimoku.columns if c.startswith('ISB')][0]
        its_col = [c for c in ichimoku.columns if c.startswith('ITS')][0]
        iks_col = [c for c in ichimoku.columns if c.startswith('IKS')][0]
    
    # Create subplots: 2 rows, Row 1 = Price + Indicators, Row 2 = Volume
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03)
    
    # Layer 1: Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Price", increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
    ), row=1, col=1)
    
    # Layer 2: MAs
    colors = {10: '#E1BEE7', 20: '#CE93D8', 50: '#BA68C8', 100: '#AB47BC', 150: '#8E24AA', 200: '#4A148C', 1500: '#311B92'}
    for length in [10, 20, 50, 100, 150, 200, 1500]:
        if f'SMA{length}' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[f'SMA{length}'], mode='lines', name=f'MA{length}', line=dict(color=colors[length], width=1)), row=1, col=1)
            
    # Layer 3: VWAP
    if 'VWAP' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], mode='lines', name='VWAP', line=dict(color='orange', width=2, dash='dot')), row=1, col=1)
        
    # Layer 4: Bollinger Bands
    if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], mode='lines', name='BB Upper', line=dict(color='rgba(173, 216, 230, 0.5)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], mode='lines', name='BB Lower', line=dict(color='rgba(173, 216, 230, 0.5)', width=1), fill='tonexty', fillcolor='rgba(173, 216, 230, 0.1)'), row=1, col=1)

    # Layer 5: Ichimoku Cloud
    if ichimoku is not None:
        fig.add_trace(go.Scatter(x=df.index, y=ichimoku[isa_col], mode='lines', name='Senkou Span A', line=dict(color='rgba(0, 255, 0, 0.3)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=ichimoku[isb_col], mode='lines', name='Senkou Span B', line=dict(color='rgba(255, 0, 0, 0.3)', width=1), fill='tonexty', fillcolor='rgba(128, 128, 128, 0.1)'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=ichimoku[its_col], mode='lines', name='Tenkan-sen', line=dict(color='#0288D1', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=ichimoku[iks_col], mode='lines', name='Kijun-sen', line=dict(color='#D32F2F', width=1)), row=1, col=1)

    # Layer 6: Volume (Bottom Subplot)
    vol_colors = ['#26a69a' if row['Close'] >= row['Open'] else '#ef5350' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name="Volume"), row=2, col=1)
        
    # Layer 7: Markers and Hover Text
    buy_preds = trades[trades['direction'] == 1]
    sell_preds = trades[trades['direction'] == -1]
    
    def add_markers(subset, is_buy):
        if len(subset) == 0: return
        
        merged = subset.merge(df, left_on='entry_time', right_index=True, how='left')
        # Use ATR‑based offset for clearer marker placement
        offset = merged['ATR'] * 0.3 if 'ATR' in merged.columns else 2
        y_pos = merged['Low'] - offset if is_buy else merged['High'] + offset
        marker_symbol = 'triangle-up' if is_buy else 'triangle-down'
        
        colors = [get_color(c, 1 if is_buy else -1) for c in subset['Confidence']]
        
        hover_texts = []
        for _, row in merged.iterrows():
            tp_dist = abs(row['tp'] - row['entry_price'])
            sl_dist = abs(row['entry_price'] - row['sl'])
            txt = (f"<b>{'BUY' if is_buy else 'SELL'}</b><br>"
                   f"Time: {row['entry_time']}<br>"
                   f"Confidence: {row.get('Confidence', 0)*100:.1f}%<br>"
                   f"Close: {row.get('entry_price', '')}<br>"
                   f"TP: +{row.get('tp', 0):.1f} | SL: -{row.get('sl', 0):.1f}<br>"
                   f"ATR: {row.get('ATR', 0):.2f}<br>"
                   f"Volume Spike: {row.get('RVOL', 0):.1f}x<br>"
                   f"EMA Dist: {row.get('EMA_Distance', 0)*100:.2f}%<br>"
                   f"RSI: {row.get('RSI', 0):.1f}")
            hover_texts.append(txt)
            
        fig.add_trace(go.Scatter(
            x=merged['entry_time'],
            y=y_pos,
            mode='markers',
            marker=dict(symbol=marker_symbol, size=12, color=colors, line=dict(width=1, color='black')),
            name="BUY Signal" if is_buy else "SELL Signal",
            text=hover_texts,
            hoverinfo='text'
        ), row=1, col=1)
        
    add_markers(buy_preds, is_buy=True)
    add_markers(sell_preds, is_buy=False)
    
    # Dashboard Annotation
    dashboard_text = (
        f"<b>Thống kê (Mini Backtest)</b><br>"
        f"--------------------------<br>"
        f"Trades: {metrics['Trades']}<br>"
        f"Winrate: {metrics['Winrate']}<br>"
        f"Profit Factor: {metrics['PF']}<br>"
        f"Net Profit: {metrics['Net Profit']}<br>"
        f"Avg Profit: {metrics['Avg Profit']}<br>"
        f"Avg Loss: {metrics['Avg Loss']}<br>"
        f"Expectancy: {metrics['Expectancy']}<br>"
        f"Sharpe: {metrics['Sharpe']}<br>"
        f"Recovery Factor: {metrics['Recovery Factor']}<br>"
        f"Avg Hold: {metrics['Avg Hold']}<br>"
        f"Max Drawdown: {metrics['Max DD']}"
    )    
    fig.add_annotation(
        text=dashboard_text,
        align='left',
        showarrow=False,
        xref='paper', yref='paper',
        x=0.01, y=0.98,
        bordercolor='black',
        borderwidth=1,
        borderpad=10,
        bgcolor='rgba(255, 255, 255, 0.9)',
        font=dict(size=12, color='black')
    )
    
    # Layout adjustments
    fig.update_layout(
        title="VN30F1M Trading Engine Visualization",
        yaxis_title="Price",
        yaxis2_title="Volume",
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
        template='plotly_white',
        height=900,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # Save and show
    out_file = os.path.join(BASE_DIR, "trading_engine", "visualize", "chart.html")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    fig.write_html(out_file)
    print(f"Chart saved to {out_file}")
    
    # Try to open automatically
    import webbrowser
    webbrowser.open(f"file:///{out_file.replace(os.sep, '/')}")

def main():
    parser = argparse.ArgumentParser(description="Visualize Backtest Results.")
    parser.add_argument("--bars", type=int, help="Number of recent bars to show (e.g. 5000)")
    parser.add_argument("--days", type=int, help="Number of recent days to show")
    parser.add_argument("--from-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--session", type=str, help="Single trading session date (YYYY-MM-DD)")
    parser.add_argument("--min-conf", type=float, default=0.0, help="Minimum confidence threshold (0.0 to 1.0)")
    
    args = parser.parse_args()
    
    print("Loading data...")
    df, trades = load_data()
    
    print("Filtering data...")
    df_filtered, trades_filtered = filter_data(df, trades, args)
    
    print("Calculating metrics...")
    metrics = calc_dashboard_metrics(trades_filtered)
    
    print("Generating chart...")
    create_chart(df_filtered, trades_filtered, metrics)

if __name__ == "__main__":
    main()
