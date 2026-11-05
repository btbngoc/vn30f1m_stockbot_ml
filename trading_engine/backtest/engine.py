import math

import pandas as pd

from .config import BacktestConfig, DEFAULT_BACKTEST_CONFIG
from .metrics import MetricsCalculator


class BacktestEngine:
    """Event-driven backtest using the same ATR exits as the ML labels."""

    def __init__(self, df: pd.DataFrame, config: BacktestConfig = DEFAULT_BACKTEST_CONFIG, initial_capital: float = 100_000_000.0):
        self.df = df
        self.config = config
        self.initial_capital = initial_capital
        self.trade_log: list[dict] = []

    def _contracts(self, entry_price: float, atr: float, equity: float, position: int = 1) -> int:
        if getattr(self.config, "fixed_contracts", None) is not None:
            return self.config.fixed_contracts
        risk_per_contract = atr * self.config.stop_loss_atr * self.config.point_multiplier
        if risk_per_contract <= 0:
            return 1
        capital_fraction = 0.70 if position == 1 else 0.30
        return max(1, math.floor(((equity * capital_fraction) * self.config.risk_per_trade) / risk_per_contract))

    def _exit_price_with_slippage(self, raw_price: float, position: int) -> float:
        return raw_price - position * self.config.slippage_points

    def _record_trade(self, entry_date, exit_date, position, entry_price, exit_price, contracts, reason, initial_sl, trailing_sl, tp, confidence):
        gross_pnl = (exit_price - entry_price) * position * contracts * self.config.point_multiplier
        fees = 2 * contracts * self.config.commission_per_contract
        net_pnl = gross_pnl - fees
        rec_tp = None if (tp is None or math.isinf(tp)) else tp
        self.trade_log.append({
            "Entry Date": entry_date,
            "Exit Date": exit_date,
            "Type": "LONG" if position == 1 else "SHORT",
            "Entry": entry_price,
            "Exit": exit_price,
            "Contracts": contracts,
            "Gross PnL": gross_pnl,
            "Fees": fees,
            "PnL": net_pnl,
            "Reason": reason,
            "Initial Stop Loss": initial_sl,
            "Stop Loss at Exit": trailing_sl,
            "Take Profit": rec_tp,
            "Confidence": confidence,
        })
        return net_pnl

    def run(self):
        position = 0
        entry_price = entry_date = None
        contracts = 0
        initial_sl = trailing_sl = hard_sl = tp = 0.0
        bars_held = 0
        cooldown_remaining = 0
        confidence = 1.0
        equity = self.initial_capital

        for timestamp, row in self.df.iterrows():
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
            signal = int(row.get("Signal", 0))
            close, high, low = row["Close"], row["High"], row["Low"]

            if position:
                bars_held += 1
                atr = row.get("ATR", 0.0)

                raw_exit = None
                reason = None
                # H-01 flat_before_atc rule:
                # Vị thế đang mở lúc 14:25 đóng ở giá mở cửa nến 14:25 ± slippage
                if self.config.flat_before_atc and (timestamp.hour == 14 and timestamp.minute >= 25):
                    raw_exit, reason = row["Open"], "Flat_Before_ATC"
                elif position == 1:
                    # LONG position exit logic (Symmetric với Short):
                    # 1. Emergency Hard SL (Cắt lỗ khẩn cấp bảo vệ cú sập bất ngờ)
                    if low <= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    # 2. In-profit trailing stop: khóa lãi ngay khi đã ở vùng có lời
                    elif trailing_sl >= entry_price and low <= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
                    # 3. Soft stop loss: chỉ cắt lỗ khi khung lớn 15m xác nhận đảo chiều giảm
                    elif low <= trailing_sl:
                        htf_reversal_down = (
                            row.get("HTF_15m_TrendDownOK", 0) == 1
                            or row.get("HTF_15m_TrendTransitionDown", 0) == 1
                        )
                        if htf_reversal_down:
                            raw_exit, reason = trailing_sl, "SL"
                    elif high >= tp:
                        raw_exit, reason = tp, "TP"
                    elif signal == -1:
                        raw_exit, reason = close, "Reversal"
                else:
                    # SHORT position exit logic:
                    # 1. Emergency Hard SL (catastrophic gap / spike protection)
                    if high >= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    # 2. In-profit or breakeven trailing stop: lock in profit immediately
                    elif trailing_sl <= entry_price and high >= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
                    # 3. Soft stop loss: only stop loss if HTF 15m confirms reversal
                    elif high >= trailing_sl:
                        htf_reversal = (
                            row.get("HTF_15m_TrendOK", 0) == 1
                            or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0)
                        )
                        if htf_reversal:
                            raw_exit, reason = trailing_sl, "SL"
                    elif low <= tp:
                        raw_exit, reason = tp, "TP"
                    elif signal == 1:
                        raw_exit, reason = close, "Reversal"

                if raw_exit is None and atr > 0:
                    trailing_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                    if position == 1:
                        trailing_sl = max(trailing_sl, close - self.config.trailing_stop_atr * trailing_atr)
                    else:
                        trailing_sl = min(trailing_sl, close + self.config.trailing_stop_atr * trailing_atr)

                # As with the close-derived trailing stop, breakeven is armed
                # only after this candle has completed.  It is therefore not
                # allowed to use this candle's high/low and then claim an exit
                # at breakeven inside that same candle.
                if raw_exit is None and self.config.breakeven_trigger_r is not None:
                    initial_risk = abs(entry_price - initial_sl)
                    trigger_distance = initial_risk * self.config.breakeven_trigger_r
                    if position == 1 and high >= entry_price + trigger_distance:
                        trailing_sl = max(trailing_sl, entry_price)
                    elif position == -1 and low <= entry_price - trigger_distance:
                        trailing_sl = min(trailing_sl, entry_price)


                if raw_exit is None and self.config.max_holding_bars is not None and bars_held >= self.config.max_holding_bars:
                    raw_exit, reason = close, "TimeLimit"

                if raw_exit is not None:
                    exit_price = self._exit_price_with_slippage(raw_exit, position)
                    equity += self._record_trade(entry_date, timestamp, position, entry_price, exit_price, contracts, reason, initial_sl, trailing_sl, tp, confidence)
                    position = 0
                    # Do not reverse or re-enter immediately after an exit.
                    cooldown_remaining = self.config.cooldown_bars
                    continue

            if position == 0 and signal and cooldown_remaining == 0:
                # H-01: Không mở lệnh mới từ 14:25
                if self.config.flat_before_atc and (timestamp.hour == 14 and timestamp.minute >= 25):
                    continue
                atr = row.get("ATR", 0.0)
                if atr <= 0:
                    continue
                position = signal
                entry_date = timestamp
                entry_price = close + position * self.config.slippage_points
                if position == 1:
                    setup = str(row.get("EntrySetup", ""))
                    if "SPRING" in setup:
                        trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0)))
                    else:
                        trade_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                else:
                    setup = str(row.get("EntrySetup", ""))
                    if "UTAD" in setup:
                        trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0)))
                    else:
                        trade_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                contracts = self._contracts(entry_price, trade_atr, equity, position)
                initial_sl = entry_price - position * self.config.stop_loss_atr * trade_atr
                trailing_sl = initial_sl
                hsl_mult = getattr(self.config, "hard_sl_atr_mult", 2.5)
                hard_sl = entry_price - position * hsl_mult * self.config.stop_loss_atr * trade_atr
                if self.config.take_profit_atr is not None:
                    tp = entry_price + position * self.config.take_profit_atr * trade_atr
                else:
                    tp = float("inf") if position == 1 else float("-inf")
                confidence = float(row.get("Confidence", 1.0))
                bars_held = 0

        if position:
            raw_exit = self.df.iloc[-1]["Close"]
            exit_price = self._exit_price_with_slippage(raw_exit, position)
            self._record_trade(entry_date, self.df.index[-1], position, entry_price, exit_price, contracts, "End of Data", initial_sl, trailing_sl, tp, confidence)

        return pd.DataFrame(self.trade_log)

    def get_metrics(self):
        return MetricsCalculator.calculate_all(pd.DataFrame(self.trade_log), self.initial_capital)
