import pandas as pd
import numpy as np

class MetricsCalculator:
    @staticmethod
    def calculate_all(trade_log: pd.DataFrame, initial_capital: float = 100000.0) -> dict:
        if trade_log.empty:
            return {}
            
        metrics = {}
        
        # Basic stats
        total_trades = len(trade_log)
        winning_trades = trade_log[trade_log['PnL'] > 0]
        losing_trades = trade_log[trade_log['PnL'] <= 0]
        
        winrate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        gross_profit = winning_trades['PnL'].sum()
        gross_loss = abs(losing_trades['PnL'].sum())
        net_profit = trade_log['PnL'].sum()
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        avg_win = winning_trades['PnL'].mean() if len(winning_trades) > 0 else 0
        avg_loss = abs(losing_trades['PnL'].mean()) if len(losing_trades) > 0 else 0
        expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)
        
        # Risk Reward Ratio
        rr = avg_win / avg_loss if avg_loss > 0 else float('inf')
        
        # Cumulative Equity & Drawdown
        trade_log['Equity'] = initial_capital + trade_log['PnL'].cumsum()
        trade_log['Peak'] = trade_log['Equity'].cummax()
        trade_log['Drawdown'] = (trade_log['Equity'] - trade_log['Peak']) / trade_log['Peak']
        max_drawdown = abs(trade_log['Drawdown'].min())
        
        metrics = {
            'Total Trades': total_trades,
            'Winrate': round(winrate * 100, 2),
            'Net Profit': round(net_profit, 2),
            'Gross Profit': round(gross_profit, 2),
            'Gross Loss': round(gross_loss, 2),
            'Profit Factor': round(profit_factor, 2),
            'Expectancy': round(expectancy, 2),
            'Risk/Reward Ratio': round(rr, 2),
            'Max Drawdown %': round(max_drawdown * 100, 2)
        }
        
        return metrics
