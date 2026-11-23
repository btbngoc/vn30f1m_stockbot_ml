#!/usr/bin/env python3
"""
STAGE 40.1 - SQLITE PRAGMA INTEGRITY AUDIT SCRIPT
Standard: P40-DOC-08 Section 7.5
Verifies SQLite WAL database integrity using PRAGMA integrity_check
and asserts committed transaction records exist for both Baseline and Stress runs.
"""
import sys
import os
import sqlite3

def check_db(name, path):
    print(f"Auditing Database Integrity for {name}: {path}")
    if not os.path.exists(path):
        sys.exit(f"FATAL: Database file does not exist: {path}")

    try:
        conn = sqlite3.connect(path, timeout=5.0)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()[0]
        if res != 'ok':
            sys.exit(f"FATAL: SQLite corruption detected in {name}! Result: {res}")

        cur.execute("SELECT COUNT(*) FROM bot1_state;")
        cnt = cur.fetchone()[0]
        if cnt == 0:
            sys.exit(f"FATAL: Database {name} has 0 committed rows in bot1_state!")

        print(f"  -> {name}: PRAGMA integrity_check = OK | Committed State Rows = {cnt}")
        conn.close()
    except Exception as e:
        sys.exit(f"FATAL: SQLite verification failed for {name}: {e}")

def main():
    if len(sys.argv) < 3:
        sys.exit("FATAL: check_sqlite.py requires <baseline_db_path> <stress_db_path>")

    base_db = sys.argv[1]
    stress_db = sys.argv[2]

    check_db("Mock Bot 1 Baseline DB", base_db)
    check_db("Mock Bot 1 Stress DB", stress_db)
    print("SQLITE INTEGRITY AUDIT PASSED: Both databases are 100% integral and contain committed data.\n")
    return 0

if __name__ == '__main__':
    sys.exit(main())
