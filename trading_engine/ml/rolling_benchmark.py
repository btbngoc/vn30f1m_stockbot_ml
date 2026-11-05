"""Quarterly out-of-sample validation for the model/horizon candidates.

This is deliberately narrower than ``model_benchmark``.  That benchmark
eliminated most combinations; this module asks whether the remaining
candidates survive repeated, independent quarterly tests.
"""

import json

import pandas as pd
import xgboost as xgb
from catboost import CatBoostClassifier

from ..logging_config import logger
from .schema import ML_FEATURE_COLUMNS
from .train import (
    FEATURES_PATH,
    MODEL_DIR,
    THRESHOLD_CANDIDATES,
    XGBOOST_PARAMS,
    _backtest_metrics,
    _classification_metrics,
)
from .walk_forward import _split

# Keep the strict-20 result intact so the two gates can be compared directly.
OUTPUT_PATH = MODEL_DIR / "rolling_quarterly_evaluation_min8.json"
MIN_VALIDATION_TRADES = 8

# Candidates selected only as hypotheses from the annual benchmark.  They are
# not approved for live trading unless they pass this repeated OOS evaluation.
CANDIDATES = {
    "xgboost_h50": (50, lambda: xgb.XGBClassifier(**XGBOOST_PARAMS)),
    "catboost_h100": (
        100,
        lambda: CatBoostClassifier(
            iterations=500,
            learning_rate=0.03,
            depth=6,
            loss_function="Logloss",
            random_seed=42,
            verbose=False,
        ),
    ),
}


def _pf_above_one(backtest: dict) -> bool:
    """Treat a profitable run with no losing trade as an infinite PF."""
    profit_factor = backtest["profit_factor"]
    if profit_factor is not None:
        return profit_factor > 1
    return backtest["gross_profit"] > 0 and backtest["gross_loss"] == 0


def _quarterly_folds():
    """Return expanding-train folds from 2024Q1 through completed 2026Q2."""
    test_starts = pd.date_range("2024-01-01", "2026-04-01", freq="QS")

    def quarter_name(timestamp: pd.Timestamp) -> str:
        return f"{timestamp.year}Q{timestamp.quarter}"

    return [
        (
            f"validation {quarter_name(validation_start)} / test {quarter_name(test_start)}",
            validation_start,
            test_start,
            test_start + pd.offsets.QuarterBegin(startingMonth=1),
        )
        for test_start in test_starts
        for validation_start in [test_start - pd.offsets.QuarterBegin(startingMonth=1)]
    ]


def _select_threshold(model, validation, features, validation_start, test_start):
    probabilities = model.predict_proba(validation[ML_FEATURE_COLUMNS])[:, 1]
    evaluations = [
        {
            "threshold": threshold,
            **_classification_metrics(validation["label"], probabilities, threshold),
            "backtest": _backtest_metrics(model, features, validation_start, test_start, threshold),
        }
        for threshold in THRESHOLD_CANDIDATES
    ]
    eligible = [
        item
        for item in evaluations
        if item["backtest"]["trades"] >= MIN_VALIDATION_TRADES
        and item["backtest"]["net_pnl"] > 0
        and _pf_above_one(item["backtest"])
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda item: (
            item["backtest"]["net_pnl"],
            item["backtest"]["profit_factor"] if item["backtest"]["profit_factor"] is not None else float("inf"),
        ),
    )


def run_rolling_benchmark() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    results = []

    for candidate_name, (horizon, factory) in CANDIDATES.items():
        dataset_path = MODEL_DIR.parent / "data" / f"ml_dataset_h{horizon}.csv"
        dataset = pd.read_csv(dataset_path)
        dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
        dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
        folds = []

        for name, validation_start, test_start, test_end in _quarterly_folds():
            train, validation, test = _split(dataset, validation_start, test_start, test_end)
            if min(len(train), len(validation), len(test)) == 0 or train["label"].nunique() < 2:
                raise ValueError(f"Invalid rolling split: {name}")
            logger.info(
                "Rolling %s | %s | train=%d validation=%d test=%d",
                candidate_name,
                name,
                len(train),
                len(validation),
                len(test),
            )
            model = factory()
            model.fit(train[ML_FEATURE_COLUMNS], train["label"])
            selected = _select_threshold(model, validation, features, validation_start, test_start)
            if selected is None:
                folds.append({"fold": name, "status": "NO_TRADE", "test": None})
                continue
            probabilities = model.predict_proba(test[ML_FEATURE_COLUMNS])[:, 1]
            folds.append(
                {
                    "fold": name,
                    "status": "TRADE",
                    "selected_threshold": selected["threshold"],
                    "validation": selected,
                    "test": {
                        "classification": _classification_metrics(test["label"], probabilities, selected["threshold"]),
                        "backtest": _backtest_metrics(model, features, test_start, test_end, selected["threshold"]),
                    },
                }
            )

        tests = [fold["test"]["backtest"] for fold in folds if fold["test"]]
        gross_profit = sum(item["gross_profit"] for item in tests)
        gross_loss = sum(item["gross_loss"] for item in tests)
        results.append(
            {
                "candidate": candidate_name,
                "horizon": horizon,
                "folds": folds,
                "summary": {
                    "quarterly_test_folds": len(folds),
                    "trade_folds": len(tests),
                    "pf_above_one_folds": sum(_pf_above_one(item) for item in tests),
                    "profitable_folds": sum(item["net_pnl"] > 0 for item in tests),
                    "total_test_trades": sum(item["trades"] for item in tests),
                    "aggregate_test_net_pnl": sum(item["net_pnl"] for item in tests),
                    "aggregate_test_profit_factor": gross_profit / gross_loss if gross_loss else None,
                    "worst_test_drawdown": max((item["max_drawdown"] for item in tests), default=0.0),
                },
            }
        )

    report = {
        "selection_rule": "NO_TRADE unless validation has >=8 trades, positive net PnL and PF > 1",
        "minimum_validation_trades": MIN_VALIDATION_TRADES,
        "acceptance_rule": "A candidate needs PF > 1 and positive PnL in a majority of TRADE test folds, with enough cumulative OOS trades.",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Quarterly rolling evaluation written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_rolling_benchmark()


if __name__ == "__main__":
    main()
