#!/usr/bin/env bash
# ==============================================================================
# LINUX STAGING CGROUP V2 & SYSTEMD RESOURCE ISOLATION VERIFICATION HARNESS
# Reference: P40-STAGE-40-1-LINUX-VERIFY (v2.3 FINAL - Strict Fail-Closed)
# Standard: P40-DOC-08 Final Technical Requirements
# Author: Quantitative Trading Engineering & QA Team
# Approver: Tech Lead
#
# Requirements:
#   - Linux Kernel >= 5.8 (Unified Cgroup v2 mounted at /sys/fs/cgroup as cgroup2fs)
#   - systemd active with memory, cpu, pids controllers enabled and delegated
#   - Independent Linux Staging VM only (Zero Touch Production VPS)
# ==============================================================================

set -Eeuo pipefail

# ------------------------------------------------------------------------------
# 1. DIRECTORY STRUCTURE & NAMESPACING (P40-DOC-08 Section 2, 3)
# ------------------------------------------------------------------------------
OUTPUT_DIR="${1:-/tmp/stage_40_1_artifacts}"
RUNTIME_DIR="/tmp/stage_40_1_runtime"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "${OUTPUT_DIR}" "${RUNTIME_DIR}/bot1_base" "${RUNTIME_DIR}/bot1_stress" "${RUNTIME_DIR}/bot2"

EXECUTION_LOG="${OUTPUT_DIR}/execution.log"
exec > >(tee -a "${EXECUTION_LOG}") 2>&1

echo "================================================================================"
echo "STAGE 40.1 - LINUX NATIVE CGROUP V2 & SYSTEMD ISOLATION VERIFICATION (v2.3 FINAL)"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Artifacts Destination : ${OUTPUT_DIR}"
echo "Runtime Directory     : ${RUNTIME_DIR}"
echo "Script Base Directory : ${SCRIPT_DIR}"
echo "================================================================================"

# Namespaced systemd units
UNIT_PREFIX="p40-stage40-1"
UNIT_BOT1_BASE="${UNIT_PREFIX}-bot1-base"
UNIT_BOT1_STRESS="${UNIT_PREFIX}-bot1-stress"
UNIT_BOT2="${UNIT_PREFIX}-bot2-stress"

START_TRIGGER="${RUNTIME_DIR}/bot2_start.trigger"
STOP_TRIGGER="${RUNTIME_DIR}/bot2_stop.trigger"
rm -f "${START_TRIGGER}" "${STOP_TRIGGER}"

# Determine systemd manager mode (system vs user)
SYSTEMD_CMD="systemd-run"
SYSTEMCTL_CMD="systemctl"
SYSTEMD_EXTRA_ARGS=""

if [[ $EUID -ne 0 ]]; then
    echo "Running as non-root user. Using user systemd manager (--user)..."
    SYSTEMD_EXTRA_ARGS="--user"
    SYSTEMCTL_CMD="systemctl --user"
else
    echo "Running as root. Using system systemd manager..."
fi

# ------------------------------------------------------------------------------
# PRE-EXECUTION CHECK (P0-01 STRICT): FAIL IMMEDIATELY IF ANY UNIT PRE-EXISTS
# Never touch, stop, or reset pre-existing units!
# ------------------------------------------------------------------------------
for u in "${UNIT_BOT1_BASE}" "${UNIT_BOT1_STRESS}" "${UNIT_BOT2}"; do
    UNIT_ACTIVE=$(${SYSTEMCTL_CMD} is-active "${u}.service" 2>/dev/null || true)
    UNIT_LOADED=$(${SYSTEMCTL_CMD} show "${u}.service" -p LoadState --value 2>/dev/null || true)
    if [[ "${UNIT_ACTIVE}" == "active" || "${UNIT_LOADED}" == "loaded" ]]; then
        echo "FATAL (P0-01): Unit ${u}.service already exists or is active (Active: ${UNIT_ACTIVE}, Load: ${UNIT_LOADED})."
        echo "Harness is strictly forbidden from touching, stopping, or resetting pre-existing units. Aborting immediately."
        exit 1
    fi
