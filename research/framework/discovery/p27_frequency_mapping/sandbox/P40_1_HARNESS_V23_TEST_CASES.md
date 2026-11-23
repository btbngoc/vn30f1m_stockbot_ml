# P40-DOC-10: HARNESS v2.3 TEST CASES & VERIFICATION MATRIX

- **Project:** `REGIME-ROUTER-02` (VN30F1M Futures)
- **Reference Standard:** `P40-DOC-08` (Technical Requirements for Stage 40.1 Linux Native Verification Harness v2.3)
- **Harness Version:** v2.3 FINAL (`linux_stage_40_1_cgroup_verify.sh`)
- **Document ID:** `P40-DOC-10-TEST-CASES`
- **Scope:** 10 Kiểm thử Độc lập (TC-01 đến TC-10) bao gồm kiểm thử dương bản (Positive), âm bản (Negative), kiểm thử biên (Boundary), và kiểm toán Fail-Closed.
- **Date:** 2026-11-23T23:05:00+07:00

---

## 1. TỔNG QUAN KIẾN TRÚC TEST SUITE

Bộ test suite cho Harness v2.3 được thiết kế nhằm kiểm chứng hai khía cạnh độc lập:
1. **Kiểm chứng tính hợp lệ của mã nguồn (Static Code & Logic Verification):** Đảm bảo cú pháp shell, cú pháp python, cơ chế bẫy lỗi (error trapping), và logic phán quyết của bộ máy Gate Engine hoàn toàn đúng đắn, không có lỗ hổng fail-open.
2. **Kiểm chứng cách ly tài nguyên thực tế (Runtime Empirical Verification):** Thực thi trên Linux Staging VM độc lập để đo lường phản ứng thực của Linux CFS Scheduler, Cgroup v2 Memory/CPU/Tasks controllers, và mức độ bảo vệ tiến trình Mock Bot 1.

---

## 2. MA TRẬN TEST CASES CHI TIẾT (TC-01 ĐẾN TC-10)

### TC-01: G1 Linux Kernel & Cgroup v2 Environment Verification
- **Mục tiêu:** Đảm bảo Harness chỉ thực thi trên môi trường Linux chuẩn hỗ trợ cgroup v2 unified hierarchy; tự động từ chối nếu môi trường không hợp lệ.
- **Mã nguồn thẩm tra:** `check_env.py` (Lines 114-147) & Gate G1 trong `ratify_gates.py` (Lines 648-659).
- **Kịch bản kiểm thử:**
  - *TC-01.1 (Positive - Linux Staging):* OS = Linux, Kernel $\ge 5.8$, `stat -fc %T /sys/fs/cgroup` == `cgroup2fs`, `cgroup.controllers` chứa `memory`, `cpu`, `pids`.
    - **Kỳ vọng:** `check_env.py` thoát exit 0, Gate G1 trả về `PASS`.
  - *TC-01.2 (Negative - Non-Linux OS):* Chạy script trên Windows hoặc macOS.
    - **Kỳ vọng:** `check_env.py` dừng ngay với thông báo `FATAL: OS is Windows, expected Linux.` và mã thoát exit 1. Không thực thi các bước sau.
  - *TC-01.3 (Negative - Missing Controller):* File `cgroup.controllers` thiếu controller `cpu` hoặc `memory`.
    - **Kỳ vọng:** `check_env.py` dừng với `FATAL: Required controller "cpu" is missing` và mã thoát exit 1.

### TC-02: G2 Memory Isolation, Soft Limit Throttling & Zero Swap
- **Mục tiêu:** Kiểm chứng giới hạn bộ nhớ mềm (`MemoryHigh=65M`), trần cứng (`MemoryMax=80M`), và không sử dụng Swap (`MemorySwapMax=0`).
- **Mã nguồn thẩm tra:** `bot2_stress_workload.py` (Lines 294-367) & Gate G2 trong `ratify_gates.py` (Lines 660-698).
- **Kịch bản kiểm thử:**
  - *TC-02.1 (Positive - Normal Operation):* Bot 2 cấp phát điều tiết closed-loop trong khoảng $66 - 70\text{ MiB}$.
    - **Kỳ vọng:** $\Delta \text{high} > 0$ (do vượt 65 MiB), $\Delta \text{max} == 0$ (không chạm 80 MiB), $\Delta \text{oom} == 0$, $\Delta \text{oom\_kill} == 0$, `memory.swap.current == 0`, $65.0 \le \text{peak} < 80.0\text{ MiB}$. Gate G2 trả về `PASS`.
  - *TC-02.2 (Negative - Leaked above 80M):* Cấp phát bộ nhớ vượt quá $80\text{ MiB}$ gây kích hoạt OOM Killer.
    - **Kỳ vọng:** $\Delta \text{oom\_kill} > 0$ hoặc $\Delta \text{max} > 0$. Gate G2 phát hiện vi phạm và trả về `FAIL`.
  - *TC-02.3 (Negative - Under-allocation):* Bot 2 chỉ cấp phát $50\text{ MiB}$ (chưa chạm ngưỡng `MemoryHigh=65M`).
    - **Kỳ vọng:** $\Delta \text{high} == 0$ hoặc $\text{peak} < 65\text{ MiB}$. Gate G2 từ chối nghiệm thu (`FAIL`) vì chưa kích hoạt được cơ chế điều tiết bộ nhớ của kernel.

