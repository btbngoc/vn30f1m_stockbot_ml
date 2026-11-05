from __future__ import annotations

import argparse
import html
import json
import shutil
import webbrowser
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..run_context import (
    generate_run_id,
    get_run_dir,
    read_latest_run_id,
    validate_run_id,
    write_latest_run_id,
)


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "trading_engine" / "data"
FEATURES_PATH = DATA_DIR / "VN30F1M_features.parquet"
LATEST_TRADES_PATH = DATA_DIR / "backtest_trades.csv"
LATEST_DASHBOARD_PATH = DATA_DIR / "dashboard.json"
LATEST_CHART_PATH = BASE_DIR / "trading_engine" / "visualize" / "chart.html"


def load_data(trades_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Features parquet not found at {FEATURES_PATH}.")
    # Load only columns used by this view; the full feature file currently has
    # more than 100 columns and is unnecessarily expensive to deserialize.
    selected_columns = [
        "datetime",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "VWAP",
        "ATR",
        "BB_Upper",
        "BB_Lower",
    ]
    df = pd.read_parquet(FEATURES_PATH, columns=selected_columns)

    if not isinstance(df.index, pd.DatetimeIndex):
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="raise")
            df.set_index("datetime", inplace=True)
        else:
            df.index = pd.to_datetime(df.index, errors="raise")
    df = df.sort_index()

    if not trades_path.exists():
        raise FileNotFoundError(f"Backtest trades not found at {trades_path}.")
    trades = pd.read_csv(trades_path)
    trades.rename(
        columns={
            "Entry Date": "entry_time",
            "Exit Date": "exit_time",
            "Entry": "entry_price",
            "Exit": "exit_price",
            "PnL": "pnl",
            "Type": "direction",
            "Initial Stop Loss": "sl",
            "Take Profit": "tp",
        },
        inplace=True,
    )

    required = {"entry_time", "exit_time", "entry_price", "pnl", "direction"}
    missing = required.difference(trades.columns)
    if missing:
        raise ValueError(f"Trade file is missing columns: {', '.join(sorted(missing))}")

    if "Confidence" not in trades.columns:
        trades["Confidence"] = 1.0
    trades["Confidence"] = pd.to_numeric(trades["Confidence"], errors="coerce").fillna(0.0)
    trades["direction"] = trades["direction"].map(
        lambda value: 1 if str(value).upper() == "LONG" or value == 1 else -1
    )
    trades["entry_time"] = pd.to_datetime(trades["entry_time"], errors="raise")
    trades["exit_time"] = pd.to_datetime(trades["exit_time"], errors="raise")
    return df, trades.sort_values("entry_time")


def resolve_run_trades(run_id: str | None) -> tuple[str, Path]:
    """Use an immutable run snapshot, creating one from the legacy latest file if needed."""
    selected_run_id = validate_run_id(run_id) if run_id else read_latest_run_id()
    if selected_run_id:
        run_trades = get_run_dir(selected_run_id) / "backtest_trades.csv"
        if run_trades.exists():
            return selected_run_id, run_trades
        if run_id:
            raise FileNotFoundError(
                f"Run {selected_run_id} has no backtest snapshot at {run_trades}."
            )

    if not LATEST_TRADES_PATH.exists():
        raise FileNotFoundError(
            f"Backtest trades not found at {LATEST_TRADES_PATH}. Run backtest first."
        )

    selected_run_id = generate_run_id()
    run_dir = get_run_dir(selected_run_id, create=True)
    run_trades = run_dir / "backtest_trades.csv"
    shutil.copy2(LATEST_TRADES_PATH, run_trades)
    write_latest_run_id(selected_run_id)
    return selected_run_id, run_trades


