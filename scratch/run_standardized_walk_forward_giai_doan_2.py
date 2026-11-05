import sys
sys.path.insert(0, ".")
import math
import json
from pathlib import Path
import pandas as pd
import numpy as np
import xgboost as xgb

sys.stdout.reconfigure(encoding='utf-8')

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import DATASET_PATH, FEATURES_PATH, XGBOOST_PARAMS
from trading_engine.backtest.config import BacktestConfig

def round_tick(price: float) -> float:
    return round(price * 10.0) / 10.0

dataset = pd.read_csv(DATASET_PATH)
dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
features = pd.read_parquet(FEATURES_PATH)
features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")

FOLDS = [
    ("Fold 1 (OOS 2024)", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), 0.55),
    ("Fold 2 (OOS 2025)", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), 0.50),
    ("Fold 3 (OOS 2026)", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), None, 0.55),
]

# Train models with fixed random_state = 42
trained_models = []
for (name, val_start, test_start, test_end, th) in FOLDS:
    train = dataset[dataset["exit_time"] < val_start]
    params = XGBOOST_PARAMS.copy()
    params["random_state"] = 42
    model = xgb.XGBClassifier(**params)
    model.fit(train[ML_FEATURE_COLUMNS], train["label"])
    trained_models.append(model)

class StandardizedEngine:
    def __init__(self, df: pd.DataFrame, config: BacktestConfig, gap_aware: bool = True):
        self.df = df
        self.config = config
        self.gap_aware = gap_aware
        self.initial_capital = 100_000_000.0
        self.trade_log = []

    def run(self):
        position = 0
        entry_price = entry_date = None
        contracts = 1
        initial_sl = trailing_sl = hard_sl = tp = 0.0
        confidence = 1.0
        cooldown_remaining = 0
        bars_held = 0
        equity = self.initial_capital

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

                if self.config.flat_before_atc and (timestamp.hour == 14 and timestamp.minute >= 25):
                    raw_exit, reason = op, "Flat_Before_ATC"
                elif position == 1:
                    # LONG position exits
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
                    # SHORT position exits
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

                # Update trailing stop for next bar
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

                    # ATC is auction match, no market order slippage
                    slip = 0.0 if is_atc else self.config.slippage_points
                    exit_price = round_tick(actual_exit_base - position * slip)

                    gross_pnl = (exit_price - entry_price) * position * contracts * self.config.point_multiplier
                    fees = 2 * contracts * self.config.commission_per_contract
                    net_pnl = gross_pnl - fees
                    pts = (exit_price - entry_price) * position

                    # Check if overnight trade
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
                    equity += net_pnl
                    position = 0
                    cooldown_remaining = self.config.cooldown_bars
                    continue

            if position == 0 and signal and cooldown_remaining == 0:
                if self.config.flat_before_atc and (timestamp.hour == 14 and timestamp.minute >= 25):
                    continue
                atr = row.get("ATR", 0.0)
                if atr <= 0:
                    continue
                position = signal
                entry_date = timestamp
                entry_price = round_tick(close + position * self.config.slippage_points)
                if position == 1:
                    setup = str(row.get("EntrySetup", ""))
                    trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "SPRING" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
                else:
                    setup = str(row.get("EntrySetup", ""))
                    trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "UTAD" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
                
                initial_sl = round_tick(entry_price - position * self.config.stop_loss_atr * trade_atr)
                trailing_sl = initial_sl
                hsl_mult = getattr(self.config, "hard_sl_atr_mult", 2.5)
                hard_sl = round_tick(entry_price - position * hsl_mult * self.config.stop_loss_atr * trade_atr)
                confidence = float(row.get("Confidence", 1.0))
                bars_held = 0

        return pd.DataFrame(self.trade_log)

def run_fold_backtest(model, features, start, end, threshold, slippage=0.30, gap_aware=True):
    period = features[features["datetime"] >= start].copy()
    if end is not None:
        period = period[period["datetime"] < end].copy()
    
    prob = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period["Confidence"] = prob
    strat = period["StrategySignal"].astype(int)
    pass_long = period["Confidence"] >= threshold
    pass_short = period["Confidence"] >= threshold
    short_gate = (
        (period["MarketRegime"] == "TREND_DOWN")
        | (period.get("HTF_15m_TrendDownOK", 0) == 1)
        | (period.get("HTF_15m_TrendTransitionDown", 0) == 1)
    )
    sig = pd.Series(0, index=period.index, dtype=int)
    sig[(strat == 1) & pass_long] = 1
    sig[(strat == -1) & pass_short & short_gate] = -1
    period["Signal"] = sig

    cfg = BacktestConfig(
        slippage_points=slippage,
        commission_per_contract=15_000.0,
        fixed_contracts=1,
        take_profit_atr=None,
        trailing_stop_atr=1.5,
        stop_loss_atr=1.0,
        hard_sl_atr_mult=2.5,
        max_holding_bars=None,
        cooldown_bars=15
    )
    engine = StandardizedEngine(period.set_index("datetime"), config=cfg, gap_aware=gap_aware)
    trades = engine.run()
    return trades

