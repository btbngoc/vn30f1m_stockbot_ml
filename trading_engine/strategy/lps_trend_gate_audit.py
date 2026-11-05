"""Evaluate a short-term no-trade gate on the fixed LPS reclaim setup."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .lps_parameter_walk_forward import _build_5m, _lps_source, _timing
from .setup_audit import _metrics

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "lps_trend_gate_quarterly_audit_no_commission.json"


def run_lps_trend_gate_audit() -> dict:
    frame = pd.read_parquet(FEATURES_PATH)
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="raise")
    frame = frame.sort_values("datetime").set_index("datetime")
    htf, bucket = _build_5m(frame)
    source_lps = _lps_source(htf, 6, 6)
    event = pd.Series(bucket, index=frame.index).map(source_lps.shift(1).fillna(False)).fillna(False).astype(bool)
    event &= frame["HTF_15m_TrendOK"] == 1
    baseline = _timing(event, frame, "pullback_reclaim")
    gate_pass = (
        (frame["MarketRegime"] != "RANGE")
        & (frame["ADX"] >= 25)
        & (frame["TrendScore"] > 0)
    )
    gated = baseline & gate_pass
    quarters = pd.period_range(frame.index.min().to_period("Q"), frame.index.max().to_period("Q"), freq="Q")
    rows = []
    all_baseline = []
    all_gated = []
    for quarter in quarters:
        period = frame.loc[(frame.index >= quarter.start_time) & (frame.index < quarter.end_time + pd.Timedelta(days=1))].copy()
        for name, signal, store in (("baseline", baseline, all_baseline), ("trend_gate", gated, all_gated)):
            test = period.copy()
            test["Signal"] = signal.loc[test.index].astype(int)
            trades = BacktestEngine(test).run()
            if not trades.empty:
                store.append(trades)
            rows.append({"quarter": str(quarter), "variant": name, "raw_events": int(test["Signal"].sum()), **_metrics(trades)})
    table = pd.DataFrame(rows)
    summaries = {}
    for name, trades in (("baseline", all_baseline), ("trend_gate", all_gated)):
        combined = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
        active = table[(table["variant"] == name) & (table["trades"] > 0)]
        summaries[name] = {
            **_metrics(combined),
            "quarters_with_trades": int(len(active)),
            "positive_quarters": int((active["net_pnl"] > 0).sum()),
            "events": int(table.loc[table["variant"] == name, "raw_events"].sum()),
        }
    report = {
        "configuration": "test6 + lps6 + pullback-reclaim",
        "gate": "MarketRegime != RANGE AND ADX >= 25 AND TrendScore > 0",
        "execution": "raw strategy only; no ML; commission=0 research mode with slippage and corrected non-lookahead trailing stop",
        "summaries": summaries,
        "quarterly_results": rows,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("LPS trend-gate audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_lps_trend_gate_audit()


if __name__ == "__main__":
    main()
