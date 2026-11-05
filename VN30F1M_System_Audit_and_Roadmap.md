# BÁO CÁO KIỂM ĐỊNH TOÀN DIỆN & LỘ TRÌNH ĐÓNG BĂNG HỆ THỐNG VN30F1M

> **Mã Commit Git:** `55115f93c994d2d4754484ea885c220d1fc11a84`  
> **Trạng thái hệ thống:** ĐÓNG BĂNG BASELINE (Frozen Baseline) — `Real Money Allocation = 0` (Ngoại trừ tối đa 1 HĐ thực nghiệm đo ma sát)  
> **Phiên bản:** 3.1 (Đã tích hợp đầy đủ các hiệu chỉnh phương pháp luận)  
> **Ngày phê duyệt:** 04/11/2026  

---

## 1. NHẬT KÝ KIỂM TOÁN CÁC LẦN THỬ NGHIỆM (TRIAL AUDIT LEDGER)

Theo nguyên tắc **EP-01** và **AI-04**, mọi can thiệp và tinh chỉnh thông số trong lịch sử nghiên cứu phải được ghi nhận minh bạch để tránh việc che giấu mức độ thử nghiệm (multiple testing / degrees of freedom).

> [!WARNING]
> **Cảnh báo về Chi phí Bậc tự do (Multiple Testing Penalty):**  
> Ngoài 8 can thiệp kiến trúc lớn (T-01 đến T-08) dưới đây, quá trình nghiên cứu đã trải qua hàng chục lượt quét tham số (quét dải ngưỡng 0.45 – 0.60, thử nghiệm horizon 50m vs 240m, thay đổi trọng số phân loại, các biến thể walk-forward). Toàn bộ các lần quét này đều làm tiêu hao bậc tự do thống kê. Do đó, các kết quả backtest/walk-forward không được coi là bằng chứng về alpha tương lai nếu không có kiểm định trên dữ liệu forward mới.

| STT | Thời điểm | Nội dung can thiệp | Lý do / Bối cảnh | Kết quả thực nghiệm đo được | Trạng thái hiện tại |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **T-01** | 15/10/2026 | Đổi horizon nhãn từ 50 lên 240 nến (4h) | Tăng khả năng nắm bắt xu hướng dài | AUC tăng vọt từ 0.51 lên 0.63 | **Đã loại bỏ rò rỉ:** Purged AUC thực tế là `0.57 - 0.58` (2024–2025) và `0.53` (2026). |
| **T-02** | 19/10/2026 | Bổ sung Soft SL (chờ nến 15m xác nhận) | Chống quét stop râu nến micro-tick | Net PnL tăng `+3.55M VND` (trung bình 10 seed); vượt trội trên 9/10 seed | **CHẤP THUẬN làm Baseline** |
| **T-03** | 20/10/2026 | Tăng ngưỡng lọc ML từ 0.52 lên 0.55 | Tinh chỉnh sau khi thấy drawdown 2026 | Số lệnh giảm, kết quả OOS biến động | **ĐÓNG BĂNG:** Giữ nguyên theo Walk-forward validation, không chỉnh tay. |
| **T-04** | 21/10/2026 | Thêm Short Regime Gate | Cố gắng chặn các lệnh Short thua lỗ 2026 | Chặn nhầm lệnh thắng +2.04M; tổng PnL 3 năm giảm từ +7.82M xuống +3.39M | **BÁC BỎ VĨNH VIỄN (Curve-fit)** |
| **T-05** | 02/11/2026 | Đề xuất Overnight Profit Buffer (H-07) | Giả thuyết cần lãi đệm trước khi giữ qua đêm | Phân tích 14:25 cho thấy các lệnh đang âm lại tạo +5.86M (78.6% WR) do đuôi dày | **BÁC BỎ VĨNH VIỄN (Survivorship bias)** |
| **T-06** | 03/11/2026 | Kiểm tra 10 Random Seeds XGBoost | Đo độ ổn định thống kê của mô hình ML | Mean +4.18M (std 4.92M), Median +6.66M, 2/10 seed âm vốn | **XÁC NHẬN làm phân phối chuẩn** |
| **T-07** | 03/11/2026 | Lag 1 nến toàn bộ Feature đa khung HTF | Kiểm tra rò rỉ nến HTF chưa đóng | $\Delta$ Purged AUC chỉ `-0.0003` đến `-0.0092` | **XÁC MINH: Không có rò rỉ HTF lookahead** |
| **T-08** | 04/11/2026 | Đề xuất trần Hard Stop $\le 12$ điểm | Ý tưởng khống chế lỗ đuôi qua đêm | Trích xuất hậu nghiệm từ dữ liệu 2026; không ngăn được gap mở cửa | **QUARANTINED (Cách ly / Chưa thử nghiệm)** |
| **T-09** | 05/11/2026 | Phép thử Hoán vị Phân tầng (Stratified Permutation Test) | Đo kỹ năng thực của ML so với rút ngẫu nhiên cùng năm & hướng (1,000 lần) | 2024 có tín hiệu ($p=0.028$), 2025 vượt trội ($p=0.000$), nhưng 2026 mất sạch kỹ năng ($p=0.590$). Tổng thể $p=0.014$ (chưa phạt số lần thử). | **ĐÃ XÁC MINH: Alpha suy giảm theo thời gian** |