print("Engine and backtest runner ready.")

def compute_metrics(trades: pd.DataFrame, initial_capital: float = 100_000_000.0) -> dict:
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "pf": 0.0, "win_rate": 0.0, "exp_vnd": 0.0, "exp_pts": 0.0, "payoff": 0.0, "max_dd": 0.0}
    
    n = len(trades)
    net_pnl = trades["PnL"].sum()
    wins = trades[trades["PnL"] > 0]
    losses = trades[trades["PnL"] <= 0]
    
    n_wins = len(wins)
    n_losses = len(losses)
    win_rate = n_wins / n if n > 0 else 0.0
    
    gross_win = wins["PnL"].sum() if n_wins > 0 else 0.0
    gross_loss = -losses["PnL"].sum() if n_losses > 0 else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else (99.0 if gross_win > 0 else 0.0)
    
    avg_win = gross_win / n_wins if n_wins > 0 else 0.0
    avg_loss = gross_loss / n_losses if n_losses > 0 else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else 0.0
    
    exp_vnd = net_pnl / n if n > 0 else 0.0
    exp_pts = trades["Points"].mean() if n > 0 else 0.0
    
    # Cumulative Drawdown
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
        "exp_pts": exp_pts,
        "max_dd": max_dd
    }

def bootstrap_pf_and_exp(trades: pd.DataFrame, n_resamples: int = 2000, seed: int = 42) -> dict:
    if trades.empty:
        return {"pf_ci": (0.0, 0.0), "exp_ci": (0.0, 0.0)}
    np.random.seed(seed)
    trades = trades.copy()
    trades["Date"] = pd.to_datetime(trades["Entry Date"]).dt.date
    unique_dates = trades["Date"].unique()
    n_dates = len(unique_dates)
    
    boot_pfs = []
    boot_exps = []
    
    for _ in range(n_resamples):
        sample_dates = np.random.choice(unique_dates, size=n_dates, replace=True)
        sampled_trades = trades[trades["Date"].isin(sample_dates)]
        if sampled_trades.empty:
            continue
        gw = sampled_trades.loc[sampled_trades["PnL"] > 0, "PnL"].sum()
        gl = -sampled_trades.loc[sampled_trades["PnL"] <= 0, "PnL"].sum()
        pf_boot = gw / gl if gl > 0 else 99.0
        exp_boot = sampled_trades["PnL"].mean()
        boot_pfs.append(pf_boot)
        boot_exps.append(exp_boot)
        
    pf_lower = np.percentile(boot_pfs, 2.5)
    pf_upper = np.percentile(boot_pfs, 97.5)
    exp_lower = np.percentile(boot_exps, 2.5)
    exp_upper = np.percentile(boot_exps, 97.5)
    
    return {
        "pf_ci": (pf_lower, pf_upper),
        "exp_ci": (exp_lower, exp_upper)
    }

print("\n" + "="*80)
print("GIAI ĐOẠN 2: CHẠY LẠI CHUẨN HÓA WALK-FORWARD 2024 - 2026")
print("Cấu hình: Slip 0.3 pt, Phí 30k, Gap-Aware chuẩn hóa (ATC không dồn slip), Round Tick 0.1 pt")
print("="*80)

all_oos_trades = []
fold_results = []

for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    year = "2024" if idx == 0 else ("2025" if idx == 1 else "2026")
    m = trained_models[idx]
    trades = run_fold_backtest(m, features, test_start, test_end, th, slippage=0.30, gap_aware=True)
    trades["Year"] = year
    trades["Fold"] = name
    all_oos_trades.append(trades)
    
    stats = compute_metrics(trades)
    boot = bootstrap_pf_and_exp(trades)
    
    # Sub-segments
    longs = trades[trades["Type"] == "LONG"]
    shorts = trades[trades["Type"] == "SHORT"]
    overnight = trades[trades["IsOvernight"] == True]
    intraday = trades[trades["IsOvernight"] == False]
    
    fold_results.append({
        "year": year,
        "name": name,
        "threshold": th,
        "overall": stats,
        "boot": boot,
        "longs": compute_metrics(longs),
        "shorts": compute_metrics(shorts),
        "overnight": compute_metrics(overnight),
        "intraday": compute_metrics(intraday),
        "trades": trades
    })