done

# ------------------------------------------------------------------------------
# 2. TRAP & CLEANUP HANDLER (Preserving Artifacts on Trap) (Section 3.2, 9)
# ------------------------------------------------------------------------------
CURRENT_STEP="INIT"

cleanup_stage_40_1() {
    local exit_code=$?
    echo ""
    echo "================================================================================"
    echo "STAGE 40.1 CLEANUP & SAFEHAVEN HANDLER"
    echo "Exit Code: ${exit_code} | Failure Step: ${CURRENT_STEP}"
    echo "================================================================================"

    # Signal Bot 2 to terminate if running
    touch "${STOP_TRIGGER}" 2>/dev/null || true

    # Stop test units that were spawned during this test session only
    echo "Stopping test units..."
    for u in "${UNIT_BOT1_BASE}" "${UNIT_BOT1_STRESS}" "${UNIT_BOT2}"; do
        ${SYSTEMCTL_CMD} stop "${u}.service" 2>/dev/null || true
        ${SYSTEMCTL_CMD} reset-failed "${u}.service" 2>/dev/null || true
    done

    # Remove runtime scratchpad only. KEEP OUTPUT_DIR INTACT!
    echo "Cleaning up runtime scratchpad: ${RUNTIME_DIR}..."
    rm -rf "${RUNTIME_DIR}" 2>/dev/null || true

    echo "Artifacts preserved at: ${OUTPUT_DIR}"
    if [[ ${exit_code} -ne 0 ]]; then
        echo "STAGE 40.1 EXECUTION TERMINATED WITH ERROR (Step: ${CURRENT_STEP}, Code: ${exit_code})"
    fi
    exit ${exit_code}
}

trap cleanup_stage_40_1 EXIT ERR

# ------------------------------------------------------------------------------
# 3. STEP 1: PRE-EXECUTION ENVIRONMENT & CGROUP V2 AUDIT (Gate G1, P0-05)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_1_AUDIT_ENVIRONMENT"
echo ""
echo "[STEP 1] Auditing Linux Kernel, systemd version, and Unified Cgroup v2..."

ENV_FILE="${OUTPUT_DIR}/environment.txt"
CG_CTRL_FILE="${OUTPUT_DIR}/cgroup_controllers.txt"

{
    echo "=== HOST SYSTEM ENVIRONMENT AUDIT ==="
    echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Host: $(hostname)"
    echo "Kernel: $(uname -r)"
    echo "Kernel Release Info: $(uname -a)"
    echo "OS Release:"
    cat /etc/os-release 2>/dev/null || echo "N/A"
    echo "systemd Version: $(systemctl --version | head -n 1)"
    echo "Cgroup v2 Mount:"
    mount | grep cgroup2 || echo "WARNING: cgroup2 not found in mount table!"
    echo "stat -fc %T /sys/fs/cgroup: $(stat -fc %T /sys/fs/cgroup 2>/dev/null || echo 'UNKNOWN')"
    echo "Available Root Controllers:"
    cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null || echo "NOT_FOUND"
} > "${ENV_FILE}"

cat /sys/fs/cgroup/cgroup.controllers > "${CG_CTRL_FILE}" 2>/dev/null || echo "NOT_FOUND" > "${CG_CTRL_FILE}"
cat "${ENV_FILE}"

# Deploy modular Python helpers to RUNTIME_DIR
if [[ -f "${SCRIPT_DIR}/check_env.py" ]]; then
    cp "${SCRIPT_DIR}/check_env.py" "${RUNTIME_DIR}/check_env.py"
    cp "${SCRIPT_DIR}/bot1_workload.py" "${RUNTIME_DIR}/bot1_workload.py"
    cp "${SCRIPT_DIR}/bot2_stress_workload.py" "${RUNTIME_DIR}/bot2_stress_workload.py"
    cp "${SCRIPT_DIR}/check_sqlite.py" "${RUNTIME_DIR}/check_sqlite.py"
    cp "${SCRIPT_DIR}/ratify_gates.py" "${RUNTIME_DIR}/ratify_gates.py"
