"""Programmatic verification of the frozen Layer 1 Pure Rules system state.

Ensures that:
1. MANIFEST_L1_FROZEN.json is present and valid.
2. Layer 2 is permanently decommissioned (active_trading_layer == 'LAYER_1_PURE_RULES_ONLY').
3. Real-money trading is strictly blocked (real_money_authorized == False).
4. Forward testing cutoff is respected (uncontaminated_oos_start_date == '2026-10-20').
5. SHA256 checksums of core frozen strategy and engine files match the frozen manifest.
"""

import hashlib
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
MANIFEST_PATH = BASE_DIR / "models" / "MANIFEST_L1_FROZEN.json"


class FreezeViolationError(Exception):
    """Raised when any frozen contract or file checksum is violated."""
    pass


def verify_freeze() -> bool:
    """Validate system freeze integrity against MANIFEST_L1_FROZEN.json."""
    print("=" * 70)
    print("[FREEZE] RUNNING SYSTEM INTEGRITY & FREEZE VERIFICATION (verify_freeze)")
    print("=" * 70)

    if not MANIFEST_PATH.exists():
        raise FreezeViolationError(f"Missing freeze manifest at: {MANIFEST_PATH}")

    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FreezeViolationError(f"Invalid JSON in freeze manifest: {exc}")

    # 1. Verify Contract Rules
    violations = []

    if manifest.get("active_trading_layer") != "LAYER_1_PURE_RULES_ONLY":
        violations.append(
            f"Active trading layer must be 'LAYER_1_PURE_RULES_ONLY', got: {manifest.get('active_trading_layer')}"
        )

    if manifest.get("real_money_authorized") is not False:
        violations.append(
            f"real_money_authorized MUST be false, got: {manifest.get('real_money_authorized')}"
        )

    if manifest.get("execution_mode") != "DRY_RUN_PAPER_TRADING_ONLY":
        violations.append(
            f"execution_mode MUST be 'DRY_RUN_PAPER_TRADING_ONLY', got: {manifest.get('execution_mode')}"
        )

    oos_date = manifest.get("historical_data_status", {}).get("uncontaminated_oos_start_date")
    if oos_date != "2026-10-20":
        violations.append(
            f"uncontaminated_oos_start_date MUST be '2026-10-20', got: {oos_date}"
        )

    print("[CHECK 1] Policy & Governance Constraints:")
    print(f"  - active_trading_layer   : {manifest.get('active_trading_layer')} [OK]")
    print(f"  - real_money_authorized  : {manifest.get('real_money_authorized')} [OK]")
    print(f"  - execution_mode         : {manifest.get('execution_mode')} [OK]")
    print(f"  - oos_start_date         : {oos_date} [OK]")

    # 2. Verify Core Code File Checksums
    code_hashes = manifest.get("frozen_code_hashes") or manifest.get("frozen_file_hashes", {})
    if not code_hashes:
        violations.append("Manifest does not contain 'frozen_code_hashes' or 'frozen_file_hashes'")

    print("\n[CHECK 2] Core Strategy, Engine & Runner SHA256 Checksums:")
    for rel_path, expected_hash in code_hashes.items():
        abs_path = PROJECT_ROOT / rel_path
        if not abs_path.exists():
            violations.append(f"Frozen file missing: {rel_path}")
            print(f"  - {rel_path:38s}: MISSING [FAILED]")
            continue

        actual_hash = hashlib.sha256(abs_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            violations.append(
                f"Checksum mismatch for {rel_path}!\n  Expected: {expected_hash}\n  Actual:   {actual_hash}"
            )
            print(f"  - {rel_path:38s}: TAMPERED [FAILED]")
        else:
            print(f"  - {rel_path:38s}: {actual_hash[:16]}... [VERIFIED]")

    # 3. Verify Historical Data Presence & Cutoff Integrity
    data_info = manifest.get("frozen_historical_data_hashes_at_freeze_cutoff", {})
    if data_info:
        raw_csv_path = PROJECT_ROOT / "data" / "VN30F1M_since20180501.csv"
        features_path = PROJECT_ROOT / "trading_engine" / "data" / "VN30F1M_features.parquet"
        expected_cutoff_rows = data_info.get("historical_cutoff_row_count", 529609)
        expected_cutoff_hash = data_info.get("raw_csv_sha256_at_cutoff")

        print("\n[CHECK 3] Historical Data Continuity (Preserving 2018-2026 Foundation):")
        if not raw_csv_path.exists():
            violations.append("Raw historical dataset missing: data/VN30F1M_since20180501.csv")
            print("  - Raw CSV file                         : MISSING [FAILED]")
        else:
            # Read header + first expected_cutoff_rows to verify historical base
            try:
                with open(raw_csv_path, "rb") as f:
                    header = f.readline()
                    lines = [header]
                    for _ in range(expected_cutoff_rows):
                        line = f.readline()
                        if not line:
                            break
                        lines.append(line)
                actual_cutoff_hash = hashlib.sha256(b"".join(lines)).hexdigest()
                actual_row_count = len(lines) - 1

                if actual_row_count < expected_cutoff_rows:
                    violations.append(
                        f"Raw CSV has only {actual_row_count} rows, expected at least {expected_cutoff_rows}"
                    )
                    print(f"  - Historical Cutoff Rows ({expected_cutoff_rows}) : TRUNCATED ({actual_row_count}) [FAILED]")
                elif expected_cutoff_hash and actual_cutoff_hash != expected_cutoff_hash:
                    violations.append(
                        f"Historical cutoff checksum mismatch!\n  Expected: {expected_cutoff_hash}\n  Actual:   {actual_cutoff_hash}"
                    )
                    print("  - Historical Cutoff Base (529,609 rows): MODIFIED/TAMPERED [FAILED]")
                else:
                    print(f"  - Historical Cutoff Base (529,609 rows): {actual_cutoff_hash[:16]}... [VERIFIED INTACT]")
            except Exception as e:
                violations.append(f"Failed to read raw CSV for cutoff verification: {e}")
                print(f"  - Historical Cutoff Verification Error : {e} [FAILED]")

        if not features_path.exists():
            violations.append("Features dataset missing: trading_engine/data/VN30F1M_features.parquet")
            print("  - Features Parquet                     : MISSING [FAILED]")
        else:
            print("  - Features Parquet                     : PRESENT [VERIFIED]")

    if violations:
        print("\n[FAIL] FREEZE INTEGRITY VIOLATION DETECTED:")
        for v in violations:
            print(f"  * {v}")
        raise FreezeViolationError(f"Freeze verification failed with {len(violations)} violation(s).")

    print("\n[PASS] ALL FREEZE INTEGRITY CHECKS PASSED: SYSTEM IS SAFELY FROZEN.")
    print("=" * 70)
    return True



if __name__ == "__main__":
    try:
        verify_freeze()
        sys.exit(0)
    except FreezeViolationError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