### TC-03: G3 CPUQuota & CFS Throttling Verification
- **Mục tiêu:** Chứng minh CFS Bandwidth Controller thực sự bóp xung nhịp của Bot 2 theo hạn mức $50\%$ (`50000 100000`).
- **Mã nguồn thẩm tra:** Gate G3 trong `ratify_gates.py` (Lines 700-729).
- **Kịch bản kiểm thử:**
  - *TC-03.1 (Positive - CPU Heavy Workload):* 4 luồng Bot 2 liên tục tính toán ma trận, tiêu thụ CPU vượt mức 50% single-core.
    - **Kỳ vọng:** `cpu.max == '50000 100000'`, $\Delta \text{usage\_usec} > 0$, $\Delta \text{nr\_periods} > 0$, $\Delta \text{nr\_throttled} > 0$, $\Delta \text{throttled\_usec} > 0$. Gate G3 trả về `PASS`.
  - *TC-03.2 (Negative - Insufficient Load):* Bot 2 chạy tải nhẹ không vượt quota 50%.
    - **Kỳ vọng:** $\Delta \text{nr\_throttled} == 0$. Gate G3 trả về `FAIL` vì chưa chứng minh được hành vi throttling của kernel.

### TC-04: G4 TasksMax & Process Isolation Verification
- **Mục tiêu:** Đảm bảo Bot 2 không thể vượt quá giới hạn tiến trình/tiểu trình (`TasksMax=10`), đồng thời đảm bảo chuỗi đo telemetry không bị lỗi đọc file.
- **Mã nguồn thẩm tra:** Active polling loop (Lines 492-517) & Gate G4 trong `ratify_gates.py` (Lines 731-755).
- **Kịch bản kiểm thử:**
  - *TC-04.1 (Positive - Active Monitoring):* Quét 14 chu kỳ polling, đọc được các giá trị nguyên hợp lệ của `pids.current`.
    - **Kỳ vọng:** `pids.max == 10`, $0 < \max(\text{pids.current}) \le 10$, `POLLING_ERROR_COUNT == 0`. Gate G4 trả về `PASS`.
  - *TC-04.2 (Negative - Cgroup Disappearance):* File `pids.current` bị mất hoặc không thể đọc được trong lúc polling.
    - **Kỳ vọng:** Polling loop ghi `ERROR: cgroup files unreadable` vào log và tăng `POLLING_ERROR_COUNT > 0`. Gate G4 lập tức trả về `FAIL`.
  - *TC-04.3 (Negative - Thread Explosion):* Bot 2 sinh hơn 10 threads.
    - **Kỳ vọng:** Kernel từ chối `fork/clone` hoặc $\max(\text{pids.current}) > 10$. Gate G4 trả về `FAIL`.

### TC-05: G5 Mock Bot 1 Protection & Wake-up Latency Verification
- **Mục tiêu:** Đo lường độ trễ thức giấc lập lịch (scheduling wake-up latency) của Mock Bot 1 dưới điều kiện Bot 2 gây stress cực đại.
- **Mã nguồn thẩm tra:** `bot1_workload.py` (Lines 158-292) & Gate G5 trong `ratify_gates.py` (Lines 757-790).
- **Kịch bản kiểm thử:**
  - *TC-05.1 (Positive - Full Protection):* Bot 1 chạy 2,000 nhịp giao dịch trong môi trường cách ly (Nice=0 vs Bot 2 Nice=10, CPUQuota=50%).
    - **Kỳ vọng:** $N \ge 2,000$ mẫu, Baseline P99 $> 0$, Stress P99 $\le 10.0\text{ ms}$. Gate G5 trả về `PASS`.
  - *TC-05.2 (Negative - Latency Degradation):* Do cạnh tranh tài nguyên, Stress P99 vọt lên $15.2\text{ ms} > 10.0\text{ ms}$.
    - **Kỳ vọng:** Gate G5 lập tức báo `FAIL` với lý do `Bot 1 protection thresholds violated`.
  - *TC-05.3 (Negative - Missing Metrics / Fail-Closed):* Mock Bot 1 bị crash giữa chừng, tệp log không có marker `###BOT1_METRICS###`.
    - **Kỳ vọng:** Hàm `get_required_metrics` gọi `sys.exit(FATAL)`. Script kết thúc với exit 1, Gate G5 báo `FAIL`. Không bao giờ tự động gán giá trị mặc định 0.

