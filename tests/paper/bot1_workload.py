#!/usr/bin/env python3
"""
STAGE 40.1 - MOCK BOT 1 WORKLOAD SCRIPT (FAIL-CLOSED)
Standard: P40-DOC-08 Section 4.1, 7.1-7.4
Simulates trading daemon with nominal 5.0ms scheduling loop and 500ms SQLite WAL heartbeat commits.
Generates N >= 2,000 raw samples and exports full JSON raw datasets for independent audit.
Tracks SQLite errors and strictly guarantees transaction integrity (P1-01, P1-02).
"""
import sys
import os
import time
import math
import json
import sqlite3
import datetime
import numpy as np

def run_workload():
    if len(sys.argv) < 5:
        sys.exit("FATAL: bot1_workload.py requires 4 arguments: <db_path> <duration_s> <mode> <raw_json_path>")

    db_path = sys.argv[1]
    duration_s = float(sys.argv[2])
    test_mode = sys.argv[3]          # "BASELINE" or "STRESS"
    raw_samples_path = sys.argv[4]   # Destination JSON for raw samples
    heartbeat_interval = 0.500       # 500ms nominal heartbeat interval

    start_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Ensure parent directory for database exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    # Initialize SQLite database with WAL mode and synchronous NORMAL
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("CREATE TABLE IF NOT EXISTS bot1_state (id INTEGER PRIMARY KEY, ts TEXT, uptime REAL, commit_count INTEGER);")
    conn.commit()

    sched_latencies = []
    commit_latencies = []
    heartbeat_intervals = []

    t_end = time.perf_counter() + duration_s
    last_beat = time.perf_counter()
    commit_count = 0
    sqlite_errors = 0
    sqlite_error_messages = []

    print(f"BOT1 ({test_mode}): Starting execution for {duration_s}s...")

    # Target 5ms sleep loop produces ~3000 samples over 15 seconds (guaranteeing N >= 2000)
    while time.perf_counter() < t_end:
        t0 = time.perf_counter_ns()
        time.sleep(0.005)
        t1 = time.perf_counter_ns()

        # Scheduling / Wake-up Latency: deviation between actual wake-up and target 5.0ms
        sched_lat_ms = ((t1 - t0) / 1e6) - 5.0
        val = max(0.0, sched_lat_ms)
        if math.isfinite(val):
            sched_latencies.append(val)

        now = time.perf_counter()
        interval = now - last_beat
        if interval >= heartbeat_interval:
            if math.isfinite(interval):
                heartbeat_intervals.append(interval)
            last_beat = now

            t_c0 = time.perf_counter_ns()
            try:
                conn.execute("INSERT INTO bot1_state (ts, uptime, commit_count) VALUES (datetime('now'), ?, ?);",
                             (now, commit_count))
                conn.commit()
                t_c1 = time.perf_counter_ns()
                c_lat_ms = (t_c1 - t_c0) / 1e6
                if math.isfinite(c_lat_ms):
                    commit_latencies.append(c_lat_ms)
                commit_count += 1
            except Exception as e:
                sqlite_errors += 1
                sqlite_error_messages.append(str(e))

    conn.close()
    end_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Fail-closed checks
    if sqlite_errors > 0:
        sys.exit(f"FATAL (P1-01): SQLite errors encountered during {test_mode} run: {sqlite_errors} ({sqlite_error_messages})")

    if len(sched_latencies) < 2000:
        sys.exit(f"FATAL: Insufficient scheduling samples recorded ({len(sched_latencies)} < 2000). Test invalid.")

    if len(commit_latencies) == 0:
        sys.exit("FATAL: Zero SQLite commit transactions recorded. Test invalid.")

    if len(heartbeat_intervals) == 0:
        sys.exit("FATAL: Zero heartbeat intervals recorded. Test invalid.")

    arr_sched = np.array(sched_latencies, dtype=np.float64)
    arr_commit = np.array(commit_latencies, dtype=np.float64)
    arr_hb = np.array(heartbeat_intervals, dtype=np.float64)

    # Compute percentiles
    p50 = float(np.percentile(arr_sched, 50))
    p95 = float(np.percentile(arr_sched, 95))
    p99 = float(np.percentile(arr_sched, 99))
    c_p50 = float(np.percentile(arr_commit, 50))
    c_p95 = float(np.percentile(arr_commit, 95))
    c_p99 = float(np.percentile(arr_commit, 99))
    c_max = float(np.max(arr_commit))
    hb_med = float(np.median(arr_hb))
    hb_p95 = float(np.percentile(arr_hb, 95))
    hb_max = float(np.max(arr_hb))

    # Standardized maximum lateness over nominal interval (Section 7.4)
    hb_max_lateness = float(max(0.0, hb_max - heartbeat_interval))
    late_hb_count = int(np.sum(arr_hb > (heartbeat_interval + 0.100)))

    # Persist complete raw samples dataset with full audit metadata
    raw_dataset = {
        'test_mode': test_mode,
        'start_time_utc': start_iso,
        'end_time_utc': end_iso,
        'duration_seconds': duration_s,
        'total_samples_recorded': len(sched_latencies),
        'valid_samples_count': len(sched_latencies),
        'dropped_samples_count': 0,
        'drop_reasons': [],
        'metric_name': "Scheduling / Wake-up Latency",
        'metric_definition': "Difference between actual process wake-up time and 5.0ms nominal time.sleep target",
        'unit': "milliseconds",
        'percentile_method': "numpy.percentile with linear interpolation",
        'stats': {
            'min_ms': float(np.min(arr_sched)),
            'max_ms': float(np.max(arr_sched)),
            'mean_ms': float(np.mean(arr_sched)),
            'std_ms': float(np.std(arr_sched)),
            'sched_wakeup_p50_ms': p50,
            'sched_wakeup_p95_ms': p95,
            'sched_wakeup_p99_ms': p99
        },
        'sqlite_commit_stats': {
            'successful_commits': commit_count,
            'sqlite_errors': sqlite_errors,
            'error_messages': sqlite_error_messages,
            'min_ms': float(np.min(arr_commit)),
            'max_ms': c_max,
            'mean_ms': float(np.mean(arr_commit)),
            'commit_p50_ms': c_p50,
            'commit_p95_ms': c_p95,
            'commit_p99_ms': c_p99
        },
        'heartbeat_stats': {
            'nominal_interval_s': heartbeat_interval,
            'median_interval_s': hb_med,
            'p95_interval_s': hb_p95,
            'max_interval_s': hb_max,
            'heartbeat_max_lateness_s': hb_max_lateness,
            'late_heartbeat_count_over_100ms': late_hb_count
        },
        'raw_sched_wakeup_samples_ms': sched_latencies,
        'raw_commit_samples_ms': commit_latencies,
        'raw_heartbeat_intervals_s': heartbeat_intervals
    }

    os.makedirs(os.path.dirname(os.path.abspath(raw_samples_path)), exist_ok=True)
    with open(raw_samples_path, "w", encoding="utf-8") as f_raw:
        json.dump(raw_dataset, f_raw, indent=2)

    summary = {
        'sample_count': len(arr_sched),
        'sched_wakeup_p50_ms': p50,
        'sched_wakeup_p95_ms': p95,
        'sched_wakeup_p99_ms': p99,
        'sched_wakeup_max_ms': float(np.max(arr_sched)),
        'commit_p50_ms': c_p50,
        'commit_p95_ms': c_p95,
        'commit_p99_ms': c_p99,
        'commit_max_ms': c_max,
        'hb_median_s': hb_med,
        'hb_max_s': hb_max,
        'heartbeat_max_lateness_s': hb_max_lateness,
        'late_heartbeat_count_over_100ms': late_hb_count,
        'commits_total': commit_count,
        'sqlite_errors': sqlite_errors
    }

    print("BOT1 Execution complete. Emitting telemetry marker:")
    print("###BOT1_METRICS###" + json.dumps(summary))
    return 0

if __name__ == '__main__':
    sys.exit(run_workload())
