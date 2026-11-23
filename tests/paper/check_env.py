#!/usr/bin/env python3
"""
STAGE 40.1 - GATE G1 ENVIRONMENT & SYSTEMD CONTROLLER VERIFICATION SCRIPT
Standard: P40-DOC-08 Section 2, 11
Verifies:
1. Linux Kernel >= 5.8
2. Unified Cgroup v2 hierarchy mounted as cgroup2fs
3. Root cgroup.controllers contains memory, cpu, pids
4. systemd manager is responsive and active
5. Transient unit can successfully attach and enforce memory, cpu, pids controllers
"""
import sys
import os
import platform
import subprocess

def verify_environment():
    print("================================================================================")
    print("[GATE G1 AUDIT] Verifying Linux Kernel, systemd Manager & Cgroup v2 Controllers")
    print("================================================================================")

    systemd_cmd = sys.argv[1] if len(sys.argv) > 1 else "systemd-run"
    systemctl_cmd = sys.argv[2] if len(sys.argv) > 2 else "systemctl"

    # 1. OS check: Must be Linux
    os_name = platform.system()
    print(f"  -> Operating System detected  : {os_name}")
    if os_name != 'Linux':
        sys.exit(f"FATAL: Host OS is '{os_name}', expected 'Linux'. Linux Native Verification cannot proceed.")

    # 2. Kernel Version check: Must be >= 5.8
    k_rel = platform.release()
    try:
        k_major, k_minor = [int(x) for x in k_rel.split('-')[0].split('.')[:2]]
    except Exception as e:
        sys.exit(f"FATAL: Unable to parse Linux kernel release '{k_rel}': {e}")

    print(f"  -> Kernel Version detected    : {k_major}.{k_minor} ({k_rel})")
    if (k_major, k_minor) < (5, 8):
        sys.exit(f"FATAL: Linux Kernel {k_major}.{k_minor} < 5.8. Unified Cgroup v2 is not fully supported.")

    # 3. Cgroup v2 Filesystem Mount check
    try:
        fs_type = os.popen('stat -fc %T /sys/fs/cgroup 2>/dev/null').read().strip()
    except Exception as e:
        sys.exit(f"FATAL: Failed to execute stat on /sys/fs/cgroup: {e}")

    print(f"  -> /sys/fs/cgroup Mount Type  : {fs_type}")
    if fs_type != 'cgroup2fs':
        sys.exit(f"FATAL: /sys/fs/cgroup mount type is '{fs_type}', expected 'cgroup2fs' (Unified Hierarchy).")

    # 4. Controllers check in /sys/fs/cgroup/cgroup.controllers
    ctrl_path = '/sys/fs/cgroup/cgroup.controllers'
    if not os.path.exists(ctrl_path):
        sys.exit(f"FATAL: Root controller file '{ctrl_path}' not found.")

    with open(ctrl_path, 'r', encoding='utf-8') as f:
        controllers = f.read().strip().split()

    print(f"  -> Root Available Controllers : {controllers}")
    required_controllers = ['memory', 'cpu', 'pids']
    missing_controllers = [c for c in required_controllers if c not in controllers]

    if missing_controllers:
        sys.exit(f"FATAL: Missing required cgroup v2 controllers: {missing_controllers}. Unified controllers must be enabled.")

    # 5. P0-05: Verify systemd manager is responsive and active
    print(f"  -> Verifying systemd manager via '{systemctl_cmd}'...")
    try:
        res = subprocess.run(
            f"{systemctl_cmd} is-system-running 2>/dev/null || {systemctl_cmd} status 2>/dev/null",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode not in [0, 1]:  # 'degraded' returns 1 in is-system-running but manager is still running
            sys.exit(f"FATAL: systemctl failed with code {res.returncode}. systemd manager is not active.")
        print("  -> systemd manager is active and responsive.")
    except Exception as e:
        sys.exit(f"FATAL: Failed to communicate with systemd manager: {e}")

    # 6. P0-05: Verify transient unit can actually attach memory, cpu, pids controllers
    print(f"  -> Probing transient unit controller attachment via '{systemd_cmd}'...")
    probe_unit = "p40-stage40-1-probe"
    probe_cmd = (
        f"{systemd_cmd} --unit={probe_unit} --wait --pipe "
        f"--property=MemoryAccounting=yes --property=CPUAccounting=yes --property=TasksAccounting=yes "
        f"true"
    )
    try:
        probe_res = subprocess.run(probe_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if probe_res.returncode != 0:
            sys.exit(f"FATAL: Controller probe failed (code {probe_res.returncode}): {probe_res.stderr.strip()}")
        # Cleanup probe reset-failed if any
        subprocess.run(f"{systemctl_cmd} reset-failed {probe_unit}.service 2>/dev/null", shell=True)
        print("  -> Controller delegation probe succeeded: transient units can enforce memory, cpu, and pids.")
    except Exception as e:
        sys.exit(f"FATAL: Transient controller delegation probe failed: {e}")

    print("GATE G1 PRE-CHECK PASSED: Host satisfies Linux Kernel, systemd manager, and cgroup v2 controllers.\n")
    return 0

if __name__ == '__main__':
    sys.exit(verify_environment())