---

## 2. KẾT QUẢ ĐO LƯỜNG THỰC NGHIỆM ĐÃ XÁC MINH (10-SEED DISTRIBUTION)

Mọi báo cáo hiệu năng chính thức bắt buộc sử dụng **phân phối qua 10 seed** (Seeds 40 – 49), tuyệt đối không dùng giá trị cá biệt của Seed 42 (+9.08M):

```
Phân phối Net PnL OOS qua 10 seeds (Trượt 0.3 pt, Phí 30k round-trip):
   Lỗ [-4.4M] ─── Seed 47 (-4.42M)
   Lỗ [-4.0M] ─── Seed 45 (-3.96M)
   Hòa [ 0.0M] ─── Seed 43 (+0.20M)
        [+1.0M] ─── Q1 (+0.96M)
        [+3.2M] ─── Seed 40 (+3.25M)
        [+4.2M] ─── MEAN (+4.18M, std: 4.92M)
        [+6.7M] ─── MEDIAN (+6.66M)
        [+8.0M] ─── Q3 (+8.00M)
   Đỉnh [+9.1M] ─── Seed 41 (+9.06M), Seed 42 (+9.08M)
```

- **Thống kê PnL ròng 3 năm:** Mean = `+4,179,000 VND` ($\text{std} = 4,918,905\text{ VND}$); Median = `+6,655,000 VND` [IQR: `+962,500` đến `+8,002,500`].
- **Thống kê Profit Factor:** Mean = `1.10` [Min: `0.92`, Max: `1.22`]. Có **2/10 seed âm vốn ròng** ngay tại mức trượt lý thuyết 0.3 điểm.
- **Kỳ vọng trên lệnh (Expectancy):** $\sim +26,100\text{ VND/lệnh}$ trên tổng ~160 lệnh sau 3 năm.

### 2.1. Bản chất Lệch pha Layer 1 Gross và ML (Hypothesis & Empirical Evidence)
- **Chuẩn hóa đơn vị thống kê:** Đơn vị phân tích thống kê chính thức duy nhất là **Lệnh giao dịch hoàn chỉnh (Trades)**. Mọi chỉ số đánh giá, Profit Factor, Drawdown, Expectancy và Bootstrap CI bắt buộc phải tính trên lệnh thực tế. Tỷ lệ gộp giữa nến tín hiệu thô và lệnh giao dịch là $\sim 2.06\text{ nến/lệnh}$ (do các nến tín hiệu 1-phút xuất hiện liên tiếp trong cùng một pha setup kỹ thuật và thời gian cooldown 15 nến).
- **Dữ liệu thực tế:** 
  - Tại 2025: ML lọc bỏ 147 lệnh Layer 1 đang lỗ `-19.43M`, giữ lại 55 lệnh lãi `+15.32M` (ML phát huy tối đa giá trị).
  - Tại 2026: Layer 1 thô đạt `+17.61M` gross. ML chỉ cho qua 33 lệnh (lỗ `-1.36M`), nhưng chặn 172 lệnh (trong đó 100 lệnh Long bị chặn mang lại `+21.40M` gross).
- **Trạng thái Giả thuyết Directional Bias:** 
  - Xét trên toàn bộ tín hiệu nến năm 2026: ML giữ lại **52 Short / 26 Long** (67% Short), nhưng chặn bỏ **206 Long / 137 Short** (60% Long).
  - *Kết luận phương pháp luận:* Hiện tượng Directional Bias này là một **giả thuyết được số liệu ủng hộ trên duy nhất dữ liệu năm 2026**. Hiện chưa có bằng chứng nào cho thấy hiện tượng này có tính lặp lại ở các chu kỳ khác. Do đó, **tuyệt đối không dùng giả thuyết này để đưa ra quyết định thay đổi cấu hình chiến lược** trước khi được kiểm chứng độc lập trên tập dữ liệu forward mới.

---

