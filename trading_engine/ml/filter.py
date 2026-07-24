import pandas as pd
from .model import MLWrapper

class MLFilter:
    def __init__(self, threshold=0.6, model_path="models/lgbm_model.pkl"):
        self.threshold = threshold
        self.model_wrapper = MLWrapper(model_path)
        self.is_loaded = self.model_wrapper.load_model()
        
        self.feature_cols = [
            'TrendScore', 'StructureScore', 'VolumeScore', 'MomentumScore',
            'ATR', 'ADX', 'RSI', 'VWAP_Distance', 'EMA_Distance', 'RVOL',
            'TimeOfDay', 'DayOfWeek'
        ]

    def filter_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if not self.is_loaded:
            print("[MLFilter] Model not found. Skipping ML filtering.")
            return df
            
        # Ensure features exist
        # Distances
        if 'VWAP_Distance' not in df.columns:
            df['VWAP_Distance'] = (df['Close'] - df.get('VWAP', df['Close'])) / df['Close']
        if 'EMA_Distance' not in df.columns:
            df['EMA_Distance'] = (df['Close'] - df.get('EMA50', df['Close'])) / df['Close']
        if 'TimeOfDay' not in df.columns:
            df['TimeOfDay'] = df.index.hour + df.index.minute / 60.0
        if 'DayOfWeek' not in df.columns:
            df['DayOfWeek'] = df.index.dayofweek
            
        df.fillna(0, inplace=True)
        
        # We only predict where Signal != 0
        signal_mask = df['Signal'] != 0
        if not signal_mask.any():
            return df
            
        X_infer = df.loc[signal_mask, self.feature_cols]
        probs = self.model_wrapper.predict_proba(X_infer)
        
        # Override signals that don't meet the threshold
        # Create a boolean mask of which signals to KEEP
        keep_mask = probs >= self.threshold
        
        # Where signal is not kept, set it to 0
        # df.loc[signal_mask, 'Signal'] uses a subset, we have to align indices
        indices_to_update = X_infer.index[~keep_mask]
        df.loc[indices_to_update, 'Signal'] = 0
        
        print(f"[MLFilter] Filtered out {len(indices_to_update)} / {len(X_infer)} signals.")
        return df
