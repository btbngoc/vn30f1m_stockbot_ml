# BẢN ĐẶC TẢ TRIỂN KHAI TỐI THIỂU & KIỂM CHỨNG AN TOÀN BOT 2 (v2.0)
## (Minimal Viable Deployment & Lightweight Pre-Flight Verification)

**Mã tài liệu:** `P40-DOC-09-MVD-v2`  
**Dự án:** `REGIME-ROUTER-02` (VN30F1M Futures)  
**Trạng thái:** TECH LEAD APPROVED WITH 4 CORRECTIONS  
**Môi trường đích:** Oracle Cloud Infrastructure VPS (`instance-20261114-1044`, 498 MiB RAM)  
**Môi trường kiểm chứng trước:** Staging VM Linux độc lập (512 MiB RAM)  
**Nguyên tắc cốt lõi:** ZERO TOUCH 100% đối với Production VPS và Bot 1 (`vn30f1m.service`, PID `139407`).  

---

## 1. THỐNG NHẤT ĐIỀU CHỈNH GOVERNANCE & PHẠM VI TRIỂN KHAI

Tuân thủ nghiêm ngặt chỉ đạo của Tech Lead:
1. **Dừng vĩnh viễn Harness v2.3:** Đóng băng toàn bộ framework ratifier và hệ thống manifest phức tạp. Toàn bộ mã nguồn đã được lưu trữ trên nhánh `feature/stage-40-1-harness-v23-final` làm tài liệu tham khảo kỹ thuật.
2. **Nguyên tắc kỹ thuật cốt lõi:** *Không xây thêm công cụ kiểm thử nếu một lệnh kiểm tra trực tiếp có thể chứng minh được yêu cầu.*
3. **Phạm vi Stage 40.1:** Triển khai Bot 2 độc lập theo mô hình của Bot 1, thiết lập rào chắn tài nguyên & sandbox, và thực hiện 4 bài kiểm chứng tối giản (Pre-Flight Sanity Check) trên Linux Staging VM trước khi xem xét đưa lên VPS.

---

## 2. HIỆN TRẠNG TÀI NGUYÊN VPS (498 MiB RAM) & RÀO CHẮN AN TOÀN

```
+---------------------------------------------------------------------------------+
|               PHÂN BỔ BỘ NHỚ VẬT LÝ VPS (TỔNG CỘNG: 498 MiB)                    |
+---------------------------------------------------------------------------------+
| Thành phần                  | Mức tiêu thụ thực tế / Thiết kế | Ghi chú          |
+-----------------------------+---------------------------------+------------------+
| Kernel + OS + System Daemons| ~220 - 240 MiB                  | Cố định          |
| Bot 1 (vn30f1m.service)     | Baseline: ~15 MiB (Peak: 122M)  | PID 139407       |
| Vùng đệm khả dụng (Free+Avail)| ~250 MiB (khi Bot 1 baseline)   | Dành cho Bot 2   |
+-----------------------------+---------------------------------+------------------+
| Bot 2 Hard Limit (MemoryMax)| 75 MiB (78,643,200 bytes)       | cgroup hard cap  |
| Bot 2 Soft Limit (MemoryHigh)| 60 MiB (62,914,560 bytes)       | Kernel điều tiết |
| Bot 2 Swap (MemorySwapMax)  | 0                               | Chống disk thrash|
| Buffer an toàn hệ thống     | ~175 MiB                        | Buffer cho OS    |
+-----------------------------+---------------------------------+------------------+
```

### [P0-01] Ranh giới An toàn OOM — Hiệu chỉnh Cam kết Kỹ thuật:
- `MemoryMax=75M` và `OOMPolicy=kill` đảm bảo khi cgroup Bot 2 vượt quá hạn mức, Cgroup Memory Controller sẽ kích hoạt Tier 1 Local OOM để chấm dứt nội bộ tiến trình Bot 2.
- `OOMScoreAdjust=+500` cộng thêm điểm badness cho Bot 2, giúp kernel ưu tiên lựa chọn Bot 2 trước nếu xảy ra sự cố áp lực bộ nhớ toàn hệ thống.
- **Tuyên bố ranh giới rõ ràng:** Các cơ chế trên **không cấu thành cam kết bảo vệ tuyệt đối $100\%$** trước sự cố Global OOM của host OS. Chúng đóng vai trò:
  1. Giới hạn tối đa rủi ro tiêu thụ RAM của Bot 2 trong phạm vi $\le 75\text{ MiB}$.
  2. Ưu tiên xử lý OOM cục bộ trong nội bộ cgroup của Bot 2.
  3. Giảm thiểu nguy cơ Bot 2 cạnh tranh bộ nhớ trực tiếp với Bot 1.
  4. Tuyệt đối không tuyên bố miễn nhiễm hoàn toàn đối với Global OOM.

---

## 3. THIẾT KẾ TRIỂN KHAI ĐỘC LẬP BOT 2

