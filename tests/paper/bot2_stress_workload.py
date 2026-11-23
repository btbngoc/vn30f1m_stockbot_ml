#!/usr/bin/env python3
"""
STAGE 40.1 - BOT 2 STRESS WORKLOAD SCRIPT (COORDINATED LIFECYCLE - STRICT FAIL-CLOSED)
Standard: P40-DOC-08 Section 4.2, 5.2, 8
Idles upon startup to allow idle pre-snapshots; allocates memory regulated strictly by
kernel cgroup memory.current (targeting 66.5 - 69.5 MiB) to exercise MemoryHigh=65M
while remaining safely below MemoryMax=80M; runs 4 threads to exercise CPUQuota=50%.

CRITICAL (P0-03):
Zero fallbacks allowed. If cgroup directory cannot be resolved or memory.current
cannot be read, the process exits immediately with a fatal nonzero exit code.
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

    # Strict Cgroup v2 Directory Resolution (NO FALLBACK to /sys/fs/cgroup root)
    def resolve_cgroup_dir():
        if cgroup_hint and os.path.isdir(cgroup_hint):
            return cgroup_hint
        try:
            with open('/proc/self/cgroup', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('::')
                    if len(parts) == 2:
                        rel = parts[1].lstrip('/')
                        if not rel:
                            continue
                        cand = os.path.join('/sys/fs/cgroup', rel)
                        if os.path.isdir(cand):
                            return cand
        except Exception as e:
            sys.exit(f"FATAL: Error reading /proc/self/cgroup: {e}. Zero fallback permitted.")

        sys.exit("FATAL (P0-03): Unable to resolve non-root cgroup v2 slice from /proc/self/cgroup. Zero fallback permitted.")

    cg_dir = resolve_cgroup_dir()

    # Strict Cgroup memory.current Reader (NO FALLBACK to VmRSS or 0)
    def get_cgroup_memory_current():
        mem_file = os.path.join(cg_dir, 'memory.current')
        if not os.path.exists(mem_file):
            sys.exit(f"FATAL (P0-03): Required cgroup file '{mem_file}' does not exist. Zero fallback permitted.")
        try:
            with open(mem_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content.isdigit():
                    sys.exit(f"FATAL (P0-03): Invalid non-integer memory.current '{content}' in '{mem_file}'.")
                return int(content)
        except Exception as e:
            sys.exit(f"FATAL (P0-03): Failed to read '{mem_file}': {e}. Zero fallback permitted.")

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
            print("BOT2: STOP_TRIGGER detected during idle phase. Exiting cleanly.")
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

    # Phase 3: Closed-loop memory ramp regulated strictly by cgroup memory.current
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
