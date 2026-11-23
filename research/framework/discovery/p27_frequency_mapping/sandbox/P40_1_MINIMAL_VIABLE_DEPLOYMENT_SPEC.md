# BẢN ĐẶC TẢ TRIỂN KHAI TỐI THIỂU & KIỂM CHỨNG AN TOÀN BOT 2
## (Minimal Viable Deployment & Lightweight Pre-Flight Verification)

**Mã tài liệu:** `P40-DOC-09-MVD`  
**Dự án:** `REGIME-ROUTER-02` (VN30F1M Futures)  
**Trạng thái:** ĐỀ XUẤT CHUYỂN HƯỚNG THEO CHỈ ĐẠO TECH LEAD  
**Môi trường đích:** Oracle Cloud Infrastructure VPS (`instance-20261114-1044`, 498 MiB RAM)  
**Môi trường kiểm chứng trước:** Staging VM Linux độc lập (512 MiB RAM)  
**Nguyên tắc cốt lõi:** ZERO TOUCH 100% đối với Bot 1 (`vn30f1m.service`, PID `139407`).  

---

## 1. THỐNG NHẤT ĐIỀU CHỈNH GOVERNANCE (PIVOT OVER-ENGINEERING)

Thực hiện đúng chỉ đạo của Tech Lead, nhóm kỹ thuật chấm dứt việc phát triển mở rộng `Harness v2.3`:
1. **Đóng băng (Freeze) Harness v2.3:** Toàn bộ harness v2.3, ratifier 5 cổng và hệ thống manifest phức tạp đã được lưu trữ an toàn trên branch git `feature/stage-40-1-harness-v23-final` (commit `4b4e06d`) làm tài liệu tham khảo nội bộ, không tiếp tục phát triển.
2. **Định hình lại Stage 40.1:** Chuyển trọng tâm từ "xây dựng framework kiểm thử kiểm toán" sang **"Triển khai chuẩn mực, cô lập tài nguyên độc lập và kiểm chứng trước chuyến bay (Pre-flight Sanity Check) tối giản"**.
3. **Mục tiêu tối thượng:** Đưa Bot 2 vào vận hành an toàn song song với Bot 1 trên hạ tầng thực tế, không xây dựng hệ thống kiểm thử cồng kềnh hơn chính trading bot.

---

## 2. HIỆN TRẠNG TÀI NGUYÊN VPS (498 MiB RAM) & NGÂN SÁCH TÀI NGUYÊN

Dựa trên dữ liệu thực nghiệm đã ghi nhận từ OCI VPS (`VM.Standard.E2.1.Micro`):

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
| Bot 2 Hard Limit (MemoryMax)| 75 MiB                          | Ngăn OOM hệ thống|
| Bot 2 Soft Limit (MemoryHigh)| 60 MiB                          | Kernel điều tiết |
| Bot 2 Swap (MemorySwapMax)  | 0                               | Chống disk thrash|
| Buffer an toàn còn lại      | ~175 MiB                        | Bảo vệ Bot 1 & OS|
+-----------------------------+---------------------------------+------------------+
```

> [!IMPORTANT]
> **Quy tắc an toàn sống còn:** Không bao giờ cấp cho Bot 2 quá **75 MiB RAM** (`MemoryMax=75M`). Nếu Bot 2 bị memory leak chạm trần 75 MiB, cgroup OOM Killer sẽ chỉ hủy tiến trình Bot 2 (Tier 1 Local OOM), bảo vệ tuyệt đối Bot 1 và OS khỏi nguy cơ bị OOM Killer toàn cục (Global OOM) chấm dứt.

---

## 3. BA TRỤ CỘT TRIỂN KHAI THEO CHỈ ĐẠO TECH LEAD

### Trụ cột 1: Giữ nguyên Bot 1 (100% Zero Touch)
- Không chỉnh sửa code, dependencies, thư mục `/opt/vn30f1m/`.
- Không thay đổi service `/etc/systemd/system/vn30f1m.service`.
- Không can thiệp DB SQLite của Bot 1 (`/opt/vn30f1m/app/data/`).
- Không reload/restart service Bot 1.

### Trụ cột 2: Triển khai Bot 2 độc lập (Clean Independent Setup)
Mô phỏng mô hình vận hành của Bot 1 nhưng áp dụng rào chắn độc lập:
- **Thư mục ứng dụng:** `/opt/vn30f1m-bot2/app/`
- **Virtual Environment riêng:** `/opt/vn30f1m-bot2/.venv/` (Python 3.12/3.13 cô lập hoàn toàn).
- **Cấu hình môi trường:** `/opt/vn30f1m-bot2/app/.env` (API key, client id, webhook riêng).
- **Cơ sở dữ liệu riêng:** `/opt/vn30f1m-bot2/app/data/bot2_trades.db` (bật `WAL`, `busy_timeout=5000`).
- **File Systemd Service độc lập:** `/etc/systemd/system/vn30f1m-bot2.service`.

#### Thiết kế Service `vn30f1m-bot2.service`:
```ini
[Unit]
Description=VN30F1M Institutional Paper Trading Pipeline Service (Bot 2 - REGIME-ROUTER-02)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=opc
Group=opc
WorkingDirectory=/opt/vn30f1m-bot2/app

