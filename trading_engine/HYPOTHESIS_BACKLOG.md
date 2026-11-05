# 📋 Hypothesis Backlog (Quarantined)

> **Nguyên tắc cốt lõi (Governance Principle):**
> Toàn bộ tập dữ liệu lịch sử 2018–2026 đã bị **snooped 100% (exhausted)** do quá trình nghiên cứu, thử nghiệm nhiều lần.
> **TUYỆT ĐỐI KHÔNG** lấy bất kỳ giả thuyết nào dưới đây đem thử nghiệm, tối ưu tham số hay "cherry-pick" trên dữ liệu 2018–2026.
> Mọi giả thuyết tại đây được **cách ly (Quarantined)** và chỉ được phép mang ra kiểm chứng trên tập dữ liệu Out-of-Sample tương lai (tích lũy từ 20/10/2026 trở đi qua Paper Trade).

---

### H-01: Đóng Vị Thế Trước Phiên ATC (Intra-Day Flat by 14:25)
- **Bối cảnh quan sát:**
  - 18.8% số lệnh bị trượt giá do Gap rơi vào phiên ATC (14:30 – 14:45).
  - Điển hình ngày 20/10/2026: Lệnh Short bị ép vào phiên định kỳ ATC nhảy gap từ 1845.7 lên 1850.0, xuyên thủng Hard SL 1847.9 thêm 2.1 điểm trượt giá ngoài ý muốn.
  - Quy chế DNSE xác nhận hệ thống broker KHÔNG kích hoạt lệnh điều kiện Stop Loss trong phiên ATC (14:30 – 14:45).
- **Nội dung quy tắc:**
  - Cờ `flat_before_atc` (mặc định `False`) trong `BacktestConfig`.
  - Khi bật: nếu tài khoản có vị thế mở lúc 14:25:00, đóng vị thế tại giá `Open` nến 14:25 ± slippage.
  - Không mở vị thế mới từ 14:25 trở đi. Chỉ dùng đúng mốc 14:25, tuyệt đối không quét hay tối ưu mốc khác.
- **Trạng thái:** `ĐÃ ĐO, MÔ TẢ, CHƯA XÁC NHẬN` (Measured, Descriptive, Not Validated — Awaiting Forward Paper Trade).
- **Kết quả đo lường đối chứng (2024–2026, 591 lệnh gốc vs Gap-Aware vs Flat_before_ATC):**

