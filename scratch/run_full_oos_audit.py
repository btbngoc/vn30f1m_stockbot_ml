import sys
import math
import json
from pathlib import Path
import pandas as pd
import numpy as np
import xgboost as xgb

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')

# 1. TRADE COMPARISON FOR 2026: BASE VS GAP-AWARE + SLIP 0.3
print("=== 1. PREPARING 2026 COMPARISON TABLE ===")
base_2026 = pd.read_csv('results/backtest_trades_2026.csv')

# Load features & predictions for 2026
features_path = "trading_engine/data/VN30F1M_features.parquet"
prediction_path = "trading_engine/data/prediction.parquet"
features_df = pd.read_parquet(features_path)
prediction_df = pd.read_parquet(prediction_path)

if 'datetime' not in prediction_df.columns:
    prediction_df = prediction_df.reset_index()
if 'datetime' not in features_df.columns:
    features_df = features_df.reset_index()

merged_df = pd.merge(features_df, prediction_df, on='datetime', how='inner')
merged_df['datetime'] = pd.to_datetime(merged_df['datetime'])
merged_df = merged_df.sort_values('datetime').set_index('datetime')
df_2026 = merged_df[merged_df.index >= "2026-01-01"].copy()

def run_custom_backtest(df, slippage=0.30, gap_aware=True, tick_rounding=True, fixed_fee=30_000.0):
    point_multiplier = 100_000.0
    trailing_stop_atr = 1.5
    stop_loss_atr = 1.0
    hard_sl_atr_mult = 2.5
    cooldown_bars = 15
    
    trade_log = []
    position = 0
    entry_price = entry_date = None
    contracts = 1
    initial_sl = trailing_sl = hard_sl = 0.0
    cooldown_remaining = 0
    confidence = 1.0
    
    def round_tick(price, direction_adverse):
        if not tick_rounding:
            return price
        if direction_adverse > 0:
            return math.ceil(price * 10.0 - 1e-9) / 10.0
        else:
            return math.floor(price * 10.0 + 1e-9) / 10.0

    for timestamp, row in df.iterrows():
        if cooldown_remaining > 0:
            cooldown_remaining -= 1
        signal = int(row.get("Signal", 0))
        op, close, high, low = row["Open"], row["Close"], row["High"], row["Low"]
        
        if position:
            atr = row.get("ATR", 0.0)
            raw_exit = None
            reason = None
            
            if position == 1:
                if low <= hard_sl:
                    raw_exit, reason = hard_sl, "Hard_SL"
                elif trailing_sl >= entry_price and low <= trailing_sl:
                    raw_exit, reason = trailing_sl, "SL"
                elif low <= trailing_sl:
                    htf_reversal_down = (
                        row.get("HTF_15m_TrendDownOK", 0) == 1
                        or row.get("HTF_15m_TrendTransitionDown", 0) == 1
                    )
                    if htf_reversal_down:
                        raw_exit, reason = trailing_sl, "SL"
                elif signal == -1:
                    raw_exit, reason = close, "Reversal"
            else:
                if high >= hard_sl:
                    raw_exit, reason = hard_sl, "Hard_SL"
                elif trailing_sl <= entry_price and high >= trailing_sl:
                    raw_exit, reason = trailing_sl, "SL"
                elif high >= trailing_sl:
                    htf_reversal = (
                        row.get("HTF_15m_TrendOK", 0) == 1
                        or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0)
                    )
                    if htf_reversal:
                        raw_exit, reason = trailing_sl, "SL"
                elif signal == 1:
                    raw_exit, reason = close, "Reversal"
                    
            if raw_exit is None and atr > 0:
                trailing_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                if position == 1:
                    trailing_sl = max(trailing_sl, close - trailing_stop_atr * trailing_atr)
                else:
                    trailing_sl = min(trailing_sl, close + trailing_stop_atr * trailing_atr)
                    
            if raw_exit is not None:
                actual_exit_base = raw_exit
                if gap_aware and reason in ("Hard_SL", "SL"):
                    if position == 1 and op < raw_exit:
                        actual_exit_base = op
                    elif position == -1 and op > raw_exit:
                        actual_exit_base = op
                            
                if position == 1:
                    exit_price = round_tick(actual_exit_base - slippage, direction_adverse=-1)
                else:
                    exit_price = round_tick(actual_exit_base + slippage, direction_adverse=+1)
                    
                gross_pnl = (exit_price - entry_price) * position * contracts * point_multiplier
                fees = fixed_fee
                net_pnl = gross_pnl - fees
                
                trade_log.append({
                    "Entry Date": str(entry_date),
                    "Exit Date": str(timestamp),
                    "Type": "LONG" if position == 1 else "SHORT",
                    "Entry": entry_price,
                    "Exit": exit_price,
                    "Gross PnL": gross_pnl,
                    "Fees": fees,
                    "PnL": net_pnl,
                    "Reason": reason,
                    "Confidence": confidence
                })
                
                position = 0
                cooldown_remaining = cooldown_bars
                continue
                
        if position == 0 and signal and cooldown_remaining == 0:
            atr = row.get("ATR", 0.0)
            if atr <= 0:
                continue
            position = signal
            entry_date = timestamp
            
            if position == 1:
                entry_price = round_tick(close + slippage, direction_adverse=+1)
                setup = str(row.get("EntrySetup", ""))
                trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "SPRING" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
            else:
                entry_price = round_tick(close - slippage, direction_adverse=-1)
                setup = str(row.get("EntrySetup", ""))
                trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "UTAD" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
                
            initial_sl = entry_price - position * stop_loss_atr * trade_atr
            trailing_sl = initial_sl
            hard_sl = entry_price - position * hard_sl_atr_mult * stop_loss_atr * trade_atr
            confidence = float(row.get("Confidence", 1.0))
            
    return pd.DataFrame(trade_log)

