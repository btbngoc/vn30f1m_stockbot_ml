#!/usr/bin/env python3
"""
STAGE 40.1 - SQLITE PRAGMA INTEGRITY & TRANSACTION AUDIT SCRIPT
Standard: P40-DOC-08 Section 7.5
Verifies:
1. SQLite WAL database integrity using PRAGMA integrity_check
2. Committed transaction records count matches expected successful commits exactly (P1-01)
3. Zero database errors or uncommitted transactions
"""
import sys
import os
import sqlite3

def check_db(name, path, expected_commits):
    print(f"Auditing Database Integrity for {name}: '{path}'")
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

        if cnt != expected_commits:
            sys.exit(
                f"FATAL (P1-01): Database {name} row count ({cnt}) does not match "
                f"recorded successful commits ({expected_commits})!"
            )

        print(f"  -> {name}: PRAGMA integrity_check = OK | Committed State Rows = {cnt} (Matches expected commits: {expected_commits})")
        conn.close()
    except Exception as e:
        sys.exit(f"FATAL: SQLite verification failed for {name}: {e}")

def main():
    if len(sys.argv) < 5:
        sys.exit("FATAL: check_sqlite.py requires <base_db> <stress_db> <base_expected_commits> <stress_expected_commits>")

    base_db = sys.argv[1]
    stress_db = sys.argv[2]
    base_commits = int(sys.argv[3])
    stress_commits = int(sys.argv[4])

    check_db("Mock Bot 1 Baseline DB", base_db, base_commits)
    check_db("Mock Bot 1 Stress DB", stress_db, stress_commits)
    print("SQLITE INTEGRITY AUDIT PASSED: Both databases are 100% integral and row counts match successful commits.\n")
    return 0

if __name__ == '__main__':
    sys.exit(main())
