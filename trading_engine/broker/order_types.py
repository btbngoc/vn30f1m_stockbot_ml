"""Data structures and types for real-time order execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, Optional


class PositionState(IntEnum):
    FLAT = 0
    LONG = 1
    SHORT = -1

    def label(self) -> str:
        if self == PositionState.LONG:
            return "LONG"
        if self == PositionState.SHORT:
            return "SHORT"
        return "FLAT"


@dataclass
class SignalPayload:
    symbol: str
    action: str  # "BUY", "SHORT", "SELL", "COVER"
    price: float
    setup: str = ""
    bar_time: str = ""
    sl: float = 0.0
    hard_sl: float = 0.0
    trailing_sl: float = 0.0
    volume: int = 1
    log_only: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SignalPayload:
        return cls(
            symbol=str(data.get("symbol", "VN30F1M")).upper(),
            action=str(data.get("action", "")).upper(),
            price=float(data.get("price", 0.0)),
            setup=str(data.get("setup", "")),
            bar_time=str(data.get("bar_time", "")),
            sl=float(data.get("sl", 0.0)),
            hard_sl=float(data.get("hard_sl", 0.0)),
            trailing_sl=float(data.get("trailing_sl", 0.0)),
            volume=int(data.get("volume", 1)),
            log_only=bool(data.get("log_only", False)),
            timestamp=str(data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "price": self.price,
            "setup": self.setup,
            "bar_time": self.bar_time,
            "sl": self.sl,
            "hard_sl": self.hard_sl,
            "trailing_sl": self.trailing_sl,
            "volume": self.volume,
            "log_only": self.log_only,
            "timestamp": self.timestamp,
        }


@dataclass
class OrderResult:
    success: bool
    status: str  # "SENT", "REJECTED", "SKIPPED", "ERROR"
    action: str
    symbol: str
    price: Any
    volume: int
    message: str
    order_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "action": self.action,
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume,
            "message": self.message,
            "order_id": self.order_id,
            "timestamp": self.timestamp,
        }