| Slippage | Giai đoạn | N lệnh | Base Exp (pts) | Base PF | Gap Exp (pts) | Gap PF | Gap MaxLoss | Flat N | Flat Exp (pts) | Flat PF | Lệnh đóng sớm 14:25 | PnL nhóm đóng sớm | Flat MaxLoss | Flat P99 Loss | Chênh lệch ghép cặp vs Gap-Aware (95% CI) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **0.1 pt** | 2024 | 193 | +0.27 | 1.21 | +0.08 | 1.05 | 10.20 | 186 | -0.34 | 0.72 | 34 | -0.17M (-0.05 pt) | 8.79 | 6.76 | -0.40 pt [-0.97, +0.11] |
| **0.1 pt** | 2025 | 202 | -0.11 | 0.96 | -0.69 | 0.80 | 80.10 | 198 | -0.91 | 0.67 | 47 | -0.45M (-0.10 pt) | 28.19 | 21.23 | -0.20 pt [-1.26, +1.02] |
| **0.1 pt** | 2026 | 197 | +0.96 | 1.35 | +0.45 | 1.15 | 30.70 | 195 | +0.33 | 1.14 | 50 | +22.98M (+4.60 pt) | 14.88 | 12.46 | -0.13 pt [-1.28, +0.92] |
| **0.1 pt** | **POOLED** | **591** | **+0.38** | **1.16** | **-0.05** | **0.98** | **80.10** | **579** | **-0.31** | **0.85** | **131** | **+22.36M (+1.71 pt)** | **28.19** | **14.93** | **-0.25 pt [-0.80, +0.33]** |
| **0.3 pt** | 2024 | 195 | -0.14 | 0.91 | -0.32 | 0.81 | 10.60 | 187 | -0.76 | 0.48 | 34 | -0.79M (-0.23 pt) | 8.99 | 7.20 | -0.41 pt [-0.96, +0.10] |
| **0.3 pt** | 2025 | 201 | -0.64 | 0.80 | -1.20 | 0.68 | 80.50 | 197 | -1.26 | 0.57 | 46 | -1.94M (-0.42 pt) | 28.39 | 21.49 | -0.03 pt [-1.07, +1.19] |
| **0.3 pt** | 2026 | 196 | +0.61 | 1.21 | +0.10 | 1.03 | 31.10 | 194 | -0.03 | 0.99 | 50 | +21.04M (+4.21 pt) | 15.08 | 12.66 | -0.12 pt [-1.27, +0.92] |
| **0.3 pt** | **POOLED** | **591** | **-0.06** | **0.98** | **-0.47** | **0.84** | **80.50** | **578** | **-0.68** | **0.71** | **130** | **+18.31M (+1.41 pt)** | **28.39** | **15.23** | **-0.19 pt [-0.72, +0.37]** |
| **0.5 pt** | 2024 | 195 | -0.62 | 0.66 | -0.77 | 0.61 | 11.00 | 187 | -1.19 | 0.32 | 35 | -2.21M (-0.63 pt) | 9.19 | 7.52 | -0.37 pt [-0.91, +0.11] |
| **0.5 pt** | 2025 | 200 | -1.08 | 0.69 | -1.63 | 0.59 | 80.90 | 196 | -1.52 | 0.51 | 47 | -2.70M (-0.57 pt) | 28.59 | 21.75 | +0.14 pt [-0.93, +1.38] |
| **0.5 pt** | 2026 | 196 | +0.34 | 1.11 | -0.18 | 0.95 | 31.50 | 194 | -0.36 | 0.87 | 51 | +18.98M (+3.72 pt) | 15.28 | 12.86 | -0.18 pt [-1.31, +0.89] |
| **0.5 pt** | **POOLED** | **590** | **-0.45** | **0.84** | **-0.86** | **0.73** | **80.90** | **577** | **-1.03** | **0.60** | **133** | **+14.07M (+1.06 pt)** | **28.59** | **15.53** | **-0.14 pt [-0.67, +0.43]** |

- **Nhận định định lượng chuyên sâu:**
  1. **Triệt tiêu hoàn toàn rủi ro đuôi cực đoan (Tail Risk Protection):**
     - Mức lỗ tối đa (Max Loss) dưới Gap-Aware giảm từ **80.10 điểm** (cú sập flash crash ATC ngày 25/12/2025) xuống còn **28.19 điểm** (đúng bằng Hard SL danh nghĩa do biến động ATR trong phiên).
     - Mức lỗ phân vị 99 (P99 Loss) được thu hẹp từ **19.74 điểm xuống 14.93 điểm** (ở trượt giá 0.1 pt).
  2. **Đánh đổi kỳ vọng (Expectancy Trade-off):**
     - Đóng vị thế sớm lúc 14:25 giúp bảo vệ tài khoản khỏi các cú sập ATC, nhưng lại tước đoạt phần lớn lợi nhuận chạy tiếp (overnight continuation) của các lệnh đang có lãi qua đêm.
     - Expectancy gộp giảm từ $-0.05$ pt xuống $-0.31$ pt (ở 0.1 pt slip) và $-0.47$ pt xuống $-0.68$ pt (ở 0.3 pt slip).
  3. **Kiểm định thống kê ghép cặp (Paired Difference Block Bootstrap theo ngày, 95% CI):**
     - Khoảng tin cậy 95% của chênh lệch kỳ vọng $\Delta$ bao trùm số 0 ở tất cả các mức trượt giá (ví dụ 0.1 pt slip: $[-0.80, +0.33]$ pt; 0.3 pt slip: $[-0.72, +0.37]$ pt).
     - Điều này chứng minh: trên tập dữ liệu lịch sử, **không có bằng chứng thống kê** cho thấy đóng vị thế lúc 14:25 làm tăng expectancy bình quân. Nó hoạt động thuần túy như một khoản **bảo hiểm đuôi rủi ro** (giảm variance đuôi, trả giá bằng lợi nhuận trung bình).
  4. **Kế hoạch kiểm chứng tương lai:**
     - Giữ nguyên cấu hình đóng băng cho hệ thống chính (`flat_before_atc=False`).
     - Theo dõi song song qua tệp nhật ký `trading_engine/data/paper_trade_journal_h01.csv` từ ngày 20/10/2026.
     - Tuyệt đối không chỉnh sửa tham số hay tối ưu mốc giờ trên dữ liệu 2018–2026.

