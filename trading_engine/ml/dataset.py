"""Build the labelled training dataset from the current feature parquet."""

from pathlib import Path

import numpy as np
import pandas as pd

from ..logging_config import logger
from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from .schema import ML_FEATURE_COLUMNS

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
DATASET_PATH = BASE_DIR / "data" / "ml_dataset.csv"


def build_ml_dataset(
    features_path: Path = FEATURES_PATH,
    output_path: Path = DATASET_PATH,
    buy_threshold: float = 40,
    sell_threshold: float = -40,
    tp_atr_multiplier: float = DEFAULT_BACKTEST_CONFIG.take_profit_atr,
    sl_atr_multiplier: float = DEFAULT_BACKTEST_CONFIG.stop_loss_atr,
    trailing_stop_atr: float = DEFAULT_BACKTEST_CONFIG.trailing_stop_atr,
    hard_sl_multiplier: float = getattr(DEFAULT_BACKTEST_CONFIG, "hard_sl_atr_mult", 2.5),
    horizon_bars: int | None = DEFAULT_BACKTEST_CONFIG.max_holding_bars,
) -> pd.DataFrame:
    """Create execution-aligned labels from the feature parquet.

    Each candidate is simulated as one standard contract using the active
    backtest's ATR exits, dynamic trailing stop, slippage, fees, and time
    limit. ``label == 1`` means its realized net PnL is positive after costs.

    Contract sizing is deliberately fixed at one: live sizing depends on prior
    portfolio equity, which cannot be part of an independent ML label.
    """
    if horizon_bars is None:
        horizon_bars = 240  # Đầy đủ 1 phiên giao dịch nếu không dùng TimeLimit 50 phút
    if not features_path.exists():
        raise FileNotFoundError(f"Feature file not found:\n{features_path}")

    logger.info("Loading feature parquet for dataset generation: %s", features_path)
    features = pd.read_parquet(features_path).copy()
    required = {"datetime", "High", "Low", "Close", "TrendScore", *ML_FEATURE_COLUMNS}
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError(f"Feature parquet is missing required columns: {missing}")

    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    usable_columns = ["High", "Low", "Close", *ML_FEATURE_COLUMNS]
    features = features.dropna(subset=usable_columns).reset_index(drop=True)

    # Build candidate population combining Wyckoff StrategySignals (Option 1 & 2)
    # and TrendScore threshold crossings.
    strategy_signal = features["StrategySignal"].to_numpy() if "StrategySignal" in features.columns else np.zeros(len(features), dtype=int)
    trend_score_buy = features["TrendScore"].to_numpy() >= buy_threshold
    trend_score_sell = features["TrendScore"].to_numpy() <= sell_threshold

    signals = np.select(
        [
            (strategy_signal == 1) | trend_score_buy,
            (strategy_signal == -1) | trend_score_sell,
        ],
        [1, -1],
        default=0,
    ).astype(int)



    highs = features["High"].to_numpy()
    lows = features["Low"].to_numpy()
    closes = features["Close"].to_numpy()
    atrs = features["ATR"].to_numpy()
    atrs_5m = features["HTF_5m_ATR"].to_numpy() if "HTF_5m_ATR" in features.columns else atrs * 2.0
    atrs_15m = features["HTF_15m_ATR"].to_numpy() if "HTF_15m_ATR" in features.columns else atrs * 3.0
    entry_setups = features["EntrySetup"].to_numpy() if "EntrySetup" in features.columns else np.array([""] * len(features))
    times = features["datetime"].to_numpy()
    feature_values = features[ML_FEATURE_COLUMNS].to_numpy()
    records: list[dict] = []

    for position in np.flatnonzero(signals):
        if position + horizon_bars >= len(features):
            continue
        signal, atr = signals[position], atrs[position]
        if not np.isfinite(atr) or atr <= 0:
            continue

        setup = str(entry_setups[position])
        if ("UTAD" in setup) or ("SPRING" in setup):
            trade_atr = atrs_15m[position]
        else:
            trade_atr = atrs_5m[position]

        # Same execution price used when BacktestEngine opens a position.
        entry_price = closes[position] + signal * DEFAULT_BACKTEST_CONFIG.slippage_points
        take_profit = entry_price + signal * tp_atr_multiplier * trade_atr
        stop_loss = entry_price - signal * sl_atr_multiplier * trade_atr
        trailing_stop = stop_loss
        exit_position, raw_exit_price, exit_reason = (
            position + horizon_bars, closes[position + horizon_bars], "TimeLimit" if DEFAULT_BACKTEST_CONFIG.max_holding_bars else "EndOfHorizon"
        )

        for future_position in range(position + 1, position + horizon_bars + 1):
            # BacktestEngine also evaluates stop loss before take profit when
            # both barriers are touched within one candle.
            if signal == 1:
                hard_sl = entry_price - hard_sl_multiplier * sl_atr_multiplier * trade_atr
                if lows[future_position] <= hard_sl:
                    exit_position, raw_exit_price, exit_reason = future_position, hard_sl, "SL"
                    break
                elif trailing_stop >= entry_price and lows[future_position] <= trailing_stop:
                    exit_position, raw_exit_price, exit_reason = future_position, trailing_stop, "SL"
                    break
                elif lows[future_position] <= trailing_stop:
                    is_15m_down = (
                        features.at[future_position, "HTF_15m_TrendDownOK"] == 1
                        or features.at[future_position, "HTF_15m_TrendTransitionDown"] == 1
                    )
                    if is_15m_down:
                        exit_position, raw_exit_price, exit_reason = future_position, trailing_stop, "SL"
                        break
            if signal == -1:
                hard_sl = entry_price + hard_sl_multiplier * sl_atr_multiplier * trade_atr
                if highs[future_position] >= hard_sl:
                    exit_position, raw_exit_price, exit_reason = future_position, hard_sl, "SL"
                    break
                elif trailing_stop <= entry_price and highs[future_position] >= trailing_stop:
                    exit_position, raw_exit_price, exit_reason = future_position, trailing_stop, "SL"
                    break
                elif highs[future_position] >= trailing_stop:
                    is_15m_rev = (
                        features.at[future_position, "HTF_15m_TrendOK"] == 1
                        or (features.at[future_position, "HTF_15m_TrendDownOK"] == 0 and features.at[future_position, "HTF_15m_TrendTransitionDown"] == 0)
                    )
                    if is_15m_rev:
                        exit_position, raw_exit_price, exit_reason = future_position, trailing_stop, "SL"
                        break
            if signal == 1 and highs[future_position] >= take_profit:
                exit_position, raw_exit_price, exit_reason = future_position, take_profit, "TP"
                break
            if signal == -1 and lows[future_position] <= take_profit:
                exit_position, raw_exit_price, exit_reason = future_position, take_profit, "TP"
                break

            # A close-derived trailing stop becomes active on the next candle.
            # Updating it before testing this candle would introduce look-ahead.
            if signal == 1:
                future_atr = atrs_5m[future_position]
                if np.isfinite(future_atr) and future_atr > 0:
                    trailing_stop = max(trailing_stop, closes[future_position] - trailing_stop_atr * future_atr)
            else:
                future_atr = atrs_5m[future_position]
                if np.isfinite(future_atr) and future_atr > 0:
                    trailing_stop = min(trailing_stop, closes[future_position] + trailing_stop_atr * future_atr)

        # Same exit slippage and one-contract PnL/fee calculation used by the
        # active backtest engine.
        exit_price = raw_exit_price - signal * DEFAULT_BACKTEST_CONFIG.slippage_points
        gross_pnl = (exit_price - entry_price) * signal * DEFAULT_BACKTEST_CONFIG.point_multiplier
        fees = 2 * DEFAULT_BACKTEST_CONFIG.commission_per_contract
        net_pnl = gross_pnl - fees
        label = int(net_pnl > 0)

        record = {
            "entry_time": times[position], "entry_price": entry_price,
            "signal": signal, "sl": stop_loss, "tp": take_profit,
            "exit_time": times[exit_position], "exit_price": exit_price,
            "exit_reason": exit_reason, "gross_pnl": gross_pnl,
            "fees": fees, "net_pnl": net_pnl, "label": label,
            "market_regime": features.at[position, "MarketRegime"],
        }
        record.update(dict(zip(ML_FEATURE_COLUMNS, feature_values[position], strict=True)))
        records.append(record)

    dataset = pd.DataFrame(records)
    if dataset.empty:
        raise ValueError("No labelable candidates were generated from the feature parquet.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)
    logger.info("ML dataset written to %s | rows=%d | positive_ratio=%.2f%%", output_path, len(dataset), dataset["label"].mean() * 100)
    return dataset


def main() -> None:
    build_ml_dataset()


if __name__ == "__main__":
    main()
