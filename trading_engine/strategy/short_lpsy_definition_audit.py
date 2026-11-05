"""Visual definition audit for every LPSY that passes the 15m downtrend gate.

This audit does not backtest, fit parameters, or change a trading signal.  It
answers whether the *source* 5m UTAD/Test/LPSY sequence looks structurally
valid before any Short rule is relaxed.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..logging_config import logger
from .setup_audit import _event_start
from .short_distribution_audit import load_features

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "models" / "short_lpsy_definition_audit"
INDEX_PATH = OUTPUT_DIR / "lpsy_candidates.csv"
SUMMARY_PATH = BASE_DIR / "models" / "short_lpsy_definition_audit.json"


def _aggregate(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    bucket = frame.index.floor(frequency)
    return frame.groupby(bucket).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum"))


def _candles(axis, frame: pd.DataFrame, title: str, markers: dict[str, pd.Timestamp] | None = None, range_high: float | None = None, range_low: float | None = None) -> None:
    x = np.arange(len(frame))
    axis.vlines(x, frame["Low"], frame["High"], color="#64748b", linewidth=0.7)
    up = frame["Close"] >= frame["Open"]
    axis.vlines(x[up], frame.loc[up, "Open"], frame.loc[up, "Close"], color="#0f766e", linewidth=2.0)
    axis.vlines(x[~up], frame.loc[~up, "Open"], frame.loc[~up, "Close"], color="#b91c1c", linewidth=2.0)
    if range_high is not None:
        axis.axhline(range_high, color="#7c3aed", linestyle="--", linewidth=0.9, label="prior range high")
    if range_low is not None:
        axis.axhline(range_low, color="#7c3aed", linestyle="--", linewidth=0.9, label="prior range low")
    styles = {"UTAD": ("o", "#7c3aed"), "Test": ("s", "#ea580c"), "LPSY": ("D", "#0891b2")}
    if markers:
        for name, timestamp in markers.items():
            if frame.index[0] <= timestamp <= frame.index[-1]:
                position = frame.index.get_indexer([timestamp], method="nearest")[0]
                marker, color = styles[name]
                axis.scatter(position, frame.iloc[position]["High"], marker=marker, color=color, s=46, zorder=4, label=name)
    axis.set_title(title)
    axis.grid(alpha=0.18)


def _source_event_times(features: pd.DataFrame, lpsy_time: pd.Timestamp) -> dict[str, pd.Timestamp | None]:
    # Actionable flags are shifted one completed 5m candle.  Shift back to
    # inspect what actually happened on the source candle, not five minutes
    # later when the one-minute rule first sees it.
    start = lpsy_time - pd.Timedelta(minutes=90)
    end = lpsy_time
    window = features.loc[start:end]
    result = {"LPSY": lpsy_time.floor("5min") - pd.Timedelta(minutes=5)}
    for column, name in (("HTF_5m_UTAD", "UTAD"), ("HTF_5m_ShortTest", "Test")):
        events = _event_start(window[column] == 1)
        timestamps = events.loc[events].index
        result[name] = (timestamps[-1].floor("5min") - pd.Timedelta(minutes=5)) if len(timestamps) else None
    return result


def _case_metrics(five: pd.DataFrame, events: dict[str, pd.Timestamp | None]) -> dict:
    utad_time, test_time, lpsy_time = events["UTAD"], events["Test"], events["LPSY"]
    if utad_time is None or test_time is None or lpsy_time is None or not all(time in five.index for time in (utad_time, test_time, lpsy_time)):
        return {"sequence_complete": False}
    prior = five.loc[:utad_time].iloc[:-1].tail(24)
    range_high, range_low = float(prior["High"].max()), float(prior["Low"].min())
    width = max(range_high - range_low, 1e-9)
    utad, test, lpsy = five.loc[utad_time], five.loc[test_time], five.loc[lpsy_time]
    test_volume_ratio = float(test["Volume"] / utad["Volume"]) if utad["Volume"] else None
    lpsy_position = float((lpsy["Close"] - range_low) / width)
    return {
        "sequence_complete": True,
        "range_high": range_high,
        "range_low": range_low,
        "utad_breaks_range_high": bool(utad["High"] > range_high),
        "utad_closes_back_in_range": bool(utad["Close"] < range_high),
        "test_volume_vs_utad": test_volume_ratio,
        "test_is_low_volume": bool(test_volume_ratio is not None and test_volume_ratio <= 0.75),
        "lpsy_range_position": lpsy_position,
        "lpsy_in_supply_zone": bool(lpsy_position >= 0.60),
        "lpsy_in_mid_range": bool(0.35 <= lpsy_position < 0.60),
    }


def run_short_lpsy_definition_audit() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = load_features()
    candidate = _event_start((features["HTF_5m_LPSY"] == 1) & (features["HTF_15m_TrendDownOK"] == 1))
    rows = []
    for number, timestamp in enumerate(candidate.loc[candidate].index, start=1):
        events = _source_event_times(features, timestamp)
        five = _aggregate(features.loc[timestamp - pd.Timedelta(minutes=210): timestamp + pd.Timedelta(minutes=60)], "5min")
        fifteen = _aggregate(features.loc[timestamp - pd.Timedelta(minutes=360): timestamp + pd.Timedelta(minutes=120)], "15min")
        one = features.loc[timestamp - pd.Timedelta(minutes=60): timestamp + pd.Timedelta(minutes=30)]
        metrics = _case_metrics(five, events)
        figure, axes = plt.subplots(3, 1, figsize=(14, 10))
        _candles(axes[0], fifteen, "15m — downtrend timing context")
        _candles(axes[1], five, "5m — distribution / UTAD / Test / LPSY", events, metrics.get("range_high"), metrics.get("range_low"))
        _candles(axes[2], one, "1m — timing context", {"LPSY": events["LPSY"]})
        handles, labels = axes[1].get_legend_handles_labels()
        figure.legend(handles, labels, loc="lower center", ncol=3)
        figure.suptitle(f"LPSY candidate {number} | actionable {timestamp:%Y-%m-%d %H:%M}", y=0.99)
        figure.tight_layout(rect=(0, 0.04, 1, 0.97))
        chart_file = f"LPSY_{number:02d}_{timestamp:%Y%m%d_%H%M}.png"
        figure.savefig(OUTPUT_DIR / chart_file, dpi=140)
        plt.close(figure)
        rows.append({
            "candidate_time": timestamp,
            "utad_time": events["UTAD"], "test_time": events["Test"], "lpsy_source_time": events["LPSY"],
            "chart_file": chart_file, **metrics,
        })
    index = pd.DataFrame(rows)
    index.to_csv(INDEX_PATH, index=False)
    valid = index[index["sequence_complete"]] if not index.empty else index
    report = {
        "purpose": "visual definition audit only; no parameter tuning, backtest, ML, or paper-trade changes",
        "candidates": int(len(index)),
        "sequence_complete": int(valid.shape[0]),
        "utad_breaks_and_rejects": int((valid["utad_breaks_range_high"] & valid["utad_closes_back_in_range"]).sum()) if not valid.empty else 0,
        "tests_low_volume": int(valid["test_is_low_volume"].sum()) if not valid.empty else 0,
        "lpsy_in_supply_zone": int(valid["lpsy_in_supply_zone"].sum()) if not valid.empty else 0,
        "lpsy_mid_range": int(valid["lpsy_in_mid_range"].sum()) if not valid.empty else 0,
        "index_csv": str(INDEX_PATH),
        "chart_directory": str(OUTPUT_DIR),
    }
    SUMMARY_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short LPSY definition audit written to %s", SUMMARY_PATH)
    return report


def main() -> None:
    run_short_lpsy_definition_audit()


if __name__ == "__main__":
    main()
