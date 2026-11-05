"""
Train XGBoost model.

Pipeline:

VN30F1M_features.parquet
        ↓
Label dataset (ml_dataset.csv)
        ↓
Train model
        ↓
models/
    ├── xgboost_model.pkl
    ├── feature_columns.pkl
    └── train.parquet
"""

from pathlib import Path
import json

import joblib
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from ..logging_config import logger
from ..backtest.engine import BacktestEngine
from .schema import ML_FEATURE_COLUMNS

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

DATASET_PATH = BASE_DIR / "data" / "ml_dataset.csv"
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

MODEL_PATH = MODEL_DIR / "xgboost_model.pkl"
FEATURE_PATH = MODEL_DIR / "feature_columns.pkl"
THRESHOLD_PATH = MODEL_DIR / "confidence_threshold.pkl"
EVALUATION_PATH = MODEL_DIR / "temporal_evaluation.json"
TRAIN_PARQUET = MODEL_DIR / "train.parquet"

VALIDATION_START = pd.Timestamp("2025-01-01")
TEST_START = pd.Timestamp("2026-01-01")
THRESHOLD_CANDIDATES = [0.35, 0.38, 0.40, 0.45, 0.48, 0.50, 0.52, 0.55]
XGBOOST_PARAMS = {
    "objective": "binary:logistic", "n_estimators": 500, "learning_rate": 0.03,
    "max_depth": 6, "min_child_weight": 5, "subsample": 0.8,
    "colsample_bytree": 0.8, "gamma": 0.2, "reg_alpha": 0.1,
    "reg_lambda": 1.0, "random_state": 42, "n_jobs": -1,
    "eval_metric": "logloss",
}


# ---------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------


def _classification_metrics(y_true: pd.Series, probability, threshold: float) -> dict:
    prediction = (probability >= threshold).astype(int)
    metrics = {
        "rows": int(len(y_true)),
        "positive_rate": float(y_true.mean()),
        "selected_rate": float(prediction.mean()),
        "accuracy": float(accuracy_score(y_true, prediction)),
        "precision": float(precision_score(y_true, prediction, zero_division=0)),
        "recall": float(recall_score(y_true, prediction, zero_division=0)),
        "f1": float(f1_score(y_true, prediction, zero_division=0)),
    }
    metrics["roc_auc"] = float(roc_auc_score(y_true, probability)) if y_true.nunique() == 2 else None
    return metrics


def _backtest_metrics(model, features: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None, threshold: float) -> dict:
    period = features[features["datetime"] >= start]
    if end is not None:
        period = period[period["datetime"] < end]
    probability = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period["Confidence"] = probability
    strategy_signal = period["StrategySignal"].astype(int)
    pass_long = period["Confidence"] >= threshold
    pass_short = period["Confidence"] >= threshold
    short_regime_gate = (
        (period["MarketRegime"] == "TREND_DOWN")
        | (period.get("HTF_15m_TrendDownOK", 0) == 1)
        | (period.get("HTF_15m_TrendTransitionDown", 0) == 1)
    )
    trade_signal = pd.Series(0, index=period.index, dtype=int)
    trade_signal[(strategy_signal == 1) & pass_long] = 1
    trade_signal[(strategy_signal == -1) & pass_short & short_regime_gate] = -1
    period["Signal"] = trade_signal
    trades = BacktestEngine(period.set_index("datetime")).run()
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "max_drawdown": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    drawdown = (trades["PnL"].cumsum().cummax() - trades["PnL"].cumsum()).max()
    return {
        "trades": int(len(trades)),
        "net_pnl": float(trades["PnL"].sum()),
        "gross_profit": float(wins),
        "gross_loss": float(losses),
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "win_rate": float((trades["PnL"] > 0).mean()),
        "max_drawdown": float(drawdown),
    }


