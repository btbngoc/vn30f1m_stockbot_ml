import sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv("results/backtest_trades_2026_comparison_gap_slip03.csv")

# Version A (All 45 trades)
pnl_base_total = df["Base PnL"].sum()
pnl_gap_total = df["Gap03 PnL"].sum()
diff_total = df["Diff (VND)"].sum()

wins_A = df.loc[df["Gap03 PnL"] > 0, "Gap03 PnL"].sum()
losses_A = -df.loc[df["Gap03 PnL"] <= 0, "Gap03 PnL"].sum()
pf_A = wins_A / losses_A
wr_A = (df["Gap03 PnL"] > 0).mean()

# Version B (Without Trade #9)
df_no9 = df[df["Trade"] != 9].copy()
pnl_gap_no9 = df_no9["Gap03 PnL"].sum()
wins_B = df_no9.loc[df_no9["Gap03 PnL"] > 0, "Gap03 PnL"].sum()
losses_B = -df_no9.loc[df_no9["Gap03 PnL"] <= 0, "Gap03 PnL"].sum()
pf_B = wins_B / losses_B
wr_B = (df_no9["Gap03 PnL"] > 0).mean()

print(f"2026 Base PnL: {pnl_base_total:+,.0f} VND")
print(f"2026 Gap03 PnL: {pnl_gap_total:+,.0f} VND")
print(f"Total Diff: {diff_total:+,.0f} VND")
print(f"Bản A (Có lệnh #9): N={len(df)}, PnL={pnl_gap_total:+,.0f} VND, PF={pf_A:.3f}, WinRate={wr_A*100:.1f}%, GrossWin={wins_A:+,.0f}, GrossLoss={losses_A:+,.0f}")
print(f"Bản B (Không lệnh #9): N={len(df_no9)}, PnL={pnl_gap_no9:+,.0f} VND, PF={pf_B:.3f}, WinRate={wr_B*100:.1f}%, GrossWin={wins_B:+,.0f}, GrossLoss={losses_B:+,.0f}")

# Total OOS calculation
# 2024: Net PnL = +2,033,929 VND (Gross Win = 5,693,929; Gross Loss = 3,660,000)
# 2025: Net PnL = +8,361,429 VND (Gross Win = 29,633,571; Gross Loss = 21,272,142)
gw_24_25 = 5693929.0 + 29633571.0
gl_24_25 = 3660000.0 + 21272142.0

# Total OOS Bản A
oos_pnl_A = 2033929.0 + 8361429.0 + pnl_gap_total
oos_gw_A = gw_24_25 + wins_A
oos_gl_A = gl_24_25 + losses_A
oos_pf_A = oos_gw_A / oos_gl_A

# Total OOS Bản B
oos_pnl_B = 2033929.0 + 8361429.0 + pnl_gap_no9
oos_gw_B = gw_24_25 + wins_B
oos_gl_B = gl_24_25 + losses_B
oos_pf_B = oos_gw_B / oos_gl_B

print("\n=== TỔNG HỢP OOS (2024 - 2026) ===")
print(f"OOS Bản A (Có lệnh #9): N=153, Net PnL={oos_pnl_A:+,.0f} VND, PF={oos_pf_A:.2f}")
print(f"OOS Bản B (Không lệnh #9): N=152, Net PnL={oos_pnl_B:+,.0f} VND, PF={oos_pf_B:.2f}")