## 3. QUY TRÌNH GIÁM SÁT VẬN HÀNH THỰC NGHIỆM (CHỈ ÁP DỤNG LIVE 1 HỢP ĐỒNG)

> [!IMPORTANT]
> Toàn bộ các tiêu chí về trượt giá và tỷ lệ khớp chỉ có giá trị khi đặt lệnh thực tế (Live 1 HĐ). Paper trading giả định trượt giá theo mô hình nên hoàn toàn vô hiệu cho việc kiểm chứng ma sát.

### 3.1. Tiêu chí Dừng Nghiêm ngặt (Kill-Switch Criteria)
1. **Slippage Kill-Switch:**
   - Đánh giá sau **20 lệnh khớp thật đầu tiên**.
   - Nếu trượt giá thực tế bình quân **$> 0.25\text{ điểm/lệnh}$** $\rightarrow$ **DỪNG HỆ THỐNG NGAY LẬP TỨC**.
   - *Lý do:* Ngưỡng hòa vốn trung bình của 10 seed là $\sim 0.38 - 0.42$ điểm. Dừng ở 0.25 điểm giúp bảo lưu biên an toàn tối thiểu.
2. **Limit Order Fill Rate & Adverse Selection Kill-Switch (Định nghĩa đo lường cụ thể):**
   - Với mỗi tín hiệu LO không khớp (unfilled), hệ thống tự động ghi nhận giá mở vị thế giả định tại giá đóng cửa của nến tín hiệu (tương đương khớp MTL) và theo dõi kết quả PnL giả định theo logic thoát lệnh chuẩn.
   - Định lượng mức độ lựa chọn bất lợi: $\Delta \text{PnL} = \overline{\text{PnL}}_{\text{Unfilled}} - \overline{\text{PnL}}_{\text{Filled}}$.
   - **Còi cảnh báo sớm (20 lệnh đầu):** Nếu Fill Rate $< 70\%$ HOẶC $\overline{\text{PnL}}_{\text{Unfilled}} > \overline{\text{PnL}}_{\text{Filled}} + 2.0\text{ điểm}$ $\rightarrow$ Bật cảnh báo kỹ thuật về nguy cơ bỏ lỡ trend lớn.
   - **Quyết định dừng chính thức ($\ge 50$ tín hiệu):** Nếu Fill Rate $< 70\%$ HOẶC $\overline{\text{PnL}}_{\text{Unfilled}} > \overline{\text{PnL}}_{\text{Filled}} + 1.5\text{ điểm}$ (với độ tin cậy thống kê $p < 0.05$) $\rightarrow$ **DỪNG CƠ CHẾ LIMIT ORDER** và chuyển sang rà soát lại cơ chế đặt lệnh thị trường có kiểm soát trượt giá.
3. **Drawdown Kill-Switch:**
   - Ngưỡng lỗ lũy kế chạm **$5,000,000\text{ VND}$** ($\mathbf{50.0\text{ điểm VN30F1M}}$ với 1 HĐ) $\rightarrow$ **DỪNG VÔ ĐIỀU KIỆN**.
4. **Early Warning Cảnh báo sớm:**
   - Sau 30 lệnh, nếu Rolling $\text{Profit Factor} < 0.85$ $\rightarrow$ Bật cảnh báo kỹ thuật kiểm tra lỗi kết nối hoặc lệch feed. (Chỉ mang tính chất đánh động sớm, không dùng để kết luận bác bỏ thống kê do CI tại $N=30$ rất rộng).

### 3.2. Tiêu chí Tiếp tục (Progression / Go Criteria) — *Đánh giá tại mốc 50 lệnh thật*
Nếu đạt đồng thời cả 4 điều kiện sau 50 lệnh thực tế:
- [x] Cỡ mẫu thực tế $\ge 50$ lệnh.
- [x] Trượt giá bình quân $\le 0.20$ điểm/lệnh.
- [x] Limit Order Fill Rate $\ge 75\%$.
- [x] Net $\text{Profit Factor} \ge 1.05$ và $\text{Expectancy} > +20,000\text{ VND/lệnh}$ sau toàn bộ thuế phí thực tế.
- [x] Max Drawdown $\le 25.0$ điểm ($2.5\text{M VND}$).

> [!CAUTION]
> **Giới hạn quy mô:** Đạt chuẩn 50 lệnh **CHỈ CHO PHÉP tiếp tục chạy thử nghiệm tiến tới mốc 100+ lệnh** nhằm thu hẹp sai số chuẩn ($\text{SE} \approx 20\text{k}-30\text{k VND}$ tại $N=50$). **TUYỆT ĐỐI KHÔNG TĂNG QUY MÔ VỐN.**

---

