import sys
sys.path.insert(0, ".")
import math
import json
from pathlib import Path
import pandas as pd
import numpy as np
import xgboost as xgb

sys.stdout.reconfigure(encoding='utf-8')

from trading_engine.ml.schema import ML_FEATURE_COLUMNS
from trading_engine.ml.train import DATASET_PATH, FEATURES_PATH, XGBOOST_PARAMS
from trading_engine.backtest.engine import BacktestEngine
from trading_engine.backtest.config import BacktestConfig

dataset = pd.read_csv(DATASET_PATH)
dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
features = pd.read_parquet(FEATURES_PATH)
features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")

FOLDS = [
    ("Fold 1 (OOS 2024)", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), 0.55),
    ("Fold 2 (OOS 2025)", pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), 0.50),
    ("Fold 3 (OOS 2026)", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01"), None, 0.55),
]

# Train models with fixed random_state = 42
trained_models = []
for (name, val_start, test_start, test_end, th) in FOLDS:
    train = dataset[dataset["exit_time"] < val_start]
    params = XGBOOST_PARAMS.copy()
    params["random_state"] = 42
    model = xgb.XGBClassifier(**params)
    model.fit(train[ML_FEATURE_COLUMNS], train["label"])
    trained_models.append(model)

# Engine with Gap-Aware support
class GapAwareBacktestEngine(BacktestEngine):
    def __init__(self, df, config, gap_aware=False):
        super().__init__(df, config)
        self.gap_aware = gap_aware

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
            op, close, high, low = row["Open"], row["Close"], row["High"], row["Low"]

            if position:
                bars_held += 1
                atr = row.get("ATR", 0.0)
                raw_exit = None
                reason = None

                if self.config.flat_before_atc and (timestamp.hour == 14 and timestamp.minute >= 25):
                    raw_exit, reason = row["Open"], "Flat_Before_ATC"
                elif position == 1:
                    if low <= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl >= entry_price and low <= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
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
                    if high >= hard_sl:
                        raw_exit, reason = hard_sl, "Hard_SL"
                    elif trailing_sl <= entry_price and high >= trailing_sl:
                        raw_exit, reason = trailing_sl, "SL"
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

                if raw_exit is not None:
                    # Gap-aware execution
                    actual_exit_base = raw_exit
                    if self.gap_aware and reason in ("Hard_SL", "SL"):
                        if position == 1 and op < raw_exit:
                            actual_exit_base = op
                        elif position == -1 and op > raw_exit:
                            actual_exit_base = op

                    exit_price = actual_exit_base - position * self.config.slippage_points
                    equity += self._record_trade(entry_date, timestamp, position, entry_price, exit_price, contracts, reason, initial_sl, trailing_sl, tp, confidence)
                    position = 0
                    cooldown_remaining = self.config.cooldown_bars
                    continue

            if position == 0 and signal and cooldown_remaining == 0:
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
                    trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "SPRING" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
                else:
                    setup = str(row.get("EntrySetup", ""))
                    trade_atr = float(row.get("HTF_15m_ATR", row.get("HTF_5m_ATR", atr * 3.0))) if "UTAD" in setup else float(row.get("HTF_5m_ATR", atr * 2.0))
                contracts = self._contracts(entry_price, trade_atr, equity, position)
                initial_sl = entry_price - position * self.config.stop_loss_atr * trade_atr
                trailing_sl = initial_sl
                hsl_mult = getattr(self.config, "hard_sl_atr_mult", 2.5)
                hard_sl = entry_price - position * hsl_mult * self.config.stop_loss_atr * trade_atr
                tp = float("inf") if position == 1 else float("-inf")
                confidence = float(row.get("Confidence", 1.0))
                bars_held = 0

        if position:
            raw_exit = self.df.iloc[-1]["Close"]
            exit_price = raw_exit - position * self.config.slippage_points
            self._record_trade(entry_date, self.df.index[-1], position, entry_price, exit_price, contracts, "End of Data", initial_sl, trailing_sl, tp, confidence)

        return pd.DataFrame(self.trade_log)

def evaluate_fold(model, features, test_start, test_end, threshold, slippage, gap_aware):
    period = features[features["datetime"] >= test_start].copy()
    if test_end is not None:
        period = period[period["datetime"] < test_end].copy()
    probability = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    period["Confidence"] = probability
    strategy_signal = period["StrategySignal"].astype(int)
    pass_long = period["Confidence"] >= threshold
    pass_short = period["Confidence"] >= threshold
    short_regime_gate = (
        (period["MarketRegime"] == "TREND_DOWN")
        | (period.get("HTF_15m_TrendDownOK", 0) == 1)
        | (period.get("HTF_15m_TrendTransitionDown", 0) == 1)
    )
    trade_signal = pd.Series(0, index=period.index, dtype=int)
    trade_signal[(strategy_signal == 1) & pass_long] = 1
    trade_signal[(strategy_signal == -1) & pass_short & short_regime_gate] = -1
    period["Signal"] = trade_signal

    cfg = BacktestConfig(slippage_points=slippage)
    engine = GapAwareBacktestEngine(period.set_index("datetime"), config=cfg, gap_aware=gap_aware)
    trades = engine.run()
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "max_drawdown": 0.0}
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    drawdown = (trades["PnL"].cumsum().cummax() - trades["PnL"].cumsum()).max()
    return {
        "trades": int(len(trades)),
        "net_pnl": float(trades["PnL"].sum()),
        "gross_profit": float(wins),
        "gross_loss": float(losses),
        "profit_factor": float(wins / losses) if losses > 0 else 0.0,
        "win_rate": float((trades["PnL"] > 0).mean()),
        "max_drawdown": float(drawdown),
        "trades_df": trades
    }

if __name__ == "__main__":
    scenarios = [
        ("Base (Nominal SL, Slip 0.1 pt)", 0.10, False),
        ("Gap-Aware (Slip 0.1 pt)", 0.10, True),
        ("Gap-Aware (Slip 0.3 pt)", 0.30, True),
        ("Gap-Aware (Slip 0.6 pt)", 0.60, True),
    ]

    print("=== EXACT WALK-FORWARD RESULTS ===")
    for sc_name, slip, gap in scenarios:
        fold_metrics = []
        for idx, (name, val_start, test_start, test_end, th) in enumerate(FOLDS):
            m = evaluate_fold(trained_models[idx], features, test_start, test_end, th, slip, gap)
            fold_metrics.append((name, m))
        
        total_trades = sum(m["trades"] for _, m in fold_metrics)
        total_pnl = sum(m["net_pnl"] for _, m in fold_metrics)
        total_gw = sum(m["gross_profit"] for _, m in fold_metrics)
        total_gl = sum(m["gross_loss"] for _, m in fold_metrics)
        total_pf = total_gw / total_gl if total_gl > 0 else 0.0
        worst_dd = max(m["max_drawdown"] for _, m in fold_metrics)

        print(f"\n--- {sc_name} ---")
        for fname, m in fold_metrics:
            print(f"  {fname:18s} | N={m['trades']:2d} | Win={m['win_rate']*100:4.1f}% | Net PnL={m['net_pnl']:+12,.0f} VND | PF={m['profit_factor']:4.2f} | Max DD={m['max_drawdown']:10,.0f} VND")
        print(f"  {'TỔNG HỢP OOS':18s} | N={total_trades:2d} | Net PnL={total_pnl:+12,.0f} VND | PF={total_pf:4.2f} | Worst DD={worst_dd:10,.0f} VND")

