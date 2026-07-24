import argparse
import os
from pathlib import Path
import pandas as pd

# Central logger
from ..logging_config import logger

# Backtest engine
from .engine import BacktestEngine

def main():
    parser = argparse.ArgumentParser(description="Run backtest on prediction parquet.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    prediction_path = project_root / "trading_engine" / "data" / "prediction.parquet"
    logger.info("Loading prediction data from %s", prediction_path)

    if not prediction_path.exists():
        logger.error("Prediction parquet not found at %s", prediction_path)
        raise FileNotFoundError(f"Prediction file not found at {prediction_path}")

    # Load features and merge with predictions
    features_path = project_root / "trading_engine" / "data" / "VN30F1M_features.parquet"
    logger.info("Loading features data from %s", features_path)
    if not features_path.exists():
        logger.error("Features parquet not found at %s", features_path)
        raise FileNotFoundError(f"Features file not found at {features_path}")

    features_df = pd.read_parquet(features_path)

    prediction_df = pd.read_parquet(prediction_path)

    # Ensure datetime column for merge
    if 'datetime' not in prediction_df.columns:
        prediction_df = prediction_df.reset_index()
    if 'datetime' not in features_df.columns:
        features_df = features_df.reset_index()
    # Merge on datetime
    merged_df = pd.merge(features_df, prediction_df, on='datetime', how='inner')
    logger.info("Merged dataset has %d rows", len(merged_df))

    engine = BacktestEngine(merged_df)
    trades_df = engine.run()

    output_path = project_root / "trading_engine" / "data" / "backtest_trades.csv"
    os.makedirs(output_path.parent, exist_ok=True)
    trades_df.to_csv(output_path, index=False)
    logger.info("Backtest completed. Trades saved to %s", output_path)
    logger.info("Number of trades: %d", len(trades_df))

if __name__ == "__main__":
    main()
