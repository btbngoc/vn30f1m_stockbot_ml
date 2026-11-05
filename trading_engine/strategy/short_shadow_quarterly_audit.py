"""Quarterly OOS record for all pre-registered Short shadow candidates."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _metrics
from .short_distribution_audit import load_features
from .short_shadow_setups import build_short_shadow_setups

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_shadow_quarterly_audit_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "short_shadow_quarterly_trades_no_commission.csv"


def run_short_shadow_quarterly_audit() -> dict:
    features = load_features()
    setups = build_short_shadow_setups(features)
    quarters = pd.period_range(features.index.min().to_period("Q"), features.index.max().to_period("Q"), freq="Q")
    results, all_trades = [], []
    for setup, signals in setups.items():
        rows = []
        for quarter in quarters:
            frame = features.loc[(features.index >= quarter.start_time) & (features.index < quarter.end_time + pd.Timedelta(days=1))].copy()
            frame["Signal"] = -signals.loc[frame.index].astype(int)
            trades = BacktestEngine(frame).run()
            if not trades.empty:
                tagged = trades.copy()
                tagged["Setup"], tagged["Quarter"] = setup, str(quarter)
                all_trades.append(tagged)
            rows.append({"quarter": str(quarter), "raw_events": int(signals.loc[frame.index].sum()), **_metrics(trades)})
        results.append({"setup": setup, "quarterly_results": rows, "aggregate": _metrics(pd.concat([t for t in all_trades if t["Setup"].iloc[0] == setup], ignore_index=True) if any(t["Setup"].iloc[0] == setup for t in all_trades) else pd.DataFrame())})
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(TRADES_PATH, index=False)
    report = {
        "execution": "three pre-registered raw Short candidates; each calendar quarter is evaluated independently; no ML, optimization or setup selection; commission=0 research mode with slippage and active ATR exits",
        "promotion_rule": "do not promote to paper execution unless enough OOS trades exist and PF > 1, net PnL > 0 and drawdown are acceptable across multiple quarters",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short shadow quarterly audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_shadow_quarterly_audit()


if __name__ == "__main__":
    main()
