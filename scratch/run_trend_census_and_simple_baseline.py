import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

# Load features
features = pd.read_parquet("trading_engine/data/VN30F1M_features.parquet")
features["datetime"] = pd.to_datetime(features["datetime"])
features = features.sort_values("datetime").reset_index(drop=True)

print(f"Tổng dữ liệu 1-phút: {len(features)} dòng từ {features['datetime'].min()} đến {features['datetime'].max()}")

# Resample Daily để đếm số trend lớn
daily = features.set_index("datetime").resample("1D").agg({
    "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
}).dropna()
daily = daily[daily["Volume"] > 0].copy()
daily["date"] = daily.index.date
daily["year"] = daily.index.year

print(f"Tổng số ngày giao dịch: {len(daily)} ngày")

# ==============================================================================
# PHẦN 1: ĐẾM SỐ TREND LỚN TRONG DỮ LIỆU (2018 - 2026)
# Định nghĩa: Một nhịp sóng (Swing Trend) có biên độ >= 40 điểm kéo dài >= 2 ngày
# ==============================================================================
print("\n" + "="*80)
print("PHẦN 1: THỐNG KÊ TỔNG ĐIỀU TRA SỐ TREND LỚN (>= 40 ĐIỂM, >= 2 NGÀY)")
print("="*80)

# Thuật toán ZigZag nhận diện các đỉnh/đáy sóng thực tế với ngưỡng đảo chiều tối thiểu 20 điểm
def extract_swings(df_daily, rev_threshold=20.0):
    swings = []
    trend = 0 # 1: Up, -1: Down
    extreme_p = df_daily.iloc[0]["Close"]
    extreme_idx = 0
    extreme_date = df_daily.index[0]

    for i in range(1, len(df_daily)):
        row = df_daily.iloc[i]
        c = row["Close"]
        dt = df_daily.index[i]

        if trend == 0:
            if c >= extreme_p + rev_threshold:
                trend = 1
                extreme_p = c
                extreme_idx = i
                extreme_date = dt
            elif c <= extreme_p - rev_threshold:
                trend = -1
                extreme_p = c
                extreme_idx = i
                extreme_date = dt
        elif trend == 1:
            if c > extreme_p:
                extreme_p = c
                extreme_idx = i
                extreme_date = dt
            elif c <= extreme_p - rev_threshold:
                # Ghi nhận đỉnh
                swings.append({
                    "start_date": swings[-1]["end_date"] if len(swings) > 0 else df_daily.index[0],
                    "end_date": extreme_date,
                    "type": "UP",
                    "start_price": swings[-1]["end_price"] if len(swings) > 0 else df_daily.iloc[0]["Close"],
                    "end_price": extreme_p,
                })
                # Bắt đầu sóng giảm
                trend = -1
                extreme_p = c
                extreme_idx = i
                extreme_date = dt
        elif trend == -1:
            if c < extreme_p:
                extreme_p = c
                extreme_idx = i
                extreme_date = dt
            elif c >= extreme_p + rev_threshold:
                # Ghi nhận đáy
                swings.append({
                    "start_date": swings[-1]["end_date"] if len(swings) > 0 else df_daily.index[0],
                    "end_date": extreme_date,
                    "type": "DOWN",
                    "start_price": swings[-1]["end_price"] if len(swings) > 0 else df_daily.iloc[0]["Close"],
                    "end_price": extreme_p,
                })
                # Bắt đầu sóng tăng
                trend = 1
                extreme_p = c
                extreme_idx = i
                extreme_date = dt

    sw_df = pd.DataFrame(swings)
    if not sw_df.empty:
        sw_df["points"] = (sw_df["end_price"] - sw_df["start_price"]).abs()
        sw_df["days"] = (pd.to_datetime(sw_df["end_date"]) - pd.to_datetime(sw_df["start_date"])).dt.days
        sw_df["year"] = pd.to_datetime(sw_df["start_date"]).dt.year
    return sw_df

swings_all = extract_swings(daily, rev_threshold=20.0)
major_trends = swings_all[(swings_all["points"] >= 40.0) & (swings_all["days"] >= 2)].copy()

print(f"Tổng số sóng thị trường (ZigZag >= 20 pt): {len(swings_all)}")
print(f"Tổng số TREND LỚN (>= 40 điểm và >= 2 ngày) trong gần 9 năm: {len(major_trends)} sóng")
print(f"  • Trung bình mỗi năm chỉ có: {len(major_trends) / (len(daily)/245):.1f} trend lớn!")

# Phân bổ theo năm
trend_by_year = major_trends.groupby("year")["points"].agg(["count", "mean", "max"]).reset_index()
print("\nPhân bổ Trend lớn theo năm:")
for r in trend_by_year.itertuples():
    print(f"  Năm {r.year}: {r.count:2d} trend lớn | Biên độ trung bình: {r.mean:5.1f} pts | Lớn nhất: {r.max:5.1f} pts")

