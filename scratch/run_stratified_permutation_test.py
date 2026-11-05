import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from trading_engine.backtest.config import BacktestConfig

# 1. Load data
features = pd.read_parquet("trading_engine/data/VN30F1M_features.parquet")
features["datetime"] = pd.to_datetime(features["datetime"])
features = features.sort_values("datetime").reset_index(drop=True)

cfg_real = BacktestConfig(slippage_points=0.30, commission_per_contract=15000.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)

def round_tick(price): return round(price * 10.0) / 10.0

class BacktestRunner:
    def __init__(self, df, cfg):
        self.df = df
        self.cfg = cfg
    def run(self):
        trades = []
        pos = 0
        entry_p = entry_t = None
        trailing_sl = hard_sl = 0.0
        cooldown = 0
        for timestamp, row in self.df.iterrows():
            if cooldown > 0: cooldown -= 1
            signal = int(row.get("Signal", 0))
            op, close, high, low = row["Open"], row["Close"], row["High"], row["Low"]
            atr = row.get("ATR", 1.0)
            tr_atr = float(row.get("HTF_5m_ATR", atr * 2.0))

            if pos != 0:
                raw_exit = None
                reason = ""
                is_atc = (timestamp.hour == 14 and timestamp.minute == 45)
                if pos == 1:
                    if low <= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl >= entry_p and low <= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif low <= trailing_sl:
                        htf_rev = (row.get("HTF_15m_TrendDownOK", 0) == 1 or row.get("HTF_15m_TrendTransitionDown", 0) == 1)
                        if htf_rev: raw_exit, reason = trailing_sl, "SL"
                    elif signal == -1: raw_exit, reason = close, "Reversal"
                else:
                    if high >= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_p and high >= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif high >= trailing_sl:
                        htf_rev = (row.get("HTF_15m_TrendOK", 0) == 1 or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0))
                        if htf_rev: raw_exit, reason = trailing_sl, "SL"
                    elif signal == 1: raw_exit, reason = close, "Reversal"

                if raw_exit is None:
                    if pos == 1: trailing_sl = max(trailing_sl, round_tick(close - self.cfg.trailing_stop_atr * tr_atr))
                    else: trailing_sl = min(trailing_sl, round_tick(close + self.cfg.trailing_stop_atr * tr_atr))

                if raw_exit is not None:
                    actual_base = raw_exit
                    if reason in ("Hard_SL", "SL"):
                        if pos == 1 and op < raw_exit: actual_base = op
                        elif pos == -1 and op > raw_exit: actual_base = op
                    s = 0.0 if is_atc else self.cfg.slippage_points
                    exit_p = round_tick(actual_base - pos * s)
                    pts = (exit_p - entry_p) * pos
                    net_pnl = pts * 100000.0 - 2 * self.cfg.commission_per_contract
                    trades.append({
                        "entry_time": entry_t, "exit_time": timestamp, "type": "LONG" if pos == 1 else "SHORT",
                        "entry_price": entry_p, "exit_price": exit_p, "points": pts, "net_pnl": net_pnl, "reason": reason
                    })
                    pos = 0
                    cooldown = 15
                    continue

            if pos == 0 and signal and cooldown == 0 and (timestamp.hour < 14 or (timestamp.hour == 14 and timestamp.minute <= 25)):
                pos = signal
                entry_t = timestamp
                entry_p = round_tick(close + pos * self.cfg.slippage_points)
                setup = str(row.get("EntrySetup", ""))
                trade_atr = float(row.get("HTF_15m_ATR", tr_atr)) if ("SPRING" in setup or "UTAD" in setup) else tr_atr
                hard_sl = round_tick(entry_p - pos * 2.5 * trade_atr)
                trailing_sl = round_tick(entry_p - pos * 1.0 * trade_atr)

        return pd.DataFrame(trades)

# Chạy L1 Thuần
sub = features[features["datetime"] >= "2024-01-01"].copy()
sub["Signal"] = sub["StrategySignal"].astype(int)
df_l1 = BacktestRunner(sub.set_index("datetime"), cfg_real).run()
df_l1["year"] = df_l1["entry_time"].dt.year

# Load trades của ML (Baseline Seed 42 và thống kê 10 seeds)
df_ml = pd.read_csv("results/all_trades_visualize.csv")
df_ml["entry_time"] = pd.to_datetime(df_ml["entry_time"])
df_ml["year"] = df_ml["entry_time"].dt.year

print("="*80)
print("PHÉP THỬ HOÁN VỊ PHÂN TẦNG THEO NĂM VÀ THEO HƯỚNG (STRATIFIED PERMUTATION TEST)")
print("So sánh ML vs 1,000 lần rút ngẫu nhiên khớp chính xác số lệnh Long/Short từng năm")
print("="*80)

