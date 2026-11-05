import sys
import math
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# Load merged dataset for 2026
features_path = "trading_engine/data/VN30F1M_features.parquet"
prediction_path = "trading_engine/data/prediction.parquet"

print("Loading data...")
features_df = pd.read_parquet(features_path)
prediction_df = pd.read_parquet(prediction_path)

if 'datetime' not in prediction_df.columns:
    prediction_df = prediction_df.reset_index()
if 'datetime' not in features_df.columns:
    features_df = features_df.reset_index()

merged_df = pd.merge(features_df, prediction_df, on='datetime', how='inner')
merged_df['datetime'] = pd.to_datetime(merged_df['datetime'])
merged_df = merged_df.sort_values('datetime').set_index('datetime')

# Filter for 2026 only or run full and slice 2026
# Notice: To avoid initial boundary effects, we can run on full or 2026.
# Since 2026 starts with position=0 on 2026-01-01, let's verify if first trade is 2026-01-12.
df_2026 = merged_df[merged_df.index >= "2026-01-01"].copy()
print(f"2026 Bars: {len(df_2026)}")

# Function to run backtest with custom execution model
def run_custom_backtest(df, slippage=0.10, gap_aware=True, tick_rounding=True, fixed_fee=30_000.0):
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
    
    def round_tick(price, direction_adverse, is_entry):
        if not tick_rounding:
            return price
        # Direction adverse means we want the worst price for trader:
        # Long Entry: ceil (buy higher)
        # Short Entry: floor (sell lower)
        # Long Exit: floor (sell lower)
        # Short Exit: ceil (buy higher)
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
                # LONG exit
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
                # SHORT exit
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
                # Gap-Aware Adjustment
                actual_exit_base = raw_exit
                if gap_aware and reason in ("Hard_SL", "SL"):
                    if position == 1:
                        # For long, if open gap down below stop, executed at open or lower
                        if op < raw_exit:
                            actual_exit_base = op
                    else:
                        # For short, if open gap up above stop, executed at open or higher
                        if op > raw_exit:
                            actual_exit_base = op
                            
                # Apply slippage and tick rounding
                if position == 1:
                    exit_price = round_tick(actual_exit_base - slippage, direction_adverse=-1, is_entry=False)
                else:
                    exit_price = round_tick(actual_exit_base + slippage, direction_adverse=+1, is_entry=False)
                    
                gross_pnl = (exit_price - entry_price) * position * contracts * point_multiplier
                fees = fixed_fee
                net_pnl = gross_pnl - fees
                
                trade_log.append({
                    "Entry Date": entry_date,
                    "Exit Date": timestamp,
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
                entry_price = round_tick(close + slippage, direction_adverse=+1, is_entry=True)
                setup = str(row.get("EntrySetup", ""))
                trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "SPRING" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
            else:
                entry_price = round_tick(close - slippage, direction_adverse=-1, is_entry=True)
                setup = str(row.get("EntrySetup", ""))
                trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "UTAD" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
                
            initial_sl = entry_price - position * stop_loss_atr * trade_atr
            trailing_sl = initial_sl
            hard_sl = entry_price - position * hard_sl_atr_mult * stop_loss_atr * trade_atr
            confidence = float(row.get("Confidence", 1.0))
            
    return pd.DataFrame(trade_log)

# Run simulations across scenarios
scenarios = [
    ("Base (Slip 0.1 pt, Nominal SL)", 0.10, False, False),
    ("Gap-Aware + Tick 0.1 (Slip 0.1 pt)", 0.10, True, True),
    ("Gap-Aware + Tick 0.1 (Slip 0.3 pt)", 0.30, True, True),
    ("Gap-Aware + Tick 0.1 (Slip 0.6 pt)", 0.60, True, True),
]

results = []
for name, slip, gap, tick in scenarios:
    res_df = run_custom_backtest(df_2026, slippage=slip, gap_aware=gap, tick_rounding=tick)
    n = len(res_df)
    wins = (res_df['PnL'] > 0).sum()
    wr = wins / n * 100 if n > 0 else 0
    pnl = res_df['PnL'].sum()
    gw = res_df[res_df['PnL'] > 0]['PnL'].sum()
    gl = abs(res_df[res_df['PnL'] < 0]['PnL'].sum())
    pf = gw / gl if gl > 0 else np.nan
    max_dd = 0
    cum = res_df['PnL'].cumsum()
    peak = cum.cummax()
    dd = peak - cum
    max_dd = dd.max() if len(dd) > 0 else 0
    worst_loss = res_df['PnL'].min()
    
    results.append({
        "Kịch bản": name,
        "Số Lệnh": n,
        "Winrate (%)": f"{wr:.1f}%",
        "Net PnL (VND)": f"{pnl:+12,.0f}",
        "Profit Factor": f"{pf:.3f}",
        "Max Drawdown (VND)": f"{max_dd:11,.0f}",
        "Lệnh Thua Nặng Nhất": f"{worst_loss:+10,.0f}"
    })

print("\n=== KẾT QUẢ SO SÁNH CÁC KỊCH BẢN TRƯỢT GIÁ & GAP 2026 ===")
res_table = pd.DataFrame(results)
print(res_table.to_string(index=False))
