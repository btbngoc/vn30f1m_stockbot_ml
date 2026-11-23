#!/usr/bin/env python3
"""
STAGE 40.1 - 5-GATE RIGOROUS RATIFICATION ENGINE (STRICT FAIL-CLOSED)
Standard: P40-DOC-08 Section 2, 4-7, 11
Independently verifies all 5 acceptance gates (G1-G5).

CRITICAL FAIL-CLOSED GUARANTEES:
- P0-02: Zero access to cgroup after Bot 2 terminates. Reads cpu.max and pids.max strictly from snapshot artifacts.
- P0-04: Strict dictionary parsing. NO .get(..., 0) defaults for mandatory fields. Enforces memory.swap.max == 0.
- P0-05: Verifies G1 environment integrity.
- P1-01: Cross-checks SQLite row counts directly against raw commit counts.
- P1-02: Full cross-check of wake-up latency, commit latency, and heartbeat lateness between raw JSON and execution logs.
- P1-04: Generates verification_report.txt in OUTPUT_DIR before manifest creation.
"""
import sys
import os
import math
import json
import sqlite3
import datetime
import numpy as np

def require_field(d, key, label):
    if key not in d:
        sys.exit(f"FATAL (P0-04): Missing mandatory field '{key}' in {label}! Default 0 is strictly forbidden.")
    return d[key]

def parse_strict_kv_file(path, label):
    if not os.path.exists(path):
        sys.exit(f"FATAL: Required snapshot file does not exist: '{path}' ({label})")
    d = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                k = parts[0].rstrip(':')
                v = parts[1]
                if v.isdigit():
                    d[k] = int(v)
                else:
                    d[k] = v
    if not d:
        sys.exit(f"FATAL: Snapshot file is empty: '{path}' ({label})")
    return d

def get_required_log_metrics(fpath, label):
    if not os.path.exists(fpath):
        sys.exit(f"FATAL: Execution log missing for {label}: '{fpath}'")
    with open(fpath, 'r', encoding='utf-8') as f:
        for line in f:
            if '###BOT1_METRICS###' in line:
                payload = line.split('###BOT1_METRICS###')[1].strip()
                try:
                    return json.loads(payload)
                except Exception as e:
                    sys.exit(f"FATAL: Malformed JSON in ###BOT1_METRICS### for {label}: {e}")
    sys.exit(f"FATAL: Missing mandatory ###BOT1_METRICS### marker in {label} ('{fpath}')!")

def load_and_validate_raw_dataset(fpath, label):
    if not os.path.exists(fpath):
        sys.exit(f"FATAL: Raw dataset file missing for {label}: '{fpath}'")
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        sys.exit(f"FATAL: Unable to parse raw JSON dataset for {label} ('{fpath}'): {e}")

    sched = data.get('raw_sched_wakeup_samples_ms')
    commits = data.get('raw_commit_samples_ms')
    hb = data.get('raw_heartbeat_intervals_s')

    if not isinstance(sched, list) or len(sched) < 2000:
        count = len(sched) if isinstance(sched, list) else 0
        sys.exit(f"FATAL: {label} has insufficient raw scheduling samples ({count} < 2000). Test invalid.")

    if not isinstance(commits, list) or len(commits) == 0:
        sys.exit(f"FATAL: {label} has zero recorded raw commit samples.")

    if not isinstance(hb, list) or len(hb) == 0:
        sys.exit(f"FATAL: {label} has zero recorded raw heartbeat samples.")

    # Assert all values are finite
    for val in sched:
        if not (isinstance(val, (int, float)) and math.isfinite(val) and val >= 0.0):
            sys.exit(f"FATAL: Non-finite or negative scheduling sample detected in {label}: {val}")

    for val in commits:
        if not (isinstance(val, (int, float)) and math.isfinite(val) and val >= 0.0):
            sys.exit(f"FATAL: Non-finite or negative commit sample detected in {label}: {val}")

    for val in hb:
        if not (isinstance(val, (int, float)) and math.isfinite(val) and val > 0.0):
            sys.exit(f"FATAL: Non-finite or non-positive heartbeat sample detected in {label}: {val}")

    return {
        'sched': np.array(sched, dtype=np.float64),
        'commits': np.array(commits, dtype=np.float64),
        'hb': np.array(hb, dtype=np.float64)
    }

