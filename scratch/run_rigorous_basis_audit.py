import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

def load_data():
    df = pd.read_parquet("trading_engine/data/VN30_Basis_1m.parquet")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df

def run_audit():
    df = load_data()
    n_total = len(df)
    print(f"Loaded {n_total} 1m bars from {df['datetime'].min()} to {df['datetime'].max()}")
    
    # -------------------------------------------------------------
    # Vectorized forward returns & paths calculation
    # Horizons H in [15, 30, 60, 120, 240] bars
    # -------------------------------------------------------------
    horizons = [15, 30, 60, 120, 240]
    
    print("Vectorized precomputing rolling forward horizons...")
    for h in horizons:
        # Fwd return F1M & VN30
        df[f"fwd_f1m_{h}"] = df["Close"].shift(-h) - df["Close"]
        df[f"fwd_vn30_{h}"] = df["close"].shift(-h) - df["close"]
        
        # Future min Low and max High over next h bars (excluding current bar)
        # Using reversed rolling min/max
        future_min_low = df["Low"].iloc[::-1].rolling(h).min().iloc[::-1].shift(-1)
        future_max_high = df["High"].iloc[::-1].rolling(h).max().iloc[::-1].shift(-1)
        
        df[f"fwd_mae_{h}"] = future_min_low - df["Close"]  # <= 0
        df[f"fwd_mfe_{h}"] = future_max_high - df["Close"] # >= 0
        
    print("Done precomputing forward paths.")
    
    # =========================================================================
    # PHẦN 1: UNCONDITIONAL BASELINE (DRIFT CỦA THỊ TRƯỜNG)
    # =========================================================================
    print("\n" + "="*80)
    print("PHẦN 1: UNCONDITIONAL BASELINE & DRIFT THỊ TRƯỜNG TOÀN KỲ (2023-2026)")
    print("="*80)
    
    uncond_stats = {}
    for h in horizons:
        valid_mask = ~df[f"fwd_f1m_{h}"].isna()
        mean_ret = df.loc[valid_mask, f"fwd_f1m_{h}"].mean()
        std_ret = df.loc[valid_mask, f"fwd_f1m_{h}"].std()
        med_ret = df.loc[valid_mask, f"fwd_f1m_{h}"].median()
        win_rate = (df.loc[valid_mask, f"fwd_f1m_{h}"] > 0).mean() * 100
        uncond_stats[h] = {
            "mean": mean_ret,
            "std": std_ret,
            "median": med_ret,
            "win_rate": win_rate
        }
        print(f"Horizon {h:3d}m: Unconditional Mean Return = {mean_ret:+.3f} pts | Std: {std_ret:.2f} | Median: {med_ret:+.2f} | WinRate: {win_rate:.1f}%")

    print("\nUnconditional Long F1M Drift theo từng năm:")
    for yr in sorted(df["year"].unique()):
        sub = df[df["year"] == yr]
        m60 = sub["fwd_f1m_60"].dropna().mean()
        m120 = sub["fwd_f1m_120"].dropna().mean()
        m240 = sub["fwd_f1m_240"].dropna().mean()
        print(f"  Năm {yr} (N={len(sub):6d} nến): h=60m: {m60:+.3f} pts | h=120m: {m120:+.3f} pts | h=240m: {m240:+.3f} pts")

    # =========================================================================
    # PHẦN 2: KIỂM ĐỊNH TỪNG NGƯỠNG BASIS VỚI CLUSTERING THEO NGÀY
    # =========================================================================
    thresholds = [-4.0, -6.0, -8.0, -10.0]
    
    for thres in thresholds:
        print("\n" + "#"*80)
        print(f"KIỂM ĐỊNH NGƯỠNG BASIS <= {thres} PTS")
        print("#"*80)
        
        cond_raw = df["basis"] <= thres
        cond_entry = cond_raw & (~cond_raw.shift(1).fillna(False))
        
        # Method: FIRST trigger per day (Cluster theo ngày giao dịch độc lập)
        first_per_day_indices = df.loc[cond_entry].groupby("date").head(1).index
        events = df.loc[first_per_day_indices].copy()
        n_days = len(events)
        
        print(f"Tổng số nến thỏa: {cond_raw.sum():5d} | Số đợt excursion: {cond_entry.sum():4d} | SỐ NGÀY ĐỘC LẬP (N_days): {n_days:3d}")
        if n_days == 0:
            print("Không có dữ liệu.")
            continue
            
        # 1. BẢNG EXCESS EDGE VS DRIFT (DAY CLUSTERED)
        print(f"\n[1] LỢI NHUẬN GỘP & EXCESS EDGE (MỖI NGÀY TỐI ĐA 1 LỆNH, N={n_days} NGÀY)")
        print(f"{'Horizon':<8} | {'Gross F1M':<12} | {'Uncond Drift':<12} | {'EXCESS EDGE':<14} | {'WinRate':<8} | {'ΔVN30':<10} | {'ΔBasis':<10}")
        print("-" * 85)
        for h in [30, 60, 120, 240]:
            gross_f1m = events[f"fwd_f1m_{h}"].mean()
            gross_vn30 = events[f"fwd_vn30_{h}"].mean()
            delta_basis = gross_f1m - gross_vn30
            uncond = uncond_stats[h]["mean"]
            excess = gross_f1m - uncond
            win_r = (events[f"fwd_f1m_{h}"] > 0).mean() * 100
            print(f"{h:4d}m   | {gross_f1m:+8.3f} pts | {uncond:+8.3f} pts   | {excess:+10.3f} pts   | {win_r:6.1f}%  | {gross_vn30:+8.3f}   | {delta_basis:+8.3f}")

        # 2. PHÂN RÃ THEO TỪNG NĂM (YEARLY BREAKDOWN CHO h=120m)
        print(f"\n[2] PHÂN RÃ THEO NĂM (Horizon = 120m, 2 Giờ)")
        print(f"{'Năm':<6} | {'N_days':<8} | {'Gross F1M':<12} | {'Uncond Drift':<12} | {'EXCESS EDGE':<14} | {'WinRate':<8} | {'Min/Max PnL':<18}")
        print("-" * 88)
        for yr in sorted(events["year"].unique()):
            ev_yr = events[events["year"] == yr]
            n_yr_days = len(ev_yr)
            g_f1m = ev_yr["fwd_f1m_120"].mean()
            u_drift = df[df["year"] == yr]["fwd_f1m_120"].dropna().mean()
            ex = g_f1m - u_drift
            wr = (ev_yr["fwd_f1m_120"] > 0).mean() * 100
            min_p = ev_yr["fwd_f1m_120"].min()
            max_p = ev_yr["fwd_f1m_120"].max()
            print(f"{yr:<6} | {n_yr_days:<8} | {g_f1m:+8.3f} pts | {u_drift:+8.3f} pts   | {ex:+10.3f} pts   | {wr:6.1f}%  | [{min_p:+6.1f}, {max_p:+6.1f}] pts")

        # 3. LỌC TUẦN ĐÁO HẠN (EXPIRATION FILTER)
        print(f"\n[3] PHÂN TÍCH TUẦN ĐÁO HẠN (Horizon = 120m)")
        ev_exp = events[events["days_to_exp"] <= 3]
        ev_norm = events[events["days_to_exp"] > 3]
        
        g_exp = ev_exp['fwd_f1m_120'].mean() if len(ev_exp) > 0 else np.nan
        wr_exp = (ev_exp['fwd_f1m_120'] > 0).mean() * 100 if len(ev_exp) > 0 else np.nan
        db_exp = (ev_exp['fwd_f1m_120'] - ev_exp['fwd_vn30_120']).mean() if len(ev_exp) > 0 else np.nan

        g_norm = ev_norm['fwd_f1m_120'].mean() if len(ev_norm) > 0 else np.nan
        wr_norm = (ev_norm['fwd_f1m_120'] > 0).mean() * 100 if len(ev_norm) > 0 else np.nan
        db_norm = (ev_norm['fwd_f1m_120'] - ev_norm['fwd_vn30_120']).mean() if len(ev_norm) > 0 else np.nan

        print(f"  Tuần đáo hạn (<=3 ngày): N={len(ev_exp):2d} ngày | Gross F1M = {g_exp:+.3f} pts | WinRate = {wr_exp:5.1f}% | ΔBasis = {db_exp:+.3f}")
        print(f"  Bình thường  (> 3 ngày): N={len(ev_norm):2d} ngày | Gross F1M = {g_norm:+.3f} pts | WinRate = {wr_norm:5.1f}% | ΔBasis = {db_norm:+.3f}")

        # 4. ADVERSE EXCURSION & STOP LOSS SIMULATION
        print(f"\n[4] MAE (DRAWDOWN TỐI ĐA) & MÔ PHỎNG STOP LOSS (Horizon = 120m)")
        mae_series = events["fwd_mae_120"].dropna()
        mfe_series = events["fwd_mfe_120"].dropna()
        
        print(f"MAE (Drawdown tối đa trong 2h): Mean = {mae_series.mean():.2f} pts | Median = {mae_series.median():.2f} pts | 25th %tile = {np.percentile(mae_series, 25):.2f} pts | Min = {mae_series.min():.2f} pts")
        print(f"MFE (Lãi tối đa trong 2h):     Mean = {mfe_series.mean():.2f} pts | Median = {mfe_series.median():.2f} pts | 75th %tile = {np.percentile(mfe_series, 75):.2f} pts | Max = {mfe_series.max():.2f} pts")
        
        print("\nMô phỏng thực thi SL cứng (với trượt giá hoảng loạn):")
        print(f"{'Stop Level':<12} | {'Trượt giá':<10} | {'Tỷ lệ dính SL':<15} | {'PnL TB sau SL':<16} | {'So với Giữ hết 2h'}")
        print("-" * 75)
        for sl in [3.0, 5.0, 7.0, 10.0]:
            for slip in [0.0, 0.5, 1.0]:
                stopped = events["fwd_mae_120"] <= -sl
                hit_rate = stopped.mean() * 100
                pnl_sim = np.where(stopped, -sl - slip, events["fwd_f1m_120"])
                avg_pnl = np.nanmean(pnl_sim)
                diff = avg_pnl - events["fwd_f1m_120"].mean()
                print(f"-{sl:4.1f} pts   | {slip:4.1f} pt    | {hit_rate:6.1f}%          | {avg_pnl:+8.3f} pts       | {diff:+8.3f} pts")

        # 5. BOOTSTRAP 95% CONFIDENCE INTERVAL & P-VALUE
        print(f"\n[5] BOOTSTRAP 95% CONFIDENCE INTERVAL (Horizon = 120m, 10,000 resamples)")
        vals = events["fwd_f1m_120"].dropna().values
        np.random.seed(42)
        boot_means = [np.mean(np.random.choice(vals, size=len(vals), replace=True)) for _ in range(10000)]
        ci_lower = np.percentile(boot_means, 2.5)
        ci_upper = np.percentile(boot_means, 97.5)
        p_val_zero = (np.array(boot_means) <= 0).mean()
        print(f"Day-clustered Mean: {np.mean(vals):+.3f} pts | 95% CI: [{ci_lower:+.3f}, {ci_upper:+.3f}] pts | p(mean <= 0): {p_val_zero:.4f}")

if __name__ == "__main__":
    run_audit()