combined_trades = pd.concat(all_oos_trades, ignore_index=True)
combined_trades.sort_values(by="Entry Date", inplace=True)
combined_trades.reset_index(drop=True, inplace=True)

# Combined equity and Max DD
comb_stats = compute_metrics(combined_trades)
comb_boot = bootstrap_pf_and_exp(combined_trades)

# Combined Annualized Calmar Ratio
# Period is 2024-01-01 to 2026-10-29 (~2.83 years)
n_years = (combined_trades["Exit Date"].max() - combined_trades["Entry Date"].min()).days / 365.25
annualized_return = comb_stats["net_pnl"] / n_years if n_years > 0 else 0.0
calmar = annualized_return / comb_stats["max_dd"] if comb_stats["max_dd"] > 0 else 0.0

# Print Year-by-Year Results Table
print("\n--- 1. BẢNG HIỆU SUẤT THEO TỪNG NĂM & TỔNG HỢP ---")
header = f"{'Năm':<6} | {'N lệnh':<7} | {'Win Rate':<9} | {'Net PnL (VND)':<15} | {'PF':<6} | {'PF 95% CI':<16} | {'Exp (VND)':<11} | {'Payoff':<7} | {'Max DD (VND)':<12}"
print(header)
print("-" * len(header))

for r in fold_results:
    s = r["overall"]
    b = r["boot"]
    ci_str = f"[{b['pf_ci'][0]:.2f}, {b['pf_ci'][1]:.2f}]"
    print(f"{r['year']:<6} | {s['trades']:<7d} | {s['win_rate']*100:<8.1f}% | {s['net_pnl']:<+15,.0f} | {s['pf']:<6.2f} | {ci_str:<16} | {s['exp_vnd']:<+11,.0f} | {s['payoff']:<7.2f} | {s['max_dd']:<12,.0f}")

ci_comb_str = f"[{comb_boot['pf_ci'][0]:.2f}, {comb_boot['pf_ci'][1]:.2f}]"
print("-" * len(header))
print(f"{'TỔNG':<6} | {comb_stats['trades']:<7d} | {comb_stats['win_rate']*100:<8.1f}% | {comb_stats['net_pnl']:<+15,.0f} | {comb_stats['pf']:<6.2f} | {ci_comb_str:<16} | {comb_stats['exp_vnd']:<+11,.0f} | {comb_stats['payoff']:<7.2f} | {comb_stats['max_dd']:<12,.0f}")
print(f"\n=> Calmar Ratio Niên Hóa (Annualized Calmar): {calmar:.2f} (Lợi nhuận niên hóa: {annualized_return:,.0f} VND/năm, Max DD ghép: {comb_stats['max_dd']:,.0f} VND)")

# Print Segmented Tables: Long vs Short & Overnight vs Intraday
print("\n--- 2. PHÂN TÁCH LONG vs SHORT ---")
print(f"{'Năm':<6} | {'Hướng':<6} | {'N lệnh':<7} | {'Win Rate':<9} | {'Net PnL (VND)':<15} | {'PF':<6} | {'Exp (VND)':<11} | {'Payoff':<7}")
print("-" * 75)
for r in fold_results:
    for direction, s in [('LONG', r['longs']), ('SHORT', r['shorts'])]:
        print(f"{r['year']:<6} | {direction:<6} | {s['trades']:<7d} | {s['win_rate']*100:<8.1f}% | {s['net_pnl']:<+15,.0f} | {s['pf']:<6.2f} | {s['exp_vnd']:<+11,.0f} | {s['payoff']:<7.2f}")

comb_longs = compute_metrics(combined_trades[combined_trades["Type"] == "LONG"])
comb_shorts = compute_metrics(combined_trades[combined_trades["Type"] == "SHORT"])
print("-" * 75)
print(f"{'TỔNG':<6} | {'LONG':<6} | {comb_longs['trades']:<7d} | {comb_longs['win_rate']*100:<8.1f}% | {comb_longs['net_pnl']:<+15,.0f} | {comb_longs['pf']:<6.2f} | {comb_longs['exp_vnd']:<+11,.0f} | {comb_longs['payoff']:<7.2f}")
print(f"{'TỔNG':<6} | {'SHORT':<6} | {comb_shorts['trades']:<7d} | {comb_shorts['win_rate']*100:<8.1f}% | {comb_shorts['net_pnl']:<+15,.0f} | {comb_shorts['pf']:<6.2f} | {comb_shorts['exp_vnd']:<+11,.0f} | {comb_shorts['payoff']:<7.2f}")

