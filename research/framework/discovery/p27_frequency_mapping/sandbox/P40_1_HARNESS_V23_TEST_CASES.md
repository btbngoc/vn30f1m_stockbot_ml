# P40-DOC-10: HARNESS v2.3 FINAL TEST CASES & VERIFICATION MATRIX

- **Project:** `REGIME-ROUTER-02` (VN30F1M Futures)
- **Reference Standard:** `P40-DOC-08` (Technical Requirements for Stage 40.1 Linux Native Verification Harness v2.3)
- **Harness Version:** v2.3 FINAL (`linux_stage_40_1_cgroup_verify.sh` & 5 Modular Python Scripts)
- **Git Branch:** `feature/stage-40-1-harness-v23-final`
- **Document ID:** `P40-DOC-10-TEST-CASES`
- **Scope:** 10 Kiểm thử Độc lập (TC-01 đến TC-10) bao gồm kiểm thử dương bản (Positive), âm bản (Negative), kiểm thử biên (Boundary), và kiểm toán Fail-Closed.
- **Date:** 2026-11-23T23:44:00+07:00

---

## 1. TỔNG QUAN KIẾN TRÚC TEST SUITE

Bộ test suite cho Harness v2.3 FINAL được thiết kế nhằm kiểm chứng hai khía cạnh độc lập:
1. **Kiểm chứng tính hợp lệ của mã nguồn (Static Code & Logic Verification):** Đảm bảo cú pháp shell, cú pháp python, cơ chế bẫy lỗi (error trapping), bẫy lỗi unit pre-existing, zero-fallback, và logic phán quyết của bộ máy Gate Engine hoàn toàn đúng đắn, không có lỗ hổng fail-open.
2. **Kiểm chứng cách ly tài nguyên thực tế (Runtime Empirical Verification):** Thực thi trên Linux Staging VM độc lập để đo lường phản ứng thực của Linux CFS Scheduler, Cgroup v2 Memory/CPU/Tasks controllers, và mức độ bảo vệ tiến trình Mock Bot 1.

---

## 2. MA TRẬN TEST CASES CHI TIẾT (TC-01 ĐẾN TC-10)

### TC-01: G1 Linux Kernel, systemd Manager & Transient Controller Delegation (P0-05)
- **Mục tiêu:** Đảm bảo Harness chỉ thực thi trên môi trường Linux chuẩn hỗ trợ cgroup v2 unified hierarchy, systemd manager đang active, và transient unit có thể thực sự gán controller; tự động từ chối nếu môi trường không hợp lệ.
- **Mã nguồn thẩm tra:** `check_env.py` & Gate G1 trong `ratify_gates.py`.
- **Kịch bản kiểm thử:**
  - *TC-01.1 (Positive - Linux Staging):* OS = Linux, Kernel $\ge 5.8$, `cgroup2fs`, `cgroup.controllers` chứa `memory`, `cpu`, `pids`, systemd manager active, transient probe `p40-stage40-1-probe` gán 3 controller thành công.
    - **Kỳ vọng:** `check_env.py` thoát exit 0, Gate G1 trả về `PASS`.
  - *TC-01.2 (Negative - Non-Linux OS):* Chạy script trên Windows hoặc macOS.
    - **Kỳ vọng:** `check_env.py` dừng ngay với `FATAL: Host OS is Windows, expected Linux.` và mã thoát exit 1.
  - *TC-01.3 (Negative - Controller Delegation Failure):* Transient unit không gán được `MemoryAccounting`.
    - **Kỳ vọng:** Probe unit thất bại, `check_env.py` thoát `FATAL` ngay lập tức.

