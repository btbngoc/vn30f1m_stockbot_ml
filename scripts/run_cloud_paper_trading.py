"""
VN30F1M Institutional Algorithmic Paper Trading — Cloud Production Daemon
Milestone P17 — OCI Cloud Deployment & Connection Runtime

Pipeline Topology:
    DNSE Live WebSocket (wss://ws-openapi.dnse.com.vn)
    -> DNSEMarketDataConnector (P16.01)
    -> DNSEDataAdapter (P16.02)
    -> PaperTradingPipeline (P15.06)
        -> Data Integrity Monitor (P15.02)
        -> Regime Runtime Engine (P15.03)
        -> Signal Engine (P15.04A)
        -> Risk Engine (P15.04B)
        -> Paper Execution Engine (P15.05B)
    -> SQLite WAL Mode (/var/lib/vn30f1m/data/paper_trading.db)

Operational Invariants:
- PAPER TRADING ONLY — ZERO REAL CAPITAL RISK — ZERO LIVE TRADING API.
- Single-writer process lock enforced via /run/vn30f1m/vn30f1m.pid.
- Automatic reconnection with exponential backoff and fresh HMAC nonces.
- Graceful shutdown on SIGTERM/SIGINT with clean SQLite WAL checkpoint.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import websockets

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dnse_market_data_connector import (
    ChannelType,
    ConnectionState,
    DNSEWebSocketClient,
    OHLCClosedEvent,
    OHLCEvent,
    QuoteEvent,
    TradeEvent,
    TIMEZONE_ICT,
    TIMEZONE_UTC,
)
from src.dnse_data_adapter import AdapterConfig, AdapterEventStatus, DNSEDataAdapter
from src.paper_trading_pipeline import PaperTradingPipeline, PipelineConfig

# Logging configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("VN30CloudTradingDaemon")


def load_env_credentials() -> tuple[str, str]:
    """Loads DNSE credentials from environment or .env file."""
    api_key = os.environ.get("DNSE_API_KEY", "").strip()
    api_secret = os.environ.get("DNSE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        env_file = PROJECT_ROOT / ".env"
        if env_file.is_file():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k == "DNSE_API_KEY" and not api_key:
                        api_key = v
                    elif k == "DNSE_API_SECRET" and not api_secret:
                        api_secret = v

    return api_key, api_secret


class SingleWriterLock:
    """Enforces exclusive single-writer execution via POSIX file lock."""

    def __init__(self, lock_path: str):
        self.lock_path = lock_path
        self._fp = None

    def acquire(self) -> bool:
        try:
            Path(self.lock_path).parent.mkdir(parents=True, exist_ok=True)
            self._fp = open(self.lock_path, "w")
            fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fp.write(f"{os.getpid()}\n")
            self._fp.flush()
            return True
        except (IOError, OSError) as e:
            logger.error("Failed to acquire single-writer lock on %s: %s", self.lock_path, e)
            return False

    def release(self) -> None:
        if self._fp and not self._fp.closed:
            try:
                fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
                self._fp.close()
                self._fp = None
                if os.path.exists(self.lock_path):
                    os.remove(self.lock_path)
            except Exception as e:
                logger.warning("Error releasing lock: %s", e)


class LiveWebSocketTransportAdapter:
    """Thread-safe adapter for websockets library delegating to asyncio loop."""

    def __init__(self, ws: websockets.WebSocketClientProtocol, loop: asyncio.AbstractEventLoop):
        self._ws = ws
        self._loop = loop

    def send(self, data: str) -> None:
        asyncio.run_coroutine_threadsafe(self._ws.send(data), self._loop)

    def close(self) -> None:
        asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)


class CloudHealthTracker:
    """Real-time operational health and pipeline telemetry tracker."""

    def __init__(self, health_file_path: str = "/run/vn30f1m/health.json"):
        self.health_file_path = health_file_path
        self.start_time = time.time()
        self.last_heartbeat_time: float = time.time()

        # Four Operational Connection States (Section B Verification)
        self.is_connected: bool = False
        self.is_authenticated: bool = False
        self.is_subscribed: bool = False
        self.is_data_received: bool = False

        # Health & Pipeline Metrics (Section C Verification)
        self.last_market_event: Optional[Dict[str, Any]] = None
        self.last_completed_15m_candle: Optional[Dict[str, Any]] = None
        self.last_pipeline_execution: Optional[Dict[str, Any]] = None
        self.last_database_commit_time: Optional[float] = None

        self.total_events_processed: int = 0
        self.total_bars_completed: int = 0
        self.total_pipeline_steps: int = 0
        self.total_db_commits: int = 0
        self.exception_count: int = 0
        self.duplicate_event_count: int = 0
        self.concurrency_limit_hits: int = 0
        self.last_seen_sequence: int = -1
        self.last_error: Optional[str] = None

    def update_states(self, connector: Optional[DNSEWebSocketClient]) -> None:
        if not connector or not hasattr(connector, "lifecycle"):
            return
        state = connector.lifecycle.state
        if state in (ConnectionState.CONNECTED, ConnectionState.AUTHENTICATING, ConnectionState.AUTHENTICATED, ConnectionState.SUBSCRIBED):
            self.is_connected = True
        else:
            self.is_connected = False
            self.is_authenticated = False
            self.is_subscribed = False

        if state in (ConnectionState.AUTHENTICATED, ConnectionState.SUBSCRIBED):
            self.is_authenticated = True

        if state == ConnectionState.SUBSCRIBED:
            self.is_subscribed = True

    def to_dict(self) -> Dict[str, Any]:
        now_ts = time.time()
        ict_offset = timezone(timedelta(hours=7))

        if self.is_data_received:
            stage = "DATA_RECEIVED"
        elif self.is_subscribed:
            stage = "SUBSCRIBED"
        elif self.is_authenticated:
            stage = "AUTHENTICATED"
        elif self.is_connected:
            stage = "CONNECTED"
        else:
            stage = "DISCONNECTED"

        last_db_str = None
        if self.last_database_commit_time:
            last_db_str = datetime.fromtimestamp(self.last_database_commit_time, ict_offset).strftime("%Y-%m-%d %H:%M:%S ICT")

        return {
            "stage": stage,
            "states": {
                "1_CONNECTED": self.is_connected,
                "2_AUTHENTICATED": self.is_authenticated,
                "3_SUBSCRIBED": self.is_subscribed,
                "4_DATA_RECEIVED": self.is_data_received,
            },
            "uptime_seconds": round(now_ts - self.start_time, 1),
            "last_heartbeat_utc": datetime.fromtimestamp(self.last_heartbeat_time, timezone.utc).isoformat(),
            "last_heartbeat_ict": datetime.fromtimestamp(self.last_heartbeat_time, ict_offset).strftime("%Y-%m-%d %H:%M:%S ICT"),
            "last_market_event": self.last_market_event,
            "last_completed_15m_candle": self.last_completed_15m_candle,
            "last_pipeline_execution": self.last_pipeline_execution,
            "last_database_commit_ict": last_db_str,
            "counters": {
                "total_events_processed": self.total_events_processed,
                "total_bars_completed": self.total_bars_completed,
                "total_pipeline_steps": self.total_pipeline_steps,
                "total_db_commits": self.total_db_commits,
                "exception_count": self.exception_count,
                "duplicate_events": self.duplicate_event_count,
                "concurrency_limit_hits": self.concurrency_limit_hits,
            },
            "last_error": self.last_error,
        }

    def write_snapshot(self) -> None:
        try:
            p = Path(self.health_file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = p.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            tmp_path.replace(p)
        except Exception as e:
            logger.warning("Error writing health snapshot: %s", e)


class CloudPaperTradingDaemon:
    """Production service daemon managing market data streaming and paper execution."""

    def __init__(
        self,
        db_path: str = "/var/lib/vn30f1m/data/paper_trading.db",
        symbol: str = "VN30F1M",
        lock_path: str = "/run/vn30f1m/vn30f1m.pid",
        health_path: Optional[str] = None,
        audit_path: Optional[str] = None,
    ):
        self.symbol = symbol
        self.db_path = db_path
        self.lock_path = lock_path
        self.health_path = health_path
        self.audit_path = audit_path
        self.lock = SingleWriterLock(lock_path)
        self.is_running = False
        self._is_shut_down = False
        self._sleep_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self.pipeline: Optional[PaperTradingPipeline] = None
        self.adapter: Optional[DNSEDataAdapter] = None
        self.connector: Optional[DNSEWebSocketClient] = None
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

        if health_path:
            health_file = health_path
        else:
            health_file = "/run/vn30f1m/health.json" if os.path.exists("/run/vn30f1m") else str(PROJECT_ROOT / "health.json")
        self.tracker = CloudHealthTracker(health_file_path=health_file)

    def initialize_pipeline(self) -> None:
        """Initializes the P15.06 Pipeline with persistent SQLite WAL storage."""
        # Ensure directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Initializing PaperTradingPipeline with DB: %s", self.db_path)
        config = PipelineConfig(
            db_path=self.db_path,
            auto_recover=True,
            warmup_bars=20,
            v_point=100_000.0,
            default_contracts=1,
            enable_eod_flatten=False,  # OCI Swing Mode: Cho phép giữ lệnh qua đêm (Max Profit)
            take_profit_rr=10.0,       # Candidate TP 10.0x ATR: Tối ưu lợi nhuận cho 1 HĐ
        )
        self.pipeline = PaperTradingPipeline(config=config)
        self.tracker.last_database_commit_time = time.time()

        # Initialize Adapter connecting to Pipeline
        adapter_cfg = AdapterConfig(
            target_symbol=self.symbol,
            target_resolution_minutes=15,
        )
        self.adapter = DNSEDataAdapter(config=adapter_cfg, pipeline=self.pipeline)
        logger.info("DNSEDataAdapter initialized. Auto-recover state: %s", self.pipeline.state.value)

    def setup_callbacks(self) -> None:
        """Connects DNSEMarketDataConnector callbacks to Adapter and Logging."""
        assert self.connector is not None
        assert self.adapter is not None

        def on_trade(event: TradeEvent) -> None:
            now_ts = time.time()
            freshness = now_ts - event.timestamp_utc.timestamp()
            if event.sequence_id <= self.tracker.last_seen_sequence and event.sequence_id > 0:
                self.tracker.duplicate_event_count += 1
            self.tracker.last_seen_sequence = max(self.tracker.last_seen_sequence, event.sequence_id)
            self.tracker.is_data_received = True
            self.tracker.total_events_processed += 1
            self.tracker.last_market_event = {
                "type": "TradeEvent",
                "symbol": event.symbol,
                "price": event.price,
                "volume": event.volume,
                "side": event.side,
                "sequence_id": event.sequence_id,
                "event_timestamp_ict": event.timestamp_ict.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "freshness_seconds": round(freshness, 3),
                "is_stale": abs(freshness) > 60.0,
            }
            t_str = event.timestamp_ict.strftime("%H:%M:%S.%f")[:-3]
            logger.info("[TRADE] %s | Price: %7.1f | Vol: %3d | Side: %4s | Seq: %6d | ICT: %s",
                        event.symbol, event.price, event.volume, event.side, event.sequence_id, t_str)
            self.adapter.ingest_event(event)

        def on_quote(event: QuoteEvent) -> None:
            self.tracker.is_data_received = True
            self.tracker.total_events_processed += 1
            self.tracker.last_market_event = {
                "type": "QuoteEvent",
                "symbol": event.symbol,
                "event_timestamp_ict": event.timestamp_ict.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "freshness_seconds": round(time.time() - event.timestamp_utc.timestamp(), 3),
            }
            self.adapter.ingest_event(event)

        def on_ohlc(event: OHLCEvent) -> None:
            self.tracker.is_data_received = True
            self.tracker.total_events_processed += 1
            self.tracker.last_market_event = {
                "type": "OHLCEvent",
                "resolution": event.resolution,
                "open": event.open, "high": event.high, "low": event.low, "close": event.close, "volume": event.volume,
                "event_timestamp_ict": event.timestamp_ict.strftime("%Y-%m-%d %H:%M:%S"),
            }
            logger.info("[OHLC %s FORMING] O:%.1f H:%.1f L:%.1f C:%.1f Vol:%d",
                        event.resolution, event.open, event.high, event.low, event.close, event.volume)
            self.adapter.ingest_event(event)

        def on_ohlc_closed(event: OHLCClosedEvent) -> None:
            self.tracker.total_bars_completed += 1
            self.tracker.last_completed_15m_candle = {
                "resolution": event.resolution,
                "open": event.open, "high": event.high, "low": event.low, "close": event.close, "volume": event.volume,
                "bar_close_time_ict": event.timestamp_ict.strftime("%Y-%m-%d %H:%M:%S"),
            }
            logger.info("[OHLC %s CLOSED] O:%.1f H:%.1f L:%.1f C:%.1f Vol:%d -> Ingesting to Pipeline",
                        event.resolution, event.open, event.high, event.low, event.close, event.volume)
            res = self.adapter.ingest_event(event)
            if res.status == AdapterEventStatus.ACCEPTED and res.pipeline_result:
                action = res.pipeline_result.get("action_taken", "NONE")
                pos = res.pipeline_result.get("position_state", "FLAT")
                equity = res.pipeline_result.get("final_capital", 0.0)
                self.tracker.total_pipeline_steps += 1
                self.tracker.total_db_commits += 1
                self.tracker.last_database_commit_time = time.time()
                self.tracker.last_pipeline_execution = {
                    "timestamp_ict": datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S"),
                    "action": action,
                    "position": pos,
                    "equity": equity,
                }
                logger.info("[PIPELINE STEP] Action: %s | Pos: %s | Equity: %s VND", action, pos, f"{equity:,.0f}")

        self.connector.register_on_trade(on_trade)
        self.connector.register_on_quote(on_quote)
        self.connector.register_on_ohlc(on_ohlc)
        self.connector.register_on_ohlc_closed(on_ohlc_closed)

    async def _heartbeat_loop(self) -> None:
        """Periodic background task refreshing health telemetry snapshot every 15s."""
        logger.info("Operational Health Monitor & Heartbeat loop started.")
        ticks = 0
        while self.is_running:
            try:
                self.tracker.last_heartbeat_time = time.time()
                self.tracker.update_states(self.connector)
                self.tracker.write_snapshot()
                ticks += 1
                if ticks % 4 == 0:  # Every 60s
                    st = self.tracker.to_dict()
                    logger.info(
                        "[HEARTBEAT] Stage: %s | Uptime: %.0fs | Events: %d | 15m Bars: %d | Pipeline: %d | DB Commits: %d | Exceptions: %d",
                        st["stage"], st["uptime_seconds"],
                        st["counters"]["total_events_processed"],
                        st["counters"]["total_bars_completed"],
                        st["counters"]["total_pipeline_steps"],
                        st["counters"]["total_db_commits"],
                        st["counters"]["exception_count"],
                    )
            except Exception as e:
                logger.warning("Error in heartbeat loop: %s", e)
            await asyncio.sleep(15.0)

    async def run(self) -> None:
        """Main execution loop with reconnect handling."""
        if not self.lock.acquire():
            logger.error("Another daemon instance is already running! Terminating.")
            sys.exit(1)

        api_key, api_secret = load_env_credentials()
        if not api_key or not api_secret:
            logger.error("DNSE_API_KEY and DNSE_API_SECRET must be configured!")
            sys.exit(1)

        self.initialize_pipeline()

        if self.audit_path:
            audit_file = Path(self.audit_path)
            audit_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            audit_dir = Path("/var/log/vn30f1m/audit")
            audit_dir.mkdir(parents=True, exist_ok=True)
            audit_file = audit_dir / "dnse_cloud_audit.jsonl"

        self.connector = DNSEWebSocketClient(
            symbol=self.symbol,
            api_key=api_key,
            api_secret=api_secret,
            audit_file_path=str(audit_file),
            auto_auth=True,
        )
        self.setup_callbacks()

        # Build subscriptions
        self.connector.subscriptions.build_subscription_payload(
            channels=[ChannelType.TRADE, ChannelType.QUOTES, ChannelType.OHLC, ChannelType.OHLC_CLOSED],
            symbol=self.symbol,
            action="subscribe",
        )

        self.is_running = True
        loop = asyncio.get_running_loop()
        backoff_sec = 5.0

        # Start periodic health & telemetry snapshot task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info("Starting Cloud Market Data & Paper Trading loop for %s...", self.symbol)

        while self.is_running:
            connected_at = 0.0
            try:
                ws_url = self.connector.ws_url
                logger.info("Connecting to DNSE Gateway: %s", ws_url)

                async with websockets.connect(ws_url, ping_interval=None) as ws:
                    self._ws = ws
                    transport = LiveWebSocketTransportAdapter(ws, loop)
                    self.connector.attach_mock_transport(transport)
                    connected_at = time.time()
                    self.tracker.update_states(self.connector)
                    self.tracker.write_snapshot()

                    logger.info("WebSocket connected! Listening for live market events...")

                    async for message in ws:
                        if not self.is_running:
                            break
                        raw_str = message if isinstance(message, str) else message.decode("utf-8")
                        self.connector.handle_raw_message(raw_str)
                        self.tracker.update_states(self.connector)

                        # Reset backoff if connection has survived stably for at least 30s
                        if time.time() - connected_at > 30.0:
                            backoff_sec = 5.0

            except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e:
                logger.warning("WebSocket connection closed: %s. Reconnecting in %.1fs...", e, backoff_sec)
                self.tracker.update_states(self.connector)
            except Exception as e:
                self.tracker.exception_count += 1
                self.tracker.last_error = str(e)
                logger.error("Unexpected error in streaming loop: %s. Reconnecting in %.1fs...", e, backoff_sec)

            # Check if gateway rejected due to concurrency limit
            last_reason = getattr(self.connector.lifecycle, "_last_disconnect_reason", "")
            if "MAX_CONNECTIONS_EXCEEDED" in last_reason or "max connections exceeded" in last_reason.lower():
                self.tracker.concurrency_limit_hits += 1
                backoff_sec = max(backoff_sec, 60.0)
                logger.warning("DNSE concurrency limit reached. Enforcing %.1fs backoff to drain sessions.", backoff_sec)

            self.tracker.update_states(self.connector)
            self.tracker.write_snapshot()

            if self.is_running:
                logger.info("Awaiting %.1fs backoff before next connection attempt...", backoff_sec)
                try:
                    self._sleep_task = asyncio.create_task(asyncio.sleep(backoff_sec))
                    await self._sleep_task
                except asyncio.CancelledError:
                    logger.info("Sleep interrupted by cancellation.")
                    break
                finally:
                    self._sleep_task = None
                backoff_sec = min(backoff_sec * 2.0, 120.0)

        self.shutdown()

    def shutdown(self) -> None:
        """Performs clean shutdown, flushes SQLite WAL, and releases lock."""
        if self._is_shut_down:
            return
        self._is_shut_down = True
        logger.info("Initiating graceful shutdown...")
        self.is_running = False

        if self._sleep_task and not self._sleep_task.done():
            self._sleep_task.cancel()

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

        if self.connector:
            try:
                self.connector.disconnect(reason="Daemon shutdown")
            except Exception as e:
                logger.warning("Error disconnecting connector: %s", e)

        if self.pipeline:
            try:
                logger.info("Closing PaperTradingPipeline and flushing SQLite WAL...")
                self.pipeline.close()
                logger.info("SQLite WAL flushed and database closed cleanly.")
            except Exception as e:
                logger.error("Error closing pipeline: %s", e)

        try:
            self.tracker.update_states(self.connector)
            self.tracker.write_snapshot()
        except Exception:
            pass

        self.lock.release()
        logger.info("Daemon shutdown complete.")


def handle_signals(daemon: CloudPaperTradingDaemon) -> None:
    def _sig_handler(sig: int, frame: Any) -> None:
        logger.info("Received termination signal %s. Triggering shutdown...", sig)
        daemon.is_running = False
        if daemon._sleep_task and not daemon._sleep_task.done():
            daemon._sleep_task.cancel()

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)


def main() -> None:
    import argparse

    default_db = os.getenv("BOT_DB_PATH")
    if not default_db:
        default_db = "/var/lib/vn30f1m/data/paper_trading.db" if os.path.exists("/var/lib/vn30f1m") else str(PROJECT_ROOT / "data" / "paper_trading.db")

    default_lock = os.getenv("BOT_LOCK_PATH")
    if not default_lock:
        default_lock = "/run/vn30f1m/vn30f1m.pid" if os.path.exists("/run/vn30f1m") else str(PROJECT_ROOT / "vn30f1m.pid")

    default_health = os.getenv("BOT_HEALTH_FILE")
    if not default_health:
        default_health = "/run/vn30f1m/health.json" if os.path.exists("/run/vn30f1m") else str(PROJECT_ROOT / "health.json")

    default_audit = os.getenv("BOT_AUDIT_FILE")

    parser = argparse.ArgumentParser(description="VN30F1M Cloud Paper Trading Daemon")
    parser.add_argument("--db-path", default=default_db, help="Path to SQLite database")
    parser.add_argument("--lock-path", default=default_lock, help="Path to single-writer lockfile")
    parser.add_argument("--health-file", default=default_health, help="Path to health status json file")
    parser.add_argument("--audit-file", default=default_audit, help="Path to market data audit jsonl file")
    args = parser.parse_args()

    daemon = CloudPaperTradingDaemon(
        db_path=args.db_path,
        lock_path=args.lock_path,
        health_path=args.health_file,
        audit_path=args.audit_file,
    )
    handle_signals(daemon)

    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Terminated by user keyboard interrupt.")
    finally:
        daemon.shutdown()


if __name__ == "__main__":
    main()
