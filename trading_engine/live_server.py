"""Live Webhook Trading Server.

Receives real-time trading signals from AmiBroker (VN30F1M_Wyckoff_Strategy.afl),
validates them against Risk Manager, routes orders to AmiX (DNSE),
and maintains a live journal.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from .broker.amix_client import AmiXClient
from .broker.order_types import SignalPayload
from .broker.risk_manager import RiskManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LiveTradingServer")


class LiveServerState:
    """Singleton container holding engine components."""
    client: AmiXClient
    risk: RiskManager


state = LiveServerState()


class SignalWebhookHandler(BaseHTTPRequestHandler):
    """HTTP Handler processing AmiBroker webhooks."""

    def _send_json_response(self, status_code: int, data: Dict[str, Any]) -> None:
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.error("Failed to write response: %s", e)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/status" or self.path == "/":
            amix_health = state.client.health_check()
            risk_status = state.risk.get_status()
            res = {
                "server": "AmiBroker-Python-AmiX Realtime Bridge",
                "status": "RUNNING",
                "amix_connection": amix_health,
                "risk_engine": risk_status,
                "config": {
                    "account": state.client.account,
                    "loan_id": state.client.loan_id,
                    "dry_run": state.client.dry_run,
                    "price_mode": state.client.price_mode,
                },
            }
            self._send_json_response(200, res)
        elif self.path == "/health":
            self._send_json_response(200, {"status": "OK"})
        else:
            self._send_json_response(404, {"error": "Endpoint not found"})

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")

        if self.path == "/webhook/signal":
            try:
                payload = json.loads(raw_body) if raw_body else {}
                signal = SignalPayload.from_dict(payload)
                logger.info(
                    "--> [WEBHOOK RECEIVED] Action: %s | Symbol: %s | Price: %.1f | BarTime: %s | Setup: %s",
                    signal.action, signal.symbol, signal.price, signal.bar_time, signal.setup
                )

                # Handle PING_TEST from AmiBroker
                if signal.action.upper() == "PING_TEST":
                    logger.info("[PING_TEST] AmiBroker connection PING verified successfully at %.1f | BarTime: %s", signal.price, signal.bar_time)
                    self._send_json_response(200, {
                        "success": True,
                        "status": "PING_OK",
                        "message": "AmiBroker to Python connection is ACTIVE and HEALTHY!",
                        "timestamp": signal.timestamp,
                    })
                    return

                action = signal.action.upper()

                # Handle LOG_ONLY signals (from Dual Mode: AmiX executes direct, Python monitors)
                if signal.log_only or action.startswith("LOG_"):
                    clean_action = action.replace("LOG_", "")
                    logger.info("[LOG ONLY SIGNAL] Received %s @ %.1f | BarTime: %s (No duplicate broker order)", clean_action, signal.price, signal.bar_time)
                    if clean_action in ["BUY", "LONG"]:
                        state.risk.current_position = 1
                    elif clean_action in ["SHORT"]:
                        state.risk.current_position = -1
                    else:
                        state.risk.current_position = 0

                    self._send_json_response(200, {
                        "success": True,
                        "status": "LOGGED_ONLY",
                        "message": f"Signal {clean_action} logged for monitoring without duplicate order placement.",
                        "risk_status": state.risk.get_status(),
                    })
                    return

                # 1. Validate with Risk Manager
                is_safe, reason = state.risk.validate_signal(signal)
                if not is_safe:
                    logger.warning("[RISK REJECTED] %s", reason)
                    self._send_json_response(200, {
                        "success": False,
                        "status": "REJECTED",
                        "reason": reason,
                        "signal": signal.to_dict(),
                    })
                    return

                # 2. Route order to AmiX
                order_result = None

                if action == "BUY":
                    order_result = state.client.send_order(
                        side="NB", symbol=signal.symbol, price=signal.price, volume=signal.volume
                    )
                    state.risk.record_entry(signal, order_result)

                elif action == "SHORT":
                    order_result = state.client.send_order(
                        side="NS", symbol=signal.symbol, price=signal.price, volume=signal.volume
                    )
                    state.risk.record_entry(signal, order_result)

                elif action in ["SELL", "COVER", "EXIT"]:
                    # Close position via AmiX
                    order_result = state.client.close_all_deals(all_account=False)
                    state.risk.record_exit(signal, order_result, exit_reason=signal.setup or "EXIT_SIGNAL")

                else:
                    self._send_json_response(400, {"error": f"Unknown action: {action}"})
                    return

                logger.info("<-- [ORDER RESULT] %s", order_result.to_dict())
                self._send_json_response(200, {
                    "success": order_result.success,
                    "status": order_result.status,
                    "order": order_result.to_dict(),
                    "risk_status": state.risk.get_status(),
                })

            except Exception as e:
                logger.exception("Error processing signal webhook: %s", e)
                self._send_json_response(500, {"error": str(e)})

        elif self.path == "/close_emergency":
            logger.warning("[EMERGENCY] Close all deals requested manually!")
            res = state.client.close_all_deals(all_account=False)
            state.risk.current_position = 0
            self._send_json_response(200, {"result": res.to_dict()})

        else:
            self._send_json_response(404, {"error": "Endpoint not found"})

    def log_message(self, format: str, *args: Any) -> None:
        """Silence standard Apache request logging to keep console clean."""
        return


def run_live_server(
    port: int = 8000,
    amix_host: str = "http://localhost:7979",
    account: str = "",
    loan_id: str = "2403",
    dry_run: bool = False,
    price_mode: str = "MTL",
    max_daily_loss: float = 20.0,
) -> None:
    """Initialize and run the live trading server."""
    state.client = AmiXClient(
        base_url=amix_host,
        account=account,
        loan_id=loan_id,
        dry_run=dry_run,
        price_mode=price_mode,
    )
    state.risk = RiskManager(max_daily_loss_points=max_daily_loss)

    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, SignalWebhookHandler)

    mode_str = "DRY RUN (MOCK / PAPER)" if dry_run else "REAL TRADING (LIVE CAPITAL)"
    print("=" * 70)
    print("    [VN30F1M] LIVE TRADING SERVER (AMIBROKER <-> AMIX BRIDGE)")
    print("=" * 70)
    print(f" - Mode:             {mode_str}")
    print(f" - Webhook Server:   http://localhost:{port}/webhook/signal")
    print(f" - Status Endpoint:  http://localhost:{port}/status")
    print(f" - AmiX Port:        {amix_host}")
    print(f" - DNSE Account:     {account or '(Default from AmiX app)'}")
    print(f" - Loan ID:          {loan_id}")
    print(f" - Order Price Mode: {price_mode}")
    print(f" - Max Daily Loss:   {max_daily_loss} points")
    print("=" * 70)
    print(" Listening for Realtime signals from AmiBroker... (Ctrl+C to stop)")
    print("=" * 70)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOPPING] Shutting down Live Server...")
    finally:
        httpd.server_close()
        print("[STOPPED] Live Server stopped safely.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Webhook Trading Server for AmiBroker & AmiX")
    parser.add_argument("--port", type=int, default=8000, help="Local webhook port (default: 8000)")
    parser.add_argument("--amix-url", type=str, default="http://localhost:7979", help="AmiX base URL")
    parser.add_argument("--account", type=str, default="", help="DNSE account number")
    parser.add_argument("--loan", type=str, default="2403", help="DNSE loan package ID")
    parser.add_argument("--dry-run", action="store_true", help="Run in mock/dry-run mode without sending real orders")
    parser.add_argument("--price-mode", type=str, default="MTL", choices=["MTL", "LO"], help="Order price mode")
    parser.add_argument("--max-loss", type=float, default=20.0, help="Max daily loss in points before auto-halt")

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
