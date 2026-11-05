import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

# =============================================================================
# KIỂM ĐỊNH HIỆU ỨNG ĐÁO HẠN VN30F1M (EXPIRATION STUDY)
# TIÊU CHÍ LOẠI ĐÃ ĐẶT TRƯỚC (PRE-REGISTERED KILL CRITERIA):
# 1. Biên gộp trung vị theo kỳ < 2.7 điểm (3 lần ma sát 0.9 pt) -> LOẠI.
# 2. 95% Bootstrap CI theo kỳ chứa 0 -> LOẠI.
# 3. Kết quả phụ thuộc vào 1-2 kỳ dị biệt (bỏ top-2 kỳ mà hiệu ứng <= 0) -> LOẠI.
# 4. Ngưỡng ý nghĩa thống kê hiệu chỉnh Bonferroni: p < 0.0125.
# =============================================================================

def get_expiration_date(year, month):
    # Thứ Năm tuần thứ 3 trong tháng
    first_day = pd.Timestamp(year, month, 1)
    day_of_week = first_day.dayofweek # Monday=0, Thursday=3
    days_to_thursday = (3 - day_of_week) % 7
    first_thursday = first_day + pd.Timedelta(days=days_to_thursday)
    third_thursday = first_thursday + pd.Timedelta(weeks=2)
    return third_thursday.date()

