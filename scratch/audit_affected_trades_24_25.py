import sys
sys.path.insert(0, ".")
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

from scratch.run_exact_wf import evaluate_fold, trained_models, features, FOLDS

all_affected = []

for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS[:2]):
    year = "2024" if idx == 0 else "2025"
    m_base = evaluate_fold(trained_models[idx], features, test_start, test_end, th, 0.10, False)
    m_gap03 = evaluate_fold(trained_models[idx], features, test_start, test_end, th, 0.30, True)
    
    df_b = m_base['trades_df']
    df_g = m_gap03['trades_df']
    
    for i in range(len(df_b)):
        tb = df_b.iloc[i]
        tg = df_g.iloc[i]
        # PnL difference
        pnl_diff = tg['PnL'] - tb['PnL']
        exit_base = tb['Exit']
        exit_gap03 = tg['Exit']
        # If exit price differed by more than the 0.2 pt slippage delta
        # Base slip is 0.1, Gap03 slip is 0.3 -> normal delta without gap is 0.2 pt on exit, 0.2 pt on entry = -40,000 VND
        is_gap_affected = abs(abs(exit_gap03 - exit_base) - 0.2) > 0.05
        if is_gap_affected:
            all_affected.append({
                "Year": year,
                "TradeNum": i + 1,
                "EntryTime": str(tb['Entry Date']),
                "ExitTime": str(tb['Exit Date']),
                "Type": tb['Type'],
                "Reason": tb['Reason'],
                "EntryBase": tb['Entry'],
                "ExitBase": exit_base,
                "ExitGap03": exit_gap03,
                "PnLBase": tb['PnL'],
                "PnLGap03": tg['PnL'],
                "PnLDiff": pnl_diff,
                "GapSizePt": abs(exit_gap03 - exit_base) - 0.2
            })

df_aff = pd.DataFrame(all_affected)
print("=== AFFECTED TRADES IN 2024 AND 2025 ===")
print(df_aff.to_string(index=False))

# Export to CSV
csv_path = "results/affected_trades_2024_2025_gap_slip03.csv"
df_aff.to_csv(csv_path, index=False)
print(f"\nSaved affected trades to {csv_path}")
