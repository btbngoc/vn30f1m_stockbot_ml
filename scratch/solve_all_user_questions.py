import sys
sys.path.insert(0, ".")
import math
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import roc_auc_score

sys.stdout.reconfigure(encoding='utf-8')

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import XGBOOST_PARAMS, FEATURES_PATH, DATASET_PATH
from trading_engine.backtest.config import BacktestConfig

def round_tick(price: float) -> float:
    return round(price * 10.0) / 10.0

def compute_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "pf": 0.0, "win_rate": 0.0, "exp_vnd": 0.0, "payoff": 0.0, "max_dd": 0.0}
    n = len(trades)
    net_pnl = trades["PnL"].sum()
    wins = trades[trades["PnL"] > 0]
    losses = trades[trades["PnL"] <= 0]
    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = n_wins / n if n > 0 else 0.0
    gross_win = wins["PnL"].sum() if n_wins > 0 else 0.0
    gross_loss = -losses["PnL"].sum() if n_losses > 0 else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else 99.0
    avg_win = gross_win / n_wins if n_wins > 0 else 0.0
    avg_loss = gross_loss / n_losses if n_losses > 0 else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else 0.0
    exp_vnd = net_pnl / n if n > 0 else 0.0
    equity = trades["PnL"].cumsum()
    max_dd = (equity.cummax() - equity).max()
    return {
        "trades": n,
        "net_pnl": net_pnl,
        "pf": pf,
        "win_rate": win_rate,
        "gross_win": gross_win,
        "gross_loss": gross_loss,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff": payoff,
        "exp_vnd": exp_vnd,
        "max_dd": max_dd
    }

class IsolatedEngine:
    def __init__(self, df: pd.DataFrame, config: BacktestConfig, stop_mode: str = "soft_15m", atr_source: str = "htf_5m_15m"):
        self.df = df
        self.config = config
        self.stop_mode = stop_mode # 'immediate_1m', 'immediate_5m', 'soft_15m'
        self.atr_source = atr_source # '1m', 'htf_5m_15m'
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
                            # Immediate exit
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
                            # Immediate exit
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
                        if position == 1 and op < raw_exit:
                            actual_exit_base = op
                        elif position == -1 and op > raw_exit:
                            actual_exit_base = op

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
                        "Initial Stop Loss": initial_sl,
                        "Stop Loss at Exit": trailing_sl,
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

def bootstrap_auc_ci(y_true, y_pred, n_boot=1000, seed=42):
    np.random.seed(seed)
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    n = len(y_true)
    scores = []
    for _ in range(n_boot):
        idx = np.random.randint(0, n, size=n)
        if len(np.unique(y_true[idx])) < 2:
            continue
        scores.append(roc_auc_score(y_true[idx], y_pred[idx]))
    return np.percentile(scores, 2.5), np.percentile(scores, 97.5)

# ==============================================================================
# PHẦN 1: AUC ĐỦ 3 FOLD TRƯỚC VÀ SAU PURGE KÈM 95% BOOTSTRAP CI
# ==============================================================================
print("\n" + "="*80)
print("PHẦN 1: ĐO LƯỜNG AUC TRÊN CẢ 3 FOLD TRƯỚC VÀ SAU PURGE (KÈM 95% CI)")
print("="*80)

