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

import joblib
import pandas as pd
import xgboost as xgb

from ..logging_config import logger

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

DATASET_PATH = BASE_DIR / "data" / "ml_dataset.csv"

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

MODEL_PATH = MODEL_DIR / "xgboost_model.pkl"
FEATURE_PATH = MODEL_DIR / "feature_columns.pkl"
TRAIN_PARQUET = MODEL_DIR / "train.parquet"


# ---------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------


def train_xgboost():

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found:\n{DATASET_PATH}"
        )

    logger.info("Loading dataset: %s", DATASET_PATH)

    df = pd.read_csv(DATASET_PATH)

    if "label" not in df.columns:
        raise ValueError("Column 'label' not found.")

    # ------------------------------------------------------------
    # Remove columns not used for ML
    # ------------------------------------------------------------

    ignore_columns = {
        "label",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "signal",
        "sl",
        "tp",
        "exit_reason",
    }

    feature_columns = [
        c for c in df.columns
        if c not in ignore_columns
    ]

    X = df[feature_columns]
    y = df["label"]

    logger.info(
        "Training rows : %d",
        len(df),
    )

    logger.info(
        "Feature count : %d",
        len(feature_columns),
    )

    logger.info(
        "Positive ratio : %.2f%%",
        y.mean() * 100,
    )

    params = {
        "objective": "binary:logistic",
        "n_estimators": 500,
        "learning_rate": 0.03,
        "max_depth": 6,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "gamma": 0.2,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "random_state": 42,
        "n_jobs": -1,
        "eval_metric": "logloss",
    }

    model = xgb.XGBClassifier(**params)

    logger.info("Training XGBoost...")

    model.fit(X, y)

    # ------------------------------------------------------------
    # Save
    # ------------------------------------------------------------

    joblib.dump(model, MODEL_PATH)
    joblib.dump(feature_columns, FEATURE_PATH)

    df.to_parquet(TRAIN_PARQUET, index=False)

    logger.info("Model saved      : %s", MODEL_PATH)
    logger.info("Features saved   : %s", FEATURE_PATH)
    logger.info("Train parquet    : %s", TRAIN_PARQUET)

    logger.info("Training completed.")


def main():
    train_xgboost()


if __name__ == "__main__":
    main()