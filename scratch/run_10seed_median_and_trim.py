import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import xgboost as xgb

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import XGBOOST_PARAMS, FEATURES_PATH, DATASET_PATH
from trading_engine.backtest.config import BacktestConfig

dataset = pd.read_csv(DATASET_PATH)
dataset["entry_time"] = pd.to_datetime(dataset["entry_time"])
dataset["exit_time"] = pd.to_datetime(dataset["exit_time"])
features = pd.read_parquet(FEATURES_PATH)
features["datetime"] = pd.to_datetime(features["datetime"])

FOLDS = [
    ("Fold 1 (OOS 2024)", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), 0.55),
    ("Fold 2 (OOS 2025)", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), 0.50),
    ("Fold 3 (OOS 2026)", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), None, 0.55),
]

cfg_real = BacktestConfig(slippage_points=0.30, commission_per_contract=15000.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)

def round_tick(price: float) -> float:
    return round(price * 10.0) / 10.0

class BacktestFast:
    def __init__(self, df: pd.DataFrame, config: BacktestConfig):
        self.df = df
        self.config = config

    def run(self):
        trades = []
        position = 0
        entry_price = entry_date = None
        contracts = 1
        initial_sl = trailing_sl = hard_sl = 0.0
        confidence = 1.0
        cooldown_remaining = 0
        bars_held = 0

        for timestamp, row in self.df.iterrows():
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
            signal = int(row.get("Signal", 0))
            op, close, high, low = row["Open"], row["Close"], row["High"], row["Low"]

            if position:
                bars_held += 1
                atr = row.get("ATR", 0.0)
                raw_exit = None
                reason = None

                if position == 1:
                    if low <= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl >= entry_price and low <= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
                    elif low <= trailing_sl:
                        htf_rev_down = (row.get("HTF_15m_TrendDownOK", 0) == 1 or row.get("HTF_15m_TrendTransitionDown", 0) == 1)
                        if htf_rev_down:
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == -1:
                        raw_exit, reason = close, "Reversal"
                else:
                    if high >= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_price and high >= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
                    elif high >= trailing_sl:
                        htf_rev = (row.get("HTF_15m_TrendOK", 0) == 1 or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0))
                        if htf_rev:
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == 1:
                        raw_exit, reason = close, "Reversal"

                if raw_exit is None and atr > 0:
                    trailing_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                    if position == 1:
                        trailing_sl = max(trailing_sl, round_tick(close - self.config.trailing_stop_atr * trailing_atr))
                    else:
                        trailing_sl = min(trailing_sl, round_tick(close + self.config.trailing_stop_atr * trailing_atr))

                if raw_exit is not None:
                    actual_exit_base = raw_exit
                    is_atc = (timestamp.hour == 14 and timestamp.minute == 45)

                    if reason in ("Hard_SL", "SL"):
                        if position == 1 and op < raw_exit: actual_exit_base = op
                        elif position == -1 and op > raw_exit: actual_exit_base = op

                    slip = 0.0 if is_atc else self.config.slippage_points
                    exit_price = round_tick(actual_exit_base - position * slip)

                    gross_pnl = (exit_price - entry_price) * position * contracts * self.config.point_multiplier
                    fees = 2 * contracts * self.config.commission_per_contract
                    net_pnl = gross_pnl - fees
                    pts = (exit_price - entry_price) * position
                    is_overnight = (entry_date.date() != timestamp.date())

                    trades.append({
                        "entry_time": entry_date,
                        "exit_time": timestamp,
                        "type": "LONG" if position == 1 else "SHORT",
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "points": pts,
                        "net_pnl": net_pnl,
                        "reason": reason,
                        "is_overnight": is_overnight,
                        "bars_held": bars_held,
                        "confidence": confidence
                    })
                    position = 0
                    cooldown_remaining = self.config.cooldown_bars
                    continue

            if position == 0 and signal and cooldown_remaining == 0:
                atr = row.get("ATR", 0.0)
                if atr <= 0:
                    continue
                position = signal
                entry_date = timestamp
                entry_price = round_tick(close + position * self.config.slippage_points)
                setup = str(row.get("EntrySetup", ""))
                if "SPRING" in setup or "UTAD" in setup:
                    trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0)))
                else:
                    trade_atr = float(row.get("HTF_5m_ATR", atr * 2.0))

                initial_sl = round_tick(entry_price - position * self.config.stop_loss_atr * trade_atr)
                trailing_sl = initial_sl
                hsl_mult = getattr(self.config, "hard_sl_atr_mult", 2.5)
                hard_sl = round_tick(entry_price - position * hsl_mult * self.config.stop_loss_atr * trade_atr)
                confidence = float(row.get("Confidence", 1.0))
                bars_held = 0

        return pd.DataFrame(trades)