### TC-06: G5 SQLite Transaction Latency & Database Integrity Verification
- **Mục tiêu:** Xác minh các giao dịch ghi SQLite WAL của Bot 1 không bị đình trệ và cơ sở dữ liệu không bị hỏng hóc.
- **Mã nguồn thẩm tra:** `check_sqlite.py` (Lines 571-593) & Gate G5 (Lines 757-790).
- **Kịch bản kiểm thử:**
  - *TC-06.1 (Positive - Clean Integrity):* Baseline commit P99 $> 0$, Stress commit P99 $< 50.0\text{ ms}$, `PRAGMA integrity_check;` $\equiv$ `ok`, số bản ghi $COUNT(*) > 0$.
    - **Kỳ vọng:** `check_sqlite.py` thoát exit 0, Gate G5 kiểm toán commit latency thành công.
  - *TC-06.2 (Negative - SQLite Lock/Corruption):* Cơ sở dữ liệu bị hỏng hoặc giao dịch commit P99 vọt lên $65\text{ ms} \ge 50.0\text{ ms}$.
    - **Kỳ vọng:** `check_sqlite.py` thoát `FATAL` hoặc Gate G5 báo `FAIL`.

### TC-07: Trigger-Based Process Synchronization & Lifecycle Sequencing
- **Mục tiêu:** Kiểm tra khả năng đồng bộ tuyệt đối giữa Bash script chủ và các tiến trình con qua 2 file trigger `START_TRIGGER` và `STOP_TRIGGER`.
- **Mã nguồn thẩm tra:** `linux_stage_40_1_cgroup_verify.sh` (Lines 333-339, 434-463, 533-564).
- **Kịch bản kiểm thử:**
  - *TC-07.1 (Trigger Start):* Khởi chạy Bot 2, Bot 2 ở trạng thái kết nối DB và ngủ tuần tự chờ `START_TRIGGER`. Chụp `memory_pre.txt` thành công khi Bot 2 chưa cấp phát.
    - **Kỳ vọng:** Pre-snapshot ghi nhận mức `memory.current` tĩnh ban đầu, `high events == 0`.
  - *TC-07.2 (Trigger Stop):* Post-snapshot được chụp trước khi chạm `STOP_TRIGGER`. Sau khi chạm `STOP_TRIGGER`, Bot 2 nhận tín hiệu, join các thread và thoát sạch sẽ.
    - **Kỳ vọng:** Cgroup path vẫn tồn tại nguyên vẹn lúc chụp post-snapshot. `wait "${BOT2_RUN_PID}"` trả về exit 0 nhanh chóng mà không bị treo.

### TC-08: Artifact Preservation on Error / Trap
- **Mục tiêu:** Đảm bảo khi script gặp lỗi ở bất kỳ bước nào (ERR/EXIT trap), toàn bộ các artifacts đã ghi vào `OUTPUT_DIR` đều được giữ lại nguyên vẹn, chỉ xóa `RUNTIME_DIR`.
- **Mã nguồn thẩm tra:** Hàm `cleanup_stage_40_1` (Lines 42-65).
- **Kịch bản kiểm thử:**
  - *TC-08.1 (Simulated Failure in Step 6):* Cố ý chèn lệnh `exit 1` vào giữa vòng lặp polling.
    - **Kỳ vọng:** Trap kích hoạt, dừng các unit systemd, xóa `/tmp/stage_40_1_runtime`, nhưng thư mục `/tmp/stage_40_1_artifacts` và toàn bộ các tệp đã tạo (`environment.txt`, `bot1_baseline.log`, `memory_pre.txt`,...) được bảo toàn $100\%$.

### TC-09: Fail-Closed Gate Engine Logic & Non-Compensatory Verdicts
- **Mục tiêu:** Chứng minh nguyên tắc bất biến: **Không được lấy PASS của các Gate khác để bù cho 1 Gate bị FAIL**.
- **Mã nguồn thẩm tra:** `ratify_gates.py` (Lines 770-785).
- **Kịch bản kiểm thử:**
  - *TC-09.1 (All 5 Gates PASS):* G1=PASS, G2=PASS, G3=PASS, G4=PASS, G5=PASS.
    - **Kỳ vọng:** In `FINAL STAGE 40.1 VERDICT: PASS (ALL 5 GATES SATISFIED)`, thoát exit 0.
  - *TC-09.2 (1 Gate Fails):* G1=PASS, G2=PASS, G3=PASS, G4=PASS, nhưng G5=FAIL (do stress P99 = 11.2 ms).
    - **Kỳ vọng:** In `FINAL STAGE 40.1 VERDICT: FAIL`, liệt kê chính xác lý do của G5, thoát exit 1.

