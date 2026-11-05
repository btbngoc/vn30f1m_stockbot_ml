import sys
sys.path.insert(0, ".")
import pandas as pd
from trading_engine.backtest.engine import BacktestEngine
from trading_engine.backtest.config import BacktestConfig

sys.stdout.reconfigure(encoding='utf-8')

features_df = pd.read_parquet('trading_engine/data/VN30F1M_features.parquet')
prediction_df = pd.read_parquet('trading_engine/data/prediction.parquet')
if 'datetime' not in prediction_df.columns:
    prediction_df = prediction_df.reset_index()
if 'datetime' not in features_df.columns:
    features_df = features_df.reset_index()
merged_df = pd.merge(features_df, prediction_df, on='datetime', how='inner')
merged_df['datetime'] = pd.to_datetime(merged_df['datetime'])
merged_df = merged_df.sort_values('datetime').set_index('datetime')

# Run official BacktestEngine on merged_df
engine = BacktestEngine(merged_df)
trades = engine.run()
trades_2026 = trades[trades['Entry Date'].astype(str).str.startswith('2026')].copy()
print(f"Official BacktestEngine (full merged_df) 2026 trades: {len(trades_2026)}")
print(f"Official BacktestEngine (full merged_df) 2026 Net PnL: {trades_2026['PnL'].sum():,.2f}")

# What if BacktestEngine is run ONLY on df_2026 (from 2026-01-01)?
df_2026 = merged_df[merged_df.index >= '2026-01-01'].copy()
engine_2026 = BacktestEngine(df_2026)
trades_only_2026 = engine_2026.run()
print(f"Official BacktestEngine (df_2026 only) trades: {len(trades_only_2026)}")
print(f"Official BacktestEngine (df_2026 only) Net PnL: {trades_only_2026['PnL'].sum():,.2f}")