fi

# Rigorous G1 Verification (P0-05): Verifies Kernel, systemd manager active, and transient controller delegation
python3 "${RUNTIME_DIR}/check_env.py" "${SYSTEMD_CMD}" "${SYSTEMCTL_CMD}"

# ------------------------------------------------------------------------------
# 4. STEP 2: SETUP WORKLOAD RUNTIMES & DATABASES (Section 4, 5, 7)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_2_SETUP_DATABASES"
BOT1_BASE_DB="${RUNTIME_DIR}/bot1_base/bot1.db"
BOT1_STRESS_DB="${RUNTIME_DIR}/bot1_stress/bot1.db"
BOT2_DB="${RUNTIME_DIR}/bot2/bot2.db"

# ------------------------------------------------------------------------------
# 5. STEP 3: RUN MOCK BOT 1 BASELINE (ALONE) -> bot1_baseline.log (Section 7.1)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_3_RUN_BASELINE"
echo ""
echo "[STEP 2] Running Mock Bot 1 Baseline (Alone, 15s)..."
BOT1_BASELINE_LOG="${OUTPUT_DIR}/bot1_baseline.log"
BOT1_BASE_RAW_JSON="${OUTPUT_DIR}/bot1_baseline.raw_samples.json"

# Strict command execution without || true
${SYSTEMD_CMD} ${SYSTEMD_EXTRA_ARGS} --unit="${UNIT_BOT1_BASE}" \
    --property=Nice=0 \
    python3 "${RUNTIME_DIR}/bot1_workload.py" "${BOT1_BASE_DB}" 15 "BASELINE" "${BOT1_BASE_RAW_JSON}" > "${BOT1_BASELINE_LOG}" 2>&1

BASE_STATUS=$(${SYSTEMCTL_CMD} show "${UNIT_BOT1_BASE}.service" -p ExecMainStatus --value)
if [[ "${BASE_STATUS}" != "0" ]]; then
    echo "FATAL: Mock Bot 1 Baseline run failed with exit status ${BASE_STATUS}"
    cat "${BOT1_BASELINE_LOG}"
    exit 1
fi

echo "  -> Baseline run complete. Parsing baseline summary metrics:"
grep "###BOT1_METRICS###" "${BOT1_BASELINE_LOG}"

# ------------------------------------------------------------------------------
# 6. STEP 4: LAUNCH BOT 2 (IDLE STATE) & RESOLVE CGROUP (Section 4.3, 8)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_4_LAUNCH_BOT2_IDLE"
echo ""
echo "[STEP 3] Launching Bot 2 in IDLE state under Cgroup v2 (P40-DOC-08 Section 4.3)..."

${SYSTEMD_CMD} ${SYSTEMD_EXTRA_ARGS} --unit="${UNIT_BOT2}" \
    --property=MemoryAccounting=yes \
    --property=MemoryMax=80M \
    --property=MemoryHigh=65M \
    --property=MemorySwapMax=0 \
    --property=CPUAccounting=yes \
    --property=CPUQuota=50% \
    --property=TasksAccounting=yes \
    --property=TasksMax=10 \
    --property=Nice=10 \
    python3 "${RUNTIME_DIR}/bot2_stress_workload.py" "${BOT2_DB}" "${START_TRIGGER}" "${STOP_TRIGGER}" > "${OUTPUT_DIR}/bot2_stress.log" 2>&1 &
BOT2_RUN_PID=$!

sleep 2

