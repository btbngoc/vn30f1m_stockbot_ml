import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import numpy as np
import pandas as pd

# Load 1-minute features
features = pd.read_parquet("trading_engine/data/VN30F1M_features.parquet")
features["datetime"] = pd.to_datetime(features["datetime"])
features = features.sort_values("datetime").reset_index(drop=True)

# 1. Resample sang 1-hour (60m) và Daily (1D)
bars_1h = features.set_index("datetime").resample("60min").agg({
    "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
}).dropna()
bars_1h = bars_1h[bars_1h["Volume"] > 0].copy()

# ATR 1h
bars_1h["tr"] = np.maximum(
    bars_1h["High"] - bars_1h["Low"],
    np.maximum(
        (bars_1h["High"] - bars_1h["Close"].shift(1)).abs(),
        (bars_1h["Low"] - bars_1h["Close"].shift(1)).abs()
    )
)
bars_1h["ATR"] = bars_1h["tr"].rolling(14).mean()

# Daily
bars_1d = features.set_index("datetime").resample("1D").agg({
    "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
}).dropna()
bars_1d = bars_1d[bars_1d["Volume"] > 0].copy()
bars_1d["tr"] = np.maximum(
    bars_1d["High"] - bars_1d["Low"],
    np.maximum(
        (bars_1d["High"] - bars_1d["Close"].shift(1)).abs(),
        (bars_1d["Low"] - bars_1d["Close"].shift(1)).abs()
    )
)
bars_1d["ATR"] = bars_1d["tr"].rolling(14).mean()

def run_donchian_engine(df_bars, n_bars=20, atr_mult=2.0, slip=0.3, fee=15000.0):
    df = df_bars.copy()
    df["High_N"] = df["High"].shift(1).rolling(n_bars).max()
    df["Low_N"] = df["Low"].shift(1).rolling(n_bars).min()

    trades = []
    pos = 0
    entry_p = 0.0
    entry_t = None
    stop_p = 0.0

    for t, r in df.iterrows():
        op, hi, lo, cl = r["Open"], r["High"], r["Low"], r["Close"]
        hi_n, lo_n = r["High_N"], r["Low_N"]
        atr = r["ATR"] if not np.isnan(r["ATR"]) and r["ATR"] > 0 else 5.0

        if pos != 0:
            raw_exit = None
            reason = ""
            if pos == 1:
                stop_p = max(stop_p, cl - atr_mult * atr)
                if lo <= stop_p:
                    raw_exit = stop_p
                    reason = "Trailing_SL"
                elif cl < lo_n:
                    raw_exit = cl
                    reason = "Reverse"
            else:
                stop_p = min(stop_p, cl + atr_mult * atr)
                if hi >= stop_p:
                    raw_exit = stop_p
                    reason = "Trailing_SL"
                elif cl > hi_n:
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

def calc_stats(df_tr, label=""):
    if df_tr is None or df_tr.empty:
        return {"label": label, "trades": 0, "net_pnl": 0, "pts": 0, "wr": 0, "pf": 0, "exp": 0, "trim5_pnl": 0, "trim5_pf": 0, "big_30": 0}
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
    trimmed = df_tr.sort_values("net_pnl", ascending=False).iloc[5:] if len(df_tr) > 5 else pd.DataFrame()
    if not trimmed.empty:
        w_trim = trimmed[trimmed["net_pnl"] > 0]["net_pnl"].sum()
        l_trim = abs(trimmed[trimmed["net_pnl"] <= 0]["net_pnl"].sum())
        pf_trim = w_trim / l_trim if l_trim > 0 else 999.0
        pnl_trim = trimmed["net_pnl"].sum()
    else:
        pf_trim, pnl_trim = 0.0, 0.0

    big_30 = len(df_tr[df_tr["points"] >= 30.0])
    return {
        "label": label, "trades": n, "net_pnl": net_pnl, "pts": pts, "wr": wr, "pf": pf, "exp": exp,
        "trim5_pnl": pnl_trim, "trim5_pf": pf_trim, "big_30": big_30
    }