Environment="PYTHONUNBUFFERED=1"
Environment="PATH=/opt/vn30f1m-bot2/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
EnvironmentFile=/opt/vn30f1m-bot2/app/.env

ExecStart=/opt/vn30f1m-bot2/.venv/bin/python scripts/run_cloud_paper_trading.py

Restart=always
RestartSec=10s
TimeoutStartSec=30s
TimeoutStopSec=30s
KillSignal=SIGTERM
KillMode=mixed

LimitNOFILE=65535

# --- BẢO VỆ FILESYSTEM & CÔ LẬP VỚI BOT 1 ---
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/opt/vn30f1m-bot2
InaccessiblePaths=/opt/vn30f1m

# --- GIỚI HẠN TÀI NGUYÊN (PHÙ HỢP VPS 498 MiB) ---
MemoryAccounting=yes
MemoryMax=75M
MemoryHigh=60M
MemorySwapMax=0
CPUAccounting=yes
CPUQuota=40%
TasksMax=30
Nice=10
OOMScoreAdjust=+500

StandardOutput=journal
StandardError=journal
SyslogIdentifier=vn30f1m-bot2

[Install]
WantedBy=multi-user.target
```

### Trụ cột 3: Bộ kiểm tra tối thiểu trước khi chạy (Pre-Flight Sanity Check)
Thay thế toàn bộ harness phức tạp bằng **4 bài test cơ bản trực tiếp**:

| STT | Bài kiểm tra | Phương thức thực hiện | Tiêu chí đạt (Pass Criteria) |
|:---:|:---|:---|:---|
| **1** | **Permission Boundary** | Cho Bot 2 cố đọc `/opt/vn30f1m/app/.env` và ghi vào `/opt/vn30f1m/app/data/` | Bắt buộc nhận lỗi `Permission Denied` từ kernel / systemd sandbox. |
| **2** | **Cgroup Limits Enforcement** | Kiểm tra `/sys/fs/cgroup/system.slice/vn30f1m-bot2.service/` khi unit khởi động | `memory.max == 78643200` (75M), `memory.swap.max == 0`, `cpu.max == "40000 100000"`. |
| **3** | **SQLite WAL Concurrency** | Bot 2 ghi 500 records liên tục vào `bot2_trades.db` ở chế độ WAL | 100% commits thành công, không gặp SQLITE_BUSY, checkpoint hoạt động. |
| **4** | **Controlled Load Co-existence** | Chạy thử nghiệm 10 phút trên Staging VM (512 MiB RAM) cùng 1 tiến trình mô phỏng Bot 1 | Tổng RAM VPS < 350 MiB, Swap = 0, Heartbeat Bot 1 không trễ quá 50ms. |

---

## 4. MA TRẬN PHÂN ĐỊNH TRÁCH NHIỆM & BƯỚC TIẾP THEO

- **Bước 1 (Staging Pre-flight):** Thực thi 4 bài kiểm tra tinh gọn trên Staging VM Linux độc lập.
- **Bước 2 (Báo cáo kết quả tối giản):** Lập biên bản 1 trang xác nhận 4 tiêu chí đạt.
- **Bước 3 (Xin phê duyệt Go-Live):** Trình Tech Lead phê duyệt trước khi kích hoạt `vn30f1m-bot2.service` trên VPS Production.
