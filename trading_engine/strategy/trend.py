import pandas as pd
from .base import BaseStrategy

class TrendStrategy(BaseStrategy):
    def __init__(self, name="TrendStrategy"):
        super().__init__(name)
        
    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates TrendScore based on EMA and VWAP.
        """
        df = df.copy()
        
        # Initialize scores
        df['TrendScore'] = 0
        df['TrendScore'] = df['TrendScore'].astype(float)
        
        # Rule 1: EMA20 > EMA50 (+20 points), EMA20 < EMA50 (-20 points)
        df.loc[df['EMA20'] > df['EMA50'], 'TrendScore'] += 20
        df.loc[df['EMA20'] < df['EMA50'], 'TrendScore'] -= 20
        
        # Rule 2: EMA50 > EMA200 (+20 points), EMA50 < EMA200 (-20 points)
        df.loc[df['EMA50'] > df['EMA200'], 'TrendScore'] += 20
        df.loc[df['EMA50'] < df['EMA200'], 'TrendScore'] -= 20
        
        # Rule 3: Close > VWAP (+20 points), Close < VWAP (-20 points)
        df.loc[df['Close'] > df['VWAP'], 'TrendScore'] += 20
        df.loc[df['Close'] < df['VWAP'], 'TrendScore'] -= 20
        
        # Basic Volume/Momentum for V1 placeholder
        df['VolumeScore'] = 0.0
        df.loc[df['RVOL'] > 1.5, 'VolumeScore'] += 20
        
        df['MomentumScore'] = 0.0
        df.loc[df['RSI'] > 55, 'MomentumScore'] += 10
        df.loc[df['RSI'] < 45, 'MomentumScore'] -= 10
        
        # Structure score placeholder
        df['StructureScore'] = 0.0
        
        return df
