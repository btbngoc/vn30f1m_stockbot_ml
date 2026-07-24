import argparse

from trading_engine.data.vci_api import fetch_vn30f1m_daily
from trading_engine.data.indicators import IndicatorEngine
from trading_engine.strategy.trend import TrendStrategy
from trading_engine.strategy.structure import StructureStrategy
from trading_engine.strategy.signal import SignalEngine
from trading_engine.ml.dataset import TripleBarrierLabeler
from trading_engine.ml.model import MLWrapper

def parse_args():
    parser = argparse.ArgumentParser(description="Build and train the VN30F1M ML model.")
    parser.add_argument("--days", type=int, default=2000, help="Number of daily bars to request.")
    parser.add_argument("--dataset-path", default="ml_dataset_debug.csv", help="Output CSV path.")
    return parser.parse_args()


def main():
    args = parse_args()
    print("--- Generating ML Dataset ---")
    
    # 1. Load Data
    print("Loading data from VCI API...")
    df = fetch_vn30f1m_daily(days=args.days)
    print(f"Loaded {len(df)} candles.")
    
    if df.empty:
        print("Data is empty. Exiting.")
        return
        
    # 2. Calculate Indicators & Strategies
    print("Calculating indicators...")
    df = IndicatorEngine.calculate_all(df)
    
    print("Applying Strategies...")
    df = TrendStrategy().calculate_scores(df)
    df = StructureStrategy().calculate_scores(df)
    
    # Generate all signals (we lower thresholds to get more candidates)
    # The normal threshold was 40. We can keep it 40 or lower it for more data.
    signal_engine = SignalEngine(buy_threshold=40, sell_threshold=-40)
    df = signal_engine.generate_signals(df)
    
    num_candidates = (df['Signal'] != 0).sum()
    print(f"Found {num_candidates} raw candidates for labeling.")
    
    # 3. Label Dataset
    print("Applying Triple Barrier Labeling...")
    labeler = TripleBarrierLabeler(tp_atr_mult=2.0, sl_atr_mult=1.0, time_limit_bars=50)
    dataset = labeler.create_dataset(df)
    
    print(f"Dataset generated. Shape: {dataset.shape}")
    if dataset.empty:
        print("No labelable candidates were generated. Exiting without replacing the model.")
        return
    print(dataset['label'].value_counts(dropna=False))
    
    # Save dataset for inspection
    dataset.to_csv(args.dataset_path, index=False)
    
    # 4. Train Model
    print("--- Training ML Model ---")
    wrapper = MLWrapper()
    wrapper.train(dataset, labeler.feature_cols, purge_bars=labeler.time_limit_bars)

if __name__ == "__main__":
    main()
