import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import os
import time
import requests
import numpy as np
import pandas as pd

from trading_engine.data.vci_api import fetch_vci_1m_one_shot

# ==============================================================================
# BƯỚC 1: TẢI TOÀN BỘ DỮ LIỆU 1-PHÚT CỦA CHỈ SỐ VN30 TỪ API VIETCAP
# ==============================================================================
vn30_parquet_path = "trading_engine/data/VN30_1m.parquet"

if not os.path.exists(vn30_parquet_path):
    print("Đang tải dữ liệu 1-phút của chỉ số VN30 từ API Vietcap...")
    chunks = []
    current_to = int(time.time())
    
    # Tải từng chunk 100,000 nến
    for i in range(4):
        print(f"  • Đang tải chunk {i+1} (kết thúc tại timestamp {current_to})...")
        df_chunk = fetch_vci_1m_one_shot("VN30", count_back=100000, to_epoch=current_to)
        if df_chunk.empty:
            print(f"    -> Hết dữ liệu tại chunk {i+1}.")
            break
        print(f"    -> Tải thành công {len(df_chunk)} nến từ {df_chunk['time'].min()} đến {df_chunk['time'].max()}")
        chunks.append(df_chunk)
        # Cập nhật mốc kết thúc cho chunk tiếp theo (lùi 1 giây trước nến sớm nhất)
        earliest_dt = df_chunk['time'].min()
        current_to = int(pd.Timestamp(earliest_dt, tz="Asia/Ho_Chi_Minh").timestamp()) - 1
        time.sleep(1)

    all_vn30 = pd.concat(chunks, ignore_index=True)
    all_vn30 = all_vn30.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    all_vn30.to_parquet(vn30_parquet_path)
    print(f"-> Đã lưu thành công {len(all_vn30)} nến 1-phút VN30 vào {vn30_parquet_path}")
else:
    print(f"Đã có sẵn file cache: {vn30_parquet_path}")
    all_vn30 = pd.read_parquet(vn30_parquet_path)
    print(f"Loaded {len(all_vn30)} nến 1-phút VN30 từ {all_vn30['time'].min()} đến {all_vn30['time'].max()}")

# ==============================================================================
# BƯỚC 2: KHỚP NỐI VỚI VN30F1M VÀ TÍNH CHUỖI BASIS
# ==============================================================================
print("\nĐang khớp nối với dữ liệu VN30F1M...")
f1m = pd.read_parquet("trading_engine/data/VN30F1M_features.parquet")
f1m["datetime"] = pd.to_datetime(f1m["datetime"])

all_vn30["datetime"] = pd.to_datetime(all_vn30["time"])
merged = pd.merge(
    f1m[["datetime", "Open", "High", "Low", "Close", "Volume"]],
    all_vn30[["datetime", "open", "high", "low", "close", "volume"]],
    on="datetime",
    suffixes=("_f1m", "_vn30")
).sort_values("datetime").reset_index(drop=True)

merged["basis"] = merged["Close"] - merged["close"]
print(f"Số nến khớp hoàn hảo 1-1: {len(merged)} nến (từ {merged['datetime'].min()} đến {merged['datetime'].max()})")

# Tính các biến số lịch và độ lệch thống kê
merged["date"] = merged["datetime"].dt.date
merged["year"] = merged["datetime"].dt.year
merged["hour"] = merged["datetime"].dt.hour
merged["minute"] = merged["datetime"].dt.minute

# Rolling statistics của Basis
merged["basis_ma60"] = merged["basis"].rolling(60).mean()
merged["basis_std60"] = merged["basis"].rolling(60).std()
merged["basis_z60"] = (merged["basis"] - merged["basis_ma60"]) / (merged["basis_std60"] + 1e-6)

