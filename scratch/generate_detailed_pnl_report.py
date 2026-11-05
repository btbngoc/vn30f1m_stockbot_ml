import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import pandas as pd
import numpy as np

df = pd.read_csv("results/all_trades_visualize.csv")
df["entry_time"] = pd.to_datetime(df["entry_time"])
df["exit_time"] = pd.to_datetime(df["exit_time"])
df["year"] = df["entry_time"].dt.year

def analyze_subset(sub, name=""):
    n = len(sub)
    if n == 0:
        return {}
    net_pnl = sub["net_pnl"].sum()
    pts = sub["points"].sum()
    wins = sub[sub["net_pnl"] > 0]
    losses = sub[sub["net_pnl"] <= 0]
    n_win = len(wins)
    n_loss = len(losses)
    wr = n_win / n * 100
    gross_win = wins["net_pnl"].sum() if n_win > 0 else 0.0
    gross_loss = abs(losses["net_pnl"].sum()) if n_loss > 0 else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else 999.0
    avg_win = gross_win / n_win if n_win > 0 else 0.0
    avg_loss = gross_loss / n_loss if n_loss > 0 else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else 0.0
    exp_vnd = net_pnl / n
    exp_pts = pts / n

    # Drawdown
    equity = sub["net_pnl"].cumsum()
    peak = equity.cummax()
    dd = peak - equity
    max_dd = dd.max()

    return {
        "name": name,
        "trades": n,
        "wins": n_win,
        "losses": n_loss,
        "win_rate": wr,
        "net_pnl": net_pnl,
        "net_pts": pts,
        "gross_win": gross_win,
        "gross_loss": gross_loss,
        "pf": pf,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff": payoff,
        "exp_vnd": exp_vnd,
        "exp_pts": exp_pts,
        "max_dd": max_dd,
        "max_win_trade": sub["net_pnl"].max(),
        "max_loss_trade": sub["net_pnl"].min(),
        "max_win_pts": sub["points"].max(),
        "max_loss_pts": sub["points"].min()
    }

# 1. Tổng thể
total_stats = analyze_subset(df, "TỔNG THỂ HỆ THỐNG")

# 2. Theo năm
by_year = [analyze_subset(df[df["year"] == y], f"Năm {y}") for y in sorted(df["year"].unique())]

# 3. Theo chiều Long / Short
by_type = [analyze_subset(df[df["type"] == t], f"Vị thế {t}") for t in ["LONG", "SHORT"]]

# 4. Theo qua đêm
by_on = [
    analyze_subset(df[df["is_overnight"] == False], "Trong ngày (Intraday)"),
    analyze_subset(df[df["is_overnight"] == True], "Qua đêm (Overnight)")
]

# 5. Theo lý do thoát lệnh
reasons = df["reason"].unique()
by_reason = [analyze_subset(df[df["reason"] == r], f"Thoát: {r}") for r in reasons]

# In báo cáo
print("="*80)
print("BÁO CÁO TỔNG HỢP TOÀN DIỆN KẾT QUẢ NET PROFIT VÀ PnL (WALK-FORWARD 2024-2026)")
print("="*80)
print(f"Tổng số lệnh giao dịch   : {total_stats['trades']} lệnh")
print(f"Tổng Net Profit (PnL)     : {total_stats['net_pnl']:>+14,.0f} VND ({total_stats['net_pts']:>+6.1f} điểm)")
print(f"Tổng Lãi gộp (Gross Win)  : {total_stats['gross_win']:>+14,.0f} VND")
print(f"Tổng Lỗ gộp (Gross Loss)  : {total_stats['gross_loss']:>+14,.0f} VND")
print(f"Profit Factor (PF)        : {total_stats['pf']:14.2f}")
print(f"Tỷ lệ Thắng (Win Rate)    : {total_stats['win_rate']:13.1f}% ({total_stats['wins']} thắng / {total_stats['losses']} thua)")
print(f"Lãi trung bình / lệnh thắng: {total_stats['avg_win']:>+13,.0f} VND")
print(f"Lỗ trung bình / lệnh thua  : -{total_stats['avg_loss']:>12,.0f} VND")
print(f"Tỷ lệ Lãi/Lỗ (Payoff Ratio): {total_stats['payoff']:14.2f}")
print(f"Kỳ vọng bình quân / lệnh  : {total_stats['exp_vnd']:>+14,.0f} VND/lệnh ({total_stats['exp_pts']:>+5.2f} điểm)")
print(f"Max Drawdown (Sụt giảm tối đa): {total_stats['max_dd']:>11,.0f} VND")
print(f"Lệnh thắng lớn nhất       : {total_stats['max_win_trade']:>+14,.0f} VND ({total_stats['max_win_pts']:>+5.1f} điểm)")
print(f"Lệnh thua lớn nhất        : {total_stats['max_loss_trade']:>+14,.0f} VND ({total_stats['max_loss_pts']:>+5.1f} điểm)")

print("\n" + "-"*80)
print("1. BÓC TÁCH HIỆU SUẤT THEO NĂM (WALK-FORWARD FOLDS)")
print("-"*80)
for s in by_year:
    print(f"{s['name']:<10} | Lệnh: {s['trades']:2d} | WR: {s['win_rate']:4.1f}% | Net PnL: {s['net_pnl']:>+11,.0f} VND ({s['net_pts']:>+5.1f} pts) | PF: {s['pf']:4.2f} | MaxDD: {s['max_dd']:>9,.0f} VND")

print("\n" + "-"*80)
print("2. BÓC TÁCH HIỆU SUẤT THEO VỊ THẾ (LONG vs SHORT)")
print("-"*80)
for s in by_type:
    print(f"{s['name']:<12} | Lệnh: {s['trades']:2d} | WR: {s['win_rate']:4.1f}% | Net PnL: {s['net_pnl']:>+11,.0f} VND ({s['net_pts']:>+5.1f} pts) | PF: {s['pf']:4.2f} | Exp: {s['exp_vnd']:>+8,.0f} VND")

print("\n" + "-"*80)
print("3. BÓC TÁCH HIỆU SUẤT GIỮ LỆNH (INTRADAY vs OVERNIGHT)")
print("-"*80)
for s in by_on:
    print(f"{s['name']:<22} | Lệnh: {s['trades']:3d} | WR: {s['win_rate']:4.1f}% | Net PnL: {s['net_pnl']:>+11,.0f} VND ({s['net_pts']:>+5.1f} pts) | PF: {s['pf']:4.2f}")

print("\n" + "-"*80)
print("4. BÓC TÁCH THEO LÝ DO THOÁT LỆNH (EXIT REASONS)")
print("-"*80)
for s in by_reason:
    print(f"{s['name']:<18} | Lệnh: {s['trades']:3d} | WR: {s['win_rate']:4.1f}% | Net PnL: {s['net_pnl']:>+11,.0f} VND | Lệnh Max: {s['max_loss_trade']:>+10,.0f} VND")

# Chuỗi thắng / thua liên tiếp
consec_wins = 0
consec_losses = 0
max_cw = 0
max_cl = 0
cur_cw = 0
cur_cl = 0
for r in df.itertuples():
    if r.net_pnl > 0:
        cur_cw += 1
        cur_cl = 0
        if cur_cw > max_cw: max_cw = cur_cw
    else:
        cur_cl += 1
        cur_cw = 0
        if cur_cl > max_cl: max_cl = cur_cl

print(f"\nChuỗi thắng liên tiếp lớn nhất: {max_cw} lệnh")
print(f"Chuỗi thua liên tiếp lớn nhất : {max_cl} lệnh")

