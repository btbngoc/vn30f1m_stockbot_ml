"""Raw out-of-sample audit for the state-machine LPS and SOS entry events."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "wyckoff_state_machine_raw_audit_no_commission.json"


def _one_minute_reclaim(event: pd.Series, features: pd.DataFrame) -> pd.Series:
    """Delay an HTF event until a 1m pullback and reclaim occurs.

    This avoids buying the first impulse candle.  The event opens a ten-minute
    timing window; entry needs a red/flat pullback bar followed by a close above
    that bar's high in the upper half of its own range.
    """
    event_start = _event_start(event)
    pending = event_start.shift(1, fill_value=False).rolling(10, min_periods=1).max().astype(bool)
    pullback = features["Close"].shift(1) <= features["Open"].shift(1)
    reclaim = (
        (features["Close"] > features["High"].shift(1))
        & (features["Close"] > features["EMA10"])
        & (features["Close"] >= (features["High"] + features["Low"]) / 2)
    )
    candidate = pending & pullback & reclaim
    return candidate & ~candidate.shift(1, fill_value=False)


def run_state_machine_setup_audit() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    trend = features["HTF_15m_TrendOK"] == 1
    base_events = {
        "LPS": _event_start((features["HTF_5m_LPS"] == 1) & trend),
        "SOS": _event_start((features["HTF_5m_SOS"] == 1) & trend),
    }
    setups = {
        **base_events,
        "LPS_1M_RECLAIM": _one_minute_reclaim(base_events["LPS"], features),
        "SOS_1M_RECLAIM": _one_minute_reclaim(base_events["SOS"], features),
    }
    results = []
    for setup, signals in setups.items():
        yearly = []
        for name, start, end in PERIODS:
            period = features[features["datetime"] >= start].copy()
            if end:
                period = period[period["datetime"] < end].copy()
            period["Signal"] = signals.loc[period.index].astype(int)
            trades = BacktestEngine(period.set_index("datetime")).run()
            yearly.append({"period": name, "raw_events": int(period["Signal"].sum()), **_metrics(trades)})
        results.append({"setup": setup, "years": yearly})
    report = {
        "execution": "raw state-machine events plus an experimental 1m pullback/reclaim timing variant; no ML or score threshold; commission=0 research mode with slippage and active ATR exits",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("State-machine raw setup audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_state_machine_setup_audit()


if __name__ == "__main__":
    main()
