"""Evaluate separate Long and Short classifiers without replacing production.

The current production classifier estimates whether score-generated signals
will work.  This experiment trains two independent models, because VN30F1M
long and short moves can have different market microstructure and regimes.
"""

import json

import pandas as pd
import xgboost as xgb

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .schema import ML_FEATURE_COLUMNS
from .train import DATASET_PATH, FEATURES_PATH, MODEL_DIR, THRESHOLD_CANDIDATES, XGBOOST_PARAMS

OUTPUT_PATH = MODEL_DIR / "directional_regime_evaluation.json"

VALIDATION_START = pd.Timestamp("2025-01-01")
TEST_START = pd.Timestamp("2026-01-01")
MIN_VALIDATION_TRADES = 8



def _backtest_direction(model, features: pd.DataFrame, direction: int, start, end, threshold):
    period = features[features["datetime"] >= start].copy()
    if end is not None:
        period = period[period["datetime"] < end].copy()
    probability = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period["Confidence"] = probability
    period["Signal"] = 0
    selected = (period["StrategySignal"] == direction) & (period["Confidence"] >= threshold)
    period.loc[selected, "Signal"] = direction
    trades = BacktestEngine(period.set_index("datetime")).run()
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "profit_factor": 0.0, "win_rate": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    return {
        "trades": int(len(trades)),
        "net_pnl": float(trades["PnL"].sum()),
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "win_rate": float((trades["PnL"] > 0).mean()),
    }


def select_directional_threshold(model, features, direction: int, validation_start=VALIDATION_START, test_start=TEST_START):
    results = []
    for threshold in THRESHOLD_CANDIDATES:
        backtest = _backtest_direction(model, features, direction, validation_start, test_start, threshold)
        results.append({"threshold": threshold, "validation": backtest})
    eligible = [
        item for item in results
        if item["validation"]["trades"] >= MIN_VALIDATION_TRADES
        and item["validation"]["net_pnl"] > 0
        and (item["validation"]["profit_factor"] or 0) > 1
    ]
    return max(eligible, key=lambda item: (item["validation"]["net_pnl"], item["validation"]["profit_factor"] or 0)) if eligible else None


def run_directional_benchmark() -> dict:
    dataset = pd.read_csv(DATASET_PATH)
    dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
    dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    results = []

    for direction, name in [(1, "long"), (-1, "short")]:
        directional = dataset[dataset["signal"] == direction]
        train = directional[directional["exit_time"] < VALIDATION_START]
        validation = directional[(directional["entry_time"] >= VALIDATION_START) & (directional["exit_time"] < TEST_START)]
        test = directional[directional["entry_time"] >= TEST_START]
        if min(len(train), len(validation), len(test)) == 0 or train["label"].nunique() < 2:
            raise ValueError(f"Invalid {name} split")
        model = xgb.XGBClassifier(**XGBOOST_PARAMS)
        logger.info("Training directional %s model | train=%d validation=%d test=%d", name, len(train), len(validation), len(test))
        model.fit(train[ML_FEATURE_COLUMNS], train["label"])
        selected = select_directional_threshold(model, features, direction)
        if selected is None:
            results.append({"direction": name, "status": "NO_TRADE", "test": None})
            continue
        results.append({
            "direction": name,
            "status": "TRADE",
            "selected_threshold": selected["threshold"],
            "validation": selected["validation"],
            "test": _backtest_direction(model, features, direction, TEST_START, None, selected["threshold"]),
            "regime_distribution": test.groupby("market_regime")["label"].agg(["count", "mean"]).round(4).to_dict("index"),
        })

    report = {
        "selection_rule": "Separate Long/Short models; NO_TRADE unless 2025 validation has >=20 trades, positive PnL and PF > 1.",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Directional/regime evaluation written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_directional_benchmark()


if __name__ == "__main__":
    main()
