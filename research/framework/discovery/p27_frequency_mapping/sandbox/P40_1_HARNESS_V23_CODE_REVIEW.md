# P40-DOC-09: HARNESS v2.3 FINAL CODE REVIEW & COMPLIANCE AUDIT REPORT

- **Project:** `REGIME-ROUTER-02` (VN30F1M Futures)
- **Reference Standard:** `P40-DOC-08` (Technical Requirements for Stage 40.1 Linux Native Verification Harness v2.3)
- **Harness Version:** v2.3 FINAL (`linux_stage_40_1_cgroup_verify.sh` & 5 Modular Python Scripts)
- **Git Branch:** `feature/stage-40-1-harness-v23-final`
- **Reviewer:** Engineering Team Self-Audit & Pre-Execution Gatekeeper
- **Status:** `VERIFIED & READY FOR CODE ACCEPTANCE`
- **Zero Touch Target:** Production VPS Oracle Cloud (`instance-20261114-1044`, PID `139407`) — **100% PROTECTED**
- **Date:** 2026-11-23T23:43:00+07:00

---

## 1. MỤC TIÊU & TỔNG QUAN ĐỢT RÀ SOÁT MÃ NGUỒN

Báo cáo này cung cấp bằng chứng tự kiểm toán (self-audit) chi tiết, đối chiếu từng dòng mã nguồn thực tế trong bộ 6 tệp thực thi với toàn bộ yêu cầu của Tech Lead tại văn bản `P40-DOC-08` và các phản biện vòng rà soát cuối:

### Nguyên tắc chỉ đạo:
> *"Một harness chuẩn không phải là một công cụ tạo ra các dòng PASS màu xanh, mà là một chốt chặn kỹ thuật tự động dừng và báo FAIL khi bất kỳ một giả định hay giới hạn an toàn nào bị vi phạm."*

---

## 2. MA TRẬN ĐỐI CHIẾU CHI TIẾT 10 ĐIỂM SỬA ĐỔI KỸ THUẬT

| Mã lỗi | Yêu cầu kỹ thuật theo Tech Lead | Thực thi trong Harness v2.3 FINAL | Vị trí mã nguồn thực tế | Kết quả kiểm toán |
| :---: | :--- | :--- | :--- | :---: |
| **P0-01** | **Unit đã tồn tại:** Không được cảnh báo rồi stop/reset unit đang active; phải dừng ngay với mã lỗi. | Quét cả 3 unit; nếu phát hiện unit đang `active` hoặc `loaded`, in thông báo `FATAL (P0-01)` và `exit 1` ngay lập tức. Tuyệt đối không gọi `stop` hay `reset-failed` trên pre-existing unit. | `linux_stage_40_1_cgroup_verify.sh`<br>`Lines 60-70` | **PASS (100% Compliant)** |
| **P0-02** | **Cgroup snapshot timing:** Ratifier không được truy cập cgroup sau khi Bot 2 dừng; phải đọc từ snapshot artifact. | Chụp `cpu.max` thành `cpu_max.txt` và `pids.max` thành `pids_max.txt` khi Bot 2 còn sống trong cgroup. `ratify_gates.py` đọc trực tiếp từ 2 snapshot này, không chạm cgroup sau khi Bot 2 dừng. | `linux_stage_40_1_cgroup_verify.sh` (`Lines 225-235`)<br>`ratify_gates.py` (`Lines 185-225`) | **PASS (100% Compliant)** |
| **P0-03** | **Cgroup memory control:** Bỏ toàn bộ fallback của cgroup resolver và memory.current; lỗi thì exit nonzero. | `resolve_cgroup_dir()` và `get_cgroup_memory_current()` trong `bot2_stress_workload.py` xóa bỏ $100\%$ fallback về `/sys/fs/cgroup` và VmRSS. Nếu không đọc được `memory.current` integer thì `sys.exit(1)` ngay. | `bot2_stress_workload.py`<br>`Lines 26-62` | **PASS (100% Compliant)** |
| **P0-04** | **Kiểm toán Zero Swap & Cấm default 0:** Ghi và xác minh `memory.swap.max == 0`; cấm dùng `.get(..., 0)` che giấu dữ liệu thiếu. | Chụp cả `memory.swap.max` và `memory.swap.current`. Hàm `require_field()` trong `ratify_gates.py` bắt buộc có đủ tất cả các trường. Xác minh `swap_max == 0` và `swap_cur == 0`. | `ratify_gates.py` (`Lines 20-25, 140-180`)<br>`linux_stage_40_1_cgroup_verify.sh` (`Lines 215-225`) | **PASS (100% Compliant)** |
| **P0-05** | **Xác thực systemd & Controller delegation:** Xác minh systemd manager active và transient unit thực sự dùng được controller. | `check_env.py` kiểm tra systemd manager active qua `systemctl`, đồng thời chạy probe transient unit `p40-stage40-1-probe` gán 3 controller (`MemoryAccounting`, `CPUAccounting`, `TasksAccounting`). Probe thất bại $\to$ dừng script. | `check_env.py`<br>`Lines 65-88` | **PASS (100% Compliant)** |
| **P1-01** | **Đối chiếu giao dịch SQLite:** Đối chiếu $1-1$ số row DB với commit count; báo cáo SQLite errors. | `bot1_workload.py` đếm `sqlite_errors`. `check_sqlite.py` và `ratify_gates.py` đối chiếu trực tiếp `SELECT COUNT(*) FROM bot1_state;` khớp chính xác với `commits_total`. Khác biệt $\to$ FAIL. | `bot1_workload.py` (`Lines 60-70`)<br>`check_sqlite.py` (`Lines 28-35`) | **PASS (100% Compliant)** |
| **P1-02** | **Cross-check toàn diện Raw vs Log:** Đối chiếu cả wake-up P99, commit P99 và heartbeat lateness. | `ratify_gates.py` đối chiếu chéo $100\%$ cả 3 chỉ số giữa raw JSON dataset và summary log marker `###BOT1_METRICS###`. Lệch $> 0.001\text{ ms}$ hoặc phát hiện SQLite error $\to$ FAIL. | `ratify_gates.py`<br>`Lines 260-295` | **PASS (100% Compliant)** |
| **P1-03** | **Xác minh chính xác danh sách Artifact:** Kiểm tra đủ danh sách artifact yêu cầu trước khi lập manifest. | Vòng lặp kiểm tra mảng `MANDATORY_ARTIFACTS` (đúng 17 file). Bất kỳ file nào thiếu hoặc $0\text{ bytes}$ thì script lập tức báo FATAL và dừng trước khi băm SHA-256. | `linux_stage_40_1_cgroup_verify.sh`<br>`Lines 290-330` | **PASS (100% Compliant)** |
| **P1-04** | **Trình tự lập báo cáo & Manifest:** Tạo report bắt buộc trước khi lập manifest; manifest là bước cuối. | `ratify_gates.py` tự động ghi `verification_report.txt` trong `OUTPUT_DIR`. Sau đó script mới đóng luồng log và sinh `manifest.sha256` ở bước cuối cùng. | `ratify_gates.py` (`Lines 320-350`)<br>`linux_stage_40_1_cgroup_verify.sh` (`Lines 280-335`) | **PASS (100% Compliant)** |
| **Shell** | **Loại bỏ `\|\| true` khi chờ workload:** Không che giấu exit status của workload chạy test. | Xóa bỏ toàn bộ `\|\| true` trong các lệnh `wait "${BOT1_STRESS_RUN_PID}"` và `wait "${BOT2_RUN_PID}"`. Chỉ cho phép `\|\| true` trong hàm cleanup trap khi hệ thống đã ở trạng thái dọn dẹp lỗi. | `linux_stage_40_1_cgroup_verify.sh`<br>`Lines 198, 238` | **PASS (100% Compliant)** |

