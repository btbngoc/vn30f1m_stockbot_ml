import sys
sys.path.insert(0, ".")
import pandas as pd
from scratch.run_exact_wf import evaluate_fold, trained_models, features, FOLDS

# Fold 3 is 2026
m_base = evaluate_fold(trained_models[2], features, FOLDS[2][2], FOLDS[2][3], FOLDS[2][4], slippage=0.10, gap_aware=False)
m_gap03 = evaluate_fold(trained_models[2], features, FOLDS[2][2], FOLDS[2][3], FOLDS[2][4], slippage=0.30, gap_aware=True)

df_base = m_base["trades_df"]
df_gap03 = m_gap03["trades_df"]

records = []
for i in range(len(df_base)):
    b = df_base.iloc[i]
    g = df_gap03.iloc[i]
    diff = g["PnL"] - b["PnL"]
    records.append({
        "Trade": i + 1,
        "Entry Date": b["Entry Date"],
        "Exit Date": b["Exit Date"],
        "Type": b["Type"],
        "Base In": round(b["Entry"], 2),
        "Base Out": round(b["Exit"], 2),
        "Base PnL": round(b["PnL"], 0),
        "Gap03 In": round(g["Entry"], 2),
        "Gap03 Out": round(g["Exit"], 2),
        "Gap03 PnL": round(g["PnL"], 0),
        "Diff (VND)": round(diff, 0),
        "Base Reason": b["Reason"],
        "Gap Reason": g["Reason"],
        "Confidence": round(b["Confidence"], 3)
    })

comp_df = pd.DataFrame(records)
comp_df.to_csv("results/backtest_trades_2026_comparison_gap_slip03.csv", index=False)
print("Saved clean results/backtest_trades_2026_comparison_gap_slip03.csv")
print("Base Net PnL:", comp_df["Base PnL"].sum())
print("Gap03 Net PnL:", comp_df["Gap03 PnL"].sum())
print("Sum of Diff:", comp_df["Diff (VND)"].sum())
