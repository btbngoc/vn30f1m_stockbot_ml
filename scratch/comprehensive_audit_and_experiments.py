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

class ConfigurableEngine:
    def __init__(self, df: pd.DataFrame, config: BacktestConfig, gap_aware: bool = True, atc_slip: float = 0.0, soft_sl: bool = True):
        self.df = df
        self.config = config
        self.gap_aware = gap_aware
        self.atc_slip = atc_slip
        self.soft_sl = soft_sl
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
                        if self.soft_sl:
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
                        if self.soft_sl:
                            htf_reversal = (row.get("HTF_15m_TrendOK", 0) == 1 or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0))
                            if htf_reversal:
                                raw_exit, reason = trailing_sl, "SL"
                        else:
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

                    if self.gap_aware and reason in ("Hard_SL", "SL"):
                        if position == 1 and op < raw_exit:
                            actual_exit_base = op
                        elif position == -1 and op > raw_exit:
                            actual_exit_base = op

                    slip = self.atc_slip if is_atc else self.config.slippage_points
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
                trade_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                initial_sl = round_tick(entry_price - position * self.config.stop_loss_atr * trade_atr)
                trailing_sl = initial_sl
                hsl_mult = getattr(self.config, "hard_sl_atr_mult", 2.5)
                hard_sl = round_tick(entry_price - position * hsl_mult * self.config.stop_loss_atr * trade_atr)
                confidence = float(row.get("Confidence", 1.0))
                bars_held = 0

        return pd.DataFrame(self.trade_log)

print("Libraries and engines compiled.")

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

trained_models = []
for (name, val_start, test_start, test_end, th) in FOLDS:
    train = dataset[dataset["exit_time"] < val_start]
    params = XGBOOST_PARAMS.copy()
    params["random_state"] = 42
    model = xgb.XGBClassifier(**params)
    model.fit(train[ML_FEATURE_COLUMNS], train["label"])
    trained_models.append(model)

cfg_std = BacktestConfig(slippage_points=0.30, commission_per_contract=15000.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)

# ==============================================================================
# EXPERIMENT 1: ĐỐI SOÁT HAI BIẾN THỂ ATC TRÊN CÙNG MỘT MÃ NGUỒN VÀ ROUND_TICK
# ==============================================================================
print("\n" + "="*80)
print("THÍ NGHIỆM 1: ĐỐI SOÁT 2 BIẾN THỂ ATC TRÊN CÙNG CODE (ROUND_TICK 0.1 PT)")
print("="*80)

for atc_name, atc_slip_val in [("Variant 1 (ATC slip = 0.0)", 0.0), ("Variant 2 (ATC slip = 0.3)", 0.30)]:
    all_tr = []
    print(f"\n--- {atc_name} ---")
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None:
            period = period[period["datetime"] < test_end].copy()
        prob = trained_models[idx].predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
        period["Confidence"] = prob
        strat = period["StrategySignal"].astype(int)
        short_gate = ((period["MarketRegime"] == "TREND_DOWN") | (period.get("HTF_15m_TrendDownOK", 0) == 1) | (period.get("HTF_15m_TrendTransitionDown", 0) == 1))
        sig = pd.Series(0, index=period.index, dtype=int)
        sig[(strat == 1) & (period["Confidence"] >= th)] = 1
        sig[(strat == -1) & (period["Confidence"] >= th) & short_gate] = -1
        period["Signal"] = sig
        
        engine = ConfigurableEngine(period.set_index("datetime"), config=cfg_std, gap_aware=True, atc_slip=atc_slip_val, soft_sl=True)
        tr = engine.run()
        st = compute_metrics(tr)
        all_tr.append(tr)
        print(f"  {name:18s} | N={st['trades']:2d} | WinRate={st['win_rate']*100:4.1f}% | Net PnL={st['net_pnl']:>+12,.0f} VND | PF={st['pf']:4.2f}")
    
    comb = pd.concat(all_tr, ignore_index=True)
    c_st = compute_metrics(comb)
    print(f"  {'TỔNG OOS':18s} | N={c_st['trades']:2d} | WinRate={c_st['win_rate']*100:4.1f}% | Net PnL={c_st['net_pnl']:>+12,.0f} VND | PF={c_st['pf']:4.2f} | Exp={c_st['exp_vnd']:>+8,.0f} VND/lệnh")

# ==============================================================================
# EXPERIMENT 2: ĐO LƯỜNG LAYER 1 THUẦN QUY TẮC (PURE RULES, BỎ HOÀN TOÀN ML)
# ==============================================================================
print("\n" + "="*80)
print("THÍ NGHIỆM 2: LAYER 1 THUẦN QUY TẮC (PURE STRATEGY SIGNAL, NO ML FILTER)")
print("Cấu hình: Trượt giá 0.3 pt, Thuế phí 30k round-trip, Gap-aware, Soft SL")
print("="*80)

all_l1_trades = []
for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    period = features[features["datetime"] >= test_start].copy()
    if test_end is not None:
        period = period[period["datetime"] < test_end].copy()
    # No ML filter: use raw StrategySignal directly
    period["Signal"] = period["StrategySignal"].astype(int)
    engine = ConfigurableEngine(period.set_index("datetime"), config=cfg_std, gap_aware=True, atc_slip=0.0, soft_sl=True)
    tr = engine.run()
    st = compute_metrics(tr)
    all_l1_trades.append(tr)
    print(f"  {name:18s} | N={st['trades']:3d} | WinRate={st['win_rate']*100:4.1f}% | Net PnL={st['net_pnl']:>+12,.0f} VND | PF={st['pf']:4.2f} | Exp={st['exp_vnd']:>+8,.0f} VND")