---

### H-02: Thu Hẹp Khoảng Cách Dừng Lỗ Khẩn Cấp (Hard SL Multiplier 1.5x thay vì 2.5x)
- **Bối cảnh quan sát:**
  - Mức Hard SL hiện tại là $2.5 \times \text{HTF\_5m\_ATR}$ (~6.7 – 15.0 điểm tùy biến động).
  - Thống kê chi tiết 45 lệnh OOS năm 2026: Có đúng **10 lệnh dính Hard_SL gây ra 74.37% tổng số tiền lỗ** (-9,991,071 VND trên tổng lỗ -13,433,571 VND). Chênh lệch điểm thua trung bình mỗi lệnh Hard_SL lên tới **-9.7 điểm** (lớn nhất là cú gap ATO -30.4 điểm ngày 10/03/2026).
  - Đuôi lỗ quá sâu của nhóm Hard_SL phá hủy toàn bộ expectancy của hệ thống.
- **Nội dung giả thuyết:**
  - Giảm hệ số `hard_sl_atr_mult` từ 2.5 xuống 1.5 – 1.8 (~4.0 – 5.5 điểm) hoặc cố định mức max loss danh nghĩa để cắt đứt đuôi rủi ro cực đoan.
- **Kỷ luật Quants & Quản trị dữ liệu (Data Governance):**
  - **TUYỆT ĐỐI KHÔNG** chỉnh sửa tham số `hard_sl_atr_mult` rồi chạy test lại trên cùng tập dữ liệu 2026 (tránh data snooping / curve-fitting làm hỏng tập OOS 2026).
  - Giả thuyết được cách ly và chỉ được phép kiểm chứng forward trên tập dữ liệu mới tích lũy qua Paper Trade từ 20/10/2026 trở đi.
- **Trạng thái:** `QUARANTINED` (Cách ly, không backtest hồi tố trên 2018–2026).

---

### H-07: Bộ Lọc Giữ Qua Đêm Khi Có Đệm Lợi Nhuận & Triệt Tiêu Ma Sát Intraday (Overnight Continuation vs. Intraday Friction)
- **Bối cảnh quan sát:**
  - Bóc tách phân rã 45 lệnh OOS năm 2026:
    - **Nhóm Intraday (32 lệnh, 71.1%):** Lỗ lũy kế **-5,172,143 VND**, Win rate 50.0%, Profit Factor chỉ đạt **0.43**. Ma sát thuế phí 30,000 VND/round-trip cùng biên co giằng co trong ngày bào mòn toàn bộ vốn.
    - **Nhóm Overnight (13 lệnh, 28.9%):** Lãi lũy kế **+4,593,929 VND**, Win rate **61.5%**, Profit Factor đạt **2.04**. Lệnh giữ qua đêm gánh toàn bộ hiệu suất của hệ thống.
    - Tuy nhiên, lệnh qua đêm lại tiềm ẩn rủi ro nhảy gap ATO sáng hôm sau (điển hình ngày 10/03/2026 ATO nhảy vọt +52.2 điểm so với ATC hôm trước khiến lệnh Short bị lỗ thực tế -30.4 điểm).
- **Nội dung quy tắc giả thuyết:**
  - 1. Chỉ cho phép vị thế được giữ qua đêm nếu trước 14:25 tài khoản đang có **đệm lợi nhuận thả nổi (unrealized profit) tối thiểu $\ge +2.5$ đến $+3.0$ điểm**.
  - 2. Nếu vị thế chưa đạt đệm lãi bảo vệ (lãi mỏng $< 1.0$ điểm hoặc đang âm nhẹ), hệ thống tự động đóng vị thế trước 14:25 để loại trừ rủi ro nhảy gap ATO sáng hôm sau và hạn chế ma sát intraday.
- **Kỷ luật kiểm chứng:**
  - Giữ nguyên cấu hình đóng băng của hệ thống hiện tại.
  - Tuyệt đối không tối ưu hóa ngưỡng đệm lãi trên dữ liệu lịch sử 2018–2026.
  - Chỉ theo dõi và kiểm chứng trên tập dữ liệu tương lai (Forward Paper Trade từ 20/10/2026 trở đi).
- **Trạng thái:** `QUARANTINED` (Cách ly, chờ kiểm chứng Paper Trade).

