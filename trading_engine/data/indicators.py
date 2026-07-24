import pandas as pd
import pandas_ta as ta
from ..strategy.trend import TrendStrategy

class IndicatorEngine:
    """
    Computes technical indicators without generating trading signals.
    """
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Moving Averages
        df['EMA20'] = ta.ema(df['Close'], length=20)
        df['EMA50'] = ta.ema(df['Close'], length=50)
        df['EMA200'] = ta.ema(df['Close'], length=200)
        
        # VWAP
        df['VWAP'] = ta.vwap(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'])
        
        # Volatility / Risk
        df['ATR'] = ta.atr(high=df['High'], low=df['Low'], close=df['Close'], length=14)
        
        # Momentum
        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_Signal'] = macd['MACDs_12_26_9']
            df['MACD_Hist'] = macd['MACDh_12_26_9']
            
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # Bollinger Bands
        bb = ta.bbands(df['Close'], length=20, std=2)
        if bb is not None:
            df['BB_Lower'] = bb.iloc[:, 0]
            df['BB_Mid'] = bb.iloc[:, 1]
            df['BB_Upper'] = bb.iloc[:, 2]
            
        # Trend Strength
        adx = ta.adx(high=df['High'], low=df['Low'], close=df['Close'], length=14)
        if adx is not None:
            df['ADX'] = adx['ADX_14']
            
        # Volume
        df['Volume_MA20'] = ta.sma(df['Volume'], length=20)
        df['RVOL'] = df['Volume'] / df['Volume_MA20']
        
        return df

from .loader_csv import load_raw_csv
from ..logging_config import logger
from pathlib import Path


def main():
    """
    Generate master feature dataset (VN30F1M_features.parquet).
    """

    logger.info("Loading raw CSV data for indicator generation.")

    raw_df = load_raw_csv()

    logger.info("Calculating technical indicators.")

    features_df = IndicatorEngine.calculate_all(raw_df)

    logger.info("Calculating strategy scores.")

    features_df = TrendStrategy().calculate_scores(features_df)

    output_path = (
        Path(__file__).resolve().parents[2]
        / "trading_engine"
        / "data"
        / "VN30F1M_features.parquet"
    )

    features_df.to_parquet(
        output_path,
        index=False,
    )

    logger.info(
        "Features parquet written to %s",
        output_path,
    )


    

if __name__ == "__main__":
    main()
