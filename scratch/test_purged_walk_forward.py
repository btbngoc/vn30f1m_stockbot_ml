import sys
sys.path.insert(0, ".")
import pandas as pd
import numpy as np
import xgboost as xgb

sys.stdout.reconfigure(encoding='utf-8')

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import XGBOOST_PARAMS, FEATURES_PATH, DATASET_PATH
from scratch.run_standardized_walk_forward_giai_doan_2 import StandardizedEngine, compute_metrics, BacktestConfig

df = pd.read_csv(DATASET_PATH)
df['entry_time'] = pd.to_datetime(df['entry_time'])
df['exit_time'] = pd.to_datetime(df['exit_time'])
features = pd.read_parquet(FEATURES_PATH)
features['datetime'] = pd.to_datetime(features['datetime'])

def purge_df(df_sub):
    entry_arr = df_sub['entry_time'].values
    exit_arr = df_sub['exit_time'].values
    selected = []
    last_exit = pd.Timestamp.min
    for i in range(len(entry_arr)):
        en = pd.Timestamp(entry_arr[i])
        if en >= last_exit:
            selected.append(i)
            last_exit = pd.Timestamp(exit_arr[i]) + pd.Timedelta(minutes=15)
    return df_sub.iloc[selected]

FOLDS = [
    ('Fold 1 (OOS 2024)', pd.Timestamp('2023-01-01'), pd.Timestamp('2024-01-01'), pd.Timestamp('2025-01-01'), 0.55),
    ('Fold 2 (OOS 2025)', pd.Timestamp('2024-01-01'), pd.Timestamp('2025-01-01'), pd.Timestamp('2026-01-01'), 0.50),
    ('Fold 3 (OOS 2026)', pd.Timestamp('2025-01-01'), pd.Timestamp('2026-01-01'), None, 0.55),
]

print("=== PURGED & EMBARGOED MODEL WALK-FORWARD BACKTEST (SLIP 0.3, PHI 30K) ===")
all_purged_trades = []

for idx, (fname, val_start, test_start, test_end, th) in enumerate(FOLDS):
    train = df[df['exit_time'] < val_start]
    train_p = purge_df(train)
    p = XGBOOST_PARAMS.copy()
    p['random_state'] = 42
    model_p = xgb.XGBClassifier(**p)
    model_p.fit(train_p[ML_FEATURE_COLUMNS], train_p['label'])
    
    period = features[features['datetime'] >= test_start].copy()
    if test_end is not None:
        period = period[period['datetime'] < test_end].copy()
    
    prob = model_p.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period['Confidence'] = prob
    strat = period['StrategySignal'].astype(int)
    short_gate = ((period['MarketRegime'] == 'TREND_DOWN') | (period.get('HTF_15m_TrendDownOK', 0) == 1) | (period.get('HTF_15m_TrendTransitionDown', 0) == 1))
    sig = pd.Series(0, index=period.index, dtype=int)
    sig[(strat == 1) & (period['Confidence'] >= th)] = 1
    sig[(strat == -1) & (period['Confidence'] >= th) & short_gate] = -1
    period['Signal'] = sig
    
    cfg = BacktestConfig(
        slippage_points=0.30,
        commission_per_contract=15000.0,
        fixed_contracts=1,
        take_profit_atr=None,
        trailing_stop_atr=1.5,
        stop_loss_atr=1.0,
        hard_sl_atr_mult=2.5,
        max_holding_bars=None,
        cooldown_bars=15
    )
    tr = StandardizedEngine(period.set_index('datetime'), config=cfg, gap_aware=True).run()
    st = compute_metrics(tr)
    all_purged_trades.append(tr)
    n = st['trades']
    wr = st['win_rate'] * 100
    pnl = st['net_pnl']
    pf = st['pf']
    dd = st['max_dd']
    print(f"{fname:18s} | N={n:2d} | WinRate={wr:4.1f}% | Net PnL={pnl:>+12,.0f} VND | PF={pf:4.2f} | Max DD={dd:10,.0f} VND")

comb_p = pd.concat(all_purged_trades, ignore_index=True)
st_comb = compute_metrics(comb_p)
n = st_comb['trades']
wr = st_comb['win_rate'] * 100
pnl = st_comb['net_pnl']
pf = st_comb['pf']
dd = st_comb['max_dd']
print("-" * 80)
print(f"{'TONG HOP PURGED':18s} | N={n:2d} | WinRate={wr:4.1f}% | Net PnL={pnl:>+12,.0f} VND | PF={pf:4.2f} | Max DD={dd:10,.0f} VND")

