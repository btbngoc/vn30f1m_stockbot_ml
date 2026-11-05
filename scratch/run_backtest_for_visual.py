import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, ".")

import json
import numpy as np
import pandas as pd
import xgboost as xgb

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import XGBOOST_PARAMS, FEATURES_PATH, DATASET_PATH
from trading_engine.backtest.config import BacktestConfig

dataset = pd.read_csv(DATASET_PATH)
dataset["entry_time"] = pd.to_datetime(dataset["entry_time"])
dataset["exit_time"] = pd.to_datetime(dataset["exit_time"])
features = pd.read_parquet(FEATURES_PATH)
features["datetime"] = pd.to_datetime(features["datetime"])

FOLDS = [
    ("Fold 1 (OOS 2024)", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), 0.55),
    ("Fold 2 (OOS 2025)", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), 0.50),
    ("Fold 3 (OOS 2026)", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), None, 0.55),
]

cfg_real = BacktestConfig(slippage_points=0.30, commission_per_contract=15000.0, fixed_contracts=1, take_profit_atr=None, trailing_stop_atr=1.5, stop_loss_atr=1.0, hard_sl_atr_mult=2.5, max_holding_bars=None, cooldown_bars=15)

def round_tick(price: float) -> float:
    return round(price * 10.0) / 10.0

class BacktestWithDetailLogs:
    def __init__(self, df: pd.DataFrame, config: BacktestConfig, stop_mode: str = "soft_15m"):
        self.df = df
        self.config = config
        self.stop_mode = stop_mode
        self.trade_log = []

    def run(self):
        position = 0
        entry_price = entry_date = None
        contracts = 1
        initial_sl = trailing_sl = hard_sl = 0.0
        confidence = 1.0
        cooldown_remaining = 0
        bars_held = 0

        for timestamp, row in self.df.iterrows():
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
            signal = int(row.get("Signal", 0))
            op, close, high, low = row["Open"], row["Close"], row["High"], row["Low"]

            if position:
                bars_held += 1
                atr = row.get("ATR", 0.0)
                raw_exit = None
                reason = None

                if position == 1:
                    if low <= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl >= entry_price and low <= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
                    elif low <= trailing_sl:
                        htf_rev_down = (row.get("HTF_15m_TrendDownOK", 0) == 1 or row.get("HTF_15m_TrendTransitionDown", 0) == 1)
                        if htf_rev_down:
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == -1:
                        raw_exit, reason = close, "Reversal"
                else:
                    if high >= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_price and high >= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
                    elif high >= trailing_sl:
                        htf_rev = (row.get("HTF_15m_TrendOK", 0) == 1 or (row.get("HTF_15m_TrendDownOK", 1) == 0 and row.get("HTF_15m_TrendTransitionDown", 1) == 0))
                        if htf_rev:
                            raw_exit, reason = trailing_sl, "SL"
                    elif signal == 1:
                        raw_exit, reason = close, "Reversal"

                if raw_exit is None and atr > 0:
                    trailing_atr = float(row.get("HTF_5m_ATR", atr * 2.0))
                    if position == 1:
                        trailing_sl = max(trailing_sl, round_tick(close - self.config.trailing_stop_atr * trailing_atr))
                    else:
                        trailing_sl = min(trailing_sl, round_tick(close + self.config.trailing_stop_atr * trailing_atr))

                if raw_exit is not None:
                    actual_exit_base = raw_exit
                    is_atc = (timestamp.hour == 14 and timestamp.minute == 45)

                    if reason in ("Hard_SL", "SL"):
                        if position == 1 and op < raw_exit: actual_exit_base = op
                        elif position == -1 and op > raw_exit: actual_exit_base = op

                    slip = 0.0 if is_atc else self.config.slippage_points
                    exit_price = round_tick(actual_exit_base - position * slip)

                    gross_pnl = (exit_price - entry_price) * position * contracts * self.config.point_multiplier
                    fees = 2 * contracts * self.config.commission_per_contract
                    net_pnl = gross_pnl - fees
                    pts = (exit_price - entry_price) * position
                    is_overnight = (entry_date.date() != timestamp.date())

                    self.trade_log.append({
                        "id": len(self.trade_log) + 1,
                        "entry_time": str(entry_date),
                        "exit_time": str(timestamp),
                        "type": "LONG" if position == 1 else "SHORT",
                        "entry_price": float(entry_price),
                        "exit_price": float(exit_price),
                        "initial_sl": float(initial_sl),
                        "hard_sl": float(hard_sl),
                        "exit_sl": float(trailing_sl),
                        "points": float(round(pts, 2)),
                        "net_pnl": float(round(net_pnl, 0)),
                        "reason": str(reason),
                        "is_overnight": bool(is_overnight),
                        "bars_held": int(bars_held),
                        "confidence": float(round(confidence, 4))
                    })
                    position = 0
                    cooldown_remaining = self.config.cooldown_bars
                    continue

            if position == 0 and signal and cooldown_remaining == 0:
                atr = row.get("ATR", 0.0)
                if atr <= 0:
                    continue
                position = signal
                entry_date = timestamp
                entry_price = round_tick(close + position * self.config.slippage_points)
                setup = str(row.get("EntrySetup", ""))
                if "SPRING" in setup or "UTAD" in setup:
                    trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0)))
                else:
                    trade_atr = float(row.get("HTF_5m_ATR", atr * 2.0))

                initial_sl = round_tick(entry_price - position * self.config.stop_loss_atr * trade_atr)
                trailing_sl = initial_sl
                hsl_mult = getattr(self.config, "hard_sl_atr_mult", 2.5)
                hard_sl = round_tick(entry_price - position * hsl_mult * self.config.stop_loss_atr * trade_atr)
                confidence = float(row.get("Confidence", 1.0))
                bars_held = 0

        return pd.DataFrame(self.trade_log)

all_trades = []
# Dùng Seed 42 làm đại diện trực quan hóa các điểm vào ra
for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
    train = dataset[dataset["exit_time"] < val_start]
    p = XGBOOST_PARAMS.copy()
    p["random_state"] = 42
    m = xgb.XGBClassifier(**p)
    m.fit(train[ML_FEATURE_COLUMNS], train["label"])

    period = features[features["datetime"] >= test_start].copy()
    if test_end is not None:
        period = period[period["datetime"] < test_end].copy()
    period["Confidence"] = m.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    strat = period["StrategySignal"].astype(int)
    sig = pd.Series(0, index=period.index, dtype=int)
    sig[(strat == 1) & (period["Confidence"] >= th)] = 1
    sig[(strat == -1) & (period["Confidence"] >= th)] = -1
    period["Signal"] = sig

    engine = BacktestWithDetailLogs(period.set_index("datetime"), config=cfg_real, stop_mode="soft_15m")
    tr = engine.run()
    if not tr.empty:
        tr["fold"] = name
        all_trades.append(tr)

trades_df = pd.concat(all_trades, ignore_index=True)
trades_df["id"] = range(1, len(trades_df) + 1)
print(f"Tổng số lệnh OOS 2024-2026: {len(trades_df)}")
print(f"Tổng Net PnL: {trades_df['net_pnl'].sum():>+12,.0f} VND")
print(f"Tỷ lệ thắng: {len(trades_df[trades_df['net_pnl'] > 0]) / len(trades_df) * 100:.1f}%")

# Lưu danh sách lệnh
trades_df.to_csv("results/all_trades_visualize.csv", index=False)
print("Đã lưu results/all_trades_visualize.csv")