### TC-02: G2 Memory Isolation, Soft Limit Throttling & Zero Swap (P0-03, P0-04)
- **Mục tiêu:** Kiểm chứng giới hạn bộ nhớ mềm (`MemoryHigh=65M`), trần cứng (`MemoryMax=80M`), và không sử dụng Swap (`MemorySwapMax=0`). Bỏ toàn bộ fallback của cgroup resolver.
- **Mã nguồn thẩm tra:** `bot2_stress_workload.py` & Gate G2 trong `ratify_gates.py`.
- **Kịch bản kiểm thử:**
  - *TC-02.1 (Positive - Normal Operation):* Bot 2 điều tiết bộ nhớ dựa trực tiếp trên `memory.current` cgroup kernel (giữ trong khoảng $66.5 - 69.5\text{ MiB}$).
    - **Kỳ vọng:** $\Delta \text{high} > 0$, $\Delta \text{max} == 0$, $\Delta \text{oom} == 0$, $\Delta \text{oom\_kill} == 0$, `memory.swap.max == 0`, `memory.swap.current == 0`, $65.0 \le \text{peak} < 80.0\text{ MiB}$. Gate G2 trả về `PASS`.
  - *TC-02.2 (Negative - Cgroup Unreadable / P0-03):* Bot 2 không đọc được `memory.current` từ cgroup.
    - **Kỳ vọng:** Bot 2 thoát `sys.exit(1)` ngay lập tức, không fallback sang VmRSS, không fallback về 0.
  - *TC-02.3 (Negative - Missing Swap Field / P0-04):* File snapshot thiếu trường `memory.swap.max`.
    - **Kỳ vọng:** Hàm `require_field()` phát hiện thiếu trường, script thoát `FATAL` ngay lập tức, không gán default 0.

### TC-03: G3 CPUQuota & CFS Throttling (P0-02 Snapshot Isolation)
- **Mục tiêu:** Chứng minh CFS Bandwidth Controller thực sự bóp xung nhịp của Bot 2 theo hạn mức $50\%$ (`50000 100000`). Ratifier đọc trực tiếp từ `cpu_max.txt`, không chạm cgroup sau khi Bot 2 dừng.
- **Mã nguồn thẩm tra:** `cpu_max.txt`, `cpu_stat_post.txt`, & Gate G3 trong `ratify_gates.py`.
- **Kịch bản kiểm thử:**
  - *TC-03.1 (Positive - CPU Heavy Workload):* 4 luồng Bot 2 liên tục tính toán ma trận, tiêu thụ CPU vượt mức 50% single-core.
    - **Kỳ vọng:** `cpu_max.txt` ghi nhận `'50000 100000'`, $\Delta \text{usage\_usec} > 0$, $\Delta \text{nr\_periods} > 0$, $\Delta \text{nr\_throttled} > 0$, $\Delta \text{throttled\_usec} > 0$. Gate G3 trả về `PASS`.
  - *TC-03.2 (Negative - Missing Snapshot / P0-02):* Tệp `cpu_max.txt` bị thiếu.
    - **Kỳ vọng:** Ratifier thoát `FATAL (P0-02)` ngay lập tức, không cố mở `/sys/fs/cgroup`.

### TC-04: G4 TasksMax & Process Isolation (P0-02 Snapshot Isolation)
- **Mục tiêu:** Đảm bảo Bot 2 không thể vượt quá giới hạn tiến trình/tiểu trình (`TasksMax=10`). Ratifier đọc từ `pids_max.txt`.
- **Mã nguồn thẩm tra:** Active polling loop & Gate G4 trong `ratify_gates.py`.
- **Kịch bản kiểm thử:**
  - *TC-04.1 (Positive - Active Monitoring):* Quét 14 chu kỳ polling, đọc được các giá trị nguyên hợp lệ của `pids.current`.
    - **Kỳ vọng:** `pids_max.txt` == 10, $0 < \max(\text{pids.current}) \le 10$, `POLLING_ERROR_COUNT == 0`. Gate G4 trả về `PASS`.
  - *TC-04.2 (Negative - Cgroup Disappearance during polling):* File `pids.current` bị mất trong lúc polling.
    - **Kỳ vọng:** Polling loop ghi `ERROR: cgroup files unreadable` và tăng `POLLING_ERROR_COUNT > 0`. Gate G4 trả về `FAIL`.

