"""
Prediction script for the trained XGBoost model.

Input:
    trading_engine/data/VN30F1M_features.parquet

Output:
    trading_engine/data/prediction.parquet

prediction.parquet contains only:
    - datetime
    - Signal
    - Confidence
"""

from pathlib import Path
import joblib
import pandas as pd

from ..logging_config import logger

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
MODEL_PATH = BASE_DIR / "models" / "xgboost_model.pkl"
OUTPUT_PATH = BASE_DIR / "data" / "prediction.parquet"

# các cột KHÔNG dùng làm feature
EXCLUDE_COLUMNS = {
    "datetime",
    "Signal",
    "Confidence",
    "Prediction",
    "Label",
}


def predict() -> None:

    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Feature file not found:\n{FEATURES_PATH}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found:\n{MODEL_PATH}")

    logger.info("Loading feature dataset...")
    features = pd.read_parquet(FEATURES_PATH)

    if "datetime" not in features.columns:
        raise ValueError("Column 'datetime' not found in feature parquet.")

    logger.info("Loading XGBoost model...")
    model = joblib.load(MODEL_PATH)

    feature_cols = [
        c for c in features.columns
        if c not in EXCLUDE_COLUMNS
    ]

    X = features[feature_cols]

    logger.info("Predicting %d rows...", len(X))

    predictions = model.predict(X)

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(X)

        # binary model -> probability của class 1
        if probabilities.shape[1] == 2:
            confidence = probabilities[:, 1]
        else:
            confidence = probabilities.max(axis=1)

    else:
        confidence = [0.5] * len(X)

    prediction_df = pd.DataFrame({
        "datetime": features["datetime"],
        "Signal": predictions,
        "Confidence": confidence,
    })

    prediction_df.to_parquet(
        OUTPUT_PATH,
        index=False,
    )

    logger.info("Prediction saved to %s", OUTPUT_PATH)

    logger.info(
        "Prediction summary | rows=%d | Signal=1:%d | Signal=0:%d",
        len(prediction_df),
        (prediction_df.Signal == 1).sum(),
        (prediction_df.Signal == 0).sum(),
    )


def main():
    predict()


if __name__ == "__main__":
    main()