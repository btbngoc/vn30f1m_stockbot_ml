"""Independent OOS backtest of the pre-specified Short context gate.

Gate specification is fixed before this run:
    BREAKDOWN_WEAK_TEST
    AND not LunchSession
    AND 1 <= remaining distance to current day low <= 3 ATR

No ML, trend, VWAP, EMA, regime, or parameter-selection gate is added here.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics
from .short_distribution_audit import load_features

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_breakdown_weak_test_context_gate_oos_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "short_breakdown_weak_test_context_gate_trades_no_commission.csv"
EXECUTION_COLUMNS = ["Open", "High", "Low", "Close", "ATR"]


def _entry_gate(features: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    event = _event_start(features["HTF_5m_BreakdownWeakTest"] == 1)
    day_low = features["Close"] / (1 + features["Distance_DayLow"])
    room_to_low_atr = (features["Close"] - day_low) / features["ATR"]
    lunch = features["LunchSession"].fillna(0).astype(bool)
    gate = event & ~lunch & room_to_low_atr.between(1.0, 3.0, inclusive="both")
    diagnostics = pd.DataFrame({
        "raw_events": event.astype(int),
        "lunch": lunch.astype(int),
        "room_to_day_low_atr": room_to_low_atr,
        "gate": gate.astype(int),
    }, index=features.index)
    return gate, diagnostics


def _run_period(features: pd.DataFrame, signals: pd.Series) -> pd.DataFrame:
    # Keep the execution frame small; BacktestEngine only needs OHLC, ATR and
    # Signal.  This avoids retaining the full feature table in every OOS run.
    frame = features.loc[:, EXECUTION_COLUMNS].copy()
    frame["Signal"] = -signals.astype(int)
    return BacktestEngine(frame).run()


def run_short_breakdown_weak_test_gate_audit() -> dict:
    features = load_features()
    required = ["HTF_5m_BreakdownWeakTest", "Distance_DayLow", "LunchSession", *EXECUTION_COLUMNS]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Regenerate feature parquet before this audit; missing {missing}")

    signals, diagnostics = _entry_gate(features)
    all_trades = _run_period(features, signals)
    if not all_trades.empty:
        all_trades.to_csv(TRADES_PATH, index=False)

    years = []
    for name, start, end in PERIODS:
        mask = features.index >= start
        if end:
            mask &= features.index < end
        frame = features.loc[mask]
        trades = _run_period(frame, signals.loc[frame.index])
        raw_events = int(diagnostics.loc[frame.index, "raw_events"].sum())
        lunch_rejected = int((diagnostics.loc[frame.index, "raw_events"].astype(bool) & diagnostics.loc[frame.index, "lunch"].astype(bool)).sum())
        room_rejected = int((diagnostics.loc[frame.index, "raw_events"].astype(bool) & ~diagnostics.loc[frame.index, "lunch"].astype(bool) & ~diagnostics.loc[frame.index, "gate"].astype(bool)).sum())
        years.append({
            "period": name,
            "raw_events": raw_events,
            "lunch_rejected": lunch_rejected,
            "room_rejected": room_rejected,
            "selected_events": int(signals.loc[frame.index].sum()),
            **_metrics(trades),
        })

    profitable_pf_folds = sum(item["profit_factor"] is not None and item["profit_factor"] > 1.0 for item in years)
    report = {
        "execution": "pre-specified raw Short gate: completed 5m BREAKDOWN_WEAK_TEST + not LunchSession + 1-3 ATR room to current day low; no ML or other filters; commission=0 research mode with slippage and active ATR exits",
        "all_history": {"selected_events": int(signals.sum()), **_metrics(all_trades)},
        "years": years,
        "decision_rule": "keep only if PF > 1 in at least 2 of the 3 independent annual folds",
        "pf_above_one_folds": profitable_pf_folds,
        "passes_oos_rule": profitable_pf_folds >= 2,
        "trades_csv": str(TRADES_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short BREAKDOWN_WEAK_TEST context-gate OOS audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_breakdown_weak_test_gate_audit()


if __name__ == "__main__":
    main()
