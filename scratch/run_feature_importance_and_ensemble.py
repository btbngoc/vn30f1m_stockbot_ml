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

print("="*80)
print("1. ĐO LƯỜNG FEATURE IMPORTANCE (GAIN) CỦA XGBOOST THEO TỪNG FOLD")
print("="*80)

fold_models = {}
for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    train = dataset[dataset["exit_time"] < val_start]
    p = XGBOOST_PARAMS.copy()
    p["random_state"] = 42
    m = xgb.XGBClassifier(**p)
    m.fit(train[ML_FEATURE_COLUMNS], train["label"])
    fold_models[name] = m
    
    # Feature importance theo Gain
    booster = m.get_booster()
    score_gain = booster.get_score(importance_type="gain")
    # Sort
    sorted_gain = sorted(score_gain.items(), key=lambda x: x[1], reverse=True)
    print(f"\n--- {name} Top 7 Features theo Gain ---")
    for feat, val in sorted_gain[:7]:
        print(f"  {feat:25s}: {val:8.4f}")

print("\n" + "="*80)
print("2. ĐO LƯỜNG ĐẶC TÍNH ĐỊNH LƯỢNG CỦA CÁC LỆNH BỊ CHẶN (2025 vs 2026)")
print("="*80)

# Khảo sát đặc tính thực tế (ATR, NATR, ADX, RSI, Trend) của các trade L1 trong 2025 vs 2026
for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    if "2024" in name: continue
    m = fold_models[name]
    period = features[features["datetime"] >= test_start].copy()
    if test_end is not None:
        period = period[period["datetime"] < test_end].copy()
    
    period["Confidence"] = m.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    strat = period["StrategySignal"].astype(int)
    period["Signal"] = strat
    
    # Lấy các nến có sinh tín hiệu
    sig_bars = period[period["Signal"].isin([1, -1])].copy()
    sig_bars["Passed"] = (sig_bars["Confidence"] >= th).astype(int)
    
    print(f"\n--- {name} Phân tích định lượng tín hiệu (N={len(sig_bars)}) ---")
    for group_name, df_grp in [("ĐƯỢC GIỮ LẠI (Passed)", sig_bars[sig_bars["Passed"] == 1]), 
                               ("BỊ CHẶN BỎ  (Blocked)", sig_bars[sig_bars["Passed"] == 0])]:
        print(f"  * Nhóm {group_name} (N={len(df_grp)}):")
        print(f"    - Mean Confidence : {df_grp['Confidence'].mean():.4f}")
        print(f"    - Mean ATR (1m)   : {df_grp['ATR'].mean():.2f}")
        print(f"    - Mean ADX        : {df_grp['ADX'].mean():.2f}")
        print(f"    - Mean RSI        : {df_grp['RSI'].mean():.2f}")
        print(f"    - Tỷ lệ Long/Short: {sum(df_grp['Signal']==1)} Long / {sum(df_grp['Signal']==-1)} Short")

print("\n" + "="*80)
print("3. ĐO HIỆU QUẢ CỦA ENSEMBLE 10 SEEDS (SEEDS 40-49)")
print("="*80)

def round_tick(price: float) -> float:
    return round(price * 10.0) / 10.0