# Section 8: Strictly retrieve ControlGroup via systemctl (NO fallback guessing!)
CGROUP_REL=$(${SYSTEMCTL_CMD} show "${UNIT_BOT2}.service" -p ControlGroup --value || echo "")
echo "  -> Dynamically resolved ControlGroup property: '${CGROUP_REL}'"

if [[ -z "${CGROUP_REL}" || "${CGROUP_REL}" == "/" ]]; then
    echo "FATAL: systemctl show failed to return a valid non-root ControlGroup for ${UNIT_BOT2}. Found: '${CGROUP_REL}'"
    exit 1
fi

CGROUP_DIR="/sys/fs/cgroup/${CGROUP_REL}"
echo "  -> Cgroup absolute directory: ${CGROUP_DIR}"

if [[ ! -d "${CGROUP_DIR}" ]]; then
    echo "FATAL: Cgroup directory does not exist: '${CGROUP_DIR}'"
    exit 1
fi

# Verify required controller files exist in cgroup
for f in memory.max memory.high memory.swap.max memory.swap.current memory.current memory.events cpu.max cpu.stat pids.max pids.current; do
    if [[ ! -f "${CGROUP_DIR}/${f}" ]]; then
        echo "FATAL: Required cgroup controller file missing: ${CGROUP_DIR}/${f}"
        exit 1
    fi
done

# ------------------------------------------------------------------------------
# 7. STEP 5: PRE-TEST SNAPSHOTS (While Bot 2 is IDLE) (Section 4.3, P0-04)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_5_PRE_SNAPSHOTS"
echo ""
echo "[STEP 4] Recording Pre-test Cgroup Snapshots (Bot 2 verified IDLE)..."
MEMORY_PRE="${OUTPUT_DIR}/memory_pre.txt"
CPU_STAT_PRE="${OUTPUT_DIR}/cpu_stat_pre.txt"

{
    echo "=== PRE-TEST MEMORY SNAPSHOT ==="
    echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "memory.max: $(cat "${CGROUP_DIR}/memory.max")"
    echo "memory.high: $(cat "${CGROUP_DIR}/memory.high")"
    echo "memory.swap.max: $(cat "${CGROUP_DIR}/memory.swap.max")"
    echo "memory.swap.current: $(cat "${CGROUP_DIR}/memory.swap.current")"
    echo "memory.current: $(cat "${CGROUP_DIR}/memory.current")"
    echo "memory.events:"
    cat "${CGROUP_DIR}/memory.events"
} > "${MEMORY_PRE}"

cat "${CGROUP_DIR}/cpu.stat" > "${CPU_STAT_PRE}"

echo "  -> Pre-test snapshots successfully recorded:"
cat "${MEMORY_PRE}"

# ------------------------------------------------------------------------------
# 8. STEP 6: TRIGGER STRESS & RUN CONCURRENT MOCK BOT 1 (Section 4.3, 7.1)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_6_CONCURRENT_STRESS"
echo ""
echo "[STEP 5] Triggering Bot 2 Stress Phase and launching Mock Bot 1 Stress Run..."
touch "${START_TRIGGER}"

BOT1_STRESS_LOG="${OUTPUT_DIR}/bot1_stress.log"
BOT1_STRESS_RAW_JSON="${OUTPUT_DIR}/bot1_stress.raw_samples.json"

# Strict command execution without || true
${SYSTEMD_CMD} ${SYSTEMD_EXTRA_ARGS} --unit="${UNIT_BOT1_STRESS}" \
    --property=Nice=0 \
    python3 "${RUNTIME_DIR}/bot1_workload.py" "${BOT1_STRESS_DB}" 15 "STRESS" "${BOT1_STRESS_RAW_JSON}" > "${BOT1_STRESS_LOG}" 2>&1 &
BOT1_STRESS_RUN_PID=$!

