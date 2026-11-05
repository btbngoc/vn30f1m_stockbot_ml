"""Audit the losing OOS quarters of the fixed LPS pullback-reclaim setup."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .lps_parameter_walk_forward import _build_5m, _lps_source, _timing
from .state_machine_visual_audit import _write_chart

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
WALK_FORWARD_PATH = BASE_DIR / "models" / "lps_parameter_walk_forward_no_commission.json"
OUTPUT_PATH = BASE_DIR / "models" / "lps_oos_loss_quarter_audit.json"
TRADES_PATH = BASE_DIR / "models" / "lps_oos_loss_quarter_trades.csv"
FIXED_CONFIG = "test6_lps6_pullback_reclaim"


def _metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "profit_factor": 0.0, "win_rate": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    return {"trades": int(len(trades)), "net_pnl": float(trades["PnL"].sum()), "profit_factor": float(wins / losses) if losses else None, "win_rate": float((trades["PnL"] > 0).mean())}


def run_lps_oos_loss_audit() -> dict:
    walk_forward = json.loads(WALK_FORWARD_PATH.read_text(encoding="utf-8"))["walk_forward"]
    loss_quarters = [
        item["quarter"] for item in walk_forward
        if item.get("test") and item["test"]["net_pnl"] < 0
    ]
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    features = features.sort_values("datetime").set_index("datetime")
    htf, bucket = _build_5m(features)
    source_lps = _lps_source(htf, 6, 6)
    event = pd.Series(bucket, index=features.index).map(source_lps.shift(1).fillna(False)).fillna(False).astype(bool)
    event &= features["HTF_15m_TrendOK"] == 1
    signal = _timing(event, features, "pullback_reclaim")

    quarter_reports = []
    all_trades = []
    for number, quarter_name in enumerate(loss_quarters, start=1):
        quarter = pd.Period(quarter_name, freq="Q")
        frame = features.loc[(features.index >= quarter.start_time) & (features.index < quarter.end_time + pd.Timedelta(days=1))].copy()
        frame["Signal"] = signal.loc[frame.index].astype(int)
        trades = BacktestEngine(frame).run()
        enriched = trades.copy()
        if not enriched.empty:
            entry_features = features.reindex(pd.to_datetime(enriched["Entry Date"]))
            enriched["OOSQuarter"] = quarter_name
            enriched["EntryMarketRegime"] = entry_features["MarketRegime"].to_numpy()
            enriched["EntryRVOL"] = entry_features["RVOL"].to_numpy()
            enriched["EntryADX"] = entry_features["ADX"].to_numpy()
            enriched["EntryTrendScore"] = entry_features["TrendScore"].to_numpy()
            enriched["ChartFile"] = [
                _write_chart(features, trade, "LPS_OOS_LOSS", quarter_name, number * 100 + index)
                for index, (_, trade) in enumerate(enriched.iterrows(), start=1)
            ]
            all_trades.append(enriched)
        quarter_reports.append({"quarter": quarter_name, "raw_events": int(frame["Signal"].sum()), **_metrics(trades)})
    combined = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    if not combined.empty:
        combined.to_csv(TRADES_PATH, index=False)
    losing_entries = combined[combined["PnL"] < 0] if not combined.empty else combined
    report = {
        "fixed_configuration": FIXED_CONFIG,
        "execution": "raw LPS-only OOS audit; no ML; commission=0 research mode with slippage and corrected non-lookahead trailing stop",
        "loss_quarters": quarter_reports,
        "loss_entry_regimes": losing_entries.groupby("EntryMarketRegime").size().to_dict() if not losing_entries.empty else {},
        "loss_entry_averages": {
            "rvol": float(losing_entries["EntryRVOL"].mean()), "adx": float(losing_entries["EntryADX"].mean()), "trend_score": float(losing_entries["EntryTrendScore"].mean()),
        } if not losing_entries.empty else {},
        "trades_csv": str(TRADES_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("LPS OOS loss-quarter audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_lps_oos_loss_audit()


if __name__ == "__main__":
    main()