print("\n--- 3. PHÂN TÁCH OVERNIGHT vs INTRADAY ---")
print(f"{'Năm':<6} | {'Nhóm':<10} | {'N lệnh':<7} | {'Win Rate':<9} | {'Net PnL (VND)':<15} | {'PF':<6} | {'Exp (VND)':<11} | {'Payoff':<7}")
print("-" * 78)
for r in fold_results:
    for group_name, s in [('OVERNIGHT', r['overnight']), ('INTRADAY', r['intraday'])]:
        print(f"{r['year']:<6} | {group_name:<10} | {s['trades']:<7d} | {s['win_rate']*100:<8.1f}% | {s['net_pnl']:<+15,.0f} | {s['pf']:<6.2f} | {s['exp_vnd']:<+11,.0f} | {s['payoff']:<7.2f}")

comb_ovn = compute_metrics(combined_trades[combined_trades["IsOvernight"] == True])
comb_intra = compute_metrics(combined_trades[combined_trades["IsOvernight"] == False])
print("-" * 78)
print(f"{'TỔNG':<6} | {'OVERNIGHT':<10} | {comb_ovn['trades']:<7d} | {comb_ovn['win_rate']*100:<8.1f}% | {comb_ovn['net_pnl']:<+15,.0f} | {comb_ovn['pf']:<6.2f} | {comb_ovn['exp_vnd']:<+11,.0f} | {comb_ovn['payoff']:<7.2f}")
print(f"{'TỔNG':<6} | {'INTRADAY':<10} | {comb_intra['trades']:<7d} | {comb_intra['win_rate']*100:<8.1f}% | {comb_intra['net_pnl']:<+15,.0f} | {comb_intra['pf']:<6.2f} | {comb_intra['exp_vnd']:<+11,.0f} | {comb_intra['payoff']:<7.2f}")

# Save combined standardized trades
csv_out = "results/standardized_walk_forward_trades_2024_2026.csv"
combined_trades.to_csv(csv_out, index=False)
print(f"\n[OK] Đã xuất toàn bộ nhật ký giao dịch chuẩn hóa ra: {csv_out}")

# Threshold Sensitivity Analysis
print("\n--- 4. KIỂM TRA ĐỘ NHẠY THEO DẢI NGƯỠNG LÂN CẬN (0.45 - 0.60) ---")
test_thresholds = [0.45, 0.48, 0.50, 0.52, 0.55, 0.58, 0.60]
print(f"{'Threshold':<10} | {'2024 Trades':<11} | {'2024 PF':<8} | {'2025 Trades':<11} | {'2025 PF':<8} | {'2026 Trades':<11} | {'2026 PF':<8} | {'Tổng PnL (VND)':<15}")
print("-" * 95)

for th_cand in test_thresholds:
    pnl_total = 0.0
    row_strs = []
    for idx, (name, val_start, test_start, test_end, _) in enumerate(FOLDS):
        tr = run_fold_backtest(trained_models[idx], features, test_start, test_end, th_cand, slippage=0.30, gap_aware=True)
        st = compute_metrics(tr)
        pnl_total += st["net_pnl"]
        row_strs.append(f"{st['trades']:<11d} | {st['pf']:<8.2f}")
    print(f"{th_cand:<10.2f} | {row_strs[0]} | {row_strs[1]} | {row_strs[2]} | {pnl_total:<+15,.0f}")

# Deep Dive: Validation vs OOS for Fold 3
print("\n--- 5. GIẢI MÃ FOLD 3: VÌ SAO VALIDATION (2025) PF = 3.02 NHƯNG OOS (2026) CHỈ 1.10 (BASE) / ÂM (GAP)? ---")
m3 = trained_models[2]
val_tr_3 = run_fold_backtest(m3, features, pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), 0.55, slippage=0.30, gap_aware=True)
val_st_3 = compute_metrics(val_tr_3)
print(f"Fold 3 Validation (2025) @ th=0.55: Trades={val_st_3['trades']}, WinRate={val_st_3['win_rate']*100:.1f}%, Net PnL={val_st_3['net_pnl']:+,.0f} VND, PF={val_st_3['pf']:.2f}")

oos_tr_3 = run_fold_backtest(m3, features, pd.Timestamp("2026-01-01"), None, 0.55, slippage=0.30, gap_aware=True)
oos_st_3 = compute_metrics(oos_tr_3)
print(f"Fold 3 OOS Test   (2026) @ th=0.55: Trades={oos_st_3['trades']}, WinRate={oos_st_3['win_rate']*100:.1f}%, Net PnL={oos_st_3['net_pnl']:+,.0f} VND, PF={oos_st_3['pf']:.2f}")

print("\nHoàn tất phân tích Giai đoạn 2.")
