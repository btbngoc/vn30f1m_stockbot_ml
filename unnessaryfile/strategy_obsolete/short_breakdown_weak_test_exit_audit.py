"""Context and exit audit for the raw BREAKDOWN_WEAK_TEST Short setup.

This is diagnostic only: it does not alter the entry state machine, ML model,
dataset, or backtest configuration.  Its purpose is to identify context gates
that are supported by the existing 140-trade sample before any rule is changed.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..logging_config import logger
from .setup_audit import _metrics
from .short_distribution_audit import load_features

BASE_DIR = Path(__file__).resolve().parents[1]
TRADES_PATH = BASE_DIR / "models" / "short_condition_breakdown_trades_no_commission.csv"
OUTPUT_PATH = BASE_DIR / "models" / "short_breakdown_weak_test_context_audit_no_commission.json"
DETAIL_PATH = BASE_DIR / "models" / "short_breakdown_weak_test_context_audit_no_commission.csv"
SETUP = "BREAKDOWN_WEAK_TEST"


def _group_metrics(frame: pd.DataFrame, field: str) -> list[dict]:
    rows = []
    for value, group in frame.groupby(field, dropna=False, observed=False):
        metrics = _metrics(group)
        rows.append({"value": str(value), **metrics, "mean_r": float(group["RMultiple"].mean())})
    return rows


def _session(row: pd.Series) -> str:
    if row.get("OpenSession", 0):
        return "OPEN"
    if row.get("LunchSession", 0):
        return "LUNCH_EDGE"
    if row.get("CloseSession", 0):
        return "CLOSE"
    return "MID_SESSION"


def run_short_breakdown_weak_test_exit_audit() -> dict:
    if not TRADES_PATH.exists():
        raise FileNotFoundError(f"Run short-narrow-range-audit first: {TRADES_PATH}")

    trades = pd.read_csv(TRADES_PATH)
    trades = trades.loc[trades["Setup"] == SETUP].copy()
    if trades.empty:
        raise ValueError(f"No trades found for {SETUP}")
    trades["Entry Date"] = pd.to_datetime(trades["Entry Date"], errors="raise")

    features = load_features()
    context = features.reindex(trades["Entry Date"])
    context.index = trades.index
    result = trades.copy()
    result["Win"] = result["PnL"] > 0
    initial_risk = (
        (result["Entry"] - result["Initial Stop Loss"]).abs()
        * result["Contracts"]
        * DEFAULT_BACKTEST_CONFIG.point_multiplier
    )
    result["RMultiple"] = result["PnL"] / initial_risk.replace(0, np.nan)
    result["MarketRegime"] = context["MarketRegime"].fillna("UNKNOWN")
    result["TrendTransitionDown15m"] = context["HTF_15m_TrendTransitionDown"].fillna(0).astype(int)
    result["TrendDown15m"] = context["HTF_15m_TrendDownOK"].fillna(0).astype(int)
    result["BelowVWAP"] = (context["Close"] < context["VWAP"]).fillna(False)
    result["BearishEMA"] = ((context["EMA10"] < context["EMA20"]) & (context["EMA20"] < context["EMA50"])).fillna(False)
    result["Session"] = context.apply(_session, axis=1)
    result["TestRVOL_1m"] = context["RVOL"]
    result["TestSpreadATR_1m"] = (context["High"] - context["Low"]) / context["ATR"]
    result["TestCloseLocation_1m"] = (context["Close"] - context["Low"]) / (context["High"] - context["Low"]).replace(0, np.nan)
    day_low = context["Close"] / (1 + context["Distance_DayLow"])
    result["RoomToDayLowATR"] = (context["Close"] - day_low) / context["ATR"]
    result["RoomToDayLowBucket"] = pd.cut(
        result["RoomToDayLowATR"], [-np.inf, 1, 3, np.inf], labels=["<=1_ATR", "1_to_3_ATR", ">3_ATR"]
    )
    result["RVOLBucket"] = pd.cut(result["TestRVOL_1m"], [-np.inf, 0.8, 1.2, np.inf], labels=["LOW", "NORMAL", "HIGH"])
    result.to_csv(DETAIL_PATH, index=False)

    win_loss = []
    for win, group in result.groupby("Win"):
        win_loss.append({
            "outcome": "WIN" if win else "LOSS",
            **_metrics(group),
            "mean_r": float(group["RMultiple"].mean()),
            "median_r": float(group["RMultiple"].median()),
            "mean_test_rvol_1m": float(group["TestRVOL_1m"].mean()),
            "mean_room_to_day_low_atr": float(group["RoomToDayLowATR"].mean()),
        })

    report = {
        "execution": "diagnostic audit only for raw BREAKDOWN_WEAK_TEST trades; no entry, ML, model, dataset, fee, or exit-rule change",
        "all_trades": {**_metrics(result), "mean_r": float(result["RMultiple"].mean()), "median_r": float(result["RMultiple"].median())},
        "win_vs_loss": win_loss,
        "exit_reasons": _group_metrics(result, "Reason"),
        "context_groups": {
            "market_regime": _group_metrics(result, "MarketRegime"),
            "transition_down_15m": _group_metrics(result, "TrendTransitionDown15m"),
            "slow_downtrend_15m": _group_metrics(result, "TrendDown15m"),
            "below_vwap": _group_metrics(result, "BelowVWAP"),
            "bearish_ema": _group_metrics(result, "BearishEMA"),
            "session": _group_metrics(result, "Session"),
            "room_to_day_low": _group_metrics(result, "RoomToDayLowBucket"),
            "entry_rvol": _group_metrics(result, "RVOLBucket"),
        },
        "details_csv": str(DETAIL_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short BREAKDOWN_WEAK_TEST context audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_breakdown_weak_test_exit_audit()


if __name__ == "__main__":
    main()