# Chạy toàn bộ 10 seeds
seeds = list(range(40, 50))
all_seed_results = []
seed_trades_dict = {}

for s in seeds:
    folds_tr = []
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        train = dataset[dataset["exit_time"] < val_start]
        p = XGBOOST_PARAMS.copy()
        p["random_state"] = s
        m = xgb.XGBClassifier(**p)
        m.fit(train[ML_FEATURE_COLUMNS], train["label"])

        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None:
            period = period[period["datetime"] < test_end].copy()
        period["Confidence"] = m.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
        strat = period["StrategySignal"].astype(int)
        sig = pd.Series(0, index=period.index, dtype=int)
        sig[(strat == 1) & (period["Confidence"] >= th)] = 1
        sig[(strat == -1) & (period["Confidence"] >= th)] = -1
        period["Signal"] = sig

        tr = BacktestFast(period.set_index("datetime"), config=cfg_real).run()
        if not tr.empty:
            tr["year"] = tr["entry_time"].dt.year
            tr["fold"] = name
            folds_tr.append(tr)

    df_s = pd.concat(folds_tr, ignore_index=True)
    seed_trades_dict[s] = df_s

    # Thống kê từng seed
    wins = df_s[df_s["net_pnl"] > 0]
    losses = df_s[df_s["net_pnl"] <= 0]
    gw = wins["net_pnl"].sum()
    gl = abs(losses["net_pnl"].sum())
    pf = gw / gl if gl > 0 else 999.0
    
    # Theo năm
    f1 = df_s[df_s["year"] == 2024]
    f2 = df_s[df_s["year"] == 2025]
    f3 = df_s[df_s["year"] == 2026]

    all_seed_results.append({
        "seed": s,
        "trades": len(df_s),
        "wr": len(wins) / len(df_s) * 100,
        "net_pnl": df_s["net_pnl"].sum(),
        "pf": pf,
        "exp": df_s["net_pnl"].sum() / len(df_s),
        "f1_trades": len(f1),
        "f1_pnl": f1["net_pnl"].sum(),
        "f1_pf": (f1[f1["net_pnl"]>0]["net_pnl"].sum() / abs(f1[f1["net_pnl"]<=0]["net_pnl"].sum())) if len(f1[f1["net_pnl"]<=0])>0 else 999.0,
        "f2_trades": len(f2),
        "f2_pnl": f2["net_pnl"].sum(),
        "f2_pf": (f2[f2["net_pnl"]>0]["net_pnl"].sum() / abs(f2[f2["net_pnl"]<=0]["net_pnl"].sum())) if len(f2[f2["net_pnl"]<=0])>0 else 999.0,
        "f3_trades": len(f3),
        "f3_pnl": f3["net_pnl"].sum(),
        "f3_pf": (f3[f3["net_pnl"]>0]["net_pnl"].sum() / abs(f3[f3["net_pnl"]<=0]["net_pnl"].sum())) if len(f3[f3["net_pnl"]<=0])>0 else 999.0,
        "long_trades": len(df_s[df_s["type"]=="LONG"]),
        "long_pnl": df_s[df_s["type"]=="LONG"]["net_pnl"].sum(),
        "short_trades": len(df_s[df_s["type"]=="SHORT"]),
        "short_pnl": df_s[df_s["type"]=="SHORT"]["net_pnl"].sum(),
    })

seed_summary = pd.DataFrame(all_seed_results)

