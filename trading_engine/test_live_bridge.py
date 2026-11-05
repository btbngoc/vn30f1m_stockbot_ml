"""Unit and Integration Test for Live Trading Bridge."""

import json
import threading
import time
import requests

from trading_engine.broker.amix_client import AmiXClient
from trading_engine.broker.order_types import SignalPayload
from trading_engine.broker.risk_manager import RiskManager
from trading_engine.live_server import run_live_server, state


def test_dry_run_pipeline():
    print("[TEST 1] Testing AmiXClient Dry-Run Mode...")
    client = AmiXClient(dry_run=True, account="0001999999", loan_id="2403")
    health = client.health_check()
    assert health["connected"] is True, f"Health check failed: {health}"

    buy_res = client.send_order(side="NB", symbol="VN30F1M", price="MTL", volume=1)
    assert buy_res.success is True, f"Buy order failed: {buy_res}"
    print("  -> Buy Order Result:", buy_res.message)

    close_res = client.close_all_deals()
    assert close_res.success is True
    print("  -> Close Deals Result:", close_res.message)
    print("  [PASSED] AmiXClient test successful!\n")


def test_risk_manager_state():
    print("[TEST 2] Testing RiskManager Validation & Debouncing...")
    rm = RiskManager(max_daily_loss_points=15.0, max_consecutive_losses=3)

    sig1 = SignalPayload(
        symbol="VN30F1M", action="BUY", price=1250.0, setup="Spring",
        bar_time="2026-10-19 09:15:00", sl=1245.0, hard_sl=1240.0
    )
    ok, reason = rm.validate_signal(sig1)
    assert ok is True, f"Initial signal should be approved: {reason}"

    # Simulate entry
    client = AmiXClient(dry_run=True)
    order_res = client.send_order(side="NB", price=sig1.price)
    rm.record_entry(sig1, order_res)
    assert rm.current_position == 1, "Position should be LONG"

    # Duplicate signal test
    ok_dup, reason_dup = rm.validate_signal(sig1)
    assert ok_dup is False, "Duplicate bar signal must be rejected"
    print("  -> Duplicate Signal Guard:", reason_dup)

    # Exit signal test
    sig_exit = SignalPayload(
        symbol="VN30F1M", action="SELL", price=1258.0, setup="Trail_SL",
        bar_time="2026-10-19 09:30:00"
    )
    ok_exit, _ = rm.validate_signal(sig_exit)
    assert ok_exit is True
    order_exit = client.close_all_deals()
    rm.record_exit(sig_exit, order_exit, exit_reason="Trail_SL")
    assert rm.current_position == 0, "Position should be FLAT"
    assert rm.daily_pnl_points == 8.0, f"Expected +8 pts, got {rm.daily_pnl_points}"
    print(f"  -> Exit Recorded: PnL = +{rm.daily_pnl_points} pts (+{rm.daily_pnl_points * 100}k VND)")
    print("  [PASSED] RiskManager test successful!\n")


def test_http_webhook_server():
    print("[TEST 3] Testing Live Server Webhook HTTP API...")
    server_thread = threading.Thread(
        target=run_live_server,
        kwargs={"port": 8099, "dry_run": True, "account": "TEST001"},
        daemon=True,
    )
    server_thread.start()
    time.sleep(1.0)  # Wait for server to bind

    # 1. Health/Status Check
    resp = requests.get("http://localhost:8099/status", timeout=2.0)
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["status"] == "RUNNING"
    print("  -> /status check OK:", status_data["risk_engine"]["position"])

    # 2. Post BUY Signal
    buy_payload = {
        "symbol": "VN30F1M",
        "action": "BUY",
        "price": 1260.5,
        "setup": "SOS Pullback",
        "bar_time": "2026-10-19 10:00:00",
        "sl": 1255.0,
        "hard_sl": 1250.0,
        "volume": 1
    }
    resp_buy = requests.post("http://localhost:8099/webhook/signal", json=buy_payload, timeout=2.0)
    assert resp_buy.status_code == 200
    buy_data = resp_buy.json()
    assert buy_data["success"] is True
    print("  -> /webhook/signal BUY OK:", buy_data["status"])

    # 3. Post Duplicate Signal
    resp_dup = requests.post("http://localhost:8099/webhook/signal", json=buy_payload, timeout=2.0)
    assert resp_dup.status_code == 200
    dup_data = resp_dup.json()
    assert dup_data["status"] == "REJECTED"
    print("  -> /webhook/signal DUPLICATE REJECTED OK:", dup_data["reason"])

    # 4. Post SELL Signal
    sell_payload = {
        "symbol": "VN30F1M",
        "action": "SELL",
        "price": 1265.0,
        "setup": "TakeProfit",
        "bar_time": "2026-10-19 10:15:00",
    }
    resp_sell = requests.post("http://localhost:8099/webhook/signal", json=sell_payload, timeout=2.0)
    assert resp_sell.status_code == 200
    sell_data = resp_sell.json()
    assert sell_data["success"] is True
    print("  -> /webhook/signal SELL OK. PnL:", sell_data["risk_status"]["daily_pnl_points"], "pts")

    print("  [PASSED] HTTP Webhook Server test successful!\n")


if __name__ == "__main__":
    test_dry_run_pipeline()
    test_risk_manager_state()
    test_http_webhook_server()
    print("=" * 60)
    print("[SUCCESS] ALL TESTS PASSED! Python Realtime Engine is fully functional!")
    print("=" * 60)