---

## 3. DANH MỤC 18 BẰNG CHỨNG VẬT LÝ THEO CHUẨN SECTION 10

```text
/tmp/stage_40_1_artifacts/
├── environment.txt                # Kernel, systemd version, cgroup v2 mount check
├── cgroup_controllers.txt         # Controllers active in root cgroup
├── bot1_baseline.log              # Console log of Mock Bot 1 Baseline run
├── bot1_baseline.raw_samples.json # 2,000+ raw latency samples (Baseline)
├── bot2_stress.log                # Memory allocation & CPU stress log of Bot 2
├── memory_pre.txt                 # Pre-stress memory.events & swap limits (Bot 2 idle)
├── memory_post.txt                # Post-stress memory.events & swap limits (Bot 2 active)
├── memory_telemetry.log           # Time-series (1Hz) of memory.current and events
├── cpu_stat_pre.txt               # Pre-stress cpu.stat snapshot
├── cpu_stat_post.txt              # Post-stress cpu.stat snapshot (CFS delta)
├── cpu_max.txt                    # Snapshot of cpu.max captured while Bot 2 is alive
├── pids_max.txt                   # Snapshot of pids.max captured while Bot 2 is alive
├── pids_telemetry.log             # Time-series (1Hz) of pids.current and pids.peak
├── bot1_stress.log                # Console log of Mock Bot 1 Stress run
├── bot1_stress.raw_samples.json   # 2,000+ raw latency samples (Stress)
├── verification_report.txt        # Formal 5-Gate evaluation report (Created before manifest)
├── execution.log                  # Complete console transcript of harness execution
└── manifest.sha256                # Anti-tampering SHA-256 checksum table (Final step)
```

---

## 4. KẾT LUẬN & ĐỀ XUẤT PHÊ DUYỆT

1. **Tuân thủ kỹ thuật:** Toàn bộ 5 lỗi P0 và 4 lỗi P1 đã được giải quyết triệt để trên mã nguồn thực tế. Không còn fallback, không còn default 0, không che giấu lỗi bằng `|| true`, và cgroup snapshot được hoàn thiện trước khi tiến trình dừng.
2. **Kỷ luật an toàn tuyệt đối:** VPS Production (`instance-20261114-1044`, PID `139407`) được bảo vệ nghiêm ngặt $100\%$.
3. **Đề xuất:** Kính trình Tech Lead nghiệm thu mã nguồn (Code Acceptance) để sẵn sàng thực thi trên Linux Staging VM độc lập.

