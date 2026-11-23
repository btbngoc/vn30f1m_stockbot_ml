# P40-DOC-07: STAGE 40.1 LINUX NATIVE VERIFICATION PROTOCOL & RATIFICATION REPORT

- **Project:** `REGIME-ROUTER-02` (VN30F1M Futures)
- **Reference:** `P40-DOC-07-LINUX-VERIF` (v2.3 FINAL - Strict Fail-Closed Staging Protocol)
- **Standard:** `P40-DOC-08`
- **Phase:** Phase 40 — Stage 40.1 (Linux Resource Isolation Verification)
- **Status:** `REMEDIATED v2.3 FINAL — READY FOR CODE ACCEPTANCE`
- **Execution Target:** Independent Linux Staging VM (Zero Touch Production VPS)
- **Harness Script:** [tests/paper/linux_stage_40_1_cgroup_verify.sh](file:///d:/VN30F1M%20stock%20bot_bot%201%20c%C3%B3%20rr13/tests/paper/linux_stage_40_1_cgroup_verify.sh)
- **Git Branch:** `feature/stage-40-1-harness-v23-final`
- **Timestamp:** 2026-11-23T23:42:00+07:00

---

## 1. NGUYÊN TẮC VẬN HÀNH & TRIẾT LÝ KIỂM THỬ FAIL-CLOSED

Theo chỉ thị cốt lõi của Tech Lead:
> *"Một harness chuẩn không phải là một công cụ tạo ra các dòng PASS màu xanh, mà là một chốt chặn kỹ thuật tự động dừng và báo FAIL khi bất kỳ một giả định hay giới hạn an toàn nào bị vi phạm."*
> *"Nếu một gate không đạt, Stage 40.1 chưa được nghiệm thu. Không được lấy PASS của bốn gate còn lại để bù cho gate thất bại."*

### Kỷ luật an toàn tuyệt đối:
1. **Zero Touch Production VPS:** Giữ nguyên 100% VPS Oracle Cloud (`instance-20261114-1044`, PID `139407`). Không mở SSH, không ghi file, không truy cập database của Bot 1 thật.
2. **Zero Broker API & Streaming:** Không kết nối tài khoản chứng khoán, không đặt lệnh thật, không mở WebSocket streaming.
3. **Môi trường thực thi:** Chỉ chạy trên Linux Staging VM độc lập có nhân Linux hỗ trợ Cgroup v2 unified hierarchy và systemd active.

---

## 2. MA TRẬN 10 ĐIỂM SỬA ĐỔI TOÀN DIỆN TRONG HARNESS V2.3 FINAL

| Mã lỗi | Hạng mục khắc phục | Trạng thái trước | Cải tiến triệt để trong v2.3 FINAL | Mức độ |
| :---: | :--- | :--- | :--- | :---: |
| **P0-01** | **Unit đã tồn tại** | Cảnh báo rồi stop/reset unit đang active. | **FAIL ngay lập tức:** Nếu bất kỳ unit nào (`UNIT_BOT1_BASE`, `UNIT_BOT1_STRESS`, `UNIT_BOT2`) đang `active` hoặc `loaded`, script dừng với mã exit 1. Tuyệt đối không chạm vào unit pre-existing. | **CRITICAL** |
| **P0-02** | **Cgroup snapshot timing** | Ratifier đọc `cpu.max` và `pids.max` trực tiếp từ cgroup sau khi Bot 2 đã dừng $\to$ có thể mất file. | **Chụp snapshot khi Bot 2 còn sống:** Lưu `cpu_max.txt` và `pids_max.txt` vào artifact trước khi gửi `STOP_TRIGGER`. Ratifier chỉ đọc artifact, không chạm cgroup sau khi Bot 2 dừng. | **CRITICAL** |
| **P0-03** | **Cgroup memory control** | `resolve_cgroup_dir()` fallback về `/sys/fs/cgroup`; đọc memory fallback về VmRSS rồi về 0. | **Xóa bỏ toàn bộ fallback:** Nếu không phân giải được cgroup slice hoặc không đọc được `memory.current`, Bot 2 lập tức `sys.exit(1)`. Điều tiết bộ nhớ dựa $100\%$ vào cgroup kernel. | **CRITICAL** |
| **P0-04** | **Kiểm toán Zero Swap & Default values** | Dùng `.get(..., 0)` che giấu dữ liệu thiếu; không ghi nhận `memory.swap.max`. | **Bắt buộc `memory.swap.max == 0` & `memory.swap.current == 0`:** Sử dụng hàm `require_field()` nghiêm ngặt; thiếu bất kỳ trường nào thì FAIL ngay. | **CRITICAL** |
| **P0-05** | **Xác thực systemd & Controller delegation** | `check_env.py` chỉ đọc controller ở root, chưa kiểm tra systemd manager active hay transient unit. | **Thực hiện probe transient unit:** Kiểm tra systemd manager đang active, chạy probe unit `p40-stage40-1-probe` gán cả 3 controller (`MemoryAccounting`, `CPUAccounting`, `TasksAccounting`). Probe thất bại $\to$ dừng script. | **CRITICAL** |
| **P1-01** | **Đối chiếu giao dịch SQLite** | Chỉ kiểm tra `integrity_check = ok` và $COUNT(*) > 0$, chưa đối chiếu với số commit. | **Đối chiếu $1-1$ số row DB với commit count:** Kiểm tra `COUNT(*) == commits_total` và xác nhận `sqlite_errors == 0`. | **HIGH** |
| **P1-02** | **Cross-check toàn diện Raw vs Log** | Chỉ cross-check wake-up P99, bỏ qua commit P99 và heartbeat lateness. | **Cross-check cả 3 metrics:** Đối chiếu wake-up P99, commit P99, heartbeat max lateness, và commit count giữa raw JSON dataset và console log markers. | **HIGH** |
| **P1-03** | **Xác minh chính xác danh sách Artifact** | Manifest duyệt mọi file đang có trong thư mục bằng wildcard. | **Xác minh danh mục bắt buộc:** Kiểm tra đúng 17 file bắt buộc tồn tại và $> 0\text{ bytes}$ trước khi tiến hành tính mã băm SHA-256. | **HIGH** |
| **P1-04** | **Trình tự lập báo cáo & Manifest** | Chưa tạo report trước khi tính manifest. | **Tạo `verification_report.txt` trước:** Ratifier xuất báo cáo thẩm định chính thức vào `OUTPUT_DIR` trước khi đóng log và tạo `manifest.sha256`. Manifest là bước cuối cùng. | **HIGH** |
| **Shell** | **Loại bỏ `\|\| true` khi chờ workload** | Dùng `wait ... 2>/dev/null \|\| true` che giấu lỗi exit của workload. | **Xóa toàn bộ `\|\| true`:** Sử dụng `wait "${BOT1_STRESS_RUN_PID}"` và `wait "${BOT2_RUN_PID}"` nghiêm ngặt; kiểm tra `ExecMainStatus == 0`. | **CRITICAL** |

---

## 3. DANH MỤC 18 ARTIFACTS VẬT LÝ ĐẢM BẢO SINH RA (Section 10)

Sau khi hoàn tất thực thi, thư mục `/tmp/stage_40_1_artifacts` (hoặc `OUTPUT_DIR`) sẽ chứa đúng 18 artifacts vật lý được kiểm soát nghiêm ngặt:

1. `environment.txt` — Bằng chứng kernel, systemd version, cgroup v2 mount.
2. `cgroup_controllers.txt` — Danh sách controller gốc (`memory cpu pids`).
3. `bot1_baseline.log` — Log console Mock Bot 1 Baseline.
4. `bot1_baseline.raw_samples.json` — Dataset thô Baseline ($N \ge 2,000$ mẫu).
5. `bot2_stress.log` — Log console của tiến trình Bot 2 (closed-loop memory & CPU burn).
6. `memory_pre.txt` — Snapshot lúc Bot 2 IDLE (chứa cả `memory.swap.max` và `swap.current`).
7. `memory_post.txt` — Snapshot lúc Bot 2 đang STRESS (chứa cả `memory.swap.max` và `swap.current`).
8. `memory_telemetry.log` — Time-series từng giây của memory.current, high events, max events.
9. `cpu_stat_pre.txt` — Snapshot `cpu.stat` trước tải.
10. `cpu_stat_post.txt` — Snapshot `cpu.stat` sau tải.
11. `cpu_max.txt` — Snapshot `cpu.max` chụp trong lúc Bot 2 đang hoạt động trong cgroup.
12. `pids_max.txt` — Snapshot `pids.max` chụp trong lúc Bot 2 đang hoạt động trong cgroup.
13. `pids_telemetry.log` — Time-series tasks polling, max pids, peak tasks.
14. `bot1_stress.log` — Log console Mock Bot 1 Stress.
15. `bot1_stress.raw_samples.json` — Dataset thô Stress ($N \ge 2,000$ mẫu).
16. `verification_report.txt` — Báo cáo thẩm định 5 Gate chính thức được tạo trước khi lập manifest.
17. `execution.log` — Toàn bộ stdout/stderr của Harness run.
18. `manifest.sha256` — Bảng kiểm soát tính toàn vẹn SHA-256 cho 17 tệp trên (bước cuối cùng).

---

## 4. CHI TIẾT 5 GATES NGHIỆM THU (G1 - G5)

### Gate G1: Môi trường & Controller Delegation
- `Kernel Version` $\ge 5.8$.
- Mount type `/sys/fs/cgroup` là `cgroup2fs`.
- Tồn tại file `cgroup.controllers` chứa `memory`, `cpu`, `pids`.
- `systemd` manager đang active; transient unit probe gán thành công cả 3 controller.

### Gate G2: Cách ly bộ nhớ & Zero Swap
- `memory.max == 83886080` ($80.0\text{ MiB}$).
- `memory.high == 68157440` ($65.0\text{ MiB}$).
- `memory.swap.max == 0` và `memory.swap.current == 0` (Zero Swap bắt buộc).
- `max_mem_observed` đạt từ $65.0\text{ MiB}$ đến $< 80.0\text{ MiB}$.
- $\Delta \text{high} > 0$ (Soft limit kích hoạt), $\Delta \text{max} == 0$, $\Delta \text{oom} == 0$, $\Delta \text{oom\_kill} == 0$.

### Gate G3: Cách ly CPU & CFS Throttling
- `cpu.max == "50000 100000"` (Đọc từ artifact `cpu_max.txt`).
- $\Delta \text{usage\_usec} > 0$, $\Delta \text{nr\_periods} > 0$, $\Delta \text{nr\_throttled} > 0$, $\Delta \text{throttled\_usec} > 0$.

### Gate G4: Cách ly Task & Process
- `pids.max == 10` (Đọc từ artifact `pids_max.txt`).
- $\max(\text{pids.current during stress}) \le 10$ và $> 0$.
- `POLLING_ERROR_COUNT == 0`.

### Gate G5: Bảo vệ Bot 1 tuyệt đối & Đối chiếu dữ liệu
- Raw samples: $N \ge 2,000$ mẫu hợp lệ, tất cả finite và không âm.
- P99 tính trực tiếp từ raw samples: Wake-up P99 $\le 10.0\text{ ms}$, Commit P99 $< 50.0\text{ ms}$, Heartbeat Max Lateness $\le 2.0\text{ s}$.
- SQLite `PRAGMA integrity_check` $\equiv$ `ok`; số bản ghi DB khớp $1-1$ với raw commit count; `sqlite_errors == 0`.
- Cross-check $100\%$ giữa raw samples và log console summary.
- Exit status của cả 2 unit Bot 1 bằng `0`.

---

## 5. KẾT LUẬN & CAM KẾT VẬN HÀNH

- Toàn bộ mã nguồn đã hoàn thiện phiên bản **v2.3 FINAL** tuân thủ triệt để nguyên tắc fail-closed.
- VPS Production (`instance-20261114-1044`, PID `139407`) duy trì cam kết **ZERO TOUCH 100%**.