def filter_data(
    df: pd.DataFrame, trades: pd.DataFrame, args: argparse.Namespace
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if args.session:
        session_date = pd.to_datetime(args.session, errors="raise").date()
        df = df[df.index.date == session_date]
    elif args.from_date or args.to_date:
        if args.from_date:
            df = df[df.index >= pd.to_datetime(args.from_date, errors="raise")]
        if args.to_date:
            end = pd.to_datetime(args.to_date, errors="raise") + pd.Timedelta(days=1)
            df = df[df.index < end]
    elif args.days is not None:
        unique_dates = pd.Index(df.index.date).unique()
        if len(unique_dates) > args.days:
            df = df[df.index.date >= unique_dates[-args.days]]
    elif args.bars is not None:
        df = df.iloc[-args.bars :]
    else:
        # A chart with 5,000 one-minute candles is too dense for normal review.
        # Default to the three most recent trading sessions.
        unique_dates = pd.Index(df.index.date).unique()
        if len(unique_dates) > 3:
            df = df[df.index.date >= unique_dates[-3]]

    if df.empty:
        raise ValueError("The selected chart window contains no candles.")

    start, end = df.index.min(), df.index.max()
    in_window = trades["entry_time"].between(start, end, inclusive="both")
    passes_confidence = trades["Confidence"] >= args.min_conf
    return df, trades[in_window & passes_confidence].copy()


def resample_dataframe(df: pd.DataFrame, timeframe: str = "5m") -> pd.DataFrame:
    if timeframe == "5m":
        resample_rules = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
        resampled = df.resample("5min").agg(resample_rules).dropna(subset=["Open"])
    else:
        resampled = df.copy()

    # Recalculate VWAP
    typical_price = (resampled["High"] + resampled["Low"] + resampled["Close"]) / 3
    tp_v = typical_price * resampled["Volume"]
    dates = resampled.index.date
    cumsum_vol = resampled["Volume"].groupby(dates).cumsum()
    cumsum_tpv = tp_v.groupby(dates).cumsum()
    resampled["VWAP"] = cumsum_tpv / cumsum_vol.replace(0, pd.NA)

    # Recalculate SMAs for timeframe
    for length in (10, 20, 50, 100, 150, 200, 1500):
        if len(resampled) >= length:
            resampled[f"SMA{length}"] = resampled["Close"].rolling(length).mean()

    # Recalculate Bollinger Bands
    sma20 = resampled["Close"].rolling(20).mean()
    std20 = resampled["Close"].rolling(20).std()
    resampled["BB_Upper"] = sma20 + 2 * std20
    resampled["BB_Lower"] = sma20 - 2 * std20

    # Recalculate ATR
    tr1 = resampled["High"] - resampled["Low"]
    tr2 = (resampled["High"] - resampled["Close"].shift(1)).abs()
    tr3 = (resampled["Low"] - resampled["Close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    resampled["ATR"] = tr.rolling(14).mean()

    return resampled


def calc_dashboard_metrics(trades: pd.DataFrame) -> dict[str, object]:
    if trades.empty:
        return {
            "Trades": 0,
            "Winrate": "0.0%",
            "Profit Factor": "0.00",
            "Net Profit": "0",
            "Avg Profit": "0.00",
            "Avg Loss": "0.00",
            "Expectancy": "0.00",
            "Trade Sharpe": "0.00",
            "Recovery Factor": "0.00",
            "Avg Hold": "0 min",
            "Max Drawdown": "0",
        }

    trades = trades.copy()
    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]
    trades_count = len(trades)
    winrate = len(wins) / trades_count * 100
    gross_profit = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    net_profit = trades["pnl"].sum()
    avg_profit = wins["pnl"].mean() if not wins.empty else 0.0
    avg_loss = losses["pnl"].mean() if not losses.empty else 0.0
    expectancy = avg_profit * (winrate / 100) + avg_loss * (1 - winrate / 100)

    pnl_std = trades["pnl"].std(ddof=1)
    trade_sharpe = trades["pnl"].mean() / pnl_std if pd.notna(pnl_std) and pnl_std else 0.0
    cumulative = pd.concat([pd.Series([0.0]), trades["pnl"].cumsum()], ignore_index=True)
    drawdown = cumulative.cummax() - cumulative
    max_drawdown = drawdown.max()
    recovery_factor = net_profit / max_drawdown if max_drawdown else float("inf")
    hold_minutes = (
        (trades["exit_time"] - trades["entry_time"]).dt.total_seconds() / 60
    ).mean()

    def ratio(value: float) -> str:
        return "∞" if value == float("inf") else f"{value:.2f}"

    return {
        "Trades": trades_count,
        "Winrate": f"{winrate:.1f}%",
        "Profit Factor": ratio(profit_factor),
        "Net Profit": f"{net_profit:,.0f}",
        "Avg Profit": f"{avg_profit:,.2f}",
        "Avg Loss": f"{avg_loss:,.2f}",
        "Expectancy": f"{expectancy:,.2f}",
        "Trade Sharpe": f"{trade_sharpe:.2f}",
        "Recovery Factor": ratio(recovery_factor),
        "Avg Hold": f"{hold_minutes:.0f} min",
        "Max Drawdown": f"{max_drawdown:,.0f}",
    }


def get_color(confidence: float, signal: int) -> str:
    if confidence >= 0.90:
        return "rgba(0, 128, 0, 1)" if signal == 1 else "rgba(255, 0, 0, 1)"
    if confidence >= 0.75:
        return "rgba(0, 190, 0, 0.85)" if signal == 1 else "rgba(255, 100, 100, 0.85)"
    return "rgba(128, 128, 128, 0.65)"


def create_chart(df: pd.DataFrame, trades: pd.DataFrame, timeframe: str = "5m") -> go.Figure:
    df_plot = df.copy()
    # Format datetime as string category to completely remove non-trading gaps (overnight, lunch break, weekends)
    df_plot["x_str"] = df_plot.index.strftime("%Y-%m-%d %H:%M")
    x_str = df_plot["x_str"]

    high_9 = df_plot["High"].rolling(9).max()
    low_9 = df_plot["Low"].rolling(9).min()
    high_26 = df_plot["High"].rolling(26).max()
    low_26 = df_plot["Low"].rolling(26).min()
    tenkan = (high_9 + low_9) / 2
    kijun = (high_26 + low_26) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = (
        (df_plot["High"].rolling(52).max() + df_plot["Low"].rolling(52).min()) / 2
    ).shift(26)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.74, 0.26],
        vertical_spacing=0.04,
    )

    # Main Candlestick Chart
    fig.add_trace(
        go.Candlestick(
            x=x_str,
            open=df_plot["Open"],
            high=df_plot["High"],
            low=df_plot["Low"],
            close=df_plot["Close"],
            name=f"Price ({timeframe})",
            increasing=dict(fillcolor="#0f9d8a", line=dict(color="#0f9d8a", width=1.5)),
            decreasing=dict(fillcolor="#e5524a", line=dict(color="#e5524a", width=1.5)),
        ),
        row=1,
        col=1,
    )

    # Primary Moving Averages
    ma_colors = {
        10: "#E1BEE7",
        20: "#0288D1",
        50: "#BA68C8",
        100: "#AB47BC",
        150: "#8E24AA",
        200: "#D32F2F",
        1500: "#311B92",
    }
    # Keep MA20, MA50, MA200 visible by default, others legendonly for clean view
    visible_mas = {20, 50, 200}
    for length in (10, 20, 50, 100, 150, 200, 1500):
        column = f"SMA{length}"
        if column in df_plot.columns:
            fig.add_trace(
                go.Scatter(
                    x=x_str,
                    y=df_plot[column],
                    mode="lines",
                    name=f"MA{length}",
                    line=dict(color=ma_colors[length], width=1.2 if length in visible_mas else 1),
                    visible=True if length in visible_mas else "legendonly",
                ),
                row=1,
                col=1,
            )

    if "VWAP" in df_plot.columns:
        fig.add_trace(
            go.Scatter(
                x=x_str,
                y=df_plot["VWAP"],
                mode="lines",
                name="VWAP",
                line=dict(color="#f59e0b", width=2, dash="dot"),
            ),
            row=1,
            col=1,
        )

    if {"BB_Upper", "BB_Lower"}.issubset(df_plot.columns):
        fig.add_trace(
            go.Scatter(
                x=x_str,
                y=df_plot["BB_Upper"],
                mode="lines",
                name="BB Upper",
                line=dict(color="rgba(14, 165, 233, 0.4)", width=1),
                visible="legendonly",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=x_str,
                y=df_plot["BB_Lower"],
                mode="lines",
                name="BB Lower",
                line=dict(color="rgba(14, 165, 233, 0.4)", width=1),
                fill="tonexty",
                fillcolor="rgba(14, 165, 233, 0.06)",
                visible="legendonly",
            ),
            row=1,
            col=1,
        )

    # Ichimoku Cloud (optional toggle in legend)
    fig.add_trace(
        go.Scatter(
            x=x_str,
            y=senkou_a,
            mode="lines",
            name="Senkou Span A",
            line=dict(color="rgba(34, 197, 94, 0.35)", width=1),
            visible="legendonly",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_str,
            y=senkou_b,
            mode="lines",
            name="Senkou Span B",
            line=dict(color="rgba(239, 68, 68, 0.35)", width=1),
            fill="tonexty",
            fillcolor="rgba(100, 116, 139, 0.08)",
            visible="legendonly",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_str,
            y=tenkan,
            mode="lines",
            name="Tenkan-sen",
            line=dict(color="#0288D1", width=1),
            visible="legendonly",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_str,
            y=kijun,
            mode="lines",
            name="Kijun-sen",
            line=dict(color="#D32F2F", width=1),
            visible="legendonly",
        ),
        row=1,
        col=1,
    )

    # Volume Subplot
    volume_colors = [
        "#0f9d8a" if close >= open_ else "#e5524a"
        for open_, close in zip(df_plot["Open"], df_plot["Close"])
    ]
    fig.add_trace(
        go.Bar(
            x=x_str,
            y=df_plot["Volume"],
            marker_color=volume_colors,
            name="Volume",
            opacity=0.85,
        ),
        row=2,
        col=1,
    )

    # Trade Visuals: Entry Markers (L/S), Exit Markers (X), and Entry->Exit Lines
    def add_trade_visuals(trades_df: pd.DataFrame) -> None:
        if trades_df.empty:
            return

        trades_copy = trades_df.copy()
        if timeframe == "5m":
            trades_copy["entry_candle"] = trades_copy["entry_time"].dt.floor("5min")
            trades_copy["exit_candle"] = trades_copy["exit_time"].dt.floor("5min")
        else:
            trades_copy["entry_candle"] = trades_copy["entry_time"]
            trades_copy["exit_candle"] = trades_copy["exit_time"]

        trades_copy["entry_x_str"] = trades_copy["entry_candle"].dt.strftime("%Y-%m-%d %H:%M")
        trades_copy["exit_x_str"] = trades_copy["exit_candle"].dt.strftime("%Y-%m-%d %H:%M")

        valid_dates = set(df_plot["x_str"])

        # 1. Entry Markers (LONG L / SHORT S)
        for is_buy in [True, False]:
            direction_val = 1 if is_buy else -1
            subset = trades_copy[trades_copy["direction"] == direction_val].copy()
            subset = subset[subset["entry_x_str"].isin(valid_dates)]
            if subset.empty:
                continue

            merged = subset.merge(df_plot, left_on="entry_x_str", right_on="x_str", how="inner")
            if merged.empty:
                continue

            offset = merged["ATR"].fillna(2) * 0.35 if "ATR" in merged.columns else 2.0
            y_position = merged["Low"] - offset if is_buy else merged["High"] + offset
            hover_texts = []
            for _, row in merged.iterrows():
                direction_str = "LONG ENTRY" if is_buy else "SHORT ENTRY"
                hover_texts.append(
                    f"<b>{direction_str}</b><br>"
                    f"Entry Time: {row['entry_time']}<br>"
                    f"Entry Price: {row.get('entry_price', '')}<br>"
                    f"Confidence: {row.get('Confidence', 0) * 100:.1f}%<br>"
                    f"TP: {row.get('tp', '')} | SL: {row.get('sl', '')}"
                )
            fig.add_trace(
                go.Scatter(
                    x=merged["entry_x_str"],
                    y=y_position,
                    mode="markers+text",
                    text=["L" if is_buy else "S"] * len(merged),
                    textposition="bottom center" if is_buy else "top center",
                    textfont=dict(size=13, color="#0f9d8a" if is_buy else "#e5524a", family="Segoe UI, Arial, sans-serif"),
                    marker=dict(
                        symbol="triangle-up" if is_buy else "triangle-down",
                        size=14,
                        color=[
                            get_color(value, 1 if is_buy else -1)
                            for value in merged["Confidence"]
                        ],
                        line=dict(width=1.2, color="#111827"),
                    ),
                    name="LONG Entry (L)" if is_buy else "SHORT Entry (S)",
                    hovertext=hover_texts,
                    hoverinfo="text",
                ),
                row=1,
                col=1,
            )

        # 2. Exit Markers (Win / Loss)
        for is_win in [True, False]:
            subset = trades_copy[(trades_copy["pnl"] > 0) if is_win else (trades_copy["pnl"] <= 0)].copy()
            subset = subset[subset["exit_x_str"].isin(valid_dates)]
            if subset.empty:
                continue

            merged = subset.merge(df_plot, left_on="exit_x_str", right_on="x_str", how="inner")
            if merged.empty:
                continue

            y_position = merged["exit_price"].fillna(merged["Close"])
            hover_texts = []
            for _, row in merged.iterrows():
                result_str = "EXIT (WIN)" if is_win else "EXIT (LOSS)"
                pnl_val = row.get("pnl", 0)
                pnl_sign = f"+{pnl_val:,.0f}" if pnl_val > 0 else f"{pnl_val:,.0f}"
                hover_texts.append(
                    f"<b>{result_str}</b><br>"
                    f"Exit Time: {row['exit_time']}<br>"
                    f"Exit Price: {row.get('exit_price', '')}<br>"
                    f"PnL: {pnl_sign} VND<br>"
                    f"Entry Time: {row['entry_time']}<br>"
                    f"Entry Price: {row.get('entry_price', '')}"
                )

            fig.add_trace(
                go.Scatter(
                    x=merged["exit_x_str"],
                    y=y_position,
                    mode="markers+text",
                    text=["X"] * len(merged),
                    textposition="top center" if is_win else "bottom center",
                    textfont=dict(size=12, color="#059669" if is_win else "#dc2626", family="Segoe UI, Arial, sans-serif"),
                    marker=dict(
                        symbol="square",
                        size=10,
                        color="#059669" if is_win else "#dc2626",
                        line=dict(width=1, color="#111827"),
                    ),
                    name="Exit (Win)" if is_win else "Exit (Loss)",
                    hovertext=hover_texts,
                    hoverinfo="text",
                ),
                row=1,
                col=1,
            )

        # 3. Connecting Lines from Entry -> Exit
        win_x, win_y = [], []
        loss_x, loss_y = [], []

        for _, row in trades_copy.iterrows():
            entry_x = row["entry_x_str"]
            exit_x = row["exit_x_str"]
            if entry_x in valid_dates and exit_x in valid_dates:
                entry_y = row.get("entry_price")
                exit_y = row.get("exit_price")
                if pd.notna(entry_y) and pd.notna(exit_y):
                    if row["pnl"] > 0:
                        win_x.extend([entry_x, exit_x, None])
                        win_y.extend([entry_y, exit_y, None])
                    else:
                        loss_x.extend([entry_x, exit_x, None])
                        loss_y.extend([entry_y, exit_y, None])

        if win_x:
            fig.add_trace(
                go.Scatter(
                    x=win_x,
                    y=win_y,
                    mode="lines",
                    name="Trade (Win)",
                    line=dict(color="rgba(5, 150, 105, 0.75)", width=1.8, dash="dot"),
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )
        if loss_x:
            fig.add_trace(
                go.Scatter(
                    x=loss_x,
                    y=loss_y,
                    mode="lines",
                    name="Trade (Loss)",
                    line=dict(color="rgba(220, 38, 38, 0.75)", width=1.8, dash="dot"),
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )

    add_trade_visuals(trades)

    fig.update_layout(
        template="plotly_white",
        autosize=True,
        height=720,
        hovermode="x unified",
        margin=dict(l=55, r=25, t=95, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11),
        ),
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
        yaxis_title="Giá (VND)",
        yaxis2_title="Khối lượng",
    )
    # Set category type to remove all non-trading empty space gaps cleanly
    fig.update_xaxes(
        type="category",
        showgrid=True,
        gridcolor="#e8edf3",
        nticks=18,
        tickangle=0,
    )
    fig.update_yaxes(showgrid=True, gridcolor="#e8edf3")
    return fig



def build_dashboard_payload(
    run_id: str,
    df: pd.DataFrame,
    trades_path: Path,
    metrics: dict[str, object],
    min_conf: float,
    timeframe: str = "5m",
) -> dict[str, object]:
    return {
        "metadata": {
            "run_id": run_id,
            "timeframe": timeframe,
            "from": df.index.min().isoformat(),
            "to": df.index.max().isoformat(),
            "sessions": int(pd.Index(df.index.date).nunique()),
            "bars": int(len(df)),
            "min_confidence": min_conf,
            "trade_source": str(trades_path),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "summary": metrics,
    }


def render_html(fig: go.Figure, payload: dict[str, object]) -> str:
    metadata = payload["metadata"]
    metrics = payload["summary"]
    cards = "".join(
        '<div class="kpi-card">'
        f'<div class="kpi-label">{html.escape(str(label))}</div>'
        f'<div class="kpi-value">{html.escape(str(value))}</div>'
        "</div>"
        for label, value in metrics.items()
    )
    plot_html = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"responsive": True, "displaylogo": False, "scrollZoom": True},
    )
    date_range = (
        f"{pd.Timestamp(metadata['from']).strftime('%d/%m/%Y %H:%M')} – "
        f"{pd.Timestamp(metadata['to']).strftime('%d/%m/%Y %H:%M')}"
    )
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VN30F1M Trading Engine Visualization</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, "Segoe UI", Arial, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f4f7fb; color: #172033; }}
    .page {{ width: 100%; padding: 18px 22px 24px; }}
    .header {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 18px; margin-bottom: 14px; }}
    h1 {{ margin: 0; font-size: clamp(20px, 2vw, 28px); letter-spacing: -0.02em; }}
    .meta {{ color: #64748b; font-size: 13px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 12px; }}
    .kpi-card {{ min-height: 72px; padding: 12px 14px; border: 1px solid #dce4ee; border-radius: 10px; background: #fff; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.045); }}
    .kpi-label {{ color: #64748b; font-size: 11px; font-weight: 650; letter-spacing: .035em; text-transform: uppercase; }}
    .kpi-value {{ margin-top: 7px; color: #0f172a; font-size: 19px; font-weight: 700; white-space: nowrap; }}
    .chart-shell {{ overflow: hidden; border: 1px solid #dce4ee; border-radius: 12px; background: #fff; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05); }}
    .chart-shell .plotly-graph-div {{ width: 100% !important; height: max(520px, calc(100vh - 245px)) !important; }}
    @media (max-width: 720px) {{
      .page {{ padding: 12px; }}
      .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .chart-shell .plotly-graph-div {{ height: 620px !important; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="header">
      <h1>VN30F1M Trading Engine</h1>
      <div class="meta">Run: <b>{html.escape(str(metadata['run_id']))}</b> · Timeframe: <b>{html.escape(str(metadata.get('timeframe', '5m')))}</b> · {date_range} · {metadata['sessions']} phiên · {metadata['bars']:,} nến · Confidence ≥ {metadata['min_confidence']:.0%}</div>
    </header>
    <section class="kpi-grid" aria-label="Backtest KPIs">{cards}</section>
    <section class="chart-shell">{plot_html}</section>
  </main>
</body>
</html>
"""


def write_outputs(run_id: str, page_html: str, payload: dict[str, object]) -> tuple[Path, Path]:
    run_dir = get_run_dir(run_id, create=True)
    run_chart_path = run_dir / "chart.html"
    run_dashboard_path = run_dir / "dashboard.json"
    dashboard_json = json.dumps(payload, ensure_ascii=False, indent=2)

    run_chart_path.write_text(page_html, encoding="utf-8")
    run_dashboard_path.write_text(dashboard_json, encoding="utf-8")

    # Compatibility aliases used by the existing report and direct browser workflow.
    LATEST_CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_CHART_PATH.write_text(page_html, encoding="utf-8")
    LATEST_DASHBOARD_PATH.write_text(dashboard_json, encoding="utf-8")
    write_latest_run_id(run_id)
    return run_chart_path, run_dashboard_path


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def confidence(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("confidence must be between 0 and 1")
    return parsed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Visualize backtest results.")
    parser.add_argument("--run-id", type=validate_run_id, help="Backtest run to visualize")
    parser.add_argument("--bars", type=positive_int, help="Number of recent bars")
    parser.add_argument("--days", type=positive_int, help="Number of recent trading sessions")
    parser.add_argument("--from-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--session", type=str, help="Single trading session (YYYY-MM-DD)")
    parser.add_argument("--timeframe", type=str, choices=["1m", "5m"], default="5m", help="Timeframe for chart (1m or 5m)")
    parser.add_argument("--min-conf", type=confidence, default=0.0, help="Minimum confidence, 0 to 1")
    parser.add_argument("--no-open", action="store_true", help="Do not open the generated chart")
    args = parser.parse_args(argv)

    run_id, trades_path = resolve_run_trades(args.run_id)
    print(f"Loading run {run_id}...")
    df, trades = load_data(trades_path)
    df, trades = filter_data(df, trades, args)
    df = resample_dataframe(df, timeframe=args.timeframe)
    metrics = calc_dashboard_metrics(trades)
    fig = create_chart(df, trades, timeframe=args.timeframe)
    payload = build_dashboard_payload(run_id, df, trades_path, metrics, args.min_conf, timeframe=args.timeframe)
    page_html = render_html(fig, payload)
    chart_path, dashboard_path = write_outputs(run_id, page_html, payload)
    print(f"Chart saved to {chart_path}")
    print(f"Dashboard saved to {dashboard_path}")

    if not args.no_open:
        webbrowser.open(chart_path.resolve().as_uri())


if __name__ == "__main__":
    main()

