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

# ==============================================================================
# PHẦN 1: TÍNH CHÍNH XÁC CÁC CHỈ SỐ ANALYTICS CHO SEED 42 (PAIRED)
# ==============================================================================
def calculate_seed42_metrics():
    trades = pd.read_csv("results/all_trades_visualize.csv")
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"])
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    dt_to_idx = {dt: i for i, dt in enumerate(features["datetime"])}
    
    records = []
    for idx_t, trade in trades.iterrows():
        t_entry = trade["entry_time"]
        p_entry = trade["entry_price"]
        pos = 1 if trade["type"].upper() in ("LONG", "BUY") else -1
        hard_sl = trade["hard_sl"]
        pnl_base = trade["points"]
        
        if pos == 1:
            pnl_asym = pnl_base
            exit_reason = trade["reason"]
        else:
            e_idx = dt_to_idx.get(t_entry)
            w_start = max(0, e_idx - 120)
            w_prior = features.iloc[w_start:e_idx]
            t1 = w_prior["Low"].min()
            dist_t1 = p_entry - t1
            trade_bars = features.iloc[e_idx + 1 : e_idx + trade["bars_held"] + 1]
            pnl_asym = pnl_base
            exit_reason = trade["reason"]
            
            if dist_t1 >= 1.5 and len(trade_bars) > 0:
                for b in range(len(trade_bars)):
                    h_b, l_b = trade_bars["High"].values[b], trade_bars["Low"].values[b]
                    if l_b <= t1:
                        pnl_asym = dist_t1 - 0.1 - 0.3 # limit fill at t1-0.1, slip entry 0.3
                        exit_reason = "TP_RangeLow"
                        break
                    if h_b >= hard_sl:
                        pnl_asym = -hard_sl + p_entry - 0.6
                        exit_reason = "Hard_SL"
                        break
                        
        records.append({
            "id": trade["id"],
            "year": t_entry.year,
            "type": trade["type"],
            "entry_price": p_entry,
            "base_points": pnl_base,
            "asym_points": pnl_asym,
            "exit_reason": exit_reason,
            "is_overnight": trade["is_overnight"]
        })
        
    df = pd.DataFrame(records)
    
    # Calculate detailed analytics
    def get_stats(pnl_series):
        wins = pnl_series[pnl_series > 0]
        losses = pnl_series[pnl_series < 0]
        gross_profit = wins.sum()
        gross_loss = abs(losses.sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else np.nan
        wr = len(wins) / len(pnl_series) * 100
        payoff = (wins.mean() / abs(losses.mean())) if len(losses) > 0 and len(wins) > 0 else np.nan
        exp = pnl_series.mean()
        tot = pnl_series.sum()
        
        # Max Drawdown
        cum = pnl_series.cumsum()
        peak = cum.cummax()
        dd = cum - peak
        mdd = abs(dd.min())
        
        return {
            "Total PnL (pts)": tot,
            "Total VND (1 HĐ)": tot * 100000 - len(pnl_series) * 30000,
            "Win Rate (%)": wr,
            "Profit Factor": pf,
            "Payoff Ratio": payoff,
            "Expectancy (pts/lệnh)": exp,
            "Expectancy (VND/lệnh)": exp * 100000 - 30000,
            "Max Drawdown (pts)": mdd,
            "Max Drawdown (VND)": mdd * 100000,
            "Trades": len(pnl_series),
            "Wins": len(wins),
            "Losses": len(losses)
        }
        
    stats_base = get_stats(df["base_points"])
    stats_asym = get_stats(df["asym_points"])
    
    return df, stats_base, stats_asym

# ==============================================================================
# PHẦN 2: CHẠY LẠI FULL WALK-FORWARD ENGINE QUA 10 RANDOM SEEDS (SEEDS 40 - 49)
# ==============================================================================
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

class AsymmetricBacktestEngine:
    def __init__(self, df: pd.DataFrame, config: BacktestConfig):
        self.df = df
        self.config = config

    def run(self):
        trades = []
        position = 0
        entry_price = entry_date = None
        contracts = 1
        initial_sl = trailing_sl = hard_sl = 0.0
        short_tp = 0.0
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
                    # LONG: Giữ nguyên trailing ATR 1.5
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
                    # SHORT: Thêm cơ chế Take Profit tại RangeLow 5m
                    if short_tp > 0 and low <= short_tp:
                        raw_exit, reason = short_tp, "TP_RangeLow"
                    elif high >= hard_sl:
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

                    # Slip: Maker cho TP (0 trượt), Taker cho SL (0.3 pt)
                    if reason == "TP_RangeLow":
                        slip = 0.0
                        exit_price = round_tick(actual_exit_base - position * 0.1) # limit fill trừ 1 tick
                    else:
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
                        "bars_held": bars_held
                    })
                    position = 0
                    cooldown_remaining = self.config.cooldown_bars

            # MỞ VỊ THẾ MỚI
            if position == 0 and cooldown_remaining == 0 and signal != 0:
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
                bars_held = 0

                if position == 1:
                    short_tp = 0.0
                else:
                    rl = row.get("RangeLow_120m", None)
                    if rl is not None and (entry_price - rl) >= 1.5:
                        short_tp = rl
                    else:
                        short_tp = 0.0

        return pd.DataFrame(trades)

