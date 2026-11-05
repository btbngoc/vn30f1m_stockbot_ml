"""Audit raw TrendStrategy signals before any ML confidence filtering."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "trend_strategy_raw_audit.json"

PERIODS = [
    ("all_history", None, None),
    ("2024", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
    ("2025", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01")),
    ("2026", pd.Timestamp("2026-01-01"), None),
]


def _metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "avg_pnl": 0.0, "max_drawdown": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    equity = trades["PnL"].cumsum()
    return {
        "trades": int(len(trades)),
        "net_pnl": float(trades["PnL"].sum()),
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "win_rate": float((trades["PnL"] > 0).mean()),
        "avg_pnl": float(trades["PnL"].mean()),
        "max_drawdown": float((equity.cummax() - equity).max()),
    }


def _run(features: pd.DataFrame, start, end, direction: int | None) -> dict:
    period = features.copy()
    if start is not None:
        period = period[period["datetime"] >= start]
    if end is not None:
        period = period[period["datetime"] < end]
    period["Signal"] = period["StrategySignal"]
    if direction is not None:
        period.loc[period["Signal"] != direction, "Signal"] = 0
    raw_candidates = int((period["Signal"] != 0).sum())
    trades = BacktestEngine(period.set_index("datetime")).run()
    return {"raw_candidates": raw_candidates, **_metrics(trades)}


def run_audit() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    required = {"datetime", "StrategySignal", "Close", "High", "Low", "ATR"}
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError(f"Feature parquet is missing required columns: {missing}")
    results = []
    for name, start, end in PERIODS:
        results.append({
            "period": name,
            "combined": _run(features, start, end, None),
            "long_only": _run(features, start, end, 1),
            "short_only": _run(features, start, end, -1),
        })
    report = {
        "execution": "event-based TrendStrategy entries; EMA/ADX + breakout/pullback confirmation; one entry per EMA trend; 15-bar post-exit cooldown; active ATR exits, slippage and commissions",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Raw TrendStrategy audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_audit()


if __name__ == "__main__":
    main()
