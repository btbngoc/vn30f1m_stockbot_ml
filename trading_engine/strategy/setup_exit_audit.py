"""Audit exit causes and R-multiples for the least-bad Wyckoff setups."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "wyckoff_sos_test_exit_audit_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "wyckoff_sos_test_exit_audit_trades_no_commission.csv"


def _summary(rows: pd.DataFrame) -> dict:
    if rows.empty:
        return {"trades": 0, "net_pnl": 0.0, "avg_r_multiple": 0.0, "median_r_multiple": 0.0}
    return {
        "trades": int(len(rows)),
        "net_pnl": float(rows["PnL"].sum()),
        "avg_pnl": float(rows["PnL"].mean()),
        "win_rate": float((rows["PnL"] > 0).mean()),
        "avg_r_multiple": float(rows["RMultiple"].mean()),
        "median_r_multiple": float(rows["RMultiple"].median()),
        "avg_holding_bars": float(rows["HoldingBars"].mean()),
    }


def _run_period(period: pd.DataFrame, signals: pd.Series, setup: str) -> pd.DataFrame:
    period = period.copy()
    period["Signal"] = signals.loc[period.index].astype(int)
    trades = BacktestEngine(period.set_index("datetime")).run()
    if trades.empty:
        return trades

    entries = period.set_index("datetime")
    trades = trades.copy()
    entry_index = pd.to_datetime(trades["Entry Date"])
    exit_index = pd.to_datetime(trades["Exit Date"])
    initial_risk = (
        (trades["Entry"] - trades["Initial Stop Loss"]).abs()
        * trades["Contracts"]
        * DEFAULT_BACKTEST_CONFIG.point_multiplier
    )
    trades["Setup"] = setup
    trades["InitialRisk"] = initial_risk
    trades["RMultiple"] = trades["PnL"] / initial_risk.where(initial_risk > 0)
    entry_positions = pd.Series(range(len(period)), index=pd.DatetimeIndex(period["datetime"]))
    trades["HoldingBars"] = (
        exit_index.map(entry_positions).to_numpy() - entry_index.map(entry_positions).to_numpy()
    )
    # Retain the state at entry so changes are driven by evidence, not guesswork.
    for column in ("HTF_5m_DemandZone", "HTF_5m_SOS", "HTF_5m_Ready", "HTF_15m_TrendOK", "RVOL", "ATR_Percent", "BB_Width", "Close", "EMA10", "EMA20", "EMA50"):
        trades[f"Entry_{column}"] = entry_index.map(entries[column])
    return trades


def run_setup_exit_audit() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    trend = features["HTF_15m_TrendOK"] == 1
    demand = (features["HTF_5m_DemandZone"] == 1) | (features["HTF_5m_Ready"] == 1)
    setups = {
        "TEST": _event_start((features["HTF_5m_Test"] == 1) & trend & demand),
        "SOS": _event_start((features["HTF_5m_SOS"] == 1) & trend),
    }
    report_setups = []
    trade_frames = []
    for setup, signals in setups.items():
        yearly = []
        for name, start, end in PERIODS:
            period = features[features["datetime"] >= start].copy()
            if end:
                period = period[period["datetime"] < end].copy()
            trades = _run_period(period, signals, setup)
            if not trades.empty:
                trades["AuditPeriod"] = name
                trade_frames.append(trades)
            yearly.append({
                "period": name,
                "signal_events": int(signals.loc[period.index].sum()),
                "overall": _summary(trades),
                "by_exit_reason": {str(reason): _summary(rows) for reason, rows in trades.groupby("Reason", dropna=False)},
            })
        report_setups.append({"setup": setup, "years": yearly})
    if trade_frames:
        pd.concat(trade_frames, ignore_index=True).to_csv(TRADES_PATH, index=False)
    report = {
        "execution": "commission=0 research mode; 0.10-point slippage, ATR TP/SL/trailing, time limit and cooldown remain enabled",
        "r_multiple": "Net PnL divided by initial ATR stop risk.",
        "setups": report_setups,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("SOS/Test exit audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_setup_exit_audit()


if __name__ == "__main__":
    main()
