#!/usr/bin/env python3
"""
VN30F1M Cloud to Local Chart Bridge (Dual-Bot Edition)
Synchronizes live SQLite WAL databases from OCI Cloud (Bot 1 & Bot 2)
and exports ASCII CSV feeds for AmiBroker and Quant Terminal.

Outputs to D:\Amibroker\:
1. vn30f1m.csv       -> 15m OHLCV bars (Format: Ticker, YYYYMMDD, HHMMSS, O, H, L, C, V)
2. signals.csv        -> Active signal & position of Bot 1 (Legacy compatibility)
3. bot1_signals.csv   -> Active position & latest order of Bot 1 (REGIME-ROUTER-02)
4. bot1_trades.csv    -> Closed trade ledger & PnL points of Bot 1
5. bot2_signals.csv   -> Active position & latest order of Bot 2 (Router-D / Directional)
6. bot2_trades.csv    -> Closed trade ledger & PnL points of Bot 2
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_AMIBROKER_DIR = Path("D:/Amibroker")
SSH_KEY_PATH = PROJECT_ROOT / "oci_key.key"
CLOUD_HOST = "opc@161.33.147.149"

BOT1_CLOUD_DIR = "/var/lib/vn30f1m/data"
BOT2_CLOUD_DIR = "/opt/vn30f1m-bot2/data"

LOCAL_BOT1_DIR = PROJECT_ROOT / "data" / "bot1"
LOCAL_BOT2_DIR = PROJECT_ROOT / "data" / "bot2"


def fetch_bot_data(cloud_dir: str, local_dir: Path) -> bool:
    """Fetches all SQLite database files (.db, .db-wal, .db-shm) via scp."""
    local_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "scp",
        "-i", str(SSH_KEY_PATH),
        "-o", "StrictHostKeyChecking=no",
        f"{CLOUD_HOST}:{cloud_dir}/paper_trading.db*",
        str(local_dir)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.returncode == 0
    except Exception as e:
        print(f"[ERROR] Failed to fetch data from {cloud_dir}: {e}")
        return False


def export_bars(db_path: Path, output_csv: Path) -> int:
    """Exports processed 15m OHLCV bars in AmiBroker ASCII format."""
    if not db_path.exists():
        return 0

    count = 0
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT bar_timestamp, open, high, low, close, volume FROM processed_bars ORDER BY bar_timestamp ASC;")
        rows = cursor.fetchall()
        if rows:
            with open(output_csv, "w", encoding="utf-8") as f:
                for row in rows:
                    raw_ts = str(row[0])
                    try:
                        dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                        ymd = dt.strftime("%Y%m%d")
                        hms = dt.strftime("%H%M%S")
                    except Exception:
                        ymd = "20261114"
                        hms = "091500"
                    f.write(f"VN30F1M,{ymd},{hms},{row[1]:.1f},{row[2]:.1f},{row[3]:.1f},{row[4]:.1f},{int(row[5])}\n")
            count = len(rows)
        conn.close()
    except Exception as e:
        print(f"[WARN] Error exporting bars from {db_path.name}: {e}")
    return count


def export_bot_state(db_path: Path, bot_tag: str, signals_file: Path, trades_file: Path) -> None:
    """Exports active position and trade ledger for a specific bot."""
    if not db_path.exists():
        return

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()

        # 1. Export Active Position
        cursor.execute("SELECT direction, quantity, average_entry_price, updated_at, total_commission_paid, total_slippage_paid FROM positions ORDER BY id DESC LIMIT 1;")
        pos_row = cursor.fetchone()
        with open(signals_file, "w", encoding="utf-8") as f:
            f.write("symbol,bot,direction,quantity,entry_price,timestamp\n")
            if pos_row and pos_row[1] > 0:
                dir_str = "LONG" if pos_row[0] == 1 or pos_row[0] == "LONG" else ("SHORT" if pos_row[0] == -1 or pos_row[0] == "SHORT" else "FLAT")
                f.write(f"VN30F1M,{bot_tag},{dir_str},{pos_row[1]},{pos_row[2]},{pos_row[3]}\n")
            else:
                f.write(f"VN30F1M,{bot_tag},FLAT,0,0.0,{datetime.now().isoformat()}\n")

        # 2. Export Trade Ledger
        cursor.execute("SELECT trade_id, setup_id, direction, quantity, entry_time, exit_time, fill_entry_price, fill_exit_price, net_pnl_pts, net_pnl_vnd, exit_reason FROM trades ORDER BY trade_id ASC;")
        trade_rows = cursor.fetchall()
        with open(trades_file, "w", encoding="utf-8") as f:
            f.write("trade_id,setup_id,direction,qty,entry_time,exit_time,entry_price,exit_price,net_pnl_pts,net_pnl_vnd,exit_reason\n")
            for t in trade_rows:
                f.write(f"{t[0]},{t[1]},{t[2]},{t[3]},{t[4]},{t[5]},{t[6]},{t[7]},{t[8]},{t[9]},{t[10]}\n")

        conn.close()
    except Exception as e:
        print(f"[WARN] Error exporting state for {bot_tag}: {e}")


def sync_cycle() -> None:
    LOCAL_AMIBROKER_DIR.mkdir(parents=True, exist_ok=True)
    ts_now = datetime.now().strftime("%H:%M:%S")

    # Fetch Bot 1
    b1_ok = fetch_bot_data(BOT1_CLOUD_DIR, LOCAL_BOT1_DIR)
    # Fetch Bot 2
    b2_ok = fetch_bot_data(BOT2_CLOUD_DIR, LOCAL_BOT2_DIR)

    b1_db = LOCAL_BOT1_DIR / "paper_trading.db"
    b2_db = LOCAL_BOT2_DIR / "paper_trading.db"

    # Export bars from Bot 1 (or Bot 2 fallback)
    bars_count = export_bars(b1_db, LOCAL_AMIBROKER_DIR / "vn30f1m.csv")
    if bars_count == 0 and b2_db.exists():
        bars_count = export_bars(b2_db, LOCAL_AMIBROKER_DIR / "vn30f1m.csv")

    # Export Bot 1 state
    export_bot_state(
        b1_db, "BOT1",
        LOCAL_AMIBROKER_DIR / "bot1_signals.csv",
        LOCAL_AMIBROKER_DIR / "bot1_trades.csv"
    )
    # Legacy signals.csv mirror
    if (LOCAL_AMIBROKER_DIR / "bot1_signals.csv").exists():
        with open(LOCAL_AMIBROKER_DIR / "bot1_signals.csv") as sf:
            lines = sf.readlines()
        with open(LOCAL_AMIBROKER_DIR / "signals.csv", "w") as lf:
            lf.write("symbol,direction,quantity,entry_price,timestamp\n")
            if len(lines) > 1:
                parts = lines[1].strip().split(",")
                # VN30F1M,BOT1,DIR,QTY,PRICE,TS -> VN30F1M,DIR,QTY,PRICE,TS
                if len(parts) >= 6:
                    lf.write(f"{parts[0]},{parts[2]},{parts[3]},{parts[4]},{parts[5]}\n")

    # Export Bot 2 state
    export_bot_state(
        b2_db, "BOT2",
        LOCAL_AMIBROKER_DIR / "bot2_signals.csv",
        LOCAL_AMIBROKER_DIR / "bot2_trades.csv"
    )

    print(f"[{ts_now}] [SYNC COMPLETED] Bars: {bars_count} | Bot1: {'OK' if b1_ok else 'FAIL'} | Bot2: {'OK' if b2_ok else 'FAIL'} -> D:\\Amibroker\\")


def main():
    parser = argparse.ArgumentParser(description="VN30F1M Cloud to Local AmiBroker Sync Bridge")
    parser.add_argument("--watch", action="store_true", help="Keep running and sync periodically")
    parser.add_argument("--interval", type=int, default=30, help="Sync interval in seconds (default: 30s)")
    args = parser.parse_args()

    print("============================================================================")
    print("  VN30F1M CLOUD TO AMIBROKER DUAL-BOT BRIDGE")
    print(f"  Target Destination : {LOCAL_AMIBROKER_DIR}")
    print("============================================================================")

    if args.watch:
        print(f"[WATCH MODE] Continuous auto-sync active (Interval: {args.interval}s). Press Ctrl+C to stop.")
        while True:
            sync_cycle()
            time.sleep(args.interval)
    else:
        sync_cycle()
        print("[DONE] Charts and signals updated in D:\\Amibroker\\.")


if __name__ == "__main__":
    main()
