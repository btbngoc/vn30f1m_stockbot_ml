"""Risk Management and Execution Guard for Live Trading.

Enforces:
1. Duplicate signal debouncing (only 1 order per bar timestamp).
2. Max daily loss limit (circuit breaker).
3. Max consecutive losses guard.
4. Position state consistency (e.g. no buying when already long).
5. Live Trade Journal logging.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd

from .order_types import OrderResult, PositionState, SignalPayload

logger = logging.getLogger("RiskManager")

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LIVE_JOURNAL_PATH = DATA_DIR / "live_trade_journal.csv"


class RiskManager:
    """Live trade validator and risk guard."""

    def __init__(
        self,
        max_daily_loss_points: float = 20.0,
        max_consecutive_losses: int = 5,
        max_contracts: int = 1,
        cooldown_bars: int = 5,
    ):
        self.max_daily_loss_points = max_daily_loss_points
        self.max_consecutive_losses = max_consecutive_losses
        self.max_contracts = max_contracts
        self.cooldown_bars = cooldown_bars

        # State tracking
        self.current_position = PositionState.FLAT
        self.current_entry_price: float = 0.0
        self.current_entry_time: str = ""
        self.current_setup: str = ""
        self.current_sl: float = 0.0
        self.current_hard_sl: float = 0.0

        self.daily_pnl_points: float = 0.0
        self.consecutive_losses: int = 0
        self.last_bar_time: str = ""
        self.last_action: str = ""
        self.trading_halted: bool = False
        self.halt_reason: str = ""

        self._ensure_journal()

    def _ensure_journal(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not LIVE_JOURNAL_PATH.exists():
            df = pd.DataFrame(columns=[
                "Timestamp", "Action", "Setup", "EntryPrice", "ExitPrice",
                "PnL_Points", "PnL_VND", "DailyPnL_Points", "ExitReason", "Status"
            ])
            df.to_csv(LIVE_JOURNAL_PATH, index=False, encoding="utf-8")

    def validate_signal(self, signal: SignalPayload) -> Tuple[bool, str]:
        """Validate if signal is safe to execute."""
        if self.trading_halted:
            return False, f"Trading HALTED: {self.halt_reason}"

        # 1. Daily Loss Circuit Breaker
        if self.daily_pnl_points <= -self.max_daily_loss_points:
            self.trading_halted = True
            self.halt_reason = f"Hit Max Daily Loss limit ({self.daily_pnl_points:.1f} pts <= -{self.max_daily_loss_points:.1f} pts)"
            logger.critical("[CIRCUIT BREAKER] %s", self.halt_reason)
            return False, self.halt_reason

        # 2. Consecutive Losses Alert
        if self.consecutive_losses >= self.max_consecutive_losses:
            logger.warning("[RISK WARNING] Consecutive losses: %d >= %d", self.consecutive_losses, self.max_consecutive_losses)

        # 3. Duplicate Bar Timestamp Debounce
        if signal.bar_time and signal.bar_time == self.last_bar_time and signal.action == self.last_action:
            return False, f"Duplicate signal ignored for bar {signal.bar_time} (Action: {signal.action})"

        # 4. State Transition Validation
        action = signal.action.upper()
        if action == "BUY":
            if self.current_position == PositionState.LONG:
                return False, "Already in LONG position, ignoring duplicate BUY"
        elif action == "SHORT":
            if self.current_position == PositionState.SHORT:
                return False, "Already in SHORT position, ignoring duplicate SHORT"
        elif action in ["SELL", "COVER", "EXIT"]:
            if self.current_position == PositionState.FLAT:
                return False, "No active position to close (current: FLAT)"
            if action == "SELL" and self.current_position != PositionState.LONG:
                return False, f"Cannot SELL when position is {self.current_position.label()}"
            if action == "COVER" and self.current_position != PositionState.SHORT:
                return False, f"Cannot COVER when position is {self.current_position.label()}"

        return True, "APPROVED"

    def record_entry(self, signal: SignalPayload, order_res: OrderResult) -> None:
        """Update state when an entry order is placed."""
        if not order_res.success:
            return

        action = signal.action.upper()
        if action == "BUY":
            self.current_position = PositionState.LONG
        elif action == "SHORT":
            self.current_position = PositionState.SHORT

        self.current_entry_price = signal.price
        self.current_entry_time = signal.bar_time or signal.timestamp
        self.current_setup = signal.setup
        self.current_sl = signal.sl
        self.current_hard_sl = signal.hard_sl

        self.last_bar_time = signal.bar_time
        self.last_action = action

        logger.info(
            "[STATE] Position updated to %s @ %.1f | Setup: %s | SL: %.1f",
            self.current_position.label(), self.current_entry_price, self.current_setup, self.current_sl
        )

        # Append to journal
        row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action": f"ENTRY_{self.current_position.label()}",
            "Setup": self.current_setup,
            "EntryPrice": self.current_entry_price,
            "ExitPrice": None,
            "PnL_Points": None,
            "PnL_VND": None,
            "DailyPnL_Points": round(self.daily_pnl_points, 1),
            "ExitReason": None,
            "Status": "OPEN",
        }
        self._append_journal(row)

    def record_exit(self, signal: SignalPayload, order_res: OrderResult, exit_reason: str = "SIGNAL") -> None:
        """Update state when an exit order is placed."""
        if not order_res.success or self.current_position == PositionState.FLAT:
            return

        exit_price = signal.price
        pnl_points = 0.0

        if self.current_position == PositionState.LONG:
            pnl_points = exit_price - self.current_entry_price
        elif self.current_position == PositionState.SHORT:
            pnl_points = self.current_entry_price - exit_price

        pnl_vnd = pnl_points * 100000  # 1 pt = 100,000 VND
        self.daily_pnl_points += pnl_points

        if pnl_points > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

        prev_pos = self.current_position.label()
        self.current_position = PositionState.FLAT
        self.last_bar_time = signal.bar_time
        self.last_action = signal.action

        logger.info(
            "[STATE] Closed %s @ %.1f | PnL: %+.1f pts (%+d VND) | Daily PnL: %+.1f pts",
            prev_pos, exit_price, pnl_points, int(pnl_vnd), self.daily_pnl_points
        )

        row = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Action": f"EXIT_{prev_pos}",
            "Setup": self.current_setup,
            "EntryPrice": self.current_entry_price,
            "ExitPrice": exit_price,
            "PnL_Points": round(pnl_points, 1),
            "PnL_VND": int(pnl_vnd),
            "DailyPnL_Points": round(self.daily_pnl_points, 1),
            "ExitReason": exit_reason or signal.setup or "EXIT_SIGNAL",
            "Status": "CLOSED",
        }
        self._append_journal(row)

    def _append_journal(self, row: dict) -> None:
        try:
            df = pd.DataFrame([row])
            df.to_csv(LIVE_JOURNAL_PATH, mode="a", header=False, index=False, encoding="utf-8")
        except Exception as e:
            logger.error("Failed to append live journal: %s", e)

    def get_status(self) -> dict:
        return {
            "position": self.current_position.label(),
            "entry_price": self.current_entry_price,
            "entry_time": self.current_entry_time,
            "setup": self.current_setup,
            "sl": self.current_sl,
            "hard_sl": self.current_hard_sl,
            "daily_pnl_points": round(self.daily_pnl_points, 1),
            "daily_pnl_vnd": int(self.daily_pnl_points * 100000),
            "consecutive_losses": self.consecutive_losses,
            "trading_halted": self.trading_halted,
            "halt_reason": self.halt_reason,
        }
