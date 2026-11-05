import sys
import io
import os
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
import xgboost as xgb

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import XGBOOST_PARAMS, FEATURES_PATH, DATASET_PATH
from trading_engine.backtest.config import BacktestConfig

FOLDS = [
    ("Fold 1 (OOS 2024)", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), 0.55),
    ("Fold 2 (OOS 2025)", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), 0.50),
    ("Fold 3 (OOS 2026)", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), None, 0.55),
]

cfg_real = BacktestConfig(
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

def round_tick(price: float) -> float:
    return round(price * 10.0) / 10.0

# Engine sinh trade của Baseline chuẩn cho từng seed
class BacktestStandard:
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
                    if low <= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl >= entry_price and low <= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif low <= trailing_sl:
                        if (row.get("HTF_15m_TrendDownOK", 0) == 1 or row.get("HTF_15m_TrendTransitionDown", 0) == 1):
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == -1: raw_exit, reason = close, "Reversal"
                else:
                    if high >= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_price and high >= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif high >= trailing_sl:
                        if (row.get("HTF_15m_TrendOK", 0) == 1 or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0)):
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == 1: raw_exit, reason = close, "Reversal"

                if raw_exit is None and atr > 0:
                    trailing_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                    if position == 1: trailing_sl = max(trailing_sl, round_tick(close - self.config.trailing_stop_atr * trailing_atr))
                    else: trailing_sl = min(trailing_sl, round_tick(close + self.config.trailing_stop_atr * trailing_atr))

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

                    trades.append({
                        "entry_time": entry_date, "exit_time": timestamp,
                        "type": "LONG" if position == 1 else "SHORT",
                        "entry_price": entry_price, "exit_price": exit_price,
                        "points": pts, "net_pnl": net_pnl, "reason": reason,
                        "hard_sl": hard_sl, "bars_held": bars_held
                    })
                    position = 0
                    cooldown_remaining = self.config.cooldown_bars
                    continue

            if position == 0 and signal and cooldown_remaining == 0:
                atr = row.get("ATR", 0.0)
                if atr <= 0: continue
                position = signal
                entry_date = timestamp
                entry_price = round_tick(close + position * self.config.slippage_points)
                setup = str(row.get("EntrySetup", ""))
                trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if ("SPRING" in setup or "UTAD" in setup) else float(row.get("HTF_5m_ATR", atr * 2.0))
                initial_sl = round_tick(entry_price - position * self.config.stop_loss_atr * trade_atr)
                trailing_sl = initial_sl
                hsl_mult = getattr(self.config, "hard_sl_atr_mult", 2.5)
                hard_sl = round_tick(entry_price - position * hsl_mult * self.config.stop_loss_atr * trade_atr)
                bars_held = 0

        return pd.DataFrame(trades)