print("="*85)
print("PHẦN 1: DONCHIAN KHUNG LỚN (1H VÀ DAILY) - ĐIỀU CHỈNH TẦN SUẤT 20-60 LỆNH/NĂM")
print("Chi phí thực tế: Trượt 0.3 điểm/đầu, Phí 30k round-trip")
print("="*85)

# Cấu hình thử nghiệm
# 1h: N = 10 (~2.5 ngày), N = 20 (~5 ngày), N = 40 (~10 ngày)
# Daily: N = 5 (1 tuần), N = 10 (2 tuần), N = 20 (1 tháng)
test_configs = [
    ("Donchian 1h (N=10, ATR=2.0)", bars_1h, 10, 2.0),
    ("Donchian 1h (N=20, ATR=2.0)", bars_1h, 20, 2.0),
    ("Donchian 1h (N=40, ATR=2.0)", bars_1h, 40, 2.0),
    ("Donchian 1D (N=5, ATR=2.0)", bars_1d, 5, 2.0),
    ("Donchian 1D (N=10, ATR=2.0)", bars_1d, 10, 2.0),
    ("Donchian 1D (N=20, ATR=2.0)", bars_1d, 20, 2.0),
]

print("\n--- A. KẾT QUẢ TRÊN 2018–2022 (5 NĂM ĐẦU - HUẤN LUYỆN / LỰA CHỌN) ---")
print(f"{'Cấu hình':<30} | {'Số lệnh':<12} | {'Lệnh/Năm':<10} | {'Win Rate':<10} | {'Net PnL':<15} | {'PF':<6} | {'Expectancy':<12} | {'PnL Bỏ Top-5':<15} | {'PF Bỏ Top-5':<6} | {'Trend >=30':<10}")
print("-" * 145)

results_18_22 = {}
for name, df_source, n_b, atr_m in test_configs:
    sub_df = df_source[(df_source.index >= "2018-01-01") & (df_source.index < "2023-01-01")]
    tr = run_donchian_engine(sub_df, n_bars=n_b, atr_mult=atr_m)
    st = calc_stats(tr, name)
    results_18_22[name] = st
    l_per_year = st['trades'] / 5.0
    print(f"{name:<30} | {st['trades']:8d}     | {l_per_year:7.1f}    | {st['wr']:6.1f}%    | {st['net_pnl']:>+12,.0f} đ | {st['pf']:4.2f} | {st['exp']:>+9,.0f} đ  | {st['trim5_pnl']:>+12,.0f} đ | {st['trim5_pf']:4.2f}  | {st['big_30']:6d}")

print("\n--- B. KẾT QUẢ TRÊN 2024–2026 (CHẠY ĐÚNG 1 LẦN VỚI THAM SỐ TỪ GIAI ĐOẠN ĐẦU) ---")
print(f"{'Cấu hình':<30} | {'Số lệnh':<12} | {'Lệnh/Năm':<10} | {'Win Rate':<10} | {'Net PnL':<15} | {'PF':<6} | {'Expectancy':<12} | {'PnL Bỏ Top-5':<15} | {'PF Bỏ Top-5':<6} | {'Trend >=30':<10}")
print("-" * 145)

results_24_26 = {}
for name, df_source, n_b, atr_m in test_configs:
    sub_df = df_source[df_source.index >= "2024-01-01"]
    tr = run_donchian_engine(sub_df, n_bars=n_b, atr_mult=atr_m)
    st = calc_stats(tr, name)
    results_24_26[name] = st
    l_per_year = st['trades'] / 2.83
    print(f"{name:<30} | {st['trades']:8d}     | {l_per_year:7.1f}    | {st['wr']:6.1f}%    | {st['net_pnl']:>+12,.0f} đ | {st['pf']:4.2f} | {st['exp']:>+9,.0f} đ  | {st['trim5_pnl']:>+12,.0f} đ | {st['trim5_pf']:4.2f}  | {st['big_30']:6d}")


