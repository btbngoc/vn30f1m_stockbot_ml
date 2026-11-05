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

def load_data():
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"])
    features = features.sort_values("datetime").reset_index(drop=True)
    
    trades_seed42 = pd.read_csv("results/all_trades_visualize.csv")
    trades_seed42["entry_time"] = pd.to_datetime(trades_seed42["entry_time"])
    trades_seed42["exit_time"] = pd.to_datetime(trades_seed42["exit_time"])
    
    return features, trades_seed42

# Helper để tính Swing High/Low trên 15m
def compute_swing_levels_15m(df_1m):
    # Resample sang 15m để tìm swing points
    df_15m = df_1m.set_index("datetime").resample("15min").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last"
    }).dropna().reset_index()
    
    highs = df_15m["High"].values
    lows = df_15m["Low"].values
    n = len(df_15m)
    
    is_swing_high = np.zeros(n, dtype=bool)
    is_swing_low = np.zeros(n, dtype=bool)
    
    # N=5 nến 15m mỗi bên
    for i in range(5, n - 5):
        if highs[i] == np.max(highs[i-5:i+6]) and highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            is_swing_high[i] = True
        if lows[i] == np.min(lows[i-5:i+6]) and lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            is_swing_low[i] = True
            
    df_15m["is_swing_high"] = is_swing_high
    df_15m["is_swing_low"] = is_swing_low
    return df_15m

