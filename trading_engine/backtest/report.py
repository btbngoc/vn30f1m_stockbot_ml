import os
import json
import matplotlib.pyplot as plt
import pandas as pd

class ReportGenerator:
    def __init__(self, results_dir="results"):
        self.results_dir = results_dir
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
            
    def generate(self, run_name: str, trade_log: pd.DataFrame, metrics: dict, price_data: pd.DataFrame | None = None):
        run_dir = os.path.join(self.results_dir, run_name)
        if not os.path.exists(run_dir):
            os.makedirs(run_dir)
            
        # 1. Save Trade Log
        if not trade_log.empty:
            trade_log.to_csv(os.path.join(run_dir, 'trade_log.csv'), index=False)
            
        # 2. Save Summary JSON
        with open(os.path.join(run_dir, 'summary.json'), 'w') as f:
            json.dump(metrics, f, indent=4)
            
        # 3. Generate Equity Curve
        if not trade_log.empty:
            trade_log['Cumulative_PnL'] = trade_log['PnL'].cumsum()
            plt.figure(figsize=(10, 6))
            plt.plot(range(len(trade_log)), trade_log['Cumulative_PnL'], label='Cumulative PnL', color='blue')
            plt.title("Equity Curve (Cumulative PnL)")
            plt.xlabel("Trade Number")
            plt.ylabel("PnL")
            plt.grid(True)
            plt.savefig(os.path.join(run_dir, 'equity.png'))
            plt.close()

        # 4. Generate price chart with entries, exits, stop-losses and targets.
        if price_data is not None and not price_data.empty and not trade_log.empty:
            self._plot_trade_chart(price_data, trade_log, os.path.join(run_dir, 'trade_chart.png'))
            
        print(f"Report generated at: {run_dir}")

    @staticmethod
    def _plot_trade_chart(price_data: pd.DataFrame, trade_log: pd.DataFrame, output_path: str):
        """Plot the close series and annotate every completed backtest trade."""
        prices = price_data.copy()
        prices.index = pd.to_datetime(prices.index)
        prices = prices.sort_index()

        fig, ax = plt.subplots(figsize=(16, 8))
        ax.plot(prices.index, prices['Close'], color='#1f2937', linewidth=1.2, label='Close')

        entries = trade_log.copy()
        entries['Entry Date'] = pd.to_datetime(entries['Entry Date'])
        entries['Exit Date'] = pd.to_datetime(entries['Exit Date'])

        for _, trade in entries.iterrows():
            entry_date, exit_date = trade['Entry Date'], trade['Exit Date']
            is_long = trade['Type'] == 'LONG'
            entry_color = '#16a34a' if is_long else '#dc2626'
            marker = '^' if is_long else 'v'

            ax.scatter(entry_date, trade['Entry'], marker=marker, s=90, color=entry_color, zorder=4)
            exit_color = '#16a34a' if trade['PnL'] >= 0 else '#dc2626'
            ax.scatter(exit_date, trade['Exit'], marker='X', s=70, color=exit_color, zorder=4)

            initial_sl = trade.get('Initial Stop Loss', trade.get('Stop Loss at Exit', 0))
            final_sl = trade.get('Stop Loss at Exit', initial_sl)
            target = trade.get('Take Profit', 0)
            if pd.notna(initial_sl) and initial_sl > 0:
                ax.hlines(initial_sl, entry_date, exit_date, colors='#ef4444', linestyles='--', linewidth=1)
            if pd.notna(target) and target > 0:
                ax.hlines(target, entry_date, exit_date, colors='#2563eb', linestyles='--', linewidth=1)
            if trade['Reason'] == 'SL' and pd.notna(final_sl) and final_sl > 0:
                ax.scatter(exit_date, final_sl, marker='s', s=36, color='#ef4444', zorder=5)

        # Legend entries are added independently so repeated trade markers remain readable.
        ax.scatter([], [], marker='^', s=75, color='#16a34a', label='Long entry')
        ax.scatter([], [], marker='v', s=75, color='#dc2626', label='Short entry')
        ax.scatter([], [], marker='X', s=60, color='#16a34a', label='Profitable exit')
        ax.scatter([], [], marker='X', s=60, color='#dc2626', label='Losing exit')
        ax.plot([], [], '--', color='#ef4444', label='Stop loss')
        ax.plot([], [], '--', color='#2563eb', label='Take profit')
        ax.set_title('VN30F1M trade validation chart')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.grid(True, alpha=0.25)
        ax.legend(loc='best', ncol=3)
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
