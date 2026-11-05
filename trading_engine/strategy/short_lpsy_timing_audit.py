"""Compare raw 1m timing variants after a completed HTF LPSY event."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics
from .short_distribution_audit import load_features, one_minute_reject

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_lpsy_timing_audit_no_commission.json"


def _source_lpsy_low(features: pd.DataFrame, actionable_time: pd.Timestamp) -> float | None:
    """Return low of the completed 5m LPSY candle visible at ``actionable_time``."""
    source_start = actionable_time.floor("5min") - pd.Timedelta(minutes=5)
    source = features.loc[(features.index >= source_start) & (features.index < source_start + pd.Timedelta(minutes=5))]
    return float(source["Low"].min()) if not source.empty else None


def lpsy_break_retest_fail(event: pd.Series, features: pd.DataFrame, break_window: int = 20, retest_window: int = 10) -> pd.Series:
    """Enter Short only after breaking the LPSY low then failing a retest.

    The HTF LPSY flag is delayed until the 5m candle closes.  A state machine
    starts only then, so the test never relies on an unfinished 5m bar.
    """
    starts = _event_start(event)
    signal = pd.Series(False, index=features.index)
    state = "IDLE"
    lpsy_low = None
    age = retest_age = 0
    for timestamp, row in features.iterrows():
        if bool(starts.loc[timestamp]):
            lpsy_low = _source_lpsy_low(features, timestamp)
            state, age, retest_age = ("WAIT_BREAK", 0, 0) if lpsy_low is not None else ("IDLE", 0, 0)
            continue
        if state == "WAIT_BREAK":
            age += 1
            if row["Close"] < lpsy_low:
                state, retest_age = "WAIT_RETEST", 0
            elif age > break_window:
                state = "IDLE"
        elif state == "WAIT_RETEST":
            retest_age += 1
            close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
            failed_retest = (
                row["High"] >= lpsy_low
                and row["Close"] < lpsy_low
                and row["Close"] < row["Open"]
                and close_location <= 0.50
            )
            if failed_retest:
                signal.loc[timestamp] = True
                state = "IDLE"
            elif retest_age > retest_window:
                state = "IDLE"
    return signal


def lpsy_break_confirm(event: pd.Series, features: pd.DataFrame, break_window: int = 20) -> pd.Series:
    """Short after a break of the LPSY low plus one bearish 1m confirmation.

    The confirmation must still close under the LPSY low and at/below the
    breakout close.  A close back above that low invalidates the pending setup
    instead of allowing a delayed re-entry.
    """
    starts = _event_start(event)
    signal = pd.Series(False, index=features.index)
    state = "IDLE"
    lpsy_low = break_close = None
    age = 0
    for timestamp, row in features.iterrows():
        if bool(starts.loc[timestamp]):
            lpsy_low = _source_lpsy_low(features, timestamp)
            state, age = ("WAIT_BREAK", 0) if lpsy_low is not None else ("IDLE", 0)
            continue
        if state == "WAIT_BREAK":
            age += 1
            if row["Close"] < lpsy_low:
                state, break_close = "WAIT_CONFIRM", float(row["Close"])
            elif age > break_window:
                state = "IDLE"
        elif state == "WAIT_CONFIRM":
            if row["Close"] > lpsy_low:
                state = "IDLE"
            elif row["Close"] < lpsy_low and row["Close"] < row["Open"] and row["Close"] <= break_close:
                signal.loc[timestamp] = True
                state = "IDLE"
            else:
                # One immediate 1m confirmation is required.  A pause or an
                # indecisive bar is not a continuation entry.
                state = "IDLE"
    return signal


def run_short_lpsy_timing_audit() -> dict:
    features = load_features()
    downtrend = features["HTF_15m_TrendDownOK"] == 1
    lpsy_event = _event_start((features["HTF_5m_LPSY"] == 1) & downtrend)
    setups = {
        "LPSY_IMMEDIATE": lpsy_event,
        "LPSY_1M_REJECT": one_minute_reject(lpsy_event, features),
        "LPSY_BREAK_RETEST_FAIL": lpsy_break_retest_fail(lpsy_event, features),
        "LPSY_BREAK_CONFIRM": lpsy_break_confirm(lpsy_event, features),
    }
    results = []
    for setup, signals in setups.items():
        yearly = []
        for name, start, end in PERIODS:
            frame = features.loc[features.index >= start].copy()
            if end:
                frame = frame.loc[frame.index < end].copy()
            frame["Signal"] = -signals.loc[frame.index].astype(int)
            trades = BacktestEngine(frame).run()
            yearly.append({"period": name, "raw_events": int(signals.loc[frame.index].sum()), **_metrics(trades)})
        results.append({"setup": setup, "years": yearly})
    report = {
        "execution": "raw LPSY timing comparison only; no ML; completed 5m LPSY and 15m downtrend are unchanged; commission=0 research mode with slippage and active ATR exits",
        "timing_definitions": {
            "BREAK_RETEST_FAIL": "after LPSY is actionable, close below its source 5m low within 20m, then within 10m a bearish 1m bar must retest that low and close back below it",
            "BREAK_CONFIRM": "after LPSY is actionable, close below its source 5m low within 20m, then the immediate next 1m candle must be bearish, remain below that low and close at/below the break close; a close reclaiming the LPSY low cancels the setup",
        },
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short LPSY timing audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_lpsy_timing_audit()


if __name__ == "__main__":
    main()