---

### H-03: Nhận Diện Đảo Chiều Khung 15m Nội Thanh (Intra-Bar 15m Reversal Detection)
- **Bối cảnh quan sát:**
  - Các cờ `HTF_15m_TrendDownOK` và `HTF_15m_TrendOK` dùng `.shift(1)` theo bucket 15 phút.
  - Điều này tránh được rò rỉ dữ liệu tương lai (look-ahead) nhưng gây ra độ trễ pha lớn (lag 15 đến 29 phút). Khi thị trường đảo chiều giật mạnh, Soft Stop Loss hoàn toàn bị tê liệt trong 15 phút đó, khiến 34.8% lệnh thua bị trôi thẳng về Hard SL.
- **Nội dung giả thuyết:**
  - Cho phép Soft SL đọc EMA nhanh/chậm nội thanh hoặc đường giá 1m xuyên qua mức trung bình mà không cần đợi nến 15m đóng cửa hoàn chỉnh.
- **Trạng thái:** `QUARANTINED` (Chờ dữ liệu forward OOS).

---

### H-06: Tối Ưu Hóa Chi Phí Thực Thi & Mở Rộng Biên Lợi Nhuận Mỗi Lệnh (Execution Friction & Edge Margin Expansion)
- **Bối cảnh quan sát:**
  - Phân rã 591 lệnh (2024–2026) cho thấy:
    - Nhóm **Intraday (469 lệnh, 79.4%)** bị bào mòn nặng nề bởi phí và trượt giá: lỗ lũy kế $-65.3$M đến $-99.2$M VND (Expectancy $-1.39$ đến $-2.15$ pt/lệnh, Win Rate ~40%, PF 0.35 - 0.50).
    - Nhóm **Overnight (122 lệnh, 20.6%)** gánh toàn bộ hệ thống: lãi lũy kế $+48.2$M đến $+62.1$M VND (Expectancy $+3.77$ đến $+5.09$ pt/lệnh, Win Rate ~68%, PF 2.38 - 3.12).
  - Tác động hủy diệt của ma sát giao dịch (Friction Sensitivity):
    - Trượt giá 0.1 pt/chiều: Expectancy gộp $+0.38$ pt (+22.2M VND).
    - Trượt giá 0.3 pt/chiều: Expectancy gộp $-0.06$ pt (-3.3M VND).
    - Trượt giá 0.5 pt/chiều: Expectancy gộp $-0.45$ pt (-26.5M VND).
    - Chỉ cần tăng 0.2 pt trượt giá/chiều (0.4 pt round-trip), toàn bộ alpha tích lũy qua 3 năm bị xóa sổ hoàn toàn!
  - Tổng ma sát cố định: Thuế phí quản lý vị thế 30,000 VND/round-trip (~0.30 pt) + Trượt giá round-trip 0.60 pt = **0.90 pt/lệnh**. Trong khi biên lợi nhuận thô (Gross Edge) của Layer 1 chỉ khoảng $+0.7$ đến $+0.8$ pt/lệnh. Ma sát nuốt trọn 100% lợi thế của bot.
- **Định hướng chiến lược trọng tâm (Chi phí & Biên thay vì thêm bộ lọc):**
  1. **Dừng hoàn toàn việc thử nghiệm biến thể luật trên 2018–2026:** Tập dữ liệu lịch sử đã cạn kiệt, mọi can thiệp bộ lọc hay tinh chỉnh tham số chỉ gây overfit.
  2. **Tối ưu định tuyến lệnh AmiX / Broker API:**
     - Sử dụng lệnh LO treo chủ động tại mép nến thay vì lệnh thị trường MTL đuổi giá để ép trượt giá thực tế về 0.0 hoặc ăn spread (maker rebate).
  3. **Tối ưu biểu phí CTCK:**
     - Sử dụng chính sách miễn phí giao dịch cơ sở/phái sinh (như gói 0 đồng của DNSE/Entrade X) hoặc thương lượng phí dịch vụ cố định theo tháng để hạ chi phí round-trip từ 30k xuống mức tối thiểu (chỉ còn phí Sở VSDC ~5.4k/chiều).
  4. **Ưu tiên các setup có biên dao động lớn (Edge Expansion):**
     - Tập trung vào các setup có tỷ lệ RR tiềm năng cao (như SOS Breakout hoặc Spring có xác nhận), hạn chế các setup có biên co hẹp trong ngày để đảm bảo tỷ số $E[\text{Gross Win}] / \text{Friction} > 3.0$.
