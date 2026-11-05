"""Forward-only, non-executing journal for pre-registered Short candidates."""

import json
from pathlib import Path

import pandas as pd

from .backtest.config import DEFAULT_BACKTEST_CONFIG
from .backtest.engine import BacktestEngine
from .logging_config import logger
from .strategy.short_shadow_setups import build_short_shadow_setups

BASE_DIR = Path(__file__).resolve().parent
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
JOURNAL_PATH = BASE_DIR / "data" / "short_shadow_journal.csv"
STATE_PATH = BASE_DIR / "data" / "short_shadow_state.json"


def run_short_shadow_paper() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    features = features.sort_values("datetime").set_index("datetime")
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps({"last_seen": features.index.max().isoformat()}), encoding="utf-8")
        logger.info("Short shadow journal initialized at %s", features.index.max())
        return {"initialized": True, "new_signals": 0}
    last_seen = pd.Timestamp(json.loads(STATE_PATH.read_text(encoding="utf-8"))["last_seen"])
    journal = pd.read_csv(JOURNAL_PATH) if JOURNAL_PATH.exists() else pd.DataFrame()
    records = []
    for setup, signal in build_short_shadow_setups(features).items():
        for timestamp, row in features.loc[(features.index > last_seen) & signal].iterrows():
            atr = float(row["ATR"])
            entry = float(row["Close"] - DEFAULT_BACKTEST_CONFIG.slippage_points)
            records.append({
                "SignalKey": f"{setup}|{timestamp.isoformat()}", "SignalTime": timestamp, "Setup": setup,
                "Direction": "SHORT", "Entry": entry,
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
                journal.loc[index, ["Status", "ExitTime", "Exit", "ExitReason", "PnL"]] = ["CLOSED", trade["Exit Date"], trade["Exit"], trade["Reason"], trade["PnL"]]
        journal.to_csv(JOURNAL_PATH, index=False)
    STATE_PATH.write_text(json.dumps({"last_seen": features.index.max().isoformat()}), encoding="utf-8")
    logger.info("Short shadow scan complete | new signals=%s", len(records))
    return {"initialized": False, "new_signals": len(records), "journal": str(JOURNAL_PATH)}


def main() -> None:
    run_short_shadow_paper()


if __name__ == "__main__":
    main()