# ------------------------------------------------------------------------------
# 9. STEP 7: ACTIVE TELEMETRY SAMPLING LOOP (Section 4.4, 6.2)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_7_TELEMETRY_SAMPLING"
echo ""
echo "[STEP 6] Active Sampling of Tasks, CPU, and Memory Time Series..."
PIDS_LOG="${OUTPUT_DIR}/pids_telemetry.log"
MEM_TIME_SERIES_LOG="${OUTPUT_DIR}/memory_telemetry.log"

echo "=== ACTIVE PIDS & TASKS TELEMETRY LOG (GATE G4) ===" > "${PIDS_LOG}"
echo "=== ACTIVE MEMORY TIME SERIES LOG (GATE G2) ===" > "${MEM_TIME_SERIES_LOG}"
echo "Timestamp_UTC | Sample_Index | Memory_Current_Bytes | Memory_Current_MiB | High_Events | Max_Events" >> "${MEM_TIME_SERIES_LOG}"

MAX_PIDS_OBSERVED=0
MAX_MEM_OBSERVED=0
POLLING_ERROR_COUNT=0

for i in {1..14}; do
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if [[ -f "${CGROUP_DIR}/pids.current" && -f "${CGROUP_DIR}/memory.current" && -f "${CGROUP_DIR}/memory.events" ]]; then
        PIDS_CUR=$(cat "${CGROUP_DIR}/pids.current")
        PIDS_PEAK=$(cat "${CGROUP_DIR}/pids.peak" 2>/dev/null || echo "N/A")
        MEM_CUR=$(cat "${CGROUP_DIR}/memory.current")
        MEM_CUR_MB=$(awk -v b="${MEM_CUR}" 'BEGIN {printf "%.2f", b/1048576}')
        HIGH_EVT=$(awk '$1=="high"{print $2}' "${CGROUP_DIR}/memory.events")
        MAX_EVT=$(awk '$1=="max"{print $2}' "${CGROUP_DIR}/memory.events")

        if [ "$PIDS_CUR" -gt "$MAX_PIDS_OBSERVED" ]; then
            MAX_PIDS_OBSERVED=$PIDS_CUR
        fi
        if [ "$MEM_CUR" -gt "$MAX_MEM_OBSERVED" ]; then
            MAX_MEM_OBSERVED=$MEM_CUR
        fi
        echo "${TS} | Sample ${i} | pids.current: ${PIDS_CUR} | pids.peak: ${PIDS_PEAK} | memory.current: ${MEM_CUR_MB} MiB" >> "${PIDS_LOG}"
        echo "${TS} | ${i} | ${MEM_CUR} | ${MEM_CUR_MB} | ${HIGH_EVT} | ${MAX_EVT}" >> "${MEM_TIME_SERIES_LOG}"
    else
        # Section 6.2: Do NOT mask missing cgroup with 0. Explicitly flag error!
        echo "${TS} | Sample ${i} | ERROR: cgroup files unreadable" >> "${PIDS_LOG}"
        echo "${TS} | ${i} | ERROR | ERROR | ERROR | ERROR" >> "${MEM_TIME_SERIES_LOG}"
        POLLING_ERROR_COUNT=$((POLLING_ERROR_COUNT + 1))
    fi
    sleep 1
done

# Strict wait for Mock Bot 1 stress workload to finish (NO || true)
echo "  -> Awaiting Mock Bot 1 Stress completion..."
wait "${BOT1_STRESS_RUN_PID}"

STRESS_STATUS=$(${SYSTEMCTL_CMD} show "${UNIT_BOT1_STRESS}.service" -p ExecMainStatus --value)
if [[ "${STRESS_STATUS}" != "0" ]]; then
    echo "FATAL: Mock Bot 1 Stress run failed with exit status ${STRESS_STATUS}"
    cat "${BOT1_STRESS_LOG}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 10. STEP 8: POST-TEST SNAPSHOTS (WHILE BOT 2 IS ACTIVE) (Section 4.3, 8)