def run_paired_10seeds_audit():
    dataset = pd.read_csv(DATASET_PATH)
    dataset["exit_time"] = pd.to_datetime(dataset["exit_time"])
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"])
    features = features.sort_values("datetime").reset_index(drop=True)
    dt_to_idx = {dt: i for i, dt in enumerate(features["datetime"])}

    print("="*85)
    print("BƯỚC 1: SO SÁNH CẶP (PAIRED B - A) TRÊN CÙNG LỆNH VÀO QUA 10 RANDOM SEEDS")
    print("="*85)

    seed_diff_records = []
    all_paired_trades = []

    for seed in range(40, 50):
        # 1. Sinh tập lệnh Baseline chuẩn của seed này
        folds_tr = []
        for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
            train = dataset[dataset["exit_time"] < val_start]
            p = XGBOOST_PARAMS.copy()
            p["random_state"] = seed
            p["seed"] = seed
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

            engine = BacktestStandard(period.set_index("datetime"), cfg_real)
            tr = engine.run()
            if not tr.empty:
                folds_tr.append(tr)

        df_seed_trades = pd.concat(folds_tr, ignore_index=True)
        
        # 2. Với TỪNG lệnh vào của Baseline, áp dụng quy tắc Hybrid:
        # Long: giữ nguyên PnL Baseline
        # Short: chốt tại RangeLow 5m (120 nến 1m) nếu khoảng cách >= 1.5 pt
        pnl_base_list = []
        pnl_hybrid_list = []

        for _, tr_row in df_seed_trades.iterrows():
            pos = 1 if tr_row["type"] == "LONG" else -1
            p_entry = tr_row["entry_price"]
            hard_sl = tr_row["hard_sl"]
            pnl_base = tr_row["points"]
            
            pnl_base_list.append(pnl_base)
            
            if pos == 1:
                # Long giữ nguyên 100%
                pnl_hybrid_list.append(pnl_base)
            else:
                # Short: tìm RangeLow 120 bars
                e_idx = dt_to_idx.get(tr_row["entry_time"])
                if e_idx is None:
                    pnl_hybrid_list.append(pnl_base)
                    continue
                w_start = max(0, e_idx - 120)
                r_low = features.iloc[w_start:e_idx]["Low"].min()
                dist = p_entry - r_low
                
                trade_bars = features.iloc[e_idx + 1 : e_idx + tr_row["bars_held"] + 1]
                p_hyb = pnl_base
                
                if dist >= 1.5 and len(trade_bars) > 0:
                    for b in range(len(trade_bars)):
                        h_b = trade_bars["High"].values[b]
                        l_b = trade_bars["Low"].values[b]
                        # Check Target RangeLow trước
                        if l_b <= r_low:
                            p_hyb = dist - 0.1 - 0.3 # limit fill at r_low-0.1, slip entry 0.3
                            break
                        # Check Stop
                        if h_b >= hard_sl:
                            p_hyb = -hard_sl + p_entry - 0.6
                            break
                pnl_hybrid_list.append(p_hyb)
                
        p_base_s = np.array(pnl_base_list)
        p_hyb_s = np.array(pnl_hybrid_list)
        diff_s = p_hyb_s - p_base_s
        
        # Tính metrics cho seed này
        net_vnd_base = (p_base_s.sum() * 100000) - len(p_base_s) * 30000
        net_vnd_hyb = (p_hyb_s.sum() * 100000) - len(p_hyb_s) * 30000
        
        gp_b = p_base_s[p_base_s > 0].sum()
        gl_b = abs(p_base_s[p_base_s < 0].sum())
        pf_b = gp_b / gl_b if gl_b > 0 else np.nan

        gp_h = p_hyb_s[p_hyb_s > 0].sum()
        gl_h = abs(p_hyb_s[p_hyb_s < 0].sum())
        pf_h = gp_h / gl_h if gl_h > 0 else np.nan

        seed_diff_records.append({
            "seed": seed,
            "trades": len(df_seed_trades),
            "base_pnl_pts": p_base_s.sum(),
            "hyb_pnl_pts": p_hyb_s.sum(),
            "diff_pts": diff_s.sum(),
            "mean_diff_per_trade": diff_s.mean(),
            "base_net_vnd": net_vnd_base,
            "hyb_net_vnd": net_vnd_hyb,
            "base_pf": pf_b,
            "hyb_pf": pf_h,
            "base_wr": (p_base_s > 0).mean() * 100,
            "hyb_wr": (p_hyb_s > 0).mean() * 100
        })
        all_paired_trades.extend(diff_s)
        print(f"Seed {seed}: N={len(df_seed_trades):3d} | Base = {net_vnd_base/1e6:+6.2f}M (PF {pf_b:4.2f}) | Hyb = {net_vnd_hyb/1e6:+6.2f}M (PF {pf_h:4.2f}) | Δ = {diff_s.sum():+6.1f} pts ({diff_s.mean():+5.2f} pt/lệnh)")

    df_seeds = pd.DataFrame(seed_diff_records)
    
    print("\n" + "="*85)
    print("THỐNG KÊ PHÂN PHỐI 10 SEEDS (PAIRED B - A TRÊN CÙNG LỆNH VÀO):")
    print("="*85)
    print(f"Số lệnh trung bình mỗi seed: {df_seeds['trades'].mean():.1f} lệnh")
    print(f"Net PnL Baseline (VND):   Mean = {df_seeds['base_net_vnd'].mean()/1e6:+6.2f}M | Median = {df_seeds['base_net_vnd'].median()/1e6:+6.2f}M | Seeds âm: {(df_seeds['base_net_vnd']<0).sum()}/10")
    print(f"Net PnL Hybrid   (VND):   Mean = {df_seeds['hyb_net_vnd'].mean()/1e6:+6.2f}M | Median = {df_seeds['hyb_net_vnd'].median()/1e6:+6.2f}M | Seeds âm: {(df_seeds['hyb_net_vnd']<0).sum()}/10")
    print(f"Chênh lệch PnL (Điểm):    Mean = {df_seeds['diff_pts'].mean():+6.1f} pts | Median = {df_seeds['diff_pts'].median():+6.1f} pts")
    print(f"Chênh lệch trên mỗi lệnh: Mean = {df_seeds['mean_diff_per_trade'].mean():+5.2f} pt  | Median = {df_seeds['mean_diff_per_trade'].median():+5.2f} pt")
    print(f"Profit Factor:            Base Mean = {df_seeds['base_pf'].mean():.2f} (Med {df_seeds['base_pf'].median():.2f}) | Hyb Mean = {df_seeds['hyb_pf'].mean():.2f} (Med {df_seeds['hyb_pf'].median():.2f})")
    print(f"Win Rate:                 Base Mean = {df_seeds['base_wr'].mean():.1f}% | Hyb Mean = {df_seeds['hyb_wr'].mean():.1f}%")

    # Bootstrap 95% CI cho paired difference (trên toàn bộ lệnh ghép cặp)
    np.random.seed(42)
    all_diffs = np.array(all_paired_trades)
    boot_means = [np.mean(np.random.choice(all_diffs, size=len(all_diffs), replace=True)) for _ in range(10000)]
    ci_lower = np.percentile(boot_means, 2.5)
    ci_upper = np.percentile(boot_means, 97.5)
    p_val_zero = (np.array(boot_means) <= 0).mean()
    print(f"\nBootstrap 95% CI của chênh lệch (B - A) trên toàn bộ {len(all_diffs)} lệnh ghép cặp:")
    print(f"  Mean diff: {np.mean(all_diffs):+.3f} pts/lệnh | 95% CI: [{ci_lower:+.3f}, {ci_upper:+.3f}] pts | p(B <= A): {p_val_zero:.4f}")