gap_slip03_df = run_custom_backtest(df_2026, slippage=0.30, gap_aware=True, tick_rounding=True)

# Build comparison
comp_records = []
for i in range(len(base_2026)):
    b_row = base_2026.iloc[i]
    g_row = gap_slip03_df.iloc[i]
    diff = g_row['PnL'] - b_row['PnL']
    comp_records.append({
        "Trade": i + 1,
        "Entry Date": b_row['Entry Date'],
        "Exit Date": b_row['Exit Date'],
        "Type": b_row['Type'],
        "Base In": round(b_row['Entry'], 1),
        "Base Out": round(b_row['Exit'], 1),
        "Base PnL": round(b_row['PnL'], 0),
        "Gap03 In": round(g_row['Entry'], 1),
        "Gap03 Out": round(g_row['Exit'], 1),
        "Gap03 PnL": round(g_row['PnL'], 0),
        "Diff (VND)": round(diff, 0),
        "Base Reason": b_row['Reason'],
        "Gap Reason": g_row['Reason'],
        "Confidence": round(b_row['Confidence'], 3)
    })

comp_df = pd.DataFrame(comp_records)
comp_path = Path("results/backtest_trades_2026_comparison_gap_slip03.csv")
comp_df.to_csv(comp_path, index=False)
print(f"Saved comparison to {comp_path}")

# Print summary of comparison
print(f"Total Base PnL: {base_2026['PnL'].sum():,.0f} VND")
print(f"Total Gap+Slip03 PnL: {gap_slip03_df['PnL'].sum():,.0f} VND")
print(f"Total Difference: {gap_slip03_df['PnL'].sum() - base_2026['PnL'].sum():,.0f} VND")

# 2. RUN WALK-FORWARD 2024-2026 UNDER GAP-AWARE & SLIPPAGE SCENARIOS
print("\n=== 2. RUNNING WALK-FORWARD 2024-2026 ACROSS SCENARIOS ===")
from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import DATASET_PATH, FEATURES_PATH, THRESHOLD_CANDIDATES, XGBOOST_PARAMS

dataset = pd.read_csv(DATASET_PATH)
dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
features = pd.read_parquet(FEATURES_PATH)
features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")

