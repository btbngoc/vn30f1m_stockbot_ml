"""Independent walk-forward tests for the Long RANGE and HIGH_VOL setups."""

import json

import pandas as pd
import xgboost as xgb

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .directional_benchmark import DATASET_PATH
from .schema import ML_FEATURE_COLUMNS
from .train import FEATURES_PATH, MODEL_DIR, THRESHOLD_CANDIDATES, XGBOOST_PARAMS
from .walk_forward import FOLDS, _split

OUTPUT_PATH = MODEL_DIR / "long_regime_walk_forward_evaluation.json"
REGIMES = ("RANGE", "HIGH_VOL")
MIN_VALIDATION_TRADES = 20


def _pf_passes(metrics: dict) -> bool:
    return (metrics["profit_factor"] or 0) > 1 or (
        metrics["profit_factor"] is None and metrics["gross_profit"] > 0 and metrics["gross_loss"] == 0
    )


def _backtest_setup(model, features, regime: str, start, end, threshold: float) -> dict:
    period = features[features["datetime"] >= start].copy()
    if end is not None:
        period = period[period["datetime"] < end].copy()
    probability = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period["Confidence"] = probability
    period["Signal"] = (
        (period["StrategySignal"] == 1)
        & (period["MarketRegime"] == regime)
        & (period["Confidence"] >= threshold)
    ).astype(int)
    trades = BacktestEngine(period.set_index("datetime")).run()
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "max_drawdown": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    equity = trades["PnL"].cumsum()
    return {
        "trades": int(len(trades)),
        "net_pnl": float(trades["PnL"].sum()),
        "gross_profit": float(wins),
        "gross_loss": float(losses),
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "win_rate": float((trades["PnL"] > 0).mean()),
        "max_drawdown": float((equity.cummax() - equity).max()),
    }


def _select_threshold(model, features, regime: str, validation_start, test_start):
    candidates = []
    for threshold in THRESHOLD_CANDIDATES:
        metrics = _backtest_setup(model, features, regime, validation_start, test_start, threshold)
        candidates.append({"threshold": threshold, "validation": metrics})
    eligible = [
        item for item in candidates
        if item["validation"]["trades"] >= MIN_VALIDATION_TRADES
        and item["validation"]["net_pnl"] > 0
        and _pf_passes(item["validation"])
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item["validation"]["net_pnl"], item["validation"]["profit_factor"] or float("inf")))


def run_long_regime_walk_forward() -> dict:
    dataset = pd.read_csv(DATASET_PATH)
    dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
    dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    missing = sorted({"MarketRegime", *ML_FEATURE_COLUMNS} - set(features.columns))
    if missing:
        raise ValueError(f"Feature parquet is missing required columns: {missing}")
    results = []

    for regime in REGIMES:
        setup_data = dataset[(dataset["signal"] == 1) & (dataset["market_regime"] == regime)]
        folds = []
        for fold_name, validation_start, test_start, test_end in FOLDS:
            train, validation, test = _split(setup_data, validation_start, test_start, test_end)
            if min(len(train), len(validation), len(test)) == 0 or train["label"].nunique() < 2:
                raise ValueError(f"Invalid Long-{regime} split: {fold_name}")
            logger.info("Long-%s walk-forward %s | train=%d validation=%d test=%d", regime, fold_name, len(train), len(validation), len(test))
            model = xgb.XGBClassifier(**XGBOOST_PARAMS)
            model.fit(train[ML_FEATURE_COLUMNS], train["label"])
            selected = _select_threshold(model, features, regime, validation_start, test_start)
            if selected is None:
                folds.append({"fold": fold_name, "status": "NO_TRADE", "test": None})
                continue
            folds.append({
                "fold": fold_name,
                "status": "TRADE",
                "selected_threshold": selected["threshold"],
                "validation": selected["validation"],
                "test": _backtest_setup(model, features, regime, test_start, test_end, selected["threshold"]),
            })
        tests = [fold["test"] for fold in folds if fold["test"]]
        gross_profit = sum(item["gross_profit"] for item in tests)
        gross_loss = sum(item["gross_loss"] for item in tests)
        results.append({
            "setup": f"LONG_{regime}",
            "folds": folds,
            "summary": {
                "test_folds": len(folds),
                "trade_folds": len(tests),
                "pf_above_one_folds": sum(_pf_passes(item) for item in tests),
                "profitable_folds": sum(item["net_pnl"] > 0 for item in tests),
                "total_test_trades": sum(item["trades"] for item in tests),
                "aggregate_test_net_pnl": sum(item["net_pnl"] for item in tests),
                "aggregate_test_profit_factor": gross_profit / gross_loss if gross_loss else None,
                "worst_test_drawdown": max((item["max_drawdown"] for item in tests), default=0.0),
            },
        })

    report = {
        "selection_rule": "For each Long regime setup: choose threshold by validation PnL; PF breaks ties; NO_TRADE unless >=20 validation trades, positive PnL and PF > 1.",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Long regime walk-forward evaluation written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_long_regime_walk_forward()


if __name__ == "__main__":
    main()
