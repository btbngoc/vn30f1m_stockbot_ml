"""Audit whether a broken LPSY low retests late or continues straight down."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..logging_config import logger
from .setup_audit import _event_start
from .short_distribution_audit import load_features
from .short_lpsy_timing_audit import _source_lpsy_low

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "models" / "short_lpsy_break_audit"
INDEX_PATH = OUTPUT_DIR / "broken_lpsy_cases.csv"
SUMMARY_PATH = BASE_DIR / "models" / "short_lpsy_break_audit.json"


def _candles(axis, frame: pd.DataFrame, lpsy_low: float, break_time: pd.Timestamp, retest_time: pd.Timestamp | None, title: str) -> None:
    x = np.arange(len(frame))
    axis.vlines(x, frame["Low"], frame["High"], color="#64748b", linewidth=0.7)
    up = frame["Close"] >= frame["Open"]
    axis.vlines(x[up], frame.loc[up, "Open"], frame.loc[up, "Close"], color="#0f766e", linewidth=2.0)
    axis.vlines(x[~up], frame.loc[~up, "Open"], frame.loc[~up, "Close"], color="#b91c1c", linewidth=2.0)
    axis.axhline(lpsy_low, color="#7c3aed", linestyle="--", linewidth=1, label="LPSY low")
    for timestamp, marker, color, label in ((break_time, "v", "#dc2626", "break"), (retest_time, "D", "#0891b2", "failed retest")):
        if timestamp is not None and frame.index[0] <= timestamp <= frame.index[-1]:
            position = frame.index.get_indexer([timestamp], method="nearest")[0]
            axis.scatter(position, frame.iloc[position]["Close"], marker=marker, color=color, s=48, zorder=4, label=label)
    axis.set_title(title)
    axis.grid(alpha=0.18)


def _first_failed_retest(path: pd.DataFrame, lpsy_low: float) -> pd.Timestamp | None:
    for timestamp, row in path.iterrows():
        location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
        if row["High"] >= lpsy_low and row["Close"] < lpsy_low and row["Close"] < row["Open"] and location <= 0.50:
            return timestamp
    return None


def _first_retest_touch(path: pd.DataFrame, lpsy_low: float) -> pd.Timestamp | None:
    touches = path.index[path["High"] >= lpsy_low]
    return touches[0] if len(touches) else None


def run_short_lpsy_break_audit() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = load_features()
    lpsy_events = _event_start((features["HTF_5m_LPSY"] == 1) & (features["HTF_15m_TrendDownOK"] == 1))
    rows = []
    for number, actionable_time in enumerate(lpsy_events.loc[lpsy_events].index, start=1):
        lpsy_low = _source_lpsy_low(features, actionable_time)
        if lpsy_low is None:
            continue
        after = features.loc[(features.index > actionable_time) & (features.index <= actionable_time + pd.Timedelta(minutes=20))]
        broken = after[after["Close"] < lpsy_low]
        if broken.empty:
            rows.append({"actionable_time": actionable_time, "lpsy_low": lpsy_low, "outcome": "NoBreakWithin20m"})
            continue
        break_time = broken.index[0]
        break_row = broken.iloc[0]
        post = features.loc[(features.index > break_time) & (features.index <= break_time + pd.Timedelta(minutes=60))]
        retest_touch = _first_retest_touch(post, lpsy_low)
        retest = _first_failed_retest(post, lpsy_low)
        minutes_to_touch = int((retest_touch - break_time).total_seconds() // 60) if retest_touch is not None else None
        minutes_to_retest = int((retest - break_time).total_seconds() // 60) if retest is not None else None
        if retest is not None and minutes_to_retest <= 10:
            outcome = "RetestFail_0_10m"
        elif retest is not None and minutes_to_retest <= 30:
            outcome = "RetestFail_11_30m"
        elif retest is not None:
            outcome = "RetestFail_31_60m"
        elif retest_touch is not None:
            outcome = "RetestReclaim_0_60m"
        else:
            outcome = "NoRetest_60m"
        atr = float(break_row["ATR"]) if pd.notna(break_row["ATR"]) and break_row["ATR"] > 0 else None
        lowest_close = float(post["Close"].min()) if not post.empty else float(break_row["Close"])
        extension_atr = ((float(break_row["Close"]) - lowest_close) / atr) if atr else None
        chart_frame = features.loc[break_time - pd.Timedelta(minutes=30): break_time + pd.Timedelta(minutes=70)]
        figure, axis = plt.subplots(figsize=(14, 5))
        _candles(axis, chart_frame, lpsy_low, break_time, retest, f"{number}. {outcome} | LPSY actionable {actionable_time:%Y-%m-%d %H:%M}")
        handles, labels = axis.get_legend_handles_labels()
        figure.legend(handles, labels, loc="lower center", ncol=3)
        figure.tight_layout(rect=(0, 0.06, 1, 1))
        chart_file = f"LPSY_BREAK_{number:02d}_{actionable_time:%Y%m%d_%H%M}.png"
        figure.savefig(OUTPUT_DIR / chart_file, dpi=140)
        plt.close(figure)
        rows.append({
            "actionable_time": actionable_time, "lpsy_low": lpsy_low, "break_time": break_time,
            "retest_touch_time": retest_touch, "minutes_to_touch": minutes_to_touch,
            "failed_retest_time": retest, "minutes_to_retest": minutes_to_retest,
            "outcome": outcome, "extension_after_break_atr": extension_atr, "chart_file": chart_file,
        })
    index = pd.DataFrame(rows)
    index.to_csv(INDEX_PATH, index=False)
    report = {
        "purpose": "behavior audit only; no rule changes, backtest, ML, or paper-trade changes",
        "lpsy_events": int(lpsy_events.sum()),
        "outcomes": index["outcome"].value_counts().to_dict() if not index.empty else {},
        "median_extension_after_break_atr": float(index["extension_after_break_atr"].dropna().median()) if "extension_after_break_atr" in index else None,
        "index_csv": str(INDEX_PATH), "chart_directory": str(OUTPUT_DIR),
    }
    SUMMARY_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short LPSY break audit written to %s", SUMMARY_PATH)
    return report


def main() -> None:
    run_short_lpsy_break_audit()


if __name__ == "__main__":
    main()