FOLDS = [
    ("Fold 1 (OOS 2024)", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
    ("Fold 2 (OOS 2025)", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01")),
    ("Fold 3 (OOS 2026)", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), None),
]

def evaluate_fold_test(model, features, test_start, test_end, threshold, slippage, gap_aware):
    period = features[features["datetime"] >= test_start].copy()
    if test_end is not None:
        period = period[period["datetime"] < test_end].copy()
    probability = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period["Confidence"] = probability
    strategy_signal = period["StrategySignal"].astype(int)
    pass_long = period["Confidence"] >= threshold
    pass_short = period["Confidence"] >= threshold
    short_regime_gate = (
        (period["MarketRegime"] == "TREND_DOWN")
        | (period.get("HTF_15m_TrendDownOK", 0) == 1)
        | (period.get("HTF_15m_TrendTransitionDown", 0) == 1)
    )
    trade_signal = pd.Series(0, index=period.index, dtype=int)
    trade_signal[(strategy_signal == 1) & pass_long] = 1
    trade_signal[(strategy_signal == -1) & pass_short & short_regime_gate] = -1
    period["Signal"] = trade_signal
    
    trades = run_custom_backtest(period.set_index("datetime"), slippage=slippage, gap_aware=gap_aware, tick_rounding=True)
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "max_drawdown": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    drawdown = (trades["PnL"].cumsum().cummax() - trades["PnL"].cumsum()).max()
    return {
        "trades": int(len(trades)),
        "net_pnl": float(trades["PnL"].sum()),
        "gross_profit": float(wins),
        "gross_loss": float(losses),
        "profit_factor": float(wins / losses) if losses > 0 else 0.0,
        "win_rate": float((trades["PnL"] > 0).mean()),
        "max_drawdown": float(drawdown),
    }

# Selected thresholds from standard walk-forward:
# Fold 1 (2024): 0.55
# Fold 2 (2025): 0.50
# Fold 3 (2026): 0.55
selected_thresholds = [0.55, 0.50, 0.55]

# Train models for each fold
trained_models = []
for (name, val_start, test_start, test_end) in FOLDS:
    train = dataset[dataset["exit_time"] < val_start]
    model = xgb.XGBClassifier(**XGBOOST_PARAMS)
    model.fit(train[ML_FEATURE_COLUMNS], train["label"])
    trained_models.append(model)

scenarios = [
    ("Base (Nominal SL, Slip 0.1 pt)", 0.10, False),
    ("Gap-Aware (Slip 0.1 pt)", 0.10, True),
    ("Gap-Aware (Slip 0.3 pt)", 0.30, True),
    ("Gap-Aware (Slip 0.6 pt)", 0.60, True),
]

wf_results = []
for sc_name, slip, gap in scenarios:
    fold_metrics = []
    for idx, (name, val_start, test_start, test_end) in enumerate(FOLDS):
        m = evaluate_fold_test(trained_models[idx], features, test_start, test_end, selected_thresholds[idx], slip, gap)
        fold_metrics.append((name, m))
    
    total_trades = sum(m["trades"] for _, m in fold_metrics)
    total_pnl = sum(m["net_pnl"] for _, m in fold_metrics)
    total_gw = sum(m["gross_profit"] for _, m in fold_metrics)
    total_gl = sum(m["gross_loss"] for _, m in fold_metrics)
    total_pf = total_gw / total_gl if total_gl > 0 else 0.0
    worst_dd = max(m["max_drawdown"] for _, m in fold_metrics)
    
    wf_results.append({
        "scenario": sc_name,
        "folds": fold_metrics,
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "total_pf": total_pf,
        "worst_dd": worst_dd
    })

print("\n=== WALK-FORWARD DETAILED BREAKDOWN ===")
for sc in wf_results:
    print(f"\n--- {sc['scenario']} ---")
    for fname, m in sc['folds']:
        print(f"  {fname:18s} | N={m['trades']:2d} | Win={m['win_rate']*100:4.1f}% | Net PnL={m['net_pnl']:+12,.0f} VND | PF={m['profit_factor']:4.2f} | Max DD={m['max_drawdown']:10,.0f} VND")
    print(f"  {'TỔNG HỢP OOS':18s} | N={sc['total_trades']:2d} | Net PnL={sc['total_pnl']:+12,.0f} VND | PF={sc['total_pf']:4.2f} | Worst DD={sc['worst_dd']:10,.0f} VND")