- **Thư mục ứng dụng riêng:** `/opt/vn30f1m-bot2/app/`
- **Virtual Environment riêng:** `/opt/vn30f1m-bot2/.venv/` (Python 3 cô lập hoàn toàn).
- **Cấu hình môi trường riêng:** `/opt/vn30f1m-bot2/app/.env` (API key, broker settings riêng).
- **Cơ sở dữ liệu riêng:** `/opt/vn30f1m-bot2/app/data/bot2_trades.db` (bật WAL mode, `busy_timeout=5000`).
- **File Systemd Service độc lập:** `/etc/systemd/system/vn30f1m-bot2.service` (đã commit tại [scripts/vn30f1m-bot2.service](file:///d:/VN30F1M%20stock%20bot_bot%201%20c%C3%B3%20rr13/scripts/vn30f1m-bot2.service)).

---

## 4. BỐN TIÊU CHÍ KIỂM CHỨNG TỐI GIẢN (PRE-FLIGHT SANITY CHECK)

### Tiêu chí 1: Permission Boundary (Giả lập Staging VM) [P0-03]
- **Môi trường:** Staging VM độc lập. Tuyệt đối không truy cập VPS Production.
- **Chuẩn bị:** Tạo thư mục và dữ liệu mock của Bot 1 trên Staging:
  - `/opt/vn30f1m/app/.env` (chứa mock API secret).
  - `/opt/vn30f1m/app/data/bot1_trades.db` (chứa mock SQLite DB).
- **Phương thức thực thi:** Chạy kiểm tra **bằng chính tiến trình hoạt động bên trong sandbox systemd** (sử dụng cấu hình của `vn30f1m-bot2.service` với user `opc` và sandbox flags `ProtectSystem=strict`, `InaccessiblePaths=/opt/vn30f1m`). Không dùng quyền `root` để kiểm tra.
- **Tiêu chí Đạt:** Cả 2 thao tác (đọc `.env` và ghi DB của Bot 1) đều phải bị từ chối với mã lỗi `Permission Denied` (EACCES) hoặc đường dẫn bị cô lập hoàn toàn.

### Tiêu chí 2: Cgroup Enforcement (Xác định động) [P0-02]
- **Xác định đường dẫn động:** Tuyệt đối không cố định đường dẫn cgroup. Truy vấn trực tiếp từ systemd:
  ```bash
  CG_REL=$(systemctl show vn30f1m-bot2.service -p ControlGroup --value)
  CG_PATH="/sys/fs/cgroup/${CG_REL}"
  ```
- **Xác thực trực tiếp từ kernel files:**
  - `memory.high` $\rightarrow$ giá trị chính xác: `62914560` ($60\text{ MiB}$)
  - `memory.max` $\rightarrow$ giá trị chính xác: `78643200` ($75\text{ MiB}$)
  - `memory.swap.max` $\rightarrow$ giá trị chính xác: `0`
  - `cpu.max` $\rightarrow$ giá trị chính xác: `40000 100000` ($40\%$ CFS quota)
  - `pids.max` $\rightarrow$ giá trị chính xác: `30`

### Tiêu chí 3: SQLite WAL Sanity & Checkpoint
- **Mục tiêu:** Xác nhận Bot 2 ghi chép an toàn vào DB riêng mà không bị khóa.
- **Thực thi:** Bot 2 kết nối tới `/opt/vn30f1m-bot2/app/data/bot2_trades.db`, thực thi 500 transactions liên tiếp.
- **Tiêu chí Đạt:**
  - `PRAGMA journal_mode;` trả về chính xác `wal`.
  - Thực hiện checkpoint thành công (`PRAGMA wal_checkpoint(TRUNCATE);` trả về `0 0 0`).
  - $500/500$ commits hoàn tất thành công, không gặp bất kỳ lỗi `SQLITE_BUSY` hay lock.

### Tiêu chí 4: Controlled Co-existence & Latency So sánh Baseline [P0-04]
- **Định nghĩa chỉ số RAM:**
  - RAM khả dụng host: Đọc `MemAvailable` từ `/proc/meminfo`.
  - RAM sử dụng host: $\text{Used} = \text{MemTotal} - \text{MemAvailable}$.
  - RAM cgroup Bot 2: Đọc `memory.current` từ `${CG_PATH}`.
  - Swap: Đọc `SwapTotal - SwapFree` từ host `/proc/meminfo` và `memory.swap.current` từ `${CG_PATH}` (cả hai phải bằng 0).
- **Phương pháp đo Heartbeat Latency:**
  - **Giai đoạn 1 (Baseline - 5 phút):** Khởi chạy Mock Bot 1 đơn lẻ trên Staging VM. Mock Bot 1 ghi log heartbeat định kỳ mỗi 1.000s với timestamp microsecond thực tế ($T_i$). Tính độ trễ từng nhịp $L_{\text{base}, i} = (T_i - T_{i-1}) - 1.000\text{s}$. Xác định $\text{P99}_{\text{base}}$.
  - **Giai đoạn 2 (Đồng thời - 10 phút):** Khởi động `vn30f1m-bot2.service` chạy song song cùng Mock Bot 1. Mock Bot 1 tiếp tục ghi nhận chuỗi nhịp $T_j$. Tính $\text{P99}_{\text{coex}}$.
- **Tiêu chí Đạt:**
  - Độ gia tăng độ trễ: $\Delta \text{P99} = \text{P99}_{\text{coex}} - \text{P99}_{\text{base}} \le 50\text{ ms}$.
  - Không có nhịp nào bị mất (missed heartbeat $> 3.0\text{s} = 0$).
  - RAM sử dụng host ($\text{MemTotal} - \text{MemAvailable}$) duy trì $< 350\text{ MiB}$.
  - Host swap và Bot 2 swap duy trì $0$.

---

## 5. KỊCH BẢN THỰC THI & BIÊN BẢN NGHIỆM THU

Toàn bộ 4 bài kiểm tra được tích hợp trong script thực thi duy nhất: [scripts/staging_preflight_check.sh](file:///d:/VN30F1M%20stock%20bot_bot%201%20c%C3%B3%20rr13/scripts/staging_preflight_check.sh).

Kết quả nghiệm thu được xuất trực tiếp thành báo cáo gọn 1 trang theo mẫu: [P40_1_PREFLIGHT_ACCEPTANCE_REPORT_TEMPLATE.md](file:///d:/VN30F1M%20stock%20bot_bot%201%20c%C3%B3%20rr13/research/framework/discovery/p27_frequency_mapping/sandbox/P40_1_PREFLIGHT_ACCEPTANCE_REPORT_TEMPLATE.md).