print("="*80)
print("1. BẢNG PHÂN BỐ 10 SEEDS THEO NĂM (THAY THẾ BẢNG SEED 42 ĐƠN LẺ)")
print("="*80)
print(f"{'Chỉ số':<22} | {'2024 (Fold 1)':<18} | {'2025 (Fold 2)':<18} | {'2026 (Fold 3)':<18} | {'TỔNG 3 NĂM':<18}")
print("-" * 100)

for metric, f1_col, f2_col, f3_col, tot_col, fmt in [
    ("Số lệnh (Median)", "f1_trades", "f2_trades", "f3_trades", "trades", "{:.0f}"),
    ("Số lệnh (Dải Min-Max)", "f1_trades", "f2_trades", "f3_trades", "trades", "range"),
    ("Net PnL (Median)", "f1_pnl", "f2_pnl", "f3_pnl", "net_pnl", "{:>+11,.0f} đ"),
    ("Net PnL (Mean ± Std)", "f1_pnl", "f2_pnl", "f3_pnl", "net_pnl", "mean_std"),
    ("Profit Factor (Median)", "f1_pf", "f2_pf", "f3_pf", "pf", "{:.2f}"),
]:
    if fmt == "range":
        v1 = f"[{seed_summary[f1_col].min():.0f} - {seed_summary[f1_col].max():.0f}]"
        v2 = f"[{seed_summary[f2_col].min():.0f} - {seed_summary[f2_col].max():.0f}]"
        v3 = f"[{seed_summary[f3_col].min():.0f} - {seed_summary[f3_col].max():.0f}]"
        vt = f"[{seed_summary[tot_col].min():.0f} - {seed_summary[tot_col].max():.0f}]"
    elif fmt == "mean_std":
        v1 = f"{seed_summary[f1_col].mean()/1e6:>+4.1f}M ± {seed_summary[f1_col].std()/1e6:3.1f}M"
        v2 = f"{seed_summary[f2_col].mean()/1e6:>+4.1f}M ± {seed_summary[f2_col].std()/1e6:3.1f}M"
        v3 = f"{seed_summary[f3_col].mean()/1e6:>+4.1f}M ± {seed_summary[f3_col].std()/1e6:3.1f}M"
        vt = f"{seed_summary[tot_col].mean()/1e6:>+4.1f}M ± {seed_summary[tot_col].std()/1e6:3.1f}M"
    else:
        v1 = fmt.format(seed_summary[f1_col].median())
        v2 = fmt.format(seed_summary[f2_col].median())
        v3 = fmt.format(seed_summary[f3_col].median())
        vt = fmt.format(seed_summary[tot_col].median())
    print(f"{metric:<22} | {v1:<18} | {v2:<18} | {v3:<18} | {vt:<18}")

print("\n" + "="*80)
print("2. PHÂN TÍCH VỊ THẾ LONG vs SHORT QUA 10 SEEDS")
print("="*80)
print(f"Long Trades (Median): {seed_summary['long_trades'].median():.0f} lệnh (Dải: {seed_summary['long_trades'].min()} - {seed_summary['long_trades'].max()})")
print(f"Long Net PnL (Median): {seed_summary['long_pnl'].median():>+11,.0f} VND (Mean: {seed_summary['long_pnl'].mean():>+11,.0f} ± {seed_summary['long_pnl'].std():,.0f} VND)")
print(f"Short Trades (Median): {seed_summary['short_trades'].median():.0f} lệnh (Dải: {seed_summary['short_trades'].min()} - {seed_summary['short_trades'].max()})")
print(f"Short Net PnL (Median): {seed_summary['short_pnl'].median():>+11,.0f} VND (Mean: {seed_summary['short_pnl'].mean():>+11,.0f} ± {seed_summary['short_pnl'].std():,.0f} VND)")

print("\n" + "="*80)
print("3. PHÂN TÍCH ĐỘ NHẠY ĐUÔI DÀY: CẮT BỎ CÁC LỆNH THẮNG / THUA LỚN NHẤT")
print("="*80)

# Đo lường trên Seed 42 và trên toàn bộ 10 seeds
tr42 = seed_trades_dict[42].sort_values("net_pnl", ascending=False).reset_index(drop=True)

