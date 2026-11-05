import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import pandas as pd
import numpy as np
from trading_engine.data.vci_api import fetch_vci_1m_one_shot

# Lấy 10,000 nến 1-phút gần nhất của VN30 và VN30F1M
print("Fetching 10,000 bars of VN30 and VN30F1M...")
vn30 = fetch_vci_1m_one_shot("VN30", count_back=10000)
f1m = fetch_vci_1m_one_shot("VN30F1M", count_back=10000)

print(f"VN30 bars: {len(vn30)} ({vn30['time'].min()} to {vn30['time'].max()})")
print(f"F1M  bars: {len(f1m)} ({f1m['time'].min()} to {f1m['time'].max()})")

# Merge
merged = pd.merge(f1m[["time", "close"]], vn30[["time", "close"]], on="time", suffixes=("_f1m", "_vn30"))
merged["basis"] = merged["close_f1m"] - merged["close_vn30"]

print("\n--- PHÂN BỐ BASIS (VN30F1M - VN30) TRÊN 10,000 NẾN 1-PHÚT GẦN NHẤT ---")
print(f"Số nến khớp: {len(merged)}")
print(f"Mean Basis  : {merged['basis'].mean():>+6.2f} pts")
print(f"Median Basis: {merged['basis'].median():>+6.2f} pts")
print(f"Std Dev     : {merged['basis'].std():>6.2f} pts")
print(f"Min Basis   : {merged['basis'].min():>+6.2f} pts (Chiết khấu sâu nhất)")
print(f"Max Basis   : {merged['basis'].max():>+6.2f} pts (Thặng dư cao nhất)")
print(f"Phân vị 5%  : {merged['basis'].quantile(0.05):>+6.2f} pts")
print(f"Phân vị 95% : {merged['basis'].quantile(0.95):>+6.2f} pts")

# Kiểm tra tốc độ hồi quy (Mean Reversion) sau khi Basis lệch cực đoan (< 5% hoặc > 95%)
low_basis = merged[merged["basis"] <= merged["basis"].quantile(0.05)].index
reversion_moves = []
for idx in low_basis:
    if idx + 30 < len(merged):
        move = merged.loc[idx + 30, "basis"] - merged.loc[idx, "basis"]
        reversion_moves.append(move)

if len(reversion_moves) > 0:
    print(f"\nSau 30 phút kể từ khi Basis chạm đáy 5% cực đoan:")
    print(f"  • Độ co hẹp Basis trung bình: {np.mean(reversion_moves):>+6.2f} pts (Basis hồi về)")
    print(f"  • Tỷ lệ Basis hồi phục      : {np.mean(np.array(reversion_moves) > 0)*100:.1f}%")