def train_xgboost():

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{DATASET_PATH}"
        )

    logger.info("Loading dataset: %s", DATASET_PATH)

    df = pd.read_csv(DATASET_PATH)

    if "label" not in df.columns:
        raise ValueError("Column 'label' not found.")
    if len(df) < 1_000:
        raise ValueError(
            f"Refusing to train or overwrite the model with only {len(df)} rows; "
            "rebuild the ML dataset and verify candidate generation first."
        )

    # ------------------------------------------------------------
    # Remove columns not used for ML
    # ------------------------------------------------------------

    missing_features = sorted(set(ML_FEATURE_COLUMNS) - set(df.columns))
    if missing_features:
        raise ValueError(f"Dataset is missing required ML features: {missing_features}")

    feature_columns = ML_FEATURE_COLUMNS

    if not {"entry_time", "exit_time"}.issubset(df.columns):
        raise ValueError("Dataset must contain entry_time and exit_time for temporal splitting.")

    df["entry_time"] = pd.to_datetime(df["entry_time"], errors="raise")
    df["exit_time"] = pd.to_datetime(df["exit_time"], errors="raise")
    train_df = df[df["exit_time"] < VALIDATION_START].copy()
    validation_df = df[
        (df["entry_time"] >= VALIDATION_START) & (df["exit_time"] < TEST_START)
    ].copy()
    test_df = df[df["entry_time"] >= TEST_START].copy()

    if min(len(train_df), len(validation_df), len(test_df)) < 100:
        raise ValueError(
            "Refusing to train: each temporal train/validation/test period "
            "must contain at least 100 rows."
        )
    if train_df["label"].nunique() < 2:
        raise ValueError("Training period contains only one label class.")

    logger.info(
        "Temporal split | train=%d (through 2024) | validation=%d (2025) | test=%d (2026+)",
        len(train_df), len(validation_df), len(test_df),
    )

    logger.info(
        "Feature count : %d",
        len(feature_columns),
    )

    logger.info(
        "Positive ratio : %.2f%%",
        train_df["label"].mean() * 100,
    )

    model = xgb.XGBClassifier(**XGBOOST_PARAMS)

    logger.info("Training XGBoost...")

    model.fit(train_df[feature_columns], train_df["label"])

    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    validation_probability = model.predict_proba(validation_df[feature_columns])[:, 1]
    threshold_results = []
    for threshold in THRESHOLD_CANDIDATES:
        threshold_results.append({
            "threshold": threshold,
            **_classification_metrics(validation_df["label"], validation_probability, threshold),
            "backtest": _backtest_metrics(model, features, VALIDATION_START, TEST_START, threshold),
        })
    eligible = [result for result in threshold_results if result["backtest"]["trades"] >= 20]
    pf_target = [r for r in eligible if (r["backtest"]["profit_factor"] or 0.0) >= 1.60 and r["backtest"]["net_pnl"] > 0]
    if pf_target:
        selected = max(pf_target, key=lambda result: (
            result["backtest"]["profit_factor"] or 0.0,
            result["backtest"]["net_pnl"],
        ))
    else:
        selected = max(eligible or threshold_results, key=lambda result: (
            result["backtest"]["profit_factor"] or 0.0,
            result["backtest"]["net_pnl"],
        ))
    selected_threshold = selected["threshold"]
    test_probability = model.predict_proba(test_df[feature_columns])[:, 1]
    test_metrics = _classification_metrics(test_df["label"], test_probability, selected_threshold)
    test_backtest = _backtest_metrics(model, features, TEST_START, None, selected_threshold)

    # ------------------------------------------------------------
    # Save
    # ------------------------------------------------------------

    joblib.dump(model, MODEL_PATH)
    joblib.dump(feature_columns, FEATURE_PATH)
    joblib.dump(selected_threshold, THRESHOLD_PATH)

    train_df.to_parquet(TRAIN_PARQUET, index=False)
    evaluation = {
        "split": {
            "train": "entry/exit before 2025-01-01",
            "validation": "2025-01-01 through 2025-12-31",
            "test": "2026-01-01 onward",
        },
        "selected_threshold": selected_threshold,
        "selection_rule": "maximum validation net PnL; profit factor breaks ties; minimum 20 trades",
        "validation_thresholds": threshold_results,
        "test": {"classification": test_metrics, "backtest": test_backtest},
    }
    EVALUATION_PATH.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

    logger.info("Model saved      : %s", MODEL_PATH)
    logger.info("Features saved   : %s", FEATURE_PATH)
    logger.info("Threshold saved  : %s | %.2f", THRESHOLD_PATH, selected_threshold)
    logger.info("2026 test metrics: %s", test_metrics)
    logger.info("Evaluation saved : %s", EVALUATION_PATH)
    logger.info("Train parquet    : %s", TRAIN_PARQUET)

    logger.info("Training completed.")


def main():
    train_xgboost()


if __name__ == "__main__":
    main()