# Snapshot cpu.max and pids.max before stopping Bot 2 (P0-02, P0-04)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_8_POST_SNAPSHOTS"
echo ""
echo "[STEP 7] Recording Post-test Snapshots (Bot 2 is guaranteed ACTIVE in cgroup)..."
MEMORY_POST="${OUTPUT_DIR}/memory_post.txt"
CPU_STAT_POST="${OUTPUT_DIR}/cpu_stat_post.txt"
CPU_MAX_SNAPSHOT="${OUTPUT_DIR}/cpu_max.txt"
PIDS_MAX_SNAPSHOT="${OUTPUT_DIR}/pids_max.txt"

if [[ ! -d "${CGROUP_DIR}" ]]; then
    echo "FATAL: Cgroup directory disappeared prematurely before post-snapshot!"
    exit 1
fi

{
    echo "=== POST-TEST MEMORY SNAPSHOT ==="
    echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "memory.max: $(cat "${CGROUP_DIR}/memory.max")"
    echo "memory.high: $(cat "${CGROUP_DIR}/memory.high")"
    echo "memory.swap.max: $(cat "${CGROUP_DIR}/memory.swap.max")"
    echo "memory.swap.current: $(cat "${CGROUP_DIR}/memory.swap.current")"
    echo "memory.current: $(cat "${CGROUP_DIR}/memory.current")"
    echo "memory.events:"
    cat "${CGROUP_DIR}/memory.events"
} > "${MEMORY_POST}"

cat "${CGROUP_DIR}/cpu.stat" > "${CPU_STAT_POST}"
cat "${CGROUP_DIR}/cpu.max" > "${CPU_MAX_SNAPSHOT}"
cat "${CGROUP_DIR}/pids.max" > "${PIDS_MAX_SNAPSHOT}"

echo "  -> Post-test snapshots successfully recorded:"
cat "${MEMORY_POST}"

# Now safely signal Bot 2 to stop
echo "  -> Signalling Bot 2 to stop via STOP_TRIGGER..."
touch "${STOP_TRIGGER}"

# Strict wait for Bot 2 to exit (NO || true)
wait "${BOT2_RUN_PID}"
sleep 1

# ------------------------------------------------------------------------------
# 11. STEP 9: SQLITE PRAGMA INTEGRITY & TRANSACTION AUDIT (Section 7.5, P1-01)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_9_SQLITE_INTEGRITY"
echo ""
echo "[STEP 8] Performing SQLite PRAGMA integrity_check and commit reconciliation (P1-01)..."

BASE_COMMITS=$(grep "###BOT1_METRICS###" "${BOT1_BASELINE_LOG}" | sed 's/.*"commits_total": *\([0-9]*\).*/\1/')
STRESS_COMMITS=$(grep "###BOT1_METRICS###" "${BOT1_STRESS_LOG}" | sed 's/.*"commits_total": *\([0-9]*\).*/\1/')

python3 "${RUNTIME_DIR}/check_sqlite.py" "${BOT1_BASE_DB}" "${BOT1_STRESS_DB}" "${BASE_COMMITS}" "${STRESS_COMMITS}"

# ------------------------------------------------------------------------------
# 12. STEP 10: AUTOMATED 5-GATE ENGINE & REPORT GENERATION (P1-04)
# Ratifier reads snapshots exclusively; does NOT touch cgroup after Bot 2 exits (P0-02)
# Generates verification_report.txt before manifest generation (P1-04)
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_10_GATE_ENGINE"
echo ""
echo "================================================================================"
echo "STAGE 40.1 - 5-GATE RIGOROUS RATIFICATION (FAIL-CLOSED AUTOMATED ENGINE)"
echo "================================================================================"

