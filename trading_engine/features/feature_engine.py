"""Feature engineering module.

Loads the raw CSV (kept immutable), computes all technical indicators,
applies strategy scores, generates trading signals,
and saves the resulting DataFrame as a Parquet file for fast downstream use.
"""
import os
import pandas as pd

from trading_engine.data.loader_csv import load_raw_csv
from trading_engine.data.indicators import IndicatorEngine
from trading_engine.strategy.trend import TrendStrategy
from trading_engine.strategy.structure import StructureStrategy
from trading_engine.strategy.signal import SignalEngine

def engineer_features():
    """Compute indicators, calculate strategy scores, generate signals, and write to Parquet.
    Returns the engineered DataFrame.
    """
    df = load_raw_csv()
    
    # 1. Compute technical indicators
    df = IndicatorEngine.calculate_all(df)
    
    # 2. Apply strategy scores
    df = TrendStrategy().calculate_scores(df)
    df = StructureStrategy().calculate_scores(df)
    
    # 3. Generate trading signals
    df = SignalEngine().generate_signals(df)
    
    # 4. Save to Parquet
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "VN30F1M_features.parquet"))
    df.to_parquet(out_path)
    print(f"Features saved to {out_path}")
    return df

if __name__ == "__main__":
    engineer_features()
