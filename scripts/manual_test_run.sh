#!/usr/bin/env bash
# ==============================================================================
# BOT 2 MANUAL TEST RUN (STEP 4)
# ==============================================================================
set -e
cd /opt/vn30f1m-bot2/app

echo "=== [STEP 4: BOT 2 MANUAL TEST RUN] ==="
echo "Working directory: $(pwd)"
echo "Python interpreter: /opt/vn30f1m-bot2/.venv/bin/python"

# Verify environment file exists
if [[ ! -f .env ]]; then
    echo "[ERROR] .env file not found in $(pwd)"
    exit 1
fi

echo "[1/4] Launching Bot 2 with dedicated independent paths..."
/opt/vn30f1m-bot2/.venv/bin/python scripts/run_cloud_paper_trading.py \
    --db-path /opt/vn30f1m-bot2/data/paper_trading.db \
    --lock-path /opt/vn30f1m-bot2/run/bot2.pid \
    --health-file /opt/vn30f1m-bot2/run/health.json \
    --audit-file /opt/vn30f1m-bot2/logs/audit/dnse_cloud_audit.jsonl > /opt/vn30f1m-bot2/logs/manual_test.log 2>&1 &
BOT2_PID=$!

echo "[INFO] Bot 2 launched with PID: ${BOT2_PID}"

# Give it 8 seconds to initialize pipeline, connect to WebSocket, and log
sleep 8

echo -e "\n[2/4] Verifying Bot 2 process is alive and measuring memory RSS..."
if kill -0 ${BOT2_PID} 2>/dev/null; then
    echo "[STATUS] Bot 2 process is ACTIVE (PID ${BOT2_PID})"
    ps -o pid,user,%cpu,%mem,rss,vsz,comm -p ${BOT2_PID}
    
    BOT2_RSS=$(ps -o rss= -p ${BOT2_PID} | tr -d ' ')
    BOT2_RSS_MIB=$(( BOT2_RSS / 1024 ))
    echo "[METRIC] Bot 2 Resident Set Size: ${BOT2_RSS} kB (~${BOT2_RSS_MIB} MiB)"
else
    echo "[ERROR] Bot 2 process terminated unexpectedly! Log output:"
    cat /opt/vn30f1m-bot2/logs/manual_test.log
    exit 1
fi

echo -e "\n[3/4] Checking generated files in /opt/vn30f1m-bot2/..."
ls -la /opt/vn30f1m-bot2/data/
ls -la /opt/vn30f1m-bot2/run/
ls -la /opt/vn30f1m-bot2/logs/

echo -e "\n[4/4] Recent log entries from Bot 2:"
tail -n 15 /opt/vn30f1m-bot2/logs/manual_test.log

# Let it run another 12 seconds to observe heartbeats
sleep 12

echo -e "\n[STOP] Stopping Bot 2 gracefully with SIGTERM..."
kill -15 ${BOT2_PID} 2>/dev/null || true
wait ${BOT2_PID} 2>/dev/null || true
echo "[CLEANUP] Bot 2 gracefully shut down."

echo -e "\n=== [FINAL VERIFICATION OF BOT 1 INTEGRITY] ==="
systemctl status vn30f1m.service --no-pager | head -n 12
free -m
