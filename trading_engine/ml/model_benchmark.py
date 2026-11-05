"""Compare models and label horizons with the existing walk-forward protocol."""

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import xgboost as xgb
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..logging_config import logger
from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..backtest.engine import BacktestEngine
from .schema import ML_FEATURE_COLUMNS
from .train import FEATURES_PATH, MODEL_DIR, THRESHOLD_CANDIDATES, XGBOOST_PARAMS, _classification_metrics
from .walk_forward import FOLDS, _split

OUTPUT_PATH = MODEL_DIR / "model_horizon_benchmark_net_pnl_label.json"
HORIZONS = (20, 50, 100)


def _models():
    return {
        "xgboost": lambda: xgb.XGBClassifier(**XGBOOST_PARAMS),
        "lightgbm": lambda: LGBMClassifier(n_estimators=500, learning_rate=0.03, max_depth=6, num_leaves=31, subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1, verbosity=-1),
        "catboost": lambda: CatBoostClassifier(iterations=500, learning_rate=0.03, depth=6, loss_function="Logloss", random_seed=42, verbose=False),
        "logistic_regression": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
    }


def _backtest_metrics(model, features, start, end, threshold: float, horizon: int) -> dict:
    """Backtest each label horizon with its matching time-limit exit."""
    period = features[features["datetime"] >= start].copy()
    if end is not None:
        period = period[period["datetime"] < end].copy()
    probability = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period["Confidence"] = probability
    period["Signal"] = period["StrategySignal"].where(period["Confidence"] >= threshold, 0).astype(int)
    config = replace(DEFAULT_BACKTEST_CONFIG, max_holding_bars=horizon)
    trades = BacktestEngine(period.set_index("datetime"), config=config).run()
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "max_drawdown": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    equity = trades["PnL"].cumsum()
    return {
        "trades": int(len(trades)), "net_pnl": float(trades["PnL"].sum()),
        "gross_profit": float(wins), "gross_loss": float(losses),
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "win_rate": float((trades["PnL"] > 0).mean()),
        "max_drawdown": float((equity.cummax() - equity).max()),
    }


def _select_threshold(model, validation, features, validation_start, test_start, horizon: int):
    probability = model.predict_proba(validation[ML_FEATURE_COLUMNS])[:, 1]
    candidates = []
    for threshold in THRESHOLD_CANDIDATES:
        candidates.append({
            "threshold": threshold,
            **_classification_metrics(validation["label"], probability, threshold),
            "backtest": _backtest_metrics(model, features, validation_start, test_start, threshold, horizon),
        })
    eligible = [item for item in candidates if item["backtest"]["trades"] >= 20 and item["backtest"]["net_pnl"] > 0 and (item["backtest"]["profit_factor"] or 0) > 1]
    return max(eligible, key=lambda item: (item["backtest"]["net_pnl"], item["backtest"]["profit_factor"] or 0)) if eligible else None


def run_benchmark() -> dict:
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    results = []
    for horizon in HORIZONS:
        dataset = pd.read_csv(MODEL_DIR.parent / "data" / f"ml_dataset_h{horizon}.csv")
        dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
        dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
        for model_name, factory in _models().items():
            folds = []
            for fold_name, validation_start, test_start, test_end in FOLDS:
                train, validation, test = _split(dataset, validation_start, test_start, test_end)
                model = factory()
                model.fit(train[ML_FEATURE_COLUMNS], train["label"])
                selected = _select_threshold(model, validation, features, validation_start, test_start, horizon)
                if selected is None:
                    folds.append({"fold": fold_name, "status": "NO_TRADE", "test": None})
                    continue
                probability = model.predict_proba(test[ML_FEATURE_COLUMNS])[:, 1]
                folds.append({
                    "fold": fold_name, "status": "TRADE", "selected_threshold": selected["threshold"],
                    "validation": selected,
                    "test": {"classification": _classification_metrics(test["label"], probability, selected["threshold"]), "backtest": _backtest_metrics(model, features, test_start, test_end, selected["threshold"], horizon)}
                })
            test_metrics = [f["test"]["backtest"] for f in folds if f["test"]]
            results.append({"horizon": horizon, "execution_max_holding_bars": horizon, "model": model_name, "folds": folds, "summary": {
                "trade_folds": len(test_metrics), "pf_above_one_folds": sum((m["profit_factor"] or 0) > 1 for m in test_metrics),
                "profitable_folds": sum(m["net_pnl"] > 0 for m in test_metrics), "total_test_trades": sum(m["trades"] for m in test_metrics),
                "net_pnl": sum(m["net_pnl"] for m in test_metrics), "worst_drawdown": max((m["max_drawdown"] for m in test_metrics), default=0.0),
            }})
            logger.info("Benchmark horizon=%d model=%s complete", horizon, model_name)
    report = {
        "label_definition": "one-contract realized net PnL > 0 after active-backtest slippage, fees, dynamic ATR trailing stop, and time limit",
        "selection_rule": "NO_TRADE unless validation has >=20 trades, positive net PnL and PF > 1",
        "results": results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Model/horizon benchmark written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_benchmark()


if __name__ == "__main__":
    main()
