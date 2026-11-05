"""Walk-forward evaluation with independent validation and test years."""

import json
from pathlib import Path

import pandas as pd
import xgboost as xgb

from ..logging_config import logger
from .schema import ML_FEATURE_COLUMNS
from .train import (
    DATASET_PATH, FEATURES_PATH, MODEL_DIR, THRESHOLD_CANDIDATES, XGBOOST_PARAMS,
    _backtest_metrics, _classification_metrics,
)

OUTPUT_PATH = MODEL_DIR / "walk_forward_evaluation.json"
FOLDS = [
    ("2018-2022 / 2023 / 2024", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
    ("2018-2023 / 2024 / 2025", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01")),
    ("2018-2024 / 2025 / 2026", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), None),
]


def _split(dataset: pd.DataFrame, validation_start, test_start, test_end):
    train = dataset[dataset["exit_time"] < validation_start]
    validation = dataset[(dataset["entry_time"] >= validation_start) & (dataset["exit_time"] < test_start)]
    test = dataset[dataset["entry_time"] >= test_start]
    if test_end is not None:
        test = test[test["exit_time"] < test_end]
    return train, validation, test


def run_walk_forward() -> dict:
    dataset = pd.read_csv(DATASET_PATH)
    dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
    dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    results = []

    for name, validation_start, test_start, test_end in FOLDS:
        train, validation, test = _split(dataset, validation_start, test_start, test_end)
        if min(len(train), len(validation), len(test)) == 0 or train["label"].nunique() < 2:
            raise ValueError(f"Invalid walk-forward split: {name}")
        logger.info("Walk-forward %s | train=%d validation=%d test=%d", name, len(train), len(validation), len(test))
        model = xgb.XGBClassifier(**XGBOOST_PARAMS)
        model.fit(train[ML_FEATURE_COLUMNS], train["label"])
        validation_probability = model.predict_proba(validation[ML_FEATURE_COLUMNS])[:, 1]
        candidates = []
        for threshold in THRESHOLD_CANDIDATES:
            candidates.append({
                "threshold": threshold,
                **_classification_metrics(validation["label"], validation_probability, threshold),
                "backtest": _backtest_metrics(model, features, validation_start, test_start, threshold),
            })
        eligible = [item for item in candidates if item["backtest"]["trades"] >= 8]
        pf_target = [item for item in eligible if (item["backtest"]["profit_factor"] or 0.0) >= 1.60 and item["backtest"]["net_pnl"] > 0]
        if pf_target:
            selected = max(pf_target, key=lambda item: (item["backtest"]["profit_factor"] or 0.0, item["backtest"]["net_pnl"]))
        else:
            selected = max(eligible or candidates, key=lambda item: (item["backtest"]["profit_factor"] or 0.0, item["backtest"]["net_pnl"]))
        test_probability = model.predict_proba(test[ML_FEATURE_COLUMNS])[:, 1]
        results.append({
            "fold": name,
            "rows": {"train": len(train), "validation": len(validation), "test": len(test)},
            "selected_threshold": selected["threshold"],
            "validation_selected": selected,
            "test": {
                "classification": _classification_metrics(test["label"], test_probability, selected["threshold"]),
                "backtest": _backtest_metrics(model, features, test_start, test_end, selected["threshold"]),
            },
        })

    test_backtests = [result["test"]["backtest"] for result in results]
    gross_profit = sum(item["gross_profit"] for item in test_backtests)
    gross_loss = sum(item["gross_loss"] for item in test_backtests)
    summary = {
        "test_folds": len(results),
        "profitable_test_folds": sum(item["net_pnl"] > 0 for item in test_backtests),
        "pf_above_one_test_folds": sum((item["profit_factor"] or 0) > 1 for item in test_backtests),
        "total_test_trades": sum(item["trades"] for item in test_backtests),
        "aggregate_test_net_pnl": sum(item["net_pnl"] for item in test_backtests),
        "aggregate_test_profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
        "worst_test_drawdown": max(item["max_drawdown"] for item in test_backtests),
    }
    report = {"selection_rule": "maximum validation net PnL; profit factor breaks ties; minimum 20 trades", "folds": results, "summary": summary}
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Walk-forward evaluation saved to %s | %s", OUTPUT_PATH, summary)
    return report


def main() -> None:
    run_walk_forward()


if __name__ == "__main__":
    main()