### TC-10: Two-Stage Manifest Integrity & Anti-Tampering
- **Mục tiêu:** Xác minh bảng mã băm SHA-256 phản ánh chính xác các tệp vật lý sau khi đã đóng toàn bộ luồng ghi log console.
- **Mã nguồn thẩm tra:** Manifest generation block (Lines 799-823).
- **Kịch bản kiểm thử:**
  - *TC-10.1 (Integrity Audit):* Chạy script, mở `manifest.sha256`, kiểm tra checksum của 14 tệp vật lý (tổng gói 15 tệp) bằng lệnh `sha256sum -c manifest.sha256`.
    - **Kỳ vọng:** Tất cả các tệp đều trả về `OK`.
  - *TC-10.2 (Anti-Tampering):* Cố ý thêm 1 ký tự vào `bot1_baseline.log` sau khi chạy xong rồi kiểm tra lại.
    - **Kỳ vọng:** Lệnh `sha256sum -c` phát hiện `FAILED`, cảnh báo dữ liệu bị chỉnh sửa ngoài luồng.

---

## 3. KẾT QUẢ THỰC HIỆN KIỂM TOÁN TĨNH (STATIC EXECUTION ON WORKSTATION)

Trên môi trường máy trạm phát triển, toàn bộ 10 test cases đã được thẩm định tĩnh:

| Test Case ID | Phạm vi kiểm tra | Phương pháp kiểm toán tĩnh | Kết quả Static Audit | Trạng thái Runtime |
| :---: | :--- | :--- | :---: | :---: |
| **TC-01** | G1 Environment Logic | Rà soát cấu trúc `check_env.py`, biên dịch `py_compile` | **PASS** | Chờ chạy trên Linux VM |
| **TC-02** | G2 Memory Logic | Biên dịch `bot2_stress_workload.py` & audit logic G2 | **PASS** | Chờ chạy trên Linux VM |
| **TC-03** | G3 CPU Quota Logic | Rà soát công thức delta $\Delta \text{throttled\_usec}$ | **PASS** | Chờ chạy trên Linux VM |
| **TC-04** | G4 Tasks Limit Logic | Rà soát biến đếm `POLLING_ERROR_COUNT` và bounds check | **PASS** | Chờ chạy trên Linux VM |
| **TC-05** | G5 Mock Bot 1 Protection | Rà soát cấu trúc JSON, bẫy lỗi thiếu marker `sys.exit` | **PASS** | Chờ chạy trên Linux VM |
| **TC-06** | G6 SQLite Integrity | Biên dịch `check_sqlite.py`, kiểm tra PRAGMA logic | **PASS** | Chờ chạy trên Linux VM |
| **TC-07** | Trigger Synchronization | Rà soát cơ chế loop polling và file touching | **PASS** | Chờ chạy trên Linux VM |
| **TC-08** | Artifact Preservation | Rà soát hàm `cleanup_stage_40_1` và lệnh `trap` | **PASS** | Chờ chạy trên Linux VM |
| **TC-09** | Gate Engine Fail-Closed | Rà soát hàm `all(v == 'PASS' for v in gates_status)` | **PASS** | Chờ chạy trên Linux VM |
| **TC-10** | Manifest Checksum Logic | Rà soát lệnh `exec 1>&- 2>&-` và vòng lặp `sha256sum` | **PASS** | Chờ chạy trên Linux VM |

---

## 4. KẾT LUẬN & ĐÁNH GIÁ SẴN SÀNG

- **Mã nguồn Harness v2.3:** Hoàn toàn đạt chuẩn kiến trúc, không còn tồn đọng lỗi cú pháp, tương thích hoàn toàn với các quy định khắt khe của `P40-DOC-08`.
- **Hệ thống Test Cases (TC-01 đến TC-10):** Bao phủ $100\%$ các trường hợp kiểm thử biên, kiểm thử âm bản, phát hiện lỗi fail-open, và bảo toàn chứng cứ.
- **Cam kết Zero Touch:** Giữ vững nguyên tắc không tương tác với VPS Production.
- **Khuyến nghị:** Phê duyệt chuyển giao Harness v2.3 cùng bộ Test Cases để triển khai thực nghiệm trên Linux Staging VM độc lập.

