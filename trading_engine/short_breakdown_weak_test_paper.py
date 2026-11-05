"""Forward-only shadow journal for the frozen BREAKDOWN_WEAK_TEST Short gate."""

import json
from pathlib import Path

import pandas as pd

from .backtest.config import DEFAULT_BACKTEST_CONFIG
from .backtest.engine import BacktestEngine
from .logging_config import logger
from .strategy.setup_audit import _event_start

BASE_DIR = Path(__file__).resolve().parent
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
JOURNAL_PATH = BASE_DIR / "data" / "short_breakdown_weak_test_paper_journal.csv"
STATE_PATH = BASE_DIR / "data" / "short_breakdown_weak_test_paper_state.json"
SETUP = "BREAKDOWN_WEAK_TEST_NOT_LUNCH_ROOM_1_TO_3_ATR"


def build_frozen_signals(features: pd.DataFrame) -> pd.Series:
    """Pre-registered rule: completed 5m event, not lunch, 1-3 ATR room."""
    required = ["HTF_5m_BreakdownWeakTest", "Distance_DayLow", "LunchSession", "ATR"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Missing frozen Short-gate features: {missing}")
    event = _event_start(features["HTF_5m_BreakdownWeakTest"] == 1)
    day_low = features["Close"] / (1 + features["Distance_DayLow"])
    room_to_low_atr = (features["Close"] - day_low) / features["ATR"]
    return event & ~features["LunchSession"].fillna(0).astype(bool) & room_to_low_atr.between(1.0, 3.0, inclusive="both")


def run_short_breakdown_weak_test_paper() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    features = features.sort_values("datetime").set_index("datetime")
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps({"last_seen": features.index.max().isoformat()}), encoding="utf-8")
        logger.info("BREAKDOWN_WEAK_TEST paper journal initialized at %s", features.index.max())
        return {"initialized": True, "new_signals": 0, "journal": str(JOURNAL_PATH)}

    last_seen = pd.Timestamp(json.loads(STATE_PATH.read_text(encoding="utf-8"))["last_seen"])
    signals = build_frozen_signals(features)
    journal = pd.read_csv(JOURNAL_PATH) if JOURNAL_PATH.exists() else pd.DataFrame()
    records = []
    for timestamp, row in features.loc[(features.index > last_seen) & signals].iterrows():
        atr = float(row["ATR"])
        entry = float(row["Close"] - DEFAULT_BACKTEST_CONFIG.slippage_points)
        records.append({
            "SignalKey": f"{SETUP}|{timestamp.isoformat()}", "SignalTime": timestamp,
            "Setup": SETUP, "Direction": "SHORT", "Entry": entry,
            "InitialStop": entry + DEFAULT_BACKTEST_CONFIG.stop_loss_atr * atr,
            "TakeProfit": entry - DEFAULT_BACKTEST_CONFIG.take_profit_atr * atr,
            "ATR": atr, "Status": "OPEN", "Mode": "SHADOW_ONLY",
        })
    if records:
        journal = pd.concat([journal, pd.DataFrame(records)], ignore_index=True)
        journal = journal.drop_duplicates(subset=["SignalKey"], keep="last")

    if not journal.empty:
        for index, row in journal[journal["Status"] == "OPEN"].iterrows():
            start = pd.Timestamp(row["SignalTime"])
            path = features.loc[features.index >= start].copy()
            path["Signal"] = 0
            if start in path.index:
                path.loc[start, "Signal"] = -1
            trades = BacktestEngine(path).run()
            if not trades.empty and trades.iloc[0]["Reason"] != "End of Data":
                trade = trades.iloc[0]
                journal.loc[index, ["Status", "ExitTime", "Exit", "ExitReason", "PnL"]] = [
                    "CLOSED", trade["Exit Date"], trade["Exit"], trade["Reason"], trade["PnL"],
                ]
        journal.to_csv(JOURNAL_PATH, index=False)

    STATE_PATH.write_text(json.dumps({"last_seen": features.index.max().isoformat()}), encoding="utf-8")
    logger.info("BREAKDOWN_WEAK_TEST paper scan complete | new signals=%s", len(records))
    return {"initialized": False, "new_signals": len(records), "journal": str(JOURNAL_PATH)}


def main() -> None:
    run_short_breakdown_weak_test_paper()


if __name__ == "__main__":
    main()