# ==============================================================================
# PHẦN 2: TÁCH GIÁ TRỊ CỦA ML TRÊN CÙNG TÍN HIỆU (L1 THUẦN vs L1 + ML)
# ==============================================================================
print("\n" + "="*85)
print("PHẦN 2: TÁCH GIÁ TRỊ CỦA ML TRÊN CÙNG TÍN HIỆU GỐC (L1 THUẦN vs L1 + ML)")
print("Giai đoạn: Walk-Forward 2024–2026 | Chi phí: Trượt 0.3 điểm, Phí 30k | Thoát lệnh: Soft SL 15m")
print("="*85)

# 1. L1 Thuần (Tất cả tín hiệu của Wyckoff StrategySignal, không có ML filter)
from trading_engine.backtest.config import BacktestConfig

cfg_real = BacktestConfig(slippage_points=0.30, commission_per_contract=15000.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)

def round_tick(price): return round(price * 10.0) / 10.0

class BacktestRunner:
    def __init__(self, df, cfg):
        self.df = df
        self.cfg = cfg
    def run(self):
        trades = []
        pos = 0
        entry_p = entry_t = None
        trailing_sl = hard_sl = 0.0
        cooldown = 0
        for timestamp, row in self.df.iterrows():
            if cooldown > 0: cooldown -= 1
            signal = int(row.get("Signal", 0))
            op, close, high, low = row["Open"], row["Close"], row["High"], row["Low"]
            atr = row.get("ATR", 1.0)
            tr_atr = float(row.get("HTF_5m_ATR", atr * 2.0))

            if pos != 0:
                raw_exit = None
                reason = ""
                is_atc = (timestamp.hour == 14 and timestamp.minute == 45)
                if pos == 1:
                    if low <= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl >= entry_p and low <= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif low <= trailing_sl:
                        htf_rev = (row.get("HTF_15m_TrendDownOK", 0) == 1 or row.get("HTF_15m_TrendTransitionDown", 0) == 1)
                        if htf_rev: raw_exit, reason = trailing_sl, "SL"
                    elif signal == -1: raw_exit, reason = close, "Reversal"
                else:
                    if high >= hard_sl: raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_p and high >= trailing_sl: raw_exit, reason = trailing_sl, "SL"
                    elif high >= trailing_sl:
                        htf_rev = (row.get("HTF_15m_TrendOK", 0) == 1 or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0))
                        if htf_rev: raw_exit, reason = trailing_sl, "SL"
                    elif signal == 1: raw_exit, reason = close, "Reversal"

                if raw_exit is None:
                    if pos == 1: trailing_sl = max(trailing_sl, round_tick(close - self.cfg.trailing_stop_atr * tr_atr))
                    else: trailing_sl = min(trailing_sl, round_tick(close + self.cfg.trailing_stop_atr * tr_atr))

                if raw_exit is not None:
                    actual_base = raw_exit
                    if reason in ("Hard_SL", "SL"):
                        if pos == 1 and op < raw_exit: actual_base = op
                        elif pos == -1 and op > raw_exit: actual_base = op
                    s = 0.0 if is_atc else self.cfg.slippage_points
                    exit_p = round_tick(actual_base - pos * s)
                    pts = (exit_p - entry_p) * pos
                    net_pnl = pts * 100000.0 - 2 * self.cfg.commission_per_contract
                    trades.append({
                        "entry_time": entry_t, "exit_time": timestamp, "type": "LONG" if pos == 1 else "SHORT",
                        "entry_price": entry_p, "exit_price": exit_p, "points": pts, "net_pnl": net_pnl, "reason": reason
                    })
                    pos = 0
                    cooldown = 15
                    continue

            if pos == 0 and signal and cooldown == 0 and (timestamp.hour < 14 or (timestamp.hour == 14 and timestamp.minute <= 25)):
                pos = signal
                entry_t = timestamp
                entry_p = round_tick(close + pos * self.cfg.slippage_points)
                setup = str(row.get("EntrySetup", ""))
                trade_atr = float(row.get("HTF_15m_ATR", tr_atr)) if ("SPRING" in setup or "UTAD" in setup) else tr_atr
                hard_sl = round_tick(entry_p - pos * 2.5 * trade_atr)
                trailing_sl = round_tick(entry_p - pos * 1.0 * trade_atr)

        return pd.DataFrame(trades)