- **Trạng thái:** `QUARANTINED` (Định hướng chiến lược chủ đạo cho giai đoạn Live Bridge, không tối ưu luật trên 2018–2026).

---

### H-04: Setup Ứng Viên Shadow: PULLBACK_15M_TREND
- **Mô tả & Quy tắc vào/thoát:**
  - **Logic vào lệnh:** Khi khung lớn xác nhận xu hướng (`HTF_15m_TrendOK == 1` cho Long hoặc `HTF_15m_TrendDownOK == 1` cho Short), vào lệnh khi nến 5m hoàn thành đóng lại theo chiều xu hướng sau khi chạm EMA20 5m:
    - Long: `Low_5m <= EMA20_5m` & `Close_5m > EMA20_5m` & `Close_5m > Open_5m`.
    - Short: `High_5m >= EMA20_5m` & `Close_5m < EMA20_5m` & `Close_5m < Open_5m`.
  - **Logic thoát lệnh:** Dùng đúng cơ chế hiện có của Layer 1: Soft SL (1.0 * ATR 5m kèm cổng đảo chiều HTF 15m), Emergency Hard SL (2.5 * ATR 5m), và Trailing Stop (1.5 * ATR 5m). Thoát theo cơ chế **Gap-Aware** (khớp tại Open nếu nến mở cửa nhảy vọt qua stop).
  - **Kỷ luật nghiên cứu:** Tham số cố định tuyệt đối, không quét tối ưu tham số (no parameter search/tuning), chạy một lần duy nhất trên toàn bộ dữ liệu 2018–2026.
- **Kết quả kiểm định một lần trên 2018–2026 (529,784 thanh 1 phút):**
  - **Số lệnh:** 2,906 lệnh (ở slip 0.3) / 2,951 lệnh (ở slip 0.5).
  - **Biên gộp (Gross Margin):** **+0.409 điểm/lệnh** (trước chi phí).
  - **Net Expectancy (sau trượt giá & phí 30k round-trip):**
    - Trượt giá 0.3 pt: **-0.464 điểm/lệnh** (Lỗ lũy kế: $-134.78$M VND, PF: 0.82, Win Rate: 42.0%).
    - Trượt giá 0.5 pt: **-0.871 điểm/lệnh** (Lỗ lũy kế: $-257.13$M VND, PF: 0.70, Win Rate: 37.2%).
  - **Rủi ro đuôi (Gap-Aware Tail Risk):** Max Loss: **45.70 điểm**, P99 Loss: 17.19 điểm.
  - **Block Bootstrap theo ngày 95% CI (5-day blocks, 2,000 resamples):**
    - Trượt giá 0.3 pt: **[-0.71, -0.20] điểm** (Toàn bộ 95% CI nằm sâu dưới 0).
    - Trượt giá 0.5 pt: **[-1.11, -0.61] điểm** (Toàn bộ 95% CI nằm sâu dưới 0).
  - **So sánh Baseline ngẫu nhiên (Matched Random Null - cùng phân phối giờ và hướng, 100 MC draws):**
    - Trượt giá 0.3 pt: Random Exp: **-0.520 điểm**, Alpha vs Random: **+0.056 điểm**, $p = 0.300$.
    - Trượt giá 0.5 pt: Random Exp: **-0.922 điểm**, Alpha vs Random: **+0.051 điểm**, $p = 0.320$.
- **Đánh giá & Tiêu chí giữ lại:**
  - Setup có biên gộp dương (+0.41 pt) nhưng biên quá mỏng so với tổng ma sát thực tế (0.90 đến 1.30 pt round-trip).
  - Alpha so với điểm vào ngẫu nhiên cùng giờ/hướng chỉ là +0.056 pt với p-value = 0.300 (không có ý nghĩa thống kê, không chứng minh được lợi thế chọn thời điểm).
  - **Quyết định:** Giữ lại dưới dạng **SHADOW FORWARD TRACKING** trong journal riêng (`paper_trade_journal_shadow.csv`), không đưa vào sổ chính và không điều chỉnh bất kỳ tham số nào.

---