## 4. LỘ TRÌNH HÀNH ĐỘNG THEO THỨ TỰ ƯU TIÊN

```
ƯU TIÊN 1 (Quyết định Go/No-Go):
   Đo lường ma sát thực tế (Live 1 HĐ: LO vs MTL, Broker Fee ~11k, Fill Rate)
                           │
       ┌───────────────────┴───────────────────┐
       ▼ (Slip > 0.25 pt hoặc Fill Rate < 70%) ▼ (Slip <= 0.20 pt & Fill Rate >= 75%)
   DỪNG DỰ ÁN                               ƯU TIÊN 2:
(Ma sát nuốt hết alpha)                      Nghiên cứu Cải tiến Bộ lọc ML
                                             • Tách Model Long / Short riêng
                                             • So sánh Expanding vs Rolling Window (2/3/5 năm)
                                             • Loại bỏ Feature Khung giờ (Lunch/Close)
                                             • Làm mượt ngưỡng theo Plateau Expectancy
                                                       │
                                                       ▼
                                             ƯU TIÊN 3 (Backlog - QUARANTINED):
                                             • Quản trị rủi ro đuôi qua đêm theo % Equity
                                             • Nghiên cứu Alpha Basis VN30F1M - VN30
```

### Chi tiết Ưu tiên 1: Giảm ma sát và Đo đạc Khớp lệnh Thực
1. **Lệnh vào (Entry):** Thử nghiệm Lệnh giới hạn (Limit Order) đặt tại giá Bid/Ask tốt nhất lúc phát tín hiệu. Ghi nhận chi tiết: Slippage, Thời gian chờ khớp, và Tỷ lệ khớp (Fill Rate).
2. **Lệnh ra / Cắt lỗ (Exit):** Bắt buộc dùng Lệnh thị trường (MTL / Stop Market) để đảm bảo vị thế được đóng dứt khoát.
3. **Biểu phí:** Kích hoạt gói phái sinh miễn phí môi giới để kéo chi phí vòng từ $30,000\text{ VND}$ xuống $\sim 11,000\text{ VND/hợp đồng}$ (tiết kiệm ngay $\sim 19,000\text{ VND/lệnh}$, nâng biên an toàn của hệ thống).

### Chi tiết Ưu tiên 2: Cải tiến Bộ lọc ML (Chỉ làm khi Ưu tiên 1 đạt chuẩn)
1. **Mô hình Long / Short riêng biệt:** Huấn luyện 2 mô hình độc lập để triệt tiêu Directional Bias.
2. **Thực nghiệm Cửa sổ Huấn luyện (Windowing):** So sánh công bằng giữa Expanding Window và Rolling Window (2 năm, 3 năm, 5 năm kèm time-decay) qua 10 seeds; ghi nhận đầy đủ vào Trial Ledger và chọn bằng Validation.
3. **Loại bỏ Feature Khung giờ:** Bỏ `LunchSession`, `CloseSession`, `OpenSession` để kiểm tra xem Purged AUC có duy trì được $\sim 0.57$ mà không bị phụ thuộc vào giờ giao dịch hay không.
4. **Làm mượt Ngưỡng (Threshold Smoothing):** Không chọn đỉnh nhọn (point estimate) của Expectancy trên Validation nhỏ, mà chọn vùng bình nguyên (plateau) hoặc dùng top-k% phân vị.

### Chi tiết Ưu tiên 3: Các hạng mục Cách ly (QUARANTINED Backlog)
1. **Trần Hard Stop:** Đưa vào trạng thái `QUARANTINED`. Không áp dụng mức trần cứng 12 điểm vì đây là số liệu nhìn trộm từ 2026 và không chặn được gap qua đêm. Mọi quy tắc quản trị rủi ro qua đêm trong tương lai phải được suy ra từ hạn mức % vốn tài khoản và chỉ kiểm tra trên dữ liệu forward.
2. **Alpha Basis VN30F1M − VN30:** Đưa vào trạng thái `QUARANTINED` cho đến khi thu thập đủ dữ liệu 1-phút sạch không có độ trễ feed.

---

## 5. TỔNG KẾT QUYẾT ĐỊNH

- **Baseline đóng băng:** Wyckoff Layer 1 + Soft SL 15m (Stop 5m ATR) + XGBoost Walk-Forward (10 seeds mean/median).
- **Phân bổ vốn:** Duy trì ở mức **0**, ngoại trừ 1 hợp đồng đo lường ma sát thực nghiệm.
- **Tiêu chuẩn chấp thuận:** Mọi kết luận trong tương lai phải có bằng chứng từ ít nhất 10 random seeds và trích xuất từ dữ liệu thực tế.