def run_expiration_study():
    # -------------------------------------------------------------------------
    # DỮ LIỆU ĐỒNG BỘ F1M & VN30 (09/2023 - 10/2026: 38 KỲ ĐÁO HẠN)
    # -------------------------------------------------------------------------
    df_sync = pd.read_parquet("trading_engine/data/VN30_Basis_1m.parquet")
    df_sync["datetime"] = pd.to_datetime(df_sync["datetime"])
    df_sync = df_sync.sort_values("datetime").reset_index(drop=True)
    df_sync["date"] = df_sync["datetime"].dt.date
    
    # -------------------------------------------------------------------------
    # DỮ LIỆU F1M DÀI HẠN (2018 - 2026: >100 KỲ ĐÁO HẠN)
    # -------------------------------------------------------------------------
    df_f1m_long = pd.read_parquet("trading_engine/data/VN30F1M_features.parquet")
    df_f1m_long["datetime"] = pd.to_datetime(df_f1m_long["datetime"])
    df_f1m_long = df_f1m_long.sort_values("datetime").reset_index(drop=True)
    df_f1m_long["date"] = df_f1m_long["datetime"].dt.date
    
    # Tính ngày đáo hạn chính xác cho từng ngày giao dịch
    def build_exp_info(df):
        unique_dates = sorted(df["date"].unique())
        exp_dates = []
        # Tìm tất cả thứ Năm tuần thứ 3 từ min_year đến max_year
        min_y = min(d.year for d in unique_dates)
        max_y = max(d.year for d in unique_dates)
        
        all_thursdays = []
        for y in range(min_y, max_y + 1):
            for m in range(1, 13):
                all_thursdays.append(get_expiration_date(y, m))
                
        # Map mỗi ngày giao dịch tới ngày đáo hạn tương ứng (ngày đáo hạn gần nhất >= date)
        date_to_exp = {}
        date_to_cycle = {}
        for d in unique_dates:
            future_exps = [exp for exp in all_thursdays if exp >= d]
            if len(future_exps) > 0:
                cur_exp = future_exps[0]
                date_to_exp[d] = cur_exp
                date_to_cycle[d] = f"{cur_exp.year}-{cur_exp.month:02d}"
            else:
                date_to_exp[d] = None
                date_to_cycle[d] = None
                
        df["exp_date"] = df["date"].map(date_to_exp)
        df["cycle"] = df["date"].map(date_to_cycle)
        # Tính số ngày giao dịch còn lại tới ngày đáo hạn (trading days to exp)
        # Tạo mapping số trading days
        t_days_map = {}
        for cyc, group in df.groupby("cycle"):
            cyc_dates = sorted(group["date"].unique())
            # target date is exp_date
            exp_d = group["exp_date"].iloc[0]
            for idx, d in enumerate(cyc_dates):
                # distance to last date of cycle (which is the expiration day)
                # trading days to expiration: 0 on expiration day, 1 on day before, etc.
                dist = len(cyc_dates) - 1 - idx
                t_days_map[d] = dist
        df["t_days_to_exp"] = df["date"].map(t_days_map)
        return df

    print("Building expiration mapping for synchronized data (2023-2026)...")
    df_sync = build_exp_info(df_sync)
    print("Building expiration mapping for long-term F1M data (2018-2026)...")
    df_f1m_long = build_exp_info(df_f1m_long)

    # =========================================================================
    # GIẢ THUYẾT H1a: BASIS HỘI TỤ VỀ 0 TRONG 5 NGÀY CUỐI (T = 5 -> 0)
    # Cơ chế: Basis có co hẹp không, và động lượng do F1M hay VN30 dịch chuyển?
    # =========================================================================
    print("\n" + "="*80)
    print("KIỂM ĐỊNH H1a: BASIS HỘI TỤ TỪ T=5 ĐẾN T=0 (DỮ LIỆU ĐỒNG BỘ 2023-2026, 38 KỲ)")
    print("="*80)
    
    # Với mỗi kỳ đáo hạn, lấy giá đóng cửa tại T=5 và T=0 (phiên đáo hạn)
    # Đo: ΔF1M, ΔVN30, ΔBasis
    h1a_records = []
    for cyc, g in df_sync.groupby("cycle"):
        if g["exp_date"].iloc[0] is None:
            continue
        # Lọc nến cuối ngày tại T=5 (hoặc ngày sớm nhất trong tuần đáo hạn nếu nghỉ lễ)
        t5_bars = g[g["t_days_to_exp"] == 5]
        t0_bars = g[g["t_days_to_exp"] == 0]
        
        if len(t5_bars) > 0 and len(t0_bars) > 0:
            p_f1m_start = t5_bars.iloc[-1]["Close"]
            p_vn30_start = t5_bars.iloc[-1]["close"]
            basis_start = p_f1m_start - p_vn30_start
            
            # Kết thúc lúc 14:15 ngày đáo hạn (trước khi vào ATC)
            t0_pre_atc = t0_bars[t0_bars["hour"] == 14]
            if len(t0_pre_atc) > 0:
                p_f1m_end = t0_pre_atc.iloc[-1]["Close"]
                p_vn30_end = t0_pre_atc.iloc[-1]["close"]
                basis_end = p_f1m_end - p_vn30_end
                
                h1a_records.append({
                    "cycle": cyc,
                    "basis_start": basis_start,
                    "basis_end": basis_end,
                    "delta_basis": basis_end - basis_start,
                    "delta_f1m": p_f1m_end - p_f1m_start,
                    "delta_vn30": p_vn30_end - p_vn30_start,
                })
                
    df_h1a = pd.DataFrame(h1a_records)
    print(f"Số kỳ có đủ dữ liệu T=5 và T=0: {len(df_h1a)} kỳ")
    print(f"Basis khởi điểm trung bình (T=5): {df_h1a['basis_start'].mean():+.2f} pts (Median: {df_h1a['basis_start'].median():+.2f})")
    print(f"Basis kết thúc trung bình (T=0):  {df_h1a['basis_end'].mean():+.2f} pts (Median: {df_h1a['basis_end'].median():+.2f})")
    print(f"ΔBasis hội tụ trung bình:         {df_h1a['delta_basis'].mean():+.2f} pts")
    print(f"ΔF1M di chuyển trung bình:         {df_h1a['delta_f1m'].mean():+.2f} pts")
    print(f"ΔVN30 di chuyển trung bình:        {df_h1a['delta_vn30'].mean():+.2f} pts")
    print("\nChi tiết từng kỳ: Có hiện tượng gì nhất quán không?")
    print(f"  Số kỳ F1M tăng: {(df_h1a['delta_f1m'] > 0).sum()}/{len(df_h1a)} ({(df_h1a['delta_f1m'] > 0).mean()*100:.1f}%)")
    print(f"  F1M Mean = {df_h1a['delta_f1m'].mean():+.2f} pts | Std = {df_h1a['delta_f1m'].std():.2f} pts | Median = {df_h1a['delta_f1m'].median():+.2f} pts")

    # =========================================================================
    # GIẢ THUYẾT H1b: ÁP LỰC ROLL VỊ THẾ 2-3 NGÀY TRƯỚC ĐÁO HẠN (T=3 -> T=1)
    # Kiểm định trên TOÀN BỘ 2018 - 2026 (>100 kỳ đáo hạn)
    # Cơ chế: Tổ chức roll vị thế (đóng F1M, mở F2M) có tạo áp lực ép giá F1M giảm không?
    # =========================================================================
    print("\n" + "="*80)
    print("KIỂM ĐỊNH H1b: ÁP LỰC ROLL TỪ T=3 ĐẾN T=1 (DỮ LIỆU F1M 2018-2026, >100 KỲ)")
    print("="*80)
    
    h1b_records = []
    for cyc, g in df_f1m_long.groupby("cycle"):
        if g["exp_date"].iloc[0] is None:
            continue
        t3_bars = g[g["t_days_to_exp"] == 3]
        t1_bars = g[g["t_days_to_exp"] == 1]
        
        if len(t3_bars) > 0 and len(t1_bars) > 0:
            # Giá mở cửa T=3 và giá đóng cửa T=1 (2 ngày ép roll)
            p_start = t3_bars.iloc[0]["Open"]
            p_end = t1_bars.iloc[-1]["Close"]
            ret_f1m = p_end - p_start
            year = t3_bars.iloc[0]["datetime"].year
            h1b_records.append({
                "cycle": cyc,
                "year": year,
                "ret_roll": ret_f1m
            })
            
    df_h1b = pd.DataFrame(h1b_records)
    print(f"Tổng số kỳ kiểm định từ 2018 đến 2026: {len(df_h1b)} kỳ")
    
    # Thống kê toàn kỳ
    mean_roll = df_h1b["ret_roll"].mean()
    med_roll = df_h1b["ret_roll"].median()
    std_roll = df_h1b["ret_roll"].std()
    win_short = (df_h1b["ret_roll"] < 0).mean() * 100
    
    # Bootstrap CI
    np.random.seed(42)
    boot_means = [np.mean(np.random.choice(df_h1b["ret_roll"].values, size=len(df_h1b), replace=True)) for _ in range(10000)]
    ci_95 = [np.percentile(boot_means, 2.5), np.percentile(boot_means, 97.5)]
    p_zero = (np.array(boot_means) >= 0).mean() if mean_roll < 0 else (np.array(boot_means) <= 0).mean()
    
    print(f"Biến động F1M trong 2 ngày Roll (T=3 -> T=1):")
    print(f"  Mean Return:   {mean_roll:+.2f} pts")
    print(f"  Median Return: {med_roll:+.2f} pts")
    print(f"  Std:           {std_roll:.2f} pts")
    print(f"  Tỷ lệ Short thắng (Giá giảm): {win_short:.1f}%")
    print(f"  Bootstrap 95% CI: [{ci_95[0]:+.2f}, {ci_95[1]:+.2f}] pts")
    print(f"  p-value: {p_zero:.4f}")
    
    # So sánh 2018-2022 vs 2023-2026
    sub_old = df_h1b[df_h1b["year"] <= 2022]
    sub_new = df_h1b[df_h1b["year"] >= 2023]
    print("\nSo sánh phân kỳ thời gian:")
    print(f"  2018-2022 (N={len(sub_old)} kỳ): Mean = {sub_old['ret_roll'].mean():+.2f} pts | Median = {sub_old['ret_roll'].median():+.2f} pts | Short Win: {(sub_old['ret_roll']<0).mean()*100:.1f}%")
    print(f"  2023-2026 (N={len(sub_new)} kỳ): Mean = {sub_new['ret_roll'].mean():+.2f} pts | Median = {sub_new['ret_roll'].median():+.2f} pts | Short Win: {(sub_new['ret_roll']<0).mean()*100:.1f}%")

    # =========================================================================
    # GIẢ THUYẾT H1c: 30 PHÚT CUỐI PHIÊN ĐÁO HẠN (13:45 - 14:45 T=0)
    # Cơ chế: Giá F1M có bị kéo về giá trị thanh toán trung bình của VN30 không?
    # Nếu tại 14:00, F1M lệch khỏi VN30, có edge hội tụ nào vượt ma sát không?
    # =========================================================================
    print("\n" + "="*80)
    print("KIỂM ĐỊNH H1c: HỘI TỤ 30 PHÚT CUỐI PHIÊN ĐÁO HẠN (13:45 - 14:45 T=0)")
    print("="*80)
    
    h1c_records = []
    # Lấy các ngày đáo hạn T=0 trong df_sync
    t0_days = df_sync[df_sync["t_days_to_exp"] == 0]["date"].unique()
    
    for d in t0_days:
        day_bars = df_sync[df_sync["date"] == d].copy()
        
        # Mốc 14:00 (hoặc 14:15) so với giá đóng cửa ATC
        bar_1400 = day_bars[(day_bars["hour"] == 14) & (day_bars["minute"] == 0)]
        bar_1415 = day_bars[(day_bars["hour"] == 14) & (day_bars["minute"] == 15)]
        bar_atc = day_bars.iloc[-1]
        
        if len(bar_1400) > 0:
            f1m_1400 = bar_1400.iloc[0]["Close"]
            vn30_1400 = bar_1400.iloc[0]["close"]
            basis_1400 = f1m_1400 - vn30_1400
            
            f1m_atc = bar_atc["Close"]
            vn30_atc = bar_atc["close"]
            
            # Nếu Basis_1400 < 0, Long F1M; nếu Basis_1400 > 0, Short F1M
            # Giả sử đánh theo hướng hội tụ Basis về ATC:
            pnl_convergence = -basis_1400 if basis_1400 > 0 else basis_1400 # nếu basis > 0, short; nếu < 0, long
            # Lợi nhuận F1M thực: nếu Basis < 0 (mua Long) -> Close_ATC - Close_1400
            # nếu Basis > 0 (bán Short) -> Close_1400 - Close_ATC
            f1m_trade_pnl = (f1m_atc - f1m_1400) if basis_1400 < 0 else (f1m_1400 - f1m_atc)
            
            h1c_records.append({
                "date": d,
                "basis_1400": basis_1400,
                "f1m_1400": f1m_1400,
                "f1m_atc": f1m_atc,
                "vn30_atc": vn30_atc,
                "f1m_pnl": f1m_trade_pnl,
                "abs_basis_1400": abs(basis_1400)
            })
            
    df_h1c = pd.DataFrame(h1c_records)
    print(f"Số phiên đáo hạn kiểm tra: {len(df_h1c)} phiên")
    print(f"Độ lệch Basis tuyệt đối tại 14:00: Mean = {df_h1c['abs_basis_1400'].mean():.2f} pts | Median = {df_h1c['abs_basis_1400'].median():.2f} pts | Max = {df_h1c['abs_basis_1400'].max():.2f} pts")
    
    mean_h1c = df_h1c["f1m_pnl"].mean()
    med_h1c = df_h1c["f1m_pnl"].median()
    win_h1c = (df_h1c["f1m_pnl"] > 0).mean() * 100
    
    boot_h1c = [np.mean(np.random.choice(df_h1c["f1m_pnl"].values, size=len(df_h1c), replace=True)) for _ in range(10000)]
    ci_h1c = [np.percentile(boot_h1c, 2.5), np.percentile(boot_h1c, 97.5)]
    p_h1c = (np.array(boot_h1c) <= 0).mean()
    
    print(f"\nKết quả giao dịch hội tụ từ 14:00 đến ATC ngày đáo hạn:")
    print(f"  PnL F1M gộp trung bình: {mean_h1c:+.2f} pts")
    print(f"  PnL F1M gộp trung vị:   {med_h1c:+.2f} pts")
    print(f"  Win Rate:               {win_h1c:.1f}%")
    print(f"  Bootstrap 95% CI:       [{ci_h1c[0]:+.2f}, {ci_h1c[1]:+.2f}] pts")
    print(f"  p-value (mean <= 0):    {p_h1c:.4f}")
    
    # Kiểm tra loại bỏ 2 kỳ tốt nhất
    sorted_pnl = sorted(df_h1c["f1m_pnl"].values)
    pnl_no_top2 = sorted_pnl[:-2]
    print(f"  PnL sau khi bỏ 2 kỳ tốt nhất: Mean = {np.mean(pnl_no_top2):+.2f} pts | Median = {np.median(pnl_no_top2):+.2f} pts")

if __name__ == "__main__":
    run_expiration_study()