# Thống kê số lệnh ML theo từng năm và hướng:
target_counts = {}
for y in [2024, 2025, 2026]:
    sub_ml_y = df_ml[df_ml["year"] == y]
    n_long = len(sub_ml_y[sub_ml_y["type"] == "LONG"])
    n_short = len(sub_ml_y[sub_ml_y["type"] == "SHORT"])
    pnl_y = sub_ml_y["net_pnl"].sum()
    target_counts[y] = {"long": n_long, "short": n_short, "total": len(sub_ml_y), "pnl": pnl_y}
    print(f"ML Năm {y}: {len(sub_ml_y):2d} lệnh ({n_long} Long, {n_short} Short) | Net PnL: {pnl_y:>+11,.0f} VND")

print(f"ML Tổng 3 năm: {len(df_ml)} lệnh | Net PnL: {df_ml['net_pnl'].sum():>+11,.0f} VND")

# Chạy 1,000 lần rút ngẫu nhiên có phân tầng chính xác
np.random.seed(42)
B = 1000

strat_results = {2024: [], 2025: [], 2026: [], "total": []}

for _ in range(B):
    sampled_dfs = []
    for y in [2024, 2025, 2026]:
        pool_y = df_l1[df_l1["year"] == y]
        pool_long = pool_y[pool_y["type"] == "LONG"]
        pool_short = pool_y[pool_y["type"] == "SHORT"]
        
        n_l = target_counts[y]["long"]
        n_s = target_counts[y]["short"]
        
        # Rút ngẫu nhiên đúng số lệnh Long và Short của năm đó
        sample_l = pool_long.sample(n=min(n_l, len(pool_long)), replace=False)
        sample_s = pool_short.sample(n=min(n_s, len(pool_short)), replace=False)
        
        y_sample = pd.concat([sample_l, sample_s], ignore_index=True)
        strat_results[y].append(y_sample["net_pnl"].sum())
        sampled_dfs.append(y_sample)
        
    tot_sample = pd.concat(sampled_dfs, ignore_index=True)
    strat_results["total"].append(tot_sample["net_pnl"].sum())

print("\n" + "="*80)
print("KẾT QUẢ ĐO LƯỜNG p-value TỪNG NĂM (KHI ĐÃ KIỂM SOÁT PHÂN TẦNG)")
print("="*80)
print(f"{'Giai đoạn':<12} | {'ML Net PnL':<15} | {'Random Mean PnL':<18} | {'Random 95% CI':<30} | {'p-value':<10} | {'Đánh giá'}")
print("-" * 110)

for y in [2024, 2025, 2026]:
    ml_val = target_counts[y]["pnl"]
    rand_arr = np.array(strat_results[y])
    mean_r = np.mean(rand_arr)
    ci_low = np.percentile(rand_arr, 2.5)
    ci_high = np.percentile(rand_arr, 97.5)
    p_val = np.mean(rand_arr >= ml_val)
    eval_str = "Có tín hiệu rõ (p < 0.05)" if p_val < 0.05 else ("Tín hiệu yếu (p < 0.10)" if p_val < 0.10 else "Không có tín hiệu (p >= 0.10)")
    print(f"Năm {y:<8} | {ml_val:>+11,.0f} đ | {mean_r:>+14,.0f} đ | [{ci_low:>+11,.0f}, {ci_high:>+11,.0f}] đ | {p_val:8.4f}  | {eval_str}")

# Tổng 3 năm
tot_ml = df_ml["net_pnl"].sum()
rand_tot = np.array(strat_results["total"])
mean_tot = np.mean(rand_tot)
ci_low_tot = np.percentile(rand_tot, 2.5)
ci_high_tot = np.percentile(rand_tot, 97.5)
p_val_tot = np.mean(rand_tot >= tot_ml)

# So với ML Median 10 seeds (+6.66M)
p_val_tot_median = np.mean(rand_tot >= 6655000.0)
# So với ML Mean 10 seeds (+4.18M)
p_val_tot_mean = np.mean(rand_tot >= 4179000.0)

print("-" * 110)
print(f"TỔNG 3 NĂM   | {tot_ml:>+11,.0f} đ | {mean_tot:>+14,.0f} đ | [{ci_low_tot:>+11,.0f}, {ci_high_tot:>+11,.0f}] đ | {p_val_tot:8.4f}  | (Seed 42)")
print(f"TỔNG 3 NĂM   |  +6,655,000 đ | {mean_tot:>+14,.0f} đ | [{ci_low_tot:>+11,.0f}, {ci_high_tot:>+11,.0f}] đ | {p_val_tot_median:8.4f}  | (Median 10 seeds)")
print(f"TỔNG 3 NĂM   |  +4,179,000 đ | {mean_tot:>+14,.0f} đ | [{ci_low_tot:>+11,.0f}, {ci_high_tot:>+11,.0f}] đ | {p_val_tot_mean:8.4f}  | (Mean 10 seeds)")

print("\nHoàn tất toàn bộ phép thử.")

