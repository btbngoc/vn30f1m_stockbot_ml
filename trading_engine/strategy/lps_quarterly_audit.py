"""Quarter-by-quarter out-of-sample audit for raw LPS plus 1m reclaim entries."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _metrics, _event_start
from .state_machine_setup_audit import _one_minute_reclaim

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "lps_reclaim_quarterly_audit_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "lps_reclaim_quarterly_trades_no_commission.csv"


def run_lps_quarterly_audit() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    features = features.sort_values("datetime").set_index("datetime")
    trend = features["HTF_15m_TrendOK"] == 1
    lps_event = _event_start((features["HTF_5m_LPS"] == 1) & trend)
    timed_entry = _one_minute_reclaim(lps_event, features)
    features["Signal"] = timed_entry.astype(int)

    start_quarter = features.index.min().to_period("Q")
    end_quarter = features.index.max().to_period("Q")
    rows = []
    all_trades = []
    for quarter in pd.period_range(start_quarter, end_quarter, freq="Q"):
        start = quarter.start_time
        end = quarter.end_time + pd.Timedelta(days=1)
        frame = features.loc[(features.index >= start) & (features.index < end)].copy()
        trades = BacktestEngine(frame).run()
        if not trades.empty:
            trades["Quarter"] = str(quarter)
            all_trades.append(trades)
        rows.append({
            "quarter": str(quarter),
            "partial": bool(quarter == end_quarter and features.index.max() < quarter.end_time),
            "raw_events": int(frame["Signal"].sum()),
            **_metrics(trades),
        })
    results = pd.DataFrame(rows)
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(TRADES_PATH, index=False)
    active = results[results["trades"] > 0]
    aggregate_trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    aggregate = _metrics(aggregate_trades)
    pf_above_one = (active["profit_factor"].gt(1) | (active["profit_factor"].isna() & active["net_pnl"].gt(0)))
    report = {
        "execution": "raw LPS + 1m pullback/reclaim only; no ML, no fitted threshold; commission=0 research mode with slippage and active ATR exits",
        "quarterly_results": rows,
        "summary": {
            "quarters_total": int(len(results)),
            "quarters_with_trades": int(len(active)),
            "quarters_positive_pnl": int((active["net_pnl"] > 0).sum()),
            "quarters_pf_above_one": int(pf_above_one.sum()),
            "quarters_with_at_least_two_trades": int((active["trades"] >= 2).sum()),
            "aggregate": aggregate,
        },
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("LPS quarterly audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_lps_quarterly_audit()


if __name__ == "__main__":
    main()
