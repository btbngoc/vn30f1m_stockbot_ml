"""Launcher for the VN30F1M Real-time Trading Engine (AmiBroker <-> AmiX Bridge)."""

import argparse
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from trading_engine.live_server import run_live_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Launch Python Trading Engine bridge connecting AmiBroker and AmiX (DNSE)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Local Webhook port for AmiBroker signals (default: 8000)"
    )
    parser.add_argument(
        "--amix-url", type=str, default="http://localhost:7979", help="AmiX base URL (default: http://localhost:7979)"
    )
    parser.add_argument(
        "--account", type=str, default="", help="DNSE derivative account ID (e.g. 0001177065)"
    )
    parser.add_argument(
        "--loan", type=str, default="2403", help="DNSE loan package ID (default: 2403)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Enable dry-run / paper mode without sending real orders"
    )
    parser.add_argument(
        "--price-mode", type=str, default="MTL", choices=["MTL", "LO"], help="Order price mode (MTL or LO)"
    )
    parser.add_argument(
        "--max-loss", type=float, default=20.0, help="Max daily loss points circuit breaker (default: 20.0)"
    )

    args = parser.parse_args()

    run_live_server(
        port=args.port,
        amix_host=args.amix_url,
        account=args.account,
        loan_id=args.loan,
        dry_run=args.dry_run,
        price_mode=args.price_mode,
        max_daily_loss=args.max_loss,
    )
