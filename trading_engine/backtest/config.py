"""Shared execution assumptions for labels, validation, and backtests."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestConfig:
    point_multiplier: float = 100_000.0
    risk_per_trade: float = 0.01
    stop_loss_atr: float = 1.0
    take_profit_atr: float | None = None
    trailing_stop_atr: float = 1.5
    hard_sl_atr_mult: float = 2.5

    # Optional research-only protection.  ``None`` preserves the existing
    # execution behaviour; when set, a stop can move to entry after MFE has
    # reached this multiple of initial risk on a completed prior candle.
    breakeven_trigger_r: float | None = None
    max_holding_bars: int | None = None
    cooldown_bars: int = 15
    slippage_points: float = 0.10
    # Thuế, phí giao dịch và quản lý vị thế thực tế phái sinh VN30F1M (15,000 VND/chiều = 30,000 VND/round-trip)
    commission_per_contract: float = 15_000.0
    # Cố định khối lượng giao dịch 1 hợp đồng theo yêu cầu người dùng
    fixed_contracts: int = 1
    # H-01: Flat position at 14:25 open and block new entries from 14:25 onwards
    flat_before_atc: bool = False


DEFAULT_BACKTEST_CONFIG = BacktestConfig()