### H-05: Setup Ứng Viên Shadow: OPENING_RANGE_BREAK
- **Mô tả & Quy tắc vào/thoát:**
  - **Khung biên ban đầu:** Thiết lập biên phiên định kỳ mở cửa 09:00–09:15 (`OR_High = max(High)`, `OR_Low = min(Low)` trong khoảng 09:00-09:15).
  - **Logic vào lệnh:** Sau 09:15, vào lệnh khi giá phá biên kèm khối lượng tương đối xác nhận:
    - Long: `Close > OR_High` và `RVOL >= 1.2` (tham số cố định 1.2, không dò).
    - Short: `Close < OR_Low` và `RVOL >= 1.2` (tham số cố định 1.2, không dò).
    - Lấy tín hiệu phá biên đầu tiên trong ngày (First Breakout of Day).
  - **Logic thoát lệnh:**
    - Cắt lỗ cố định: **Hard SL = 4.0 điểm** (`InitialStop = Entry \pm 4.0`), không phụ thuộc ATR.
    - Khóa lãi: Trailing Stop khi giá chạy thuận lợi (theo cơ chế trailing hiện có).
    - Thoát theo cơ chế **Gap-Aware**.
  - **Kỷ luật nghiên cứu:** Không quét tham số, tham số cố định 4.0 điểm stop và RVOL 1.2.
- **Kết quả kiểm định một lần trên 2018–2026 (529,784 thanh 1 phút):**
  - **Số lệnh:** 2,182 lệnh (~1 lệnh/ngày giao dịch).
  - **Biên gộp (Gross Margin):** **+0.534 điểm/lệnh** (trước chi phí).
  - **Net Expectancy (sau trượt giá & phí 30k round-trip):**
    - Trượt giá 0.3 pt: **-0.359 điểm/lệnh** (Lỗ lũy kế: $-78.34$M VND, PF: 0.80, Win Rate: 31.9%).
    - Trượt giá 0.5 pt: **-0.781 điểm/lệnh** (Lỗ lũy kế: $-170.46$M VND, PF: 0.62, Win Rate: 27.7%).
  - **Rủi ro đuôi (Gap-Aware Tail Risk):** Max Loss: **5.10 điểm**, P99 Loss: 4.60 điểm (Cắt lỗ cố định 4.0 điểm đã triệt tiêu hoàn toàn các cú sập đuôi nặng nề).
  - **Block Bootstrap theo ngày 95% CI (5-day blocks, 2,000 resamples):**
    - Trượt giá 0.3 pt: **[-0.56, -0.17] điểm** (CI strictly negative do ma sát).
    - Trượt giá 0.5 pt: **[-0.98, -0.59] điểm** (CI strictly negative do ma sát).
  - **So sánh Baseline ngẫu nhiên (Matched Random Null - cùng phân phối giờ và hướng, 100 MC draws):**
    - Trượt giá 0.3 pt: Random Exp: **-0.677 điểm**, Alpha vs Random: **+0.318 điểm**, **$p = 0.000$ ($p < 0.001$)**.
    - Trượt giá 0.5 pt: Random Exp: **-1.081 điểm**, Alpha vs Random: **+0.300 điểm**, **$p = 0.000$ ($p < 0.001$)**.
- **Đánh giá & Tiêu chí giữ lại:**
  - **Điểm sáng:** Khác với Setup A, Setup B sở hữu một lợi thế định hướng thực sự vượt trội so với ngẫu nhiên ($\alpha \approx +0.32$ điểm, $p < 0.001$ cực kỳ có ý nghĩa thống kê). Cơ chế Stop 4.0 điểm cố định khống chế rủi ro đuôi xuất sắc (Max Loss chỉ 5.10 điểm so với 45.7 điểm của ATR).
  - **Nút thắt:** Biên gộp (+0.53 pt) vẫn nhỏ hơn chi phí ma sát round-trip (0.90 pt ở slip 0.3). Khi giao dịch tần suất cao mỗi ngày 1 lệnh, ma sát nuốt trọn alpha và làm âm expectancy.
  - **Quyết định:** Giữ lại dưới dạng **SHADOW FORWARD TRACKING** trong journal riêng (`paper_trade_journal_shadow.csv`) từ hôm nay (`2026-10-20`). Là ứng viên sáng giá kết hợp với nghiên cứu **H-06** (lệnh LO Maker + gói 0 đồng CTCK để ép ma sát xuống dưới 0.3 pt). Tuyệt đối không tinh chỉnh tham số sau khi thấy kết quả.
