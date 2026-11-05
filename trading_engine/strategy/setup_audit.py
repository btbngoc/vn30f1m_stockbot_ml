"""Audit individual Wyckoff/VSA setup events with commission disabled."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "wyckoff_setup_audit_no_commission.json"
PERIODS = [("2024", "2024-01-01", "2025-01-01"), ("2025", "2025-01-01", "2026-01-01"), ("2026", "2026-01-01", None)]


def _event_start(event: pd.Series) -> pd.Series:
    return event & ~event.shift(1, fill_value=False)


def _metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "profit_factor": 0.0, "win_rate": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    return {"trades": int(len(trades)), "net_pnl": float(trades["PnL"].sum()), "profit_factor": float(wins / losses) if losses else None, "win_rate": float((trades["PnL"] > 0).mean())}


def run_setup_audit() -> dict:
    df = pd.read_parquet(FEATURES_PATH)
    df["datetime"] = pd.to_datetime(df["datetime"], errors="raise")
    trend = df["HTF_15m_TrendOK"] == 1
    demand = (df["HTF_5m_DemandZone"] == 1) | (df["HTF_5m_Ready"] == 1)
    setups = {
        "SPRING": _event_start((df["HTF_5m_Spring"] == 1) & trend),
        "TEST": _event_start((df["HTF_5m_Test"] == 1) & trend & demand),
        "LPS": _event_start((df["HTF_5m_Ready"] == 1) & trend & demand),
        "SOS": _event_start((df["HTF_5m_SOS"] == 1) & trend),
        "NO_SUPPLY": _event_start((df["VSA_NoSupply"] == 1) & trend & demand),
    }
    results = []
    for setup, signals in setups.items():
        yearly = []
        for name, start, end in PERIODS:
            period = df[df["datetime"] >= start].copy()
            if end:
                period = period[period["datetime"] < end].copy()
            period["Signal"] = signals.loc[period.index].astype(int)
            trades = BacktestEngine(period.set_index("datetime")).run()
            yearly.append({"period": name, "raw_events": int(period["Signal"].sum()), **_metrics(trades)})
        results.append({"setup": setup, "years": yearly})
    report = {"execution": "commission=0 temporary research mode; slippage and all ATR exits remain enabled", "results": results}
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wyckoff setup audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_setup_audit()


if __name__ == "__main__":
    main()
