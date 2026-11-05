"""Independent raw audit of a fast 15m Markdown-transition gate for Short."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics
from .short_distribution_audit import load_features
from .short_lpsy_timing_audit import lpsy_break_confirm, lpsy_break_retest_fail

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_transition_gate_audit_no_commission.json"


def run_short_transition_gate_audit() -> dict:
    features = load_features()
    required = ["HTF_5m_LPSY", "HTF_15m_TrendDownOK", "HTF_15m_TrendTransitionDown"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Regenerate features before this audit; missing {missing}")
    lpsy = features["HTF_5m_LPSY"] == 1
    slow_event = _event_start(lpsy & (features["HTF_15m_TrendDownOK"] == 1))
    transition_event = _event_start(lpsy & (features["HTF_15m_TrendTransitionDown"] == 1))
    setups = {
        "SLOW_TREND_LPSY_BREAK_CONFIRM": lpsy_break_confirm(slow_event, features),
        "TRANSITION_LPSY_BREAK_CONFIRM": lpsy_break_confirm(transition_event, features),
        "TRANSITION_LPSY_RETEST_30M": lpsy_break_retest_fail(transition_event, features, retest_window=30),
    }
    results = []
    for setup, signal in setups.items():
        frame = features.copy()
        frame["Signal"] = -signal.astype(int)
        all_history = _metrics(BacktestEngine(frame).run())
        yearly = []
        for name, start, end in PERIODS:
            period = frame.loc[frame.index >= start].copy()
            if end:
                period = period.loc[period.index < end]
            trades = BacktestEngine(period).run()
            yearly.append({"period": name, "raw_events": int(signal.loc[period.index].sum()), **_metrics(trades)})
        results.append({"setup": setup, "all_history_events": int(signal.sum()), "all_history": all_history, "years": yearly})
    report = {
        "execution": "independent raw Short audit; completed 5m UTAD -> Test -> LPSY is unchanged; no ML, model selection or paper-trade changes; commission=0 research mode with slippage and active ATR exits",
        "fast_gate": "completed 15m Close < EMA20, EMA10 < EMA20, and EMA20.diff(3) < 0",
        "event_counts": {"slow_trend_lpsy": int(slow_event.sum()), "transition_trend_lpsy": int(transition_event.sum())},
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short transition-gate audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_transition_gate_audit()


if __name__ == "__main__":
    main()