comb_l1 = pd.concat(all_l1_trades, ignore_index=True)
c_l1 = compute_metrics(comb_l1)
print(f"  {'TỔNG OOS LAYER 1':18s} | N={c_l1['trades']:3d} | WinRate={c_l1['win_rate']*100:4.1f}% | Net PnL={c_l1['net_pnl']:>+12,.0f} VND | PF={c_l1['pf']:4.2f} | Exp={c_l1['exp_vnd']:>+8,.0f} VND")

# ==============================================================================
# EXPERIMENT 3: SHORT REGIME GATE (CÓ vs KHÔNG CÓ TRÊN CẢ 3 NĂM)
# ==============================================================================
print("\n" + "="*80)
print("THÍ NGHIỆM 3: SHORT REGIME GATE (KIỂM ĐỊNH HIỆU QUẢ TRÊN CẢ 3 NĂM)")
print("="*80)

for gate_mode in [True, False]:
    mode_name = "CÓ Short Regime Gate (Đã chỉnh)" if gate_mode else "KHÔNG CÓ Gate (Bản thuần gốc)"
    all_gate_tr = []
    print(f"\n--- {mode_name} ---")
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None:
            period = period[period["datetime"] < test_end].copy()
        prob = trained_models[idx].predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
        period["Confidence"] = prob
        strat = period["StrategySignal"].astype(int)
        short_gate = ((period["MarketRegime"] == "TREND_DOWN") | (period.get("HTF_15m_TrendDownOK", 0) == 1) | (period.get("HTF_15m_TrendTransitionDown", 0) == 1))
        sig = pd.Series(0, index=period.index, dtype=int)
        sig[(strat == 1) & (period["Confidence"] >= th)] = 1
        if gate_mode:
            sig[(strat == -1) & (period["Confidence"] >= th) & short_gate] = -1
        else:
            sig[(strat == -1) & (period["Confidence"] >= th)] = -1
        period["Signal"] = sig
        
        engine = ConfigurableEngine(period.set_index("datetime"), config=cfg_std, gap_aware=True, atc_slip=0.0, soft_sl=True)
        tr = engine.run()
        st = compute_metrics(tr)
        all_gate_tr.append(tr)
        print(f"  {name:18s} | N={st['trades']:2d} | WinRate={st['win_rate']*100:4.1f}% | Net PnL={st['net_pnl']:>+12,.0f} VND | PF={st['pf']:4.2f}")
    
    c_gate = compute_metrics(pd.concat(all_gate_tr, ignore_index=True))
    print(f"  {'TỔNG OOS':18s} | N={c_gate['trades']:2d} | WinRate={c_gate['win_rate']*100:4.1f}% | Net PnL={c_gate['net_pnl']:>+12,.0f} VND | PF={c_gate['pf']:4.2f}")

# ==============================================================================
# EXPERIMENT 4: SOFT STOP LOSS (CÓ vs KHÔNG CÓ TRÊN CẢ 3 NĂM)
# ==============================================================================
print("\n" + "="*80)
print("THÍ NGHIỆM 4: SOFT STOP LOSS (CÓ CHỜ 15M ĐẢO CHIỀU vs CẮT LỖ LẬP TỨC)")
print("="*80)

for soft_mode in [True, False]:
    mode_name = "CÓ Soft SL (Chờ nến 15m xác nhận)" if soft_mode else "KHÔNG Soft SL (Cắt lỗ tức thì khi chạm)"
    all_soft_tr = []
    print(f"\n--- {mode_name} ---")
    for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
        period = features[features["datetime"] >= test_start].copy()
        if test_end is not None:
            period = period[period["datetime"] < test_end].copy()
        prob = trained_models[idx].predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
        period["Confidence"] = prob
        strat = period["StrategySignal"].astype(int)
        short_gate = ((period["MarketRegime"] == "TREND_DOWN") | (period.get("HTF_15m_TrendDownOK", 0) == 1) | (period.get("HTF_15m_TrendTransitionDown", 0) == 1))
        sig = pd.Series(0, index=period.index, dtype=int)
        sig[(strat == 1) & (period["Confidence"] >= th)] = 1
        sig[(strat == -1) & (period["Confidence"] >= th) & short_gate] = -1
        period["Signal"] = sig
        
        engine = ConfigurableEngine(period.set_index("datetime"), config=cfg_std, gap_aware=True, atc_slip=0.0, soft_sl=soft_mode)
        tr = engine.run()
        st = compute_metrics(tr)
        all_soft_tr.append(tr)
        print(f"  {name:18s} | N={st['trades']:2d} | WinRate={st['win_rate']*100:4.1f}% | Net PnL={st['net_pnl']:>+12,.0f} VND | PF={st['pf']:4.2f}")
    
    c_soft = compute_metrics(pd.concat(all_soft_tr, ignore_index=True))
    print(f"  {'TỔNG OOS':18s} | N={c_soft['trades']:2d} | WinRate={c_soft['win_rate']*100:4.1f}% | Net PnL={c_soft['net_pnl']:>+12,.0f} VND | PF={c_soft['pf']:4.2f}")

print("\nHoàn tất toàn bộ thí nghiệm kiểm định.")
