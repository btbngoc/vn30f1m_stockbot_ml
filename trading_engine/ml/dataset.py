import pandas as pd
import numpy as np

class TripleBarrierLabeler:
    def __init__(self, tp_atr_mult=2.0, sl_atr_mult=1.0, time_limit_bars=50):
        self.tp_atr_mult = tp_atr_mult
        self.sl_atr_mult = sl_atr_mult
        self.time_limit_bars = time_limit_bars
        
        self.feature_cols = [
            'TrendScore', 'StructureScore', 'VolumeScore', 'MomentumScore',
            'ATR', 'ADX', 'RSI', 'VWAP_Distance', 'EMA_Distance', 'RVOL',
            'TimeOfDay', 'DayOfWeek'
        ]

    def add_ml_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adds specific ML features to the dataframe before inference or training."""
        df = df.copy()
        
        # Distances
        if 'VWAP' in df.columns:
            df['VWAP_Distance'] = (df['Close'] - df['VWAP']) / df['Close']
        else:
            df['VWAP_Distance'] = 0
            
        if 'EMA50' in df.columns:
            df['EMA_Distance'] = (df['Close'] - df['EMA50']) / df['Close']
        else:
            df['EMA_Distance'] = 0
            
        # Ensure we have a DatetimeIndex for time features
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'datetime' in df.columns:
                df = df.set_index('datetime')
            else:
                raise ValueError('DataFrame index must be DatetimeIndex or contain a "datetime" column')
        # Time features
        df['TimeOfDay'] = df.index.hour + df.index.minute / 60.0
        df['DayOfWeek'] = df.index.dayofweek
        
        # Fill NaNs for safety
        df.fillna(0, inplace=True)
        return df

    def create_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filters for rows where Signal != 0 (Candidates) and applies the Triple Barrier Method.
        Returns a DataFrame ready for training.
        """
        df = self.add_ml_features(df)
        
        candidates = df[df['Signal'] != 0].copy()
        
        records = []
        prices = df[['High', 'Low', 'Close']].values
        times = df.index.values
        
        for idx in candidates.index:
            row = candidates.loc[idx]
            signal = row['Signal']
            entry_price = row['Close']
            atr = row.get('ATR', 0)
            
            # Skip if atr is invalid
            if atr == 0:
                continue
                
            tp_price = entry_price + signal * (self.tp_atr_mult * atr)
            sl_price = entry_price - signal * (self.sl_atr_mult * atr)
            
            # Find integer position of this index in the full dataframe
            pos = df.index.get_loc(idx)

            # The final bars do not have a full observation window.  Keeping
            # them would label an unknown future outcome as TIME.
            if pos + self.time_limit_bars >= len(df):
                continue
            
            exit_price = None
            exit_time = None
            exit_reason = 'TIME'
            label = 0
            
            for forward_idx in range(pos + 1, pos + 1 + self.time_limit_bars):
                high = prices[forward_idx, 0]
                low = prices[forward_idx, 1]
                close = prices[forward_idx, 2]
                curr_time = times[forward_idx]
                
                if signal == 1:
                    if low <= sl_price:
                        exit_price = sl_price
                        exit_reason = 'SL'
                        label = 0
                        exit_time = curr_time
                        break
                    elif high >= tp_price:
                        exit_price = tp_price
                        exit_reason = 'TP'
                        label = 1
                        exit_time = curr_time
                        break
                elif signal == -1:
                    if high >= sl_price:
                        exit_price = sl_price
                        exit_reason = 'SL'
                        label = 0
                        exit_time = curr_time
                        break
                    elif low <= tp_price:
                        exit_price = tp_price
                        exit_reason = 'TP'
                        label = 1
                        exit_time = curr_time
                        break
                        
            if exit_price is None:
                # Time limit hit
                exit_price = prices[min(pos + self.time_limit_bars, len(df)-1), 2]
                exit_time = times[min(pos + self.time_limit_bars, len(df)-1)]
                
            record = {
                'entry_time': idx,
                'entry_price': entry_price,
                'signal': signal,
                'sl': sl_price,
                'tp': tp_price,
                'exit_time': exit_time,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'label': label
            }
            
            for col in self.feature_cols:
                record[col] = row.get(col, 0)
                
            records.append(record)
            
        return pd.DataFrame(records)