t_2018_2022 = major_trends[major_trends["year"] <= 2022]
t_2024_2026 = major_trends[major_trends["year"] >= 2024]
print(f"\n-> Giai đoạn 2018–2022 (5 năm): Có {len(t_2018_2022)} trend lớn (trung bình {len(t_2018_2022)/5:.1f} trend/năm)")
print(f"-> Giai đoạn 2024–2026 (gần 3 năm): Có {len(t_2024_2026)} trend lớn (trung bình {len(t_2024_2026)/2.8:.1f} trend/năm)")

# ==============================================================================
# PHẦN 2: CHẠY BASELINE TREND ĐƠN GIẢN (DONCHIAN BREAKOUT + ATR TRAILING)
# Khung nến: 15-phút (resample từ 1m), N=20 (Phá đỉnh/đáy 20 nến 15m = 5 giờ), Trailing Stop = 2.0 * ATR
# ==============================================================================
print("\n" + "="*80)
print("PHẦN 2: THỰC THI BASELINE TREND ĐƠN GIẢN TRÊN 2018–2022 VÀ 2024–2026")
print("Quy tắc: Phá đỉnh/đáy 20 nến 15m (Donchian 20), Trailing Stop 2.0 ATR, Trượt 0.3 pt, Phí 30k")
print("="*80)

# Tạo nến 15-phút
bars_15m = features.set_index("datetime").resample("15min").agg({
    "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
}).dropna()
bars_15m = bars_15m[bars_15m["Volume"] > 0].copy()

# Tính Donchian và ATR
bars_15m["High_N"] = bars_15m["High"].shift(1).rolling(20).max()
bars_15m["Low_N"] = bars_15m["Low"].shift(1).rolling(20).min()
bars_15m["tr"] = np.maximum(
    bars_15m["High"] - bars_15m["Low"],
    np.maximum(
        (bars_15m["High"] - bars_15m["Close"].shift(1)).abs(),
        (bars_15m["Low"] - bars_15m["Close"].shift(1)).abs()
    )
)
bars_15m["ATR"] = bars_15m["tr"].rolling(14).mean()

def run_simple_trend(df_bars, slip=0.3, fee=15000.0, atr_mult=2.0):
    trades = []
    pos = 0
    entry_p = 0.0
    entry_t = None
    stop_p = 0.0

    for t, r in df_bars.iterrows():
        op, hi, lo, cl = r["Open"], r["High"], r["Low"], r["Close"]
        hi_n, lo_n = r["High_N"], r["Low_N"]
        atr = r["ATR"] if not np.isnan(r["ATR"]) and r["ATR"] > 0 else 2.0

        if pos != 0:
            raw_exit = None
            reason = ""
            # Trailing stop
            if pos == 1:
                stop_p = max(stop_p, cl - atr_mult * atr)
                if lo <= stop_p:
                    raw_exit = stop_p
                    reason = "Trailing_SL"
                elif cl < lo_n: # Đảo chiều phá đáy
                    raw_exit = cl
                    reason = "Reverse"
            else:
                stop_p = min(stop_p, cl + atr_mult * atr)
                if hi >= stop_p:
                    raw_exit = stop_p
                    reason = "Trailing_SL"
                elif cl > hi_n: # Đảo chiều phá đỉnh
                    raw_exit = cl
                    reason = "Reverse"

            if raw_exit is not None:
                actual_exit = raw_exit
                if reason == "Trailing_SL":
                    if pos == 1 and op < raw_exit: actual_exit = op
                    elif pos == -1 and op > raw_exit: actual_exit = op

                ex_p = round(actual_exit - pos * slip, 1)
                pts = (ex_p - entry_p) * pos
                net_pnl = pts * 100000.0 - 2 * fee
                trades.append({
                    "entry_time": entry_t,
                    "exit_time": t,
                    "type": "LONG" if pos == 1 else "SHORT",
                    "entry_price": entry_p,
                    "exit_price": ex_p,
                    "points": pts,
                    "net_pnl": net_pnl,
                    "reason": reason
                })
                pos = 0

        if pos == 0 and not np.isnan(hi_n) and not np.isnan(lo_n):
            if cl > hi_n:
                pos = 1
                entry_t = t
                entry_p = round(cl + slip, 1)
                stop_p = round(entry_p - atr_mult * atr, 1)
            elif cl < lo_n:
                pos = -1
                entry_t = t
                entry_p = round(cl - slip, 1)
                stop_p = round(entry_p + atr_mult * atr, 1)

    return pd.DataFrame(trades)

# 1. Chạy trên 2018–2022
bars_train = bars_15m[(bars_15m.index >= "2018-01-01") & (bars_15m.index < "2023-01-01")]
tr_2018_2022 = run_simple_trend(bars_train)

# 2. Chạy trên 2024–2026
bars_test = bars_15m[bars_15m.index >= "2024-01-01"]
tr_2024_2026 = run_simple_trend(bars_test)

