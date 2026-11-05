"""Visual and numeric audit of the current 5m SOS/Test proxy definitions."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..logging_config import logger

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "wyckoff_definition_audit.json"
CHART_PATH = BASE_DIR / "models" / "wyckoff_definition_audit_5m.png"


def _event_start(values: pd.Series) -> pd.Series:
    return values.astype(bool) & ~values.astype(bool).shift(1, fill_value=False)


def _make_5m(features: pd.DataFrame) -> pd.DataFrame:
    indexed = features.set_index("datetime").sort_index()
    bucket = indexed.index.floor("5min")
    htf = indexed.groupby(bucket).agg(
        Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
        Close=("Close", "last"), Volume=("Volume", "sum"),
    )
    previous_close = htf["Close"].shift(1)
    true_range = pd.concat([
        htf["High"] - htf["Low"],
        (htf["High"] - previous_close).abs(),
        (htf["Low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    htf["ATR14"] = true_range.rolling(14).mean()
    htf["VolumeMA20"] = htf["Volume"].rolling(20).mean()
    htf["RangeHigh"] = htf["High"].rolling(24).max().shift(1)
    htf["RangeLow"] = htf["Low"].rolling(24).min().shift(1)
    htf["RangeWidth"] = htf["RangeHigh"] - htf["RangeLow"]
    htf["CloseLocation"] = (htf["Close"] - htf["Low"]) / (htf["High"] - htf["Low"]).replace(0, np.nan)
    htf["VolumeRatio"] = htf["Volume"] / htf["VolumeMA20"]
    htf["RangeSlopeATR"] = htf["Close"].rolling(12).mean().diff(12).abs() / htf["ATR14"]
    return htf


def _event_buckets(features: pd.DataFrame, column: str) -> pd.DatetimeIndex:
    values = features.set_index("datetime")[column] == 1
    # HTF context is deliberately shifted one completed 5m candle before it
    # is mapped to 1m rows.  Put the audit marker back on the source candle,
    # not on the following candle where the signal first becomes actionable.
    return (
        _event_start(values).loc[lambda rows: rows].index.floor("5min")
        - pd.Timedelta(minutes=5)
    ).unique()


def _plot_examples(htf: pd.DataFrame, events: dict[str, pd.DatetimeIndex]) -> None:
    selected: list[tuple[str, pd.Timestamp]] = []
    for name, times in events.items():
        for year in (2024, 2025, 2026):
            yearly = sorted(time for time in times if time.year == year)
            if yearly:
                selected.append((name, yearly[len(yearly) // 2]))
    figure, axes = plt.subplots(2, 3, figsize=(18, 9), sharey=False)
    for axis, (name, timestamp) in zip(axes.flat, selected):
        window = htf.loc[timestamp - pd.Timedelta(minutes=5 * 40): timestamp + pd.Timedelta(minutes=5 * 12)]
        x = np.arange(len(window))
        axis.vlines(x, window["Low"], window["High"], color="#64748b", linewidth=0.7)
        up = window["Close"] >= window["Open"]
        axis.vlines(x[up], window.loc[up, "Open"], window.loc[up, "Close"], color="#0f766e", linewidth=2.2)
        axis.vlines(x[~up], window.loc[~up, "Open"], window.loc[~up, "Close"], color="#b91c1c", linewidth=2.2)
        axis.plot(x, window["RangeHigh"], color="#d97706", linewidth=1, label="24-bar range high")
        axis.plot(x, window["RangeLow"], color="#d97706", linewidth=1, linestyle="--", label="24-bar range low")
        event_x = window.index.get_indexer([timestamp], method="nearest")[0]
        axis.scatter(event_x, window.iloc[event_x]["High"], marker="v", color="#7c3aed", zorder=3, label="proxy event")
        axis.set_title(f"{name} {timestamp:%Y-%m-%d %H:%M}")
        axis.grid(alpha=0.2)
    for axis in axes.flat[len(selected):]:
        axis.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3)
    figure.suptitle("Current 5m SOS/Test proxy events — 40 bars before, 12 bars after", y=0.98)
    figure.tight_layout(rect=(0, 0.05, 1, 0.95))
    figure.savefig(CHART_PATH, dpi=150)
    plt.close(figure)


def run_definition_audit() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    htf = _make_5m(features)
    events = {name: _event_buckets(features, column) for name, column in {"SOS": "HTF_5m_SOS", "TEST": "HTF_5m_Test"}.items()}
    spring_times = _event_buckets(features, "HTF_5m_Spring")
    records = {}
    for name, times in events.items():
        rows = htf.reindex(times).dropna(subset=["ATR14", "RangeHigh", "RangeLow"])
        rows = rows.copy()
        if name == "TEST":
            prior_spring = []
            for timestamp in rows.index:
                prior = spring_times[spring_times < timestamp]
                prior_spring.append((timestamp - prior[-1]).total_seconds() / 300 if len(prior) else np.nan)
            rows["BarsSinceSpring"] = prior_spring
        records[name] = {
            "events": int(len(rows)),
            "by_year": {str(year): int((rows.index.year == year).sum()) for year in (2024, 2025, 2026)},
            "median_volume_ratio": float(rows["VolumeRatio"].median()),
            "pct_close_upper_65": float((rows["CloseLocation"] >= 0.65).mean()),
            "pct_range_slope_under_1_5_atr": float((rows["RangeSlopeATR"] <= 1.5).mean()),
        }
        if name == "TEST":
            records[name].update({
                "median_bars_since_spring": float(rows["BarsSinceSpring"].median()),
                "pct_within_6_bars_of_spring": float((rows["BarsSinceSpring"] <= 6).mean()),
                "pct_more_than_24_bars_after_spring": float((rows["BarsSinceSpring"] > 24).mean()),
            })
    _plot_examples(htf, events)
    report = {
        "current_definitions": {
            "SOS": "close > previous 24-bar high AND volume >= 1.20 × 20-bar volume average",
            "TEST": "after any prior Spring: low stays within 20% of current range width above Spring low, volume <= 70% of Spring volume, close in upper half",
        },
        "diagnostics": records,
        "conclusion": [
            "Current SOS does not require a flat accumulation range, a close near the high, or a minimum spread/effort confirmation.",
            "Current Test state never expires after Spring, so a later low-volume bar can be called a Test long after the original Spring.",
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wyckoff definition audit written to %s and chart saved to %s", OUTPUT_PATH, CHART_PATH)
    return report


def main() -> None:
    run_definition_audit()


if __name__ == "__main__":
    main()
