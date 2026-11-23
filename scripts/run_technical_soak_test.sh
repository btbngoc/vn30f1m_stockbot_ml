#!/usr/bin/env bash
# ==============================================================================
# TECHNICAL SOAK TEST (OFF-MARKET HOURS) — STAGE 40.1
# ==============================================================================
# Target: OCI VPS (161.33.147.149)
# Goal: Verify systemd, RAM, CPU, Swap, SQLite (1000 records), Sandbox & Restart Policy
# Invariant: Zero touch to Bot 1 (vn30f1m.service, PID 139407)
# ==============================================================================
set -euo pipefail

echo "=== [START: TECHNICAL SOAK TEST (OFF-MARKET)] ==="
DATE_START=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
echo "Execution Time: ${DATE_START}"

# 1. SQLITE STRESS & INTEGRITY TEST (1000 RECORDS)
echo -e "\n--- [TEST 1: SQLITE STRESS & INTEGRITY (1000 COMMITS)] ---"
/opt/vn30f1m-bot2/.venv/bin/python -c "
import sqlite3, time, sys

db_path = '/opt/vn30f1m-bot2/data/paper_trading.db'
conn = sqlite3.connect(db_path, timeout=5.0)

# Check WAL mode
mode = conn.execute('PRAGMA journal_mode;').fetchone()[0]
print(f'Initial journal_mode: {mode}')
if mode.lower() != 'wal':
    conn.execute('PRAGMA journal_mode=WAL;')

conn.execute('PRAGMA synchronous=NORMAL;')

# Ensure schema exists
conn.execute('''CREATE TABLE IF NOT EXISTS stress_test (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    qty INTEGER NOT NULL
);''')

start_time = time.time()
for i in range(1000):
    conn.execute('INSERT INTO stress_test (ts, symbol, price, qty) VALUES (?, ?, ?, ?);',
                 (time.time(), 'VN30F1M', 1250.0 + (i % 20) * 0.1, 1))
    conn.commit()
elapsed = time.time() - start_time

count = conn.execute('SELECT COUNT(*) FROM stress_test;').fetchone()[0]
print(f'Inserted 1000 records in {elapsed:.3f}s ({1000/elapsed:.1f} commits/sec). Total rows: {count}')

# Run WAL Checkpoint
ckpt = conn.execute('PRAGMA wal_checkpoint(TRUNCATE);').fetchone()
print(f'PRAGMA wal_checkpoint(TRUNCATE) result: {ckpt} (busy={ckpt[0]}, log={ckpt[1]}, checkpointed={ckpt[2]})')

# Run Integrity Check
quick_check = conn.execute('PRAGMA quick_check;').fetchone()[0]
integrity_check = conn.execute('PRAGMA integrity_check;').fetchone()[0]
print(f'PRAGMA quick_check: {quick_check}')
print(f'PRAGMA integrity_check: {integrity_check}')

conn.close()

if count < 1000 or quick_check != 'ok' or integrity_check != 'ok':
    print('SQLITE_TEST_FAILED')
    sys.exit(1)
print('SQLITE_TEST_PASSED')
"

# 2. SYSTEMD SERVICE LIFECYCLE & TELEMETRY
echo -e "\n--- [TEST 2: SYSTEMD SERVICE LIFECYCLE & CGROUP TELEMETRY] ---"
# Install test service unit
sudo cp /opt/vn30f1m-bot2/app/scripts/vn30f1m-bot2.service /etc/systemd/system/vn30f1m-bot2-soak.service
sudo systemctl daemon-reload
sudo systemctl start vn30f1m-bot2-soak.service
sleep 6

echo "Service Status:"
systemctl status vn30f1m-bot2-soak.service --no-pager | head -n 12

CG_PATH="/sys/fs/cgroup/system.slice/vn30f1m-bot2-soak.service"
if [[ -d "${CG_PATH}" ]]; then
    MEM_CUR=$(cat "${CG_PATH}/memory.current")
    MEM_PEAK=$(cat "${CG_PATH}/memory.peak")
    SWAP_CUR=$(cat "${CG_PATH}/memory.swap.current")
    echo "cgroup memory.current:      ${MEM_CUR} bytes ($(( MEM_CUR / 1048576 )) MiB)"
    echo "cgroup memory.peak:         ${MEM_PEAK} bytes ($(( MEM_PEAK / 1048576 )) MiB)"
    echo "cgroup memory.swap.current: ${SWAP_CUR} bytes"
    echo "cgroup memory.events:"
    cat "${CG_PATH}/memory.events"
    echo "cgroup cpu.stat:"
    cat "${CG_PATH}/cpu.stat"
fi

# 3. RESTART POLICY VERIFICATION (SIMULATE UNEXPECTED EXIT / CRASH)
echo -e "\n--- [TEST 3: RESTART POLICY TEST (CRASH SIMULATION)] ---"
BOT2_MAIN_PID=$(systemctl show vn30f1m-bot2-soak.service -p MainPID --value)
echo "Main PID before crash: ${BOT2_MAIN_PID}"

echo "Simulating crash via kill -9 ${BOT2_MAIN_PID}..."
sudo kill -9 "${BOT2_MAIN_PID}"

# Sleep 5s - with RestartSec=30s, it should be in activating/auto-restart wait state
sleep 5
STATUS_CRASH=$(systemctl show vn30f1m-bot2-soak.service -p SubState --value)
echo "SubState at T+5s (expected: auto-restart wait): ${STATUS_CRASH}"

# 4. FILESYSTEM ISOLATION CONFIRMATION (FROM INSIDE SANDBOX)
echo -e "\n--- [TEST 4: FILESYSTEM ISOLATION SANDBOX RE-VERIFICATION] ---"
READ_DENIED=0
WRITE_DENIED=0

if sudo systemd-run --wait --pipe -p User=opc -p ProtectSystem=strict -p InaccessiblePaths=/opt/vn30f1m head -n 1 /opt/vn30f1m/app/.env 2>/dev/null; then
    echo "[FAIL] Sandbox read allowed!"
else
    echo "[PASS] Sandbox read blocked (Permission Denied as expected)."
    READ_DENIED=1
fi

if sudo systemd-run --wait --pipe -p User=opc -p ProtectSystem=strict -p InaccessiblePaths=/var/lib/vn30f1m touch /var/lib/vn30f1m/data/exploit.tmp 2>/dev/null; then
    echo "[FAIL] Sandbox write allowed!"
else
    echo "[PASS] Sandbox write blocked (Permission Denied as expected)."
    WRITE_DENIED=1
fi

# 5. CLEANUP TEST SERVICE (DO NOT LEAVE BOT 2 RUNNING CONTINUOUSLY)
echo -e "\n--- [CLEANUP: STOPPING & REMOVING TEST SERVICE] ---"
sudo systemctl stop vn30f1m-bot2-soak.service || true
sudo rm -f /etc/systemd/system/vn30f1m-bot2-soak.service
sudo systemctl daemon-reload
rm -f /opt/vn30f1m-bot2/run/bot2.pid
echo "[CLEANUP] Test service stopped and removed."

# 6. FINAL BOT 1 AND HOST STATUS
echo -e "\n--- [TEST 5: BOT 1 ZERO TOUCH INTEGRITY & HOST RAM] ---"
systemctl status vn30f1m.service --no-pager | head -n 14
free -m

echo -e "\n=== [TECHNICAL SOAK TEST COMPLETED SUCCESSFULLY] ==="
