import pandas as pd
import numpy as np
from .base import BaseStrategy

class StructureStrategy(BaseStrategy):
    def __init__(self, name="StructureStrategy", swing_length=5):
        super().__init__(name)
        # N bars on left, N bars on right to confirm swing
        self.left_bars = swing_length // 2
        self.right_bars = swing_length - self.left_bars - 1
        # For a 5 bar swing: 2 left, 1 center, 2 right
        if self.right_bars < 1: self.right_bars = 1
        if self.left_bars < 1: self.left_bars = 1

    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Initialize columns
        df['SwingHigh'] = np.nan
        df['SwingLow'] = np.nan
        df['StructureScore'] = 0.0
        
        last_sh = None
        last_sl = None
        trend_dir = 0 # 1 for up, -1 for down
        
        # We need to iterate to keep track of the most recent confirmed swings
        # and check for BOS/CHOCH on the current close
        
        highs = df['High'].values
        lows = df['Low'].values
        closes = df['Close'].values
        
        swing_high_col = np.full(len(df), np.nan)
        swing_low_col = np.full(len(df), np.nan)
        score_col = np.zeros(len(df))
        
        for i in range(self.left_bars + self.right_bars, len(df)):
            # 1. Detect Swings (Confirmed at bar i, meaning the swing was at i - right_bars)
            center = i - self.right_bars
            
            # Check Swing High
            is_sh = True
            for j in range(center - self.left_bars, center + self.right_bars + 1):
                if j != center and highs[j] >= highs[center]:
                    is_sh = False
                    break
            
            if is_sh:
                swing_high_col[center] = highs[center]
                last_sh = highs[center]
                
            # Check Swing Low
            is_sl = True
            for j in range(center - self.left_bars, center + self.right_bars + 1):
                if j != center and lows[j] <= lows[center]:
                    is_sl = False
                    break
                    
            if is_sl:
                swing_low_col[center] = lows[center]
                last_sl = lows[center]
                
            # 2. Detect BOS / CHOCH based on current Close
            current_score = 0
            if last_sh is not None and last_sl is not None:
                if trend_dir >= 0: # Uptrend or neutral
                    if closes[i] > last_sh:
                        # Bullish BOS or CHOCH
                        current_score += 30
                        trend_dir = 1
                        last_sh = None # Reset to wait for next swing high
                    elif closes[i] < last_sl:
                        # Bearish CHOCH
                        current_score -= 30
                        trend_dir = -1
                        last_sl = None # Reset to wait for next swing low
                elif trend_dir == -1: # Downtrend
                    if closes[i] < last_sl:
                        # Bearish BOS
                        current_score -= 30
                        trend_dir = -1
                        last_sl = None
                    elif closes[i] > last_sh:
                        # Bullish CHOCH
                        current_score += 30
                        trend_dir = 1
                        last_sh = None
                        
            score_col[i] = current_score
            
        df['SwingHigh'] = swing_high_col
        df['SwingLow'] = swing_low_col
        df['StructureScore'] = score_col
        
        return df