class FastBacktestEngine:
    def __init__(self, data, slippage=0.3, fee=15000.0, stop_mode="soft_15m"):
        self.data = data
        self.slip = slippage
        self.fee = fee
        self.stop_mode = stop_mode

    def run(self):
        trades = []
        pos = 0
        entry_price = 0.0
        entry_time = None
        trailing_sl = 0.0
        hard_sl = 0.0
        cooldown = 0

        for row in self.data.itertuples():
            t = row.Index
            op = row.Open
            hi = row.High
            lo = row.Low
            cl = row.Close
            sig = getattr(row, "Signal", 0)
            atr_1m = getattr(row, "ATR", 1.0)
            if np.isnan(atr_1m) or atr_1m <= 0: atr_1m = 1.0
            tr_atr = getattr(row, "HTF_5m_ATR", atr_1m * 2.0)
            if np.isnan(tr_atr) or tr_atr <= 0: tr_atr = atr_1m * 2.0

            if cooldown > 0: cooldown -= 1

            if pos != 0:
                raw_exit = None
                reason = ""
                is_atc = (t.hour == 14 and t.minute == 45)

                if pos == 1:
                    if lo <= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl >= entry_price and lo <= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif lo <= trailing_sl:
                        htf_rev = (getattr(row, "HTF_15m_TrendDownOK", 0) == 1 or 
                                   (getattr(row, "HTF_15m_TrendOK", 1) == 0 and getattr(row, "HTF_15m_TrendTransition", 1) == 0))
                        if htf_rev: raw_exit, reason = trailing_sl, "SL"
                    elif sig == -1: raw_exit, reason = cl, "Reversal"
                else:
                    if hi >= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_price and hi >= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif hi >= trailing_sl:
                        htf_rev = (getattr(row, "HTF_15m_TrendOK", 0) == 1 or 
                                   (getattr(row, "HTF_15m_TrendDownOK", 1) == 0 and getattr(row, "HTF_15m_TrendTransitionDown", 1) == 0))
                        if htf_rev: raw_exit, reason = trailing_sl, "SL"
                    elif sig == 1: raw_exit, reason = cl, "Reversal"

                if raw_exit is None:
                    if pos == 1: trailing_sl = max(trailing_sl, round_tick(cl - 1.5 * tr_atr))
                    else: trailing_sl = min(trailing_sl, round_tick(cl + 1.5 * tr_atr))

                if raw_exit is not None:
                    actual_base = raw_exit
                    if reason in ("Hard_SL", "SL"):
                        if pos == 1 and op < raw_exit: actual_base = op
                        elif pos == -1 and op > raw_exit: actual_base = op

                    s = 0.0 if is_atc else self.slip
                    exit_price = round_tick(actual_base - pos * s)
                    pnl_pts = (exit_price - entry_price) * pos
                    net_pnl = pnl_pts * 100000.0 - 2 * self.fee
                    trades.append({
                        "entry_time": entry_time, "exit_time": t, "pos": pos,
                        "entry_price": entry_price, "exit_price": exit_price,
                        "pts": pnl_pts, "net_pnl": net_pnl,
                        "win": 1 if net_pnl > 0 else 0, "reason": reason
                    })
                    pos = 0
                    cooldown = 15
                    continue

            if pos == 0 and cooldown == 0 and (t.hour < 14 or (t.hour == 14 and t.minute <= 25)):
                if sig in (1, -1):
                    entry_price = round_tick(cl + sig * self.slip)
                    entry_time = t
                    pos = sig
                    initial_atr = tr_atr
                    if pos == 1:
                        hard_sl = round_tick(entry_price - 2.5 * initial_atr)
                        trailing_sl = round_tick(entry_price - 1.0 * initial_atr)
                    else:
                        hard_sl = round_tick(entry_price + 2.5 * initial_atr)
                        trailing_sl = round_tick(entry_price + 1.0 * initial_atr)

        return pd.DataFrame(trades)

# Chạy ensemble 10 models (trung bình xác suất từ seed 40 đến 49)
ens_folds_tr = []
for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    train = dataset[dataset["exit_time"] < val_start]
    
    # Train 10 models
    models = []
    for s in range(40, 50):
        p = XGBOOST_PARAMS.copy()
        p["random_state"] = s
        m = xgb.XGBClassifier(**p)
        m.fit(train[ML_FEATURE_COLUMNS], train["label"])
        models.append(m)
        
    period = features[features["datetime"] >= test_start].copy()
    if test_end is not None:
        period = period[period["datetime"] < test_end].copy()
    
    # Lấy trung bình xác suất của 10 models
    prob_matrix = np.zeros((len(period), 10))
    x_input = period[ML_FEATURE_COLUMNS].fillna(0.0)
    for i, m in enumerate(models):
        prob_matrix[:, i] = m.predict_proba(x_input)[:, 1]
    
    period["Confidence"] = np.mean(prob_matrix, axis=1)
    strat = period["StrategySignal"].astype(int)
    sig = pd.Series(0, index=period.index, dtype=int)
    sig[(strat == 1) & (period["Confidence"] >= th)] = 1
    sig[(strat == -1) & (period["Confidence"] >= th)] = -1
    period["Signal"] = sig
    
    tr = FastBacktestEngine(period.set_index("datetime"), slippage=0.3, fee=15000.0, stop_mode="soft_15m").run()
    ens_folds_tr.append(tr)
    net_pnl = tr["net_pnl"].sum()
    wr = tr["win"].mean() * 100
    wins = tr[tr["net_pnl"] > 0]["net_pnl"].sum()
    losses = abs(tr[tr["net_pnl"] < 0]["net_pnl"].sum())
    pf = wins / losses if losses > 0 else 999.0
    print(f"Ensemble {name:18s} | Trades={len(tr):2d} | WR={wr:4.1f}% | Net PnL={net_pnl:>+11,.0f} VND | PF={pf:4.2f}")

all_ens_tr = pd.concat(ens_folds_tr, ignore_index=True)
tot_pnl = all_ens_tr["net_pnl"].sum()
tot_wr = all_ens_tr["win"].mean() * 100
wins = all_ens_tr[all_ens_tr["net_pnl"] > 0]["net_pnl"].sum()
losses = abs(all_ens_tr[all_ens_tr["net_pnl"] < 0]["net_pnl"].sum())
tot_pf = wins / losses if losses > 0 else 999.0
print(f"TỔNG ENSEMBLE (3 NĂM)       | Trades={len(all_ens_tr):2d} | WR={tot_wr:4.1f}% | Net PnL={tot_pnl:>+11,.0f} VND | PF={tot_pf:4.2f} | Exp={tot_pnl/len(all_ens_tr):>+8,.0f} VND")