### TC-05: G5 Mock Bot 1 Protection & Full Cross-Check (P1-02)
- **Mục tiêu:** Đo lường độ trễ scheduling wake-up latency của Mock Bot 1 và đối chiếu $100\%$ giữa raw JSON dataset và log console.
- **Mã nguồn thẩm tra:** `bot1_workload.py` & Gate G5 trong `ratify_gates.py`.
- **Kịch bản kiểm thử:**
  - *TC-05.1 (Positive - Full Protection & Match):* Bot 1 chạy 2,000 nhịp giao dịch trong môi trường cách ly (Nice=0 vs Bot 2 Nice=10, CPUQuota=50%).
    - **Kỳ vọng:** $N \ge 2,000$ mẫu, Baseline P99 $> 0$, Stress P99 $\le 10.0\text{ ms}$, raw P99 khớp với log marker within $0.001\text{ ms}$. Gate G5 trả về `PASS`.
  - *TC-05.2 (Negative - Raw vs Log Mismatch / P1-02):* Giá trị P99 trong log bị chỉnh sửa khác raw JSON dataset $> 0.001\text{ ms}$.
    - **Kỳ vọng:** Ratifier phát hiện sai lệch dữ liệu và đánh rớt Gate G5 (`FAIL`).

### TC-06: G5 SQLite Transaction Latency & Row Reconciliation (P1-01)
- **Mục tiêu:** Xác minh tính toàn vẹn SQLite WAL và đối chiếu $1-1$ số dòng trong cơ sở dữ liệu với số commit thành công.
- **Mã nguồn thẩm tra:** `check_sqlite.py` & Gate G5 trong `ratify_gates.py`.
- **Kịch bản kiểm thử:**
  - *TC-06.1 (Positive - Clean Reconciliation):* `PRAGMA integrity_check` $\equiv$ `ok`, số dòng $COUNT(*) == \text{commits\_total}$, `sqlite_errors == 0`, Stress commit P99 $< 50.0\text{ ms}$.
    - **Kỳ vọng:** `check_sqlite.py` thoát exit 0, Gate G5 trả về `PASS`.
  - *TC-06.2 (Negative - Row Count Mismatch / P1-01):* Số dòng trong database không khớp với số commit ghi nhận.
    - **Kỳ vọng:** `check_sqlite.py` và `ratify_gates.py` lập tức báo `FATAL (P1-01)` và thoát với exit 1.

### TC-07: Pre-Existing Unit Safety Enforcement (P0-01)
- **Mục tiêu:** Đảm bảo Harness tuyệt đối không chạm, stop hoặc reset-failed các unit đang tồn tại trước bài test.
- **Mã nguồn thẩm tra:** Pre-execution check trong `linux_stage_40_1_cgroup_verify.sh`.
- **Kịch bản kiểm thử:**
  - *TC-07.1 (Negative - Pre-existing Unit):* Tạo một service trùng tên `p40-stage40-1-bot2-stress.service` đang active hoặc loaded trước khi chạy script.
    - **Kỳ vọng:** Script phát hiện unit tồn tại, in cảnh báo `FATAL (P0-01)`, và dừng ngay lập tức. Unit pre-existing không bị stop hay reset.

### TC-08: Artifact Preservation on Error / Trap
- **Mục tiêu:** Đảm bảo khi script gặp lỗi ở bất kỳ bước nào (ERR/EXIT trap), toàn bộ các artifacts đã ghi vào `OUTPUT_DIR` đều được giữ lại nguyên vẹn, chỉ xóa `RUNTIME_DIR`.
- **Mã nguồn thẩm tra:** Hàm `cleanup_stage_40_1` trong `linux_stage_40_1_cgroup_verify.sh`.
- **Kịch bản kiểm thử:**
  - *TC-08.1 (Simulated Failure in Step 6):* Cố ý ngắt tiến trình giữa chừng.
    - **Kỳ vọng:** Trap kích hoạt, dừng các unit do phiên test sinh ra, xóa `/tmp/stage_40_1_runtime`, nhưng thư mục `/tmp/stage_40_1_artifacts` và toàn bộ các tệp đã tạo được bảo toàn $100\%$.

### TC-09: Fail-Closed Gate Engine Logic & Report Generation (P1-04)
- **Mục tiêu:** Chứng minh `verification_report.txt` được tạo trước khi lập manifest, và bất kỳ Gate nào thất bại thì tổng thể là FAIL.
- **Mã nguồn thẩm tra:** `ratify_gates.py`.
- **Kịch bản kiểm thử:**
  - *TC-09.1 (Report Creation):* Chạy `ratify_gates.py`.
    - **Kỳ vọng:** `verification_report.txt` được ghi thành công vào `OUTPUT_DIR` với đầy đủ số liệu 5 Gate trước khi script kết thúc.
  - *TC-09.2 (1 Gate Fails):* G1=PASS, G2=PASS, G3=PASS, G4=PASS, nhưng G5=FAIL.
    - **Kỳ vọng:** In `FINAL STAGE 40.1 VERDICT: FAIL`, thoát exit 1. Không bù trừ.

