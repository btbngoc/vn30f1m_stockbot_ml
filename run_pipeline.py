import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Imports for pipeline steps
from trading_engine.data.update_csv import main as update_csv_main
from trading_engine.data.indicators import main as indicators_main
from trading_engine.ml.predict import main as predict_main
from trading_engine.backtest.__main__ import main as backtest_main
from trading_engine.analysis import main as analysis_main
from trading_engine.visualize.__main__ import main as visualize_main
from trading_engine.report.report import main as report_main
# Training step (optional)
from trading_engine.ml.train import train_xgboost as train_main
from trading_engine.ml.predict import main as predict_main

def run_daily():
    """Execute the daily pipeline: update data, generate features, predict, backtest, analysis, and visualization."""
    update_csv_main()
    indicators_main()
    predict_main()
    backtest_main()
    analysis_main()
    visualize_main()
    report_main()

def run_retrain():
    """Execute the full retrain pipeline: update data, generate features, train model, predict, backtest, analysis, and visualization."""
    update_csv_main()
    indicators_main()
    train_main()
    predict_main()
    backtest_main()
    analysis_main()
    visualize_main()
    report_main()

def main():
    parser = argparse.ArgumentParser(description="Run the VN30F1M stock bot pipeline.")
    parser.add_argument(
        "--mode",
        choices=["daily", "retrain"],
        required=True,
        help="Pipeline mode: 'daily' runs the standard daily workflow, 'retrain' also retrains the model.",
    )
    args = parser.parse_args()

    if args.mode == "daily":
        run_daily()
    elif args.mode == "retrain":
        run_retrain()
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")

if __name__ == "__main__":
    main()
