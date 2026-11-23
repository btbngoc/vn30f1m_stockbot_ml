#!/usr/bin/env python3
"""
STAGE 40.1 - BOT 2 STRESS WORKLOAD SCRIPT (COORDINATED LIFECYCLE)
Standard: P40-DOC-08 Section 4.2, 5.2, 8
Idles upon startup to allow idle pre-snapshots; allocates memory regulated by
kernel cgroup memory.current (targeting 66.5 - 69.5 MiB) to exercise MemoryHigh=65M
while remaining safely below MemoryMax=80M; runs 4 threads to exercise CPUQuota=50%.
Exits cleanly upon detection of STOP_TRIGGER.
"""
import sys
import os
import time
import threading
import sqlite3

def run_bot2():
    if len(sys.argv) < 4:
        sys.exit("FATAL: bot2_stress_workload.py requires <db_path> <start_trigger> <stop_trigger> [cgroup_hint]")

    db_path = sys.argv[1]
    start_trigger = sys.argv[2]
    stop_trigger = sys.argv[3]
    cgroup_hint = sys.argv[4] if len(sys.argv) > 4 else None

    # Discover own unified cgroup v2 directory
    def resolve_cgroup_dir():
        if cgroup_hint and os.path.isdir(cgroup_hint):
            return cgroup_hint
        try:
            with open('/proc/self/cgroup', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('::')
                    if len(parts) == 2:
                        rel = parts[1].lstrip('/')
                        cand = os.path.join('/sys/fs/cgroup', rel)
                        if os.path.isdir(cand):
                            return cand
        except Exception:
            pass
        return '/sys/fs/cgroup'

    cg_dir = resolve_cgroup_dir()

    def get_cgroup_memory_current():
        mem_file = os.path.join(cg_dir, 'memory.current')
        if os.path.exists(mem_file):
            try:
                with open(mem_file, 'r', encoding='utf-8') as f:
                    return int(f.read().strip())
            except Exception:
                pass
        # Fallback to VmRSS from /proc/self/status only if cgroup file cannot be read
        try:
            with open('/proc/self/status', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('VmRSS:'):
                        return int(line.split()[1]) * 1024
        except Exception:
            pass
        return 0

    # Ensure parent directory for database exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("CREATE TABLE IF NOT EXISTS bot2_ledger (id INTEGER PRIMARY KEY, ts TEXT, data TEXT);")
    conn.commit()

    print(f"BOT2: Process started (PID {os.getpid()}). Resolved Cgroup: '{cg_dir}'.")
    print("BOT2: Idling in cgroup, waiting for START_TRIGGER before allocating memory (P0-01)...")

    # Phase 1: Wait for START_TRIGGER (allows harness to snapshot idle cgroup state)
    while not os.path.exists(start_trigger):
        if os.path.exists(stop_trigger):
            conn.close()
            print("BOT2: STOP_TRIGGER detected during idle phase. Exiting.")
            sys.exit(0)
        time.sleep(0.05)

    print("BOT2: START_TRIGGER detected. Commencing CPU burn threads and Cgroup memory.current closed loop...")

    # Phase 2: Start 4 tight CPU stress threads to saturate CPUQuota=50%
    stop_cpu = False
    def cpu_stress_worker():
        x = 0
        while not stop_cpu:
            x = (x + 1) * 31 % 1000000007

    threads = [threading.Thread(target=cpu_stress_worker, daemon=True) for _ in range(4)]
    for t in threads:
        t.start()

    # Phase 3: Closed-loop memory ramp regulated by cgroup memory.current
    # Cgroup constraints: MemoryHigh=65M (68,157,440 B), MemoryMax=80M (83,886,080 B)
    # Target: 66.5 MiB to 69.5 MiB cgroup memory.current
    TARGET_CGROUP_MIN = int(66.5 * 1024 * 1024)
    TARGET_CGROUP_MAX = int(69.5 * 1024 * 1024)
    chunks = []

    try:
        while not os.path.exists(stop_trigger):
            cg_mem = get_cgroup_memory_current()
            # Allocate 1MB chunk only if below target minimum
            if cg_mem < TARGET_CGROUP_MIN:
                chunks.append(bytearray(1 * 1024 * 1024))
            # If exceeding target maximum, release chunks immediately
            elif cg_mem > TARGET_CGROUP_MAX and chunks:
                chunks.pop()
            time.sleep(0.05)
    finally:
        stop_cpu = True
        for t in threads:
            t.join(timeout=0.2)
        conn.close()
        print("BOT2: STOP_TRIGGER detected. Clean shutdown complete.")

    return 0

if __name__ == '__main__':
    sys.exit(run_bot2())
