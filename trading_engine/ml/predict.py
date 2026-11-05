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
from uuid import uuid4
import joblib
import pandas as pd

from ..logging_config import logger
from .schema import ML_FEATURE_COLUMNS

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
MODEL_PATH = BASE_DIR / "models" / "xgboost_model.pkl"
FEATURE_PATH = BASE_DIR / "models" / "feature_columns.pkl"
THRESHOLD_PATH = BASE_DIR / "models" / "confidence_threshold.pkl"
OUTPUT_PATH = BASE_DIR / "data" / "prediction.parquet"

def predict() -> None:

    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Feature file not found:\n{FEATURES_PATH}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found:\n{MODEL_PATH}")

    logger.info("Loading feature dataset...")
    features = pd.read_parquet(FEATURES_PATH)

    if "datetime" not in features.columns:
        raise ValueError("Column 'datetime' not found in feature parquet.")
    if "StrategySignal" not in features.columns:
        raise ValueError("Column 'StrategySignal' not found in feature parquet.")

    logger.info("Loading XGBoost model...")
    model = joblib.load(MODEL_PATH)

    if FEATURE_PATH.exists():
        feature_cols = joblib.load(FEATURE_PATH)
    else:
        # Compatibility with models created before feature_columns.pkl existed.
        feature_cols = model.get_booster().feature_names or ML_FEATURE_COLUMNS

    missing_features = sorted(set(feature_cols) - set(features.columns))
    if missing_features:
        raise ValueError(f"Feature parquet is missing model features: {missing_features}")

    X = features[feature_cols]

    logger.info("Predicting %d rows...", len(X))

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(X)

        # binary model -> probability của class 1
        if probabilities.shape[1] == 2:
            confidence = probabilities[:, 1]
        else:
            confidence = probabilities.max(axis=1)

    else:
        confidence = [0.5] * len(X)

    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError(
            f"Confidence threshold file missing at {THRESHOLD_PATH}. "
            "Refusing to execute with silent fallback threshold. Ensure confidence_threshold.pkl exists."
        )
    confidence_threshold = float(joblib.load(THRESHOLD_PATH))

    # The classifier estimates whether a strategy candidate will succeed; it
    # does not decide Long versus Short. Preserve that direction from the
    # score-based strategy and set rejected candidates to Hold.
    strategy_signal = features["StrategySignal"].astype(int)
    pass_long = pd.Series(confidence, index=features.index).ge(confidence_threshold)
    pass_short = pd.Series(confidence, index=features.index).ge(confidence_threshold)
    short_regime_gate = (
        (features["MarketRegime"] == "TREND_DOWN")
        | (features["HTF_15m_TrendDownOK"] == 1)
        | (features["HTF_15m_TrendTransitionDown"] == 1)
    )

    trade_signal = pd.Series(0, index=features.index, dtype=int)
    trade_signal[(strategy_signal == 1) & pass_long] = 1
    trade_signal[(strategy_signal == -1) & pass_short & short_regime_gate] = -1




    prediction_df = pd.DataFrame({
        "datetime": features["datetime"],
        "Signal": trade_signal,
        "Confidence": confidence,
    })

    temp_path = OUTPUT_PATH.with_name(
        f".{OUTPUT_PATH.stem}.{uuid4().hex}.tmp{OUTPUT_PATH.suffix}"
    )
    try:
        prediction_df.to_parquet(temp_path, index=False)
        temp_path.replace(OUTPUT_PATH)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    logger.info("Prediction saved to %s", OUTPUT_PATH)
    logger.info("Confidence threshold: %.2f", confidence_threshold)

    logger.info(
        "Prediction summary | rows=%d | Long:%d | Short:%d | Hold:%d",
        len(prediction_df),
        (prediction_df.Signal == 1).sum(),
        (prediction_df.Signal == -1).sum(),
        (prediction_df.Signal == 0).sum(),
    )


def main():
    predict()


if __name__ == "__main__":
    main()
