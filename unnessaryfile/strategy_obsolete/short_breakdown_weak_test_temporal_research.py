"""Chronological research for broader BREAKDOWN_WEAK_TEST Short variants.

Pre-registered candidates only.  Develop through 2022, select on 2023, then
run the selected candidate once on untouched annual 2024-2026 test folds.
"""

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _event_start, _metrics
from .short_distribution_audit import load_features

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_breakdown_weak_test_temporal_research.json"
TRADES_PATH = BASE_DIR / "models" / "short_breakdown_weak_test_temporal_selected_trades.csv"
COMMISSION_PER_CONTRACT = 5_000.0  # VND per contract per side; replace with broker fee later.
EXECUTION_COLUMNS = ["Open", "High", "Low", "Close", "ATR"]



def build_candidates(features: pd.DataFrame) -> dict[str, pd.Series]:
    event = _event_start(features["HTF_5m_BreakdownWeakTest"] == 1)
    lunch = features["LunchSession"].fillna(0).astype(bool)
    day_low = features["Close"] / (1 + features["Distance_DayLow"])
    room = (features["Close"] - day_low) / features["ATR"]
    return {
        "BASELINE": event,
        "NO_LUNCH": event & ~lunch,
        "ROOM_1_TO_3_ATR": event & room.between(1.0, 3.0, inclusive="both"),
        "NO_LUNCH_ROOM_1_TO_3_ATR": event & ~lunch & room.between(1.0, 3.0, inclusive="both"),
    }


def run_backtest(features: pd.DataFrame, signal: pd.Series) -> tuple[pd.DataFrame, dict]:
    frame = features.loc[:, EXECUTION_COLUMNS].copy()
    frame["Signal"] = -signal.astype(int)
    config = replace(DEFAULT_BACKTEST_CONFIG, commission_per_contract=COMMISSION_PER_CONTRACT)
    trades = BacktestEngine(frame, config=config).run()
    return trades, _metrics(trades)


def period_frame(features: pd.DataFrame, signal: pd.Series, start: str, end: str | None = None) -> tuple[pd.DataFrame, pd.Series]:
    mask = features.index >= start
    if end:
        mask &= features.index < end
    return features.loc[mask], signal.loc[mask]


def evaluate(features: pd.DataFrame, signal: pd.Series, start: str, end: str | None = None) -> dict:
    frame, subset = period_frame(features, signal, start, end)
    _, metrics = run_backtest(frame, subset)
    return {"events": int(subset.sum()), **metrics}


def run_short_breakdown_weak_test_temporal_research() -> dict:
    features = load_features()
    required = ["HTF_5m_BreakdownWeakTest", "LunchSession", "Distance_DayLow", *EXECUTION_COLUMNS]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")
    candidates = build_candidates(features)

    development = []
    for name, signal in candidates.items():
        train = evaluate(features, signal, "2018-01-01", "2023-01-01")
        validation = evaluate(features, signal, "2023-01-01", "2024-01-01")
        eligible = (
            train["trades"] >= 30
            and train["profit_factor"] is not None and train["profit_factor"] > 1.0
            and validation["trades"] >= 5
            and validation["profit_factor"] is not None and validation["profit_factor"] > 1.0
        )
        development.append({"candidate": name, "train_2018_2022": train, "validation_2023": validation, "eligible": eligible})

    finalists = [item for item in development if item["eligible"]]
    selected = None
    tests = []
    selected_trades = pd.DataFrame()
    if finalists:
        selected = max(finalists, key=lambda item: (item["validation_2023"]["net_pnl"], item["validation_2023"]["profit_factor"]))["candidate"]
        selected_signal = candidates[selected]
        for year in ("2024", "2025", "2026"):
            frame, subset = period_frame(features, selected_signal, f"{year}-01-01", None if year == "2026" else f"{int(year) + 1}-01-01")
            trades, metrics = run_backtest(frame, subset)
            tests.append({"period": year, "events": int(subset.sum()), **metrics})
            if not trades.empty:
                trades.insert(0, "TestPeriod", year)
                selected_trades = pd.concat([selected_trades, trades], ignore_index=True)
        if not selected_trades.empty:
            selected_trades.to_csv(TRADES_PATH, index=False)

    report = {
        "method": "pre-registered four candidate gates; develop 2018-2022; select once on 2023; untouched test folds 2024, 2025, 2026",
        "commission_assumption_vnd_per_contract_per_side": COMMISSION_PER_CONTRACT,
        "selection_rule": "train >=30 trades and PF>1; validation >=5 trades and PF>1; select highest validation net PnL, then PF",
        "development": development,
        "selected_candidate": selected,
        "test_folds": tests,
        "test_pf_above_one_folds": sum(item["profit_factor"] is not None and item["profit_factor"] > 1 for item in tests),
        "selected_trades_csv": str(TRADES_PATH) if selected_trades.shape[0] else None,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Temporal BREAKDOWN_WEAK_TEST research written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_breakdown_weak_test_temporal_research()


if __name__ == "__main__":
    main()