trained_models = []
for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    train = dataset[dataset["exit_time"] < val_start]
    test = dataset[dataset["entry_time"] >= test_start]
    if test_end is not None:
        test = test[test["exit_time"] < test_end]
    
    # 1. Unpurged Model
    p = XGBOOST_PARAMS.copy()
    p["random_state"] = 42
    m_unp = xgb.XGBClassifier(**p)
    m_unp.fit(train[ML_FEATURE_COLUMNS], train["label"])
    trained_models.append(m_unp)
    pred_unp = m_unp.predict_proba(test[ML_FEATURE_COLUMNS])[:, 1]
    auc_unp = roc_auc_score(test["label"], pred_unp)
    ci_unp = bootstrap_auc_ci(test["label"], pred_unp)

    # 2. Purged Model
    train_p = purge_df_fast(train)
    test_p = purge_df_fast(test)
    m_p = xgb.XGBClassifier(**p)
    m_p.fit(train_p[ML_FEATURE_COLUMNS], train_p["label"])
    pred_p = m_p.predict_proba(test_p[ML_FEATURE_COLUMNS])[:, 1]
    auc_p = roc_auc_score(test_p["label"], pred_p)
    ci_p = bootstrap_auc_ci(test_p["label"], pred_p)

    print(f"{name:18s} | UNPURGED Test AUC: {auc_unp:.4f} [{ci_unp[0]:.4f}, {ci_unp[1]:.4f}] (N={len(test)})")
    print(f"{'':18s} | PURGED   Test AUC: {auc_p:.4f} [{ci_p[0]:.4f}, {ci_p[1]:.4f}] (N={len(test_p)})")
    print(f"{'':18s} | Delta AUC: {auc_p - auc_unp:+.4f}")
    print("-" * 80)

# ==============================================================================
# PHẦN 2: LAYER 1 THUẦN QUY TẮC Ở SLIP 0 VÀ PHÍ 0 (TÁCH TÍN HIỆU KHỎI CHI PHÍ)
# ==============================================================================
print("\n" + "="*80)
print("PHẦN 2: LAYER 1 THUẦN QUY TẮC Ở CÁC MỨC CHI PHÍ (TÁCH TÍN HIỆU KHỎI MA SÁT)")
print("="*80)

scenarios_l1 = [
    ("1. Không phí, Không trượt (Gross Pure Signal)", 0.0, 0.0),
    ("2. Trượt 0.1 pt, Không phí (Slippage Only)", 0.10, 0.0),
    ("3. Trượt 0.3 pt, Phí 30k (Thực tế đầy đủ)", 0.30, 15000.0)
]

for sc_name, slip, fee in scenarios_l1:
    cfg = BacktestConfig(slippage_points=slip, commission_per_contract=fee, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)
    all_tr = []
    print(f"\n--- {sc_name} ---")
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None:
            period = period[period["datetime"] < test_end].copy()
        period["Signal"] = period["StrategySignal"].astype(int)
        tr = IsolatedEngine(period.set_index("datetime"), config=cfg, stop_mode="soft_15m", atr_source="htf_5m_15m").run()
        st = compute_metrics(tr)
        all_tr.append(tr)
        print(f"  {name:18s} | N={st['trades']:3d} | WinRate={st['win_rate']*100:4.1f}% | Net PnL={st['net_pnl']:>+12,.0f} VND | PF={st['pf']:4.2f} | Exp={st['exp_vnd']:>+8,.0f} VND")
    
    c_st = compute_metrics(pd.concat(all_tr, ignore_index=True))
    print(f"  {'TỔNG LAYER 1':18s} | N={c_st['trades']:3d} | WinRate={c_st['win_rate']*100:4.1f}% | Net PnL={c_st['net_pnl']:>+12,.0f} VND | PF={c_st['pf']:4.2f} | Exp={c_st['exp_vnd']:>+8,.0f} VND")

# ==============================================================================
# PHẦN 3: TÁCH RIÊNG 2 YẾU TỐ CỦA SOFT SL (KHOẢNG CÁCH STOP vs CHỜ 15M)
# ==============================================================================
print("\n" + "="*80)
print("PHẦN 3: TÁCH KHOẢNG CÁCH STOP (1M vs 5M ATR) KHỎI CƠ CHẾ CHỜ NẾN 15M")
print("Cấu hình: Trượt giá 0.3 pt, Phí 30k round-trip, Không dùng Short Gate")
print("="*80)

