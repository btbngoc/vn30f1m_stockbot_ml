# BÁO CÁO HOÀN TẤT CÀI ĐẶT BOT 2 TRÊN OCI VPS (STAGE 40.1)

**Dự án:** REGIME-ROUTER-02 (VN30F1M Futures)  
**Thời gian hoàn tất:** 2026-11-24 00:30 ICT  
**Hạ tầng đích:** Oracle Cloud Infrastructure (`instance-20261114-1044` / `161.33.147.149`)  
**Trạng thái Bot 1:** `Status: Verified` — **ZERO TOUCH 100%** (PID `139407`, Uptime $> 7.3\text{ ngày}$, 0 exceptions).  
**Trạng thái Bot 2:** **ĐÃ CÀI ĐẶT HOÀN CHỈNH & ĐĂNG KÝ SYSTEMD (STANDBY / INACTIVE)**.

---

## 1. TỔNG HỢP CÁC THÀNH PHẦN ĐÃ CÀI ĐẶT TRÊN VPS

| Thành phần | Vị trí trên VPS | Trạng thái hiện tại |
|:---|:---|:---:|
| **Mã nguồn ứng dụng** | `/opt/vn30f1m-bot2/app/` | Đầy đủ `src/`, `scripts/`, `.env` |
| **Virtual Environment** | `/opt/vn30f1m-bot2/.venv/` | Python 3.12.15, Numpy 2.5.5, Pandas 3.1.1, WebSockets 17.4 |
| **Cơ sở dữ liệu SQLite** | `/opt/vn30f1m-bot2/data/paper_trading.db` | WAL mode, Checkpoint `(0,0,0)`, Quick Check `ok` |
| **Systemd Service** | `/etc/systemd/system/vn30f1m-bot2.service` | `Loaded: loaded (enabled)`, `Active: inactive (dead)` |
| **Cú pháp Systemd** | `systemd-analyze verify` | **0 errors / 0 warnings** |

---

## 2. RÀO CHẮN AN TOÀN & GIỚI HẠN TÀI NGUYÊN ĐÃ THIẾT LẬP

- **Cô lập Filesystem (Sandbox):**
  - `ProtectSystem=strict`, `ProtectHome=read-only`
  - `ReadWritePaths=/opt/vn30f1m-bot2`
  - `InaccessiblePaths=/opt/vn30f1m /var/lib/vn30f1m /var/log/vn30f1m /run/vn30f1m` *(Đã kiểm chứng: tiến trình bên trong sandbox bị từ chối đọc/ghi 100%)*.
- **Giới hạn cgroup v2:**
  - `MemoryHigh=90M` / `MemoryMax=105M` / `MemorySwapMax=0`
  - `CPUQuota=40%` / `TasksMax=30` / `Nice=10`
  - `OOMScoreAdjust=+500` / `OOMPolicy=kill`
- **Chính sách Restart an toàn:**
  - `Restart=on-failure`, `RestartSec=30s`
  - `StartLimitIntervalSec=300`, `StartLimitBurst=3`

---

## 3. HIỆN TRẠNG TÀI NGUYÊN VPS SAU KHI CÀI ĐẶT

```text
               total        used        free      shared  buff/cache   available
Mem:             498         236          57           4         227         262
Swap:           5040         399        4641
```
- **Bot 1:** PID `139407`, RAM `9.2M`, Uptime `637439s`, Heartbeat đều đặn 60s, **0 exceptions**.
- **Bot 2:** `inactive (dead)` (Ở trạng thái chờ, $0\text{ MB}$ RAM, không chiếm dụng tài nguyên).
- **RAM khả dụng của máy chủ:** **$262\text{ MiB}$** (Rất an toàn).

---

## 4. QUY TRÌNH THỰC THI CHO PHIÊN GIAO DỊCH TIẾP THEO

Khi phiên giao dịch mở cửa (ngày kia, lúc 08:45 hoặc 09:15 ICT sau ATO):

1. **Lệnh kích hoạt Bot 2:**
   ```bash
   ssh -i oci_key.key opc@161.33.147.149 "sudo systemctl start vn30f1m-bot2.service"
   ```
2. **Theo dõi trực tiếp cgroup và log (30 phút):**
   ```bash
   ssh -i oci_key.key opc@161.33.147.149 "journalctl -u vn30f1m-bot2.service -f"
   ```
3. **Lệnh dừng kiểm tra sau 30 phút:**
   ```bash
   ssh -i oci_key.key opc@161.33.147.149 "sudo systemctl stop vn30f1m-bot2.service"
   ```
