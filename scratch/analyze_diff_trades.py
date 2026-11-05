import sys
sys.path.insert(0, ".")
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# Compare base trades vs gap_slip03 trades in detail
base_trades = pd.read_csv('results/backtest_trades_2026.csv')
comp_trades = pd.read_csv('results/backtest_trades_2026_comparison_gap_slip03.csv')

print("=== CHECKING ALL TRADES WITH PnL DIFF > 50,000 VND ===")
big_diffs = comp_trades[abs(comp_trades['Diff (VND)']) > 50000]
print(big_diffs[['Trade', 'Entry Date', 'Exit Date', 'Type', 'Base In', 'Gap03 In', 'Base Out', 'Gap03 Out', 'Base PnL', 'Gap03 PnL', 'Diff (VND)', 'Base Reason', 'Gap Reason']].to_string(index=False))

print("\n=== SUMMARY OF DIFFS ===")
print("Total Base PnL:", base_trades['PnL'].sum())
print("Total Gap03 PnL:", comp_trades['Gap03 PnL'].sum())
print("Sum of Diff (VND):", comp_trades['Diff (VND)'].sum())

# Inspect Trade 17, 19, 36, 44 specifically in raw feature data
features = pd.read_parquet('trading_engine/data/VN30F1M_features.parquet')
features['datetime'] = pd.to_datetime(features['datetime'])
features = features.set_index('datetime')

for t_idx in [4, 9, 17, 19, 36, 44]:
    r = base_trades.iloc[t_idx - 1]
    entry_dt = pd.to_datetime(r['Entry Date'])
    exit_dt = pd.to_datetime(r['Exit Date'])
    print(f"\n--- Trade #{t_idx} ({r['Type']}) Entry: {entry_dt} | Exit: {exit_dt} ---")
    sub = features.loc[entry_dt:exit_dt]
    print(f"Bars in trade: {len(sub)}")
    print(f"Entry bar: Open={sub.iloc[0]['Open']}, High={sub.iloc[0]['High']}, Low={sub.iloc[0]['Low']}, Close={sub.iloc[0]['Close']}")
    print(f"Exit bar: Open={sub.iloc[-1]['Open']}, High={sub.iloc[-1]['High']}, Low={sub.iloc[-1]['Low']}, Close={sub.iloc[-1]['Close']}")
    print(f"Base In={r['Entry']}, Base Out={r['Exit']}, Base Reason={r['Reason']}")
    c_r = comp_trades.iloc[t_idx - 1]
    print(f"Gap03 In={c_r['Gap03 In']}, Gap03 Out={c_r['Gap03 Out']}, Gap03 Reason={c_r['Gap Reason']}")
