"""Walk-forward test of independent Long and Short XGBoost classifiers."""

import json

import pandas as pd
import xgboost as xgb

from ..logging_config import logger
from .directional_benchmark import DATASET_PATH, _backtest_direction, select_directional_threshold
from .schema import ML_FEATURE_COLUMNS
from .train import FEATURES_PATH, MODEL_DIR, XGBOOST_PARAMS
from .walk_forward import FOLDS, _split

OUTPUT_PATH = MODEL_DIR / "directional_walk_forward_evaluation.json"


def run_directional_walk_forward() -> dict:
    dataset = pd.read_csv(DATASET_PATH)
    dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
    dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    results = []

    for direction, name in [(1, "long"), (-1, "short")]:
        directional = dataset[dataset["signal"] == direction]
        folds = []
        for fold_name, validation_start, test_start, test_end in FOLDS:
            train, validation, test = _split(directional, validation_start, test_start, test_end)
            if min(len(train), len(validation), len(test)) == 0 or train["label"].nunique() < 2:
                raise ValueError(f"Invalid {name} walk-forward split: {fold_name}")
            logger.info("Directional walk-forward %s | %s | train=%d validation=%d test=%d", name, fold_name, len(train), len(validation), len(test))
            model = xgb.XGBClassifier(**XGBOOST_PARAMS)
            model.fit(train[ML_FEATURE_COLUMNS], train["label"])
            selected = select_directional_threshold(model, features, direction, validation_start, test_start)
            if selected is None:
                folds.append({"fold": fold_name, "status": "NO_TRADE", "test": None})
                continue
            folds.append({
                "fold": fold_name,
                "status": "TRADE",
                "selected_threshold": selected["threshold"],
                "validation": selected["validation"],
                "test": _backtest_direction(model, features, direction, test_start, test_end, selected["threshold"]),
            })
        tests = [fold["test"] for fold in folds if fold["test"]]
        results.append({
            "direction": name,
            "folds": folds,
            "summary": {
                "trade_folds": len(tests),
                "profitable_folds": sum(item["net_pnl"] > 0 for item in tests),
                "pf_above_one_folds": sum((item["profit_factor"] or 0) > 1 for item in tests),
                "total_test_trades": sum(item["trades"] for item in tests),
                "aggregate_test_net_pnl": sum(item["net_pnl"] for item in tests),
            },
        })

    report = {
        "selection_rule": "Per-direction threshold; NO_TRADE unless validation has >=20 trades, positive PnL and PF > 1.",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Directional walk-forward evaluation written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_directional_walk_forward()


if __name__ == "__main__":
    main()