def run_10seed_walk_forward_audit():
    print("Loading datasets for 10-seed Walk-Forward backtest...")
    dataset = pd.read_csv(DATASET_PATH)
    dataset["entry_time"] = pd.to_datetime(dataset["entry_time"])
    dataset["exit_time"] = pd.to_datetime(dataset["exit_time"])
    
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"])
    features = features.sort_values("datetime").reset_index(drop=True)
    
    # Precompute RangeLow 120m (24 nến 5m)
    features["RangeLow_120m"] = features["Low"].rolling(120).min().shift(1)
    
    results_asym_10seeds = []
    
    print("\nRunning Walk-Forward across 10 Random Seeds (40 to 49)...")
    for seed in range(40, 50):
        seed_trades = []
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

            engine = AsymmetricBacktestEngine(period.set_index("datetime"), cfg_real)
            f_trades = engine.run()
            if not f_trades.empty:
                f_trades["fold"] = name
                seed_trades.append(f_trades)

        all_seed_df = pd.concat(seed_trades, ignore_index=True)
        wins = all_seed_df[all_seed_df["points"] > 0]
        losses = all_seed_df[all_seed_df["points"] < 0]
        gp = wins["points"].sum()
        gl = abs(losses["points"].sum())
        pf = gp / gl if gl > 0 else np.nan
        wr = len(wins) / len(all_seed_df) * 100
        net_vnd = all_seed_df["net_pnl"].sum()
        tot_pts = all_seed_df["points"].sum()
        exp_pts = all_seed_df["points"].mean()
        
        # Drawdown
        cum = all_seed_df["points"].cumsum()
        mdd_pts = abs((cum - cum.cummax()).min())
        
        results_asym_10seeds.append({
            "seed": seed,
            "trades": len(all_seed_df),
            "net_vnd": net_vnd,
            "tot_pts": tot_pts,
            "win_rate": wr,
            "pf": pf,
            "exp_pts": exp_pts,
            "mdd_pts": mdd_pts
        })
        print(f"  Seed {seed}: Trades={len(all_seed_df):3d} | Net PnL = {net_vnd/1e6:+6.2f}M VND ({tot_pts:+6.1f} pts) | PF={pf:4.2f} | WR={wr:4.1f}% | MDD={mdd_pts:4.1f} pts")
        
    res_10 = pd.DataFrame(results_asym_10seeds)
    return res_10

if __name__ == "__main__":
    df_paired, s_base, s_asym = calculate_seed42_metrics()
    
    print("="*85)
    print("SO SÁNH BỘ CHỈ SỐ ANALYTICS: BASELINE ĐỐI XỨNG (A) VS SETUP BẤT ĐỐI XỨNG (SEED 42)")
    print("="*85)
    metrics_comp = []
    for k in s_base.keys():
        v_a = s_base[k]
        v_b = s_asym[k]
        diff = v_b - v_a
        pct = (diff / abs(v_a) * 100) if v_a != 0 else np.nan
        metrics_comp.append({
            "Chỉ số": k,
            "Baseline A (Đối xứng)": f"{v_a:,.2f}" if isinstance(v_a, float) else f"{v_a:,}",
            "Setup Bất Đối Xứng": f"{v_b:,.2f}" if isinstance(v_b, float) else f"{v_b:,}",
            "Chênh lệch (Δ)": f"{diff:+,.2f}" if isinstance(diff, float) else f"{diff:+,}",
            "Tỷ lệ cải thiện": f"{pct:+.1f}%" if not np.isnan(pct) else "—"
        })
    df_metrics = pd.DataFrame(metrics_comp)
    print(df_metrics.to_string(index=False))
    
    print("\n" + "="*85)
    print("CHẠY LẠI FULL WALK-FORWARD 10 RANDOM SEEDS (TRẠNG THÁI DỘNG KHI GIẢI PHÓNG VỊ THẾ)")
    print("="*85)
    df_10 = run_10seed_walk_forward_audit()
    
    print("\n" + "="*85)
    print("PHÂN PHỐI 10 RANDOM SEEDS CỦA SETUP BẤT ĐỐI XỨNG:")
    print("="*85)
    print(f"Net PnL (VND):   Mean = {df_10['net_vnd'].mean()/1e6:+6.2f}M | Median = {df_10['net_vnd'].median()/1e6:+6.2f}M | IQR: [{df_10['net_vnd'].quantile(0.25)/1e6:+6.2f}M, {df_10['net_vnd'].quantile(0.75)/1e6:+6.2f}M]")
    print(f"Profit Factor:   Mean = {df_10['pf'].mean():4.2f} | Median = {df_10['pf'].median():4.2f} | Min = {df_10['pf'].min():4.2f} | Max = {df_10['pf'].max():4.2f}")
    print(f"Win Rate:        Mean = {df_10['win_rate'].mean():4.1f}% | Median = {df_10['win_rate'].median():4.1f}%")
    print(f"Expectancy:      Mean = {df_10['exp_pts'].mean():+5.2f} pts | Median = {df_10['exp_pts'].median():+5.2f} pts")
    print(f"Max Drawdown:    Mean = {df_10['mdd_pts'].mean():4.1f} pts | Median = {df_10['mdd_pts'].median():4.1f} pts")
    print(f"Số seed âm vốn:  {int((df_10['net_vnd'] < 0).sum())}/10 seeds (So với 2/10 của Baseline)")
