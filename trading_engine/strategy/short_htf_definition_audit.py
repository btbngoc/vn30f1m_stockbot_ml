"""Measure whether the current 5m Distribution/UTAD definition has follow-through."""

import json
from pathlib import Path

import pandas as pd

from ..logging_config import logger
from .setup_audit import _event_start
from .short_distribution_audit import load_features

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_htf_definition_audit.json"
CASES_PATH = BASE_DIR / "models" / "short_htf_definition_cases.csv"


def _five_minute(features: pd.DataFrame) -> pd.DataFrame:
    bucket = features.index.floor("5min")
    htf = features.groupby(bucket).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum"))
    previous_close = htf["Close"].shift(1)
    tr = pd.concat([htf["High"] - htf["Low"], (htf["High"] - previous_close).abs(), (htf["Low"] - previous_close).abs()], axis=1).max(axis=1)
    htf["ATR14"] = tr.rolling(14).mean()
    htf["RangeHigh"] = htf["High"].rolling(24).max().shift(1)
    htf["RangeLow"] = htf["Low"].rolling(24).min().shift(1)
    htf["VolumeMA20"] = htf["Volume"].rolling(20).mean()
    return htf


def _first_index(index: pd.DatetimeIndex, predicate: pd.Series) -> pd.Timestamp | None:
    hits = index[predicate.to_numpy()]
    return hits[0] if len(hits) else None


def run_short_htf_definition_audit() -> dict:
    features = load_features()
    htf = _five_minute(features)
    actionable_utad = _event_start(features["HTF_5m_UTAD"] == 1)
    rows = []
    for actionable_time in actionable_utad.loc[actionable_utad].index:
        source_time = actionable_time.floor("5min") - pd.Timedelta(minutes=5)
        if source_time not in htf.index:
            continue
        position = htf.index.get_loc(source_time)
        if not isinstance(position, int) or position < 24:
            continue
        row = htf.iloc[position]
        prior = htf.iloc[position - 24:position]
        forward = htf.iloc[position + 1:position + 13]
        if pd.isna(row["ATR14"]) or forward.empty:
            continue
        width = max(float(row["RangeHigh"] - row["RangeLow"]), 1e-9)
        atr = float(row["ATR14"])
        target_time = _first_index(forward.index, forward["Low"] <= row["Close"] - atr)
        reclaim_time = _first_index(forward.index, forward["High"] >= row["High"])
        if target_time is not None and (reclaim_time is None or target_time < reclaim_time):
            outcome = "FollowThroughDown"
        elif reclaim_time is not None and (target_time is None or reclaim_time < target_time):
            outcome = "ReclaimedUTADHigh"
        else:
            outcome = "NoResolution60m"
        lpsy_window = features.loc[(features.index >= actionable_time) & (features.index <= actionable_time + pd.Timedelta(minutes=90))]
        rows.append({
            "actionable_time": actionable_time, "source_time": source_time,
            "trend_down_at_action": bool(features.loc[actionable_time, "HTF_15m_TrendDownOK"] == 1),
            "lpsy_within_90m": bool((lpsy_window["HTF_5m_LPSY"] == 1).any()),
            "range_width_atr": width / atr,
            "range_high_touches": int((prior["High"] >= row["RangeHigh"] - width * 0.15).sum()),
            "range_low_touches": int((prior["Low"] <= row["RangeLow"] + width * 0.15).sum()),
            "pre_range_return": float((prior["Close"].iloc[-1] / prior["Close"].iloc[0]) - 1),
            "utad_penetration_atr": float((row["High"] - row["RangeHigh"]) / atr),
            "utad_close_location": float((row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)),
            "utad_volume_rvol": float(row["Volume"] / row["VolumeMA20"]) if row["VolumeMA20"] else None,
            "outcome_60m": outcome,
        })
    cases = pd.DataFrame(rows)
    cases.to_csv(CASES_PATH, index=False)
    summary = cases.groupby("outcome_60m").size().to_dict() if not cases.empty else {}
    gate_summary = (cases.groupby("trend_down_at_action")["outcome_60m"].value_counts().unstack(fill_value=0).to_dict(orient="index") if not cases.empty else {})
    lpsy_summary = (cases.groupby("lpsy_within_90m")["outcome_60m"].value_counts().unstack(fill_value=0).to_dict(orient="index") if not cases.empty else {})
    report = {
        "purpose": "definition audit only; no changes to entry, model, backtest or paper trade",
        "definition": "FollowThroughDown means price reached one ATR below UTAD close before reclaiming UTAD high in the next 60 minutes; ReclaimedUTADHigh is the reverse",
        "cases": int(len(cases)), "outcomes_60m": summary,
        "by_15m_downtrend_at_action": gate_summary,
        "by_lpsy_within_90m": lpsy_summary,
        "cases_csv": str(CASES_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short HTF definition audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_htf_definition_audit()


if __name__ == "__main__":
    main()