# Tính ngày đáo hạn phái sinh (thứ 5 tuần thứ 3 hàng tháng)
def get_expiration_date(year, month):
    # Tìm thứ 5 đầu tiên của tháng
    first_day = pd.Timestamp(year, month, 1)
    day_of_week = first_day.dayofweek # Monday is 0, Thursday is 3
    days_to_thursday = (3 - day_of_week) % 7
    first_thursday = first_day + pd.Timedelta(days=days_to_thursday)
    # Thứ 5 tuần thứ 3 = first_thursday + 2 tuần
    third_thursday = first_thursday + pd.Timedelta(weeks=2)
    return third_thursday.date()

dates = pd.Series(merged["date"].unique())
exp_map = {}
for d in dates:
    exp_d = get_expiration_date(d.year, d.month)
    if d > exp_d:
        # Nếu đã qua ngày đáo hạn tháng này, hợp đồng chuyển sang tháng sau
        next_m = 1 if d.month == 12 else d.month + 1
        next_y = d.year + 1 if d.month == 12 else d.year
        exp_d = get_expiration_date(next_y, next_m)
    exp_map[d] = (pd.to_datetime(exp_d) - pd.to_datetime(d)).days

merged["days_to_exp"] = merged["date"].map(exp_map)

# Lưu file phân tích Basis
merged.to_parquet("trading_engine/data/VN30_Basis_1m.parquet")
print("Đã lưu chuỗi dữ liệu Basis vào trading_engine/data/VN30_Basis_1m.parquet")

# ==============================================================================
# BƯỚC 3: EVENT STUDY - ĐO LƯỜNG BIÊN LỢI NHUẬN GỘP THÔ (GROSS EDGE)
# ==============================================================================
print("\n" + "="*80)
print("BƯỚC 3: EVENT STUDY - KHẢO SÁT HIỆU ỨNG HỒI QUY BASIS CỰC ĐOAN (MEAN REVERSION)")
print("="*80)

# Khảo sát các ngưỡng Basis âm cực đoan (Backwardation)
# Tránh các tín hiệu liền kề nhau: áp dụng khoảng đệm cooldown 30 nến giữa các sự kiện
def run_event_study(df, condition_col, condition_val, direction="BUY_F1M", cooldown=30, horizons=[15, 30, 60, 120, 240]):
    events = []
    last_idx = -cooldown
    
    close_f1m = df["Close"].values
    basis_vals = df["basis"].values
    dtimes = df["datetime"].values
    
    cond_mask = (df[condition_col] <= condition_val) if direction == "BUY_F1M" else (df[condition_col] >= condition_val)
    cond_indices = np.where(cond_mask)[0]
    
    for idx in cond_indices:
        if idx - last_idx >= cooldown:
            if idx + max(horizons) < len(df):
                ev = {
                    "datetime": dtimes[idx],
                    "entry_basis": basis_vals[idx],
                    "entry_f1m": close_f1m[idx],
                }
                for h in horizons:
                    fwd_basis = basis_vals[idx + h]
                    fwd_f1m = close_f1m[idx + h]
                    # Delta Basis (hồi quy về 0)
                    delta_b = (fwd_basis - basis_vals[idx]) if direction == "BUY_F1M" else (basis_vals[idx] - fwd_basis)
                    # PnL F1M thuần túy (điểm)
                    delta_f1m = (fwd_f1m - close_f1m[idx]) if direction == "BUY_F1M" else (close_f1m[idx] - fwd_f1m)
                    ev[f"delta_basis_{h}m"] = delta_b
                    ev[f"f1m_pnl_{h}m"] = delta_f1m
                events.append(ev)
                last_idx = idx

    return pd.DataFrame(events)

print("\n--- A. SỰ KIỆN BASIS ÂM CỰC ĐOAN (CHIẾT KHẤU SÂU: LONG F1M CHỜ BASIS HỒI QUY) ---")
thresholds_neg = [-4.0, -6.0, -8.0, -10.0]

