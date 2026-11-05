import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import XGBOOST_PARAMS, FEATURES_PATH, DATASET_PATH
from trading_engine.backtest.config import BacktestConfig

def round_tick(price: float) -> float:
    return round(price * 10.0) / 10.0

def compute_metrics(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "pf": 0.0, "win_rate": 0.0, "exp_vnd": 0.0}
    n = len(trades)
    net_pnl = trades["PnL"].sum()
    wins = trades[trades["PnL"] > 0]
    losses = trades[trades["PnL"] <= 0]
    win_rate = len(wins) / n if n > 0 else 0.0
    gross_win = wins["PnL"].sum() if len(wins) > 0 else 0.0
    gross_loss = -losses["PnL"].sum() if len(losses) > 0 else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else 99.0
    exp_vnd = net_pnl / n if n > 0 else 0.0
    return {"trades": n, "net_pnl": net_pnl, "pf": pf, "win_rate": win_rate, "exp_vnd": exp_vnd}

class IsolatedEngine:
    def __init__(self, df: pd.DataFrame, config: BacktestConfig, stop_mode: str = "soft_15m", atr_source: str = "htf_5m_15m"):
        self.df = df
        self.config = config
        self.stop_mode = stop_mode
        self.atr_source = atr_source
        self.trade_log = []

    def run(self):
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
                        if self.stop_mode == "soft_15m":
                            htf_reversal_down = (row.get("HTF_15m_TrendDownOK", 0) == 1 or row.get("HTF_15m_TrendTransitionDown", 0) == 1)
                            if htf_reversal_down:
                                raw_exit, reason = trailing_sl, "SL"
                        else:
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == -1:
                        raw_exit, reason = close, "Reversal"
                else:
                    if high >= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_price and high >= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
                    elif high >= trailing_sl:
                        if self.stop_mode == "soft_15m":
                            htf_reversal = (row.get("HTF_15m_TrendOK", 0) == 1 or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0))
                            if htf_reversal:
                                raw_exit, reason = trailing_sl, "SL"
                        else:
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == 1:
                        raw_exit, reason = close, "Reversal"

                if raw_exit is None and atr > 0:
                    trailing_atr = atr if self.atr_source == "1m" else float(row.get("HTF_5m_ATR", atr * 2.0))
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

                    self.trade_log.append({
                        "Entry Date": entry_date,
                        "Exit Date": timestamp,
                        "Type": "LONG" if position == 1 else "SHORT",
                        "Contracts": contracts,
                        "Entry": entry_price,
                        "Exit": exit_price,
                        "Points": pts,
                        "PnL": net_pnl,
                        "Reason": reason,
                        "Confidence": confidence,
                        "IsOvernight": is_overnight,
                        "BarsHeld": bars_held
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
                if self.atr_source == "1m":
                    trade_atr = atr
                else:
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

        return pd.DataFrame(self.trade_log)

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

# ==============================================================================
# BÀI TOÁN 1: BIẾN THỂ B vs C QUA 10 SEEDS (SEEDS 40-49)
# ==============================================================================
print("="*80)
print("BÀI TOÁN 1: KIỂM NGHIỆM BIẾN THỂ B vs C QUA 10 SEEDS (SEEDS 40-49)")
print("="*80)

seeds = list(range(40, 50))
b_pnls, b_pfs = [], []
c_pnls, c_pfs = [], []
deltas_pnl = []

for s in seeds:
    b_tr_all, c_tr_all = [], []
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        train = dataset[dataset["exit_time"] < val_start]
        p = XGBOOST_PARAMS.copy()
        p["random_state"] = s
        m = xgb.XGBClassifier(**p)
        m.fit(train[ML_FEATURE_COLUMNS], train["label"])

        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None:
            period = period[period["datetime"] < test_end].copy()
        prob = m.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
        period["Confidence"] = prob
        strat = period["StrategySignal"].astype(int)
        sig = pd.Series(0, index=period.index, dtype=int)
        sig[(strat == 1) & (period["Confidence"] >= th)] = 1
        sig[(strat == -1) & (period["Confidence"] >= th)] = -1
        period["Signal"] = sig
        period_df = period.set_index("datetime")

        # Run B
        tr_b = IsolatedEngine(period_df, config=cfg_real, stop_mode="immediate_5m", atr_source="htf_5m_15m").run()
        b_tr_all.append(tr_b)

        # Run C
        tr_c = IsolatedEngine(period_df, config=cfg_real, stop_mode="soft_15m", atr_source="htf_5m_15m").run()
        c_tr_all.append(tr_c)

    res_b = pd.concat(b_tr_all, ignore_index=True)
    res_c = pd.concat(c_tr_all, ignore_index=True)
    st_b = compute_metrics(res_b)
    st_c = compute_metrics(res_c)

    b_pnls.append(st_b["net_pnl"])
    b_pfs.append(st_b["pf"])
    c_pnls.append(st_c["net_pnl"])
    c_pfs.append(st_c["pf"])
    d_pnl = st_c["net_pnl"] - st_b["net_pnl"]
    deltas_pnl.append(d_pnl)
    print(f"Seed {s:2d} | B: PnL={st_b['net_pnl']:>+10,.0f} (PF {st_b['pf']:.2f}) | C: PnL={st_c['net_pnl']:>+10,.0f} (PF {st_c['pf']:.2f}) | Delta (C-B)={d_pnl:>+10,.0f} VND")

print("\n--- THỐNG KÊ PHÂN PHỐI 10 SEEDS (B vs C) ---")
print(f"Biến thể B (Cắt tức thì 5m ATR):")
print(f"  Mean PnL   : {np.mean(b_pnls):>+10,.0f} VND (std: {np.std(b_pnls):,.0f})")
print(f"  Median PnL : {np.median(b_pnls):>+10,.0f} VND [Q1: {np.percentile(b_pnls, 25):>+10,.0f}, Q3: {np.percentile(b_pnls, 75):>+10,.0f}]")
print(f"  Mean PF    : {np.mean(b_pfs):.2f} (Min {np.min(b_pfs):.2f}, Max {np.max(b_pfs):.2f})")
print(f"Biến thể C (Chờ xác nhận nến 15m - Soft SL):")
print(f"  Mean PnL   : {np.mean(c_pnls):>+10,.0f} VND (std: {np.std(c_pnls):,.0f})")
print(f"  Median PnL : {np.median(c_pnls):>+10,.0f} VND [Q1: {np.percentile(c_pnls, 25):>+10,.0f}, Q3: {np.percentile(c_pnls, 75):>+10,.0f}]")
print(f"  Mean PF    : {np.mean(c_pfs):.2f} (Min {np.min(c_pfs):.2f}, Max {np.max(c_pfs):.2f})")
print(f"Độ vượt trội Delta (C - B):")
print(f"  Mean Delta : {np.mean(deltas_pnl):>+10,.0f} VND (std: {np.std(deltas_pnl):,.0f})")
print(f"  Tỷ lệ C > B: {sum(d > 0 for d in deltas_pnl)} / 10 seeds ({sum(d > 0 for d in deltas_pnl)*10}%)")

# ==============================================================================
# BÀI TOÁN 2: LOOKAHEAD TRONG FEATURE ĐA KHUNG (HTF LAG 1 NẾN)
# ==============================================================================
print("\n" + "="*80)
print("BÀI TOÁN 2: KIỂM TRA RÒ RỈ FEATURE ĐA KHUNG (LAG 1 NẾN CHO TOÀN BỘ HTF FEATURES)")
print("="*80)

htf_cols = [c for c in ML_FEATURE_COLUMNS if "HTF_" in c]
print(f"Các cột HTF trong feature set ({len(htf_cols)} cột): {htf_cols}")

dataset_lagged = dataset.copy()
dataset_lagged[htf_cols] = dataset_lagged[htf_cols].shift(1).bfill()

def purge_df_fast(df_sub):
    entry_arr = df_sub["entry_time"].values
    exit_arr = df_sub["exit_time"].values
    selected = []
    last_exit = pd.Timestamp.min
    for i in range(len(entry_arr)):
        en = pd.Timestamp(entry_arr[i])
        if en >= last_exit:
            selected.append(i)
            last_exit = pd.Timestamp(exit_arr[i]) + pd.Timedelta(minutes=15)
    return df_sub.iloc[selected]

for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    tr_raw = dataset[dataset["exit_time"] < val_start]
    te_raw = dataset[dataset["entry_time"] >= test_start]
    if test_end is not None: te_raw = te_raw[te_raw["exit_time"] < test_end]

    tr_lag = dataset_lagged[dataset_lagged["exit_time"] < val_start]
    te_lag = dataset_lagged[dataset_lagged["entry_time"] >= test_start]
    if test_end is not None: te_lag = te_lag[te_lag["exit_time"] < test_end]

    p = XGBOOST_PARAMS.copy()
    p["random_state"] = 42

    # Unpurged
    m_raw = xgb.XGBClassifier(**p).fit(tr_raw[ML_FEATURE_COLUMNS], tr_raw["label"])
    auc_unp_raw = roc_auc_score(te_raw["label"], m_raw.predict_proba(te_raw[ML_FEATURE_COLUMNS])[:, 1])

    m_lag = xgb.XGBClassifier(**p).fit(tr_lag[ML_FEATURE_COLUMNS], tr_lag["label"])
    auc_unp_lag = roc_auc_score(te_lag["label"], m_lag.predict_proba(te_lag[ML_FEATURE_COLUMNS])[:, 1])

    # Purged
    tr_raw_p = purge_df_fast(tr_raw)
    te_raw_p = purge_df_fast(te_raw)
    m_raw_p = xgb.XGBClassifier(**p).fit(tr_raw_p[ML_FEATURE_COLUMNS], tr_raw_p["label"])
    auc_p_raw = roc_auc_score(te_raw_p["label"], m_raw_p.predict_proba(te_raw_p[ML_FEATURE_COLUMNS])[:, 1])

    tr_lag_p = purge_df_fast(tr_lag)
    te_lag_p = purge_df_fast(te_lag)
    m_lag_p = xgb.XGBClassifier(**p).fit(tr_lag_p[ML_FEATURE_COLUMNS], tr_lag_p["label"])
    auc_p_lag = roc_auc_score(te_lag_p["label"], m_lag_p.predict_proba(te_lag_p[ML_FEATURE_COLUMNS])[:, 1])

    print(f"{name:18s} | UNPURGED AUC: Gốc {auc_unp_raw:.4f} -> Lagged {auc_unp_lag:.4f} (Delta {auc_unp_lag - auc_unp_raw:+.4f})")
    print(f"{'':18s} | PURGED   AUC: Gốc {auc_p_raw:.4f} -> Lagged {auc_p_lag:.4f} (Delta {auc_p_lag - auc_p_raw:+.4f})")
    print("-" * 80)

# ==============================================================================
# BÀI TOÁN 3: LỆCH PHA LAYER 1 GROSS VÀ ML FILTER THEO NĂM
# ==============================================================================
print("\n" + "="*80)
print("BÀI TOÁN 3: ĐIỀU TRA LỆCH PHA GIỮA LAYER 1 GROSS VÀ ML FILTER THEO NĂM")
print("="*80)

for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    train = dataset[dataset["exit_time"] < val_start]
    p = XGBOOST_PARAMS.copy()
    p["random_state"] = 42
    m = xgb.XGBClassifier(**p).fit(train[ML_FEATURE_COLUMNS], train["label"])

    period = features[features["datetime"] >= test_start].copy()
    if test_end is not None: period = period[period["datetime"] < test_end].copy()
    period["Confidence"] = m.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    
    # Layer 1 Gross (Signal = StrategySignal, Slip=0, Fee=0)
    cfg_zero = BacktestConfig(slippage_points=0.0, commission_per_contract=0.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)
    period["Signal"] = period["StrategySignal"].astype(int)
    tr_l1 = IsolatedEngine(period.set_index("datetime"), config=cfg_zero, stop_mode="soft_15m").run()

    # Match confidence
    conf_map = period.set_index("datetime")["Confidence"].to_dict()
    tr_l1["Confidence"] = tr_l1["Entry Date"].map(conf_map)
    tr_l1["Passed_ML"] = (tr_l1["Confidence"] >= th).astype(int)

    passed = tr_l1[tr_l1["Passed_ML"] == 1]
    blocked = tr_l1[tr_l1["Passed_ML"] == 0]

    print(f"\n--- {name} (Ngưỡng ML = {th}) ---")
    print(f"Tổng L1 Gross Trades: {len(tr_l1)} | Gross PnL: {tr_l1['PnL'].sum():>+11,.0f} VND")
    print(f"  • ML GIỮ LẠI (Passed) : N={len(passed):2d} ({len(passed)/len(tr_l1)*100:4.1f}%) | Gross PnL={passed['PnL'].sum():>+11,.0f} VND | WR={len(passed[passed['PnL']>0])/len(passed)*100 if len(passed)>0 else 0:4.1f}%")
    print(f"  • ML CHẶN BỎ (Blocked): N={len(blocked):2d} ({len(blocked)/len(tr_l1)*100:4.1f}%) | Gross PnL={blocked['PnL'].sum():>+11,.0f} VND | WR={len(blocked[blocked['PnL']>0])/len(blocked)*100 if len(blocked)>0 else 0:4.1f}%")
    
    long_pass = passed[passed["Type"] == "LONG"]
    short_pass = passed[passed["Type"] == "SHORT"]
    long_block = blocked[blocked["Type"] == "LONG"]
    short_block = blocked[blocked["Type"] == "SHORT"]
    print(f"    - Passed LONG : N={len(long_pass):2d} | Gross PnL={long_pass['PnL'].sum():>+10,.0f} VND")
    print(f"    - Passed SHORT: N={len(short_pass):2d} | Gross PnL={short_pass['PnL'].sum():>+10,.0f} VND")
    print(f"    - Blocked LONG: N={len(long_block):2d} | Gross PnL={long_block['PnL'].sum():>+10,.0f} VND")
    print(f"    - Blocked SHORT: N={len(short_block):2d} | Gross PnL={short_block['PnL'].sum():>+10,.0f} VND")

# ==============================================================================
# BÀI TOÁN 4: ĐO NGƯỠNG HÒA VỐN MA SÁT (BREAKEVEN SLIPPAGE)
# ==============================================================================
print("\n" + "="*80)
print("BÀI TOÁN 4: ĐO NGƯỠNG HÒA VỐN MA SÁT (BREAKEVEN SLIPPAGE)")
print("="*80)

slip_grid = [0.00, 0.05, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

print("Quét mức trượt giá (với phí cố định 30,000 VND / hợp đồng round-trip):")
print(f"{'Trượt (pt)':<12} | {'L1 Thuần Quy Tắc (Net PnL / PF)':<35} | {'L1 + ML Filter (Net PnL / PF)':<35}")
print("-" * 85)

for sl in slip_grid:
    cfg_test = BacktestConfig(slippage_points=sl, commission_per_contract=15000.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)
    
    # 1. L1
    l1_tr = []
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None: period = period[period["datetime"] < test_end].copy()
        period["Signal"] = period["StrategySignal"].astype(int)
        tr = IsolatedEngine(period.set_index("datetime"), config=cfg_test, stop_mode="soft_15m").run()
        l1_tr.append(tr)
    st_l1 = compute_metrics(pd.concat(l1_tr, ignore_index=True))

    # 2. L1 + ML (Seed 42)
    ml_tr = []
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        train = dataset[dataset["exit_time"] < val_start]
        p = XGBOOST_PARAMS.copy()
        p["random_state"] = 42
        m = xgb.XGBClassifier(**p).fit(train[ML_FEATURE_COLUMNS], train["label"])

        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None: period = period[period["datetime"] < test_end].copy()
        period["Confidence"] = m.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
        strat = period["StrategySignal"].astype(int)
        sig = pd.Series(0, index=period.index, dtype=int)
        sig[(strat == 1) & (period["Confidence"] >= th)] = 1
        sig[(strat == -1) & (period["Confidence"] >= th)] = -1
        period["Signal"] = sig
        tr = IsolatedEngine(period.set_index("datetime"), config=cfg_test, stop_mode="soft_15m").run()
        ml_tr.append(tr)
    st_ml = compute_metrics(pd.concat(ml_tr, ignore_index=True))

    print(f"{sl:8.2f} pt   | Net PnL={st_l1['net_pnl']:>+11,.0f} (PF {st_l1['pf']:4.2f})       | Net PnL={st_ml['net_pnl']:>+11,.0f} (PF {st_ml['pf']:4.2f})")

print("\nHoàn tất toàn bộ tính toán.")
