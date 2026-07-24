"""Data loader module for the trading engine.

Provides a simple wrapper around the CSV logic to load the raw historical data
without modifying it. This module is used by other pipeline stages to obtain a clean DataFrame.
"""
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "data" / "VN30F1M_since20180501.csv"

def load_base_csv() -> pd.DataFrame:
    """Load the raw CSV and create the datetime column."""
    df = pd.read_csv(CSV_PATH)
    
    # Combine date + time
    df["datetime"] = pd.to_datetime(
        df["date"].astype(str) + " " + df["time"].astype(str),
        format="%d/%m/%Y %H:%M:%S",
        errors="coerce",
    )
    return df

def load_raw_csv() -> pd.DataFrame:
    """Load the raw 1-minute CSV data.

    Returns:
        pd.DataFrame: DataFrame with a proper datetime index and capitalized OHLCV columns.
    """
    df = load_base_csv()
    
    # Rename OHLCV columns to match IndicatorEngine expectations (capitalized)
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume',
    })
    
    # Ensure the datetime column is set as the index for downstream processing.
    # We drop rows with NaT datetime if any conversion failed.
    df = df.dropna(subset=['datetime'])
    df = df.set_index('datetime')
    return df
