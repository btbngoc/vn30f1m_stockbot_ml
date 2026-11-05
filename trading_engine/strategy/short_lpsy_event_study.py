"""Forward-path event study for every completed 5m LPSY, without an entry rule."""

import json
from pathlib import Path

import pandas as pd

from ..logging_config import logger
from .setup_audit import _event_start
from .short_distribution_audit import load_features
from .short_lpsy_timing_audit import _source_lpsy_low

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_lpsy_forward_event_study.json"
CASES_PATH = BASE_DIR / "models" / "short_lpsy_forward_event_study.csv"
HORIZON_MINUTES = 60


def _first_time(frame: pd.DataFrame, condition: pd.Series) -> pd.Timestamp | None:
    hits = frame.index[condition.to_numpy()]
    return hits[0] if len(hits) else None


def _minutes(start: pd.Timestamp, end: pd.Timestamp | None) -> int | None:
    return int((end - start).total_seconds() // 60) if end is not None else None


def run_short_lpsy_event_study() -> dict:
    features = load_features()
    lpsy_events = _event_start(features["HTF_5m_LPSY"] == 1)
    rows = []
    for actionable_time in lpsy_events.loc[lpsy_events].index:
        lpsy_low = _source_lpsy_low(features, actionable_time)
        entry = features.loc[actionable_time]
        atr = float(entry["ATR"])
        if lpsy_low is None or pd.isna(atr) or atr <= 0:
            continue
        forward = features.loc[(features.index > actionable_time) & (features.index <= actionable_time + pd.Timedelta(minutes=HORIZON_MINUTES))]
        if forward.empty:
            continue
        down_target = float(entry["Close"] - atr)
        up_target = float(entry["Close"] + atr)
        down_time = _first_time(forward, forward["Low"] <= down_target)
        up_time = _first_time(forward, forward["High"] >= up_target)
        break_time = _first_time(forward, forward["Close"] < lpsy_low)
        if down_time is not None and (up_time is None or down_time < up_time):
            outcome = "Down1RBeforeUp1R"
        elif up_time is not None and (down_time is None or up_time < down_time):
            outcome = "Up1RBeforeDown1R"
        else:
            outcome = "No1RResolution60m"
        rows.append({
            "actionable_time": actionable_time, "source_lpsy_low": lpsy_low,
            "entry_close": float(entry["Close"]), "atr": atr,
            "slow_trend_down": bool(entry["HTF_15m_TrendDownOK"] == 1),
            "transition_down": bool(entry["HTF_15m_TrendTransitionDown"] == 1),
            "outcome": outcome, "down_1r_time": down_time, "up_1r_time": up_time,
            "break_lpsy_low_time": break_time,
            "minutes_to_down_1r": _minutes(actionable_time, down_time),
            "minutes_to_up_1r": _minutes(actionable_time, up_time),
            "minutes_to_break_lpsy_low": _minutes(actionable_time, break_time),
            "mfe_r_60m": float((entry["Close"] - forward["Low"].min()) / atr),
            "mae_r_60m": float((forward["High"].max() - entry["Close"]) / atr),
        })
    cases = pd.DataFrame(rows)
    cases.to_csv(CASES_PATH, index=False)
    outcome_counts = cases["outcome"].value_counts().to_dict() if not cases.empty else {}
    by_slow = cases.groupby("slow_trend_down")["outcome"].value_counts().unstack(fill_value=0).to_dict(orient="index") if not cases.empty else {}
    by_transition = cases.groupby("transition_down")["outcome"].value_counts().unstack(fill_value=0).to_dict(orient="index") if not cases.empty else {}
    report = {
        "purpose": "event study only; no entry, backtest, ML, exit or paper-trade change",
        "definition": "from the first actionable 1m bar after completed 5m LPSY, measure whether low reaches -1 ATR or high reaches +1 ATR first during the next 60 minutes",
        "events": int(len(cases)), "outcomes": outcome_counts,
        "median_minutes_to_down_1r": float(cases["minutes_to_down_1r"].dropna().median()) if not cases.empty else None,
        "median_minutes_to_break_lpsy_low": float(cases["minutes_to_break_lpsy_low"].dropna().median()) if not cases.empty else None,
        "by_slow_trend_down": by_slow, "by_transition_down": by_transition,
        "cases_csv": str(CASES_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short LPSY forward event study written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_lpsy_event_study()


if __name__ == "__main__":
    main()