def get_stats(df_tr, label=""):
    if df_tr.empty:
        return {}
    n = len(df_tr)
    net_pnl = df_tr["net_pnl"].sum()
    pts = df_tr["points"].sum()
    wins = df_tr[df_tr["net_pnl"] > 0]
    losses = df_tr[df_tr["net_pnl"] <= 0]
    wr = len(wins) / n * 100
    gw = wins["net_pnl"].sum() if len(wins) > 0 else 0
    gl = abs(losses["net_pnl"].sum()) if len(losses) > 0 else 0
    pf = gw / gl if gl > 0 else 999.0
    exp = net_pnl / n

    # Trim top 5
    trimmed = df_tr.sort_values("net_pnl", ascending=False).iloc[5:]
    w_trim = trimmed[trimmed["net_pnl"] > 0]["net_pnl"].sum()
    l_trim = abs(trimmed[trimmed["net_pnl"] <= 0]["net_pnl"].sum())
    pf_trim = w_trim / l_trim if l_trim > 0 else 999.0
    pnl_trim = trimmed["net_pnl"].sum()

    # Trend lớn bắt được (>= 30 pts)
    big_wins = len(df_tr[df_tr["points"] >= 30.0])

    return {
        "label": label, "trades": n, "net_pnl": net_pnl, "pts": pts,
        "wr": wr, "pf": pf, "exp": exp,
        "trim5_pnl": pnl_trim, "trim5_pf": pf_trim,
        "big_trends_caught": big_wins,
        "max_win_pts": df_tr["points"].max()
    }

st_simple_train = get_stats(tr_2018_2022, "Simple Trend (2018-2022)")
st_simple_test = get_stats(tr_2024_2026, "Simple Trend (2024-2026)")

# Load trades hiện tại
current_trades = pd.read_csv("results/all_trades_visualize.csv")
st_current = get_stats(current_trades, "Hệ thống Hiện tại (2024-2026)")

print("\n" + "="*80)
print("PHẦN 3: SO SÁNH TRỰC DIỆN: BASELINE TREND ĐƠN GIẢN vs HỆ THỐNG HIỆN TẠI")
print("="*80)
print(f"{'Tiêu chí đánh giá':<35} | {'Simple Trend (2018-2022)':<24} | {'Simple Trend (2024-2026)':<24} | {'Wyckoff+ML (2024-2026)':<24}")
print("-" * 115)

rows = [
    ("Số lệnh thực hiện", f"{st_simple_train['trades']} lệnh", f"{st_simple_test['trades']} lệnh", f"{st_current['trades']} lệnh"),
    ("Tỷ lệ thắng (Win Rate)", f"{st_simple_train['wr']:.1f}%", f"{st_simple_test['wr']:.1f}%", f"{st_current['wr']:.1f}%"),
    ("Tổng Net PnL (sau phí/trượt)", f"{st_simple_train['net_pnl']:>+12,.0f} đ", f"{st_simple_test['net_pnl']:>+12,.0f} đ", f"{st_current['net_pnl']:>+12,.0f} đ"),
    ("Tổng Điểm (Points)", f"{st_simple_train['pts']:>+12.1f} pts", f"{st_simple_test['pts']:>+12.1f} pts", f"{st_current['pts']:>+12.1f} pts"),
    ("Profit Factor (PF)", f"{st_simple_train['pf']:12.2f}", f"{st_simple_test['pf']:12.2f}", f"{st_current['pf']:12.2f}"),
    ("Kỳ vọng / Lệnh (Expectancy)", f"{st_simple_train['exp']:>+12,.0f} đ", f"{st_simple_test['exp']:>+12,.0f} đ", f"{st_current['exp']:>+12,.0f} đ"),
    ("Số trend >= 30 pts bắt được", f"{st_simple_train['big_trends_caught']:12d} lệnh", f"{st_simple_test['big_trends_caught']:12d} lệnh", f"{st_current['big_trends_caught']:12d} lệnh"),
    ("Lệnh thắng lớn nhất (pts)", f"{st_simple_train['max_win_pts']:>+12.1f} pts", f"{st_simple_test['max_win_pts']:>+12.1f} pts", f"{st_current['max_win_pts']:>+12.1f} pts"),
    ("Net PnL sau khi BỎ TOP 5", f"{st_simple_train['trim5_pnl']:>+12,.0f} đ", f"{st_simple_test['trim5_pnl']:>+12,.0f} đ", f"{st_current['trim5_pnl']:>+12,.0f} đ"),
    ("PF sau khi BỎ TOP 5", f"{st_simple_train['trim5_pf']:12.2f}", f"{st_simple_test['trim5_pf']:12.2f}", f"{st_current['trim5_pf']:12.2f}"),
]

for label, c1, c2, c3 in rows:
    print(f"{label:<35} | {c1:<24} | {c2:<24} | {c3:<24}")

print("\nHoàn tất toàn bộ phép thử.")