variants_sl = [
    ("A. Stop 1m ATR, Cắt tức thì (Không chờ 15m)", "immediate_1m", "1m"),
    ("B. Stop 5m ATR, Cắt tức thì (Khoảng cách rộng, Không chờ 15m)", "immediate_5m", "htf_5m_15m"),
    ("C. Stop 5m ATR, Chờ nến 15m xác nhận (Soft SL đầy đủ)", "soft_15m", "htf_5m_15m"),
]

cfg_real = BacktestConfig(slippage_points=0.30, commission_per_contract=15000.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)

for v_name, s_mode, a_src in variants_sl:
    all_tr = []
    print(f"\n--- {v_name} ---")
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None:
            period = period[period["datetime"] < test_end].copy()
        prob = trained_models[idx].predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
        period["Confidence"] = prob
        strat = period["StrategySignal"].astype(int)
        sig = pd.Series(0, index=period.index, dtype=int)
        sig[(strat == 1) & (period["Confidence"] >= th)] = 1
        sig[(strat == -1) & (period["Confidence"] >= th)] = -1 # No gate
        period["Signal"] = sig
        
        tr = IsolatedEngine(period.set_index("datetime"), config=cfg_real, stop_mode=s_mode, atr_source=a_src).run()
        st = compute_metrics(tr)
        all_tr.append(tr)
        print(f"  {name:18s} | N={st['trades']:2d} | WinRate={st['win_rate']*100:4.1f}% | Net PnL={st['net_pnl']:>+12,.0f} VND | PF={st['pf']:4.2f}")
    
    c_st = compute_metrics(pd.concat(all_tr, ignore_index=True))
    print(f"  {'TỔNG OOS':18s} | N={c_st['trades']:2d} | WinRate={c_st['win_rate']*100:4.1f}% | Net PnL={c_st['net_pnl']:>+12,.0f} VND | PF={c_st['pf']:4.2f} | Exp={c_st['exp_vnd']:>+8,.0f} VND")

# ==============================================================================
# PHẦN 4: MULTI-SEED MONTE CARLO STABILITY (10 SEEDS CHO XGBOOST)
# ==============================================================================
print("\n" + "="*80)
print("PHẦN 4: KIỂM ĐỊNH ĐỘ BIẾN THIÊN QUA 10 SEEDS NGẪU NHIÊN CỦA XGBOOST")
print("="*80)

seed_pnls = []
seed_pfs = []
seeds = [40, 41, 42, 43, 44, 45, 46, 47, 48, 49]

for s in seeds:
    all_s_tr = []
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
        sig[(strat == -1) & (period["Confidence"] >= th)] = -1 # No gate
        period["Signal"] = sig
        
        tr = IsolatedEngine(period.set_index("datetime"), config=cfg_real, stop_mode="soft_15m", atr_source="htf_5m_15m").run()
        all_s_tr.append(tr)
    
    c_s = compute_metrics(pd.concat(all_s_tr, ignore_index=True))
    seed_pnls.append(c_s["net_pnl"])
    seed_pfs.append(c_s["pf"])
    print(f"Seed {s:2d} | Trades={c_s['trades']:3d} | WinRate={c_s['win_rate']*100:4.1f}% | Net PnL={c_s['net_pnl']:>+12,.0f} VND | PF={c_s['pf']:4.2f}")

print("\n--- TỔNG KẾT PHÂN PHỐI 10 SEEDS ---")
print(f"Net PnL Trung bình: {np.mean(seed_pnls):>+12,.0f} VND (Độ lệch chuẩn std: {np.std(seed_pnls):,.0f} VND)")
print(f"Min PnL: {np.min(seed_pnls):>+12,.0f} VND | Max PnL: {np.max(seed_pnls):>+12,.0f} VND")
print(f"PF Trung bình: {np.mean(seed_pfs):.2f} (Min PF: {np.min(seed_pfs):.2f}, Max PF: {np.max(seed_pfs):.2f})")
print("\nHoàn tất toàn bộ 5 phần thực nghiệm chuyên sâu.")

