"""Diagnose raw TrendStrategy exits and R-multiples before parameter changes."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..backtest.engine import BacktestEngine
from ..logging_config import logger

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "trend_strategy_exit_audit.json"
TRADES_PATH = BASE_DIR / "models" / "trend_strategy_exit_audit_trades.csv"
PERIODS = [
    ("all_history", None, None),
    ("2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
    ("2025", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01")),
    ("2026", pd.Timestamp("2026-01-01"), None),
]


def _group_metrics(trades: pd.DataFrame, group: str) -> dict:
    if trades.empty:
        return {}
    result = {}
    for value, rows in trades.groupby(group, dropna=False):
        wins = rows.loc[rows["PnL"] > 0, "PnL"].sum()
        losses = -rows.loc[rows["PnL"] <= 0, "PnL"].sum()
        result[str(value)] = {
            "trades": int(len(rows)),
            "net_pnl": float(rows["PnL"].sum()),
            "avg_pnl": float(rows["PnL"].mean()),
            "win_rate": float((rows["PnL"] > 0).mean()),
            "profit_factor": float(wins / losses) if losses > 0 else None,
            "avg_r_multiple": float(rows["RMultiple"].mean()),
            "total_r_multiple": float(rows["RMultiple"].sum()),
        }
    return result


def _run(features: pd.DataFrame, start, end) -> pd.DataFrame:
    period = features.copy()
    if start is not None:
        period = period[period["datetime"] >= start]
    if end is not None:
        period = period[period["datetime"] < end]
    period["Signal"] = period["StrategySignal"]
    setups = period.set_index("datetime")["EntrySetup"]
    trades = BacktestEngine(period.set_index("datetime")).run()
    if trades.empty:
        return trades
    trades = trades.copy()
    trades["EntrySetup"] = pd.to_datetime(trades["Entry Date"]).map(setups).fillna("UNKNOWN")
    initial_risk = (
        (trades["Entry"] - trades["Initial Stop Loss"]).abs()
        * trades["Contracts"]
        * DEFAULT_BACKTEST_CONFIG.point_multiplier
    )
    trades["InitialRisk"] = initial_risk
    trades["RMultiple"] = trades["PnL"] / initial_risk.where(initial_risk > 0)
    return trades


def run_exit_audit() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    required = {"datetime", "StrategySignal", "EntrySetup", "Close", "High", "Low", "ATR"}
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError(f"Feature parquet is missing required columns: {missing}")
    results = []
    all_trades = []
    for name, start, end in PERIODS:
        trades = _run(features, start, end)
        if not trades.empty:
            trades["AuditPeriod"] = name
            all_trades.append(trades)
        results.append({
            "period": name,
            "trades": int(len(trades)),
            "by_exit_reason": _group_metrics(trades, "Reason"),
            "by_entry_setup": _group_metrics(trades, "EntrySetup"),
        })
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(TRADES_PATH, index=False)
    report = {
        "execution": "raw event-based TrendStrategy with current active backtest exits, fees, slippage and 15-bar cooldown",
        "r_multiple": "Net PnL divided by initial ATR stop risk, including fees.",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("TrendStrategy exit audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_exit_audit()


if __name__ == "__main__":
    main()