print(f"--- Seed 42 Baseline: N={len(tr42)} | Net PnL={tr42['net_pnl'].sum():>+11,.0f} VND | PF={tr42[tr42['net_pnl']>0]['net_pnl'].sum()/abs(tr42[tr42['net_pnl']<=0]['net_pnl'].sum()):.2f} ---")
top_wins = tr42.head(10)[["entry_time", "type", "points", "net_pnl"]].to_dict('records')
print(f"Top 5 lệnh thắng lớn nhất (tổng lãi: {sum(t['net_pnl'] for t in top_wins[:5]):>+11,.0f} VND):")
for i, t in enumerate(top_wins[:5]):
    print(f"  #{i+1}: {t['entry_time'].strftime('%Y-%m-%d')} {t['type']:5s} | +{t['points']:4.1f} pts | {t['net_pnl']:>+10,.0f} VND")

print(f"\nTop 10 lệnh thắng lớn nhất (tổng lãi: {sum(t['net_pnl'] for t in top_wins):>+11,.0f} VND):")

for trim_k in [1, 3, 5, 10]:
    # Bỏ top k lệnh thắng của Seed 42
    trimmed = tr42.iloc[trim_k:].copy()
    w_p = trimmed[trimmed["net_pnl"] > 0]["net_pnl"].sum()
    l_p = abs(trimmed[trimmed["net_pnl"] <= 0]["net_pnl"].sum())
    pf_trim = w_p / l_p if l_p > 0 else 999.0
    pnl_trim = trimmed["net_pnl"].sum()
    print(f"  • Bỏ Top-{trim_k:2d} Lệnh Thắng: Net PnL={pnl_trim:>+11,.0f} VND | PF={pf_trim:4.2f} (Kỳ vọng: {pnl_trim/len(trimmed):>+7,.0f} VND/lệnh)")

print("\n--- Ngược lại: Bỏ các Lệnh Thua Lớn Nhất (Loại bỏ rủi ro đuôi âm) ---")
for trim_loss in [1, 3, 5]:
    trimmed_l = tr42.iloc[:-trim_loss].copy()
    w_p = trimmed_l[trimmed_l["net_pnl"] > 0]["net_pnl"].sum()
    l_p = abs(trimmed_l[trimmed_l["net_pnl"] <= 0]["net_pnl"].sum())
    pf_trim = w_p / l_p if l_p > 0 else 999.0
    pnl_trim = trimmed_l["net_pnl"].sum()
    print(f"  • Bỏ Top-{trim_loss:2d} Lệnh Thua:  Net PnL={pnl_trim:>+11,.0f} VND | PF={pf_trim:4.2f} (Lệnh thua nặng nhất bỏ: {tr42.iloc[-1]['net_pnl']:>+10,.0f} VND)")

# Đo trung bình trên cả 10 seeds khi bỏ top-5 lệnh thắng
trim5_all_pnls = []
trim5_all_pfs = []
for s in seeds:
    df_cur = seed_trades_dict[s].sort_values("net_pnl", ascending=False).reset_index(drop=True)
    df_t5 = df_cur.iloc[5:]
    w = df_t5[df_t5["net_pnl"] > 0]["net_pnl"].sum()
    l = abs(df_t5[df_t5["net_pnl"] <= 0]["net_pnl"].sum())
    trim5_all_pnls.append(df_t5["net_pnl"].sum())
    trim5_all_pfs.append(w/l if l > 0 else 999.0)

print(f"\n--- Phân phối 10 Seeds KHI BỎ TOP-5 LỆNH THẮNG LỚN NHẤT ---")
print(f"Mean Net PnL: {np.mean(trim5_all_pnls):>+11,.0f} VND (std: {np.std(trim5_all_pnls):,.0f})")
print(f"Median Net PnL: {np.median(trim5_all_pnls):>+11,.0f} VND")
print(f"Mean PF: {np.mean(trim5_all_pfs):.2f} (Min: {np.min(trim5_all_pfs):.2f}, Max: {np.max(trim5_all_pfs):.2f})")
print(f"Tỷ lệ seed âm sau khi bỏ top 5: {sum(p < 0 for p in trim5_all_pnls)} / 10 seeds ({sum(p < 0 for p in trim5_all_pnls)*10}%)")

