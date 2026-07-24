import pandas as pd

class SignalEngine:
    def __init__(self, buy_threshold=40, sell_threshold=-40):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Total Score
        df['TotalScore'] = (
            df.get('TrendScore', 0) + 
            df.get('StructureScore', 0) + 
            df.get('MomentumScore', 0) + 
            df.get('VolumeScore', 0)
        )
        
        # Generate Signals: 1 for Buy, -1 for Sell, 0 for Hold
        df['Signal'] = 0
        df.loc[df['TotalScore'] >= self.buy_threshold, 'Signal'] = 1
        df.loc[df['TotalScore'] <= self.sell_threshold, 'Signal'] = -1
        
        return df
