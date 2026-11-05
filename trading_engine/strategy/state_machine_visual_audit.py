"""Create multi-timeframe charts for raw state-machine trades stopped out at SL."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_DIR = BASE_DIR / "models" / "state_machine_visual_audit"
SUMMARY_PATH = BASE_DIR / "models" / "state_machine_visual_audit_summary.json"
INDEX_PATH = OUTPUT_DIR / "sl_trade_index.csv"


def _aggregate(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    bucket = frame.index.floor(frequency)
    return frame.groupby(bucket).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum"))


def _draw_candles(axis, frame: pd.DataFrame, entry: pd.Timestamp, exit_: pd.Timestamp, title: str, events: dict[str, pd.DatetimeIndex] | None = None) -> None:
    x = np.arange(len(frame))
    axis.vlines(x, frame["Low"], frame["High"], color="#64748b", linewidth=0.7)
    up = frame["Close"] >= frame["Open"]
    axis.vlines(x[up], frame.loc[up, "Open"], frame.loc[up, "Close"], color="#0f766e", linewidth=2.1)
    axis.vlines(x[~up], frame.loc[~up, "Open"], frame.loc[~up, "Close"], color="#b91c1c", linewidth=2.1)
    for timestamp, marker, color, label in ((entry, "^", "#2563eb", "entry"), (exit_, "v", "#dc2626", "SL exit")):
        position = frame.index.get_indexer([timestamp], method="nearest")[0]
        price = frame.iloc[position]["Close"]
        axis.scatter(position, price, marker=marker, color=color, s=42, zorder=4, label=label)
    if events:
        styles = {
            "Spring": ("o", "#7c3aed"), "Test": ("s", "#ea580c"),
            "LPS": ("D", "#0891b2"), "SOS": ("P", "#16a34a"),
        }
        for label, timestamps in events.items():
            marker, color = styles[label]
            for timestamp in timestamps:
                if frame.index[0] <= timestamp <= frame.index[-1]:
                    position = frame.index.get_indexer([timestamp], method="nearest")[0]
                    axis.scatter(position, frame.iloc[position]["High"], marker=marker, color=color, s=32, zorder=4, label=label)
    axis.set_title(title)
    axis.grid(alpha=0.18)


def _prior_spring_low(features: pd.DataFrame, entry: pd.Timestamp) -> float | None:
    start = entry - pd.Timedelta(minutes=90)
    springs = features.loc[(features.index >= start) & (features.index <= entry) & (features["HTF_5m_Spring"] == 1)]
    if springs.empty:
        return None
    # Feature flags appear on the following completed 5m bucket; its 1m low is
    # only an approximation, but sufficient for grouping visual review cases.
    return float(springs["Low"].min())


def _classify_trade(features: pd.DataFrame, trade: pd.Series) -> tuple[str, int]:
    entry = pd.Timestamp(trade["Entry Date"])
    exit_ = pd.Timestamp(trade["Exit Date"])
    path = features.loc[(features.index >= entry) & (features.index <= exit_)]
    spring_low = _prior_spring_low(features, entry)
    bars = len(path) - 1
    if spring_low is not None and not path.empty and float(path["Low"].min()) < spring_low:
        return "SpringBreak", bars
    if bars <= 5:
        return "ImmediateFailure", bars
    initial_r = float(trade["Entry"] - trade["Initial Stop Loss"])
    favorable = float(path["High"].max() - trade["Entry"]) if not path.empty else 0.0
    if initial_r > 0 and favorable < initial_r * 0.50:
        return "NoFollowThrough", bars
    return "PullbackOrStopSizing", bars


def _write_chart(features: pd.DataFrame, trade: pd.Series, setup: str, period: str, number: int) -> str:
    entry = pd.Timestamp(trade["Entry Date"])
    exit_ = pd.Timestamp(trade["Exit Date"])
    one_minute = features.loc[entry - pd.Timedelta(minutes=60): exit_ + pd.Timedelta(minutes=40)]
    five_minute = _aggregate(features.loc[entry - pd.Timedelta(minutes=5 * 36): exit_ + pd.Timedelta(minutes=5 * 12)], "5min")
    fifteen_minute = _aggregate(features.loc[entry - pd.Timedelta(minutes=15 * 24): exit_ + pd.Timedelta(minutes=15 * 8)], "15min")
    event_markers = {}
    for column, label in (("HTF_5m_Spring", "Spring"), ("HTF_5m_Test", "Test"), ("HTF_5m_LPS", "LPS"), ("HTF_5m_SOS", "SOS")):
        starts = _event_start(features[column] == 1)
        # Map the deliberately delayed, actionable 1m flag back to the source
        # completed 5m candle so the chart shows the actual state transition.
        event_markers[label] = starts.loc[starts].index.floor("5min") - pd.Timedelta(minutes=5)
    figure, axes = plt.subplots(3, 1, figsize=(14, 10))
    _draw_candles(axes[0], fifteen_minute, entry, exit_, "15m — higher-timeframe trend context")
    _draw_candles(axes[1], five_minute, entry, exit_, "5m — accumulation / Spring / Test / LPS-SOS context", event_markers)
    _draw_candles(axes[2], one_minute, entry, exit_, "1m — actual entry and SL path")
    for axis in axes:
        axis.axhline(float(trade["Initial Stop Loss"]), color="#dc2626", linewidth=0.9, linestyle="--")
        axis.axhline(float(trade["Take Profit"]), color="#0f766e", linewidth=0.9, linestyle="--")
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=2)
    figure.suptitle(f"{setup} {period} | {entry:%Y-%m-%d %H:%M} | PnL {trade['PnL']:,.0f}", y=0.99)
    figure.tight_layout(rect=(0, 0.04, 1, 0.97))
    file_name = f"{setup}_{period}_{number:02d}_{entry:%Y%m%d_%H%M}.png"
    figure.savefig(OUTPUT_DIR / file_name, dpi=140)
    plt.close(figure)
    return file_name


def run_visual_audit() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    features = features.set_index("datetime").sort_index()
    trend = features["HTF_15m_TrendOK"] == 1
    setups = {
        "LPS": _event_start((features["HTF_5m_LPS"] == 1) & trend),
        "SOS": _event_start((features["HTF_5m_SOS"] == 1) & trend),
    }
    index_rows = []
    for setup, signals in setups.items():
        for period, start, end in PERIODS:
            frame = features.loc[features.index >= start].copy()
            if end:
                frame = frame.loc[frame.index < end].copy()
            frame["Signal"] = signals.loc[frame.index].astype(int)
            trades = BacktestEngine(frame).run()
            # A trailing stop can close a profitable trade.  This review is
            # specifically for failed entries, so keep only losing SL exits.
            for _, trade in trades.loc[(trades["Reason"] == "SL") & (trades["PnL"] < 0)].iterrows():
                category, bars = _classify_trade(features, trade)
                index_rows.append({
                    "setup": setup, "period": period, "entry_date": trade["Entry Date"], "exit_date": trade["Exit Date"],
                    "pnl": trade["PnL"], "holding_bars": bars, "category": category,
                    "chart_file": _write_chart(features, trade, setup, period, len(index_rows) + 1),
                })
    index = pd.DataFrame(index_rows)
    index.to_csv(INDEX_PATH, index=False)
    report = {
        "execution": "raw LPS/SOS only; no ML; commission=0 research mode with slippage and active ATR exits",
        "sl_trades": int(len(index)),
        "by_category": index.groupby("category").size().to_dict() if not index.empty else {},
        "by_setup": index.groupby("setup").size().to_dict() if not index.empty else {},
        "index_csv": str(INDEX_PATH),
        "chart_directory": str(OUTPUT_DIR),
    }
    SUMMARY_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("State-machine visual audit written to %s", SUMMARY_PATH)
    return report


def main() -> None:
    run_visual_audit()


if __name__ == "__main__":
    main()
