import os
import json
from pathlib import Path
import pandas as pd
import numpy as np

# Central logger
from .logging_config import logger


from pathlib import Path

import pandas as pd


def load_trades() -> pd.DataFrame:
    trades_path = Path(__file__).resolve().parent / "data" / "backtest_trades.csv"

    if not trades_path.exists():
        print(f"Trade file not found: {trades_path}")
        return pd.DataFrame()

    if trades_path.stat().st_size == 0:
        print("Backtest produced no trades. Analysis skipped.")
        return pd.DataFrame()

    try:
        df = pd.read_csv(trades_path)
    except pd.errors.EmptyDataError:
        print("Trade file is empty. Analysis skipped.")
        return pd.DataFrame()
    for column in ("Entry Date", "Exit Date"):
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="raise")
    return df


def compute_metrics(df: pd.DataFrame):
    """Calculate the collection of metrics required for analysis.

    Returns a tuple (summary_dict, rolling_winrate_series, rolling_dd_series).
    """
    # Basic counts
    total_trades = len(df)
    long_trades = (df.get('Type') == 'LONG').sum()
    short_trades = (df.get('Type') == 'SHORT').sum()

    # Win / loss classification
    wins = df[df['PnL'] > 0]
    losses = df[df['PnL'] <= 0]
    winrate = wins.shape[0] / total_trades * 100 if total_trades > 0 else 0.0

    gross_profit = wins['PnL'].sum()
    gross_loss = -losses['PnL'].sum()  # make positive
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_profit = df['PnL'].sum()

    avg_win = wins['PnL'].mean() if not wins.empty else 0.0
    avg_loss = losses['PnL'].mean() if not losses.empty else 0.0
    largest_win = wins['PnL'].max() if not wins.empty else 0.0
    largest_loss = losses['PnL'].min() if not losses.empty else 0.0

    expectancy = (avg_win * (winrate / 100)) + (avg_loss * (1 - winrate / 100))

    # Drawdown calculations
    cumulative = df['PnL'].cumsum()
    peak = cumulative.cummax()
    drawdown = peak - cumulative
    max_dd = drawdown.max()
    recovery_factor = net_profit / max_dd if max_dd != 0 else float('inf')

    # SQN – System Quality Number
    pnl_std = df['PnL'].std(ddof=0)
    sqn = (df['PnL'].mean() / pnl_std) * np.sqrt(total_trades) if pnl_std != 0 else float('inf')

    # Kelly criterion (percentage of capital)
    if avg_win != 0:
        kelly = (winrate / 100) - ((1 - winrate / 100) * (abs(avg_loss) / avg_win))
        kelly_pct = max(kelly, 0) * 100
    else:
        kelly_pct = 0.0

    # Max consecutive wins / losses
    outcome_series = df['PnL'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    max_consec_wins = max_consec_losses = 0
    cur_win = cur_loss = 0
    for val in outcome_series:
        if val == 1:
            cur_win += 1
            max_consec_wins = max(max_consec_wins, cur_win)
            cur_loss = 0
        elif val == -1:
            cur_loss += 1
            max_consec_losses = max(max_consec_losses, cur_loss)
            cur_win = 0
        else:
            cur_win = cur_loss = 0

    # Holding time statistics (in minutes)
    if {'Entry Date', 'Exit Date'}.issubset(df.columns):
        holding = (df['Exit Date'] - df['Entry Date']).dt.total_seconds() / 60.0
        avg_holding = holding.mean()
        median_holding = holding.median()
    else:
        avg_holding = median_holding = 0.0

    # Profit by hour (using entry time)
    if 'Entry Date' in df.columns:
        df['hour'] = df['Entry Date'].dt.hour
        profit_by_hour = df.groupby('hour')['PnL'].sum().to_dict()
        df.drop(columns=['hour'], inplace=True)
    else:
        profit_by_hour = {}

    # Profit by weekday (0=Mon)
    if 'Entry Date' in df.columns:
        df['weekday'] = df['Entry Date'].dt.weekday
        profit_by_weekday = df.groupby('weekday')['PnL'].sum().to_dict()
        df.drop(columns=['weekday'], inplace=True)
    else:
        profit_by_weekday = {}

    # PnL distribution – quantiles for insight
    pnl_distribution = {
        'min': df['PnL'].min(),
        'q10': df['PnL'].quantile(0.10),
        'q25': df['PnL'].quantile(0.25),
        'median': df['PnL'].median(),
        'q75': df['PnL'].quantile(0.75),
        'q90': df['PnL'].quantile(0.90),
        'max': df['PnL'].max()
    }

    # Rolling winrate (window = 20 trades)
    rolling_win = df['PnL'].gt(0).rolling(window=20, min_periods=1).mean() * 100
    # Rolling drawdown (window = 20 trades)
    rolling_dd = (
        df['PnL'].rolling(window=20, min_periods=1).apply(
            lambda x: (np.maximum.accumulate(np.cumsum(x)) - np.cumsum(x)).max(), raw=False
        )
    )

    summary = {
        'Total Trades': total_trades,
        'Long Trades': int(long_trades),
        'Short Trades': int(short_trades),
        'Winrate': round(winrate, 2),
        'Profit Factor': round(profit_factor, 4) if np.isfinite(profit_factor) else None,
        'Net Profit': round(net_profit, 2),
        'Gross Profit': round(gross_profit, 2),
        'Gross Loss': round(gross_loss, 2),
        'Average Win': round(avg_win, 2),
        'Average Loss': round(avg_loss, 2),
        'Largest Win': round(largest_win, 2),
        'Largest Loss': round(largest_loss, 2),
        'Expectancy': round(expectancy, 4),
        'Recovery Factor': round(recovery_factor, 4) if np.isfinite(recovery_factor) else None,
        'SQN': round(sqn, 4) if np.isfinite(sqn) else None,
        'Kelly %': round(kelly_pct, 2),
        'Max Drawdown': round(max_dd, 2),
        'Max Consecutive Wins': max_consec_wins,
        'Max Consecutive Losses': max_consec_losses,
        'Average Holding Time (min)': round(avg_holding, 2),
        'Median Holding Time (min)': round(median_holding, 2),
        'Profit by Hour': profit_by_hour,
        'Profit by Weekday': profit_by_weekday,
        'PnL Distribution': pnl_distribution
    }

    return summary, rolling_win.tolist(), rolling_dd.tolist()


def save_outputs(summary: dict, rolling_win: list, rolling_dd: list):
    project_root = Path(__file__).resolve().parents[1]
    csv_path = project_root / "trading_engine" / "data" / "analysis.csv"
    # Flatten nested dicts for CSV
    flat = summary.copy()
    for key in ['Profit by Hour', 'Profit by Weekday', 'PnL Distribution']:
        flat[key] = json.dumps(flat[key])
    pd.DataFrame([flat]).to_csv(csv_path, index=False)
    logger.info("Analysis CSV written to %s", csv_path)

    dashboard = {
        'summary': summary,
        'rolling_winrate': rolling_win,
        'rolling_drawdown': rolling_dd
    }
    json_path = project_root / "trading_engine" / "data" / "dashboard.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    logger.info("Dashboard JSON written to %s", json_path)


def main():
    logger.info("Starting analysis of backtest trades")
    trades_df = load_trades()
    if trades_df.empty:
        print("No trades available for analysis.")
        return
    summary, rolling_win, rolling_dd = compute_metrics(trades_df)
    save_outputs(summary, rolling_win, rolling_dd)
    logger.info("Analysis completed")

if __name__ == "__main__":
    main()