for th in thresholds_neg:
    ev_df = run_event_study(merged, "basis", th, direction="BUY_F1M", cooldown=30)
    if len(ev_df) >= 10:
        print(f"\n[Sự kiện Basis <= {th:4.1f} pts] (Số sự kiện độc lập N = {len(ev_df)}):")
        print(f"{'Horizon':<10} | {'Biên hồi quy Basis':<20} | {'Lợi nhuận gộp F1M':<20} | {'Win Rate F1M':<12} | {'Biên thô >= 3x ma sát (2.7pt)?'}")
        print("-" * 85)
        for h in [15, 30, 60, 120, 240]:
            b_move = ev_df[f"delta_basis_{h}m"].mean()
            f1m_move = ev_df[f"f1m_pnl_{h}m"].mean()
            f1m_wr = (ev_df[f"f1m_pnl_{h}m"] > 0).mean() * 100
            passed_friction = "ĐẠT (>= 2.7 pts)" if f1m_move >= 2.7 else "KHÔNG ĐẠT"
            print(f"{h:3d} phút   | {b_move:>+6.2f} pts             | {f1m_move:>+6.2f} pts             | {f1m_wr:5.1f}%       | {passed_friction}")

print("\n" + "-"*85)
print("--- B. SỰ KIỆN BASIS DƯƠNG CỰC ĐOAN (THẶNG DƯ CAO: SHORT F1M CHỜ BASIS CO HẸP) ---")
thresholds_pos = [+4.0, +6.0, +8.0, +10.0]

for th in thresholds_pos:
    ev_df = run_event_study(merged, "basis", th, direction="SELL_F1M", cooldown=30)
    if len(ev_df) >= 10:
        print(f"\n[Sự kiện Basis >= +{th:4.1f} pts] (Số sự kiện độc lập N = {len(ev_df)}):")
        print(f"{'Horizon':<10} | {'Biên hồi quy Basis':<20} | {'Lợi nhuận gộp F1M':<20} | {'Win Rate F1M':<12} | {'Biên thô >= 3x ma sát (2.7pt)?'}")
        print("-" * 85)
        for h in [15, 30, 60, 120, 240]:
            b_move = ev_df[f"delta_basis_{h}m"].mean()
            f1m_move = ev_df[f"f1m_pnl_{h}m"].mean()
            f1m_wr = (ev_df[f"f1m_pnl_{h}m"] > 0).mean() * 100
            passed_friction = "ĐẠT (>= 2.7 pts)" if f1m_move >= 2.7 else "KHÔNG ĐẠT"
            print(f"{h:3d} phút   | {b_move:>+6.2f} pts             | {f1m_move:>+6.2f} pts             | {f1m_wr:5.1f}%       | {passed_friction}")

# ==============================================================================
# BƯỚC 4: EVENT STUDY QUANH TUẦN ĐÁO HẠN (EXPIRATION CONVERGENCE)
# ==============================================================================
print("\n" + "="*80)
print("BƯỚC 4: EVENT STUDY TUẦN ĐÁO HẠN (3 NGÀY TRƯỚC ĐÁO HẠN: DAYS_TO_EXP <= 3)")
print("="*80)

near_exp = merged[merged["days_to_exp"] <= 3].copy()
far_exp = merged[merged["days_to_exp"] > 7].copy()

print(f"Basis trung bình khi xa ngày đáo hạn (> 7 ngày) : {far_exp['basis'].mean():>+6.2f} pts (Std: {far_exp['basis'].std():.2f})")
print(f"Basis trung bình sát ngày đáo hạn (<= 3 ngày)   : {near_exp['basis'].mean():>+6.2f} pts (Std: {near_exp['basis'].std():.2f})")
print(f"Basis tại phiên đáo hạn (Day of Expiration)      : {merged[merged['days_to_exp']==0]['basis'].mean():>+6.2f} pts (Std: {merged[merged['days_to_exp']==0]['basis'].std():.2f})")

print("\nHoàn tất toàn bộ Event Study thô.")

