"""Raw Short audit separating narrow-range, breakdown and weak-test filters.

The setup deliberately has no trend, score or ML gate:

    narrow range -> high-volume bearish breakdown -> weak-volume Test -> Short

This isolates whether the requested market behaviour has gross edge before
adding any filters.  The indicators map completed 5m candles onto the 1m
series, so a signal cannot use the still-forming 5m test candle.
"""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics
from .short_distribution_audit import load_features

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_condition_breakdown_audit_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "short_condition_breakdown_trades_no_commission.csv"


SETUPS = {
    "BREAKDOWN_ONLY": "HTF_5m_BreakdownSOW",
    "BREAKDOWN_WEAK_TEST": "HTF_5m_BreakdownWeakTest",
    "NARROW_RANGE_BREAKDOWN": "HTF_5m_NarrowRangeSOW",
    "NARROW_RANGE_BREAKDOWN_WEAK_TEST": "HTF_5m_NarrowRangeWeakTest",
}


def run_short_narrow_range_audit() -> dict:
    features = load_features()
    required = [
        "HTF_5m_NarrowRange", *SETUPS.values(),
    ]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Regenerate feature parquet before this audit; missing {missing}")

    results = []
    trade_exports = []
    for name, column in SETUPS.items():
        # An event, rather than every 1m row carrying the mapped 5m state,
        # gives exactly one entry for each completed 5m condition.
        entry_event = _event_start(features[column] == 1)
        frame = features.copy()
        frame["Signal"] = -entry_event.astype(int)
        all_trades = BacktestEngine(frame).run()
        if not all_trades.empty:
            exported = all_trades.copy()
            exported.insert(0, "Setup", name)
            trade_exports.append(exported)

        yearly = []
        for period, start, end in PERIODS:
            period_frame = features.loc[features.index >= start].copy()
            if end:
                period_frame = period_frame.loc[period_frame.index < end].copy()
            period_frame["Signal"] = -entry_event.loc[period_frame.index].astype(int)
            period_trades = BacktestEngine(period_frame).run()
            yearly.append({"period": period, "entry_events": int(entry_event.loc[period_frame.index].sum()), **_metrics(period_trades)})
        results.append({"setup": name, "signal_column": column, "all_history": {"entry_events": int(entry_event.sum()), **_metrics(all_trades)}, "years": yearly})

    if trade_exports:
        pd.concat(trade_exports, ignore_index=True).to_csv(TRADES_PATH, index=False)

    report = {
        "execution": (
            "completed 5m condition; raw Short entry on the first "
            "actionable 1m bar; no trend gate, score or ML; commission=0 "
            "research mode with slippage and active ATR exits"
        ),
        "definition": {
            "narrow_range": "24 completed 5m bars, width 2-5 ATR, flat EMA20",
            "breakdown": "close below range by 0.1 ATR, weak close, >=0.8 ATR spread, volume >=1.30x 20-bar average",
            "weak_test": "2-6 completed 5m bars later, retests lower range area, remains below range, weak close, volume <=75% of breakdown volume",
        },
        "results": results,
        "trades_csv": str(TRADES_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Narrow-range Short raw audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_narrow_range_audit()


if __name__ == "__main__":
    main()
