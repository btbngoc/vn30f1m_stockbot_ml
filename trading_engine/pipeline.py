import argparse
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import joblib
import pandas as pd

# Local imports from the project
from trading_engine.data.update_csv import load_csv
from trading_engine.data.indicators import IndicatorEngine
from trading_engine.strategy.trend import TrendStrategy
from trading_engine.strategy.structure import StructureStrategy
from trading_engine.strategy.signal import SignalEngine
from trading_engine.ml.dataset import TripleBarrierLabeler

# XGBoost import (ensure the package is installed in the environment)
import xgboost as xgb

def ensure_models_dir():
    models_path = os.path.join(os.path.dirname(__file__), "..", "models")
    os.makedirs(models_path, exist_ok=True)
    return os.path.abspath(models_path)

def run_pipeline(mode: str = "train"):
    # 1. Load raw 1‑minute CSV data
    df = load_csv()

    # 2. Compute technical indicators (1‑minute)
    df = IndicatorEngine.calculate_all(df)

    # 3. Apply strategy scores
    df = TrendStrategy().calculate_scores(df)
    df = StructureStrategy().calculate_scores(df)

    # 4. Generate trading signals
    df = SignalEngine().generate_signals(df)

    # 5. Label data with Triple Barrier method (creates a training set)
    labeler = TripleBarrierLabeler()
    labeled_df = labeler.create_dataset(df)

    # Feature columns are defined inside the labeler
    feature_cols = labeler.feature_cols

    models_dir = ensure_models_dir()
    model_path = os.path.join(models_dir, "xgboost_model.pkl")

    if mode == "train":
        # Prepare training data (exclude rows where label == -1 – already filtered by create_dataset)
        X = labeled_df[feature_cols]
        y = labeled_df["label"]

        # Simple XGBoost hyper‑parameters – can be tuned later
        xgb_params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "use_label_encoder": False,
            "n_estimators": 200,
            "learning_rate": 0.05,
            "max_depth": 5,
            "random_state": 42,
        }
        model = xgb.XGBClassifier(**xgb_params)
        model.fit(X, y)
        # Save the trained model
        joblib.dump(model, model_path)
        print(f"XGBoost model saved to {model_path}")
    elif mode == "predict":
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}. Train the model first.")
        model = joblib.load(model_path)
        X = labeled_df[feature_cols]
        # Predict probability of the positive class (label == 1)
        prob = model.predict_proba(X)[:, 1]
        labeled_df["Prediction"] = prob
        print("Predictions added to the dataframe.")
    else:
        raise ValueError("Mode must be either 'train' or 'predict'.")

    # Save the final dataframe (including predictions if any) for inspection
    output_path = os.path.abspath(os.path.join(models_dir, "processed_output.csv"))
    labeled_df.to_csv(output_path, index=False)
    print(f"Processed data saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the trading‑engine data pipeline.")
    parser.add_argument(
        "--mode",
        choices=["train", "predict"],
        default="train",
        help="Operation mode: 'train' builds a new XGBoost model, 'predict' loads an existing model and adds predictions.",
    )
    args = parser.parse_args()
    run_pipeline(mode=args.mode)