# Chạy L1 Thuần
l1_folds = []
FOLDS = [
    ("Fold 1 (2024)", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
    ("Fold 2 (2025)", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01")),
    ("Fold 3 (2026)", pd.Timestamp("2026-01-01"), None),
]

for name, start_t, end_t in FOLDS:
    sub = features[features["datetime"] >= start_t].copy()
    if end_t is not None: sub = sub[sub["datetime"] < end_t].copy()
    sub["Signal"] = sub["StrategySignal"].astype(int)
    tr = BacktestRunner(sub.set_index("datetime"), cfg_real).run()
    l1_folds.append(tr)

df_l1_pure = pd.concat(l1_folds, ignore_index=True)
st_l1_pure = calc_stats(df_l1_pure, "L1 Thuần Quy Tắc (Không ML)")

# Lấy lại kết quả L1 + ML (Seed 42 và 10-seed median)
df_l1_ml = pd.read_csv("results/all_trades_visualize.csv")
st_l1_ml = calc_stats(df_l1_ml, "L1 + ML Filter (Seed 42)")

print(f"{'Tiêu chí so sánh':<32} | {'Layer 1 Thuần (Không ML)':<25} | {'Layer 1 + ML (Baseline)':<25} | {'Chênh lệch do ML đóng góp':<30}")
print("-" * 120)

comp_rows = [
    ("Tổng số lệnh OOS (2024-2026)", f"{st_l1_pure['trades']} lệnh (~211 lệnh/năm)", f"{st_l1_ml['trades']} lệnh (~57 lệnh/năm)", f"Giảm {st_l1_pure['trades'] - st_l1_ml['trades']} lệnh (-73.2%)"),
    ("Tỷ lệ thắng (Win Rate)", f"{st_l1_pure['wr']:.1f}%", f"{st_l1_ml['wr']:.1f}%", f"+{st_l1_ml['wr'] - st_l1_pure['wr']:.1f}%"),
    ("Tổng Net PnL (sau phí & trượt)", f"{st_l1_pure['net_pnl']:>+12,.0f} đ", f"{st_l1_ml['net_pnl']:>+12,.0f} đ", f"+{st_l1_ml['net_pnl'] - st_l1_pure['net_pnl']:>+12,.0f} đ"),
    ("Profit Factor (PF)", f"{st_l1_pure['pf']:12.2f}", f"{st_l1_ml['pf']:12.2f}", f"+{st_l1_ml['pf'] - st_l1_pure['pf']:4.2f}"),
    ("Kỳ vọng / Lệnh (Expectancy)", f"{st_l1_pure['exp']:>+12,.0f} đ", f"{st_l1_ml['exp']:>+12,.0f} đ", f"+{st_l1_ml['exp'] - st_l1_pure['exp']:>+12,.0f} đ/lệnh"),
    ("Số trend >= 30 pts bắt được", f"{st_l1_pure['big_30']:12d} lệnh", f"{st_l1_ml['big_30']:12d} lệnh", f"{st_l1_ml['big_30'] - st_l1_pure['big_30']:+2d} lệnh (ML bỏ bớt trend)"),
    ("Net PnL sau khi BỎ TOP 5", f"{st_l1_pure['trim5_pnl']:>+12,.0f} đ", f"{st_l1_ml['trim5_pnl']:>+12,.0f} đ", f"+{st_l1_ml['trim5_pnl'] - st_l1_pure['trim5_pnl']:>+12,.0f} đ"),
    ("PF sau khi BỎ TOP 5", f"{st_l1_pure['trim5_pf']:12.2f}", f"{st_l1_ml['trim5_pf']:12.2f}", f"+{st_l1_ml['trim5_pf'] - st_l1_pure['trim5_pf']:4.2f}"),
]

for label, c1, c2, diff in comp_rows:
    print(f"{label:<32} | {c1:<25} | {c2:<25} | {diff:<30}")

print("\nHoàn tất toàn bộ tính toán.")

