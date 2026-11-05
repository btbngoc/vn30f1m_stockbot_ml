"""Independent +1R breakeven-exit test for the fixed transition Short entry."""

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _event_start, _metrics
from .short_distribution_audit import load_features
from .short_lpsy_timing_audit import lpsy_break_confirm

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_transition_breakeven_audit_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "short_transition_breakeven_trades_no_commission.csv"


def run_short_transition_breakeven_audit() -> dict:
    features = load_features()
    event = _event_start((features["HTF_5m_LPSY"] == 1) & (features["HTF_15m_TrendTransitionDown"] == 1))
    features["Signal"] = -lpsy_break_confirm(event, features).astype(int)
    baseline = BacktestEngine(features).run()
    breakeven_config = replace(DEFAULT_BACKTEST_CONFIG, breakeven_trigger_r=1.0)
    breakeven = BacktestEngine(features, config=breakeven_config).run()
    baseline_out = baseline.copy(); baseline_out["ExitRule"] = "baseline"
    breakeven_out = breakeven.copy(); breakeven_out["ExitRule"] = "breakeven_after_1R"
    pd.concat([baseline_out, breakeven_out], ignore_index=True).to_csv(TRADES_PATH, index=False)
    report = {
        "execution": "fixed transition-gated LPSY break-confirm entry; only exit rule changes; no ML or paper-trade changes; commission=0 research mode with slippage",
        "breakeven_rule": "after a completed candle reaches +1 initial R MFE, stop is moved to entry for the next candle; no same-candle look-ahead",
        "baseline": _metrics(baseline),
        "breakeven_after_1r": _metrics(breakeven),
        "trade_csv": str(TRADES_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short transition breakeven audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_transition_breakeven_audit()


if __name__ == "__main__":
    main()