# ==============================================================================
# BƯỚC 2: KIỂM CHỨNG TRÊN DỮ LIỆU ĐỘC LẬP 2018 - 2022 (LAYER 1 THUẦN TÚY)
# ==============================================================================
def run_unseen_2018_2022_audit():
    print("\n" + "="*85)
    print("BƯỚC 2: KIỂM CHỨNG ĐỘC LẬP TRÊN DỮ LIỆU CHƯA NHÌN (2018 - 2022, LAYER 1 THUẦN)")
    print("="*85)
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"])
    
    # Lọc giai đoạn 2018 - 2022
    mask_old = (features["datetime"] >= "2018-01-01") & (features["datetime"] < "2023-01-01")
    df_old = features[mask_old].copy().reset_index(drop=True)
    dt_to_idx = {dt: i for i, dt in enumerate(df_old["datetime"])}
    
    # Chạy Baseline Layer 1 thuần (StrategySignal != 0)
    df_old_sim = df_old.copy()
    df_old_sim["Signal"] = df_old_sim["StrategySignal"].fillna(0).astype(int)
    
    engine = BacktestStandard(df_old_sim.set_index("datetime"), cfg_real)
    trades_l1 = engine.run()
    
    print(f"Tổng số lệnh Layer 1 thuần trên 2018 - 2022: {len(trades_l1)} lệnh")
    if trades_l1.empty:
        print("Không có lệnh.")
        return
        
    # Tách Long vs Short trên Baseline
    longs = trades_l1[trades_l1["type"] == "LONG"]
    shorts = trades_l1[trades_l1["type"] == "SHORT"]
    print(f"  Long  (N={len(longs):3d}): PnL = {longs['points'].sum():+7.1f} pts | Mean = {longs['points'].mean():+5.2f} pt | WR = {(longs['points']>0).mean()*100:.1f}%")
    print(f"  Short (N={len(shorts):3d}): PnL = {shorts['points'].sum():+7.1f} pts | Mean = {shorts['points'].mean():+5.2f} pt | WR = {(shorts['points']>0).mean()*100:.1f}%")
    
    # Bây giờ áp dụng:
    # 1. Long chốt T1 vs Long thả trôi
    # 2. Short chốt T1 vs Short thả trôi
    # Xem quy tắc bất đối xứng có được ủng hộ trên 2018-2022 không!
    long_diffs = []
    short_diffs = []
    
    for _, tr in trades_l1.iterrows():
        pos = 1 if tr["type"] == "LONG" else -1
        p_entry = tr["entry_price"]
        hard_sl = tr["hard_sl"]
        pnl_base = tr["points"]
        e_idx = dt_to_idx.get(tr["entry_time"])
        if e_idx is None: continue
        
        w_start = max(0, e_idx - 120)
        w_prior = df_old.iloc[w_start:e_idx]
        
        target = w_prior["High"].max() if pos == 1 else w_prior["Low"].min()
        dist = (target - p_entry) * pos
        
        trade_bars = df_old.iloc[e_idx + 1 : e_idx + tr["bars_held"] + 1]
        pnl_t1 = pnl_base
        
        if dist >= 1.5 and len(trade_bars) > 0:
            for b in range(len(trade_bars)):
                h_b = trade_bars["High"].values[b]
                l_b = trade_bars["Low"].values[b]
                hit_tg = (h_b >= target) if pos == 1 else (l_b <= target)
                hit_sl = (l_b <= hard_sl) if pos == 1 else (h_b >= hard_sl)
                
                if hit_tg:
                    pnl_t1 = dist - 0.1 - 0.3
                    break
                if hit_sl:
                    pnl_t1 = (hard_sl - p_entry) * pos - 0.6
                    break
                    
        diff = pnl_t1 - pnl_base
        if pos == 1: long_diffs.append(diff)
        else: short_diffs.append(diff)
        
    print("\nKiểm tra quy tắc Exit trên 2018 - 2022:")
    print(f"  Chiều LONG (Chốt T1 so với Thả trôi, N={len(long_diffs)}):  Chênh lệch = {sum(long_diffs):+7.1f} pts (Mean = {np.mean(long_diffs):+5.2f} pt/lệnh)")
    print(f"  Chiều SHORT (Chốt T1 so với Thả trôi, N={len(short_diffs)}): Chênh lệch = {sum(short_diffs):+7.1f} pts (Mean = {np.mean(short_diffs):+5.2f} pt/lệnh)")

if __name__ == "__main__":
    run_paired_10seeds_audit()
    run_unseen_2018_2022_audit()