### TC-10: Two-Stage Manifest Integrity & Mandatory Artifact Enforcement (P1-03)
- **Mục tiêu:** Xác minh danh mục đúng 17 file bắt buộc tồn tại và non-empty trước khi băm SHA-256 vào `manifest.sha256`.
- **Mã nguồn thẩm tra:** Manifest generation block trong `linux_stage_40_1_cgroup_verify.sh`.
- **Kịch bản kiểm thử:**
  - *TC-10.1 (Integrity Audit):* Chạy script, mở `manifest.sha256`, kiểm tra checksum của 17 tệp bằng lệnh `sha256sum -c manifest.sha256`.
    - **Kỳ vọng:** Tất cả 17 tệp đều trả về `OK`.
  - *TC-10.2 (Negative - Missing Mandatory Artifact / P1-03):* Cố tình xóa file `cpu_max.txt` trước khi chạy khối manifest.
    - **Kỳ vọng:** Vòng lặp phát hiện thiếu artifact bắt buộc, báo `FATAL (P1-03)`, và dừng ngay lập tức. Không tạo manifest không hoàn chỉnh.

---

## 3. KẾT QUẢ THỰC HIỆN KIỂM TOÁN TĨNH (STATIC AUDIT ON WORKSTATION)

| Test Case ID | Phạm vi kiểm tra | Phương pháp kiểm toán tĩnh | Kết quả Static Audit | Trạng thái Runtime |
| :---: | :--- | :--- | :---: | :---: |
| **TC-01** | G1 & systemd Probe | Rà soát `check_env.py` (P0-05) | **PASS** | Chờ chạy trên Linux VM |
| **TC-02** | G2 Memory & Zero Swap | Rà soát zero-fallback (P0-03) & `require_field` (P0-04) | **PASS** | Chờ chạy trên Linux VM |
| **TC-03** | G3 CPU & Snapshot Read | Rà soát đọc `cpu_max.txt` (P0-02) | **PASS** | Chờ chạy trên Linux VM |
| **TC-04** | G4 Tasks & Snapshot Read | Rà soát đọc `pids_max.txt` (P0-02) | **PASS** | Chờ chạy trên Linux VM |
| **TC-05** | G5 Protection & Cross-Check | Rà soát đối chiếu chéo raw JSON vs log (P1-02) | **PASS** | Chờ chạy trên Linux VM |
| **TC-06** | G6 SQLite Row Reconciliation | Rà soát đối chiếu $1-1$ row count vs commit count (P1-01) | **PASS** | Chờ chạy trên Linux VM |
| **TC-07** | Pre-existing Unit Safety | Rà soát kiểm tra trạng thái active/loaded (P0-01) | **PASS** | Chờ chạy trên Linux VM |
| **TC-08** | Artifact Preservation | Rà soát hàm `cleanup_stage_40_1` và lệnh `trap` | **PASS** | Chờ chạy trên Linux VM |
| **TC-09** | Report Generation Pre-Manifest | Rà soát xuất `verification_report.txt` (P1-04) | **PASS** | Chờ chạy trên Linux VM |
| **TC-10** | Manifest Mandatory Verification | Rà soát mảng `MANDATORY_ARTIFACTS` 17 file (P1-03) | **PASS** | Chờ chạy trên Linux VM |

---

## 4. KẾT LUẬN & ĐÁNH GIÁ SẴN SÀNG

- Toàn bộ 5 lỗi P0 và 4 lỗi P1 đã được giải quyết triệt để trên mã nguồn thực tế.
- Bộ Test Cases (TC-01 đến TC-10) phản ánh $100\%$ các chốt chặn fail-closed được Tech Lead chỉ thị.
- Kính trình Tech Lead nghiệm thu mã nguồn (Code Acceptance).

