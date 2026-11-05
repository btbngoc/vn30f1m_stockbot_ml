"""Raw Short research for Distribution -> UTAD -> Test -> LPSY/SOW.

This module is intentionally isolated from TrendStrategy, ML and paper trading.
It reads only completed HTF state-machine fields and emits ``-1`` Short signals
for the common execution engine.
"""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "short_distribution_raw_audit_no_commission.json"


def load_features() -> pd.DataFrame:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    return features.sort_values("datetime").set_index("datetime")


def one_minute_reject(event: pd.Series, features: pd.DataFrame) -> pd.Series:
    """Wait for a 1m green pullback, then a bearish reclaim below its low."""
    event_start = _event_start(event)
    pending = event_start.shift(1, fill_value=False).rolling(10, min_periods=1).max().astype(bool)
    pullback = features["Close"].shift(1) >= features["Open"].shift(1)
    reject = (
        (features["Close"] < features["Low"].shift(1))
        & (features["Close"] < features["EMA10"])
        & (features["Close"] <= (features["High"] + features["Low"]) / 2)
    )
    candidate = pending & pullback & reject
    return candidate & ~candidate.shift(1, fill_value=False)


def short_setups(features: pd.DataFrame) -> dict[str, pd.Series]:
    required = ["HTF_15m_TrendDownOK", "HTF_5m_UTAD", "HTF_5m_ShortTest", "HTF_5m_LPSY", "HTF_5m_SOW"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Missing Short state-machine fields; regenerate feature parquet first: {missing}")
    downtrend = features["HTF_15m_TrendDownOK"] == 1
    lpsy = _event_start((features["HTF_5m_LPSY"] == 1) & downtrend)
    sow = _event_start((features["HTF_5m_SOW"] == 1) & downtrend)
    return {
        "LPSY_IMMEDIATE": lpsy,
        "SOW_IMMEDIATE": sow,
        "LPSY_1M_REJECT": one_minute_reject(lpsy, features),
        "SOW_1M_REJECT": one_minute_reject(sow, features),
    }


def run_short_distribution_audit() -> dict:
    features = load_features()
    results = []
    for setup, signals in short_setups(features).items():
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
        "execution": "raw Short state machine only; completed 5m Distribution -> UTAD -> Test -> LPSY/SOW, 15m downtrend and optional 1m pullback/reject; no ML; commission=0 research mode with slippage and active ATR exits",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short distribution raw audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_distribution_audit()


if __name__ == "__main__":
    main()