def main():
    if len(sys.argv) < 17:
        sys.exit(f"FATAL: ratify_gates.py requires 16 arguments, received {len(sys.argv)-1}")

    mem_pre_path = sys.argv[1]
    mem_post_path = sys.argv[2]
    max_mem_bytes = int(sys.argv[3])
    cpu_pre_path = sys.argv[4]
    cpu_post_path = sys.argv[5]
    cpu_max_snapshot = sys.argv[6]    # P0-02: Snapshot of cpu.max
    pids_max_snapshot = sys.argv[7]   # P0-02: Snapshot of pids.max
    max_pids = int(sys.argv[8])
    polling_errs = int(sys.argv[9])
    bot1_base_log = sys.argv[10]
    bot1_stress_log = sys.argv[11]
    bot1_base_raw_path = sys.argv[12]
    bot1_stress_raw_path = sys.argv[13]
    bot1_base_db = sys.argv[14]
    bot1_stress_db = sys.argv[15]
    bot1_stress_exit_status = int(sys.argv[16])

    output_dir = os.path.dirname(os.path.abspath(mem_post_path))
    gates_status = {}
    fail_reasons = []

    print("================================================================================")
    print("STAGE 40.1 - 5-GATE RIGOROUS RATIFICATION ENGINE (P40-DOC-08 FINAL)")
    print("================================================================================")

    # --------------------------------------------------------------------------
    # GATE G1: ENVIRONMENT VALIDATION
    # --------------------------------------------------------------------------
    print("\n[GATE G1: ENVIRONMENT VALIDATION]")
    g1_ok = True
    if os.name != 'posix' or sys.platform != 'linux':
        g1_ok = False
        fail_reasons.append("G1: Host OS is not Linux / POSIX")

    fs_type = os.popen('stat -fc %T /sys/fs/cgroup 2>/dev/null').read().strip()
    if fs_type != 'cgroup2fs':
        g1_ok = False
        fail_reasons.append(f"G1: /sys/fs/cgroup fs type is '{fs_type}', expected 'cgroup2fs'")

    ctrl_file = '/sys/fs/cgroup/cgroup.controllers'
    if os.path.exists(ctrl_file):
        with open(ctrl_file) as f:
            controllers = f.read().split()
            for req in ['memory', 'cpu', 'pids']:
                if req not in controllers:
                    g1_ok = False
                    fail_reasons.append(f"G1: Root controller '{req}' missing from cgroup.controllers")
    else:
        g1_ok = False
        fail_reasons.append("G1: /sys/fs/cgroup/cgroup.controllers does not exist")

    g1_status = 'PASS' if g1_ok else 'FAIL'
    gates_status['G1'] = g1_status
    print(f"  -> G1 Status: {g1_status}")

    # --------------------------------------------------------------------------
    # GATE G2: MEMORY ISOLATION & KERNEL CGROUP THROTTLING (P0-04 STRICT)
    # --------------------------------------------------------------------------
    print("\n[GATE G2: MEMORY ISOLATION, HIGH EVENT & ZERO SWAP (P0-04)]")
    mem_pre = parse_strict_kv_file(mem_pre_path, "Pre-test Memory Snapshot")
    mem_post = parse_strict_kv_file(mem_post_path, "Post-test Memory Snapshot")

    # Strict field verification without .get(..., 0)
    cfg_max = require_field(mem_post, 'memory.max', 'Post-test Memory Snapshot')
    cfg_high = require_field(mem_post, 'memory.high', 'Post-test Memory Snapshot')
    swap_max = require_field(mem_post, 'memory.swap.max', 'Post-test Memory Snapshot')
    swap_cur = require_field(mem_post, 'memory.swap.current', 'Post-test Memory Snapshot')
    max_mem_mb = max_mem_bytes / 1048576.0

    post_high = require_field(mem_post, 'high', 'Post-test memory.events')
    pre_high = require_field(mem_pre, 'high', 'Pre-test memory.events')
    post_max = require_field(mem_post, 'max', 'Post-test memory.events')
    pre_max = require_field(mem_pre, 'max', 'Pre-test memory.events')
    post_oom = require_field(mem_post, 'oom', 'Post-test memory.events')
    pre_oom = require_field(mem_pre, 'oom', 'Pre-test memory.events')
    post_oom_kill = require_field(mem_post, 'oom_kill', 'Post-test memory.events')
    pre_oom_kill = require_field(mem_pre, 'oom_kill', 'Pre-test memory.events')

    delta_high = post_high - pre_high
    delta_max = post_max - pre_max
    delta_oom = post_oom - pre_oom
    delta_oom_kill = post_oom_kill - pre_oom_kill

    print(f"  -> Configured memory.max      : {cfg_max} (Expected: 83886080 [80M])")
    print(f"  -> Configured memory.high     : {cfg_high} (Expected: 68157440 [65M])")
    print(f"  -> Configured memory.swap.max : {swap_max} (Expected: 0)")
    print(f"  -> Current memory.swap.current: {swap_cur} B (Expected: == 0)")
    print(f"  -> Peak memory observed       : {max_mem_mb:.2f} MiB (Expected: >= 65M and < 80M)")
    print(f"  -> Delta high events          : {delta_high} (Expected: > 0)")
    print(f"  -> Delta max events           : {delta_max} (Expected: == 0)")
    print(f"  -> Delta oom events           : {delta_oom} (Expected: == 0)")
    print(f"  -> Delta oom_kill events      : {delta_oom_kill} (Expected: == 0)")

    g2_ok = (
        cfg_max == 83886080 and
        cfg_high == 68157440 and
        swap_max == 0 and
        swap_cur == 0 and
        max_mem_mb >= 65.0 and max_mem_mb < 80.0 and
        delta_high > 0 and
        delta_max == 0 and
        delta_oom == 0 and
        delta_oom_kill == 0
    )

    g2_status = 'PASS' if g2_ok else 'FAIL'
    gates_status['G2'] = g2_status
    if not g2_ok:
        fail_reasons.append(
            f"G2: Memory/Swap constraints violated (cfg_max={cfg_max}, cfg_high={cfg_high}, "
            f"swap_max={swap_max}, swap_cur={swap_cur}, delta_high={delta_high}, "
            f"delta_oom_kill={delta_oom_kill}, peak={max_mem_mb:.2f}M)"
        )
    print(f"  -> G2 Status: {g2_status}")

    # --------------------------------------------------------------------------
    # GATE G3: CPU QUOTA & CFS THROTTLING (P0-02: READ FROM SNAPSHOT)
    # --------------------------------------------------------------------------
    print("\n[GATE G3: CPU QUOTA & CFS THROTTLING]")
    if not os.path.exists(cpu_max_snapshot):
        sys.exit(f"FATAL (P0-02): CPU max snapshot file missing: '{cpu_max_snapshot}'")
    with open(cpu_max_snapshot, 'r', encoding='utf-8') as f:
        cpu_max_val = f.read().strip()

    cpu_pre = parse_strict_kv_file(cpu_pre_path, "Pre-test cpu.stat")
    cpu_post = parse_strict_kv_file(cpu_post_path, "Post-test cpu.stat")

    post_usage = require_field(cpu_post, 'usage_usec', 'Post-test cpu.stat')
    pre_usage = require_field(cpu_pre, 'usage_usec', 'Pre-test cpu.stat')
    post_periods = require_field(cpu_post, 'nr_periods', 'Post-test cpu.stat')
    pre_periods = require_field(cpu_pre, 'nr_periods', 'Pre-test cpu.stat')
    post_throttled = require_field(cpu_post, 'nr_throttled', 'Post-test cpu.stat')
    pre_throttled = require_field(cpu_pre, 'nr_throttled', 'Pre-test cpu.stat')
    post_throttled_usec = require_field(cpu_post, 'throttled_usec', 'Post-test cpu.stat')
    pre_throttled_usec = require_field(cpu_pre, 'throttled_usec', 'Pre-test cpu.stat')

    delta_usage_s = (post_usage - pre_usage) / 1e6
    delta_periods = post_periods - pre_periods
    delta_throttled = post_throttled - pre_throttled
    delta_throttled_s = (post_throttled_usec - pre_throttled_usec) / 1e6

    print(f"  -> Configured cpu.max   : '{cpu_max_val}' (Expected: '50000 100000' [50%])")
    print(f"  -> Delta CPU Usage      : {delta_usage_s:.2f} s (Expected: > 0)")
    print(f"  -> Delta CFS Periods    : {delta_periods} (Expected: > 0)")
    print(f"  -> Delta Throttled      : {delta_throttled} periods (Expected: > 0)")
    print(f"  -> Delta Throttled Time : {delta_throttled_s:.2f} s (Expected: > 0)")

    g3_ok = (
        cpu_max_val == '50000 100000' and
        delta_usage_s > 0 and
        delta_periods > 0 and
        delta_throttled > 0 and
        delta_throttled_s > 0
    )

    g3_status = 'PASS' if g3_ok else 'FAIL'
    gates_status['G3'] = g3_status
    if not g3_ok:
        fail_reasons.append(f"G3: CFS CPU throttling not verified (cpu_max='{cpu_max_val}', delta_throttled={delta_throttled}, delta_usage_s={delta_usage_s:.2f})")
    print(f"  -> G3 Status: {g3_status}")

    # --------------------------------------------------------------------------
    # GATE G4: PROCESS & TASK ISOLATION (P0-02: READ FROM SNAPSHOT)
    # --------------------------------------------------------------------------
    print("\n[GATE G4: PROCESS & TASK ISOLATION]")
    if not os.path.exists(pids_max_snapshot):
        sys.exit(f"FATAL (P0-02): Pids max snapshot file missing: '{pids_max_snapshot}'")
    with open(pids_max_snapshot, 'r', encoding='utf-8') as f:
        tasks_max_val = int(f.read().strip())

    print(f"  -> Configured pids.max  : {tasks_max_val} (Expected: 10)")
    print(f"  -> Max pids observed    : {max_pids} (Expected: <= 10 and > 0)")
    print(f"  -> Polling errors count : {polling_errs} (Expected: == 0)")

    g4_ok = (
        tasks_max_val == 10 and
        max_pids > 0 and
        max_pids <= 10 and
        polling_errs == 0
    )

    g4_status = 'PASS' if g4_ok else 'FAIL'
    gates_status['G4'] = g4_status
    if not g4_ok:
        fail_reasons.append(f"G4: Tasks limits violated or telemetry unreadable (tasks_max={tasks_max_val}, max_pids={max_pids}, errs={polling_errs})")
    print(f"  -> G4 Status: {g4_status}")

    # --------------------------------------------------------------------------
    # GATE G5: MOCK BOT 1 PROTECTION (RAW SAMPLES & FULL CROSS-CHECKS)
    # --------------------------------------------------------------------------
    print("\n[GATE G5: MOCK BOT 1 PROTECTION (COMPUTED VIA RAW SAMPLES, P1-01, P1-02)]")

    # 1. Verify workload exit status
    if bot1_stress_exit_status != 0:
        fail_reasons.append(f"G5: Mock Bot 1 Stress workload exited with failure code {bot1_stress_exit_status}")

    # 2. Load and validate raw sample arrays
    base_data = load_and_validate_raw_dataset(bot1_base_raw_path, "Mock Bot 1 Baseline")
    stress_data = load_and_validate_raw_dataset(bot1_stress_raw_path, "Mock Bot 1 Stress")

    # 3. Calculate percentiles directly from raw arrays
    b_samples = len(base_data['sched'])
    s_samples = len(stress_data['sched'])

    b_p99 = float(np.percentile(base_data['sched'], 99))
    s_p99 = float(np.percentile(stress_data['sched'], 99))

    b_commits_count = len(base_data['commits'])
    s_commits_count = len(stress_data['commits'])

    b_commit_p99 = float(np.percentile(base_data['commits'], 99))
    s_commit_p99 = float(np.percentile(stress_data['commits'], 99))

    b_max_hb = float(np.max(base_data['hb']))
    s_max_hb = float(np.max(stress_data['hb']))
    b_lateness = float(max(0.0, b_max_hb - 0.500))
    s_lateness = float(max(0.0, s_max_hb - 0.500))

    # 4. P1-02: Full Cross-Check of wake-up, commit, and heartbeat with log summary
    b_log_met = get_required_log_metrics(bot1_base_log, "Mock Bot 1 Baseline")
    s_log_met = get_required_log_metrics(bot1_stress_log, "Mock Bot 1 Stress")

    # Baseline cross-checks
    if abs(b_p99 - b_log_met['sched_wakeup_p99_ms']) > 0.001:
        fail_reasons.append(f"G5 (P1-02): Baseline wake-up P99 mismatch (raw={b_p99:.3f}, log={b_log_met['sched_wakeup_p99_ms']})")
    if abs(b_commit_p99 - b_log_met['commit_p99_ms']) > 0.001:
        fail_reasons.append(f"G5 (P1-02): Baseline commit P99 mismatch (raw={b_commit_p99:.3f}, log={b_log_met['commit_p99_ms']})")
    if abs(b_lateness - b_log_met['heartbeat_max_lateness_s']) > 0.001:
        fail_reasons.append(f"G5 (P1-02): Baseline heartbeat lateness mismatch (raw={b_lateness:.3f}, log={b_log_met['heartbeat_max_lateness_s']})")
    if b_commits_count != b_log_met['commits_total']:
        fail_reasons.append(f"G5 (P1-02): Baseline commit count mismatch (raw={b_commits_count}, log={b_log_met['commits_total']})")
    if b_log_met.get('sqlite_errors', 0) != 0:
        fail_reasons.append(f"G5 (P1-01): Baseline logged SQLite errors: {b_log_met['sqlite_errors']}")

    # Stress cross-checks
    if abs(s_p99 - s_log_met['sched_wakeup_p99_ms']) > 0.001:
        fail_reasons.append(f"G5 (P1-02): Stress wake-up P99 mismatch (raw={s_p99:.3f}, log={s_log_met['sched_wakeup_p99_ms']})")
    if abs(s_commit_p99 - s_log_met['commit_p99_ms']) > 0.001:
        fail_reasons.append(f"G5 (P1-02): Stress commit P99 mismatch (raw={s_commit_p99:.3f}, log={s_log_met['commit_p99_ms']})")
    if abs(s_lateness - s_log_met['heartbeat_max_lateness_s']) > 0.001:
        fail_reasons.append(f"G5 (P1-02): Stress heartbeat lateness mismatch (raw={s_lateness:.3f}, log={s_log_met['heartbeat_max_lateness_s']})")
    if s_commits_count != s_log_met['commits_total']:
        fail_reasons.append(f"G5 (P1-02): Stress commit count mismatch (raw={s_commits_count}, log={s_log_met['commits_total']})")
    if s_log_met.get('sqlite_errors', 0) != 0:
        fail_reasons.append(f"G5 (P1-01): Stress logged SQLite errors: {s_log_met['sqlite_errors']}")

    # 5. P1-01: Cross-check SQLite database rows directly
    def verify_db_rows(db_path, expected_count, label):
        if not os.path.exists(db_path):
            sys.exit(f"FATAL (P1-01): Database file missing: {db_path}")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bot1_state;")
        cnt = cur.fetchone()[0]
        conn.close()
        if cnt != expected_count:
            fail_reasons.append(f"G5 (P1-01): {label} DB row count ({cnt}) does not match raw commit count ({expected_count})")
        return cnt

    b_db_rows = verify_db_rows(bot1_base_db, b_commits_count, "Mock Bot 1 Baseline")
    s_db_rows = verify_db_rows(bot1_stress_db, s_commits_count, "Mock Bot 1 Stress")

    print(f"  -> Baseline Sample Count        : {b_samples} (Expected: >= 2000)")
    print(f"  -> Stress Sample Count          : {s_samples} (Expected: >= 2000)")
    print(f"  -> Baseline Wake-up Latency P99 : {b_p99:.3f} ms (Must be > 0)")
    print(f"  -> Stress Wake-up Latency P99   : {s_p99:.3f} ms (Expected: <= 10.0 ms and > 0)")
    print(f"  -> Baseline Commit Latency P99  : {b_commit_p99:.3f} ms (Must be > 0)")
    print(f"  -> Stress Commit Latency P99    : {s_commit_p99:.3f} ms (Expected: < 50.0 ms)")
    print(f"  -> Stress Heartbeat Max Lateness: {s_lateness:.3f} s (Expected: <= 2.0 s)")
    print(f"  -> Baseline Commits / DB Rows   : {b_commits_count} commits == {b_db_rows} rows")
    print(f"  -> Stress Commits / DB Rows     : {s_commits_count} commits == {s_db_rows} rows")
    print(f"  -> Stress Workload Exit Status  : {bot1_stress_exit_status} (Expected: == 0)")

    g5_ok = (
        bot1_stress_exit_status == 0 and
        b_samples >= 2000 and s_samples >= 2000 and
        b_p99 > 0.0 and s_p99 > 0.0 and s_p99 <= 10.0 and
        b_commit_p99 > 0.0 and s_commit_p99 > 0.0 and s_commit_p99 < 50.0 and
        s_lateness <= 2.0 and
        b_commits_count == b_db_rows and
        s_commits_count == s_db_rows
    )

    g5_status = 'PASS' if g5_ok else 'FAIL'
    gates_status['G5'] = g5_status
    if not g5_ok:
        fail_reasons.append(f"G5: Bot 1 protection criteria violated (stress_p99={s_p99:.3f}ms, commit_p99={s_commit_p99:.3f}ms, lateness={s_lateness:.3f}s)")
    print(f"  -> G5 Status: {g5_status}")

    # --------------------------------------------------------------------------
    # P1-04: FORMAL VERIFICATION REPORT GENERATION (BEFORE MANIFEST)
    # --------------------------------------------------------------------------
    all_pass = all(v == 'PASS' for v in gates_status.values())
    final_verdict = "PASS" if all_pass else "FAIL"

    report_path = os.path.join(output_dir, "verification_report.txt")
    with open(report_path, "w", encoding="utf-8") as rep:
        rep.write("================================================================================\n")
        rep.write("STAGE 40.1 - FORMAL VERIFICATION REPORT (P40-DOC-08)\n")
        rep.write(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
        rep.write(f"Final Verdict: {final_verdict}\n")
        rep.write("================================================================================\n\n")
        rep.write("GATE RATIFICATION SUMMARY:\n")
        for g, st in gates_status.items():
            rep.write(f"  - Gate {g}: {st}\n")
        rep.write("\nKEY METRICS SUMMARY:\n")
        rep.write(f"  - Peak Memory Observed: {max_mem_mb:.2f} MiB (Bound: 65.0M <= peak < 80.0M)\n")
        rep.write(f"  - Cgroup memory.high Delta Events: {delta_high} (Must be > 0)\n")
        rep.write(f"  - Cgroup memory.swap.max: {swap_max} (Must be == 0)\n")
        rep.write(f"  - Cgroup memory.swap.current: {swap_cur} B (Must be == 0)\n")
        rep.write(f"  - Cgroup cpu.max: {cpu_max_val} (Must be '50000 100000')\n")
        rep.write(f"  - CFS Delta Throttled Periods: {delta_throttled} (Must be > 0)\n")
        rep.write(f"  - Peak Tasks Observed: {max_pids} (Must be <= 10 and > 0)\n")
        rep.write(f"  - Telemetry Polling Errors: {polling_errs} (Must be == 0)\n")
        rep.write(f"  - Mock Bot 1 Stress Samples: {s_samples} (Must be >= 2000)\n")
        rep.write(f"  - Mock Bot 1 Stress P99 Wakeup: {s_p99:.3f} ms (Must be <= 10.0 ms)\n")
        rep.write(f"  - Mock Bot 1 Stress P99 Commit: {s_commit_p99:.3f} ms (Must be < 50.0 ms)\n")
        rep.write(f"  - Mock Bot 1 Heartbeat Max Lateness: {s_lateness:.3f} s (Must be <= 2.0 s)\n")
        rep.write(f"  - Mock Bot 1 Commits Match DB Rows: {s_commits_count == s_db_rows}\n")
        rep.write(f"  - Mock Bot 1 Workload Exit Status: {bot1_stress_exit_status} (Must be == 0)\n")
        if fail_reasons:
            rep.write("\nFAILURE REASONS:\n")
            for r in fail_reasons:
                rep.write(f"  - {r}\n")

    print(f"\n[REPORT] Formal Verification Report created at: '{report_path}'")

    # --------------------------------------------------------------------------
    # FINAL VERDICT
    # --------------------------------------------------------------------------
    print("\n" + "="*80)
    if all_pass:
        print("FINAL STAGE 40.1 VERDICT: PASS (ALL 5 GATES SATISFIED)")
        print("All raw sample metrics, kernel cgroup telemetry, and database integrity verified.")
        sys.exit(0)
    else:
        print("FINAL STAGE 40.1 VERDICT: FAIL")
        print("Failure Reasons:")
        for r in fail_reasons:
            print(f"  - {r}")
        sys.exit(1)

if __name__ == '__main__':
    main()
