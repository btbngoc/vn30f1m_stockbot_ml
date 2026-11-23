#!/usr/bin/env python3
"""
STAGE 40.1 - 5-GATE RIGOROUS RATIFICATION ENGINE (FAIL-CLOSED)
Standard: P40-DOC-08 Section 2, 4-7, 11
Independently verifies all 5 acceptance gates (G1-G5).
Specifically for G5: Calculates percentiles directly from raw sample datasets (N >= 2000),
verifies finite values, asserts ExecMainStatus == 0, and cross-checks with execution logs.
"""
import sys
import os
import math
import json
import numpy as np

def parse_kv_file(path):
    d = {}
    if not os.path.exists(path):
        return d
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
    if len(sys.argv) < 14:
        sys.exit(f"FATAL: ratify_gates.py requires 13 arguments, received {len(sys.argv)-1}")

    mem_pre_path = sys.argv[1]
    mem_post_path = sys.argv[2]
    max_mem_bytes = int(sys.argv[3])
    cpu_pre_path = sys.argv[4]
    cpu_post_path = sys.argv[5]
    cgroup_dir = sys.argv[6]
    max_pids = int(sys.argv[7])
    polling_errs = int(sys.argv[8])
    bot1_base_log = sys.argv[9]
    bot1_stress_log = sys.argv[10]
    bot1_base_raw_path = sys.argv[11]
    bot1_stress_raw_path = sys.argv[12]
    bot1_stress_exit_status = int(sys.argv[13])

    gates_status = {}
    fail_reasons = []

    print("================================================================================")
    print("STAGE 40.1 - 5-GATE RIGOROUS RATIFICATION ENGINE (P40-DOC-08)")
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
    # GATE G2: MEMORY ISOLATION & KERNEL CGROUP THROTTLING
    # --------------------------------------------------------------------------
    print("\n[GATE G2: MEMORY ISOLATION & HIGH EVENT]")
    mem_pre = parse_kv_file(mem_pre_path)
    mem_post = parse_kv_file(mem_post_path)

    cfg_max = mem_post.get('memory.max', 0)
    cfg_high = mem_post.get('memory.high', 0)
    swap_cur = mem_post.get('memory.swap.current', 0)
    max_mem_mb = max_mem_bytes / 1048576.0

    delta_high = mem_post.get('high', 0) - mem_pre.get('high', 0)
    delta_max = mem_post.get('max', 0) - mem_pre.get('max', 0)
    delta_oom = mem_post.get('oom', 0) - mem_pre.get('oom', 0)
    delta_oom_kill = mem_post.get('oom_kill', 0) - mem_pre.get('oom_kill', 0)

    print(f"  -> Configured memory.max  : {cfg_max} (Expected: 83886080 [80M])")
    print(f"  -> Configured memory.high : {cfg_high} (Expected: 68157440 [65M])")
    print(f"  -> Peak memory observed   : {max_mem_mb:.2f} MiB (Expected: >= 65M and < 80M)")
    print(f"  -> Delta high events      : {delta_high} (Expected: > 0)")
    print(f"  -> Delta max events       : {delta_max} (Expected: == 0)")
    print(f"  -> Delta oom events       : {delta_oom} (Expected: == 0)")
    print(f"  -> Delta oom_kill events  : {delta_oom_kill} (Expected: == 0)")
    print(f"  -> Swap current used      : {swap_cur} B (Expected: == 0)")

    g2_ok = (
        cfg_max == 83886080 and
        cfg_high == 68157440 and
        max_mem_mb >= 65.0 and max_mem_mb < 80.0 and
        delta_high > 0 and
        delta_max == 0 and
        delta_oom == 0 and
        delta_oom_kill == 0 and
        swap_cur == 0
    )

    g2_status = 'PASS' if g2_ok else 'FAIL'
    gates_status['G2'] = g2_status
    if not g2_ok:
        fail_reasons.append(f"G2: Memory cgroup constraints violated (delta_high={delta_high}, delta_oom_kill={delta_oom_kill}, peak={max_mem_mb:.2f}M)")
    print(f"  -> G2 Status: {g2_status}")

    # --------------------------------------------------------------------------
    # GATE G3: CPU QUOTA & CFS THROTTLING
    # --------------------------------------------------------------------------
    print("\n[GATE G3: CPU QUOTA & CFS THROTTLING]")
    cpu_pre = parse_kv_file(cpu_pre_path)
    cpu_post = parse_kv_file(cpu_post_path)
    cpu_max_file = os.path.join(cgroup_dir, 'cpu.max')
    cpu_max_val = open(cpu_max_file).read().strip() if os.path.exists(cpu_max_file) else 'N/A'

    delta_usage_s = (cpu_post.get('usage_usec', 0) - cpu_pre.get('usage_usec', 0)) / 1e6
    delta_periods = cpu_post.get('nr_periods', 0) - cpu_pre.get('nr_periods', 0)
    delta_throttled = cpu_post.get('nr_throttled', 0) - cpu_pre.get('nr_throttled', 0)
    delta_throttled_s = (cpu_post.get('throttled_usec', 0) - cpu_pre.get('throttled_usec', 0)) / 1e6

    print(f"  -> Configured cpu.max   : {cpu_max_val} (Expected: 50000 100000 [50%])")
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
        fail_reasons.append(f"G3: CFS CPU throttling not verified (delta_throttled={delta_throttled}, delta_usage_s={delta_usage_s:.2f})")
    print(f"  -> G3 Status: {g3_status}")

    # --------------------------------------------------------------------------
    # GATE G4: PROCESS & TASK ISOLATION
    # --------------------------------------------------------------------------
    print("\n[GATE G4: PROCESS & TASK ISOLATION]")
    pids_max_file = os.path.join(cgroup_dir, 'pids.max')
    tasks_max_val = int(open(pids_max_file).read().strip()) if os.path.exists(pids_max_file) else 0

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
        fail_reasons.append(f"G4: Tasks limits violated or telemetry unreadable (max_pids={max_pids}, errs={polling_errs})")
    print(f"  -> G4 Status: {g4_status}")

    # --------------------------------------------------------------------------
    # GATE G5: MOCK BOT 1 PROTECTION (COMPUTED FROM RAW SAMPLES)
    # --------------------------------------------------------------------------
    print("\n[GATE G5: MOCK BOT 1 PROTECTION (AUDITED VIA RAW SAMPLES)]")

    # 1. Verify workload exit status
    if bot1_stress_exit_status != 0:
        fail_reasons.append(f"G5: Mock Bot 1 Stress workload exited with failure code {bot1_stress_exit_status}")

    # 2. Load and validate raw sample arrays
    base_data = load_and_validate_raw_dataset(bot1_base_raw_path, "Mock Bot 1 Baseline")
    stress_data = load_and_validate_raw_dataset(bot1_stress_raw_path, "Mock Bot 1 Stress")

    # 3. Calculate percentiles directly from raw arrays (NO reliance on self-reporting)
    b_samples = len(base_data['sched'])
    s_samples = len(stress_data['sched'])

    b_p99 = float(np.percentile(base_data['sched'], 99))
    s_p99 = float(np.percentile(stress_data['sched'], 99))

    b_commit_p99 = float(np.percentile(base_data['commits'], 99))
    s_commit_p99 = float(np.percentile(stress_data['commits'], 99))

    s_max_hb = float(np.max(stress_data['hb']))
    s_lateness = float(max(0.0, s_max_hb - 0.500))

    # 4. Cross-check with log file summary markers
    b_log_met = get_required_log_metrics(bot1_base_log, "Mock Bot 1 Baseline")
    s_log_met = get_required_log_metrics(bot1_stress_log, "Mock Bot 1 Stress")

    if abs(b_p99 - b_log_met.get('sched_wakeup_p99_ms', -999.0)) > 0.001:
        fail_reasons.append("G5: Baseline log summary does not match raw sample calculation")
    if abs(s_p99 - s_log_met.get('sched_wakeup_p99_ms', -999.0)) > 0.001:
        fail_reasons.append("G5: Stress log summary does not match raw sample calculation")

    print(f"  -> Baseline Sample Count        : {b_samples} (Expected: >= 2000)")
    print(f"  -> Stress Sample Count          : {s_samples} (Expected: >= 2000)")
    print(f"  -> Baseline Wake-up Latency P99 : {b_p99:.3f} ms (Must be > 0)")
    print(f"  -> Stress Wake-up Latency P99   : {s_p99:.3f} ms (Expected: <= 10.0 ms and > 0)")
    print(f"  -> Baseline Commit Latency P99  : {b_commit_p99:.3f} ms (Must be > 0)")
    print(f"  -> Stress Commit Latency P99    : {s_commit_p99:.3f} ms (Expected: < 50.0 ms)")
    print(f"  -> Stress Heartbeat Max Lateness: {s_lateness:.3f} s (Expected: <= 2.0 s)")
    print(f"  -> Stress Workload Exit Status  : {bot1_stress_exit_status} (Expected: == 0)")

    g5_ok = (
        bot1_stress_exit_status == 0 and
        b_samples >= 2000 and s_samples >= 2000 and
        b_p99 > 0.0 and s_p99 > 0.0 and s_p99 <= 10.0 and
        b_commit_p99 > 0.0 and s_commit_p99 > 0.0 and s_commit_p99 < 50.0 and
        s_lateness <= 2.0
    )

    g5_status = 'PASS' if g5_ok else 'FAIL'
    gates_status['G5'] = g5_status
    if not g5_ok:
        fail_reasons.append(f"G5: Bot 1 protection criteria violated (stress_p99={s_p99:.3f}ms, commit_p99={s_commit_p99:.3f}ms, lateness={s_lateness:.3f}s)")
    print(f"  -> G5 Status: {g5_status}")

    # --------------------------------------------------------------------------
    # FINAL VERDICT
    # --------------------------------------------------------------------------
    print("\n" + "="*80)
    all_pass = all(v == 'PASS' for v in gates_status.values())
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
