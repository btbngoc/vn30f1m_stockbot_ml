import sys
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# Load 2026 trades
trades = pd.read_csv('results/backtest_trades_2026.csv')

# 1. HARD SL ANALYSIS
print('=== 1. HARD SL ANALYSIS ===')
hard_sl_trades = trades[trades['Reason'] == 'Hard_SL']
all_losses = trades[trades['PnL'] < 0]['PnL'].sum()
hard_sl_losses = hard_sl_trades['PnL'].sum()
print(f'Count of Hard_SL trades: {len(hard_sl_trades)}')
print(f'Total Loss of all losing trades: {all_losses:,.0f} VND')
print(f'Total Loss from Hard_SL: {hard_sl_losses:,.0f} VND')
print(f'Percentage of Hard_SL in total loss: {hard_sl_losses / all_losses * 100:.2f}%\n')

for i, r in hard_sl_trades.iterrows():
    pts_loss = (r['Exit'] - r['Entry']) if r['Type'] == 'LONG' else (r['Entry'] - r['Exit'])
    print(f"Trade #{i+1:2d} | {r['Entry Date']} -> {r['Exit Date']} | {r['Type']:5s} | In: {r['Entry']:6.1f} | Out: {r['Exit']:6.1f} | Chênh lệch: {pts_loss:+5.1f} pt | PnL: {r['PnL']:+10,.0f} VND | Conf: {r['Confidence']:.3f}")

# 2. CONFIDENCE CALIBRATION
print('\n=== 2. CONFIDENCE CALIBRATION ===')
bins = [0.55, 0.60, 0.65, 1.01]
labels = ['0.55 - 0.60', '0.60 - 0.65', '>= 0.65']
trades['ConfGroup'] = pd.cut(trades['Confidence'], bins=bins, labels=labels, right=False)

for group, df_g in trades.groupby('ConfGroup', observed=False):
    n = len(df_g)
    wins = (df_g['PnL'] > 0).sum()
    wr = wins / n * 100 if n > 0 else 0
    pnl = df_g['PnL'].sum()
    gross_win = df_g[df_g['PnL'] > 0]['PnL'].sum()
    gross_loss = abs(df_g[df_g['PnL'] < 0]['PnL'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else np.nan
    avg_pnl = df_g['PnL'].mean()
    print(f'Group {group:12s}: N={n:2d} ({n/len(trades)*100:4.1f}%) | Win={wins:2d} ({wr:5.1f}%) | Net PnL={pnl:+11,.0f} VND | PF={pf:4.2f} | Avg PnL={avg_pnl:+9,.0f} VND')

# 3. OVERNIGHT VS INTRADAY & ATC EXIT
print('\n=== 3. INTRADAY VS OVERNIGHT VS ATC ===')
trades['EntryDT'] = pd.to_datetime(trades['Entry Date'])
trades['ExitDT'] = pd.to_datetime(trades['Exit Date'])
trades['IsOvernight'] = trades['EntryDT'].dt.date != trades['ExitDT'].dt.date
trades['IsATCExit'] = (trades['ExitDT'].dt.hour == 14) & (trades['ExitDT'].dt.minute >= 30)

for name, mask in [('Intraday (Đóng trong ngày)', ~trades['IsOvernight']), ('Overnight (Giữ qua đêm)', trades['IsOvernight'])]:
    sub = trades[mask]
    n = len(sub)
    wins = (sub['PnL'] > 0).sum()
    wr = wins / n * 100 if n > 0 else 0
    pnl = sub['PnL'].sum()
    gw = sub[sub['PnL'] > 0]['PnL'].sum()
    gl = abs(sub[sub['PnL'] < 0]['PnL'].sum())
    pf = gw / gl if gl > 0 else np.nan
    print(f'{name:28s}: N={n:2d} | Win={wins:2d} ({wr:5.1f}%) | PnL={pnl:+11,.0f} VND | PF={pf:4.2f}')

atc_sub = trades[trades['IsATCExit']]
print(f'\nLệnh dính giờ ra ATC (14:30 - 14:45): N={len(atc_sub)}')
if len(atc_sub) > 0:
    for _, r in atc_sub.iterrows():
        print(f"  {r['Entry Date']} -> {r['Exit Date']} | {r['Type']} | In: {r['Entry']} Out: {r['Exit']} | PnL: {r['PnL']:+10,.0f} | Reason: {r['Reason']}")
else:
    print('  Không có lệnh nào thoát trong phiên ATC (14:30-14:45) trong tập backtest 2026.')
