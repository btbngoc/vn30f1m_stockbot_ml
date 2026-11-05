"""Multi-timeframe visual review of losing raw Short LPSY/SOW trades."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _event_start
from .short_distribution_audit import load_features, short_setups

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "models" / "short_distribution_visual_audit"
SUMMARY_PATH = BASE_DIR / "models" / "short_distribution_visual_audit_summary.json"
INDEX_PATH = OUTPUT_DIR / "sl_trade_index.csv"


def _aggregate(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    bucket = frame.index.floor(frequency)
    return frame.groupby(bucket).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum"))


def _draw(axis, frame: pd.DataFrame, entry: pd.Timestamp, exit_: pd.Timestamp, title: str, events: dict[str, pd.DatetimeIndex] | None = None) -> None:
    x = np.arange(len(frame))
    axis.vlines(x, frame["Low"], frame["High"], color="#64748b", linewidth=0.7)
    up = frame["Close"] >= frame["Open"]
    axis.vlines(x[up], frame.loc[up, "Open"], frame.loc[up, "Close"], color="#0f766e", linewidth=2.1)
    axis.vlines(x[~up], frame.loc[~up, "Open"], frame.loc[~up, "Close"], color="#b91c1c", linewidth=2.1)
    for timestamp, marker, color, label in ((entry, "v", "#2563eb", "Short entry"), (exit_, "^", "#dc2626", "SL exit")):
        position = frame.index.get_indexer([timestamp], method="nearest")[0]
        axis.scatter(position, frame.iloc[position]["Close"], marker=marker, color=color, s=42, zorder=4, label=label)
    if events:
        styles = {"UTAD": ("o", "#7c3aed"), "Test": ("s", "#ea580c"), "LPSY": ("D", "#0891b2"), "SOW": ("P", "#16a34a")}
        for label, timestamps in events.items():
            marker, color = styles[label]
            for timestamp in timestamps:
                if frame.index[0] <= timestamp <= frame.index[-1]:
                    position = frame.index.get_indexer([timestamp], method="nearest")[0]
                    axis.scatter(position, frame.iloc[position]["Low"], marker=marker, color=color, s=32, zorder=4, label=label)
    axis.set_title(title)
    axis.grid(alpha=0.18)


def _category(features: pd.DataFrame, trade: pd.Series) -> tuple[str, int]:
    entry, exit_ = pd.Timestamp(trade["Entry Date"]), pd.Timestamp(trade["Exit Date"])
    path = features.loc[entry:exit_]
    bars = len(path) - 1
    if bars <= 5:
        return "ImmediateFailure", bars
    initial_r = float(trade["Initial Stop Loss"] - trade["Entry"])
    favorable = float(trade["Entry"] - path["Low"].min()) if not path.empty else 0.0
    if initial_r > 0 and favorable < initial_r * 0.50:
        return "NoFollowThrough", bars
    return "PullbackOrStopSizing", bars


def _write_chart(features: pd.DataFrame, trade: pd.Series, setup: str, number: int) -> str:
    entry, exit_ = pd.Timestamp(trade["Entry Date"]), pd.Timestamp(trade["Exit Date"])
    one = features.loc[entry - pd.Timedelta(minutes=60): exit_ + pd.Timedelta(minutes=40)]
    five = _aggregate(features.loc[entry - pd.Timedelta(minutes=180): exit_ + pd.Timedelta(minutes=60)], "5min")
    fifteen = _aggregate(features.loc[entry - pd.Timedelta(minutes=360): exit_ + pd.Timedelta(minutes=120)], "15min")
    events = {}
    for column, label in (("HTF_5m_UTAD", "UTAD"), ("HTF_5m_ShortTest", "Test"), ("HTF_5m_LPSY", "LPSY"), ("HTF_5m_SOW", "SOW")):
        starts = _event_start(features[column] == 1)
        events[label] = starts.loc[starts].index.floor("5min") - pd.Timedelta(minutes=5)
    figure, axes = plt.subplots(3, 1, figsize=(14, 10))
    _draw(axes[0], fifteen, entry, exit_, "15m — higher-timeframe downtrend")
    _draw(axes[1], five, entry, exit_, "5m — distribution / UTAD / Test / LPSY-SOW", events)
    _draw(axes[2], one, entry, exit_, "1m — Short entry and SL path")
    for axis in axes:
        axis.axhline(float(trade["Initial Stop Loss"]), color="#dc2626", linewidth=0.9, linestyle="--")
        axis.axhline(float(trade["Take Profit"]), color="#0f766e", linewidth=0.9, linestyle="--")
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=2)
    figure.suptitle(f"{setup} | {entry:%Y-%m-%d %H:%M} | PnL {trade['PnL']:,.0f}", y=0.99)
    figure.tight_layout(rect=(0, 0.04, 1, 0.97))
    file_name = f"{setup}_{number:02d}_{entry:%Y%m%d_%H%M}.png"
    figure.savefig(OUTPUT_DIR / file_name, dpi=140)
    plt.close(figure)
    return file_name


def run_short_distribution_visual_audit() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = load_features()
    rows = []
    for setup, signals in short_setups(features).items():
        frame = features.copy()
        frame["Signal"] = -signals.astype(int)
        trades = BacktestEngine(frame).run()
        for _, trade in trades.loc[(trades["Reason"] == "SL") & (trades["PnL"] < 0)].iterrows():
            category, bars = _category(features, trade)
            rows.append({"setup": setup, "entry_date": trade["Entry Date"], "exit_date": trade["Exit Date"], "pnl": trade["PnL"], "holding_bars": bars, "category": category, "chart_file": _write_chart(features, trade, setup, len(rows) + 1)})
    index = pd.DataFrame(rows)
    index.to_csv(INDEX_PATH, index=False)
    report = {
        "execution": "raw Short LPSY/SOW only; no ML; commission=0 research mode with slippage and active ATR exits",
        "sl_trades": int(len(index)),
        "by_category": index.groupby("category").size().to_dict() if not index.empty else {},
        "by_setup": index.groupby("setup").size().to_dict() if not index.empty else {},
        "index_csv": str(INDEX_PATH),
        "chart_directory": str(OUTPUT_DIR),
    }
    SUMMARY_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short visual audit written to %s", SUMMARY_PATH)
    return report


def main() -> None:
    run_short_distribution_visual_audit()


if __name__ == "__main__":
    main()