def run_step1_audit():
    features, trades = load_data()
    print(f"Features: {len(features)} nến | Trades Seed 42: {len(trades)} lệnh")
    
    # Tạo mapping datetime -> index trong features
    dt_to_idx = {dt: i for i, dt in enumerate(features["datetime"])}
    
    # Chuẩn bị daily highs & lows
    features["date"] = features["datetime"].dt.date
    daily_stats = features.groupby("date").agg({"High": "max", "Low": "min"}).shift(1) # hôm trước
    prev_day_high_map = daily_stats["High"].to_dict()
    prev_day_low_map = daily_stats["Low"].to_dict()
    
    # Tính swing levels 15m
    print("Computing 15m swing levels...")
    df_15m = compute_swing_levels_15m(features[["datetime", "Open", "High", "Low", "Close"]])
    swing_highs = df_15m[df_15m["is_swing_high"]][["datetime", "High"]].values
    swing_lows = df_15m[df_15m["is_swing_low"]][["datetime", "Low"]].values
    
    results = []
    
    for idx_t, trade in trades.iterrows():
        t_entry = trade["entry_time"]
        t_exit = trade["exit_time"]
        p_entry = trade["entry_price"]
        p_exit = trade["exit_price"]
        pos = 1 if trade["type"].upper() in ("LONG", "BUY") else -1
        hard_sl = trade["hard_sl"]
        init_sl = trade["initial_sl"]
        pnl_base = trade["points"]
        
        if t_entry not in dt_to_idx:
            continue
        e_idx = dt_to_idx[t_entry]
        x_idx = dt_to_idx.get(t_exit, e_idx + trade["bars_held"])
        
        # 1. T1: RangeHigh / RangeLow 5m (120 nến 1m trước entry)
        w_start = max(0, e_idx - 120)
        window_prior = features.iloc[w_start:e_idx]
        t1_target = window_prior["High"].max() if pos == 1 else window_prior["Low"].min()
        
        # 2. T2: Swing high / low 15m gần nhất
        # Tìm swing high trước t_entry và nằm trên p_entry (nếu Long)
        if pos == 1:
            valid_swings = [sh[1] for sh in swing_highs if sh[0] < t_entry and sh[1] > p_entry + 1.0]
            t2_target = valid_swings[-1] if len(valid_swings) > 0 else window_prior["High"].max()
        else:
            valid_swings = [sl[1] for sl in swing_lows if sl[0] < t_entry and sl[1] < p_entry - 1.0]
            t2_target = valid_swings[-1] if len(valid_swings) > 0 else window_prior["Low"].min()
            
        # 3. T3: Đỉnh / Đáy ngày hôm trước hoặc đỉnh phiên
        cur_date = t_entry.date()
        prev_h = prev_day_high_map.get(cur_date, window_prior["High"].max())
        prev_l = prev_day_low_map.get(cur_date, window_prior["Low"].min())
        # Đỉnh / đáy phiên hôm nay tính tới entry
        today_bars = features.iloc[max(0, e_idx - 300):e_idx]
        today_bars = today_bars[today_bars["date"] == cur_date]
        today_h = today_bars["High"].max() if len(today_bars) > 0 else p_entry
        today_l = today_bars["Low"].min() if len(today_bars) > 0 else p_entry
        
        t3_target = max(prev_h, today_h) if pos == 1 else min(prev_l, today_l)
        
        # Khoảng cách tới mục tiêu
        dist_t1 = (t1_target - p_entry) * pos
        dist_t2 = (t2_target - p_entry) * pos
        dist_t3 = (t3_target - p_entry) * pos
        
        # 4. Quỹ đạo nến trong lệnh (Trade Path)
        trade_bars = features.iloc[e_idx + 1 : min(len(features), x_idx + 1)]
        if len(trade_bars) == 0:
            trade_bars = features.iloc[e_idx : e_idx + 1]
            
        highs = trade_bars["High"].values
        lows = trade_bars["Low"].values
        closes = trade_bars["Close"].values
        
        # MFE & MAE
        if pos == 1:
            mfe_arr = highs - p_entry
            mae_arr = lows - p_entry
            mfe = np.max(mfe_arr)
            mae = np.min(mae_arr) # <= 0
            mfe_bar = np.argmax(mfe_arr) + 1
        else:
            mfe_arr = p_entry - lows
            mae_arr = p_entry - highs
            mfe = np.max(mfe_arr)
            mae = np.min(mae_arr) # <= 0
            mfe_bar = np.argmax(mfe_arr) + 1
            
        atr_5m = float(features.iloc[e_idx].get("HTF_5m_ATR", 2.0))
        
        # Squeeze Check: Có bị quét ngược >= 1.0 * ATR_5m trước khi đạt MFE không?
        # Kiểm tra min mae trước khi bar đạt MFE
        if mfe_bar > 1:
            mae_before_mfe = np.min(mae_arr[:mfe_bar])
        else:
            mae_before_mfe = mae_arr[0]
        was_squeezed_1atr = mae_before_mfe <= -atr_5m
        
        # Kiểm tra va chạm: Target chạm trước hay Stop chạm trước?
        # Target hit: High >= T (Long) hoặc Low <= T (Short)
        # Stop hit: Low <= hard_sl (Long) hoặc High >= hard_sl (Short)
        def check_race(target_val):
            if (target_val - p_entry) * pos < 1.5:
                return "SKIP_TOO_CLOSE", 0, 0
            for b_idx in range(len(trade_bars)):
                h_b, l_b = highs[b_idx], lows[b_idx]
                # Check Target
                hit_target = (h_b >= target_val) if pos == 1 else (l_b <= target_val)
                # Check Stop (Hard SL)
                hit_stop = (l_b <= hard_sl) if pos == 1 else (h_b >= hard_sl)
                
                if hit_target and not hit_stop:
                    return "HIT_TARGET", b_idx + 1, (target_val - p_entry) * pos
                elif hit_stop and not hit_target:
                    return "HIT_STOP", b_idx + 1, (hard_sl - p_entry) * pos
                elif hit_target and hit_stop:
                    # Trùng nến -> bảo thủ coi là dính Stop
                    return "HIT_STOP", b_idx + 1, (hard_sl - p_entry) * pos
            return "EXPIRED_BEFORE_BOTH", len(trade_bars), (closes[-1] - p_entry) * pos

        res_t1, bar_t1, pnl_t1 = check_race(t1_target)
        res_t2, bar_t2, pnl_t2 = check_race(t2_target)
        res_t3, bar_t3, pnl_t3 = check_race(t3_target)
        
        results.append({
            "id": trade["id"],
            "year": t_entry.year,
            "type": trade["type"],
            "entry_price": p_entry,
            "pnl_base": pnl_base,
            "mfe": mfe,
            "mae": mae,
            "mfe_bar": mfe_bar,
            "atr_5m": atr_5m,
            "was_squeezed_1atr": was_squeezed_1atr,
            "dist_t1": dist_t1,
            "dist_t2": dist_t2,
            "dist_t3": dist_t3,
            "res_t1": res_t1, "pnl_t1": pnl_t1,
            "res_t2": res_t2, "pnl_t2": pnl_t2,
            "res_t3": res_t3, "pnl_t3": pnl_t3,
        })
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print("BƯỚC 1: PHÂN PHỐI MFE / MAE VÀ ĐO LƯỜNG SQUEEZE TRÊN 160 LỆNH (SEED 42)")
    print("="*80)
    
    print(f"MFE (Lãi thuận lợi tối đa):")
    print(f"  Mean:   {res_df['mfe'].mean():.2f} pts")
    print(f"  Median: {res_df['mfe'].median():.2f} pts")
    print(f"  IQR:    [{np.percentile(res_df['mfe'], 25):.2f}, {np.percentile(res_df['mfe'], 75):.2f}] pts")
    print(f"  Top 10% đuôi lớn (MFE >= 20 pts): {(res_df['mfe'] >= 20.0).sum()} lệnh ({(res_df['mfe'] >= 20.0).mean()*100:.1f}%)")
    print(f"  Max MFE: {res_df['mfe'].max():.2f} pts")
    
    print(f"\nMAE (Mức lỗ ngược tối đa):")
    print(f"  Mean:   {res_df['mae'].mean():.2f} pts")
    print(f"  Median: {res_df['mae'].median():.2f} pts")
    print(f"  IQR:    [{np.percentile(res_df['mae'], 25):.2f}, {np.percentile(res_df['mae'], 75):.2f}] pts")
    print(f"  Min MAE: {res_df['mae'].min():.2f} pts")

    print(f"\nSqueeze Analysis (Bị rung lắc ngược >= 1.0 ATR 5m trước khi đạt đỉnh MFE):")
    n_sq = res_df["was_squeezed_1atr"].sum()
    print(f"  Số lệnh bị squeeze trước khi chạy MFE: {n_sq}/{len(res_df)} ({n_sq/len(res_df)*100:.1f}%)")

    # Đánh giá 3 mục tiêu cấu trúc T1, T2, T3
    for name, t_col, res_col, pnl_col in [
        ("T1: RangeHigh/Low Hộp 5m", "dist_t1", "res_t1", "pnl_t1"),
        ("T2: Swing High/Low 15m", "dist_t2", "res_t2", "pnl_t2"),
        ("T3: Đỉnh/Đáy Phiên & Ngày hôm trước", "dist_t3", "res_t3", "pnl_t3"),
    ]:
        print("\n" + "-"*60)
        print(f"ĐÁNH GIÁ MỤC TIÊU {name}")
        print("-"*60)
        dist = res_df[t_col]
        print(f"Khoảng cách tới mục tiêu lúc vào: Mean = {dist.mean():.2f} pts | Median = {dist.median():.2f} pts")
        
        # Bỏ qua các lệnh < 1.5 điểm
        valid = res_df[dist >= 1.5]
        print(f"Số lệnh đủ điều kiện (Khoảng cách >= 1.5 pts): {len(valid)}/{len(res_df)}")
        
        hit_tg = (valid[res_col] == "HIT_TARGET").sum()
        hit_sl = (valid[res_col] == "HIT_STOP").sum()
        expired = (valid[res_col] == "EXPIRED_BEFORE_BOTH").sum()
        
        print(f"  Tỷ lệ chạm Target trước Stop: {hit_tg}/{len(valid)} ({hit_tg/len(valid)*100:.1f}%)")
        print(f"  Tỷ lệ chạm Stop trước Target:   {hit_sl}/{len(valid)} ({hit_sl/len(valid)*100:.1f}%)")
        print(f"  Không chạm cả 2 (hết lệnh):     {expired}/{len(valid)} ({expired/len(valid)*100:.1f}%)")
        
        # So sánh PnL cặp (Paired Comparison) giữa Chốt T và Baseline Thả lãi
        pnl_paired_b = valid[pnl_col]
        pnl_paired_a = valid["pnl_base"]
        diff = pnl_paired_b - pnl_paired_a
        
        print(f"\n  SO SÁNH CẶP (PAIRED) TRÊN CÙNG {len(valid)} LỆNH:")
        print(f"    Tổng PnL Baseline (Thả lãi A):   {pnl_paired_a.sum():+.2f} pts (Mean: {pnl_paired_a.mean():+.2f})")
        print(f"    Tổng PnL Chốt sớm (Mục tiêu B):   {pnl_paired_b.sum():+.2f} pts (Mean: {pnl_paired_b.mean():+.2f})")
        print(f"    Chênh lệch (B - A):              {diff.sum():+.2f} pts (Mean: {diff.mean():+.2f})")
        
        # Win rate
        wr_a = (pnl_paired_a > 0).mean() * 100
        wr_b = (pnl_paired_b > 0).mean() * 100
        print(f"    Win Rate Baseline A: {wr_a:.1f}% | Win Rate Chốt B: {wr_b:.1f}%")
        
        # Bootstrap CI cho chênh lệch
        np.random.seed(42)
        diff_vals = diff.values
        boot_diff = [np.mean(np.random.choice(diff_vals, size=len(diff_vals), replace=True)) for _ in range(10000)]
        ci_diff = [np.percentile(boot_diff, 2.5), np.percentile(boot_diff, 97.5)]
        p_val_zero = (np.array(boot_diff) <= 0).mean()
        print(f"    95% Bootstrap CI của (B - A): [{ci_diff[0]:+.2f}, {ci_diff[1]:+.2f}] pts | p(B > A): {1 - p_val_zero:.4f}")

if __name__ == "__main__":
    run_step1_audit()

