import sys
import io
import os
import numpy as np
import pandas as pd

def compute_swing_levels_15m(df_1m):
    df_15m = df_1m.set_index("datetime").resample("15min").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last"
    }).dropna().reset_index()
    
    highs = df_15m["High"].values
    lows = df_15m["Low"].values
    n = len(df_15m)
    
    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low = np.zeros(n, dtype=bool)
    
    for i in range(5, n - 5):
        if highs[i] == np.max(highs[i-5:i+6]) and highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            is_swing_high[i] = True
        if lows[i] == np.min(lows[i-5:i+6]) and lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            is_swing_low[i] = True
            
    df_15m["is_swing_high"] = is_swing_high
    df_15m["is_swing_low"] = is_swing_low
    return df_15m

def run_detailed_breakdowns():
    features = pd.read_parquet("trading_engine/data/VN30F1M_features.parquet")
    features["datetime"] = pd.to_datetime(features["datetime"])
    features = features.sort_values("datetime").reset_index(drop=True)
    
    trades = pd.read_csv("results/all_trades_visualize.csv")
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    trades["exit_time"] = pd.to_datetime(trades["exit_time"])
    
    dt_to_idx = {dt: i for i, dt in enumerate(features["datetime"])}
    
    features["date"] = features["datetime"].dt.date
    daily_stats = features.groupby("date").agg({"High": "max", "Low": "min"}).shift(1)
    prev_day_high_map = daily_stats["High"].to_dict()
    prev_day_low_map = daily_stats["Low"].to_dict()
    
    df_15m = compute_swing_levels_15m(features[["datetime", "Open", "High", "Low", "Close"]])
    swing_highs = df_15m[df_15m["is_swing_high"]][["datetime", "High"]].values
    swing_lows = df_15m[df_15m["is_swing_low"]][["datetime", "Low"]].values
    
    records = []
    
    for idx_t, trade in trades.iterrows():
        t_entry = trade["entry_time"]
        t_exit = trade["exit_time"]
        p_entry = trade["entry_price"]
        p_exit = trade["exit_price"]
        pos = 1 if trade["type"].upper() in ("LONG", "BUY") else -1
        hard_sl = trade["hard_sl"]
        pnl_base = trade["points"]
        yr = t_entry.year
        
        if t_entry not in dt_to_idx:
            continue
        e_idx = dt_to_idx[t_entry]
        x_idx = dt_to_idx.get(t_exit, e_idx + trade["bars_held"])
        
        # T1: 5m Range (120 bars 1m)
        w_start = max(0, e_idx - 120)
        window_prior = features.iloc[w_start:e_idx]
        t1_target = window_prior["High"].max() if pos == 1 else window_prior["Low"].min()
        
        # T2: 15m Swing
        if pos == 1:
            valid_swings = [sh[1] for sh in swing_highs if sh[0] < t_entry and sh[1] > p_entry + 1.0]
            t2_target = valid_swings[-1] if len(valid_swings) > 0 else window_prior["High"].max()
        else:
            valid_swings = [sl[1] for sl in swing_lows if sl[0] < t_entry and sl[1] < p_entry - 1.0]
            t2_target = valid_swings[-1] if len(valid_swings) > 0 else window_prior["Low"].min()
            
        # T3: Prev Day High/Low & Session High/Low
        cur_date = t_entry.date()
        prev_h = prev_day_high_map.get(cur_date, window_prior["High"].max())
        prev_l = prev_day_low_map.get(cur_date, window_prior["Low"].min())
        today_bars = features.iloc[max(0, e_idx - 300):e_idx]
        today_bars = today_bars[today_bars["date"] == cur_date]
        today_h = today_bars["High"].max() if len(today_bars) > 0 else p_entry
        today_l = today_bars["Low"].min() if len(today_bars) > 0 else p_entry
        t3_target = max(prev_h, today_h) if pos == 1 else min(prev_l, today_l)
        
        # Trace bars
        trade_bars = features.iloc[e_idx + 1 : min(len(features), x_idx + 1)]
        if len(trade_bars) == 0:
            trade_bars = features.iloc[e_idx : e_idx + 1]
            
        highs = trade_bars["High"].values
        lows = trade_bars["Low"].values
        closes = trade_bars["Close"].values
        dts = trade_bars["datetime"].values
        
        def simulate_exit(target_val, intraday_only=False):
            if (target_val - p_entry) * pos < 1.5:
                return np.nan, "SKIPPED"
            for b_idx in range(len(trade_bars)):
                h_b, l_b = highs[b_idx], lows[b_idx]
                dt_b = pd.to_datetime(dts[b_idx])
                
                hit_target = (h_b >= target_val) if pos == 1 else (l_b <= target_val)
                hit_stop = (l_b <= hard_sl) if pos == 1 else (h_b >= hard_sl)
                
                if hit_target and not hit_stop:
                    fill_p = target_val - pos * 0.1
                    pnl = (fill_p - p_entry) * pos - 0.3
                    return pnl, "TARGET"
                elif hit_stop:
                    fill_p = hard_sl - pos * 0.3
                    pnl = (fill_p - p_entry) * pos - 0.3
                    return pnl, "STOP"
                
                if intraday_only and dt_b.hour == 14 and dt_b.minute == 45:
                    fill_p = closes[b_idx]
                    pnl = (fill_p - p_entry) * pos - 0.3
                    return pnl, "ATC_CLOSE"
                    
            pnl = pnl_base
            return pnl, "BASE_EXIT"

        pnl_t1, res_t1 = simulate_exit(t1_target, intraday_only=False)
        pnl_t1_intra, _ = simulate_exit(t1_target, intraday_only=True)
        
        pnl_t2, res_t2 = simulate_exit(t2_target, intraday_only=False)
        pnl_t2_intra, _ = simulate_exit(t2_target, intraday_only=True)
        
        pnl_t3, res_t3 = simulate_exit(t3_target, intraday_only=False)
        pnl_t3_intra, _ = simulate_exit(t3_target, intraday_only=True)
        
        records.append({
            "id": trade["id"],
            "year": yr,
            "type": trade["type"],
            "pnl_base": pnl_base,
            "pnl_t1": pnl_t1, "pnl_t1_intra": pnl_t1_intra,
            "pnl_t2": pnl_t2, "pnl_t2_intra": pnl_t2_intra,
            "pnl_t3": pnl_t3, "pnl_t3_intra": pnl_t3_intra,
        })
        
    df = pd.DataFrame(records)
    
    output_lines = []
    output_lines.append("="*90)
    output_lines.append("BƯỚC 2: SO SÁNH PNL VÀ EXPECTANCY GIỮA BASELINE (A) VÀ 6 BIẾN THỂ (B)")
    output_lines.append("="*90)
    
    variants = [
        ("T1 (5m Range)", "pnl_t1"),
        ("T1 Intraday (5m Range, No Overnight)", "pnl_t1_intra"),
        ("T2 (15m Swing)", "pnl_t2"),
        ("T2 Intraday (15m Swing, No Overnight)", "pnl_t2_intra"),
        ("T3 (Day/Session High/Low)", "pnl_t3"),
        ("T3 Intraday (Day/Session, No Overnight)", "pnl_t3_intra"),
    ]
    
    header = f"{'Biến thể':<40} | {'N lệnh':<7} | {'WinRate':<8} | {'Tổng PnL':<10} | {'Expectancy':<12} | {'Δ vs Base':<10} | {'95% CI (B - A)':<18}"
    output_lines.append(header)
    output_lines.append("-" * 115)
    
    for v_name, col in variants:
        sub = df.dropna(subset=[col]).copy()
        n_trades = len(sub)
        pnl_b = sub[col]
        pnl_a = sub["pnl_base"]
        diff = pnl_b - pnl_a
        
        wr_b = (pnl_b > 0).mean() * 100
        tot_b = pnl_b.sum()
        exp_b = pnl_b.mean()
        diff_tot = diff.sum()
        
        np.random.seed(42)
        diff_vals = diff.values
        boot_diff = [np.mean(np.random.choice(diff_vals, size=len(diff_vals), replace=True)) for _ in range(5000)]
        ci = [np.percentile(boot_diff, 2.5), np.percentile(boot_diff, 97.5)]
        
        row_str = f"{v_name:<40} | {n_trades:<7} | {wr_b:6.1f}%  | {tot_b:+9.1f}  | {exp_b:+9.3f} pt  | {diff_tot:+8.1f}  | [{ci[0]:+5.2f}, {ci[1]:+5.2f}] pt"
        output_lines.append(row_str)

    output_lines.append("\n" + "="*90)
    output_lines.append("PHÂN RÃ THEO TỪNG NĂM: BASELINE (A) VS T1 (5m RANGE) VÀ T1 INTRADAY")
    output_lines.append("="*90)
    for yr in [2024, 2025, 2026]:
        sub_yr = df[df["year"] == yr].dropna(subset=["pnl_t1"])
        p_a = sub_yr["pnl_base"]
        p_t1 = sub_yr["pnl_t1"]
        p_t1_in = sub_yr["pnl_t1_intra"]
        output_lines.append(f"Năm {yr} (N={len(sub_yr)} lệnh):")
        output_lines.append(f"  Baseline A:           Tổng = {p_a.sum():+6.1f} pt | Mean = {p_a.mean():+6.2f} pt | WR = {(p_a>0).mean()*100:5.1f}%")
        output_lines.append(f"  T1 (Overnight):       Tổng = {p_t1.sum():+6.1f} pt | Mean = {p_t1.mean():+6.2f} pt | WR = {(p_t1>0).mean()*100:5.1f}% (Δ: {p_t1.sum()-p_a.sum():+5.1f} pt)")
        output_lines.append(f"  T1 Intraday (No O/N): Tổng = {p_t1_in.sum():+6.1f} pt | Mean = {p_t1_in.mean():+6.2f} pt | WR = {(p_t1_in>0).mean()*100:5.1f}% (Δ: {p_t1_in.sum()-p_a.sum():+5.1f} pt)")

    output_lines.append("\n" + "="*90)
    output_lines.append("KIỂM TRA ĐỘ BỀN ĐUÔI: BỎ 3 LỆNH THẮNG LỚN NHẤT & BỎ 3 LỆNH THUA LỚN NHẤT")
    output_lines.append("="*90)
    for v_name, col in [("Baseline A", "pnl_base"), ("T1 Overnight", "pnl_t1"), ("T1 Intraday", "pnl_t1_intra")]:
        vals = sorted(df.dropna(subset=[col])[col].values)
        tot_all = np.sum(vals)
        tot_no_top3 = np.sum(vals[:-3])
        tot_no_worst3 = np.sum(vals[3:])
        output_lines.append(f"{v_name:<20}: Tổng PnL = {tot_all:+6.1f} pt | Bỏ 3 lệnh THẮNG lớn nhất = {tot_no_top3:+6.1f} pt | Bỏ 3 lệnh THUA lớn nhất = {tot_no_worst3:+6.1f} pt")

    full_output = "\n".join(output_lines)
    with open("results/structural_exit_audit_results.txt", "w", encoding="utf-8") as f:
        f.write(full_output)
    print(full_output)

if __name__ == "__main__":
    run_detailed_breakdowns()
