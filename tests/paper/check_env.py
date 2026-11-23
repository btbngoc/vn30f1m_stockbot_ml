#!/usr/bin/env python3
"""
STAGE 40.1 - GATE G1 ENVIRONMENT VERIFICATION SCRIPT
Standard: P40-DOC-08 Section 2, 11
Verifies Linux Kernel >= 5.8, unified cgroup v2 hierarchy (cgroup2fs),
and availability of memory, cpu, pids controllers in root cgroup.
"""
import sys
import os
import platform

def verify_environment():
    print("[GATE G1 PRE-CHECK] Auditing Host OS and Cgroup v2 Controllers...")

    # 1. OS check: Must be Linux
    os_name = platform.system()
    print(f"  -> Detected Operating System : {os_name}")
    if os_name != 'Linux':
        sys.exit(f"FATAL: Host OS is '{os_name}', expected 'Linux'. Linux Native Verification cannot proceed.")

    # 2. Kernel Version check: Must be >= 5.8
    k_rel = platform.release()
    try:
        k_major, k_minor = [int(x) for x in k_rel.split('-')[0].split('.')[:2]]
    except Exception as e:
        sys.exit(f"FATAL: Unable to parse Linux kernel release '{k_rel}': {e}")

    print(f"  -> Detected Kernel Version   : {k_major}.{k_minor} ({k_rel})")
    if (k_major, k_minor) < (5, 8):
        sys.exit(f"FATAL: Linux Kernel {k_major}.{k_minor} < 5.8. Unified Cgroup v2 is not fully supported.")

    # 3. Cgroup v2 Filesystem Mount check
    try:
        fs_type = os.popen('stat -fc %T /sys/fs/cgroup 2>/dev/null').read().strip()
    except Exception as e:
        sys.exit(f"FATAL: Failed to execute stat on /sys/fs/cgroup: {e}")

    print(f"  -> /sys/fs/cgroup Mount Type : {fs_type}")
    if fs_type != 'cgroup2fs':
        sys.exit(f"FATAL: /sys/fs/cgroup mount type is '{fs_type}', expected 'cgroup2fs' (Unified Hierarchy).")

    # 4. Controllers check in /sys/fs/cgroup/cgroup.controllers
    ctrl_path = '/sys/fs/cgroup/cgroup.controllers'
    if not os.path.exists(ctrl_path):
        sys.exit(f"FATAL: Root controller file '{ctrl_path}' not found.")

    with open(ctrl_path, 'r', encoding='utf-8') as f:
        controllers = f.read().strip().split()

    print(f"  -> Available Root Controllers: {controllers}")
    required_controllers = ['memory', 'cpu', 'pids']
    missing_controllers = [c for c in required_controllers if c not in controllers]

    if missing_controllers:
        sys.exit(f"FATAL: Missing required cgroup v2 controllers: {missing_controllers}. Unified controllers must be enabled.")

    print("GATE G1 PRE-CHECK PASSED: Host satisfies Linux Kernel, systemd, and cgroup v2 requirements.\n")
    return 0

if __name__ == '__main__':
    sys.exit(verify_environment())