python3 "${RUNTIME_DIR}/ratify_gates.py" \
    "${MEMORY_PRE}" \
    "${MEMORY_POST}" \
    "${MAX_MEM_OBSERVED}" \
    "${CPU_STAT_PRE}" \
    "${CPU_STAT_POST}" \
    "${CPU_MAX_SNAPSHOT}" \
    "${PIDS_MAX_SNAPSHOT}" \
    "${MAX_PIDS_OBSERVED}" \
    "${POLLING_ERROR_COUNT}" \
    "${BOT1_BASELINE_LOG}" \
    "${BOT1_STRESS_LOG}" \
    "${BOT1_BASE_RAW_JSON}" \
    "${BOT1_STRESS_RAW_JSON}" \
    "${BOT1_BASE_DB}" \
    "${BOT1_STRESS_DB}" \
    "${STRESS_STATUS}"

# ------------------------------------------------------------------------------
# 13. STEP 11: TWO-STAGE MANIFEST GENERATION (Section 10, P1-03, P1-04)
# Manifest is strictly the final step; verifies exact mandatory artifact list!
# ------------------------------------------------------------------------------
CURRENT_STEP="STEP_11_MANIFEST_GENERATION"
echo ""
echo "[STEP 10] Closing execution log redirect before hashing (Section 10)..."
echo "All steps complete. Validating mandatory artifacts and generating manifest.sha256..."

# Safely close log redirection to prevent mid-hash modification
exec 1>&-
exec 2>&-
sleep 1

# P1-03: Strict verification of exactly 17 mandatory artifact files
MANDATORY_ARTIFACTS=(
    "environment.txt"
    "cgroup_controllers.txt"
    "bot1_baseline.log"
    "bot1_baseline.raw_samples.json"
    "bot2_stress.log"
    "memory_pre.txt"
    "memory_post.txt"
    "memory_telemetry.log"
    "cpu_stat_pre.txt"
    "cpu_stat_post.txt"
    "cpu_max.txt"
    "pids_max.txt"
    "pids_telemetry.log"
    "bot1_stress.log"
    "bot1_stress.raw_samples.json"
    "verification_report.txt"
    "execution.log"
)

MANIFEST_FILE="${OUTPUT_DIR}/manifest.sha256"

# Verify all mandatory artifacts exist and are non-empty
for f in "${MANDATORY_ARTIFACTS[@]}"; do
    TARGET_PATH="${OUTPUT_DIR}/${f}"
    if [[ ! -f "${TARGET_PATH}" ]]; then
        echo "FATAL (P1-03): Mandatory artifact missing: '${TARGET_PATH}'" >&2
        exit 1
    fi
    if [[ ! -s "${TARGET_PATH}" ]]; then
        echo "FATAL (P1-03): Mandatory artifact is 0 bytes: '${TARGET_PATH}'" >&2
        exit 1
    fi
done

{
    echo "# =============================================================================="
    echo "# ARTIFACT MANIFEST & INTEGRITY AUDIT (STAGE 40.1)"
    echo "# Standard: P40-DOC-08 Section 10"
    echo "# Package Content: Exactly 18 Artifacts (17 Audited Files + 1 Manifest File)"
    echo "# Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# Host Uname: $(uname -a)"
    echo "# =============================================================================="
    printf "%-36s | %10s | %-24s | %s\n" "Artifact File" "Size (B)" "Last Modified" "SHA-256 Checksum"
    echo "-------------------------------------------------------------------------------------------------------------------"
    cd "${OUTPUT_DIR}"
    for f in "${MANDATORY_ARTIFACTS[@]}"; do
        SIZE=$(stat -c %s "$f")
        MTIME=$(stat -c "%Y" "$f")
        MTIME_FMT=$(date -u -d "@${MTIME}" "+%Y-%m-%d %H:%M:%SZ" 2>/dev/null || date -u "+%Y-%m-%d %H:%M:%SZ")
        HASH=$(sha256sum "$f" | awk '{print $1}')
        printf "%-36s | %10d | %-24s | %s\n" "$f" "$SIZE" "$MTIME_FMT" "$HASH"
    done
} > "${MANIFEST_FILE}"
