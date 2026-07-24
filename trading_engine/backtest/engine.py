import pandas as pd
from .metrics import MetricsCalculator

class BacktestEngine:
    def __init__(self, df: pd.DataFrame, risk_engine=None, initial_capital=100000000.0): # Use 100M VND default
        self.df = df
        self.risk_engine = risk_engine
        self.initial_capital = initial_capital
        self.trade_log = []
        
    def run(self):
        current_position = 0 # 1 for Long, -1 for Short, 0 for None
        entry_price = 0
        entry_date = None
        contracts = 0
        sl_price = 0
        initial_sl_price = 0
        tp_price = 0
        trailing_offset = 0
        
        current_equity = self.initial_capital
        
        for index, row in self.df.iterrows():
            signal = row.get('Signal', 0)
            close = row['Close']
            high = row['High']
            low = row['Low']
            atr = row.get('ATR', 0)
            
            # 1. Manage Open Positions (Check SL/TP before checking for new signals)
            if current_position != 0:
                exit_price = None
                exit_reason = ""
                
                # Update Trailing Stop
                if self.risk_engine is not None and trailing_offset > 0:
                    if current_position == 1:
                        new_sl = close - trailing_offset
                        if new_sl > sl_price:
                            sl_price = new_sl
                    elif current_position == -1:
                        new_sl = close + trailing_offset
                        if new_sl < sl_price:
                            sl_price = new_sl
                
                # Check Intrabar SL / TP
                if current_position == 1:
                    if sl_price > 0 and low <= sl_price:
                        exit_price = sl_price
                        exit_reason = "SL"
                    elif tp_price > 0 and high >= tp_price:
                        exit_price = tp_price
                        exit_reason = "TP"
                    elif signal == -1:
                        exit_price = close
                        exit_reason = "Reversal"
                elif current_position == -1:
                    if sl_price > 0 and high >= sl_price:
                        exit_price = sl_price
                        exit_reason = "SL"
                    elif tp_price > 0 and low <= tp_price:
                        exit_price = tp_price
                        exit_reason = "TP"
                    elif signal == 1:
                        exit_price = close
                        exit_reason = "Reversal"
                        
                # Process Exit
                if exit_price is not None:
                    point_diff = (exit_price - entry_price) if current_position == 1 else (entry_price - exit_price)
                    multiplier = self.risk_engine.point_multiplier if self.risk_engine else 100000
                    pnl = point_diff * contracts * multiplier
                    
                    self.trade_log.append({
                        'Entry Date': entry_date,
                        'Exit Date': index,
                        'Type': 'LONG' if current_position == 1 else 'SHORT',
                        'Entry': entry_price,
                        'Exit': exit_price,
                        'Contracts': contracts,
                        'PnL': pnl,
                        'Reason': exit_reason,
                        'Initial Stop Loss': initial_sl_price,
                        'Stop Loss at Exit': sl_price,
                        'Take Profit': tp_price,
                    })
                    
                    current_equity += pnl
                    current_position = 0
                    
                    # If exited due to SL/TP, we might want to prevent re-entry on the same bar.
                    # In this simple event loop, we'll just continue to the next bar if we hit SL/TP.
                    if exit_reason in ["SL", "TP"]:
                        continue

            # 2. Enter New Positions
            if current_position == 0 and signal != 0:
                current_position = signal
                entry_price = close
                entry_date = index
                
                if self.risk_engine is not None and atr > 0:
                    params = self.risk_engine.calculate_trade_parameters(entry_price, atr, current_position, current_equity)
                    contracts = params.get('contracts', 1)
                    sl_price = params.get('initial_sl', 0)
                    initial_sl_price = sl_price
                    tp_price = params.get('tp_price', 0)
                    trailing_offset = params.get('trailing_offset', 0)
                else:
                    contracts = 1
                    sl_price = 0
                    initial_sl_price = 0
                    tp_price = 0
                    trailing_offset = 0

        # Close open positions at the end of the data
        if current_position != 0:
            last_idx = self.df.index[-1]
            last_close = self.df.iloc[-1]['Close']
            point_diff = (last_close - entry_price) if current_position == 1 else (entry_price - last_close)
            multiplier = self.risk_engine.point_multiplier if self.risk_engine else 100000
            pnl = point_diff * contracts * multiplier
            
            self.trade_log.append({
                'Entry Date': entry_date,
                'Exit Date': last_idx,
                'Type': 'LONG' if current_position == 1 else 'SHORT',
                'Entry': entry_price,
                'Exit': last_close,
                'Contracts': contracts,
                'PnL': pnl,
                'Reason': 'End of Data',
                'Initial Stop Loss': initial_sl_price,
                'Stop Loss at Exit': sl_price,
                'Take Profit': tp_price,
            })
            
        return pd.DataFrame(self.trade_log)

    def get_metrics(self):
        log_df = pd.DataFrame(self.trade_log)
        return MetricsCalculator.calculate_all(log_df, self.initial_capital)
