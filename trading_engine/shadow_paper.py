"""Forward-only shadow paper trade runner for candidate setups:
A) PULLBACK_15M_TREND (HTF 15m trend + 5m EMA20 pullback)
B) OPENING_RANGE_BREAK (09:00-09:15 ORB with RVOL >= 1.2, fixed 4pt stop)

Operates in shadow mode: does NOT touch the frozen primary journal (paper_trade_journal.csv)
or parallel research journal (paper_trade_journal_h01.csv).
Outputs to:
- trading_engine/data/paper_trade_journal_shadow.csv
- trading_engine/data/paper_trade_state_shadow.json
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd

from .backtest.config import DEFAULT_BACKTEST_CONFIG, BacktestConfig
from .logging_config import logger

BASE_DIR = Path(__file__).resolve().parent
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
JOURNAL_SHADOW_PATH = BASE_DIR / "data" / "paper_trade_journal_shadow.csv"
STATE_SHADOW_PATH = BASE_DIR / "data" / "paper_trade_state_shadow.json"

JOURNAL_COLUMNS = [
    "SignalTime",
    "Type",
    "SignalDirection",
    "Setup",
    "ExpectedPrice",
    "OpenNext",
    "OpenNextSlippage",
    "RealizedPrice",
    "RealizedSlippage",
    "InitialStop",
    "TakeProfit",
    "ATR",
    "Status",
    "WyckoffScore",
    "ExitTime",
    "Exit",
    "ExitPriceGapAware",
    "ExitReason",
    "PnL",
    "PnLGapAware",
]


def extract_candidate_signals(features: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Generate signal series for Setup A and Setup B with zero look-ahead bias."""
    df_sorted = features.sort_values("datetime").reset_index(drop=True)

    # 1. SETUP A: PULLBACK_15M_TREND
    df_5m = df_sorted.set_index("datetime").copy()
    bucket_5m = df_5m.index.floor("5min")
    htf_5m = df_5m.groupby(bucket_5m).agg(
        Open=("Open", "first"),
        High=("High", "max"),
        Low=("Low", "min"),
        Close=("Close", "last"),
    )
    htf_5m["EMA20"] = htf_5m["Close"].ewm(span=20, adjust=False).mean()
    htf_5m["Long_Pullback"] = (
        (htf_5m["Low"] <= htf_5m["EMA20"])
        & (htf_5m["Close"] > htf_5m["EMA20"])
        & (htf_5m["Close"] > htf_5m["Open"])
    )
    htf_5m["Short_Pullback"] = (
        (htf_5m["High"] >= htf_5m["EMA20"])
        & (htf_5m["Close"] < htf_5m["EMA20"])
        & (htf_5m["Close"] < htf_5m["Open"])
    )
    htf_5m_completed = htf_5m[["Long_Pullback", "Short_Pullback"]].shift(1).fillna(False)

    df_sorted["bucket_5m"] = df_sorted["datetime"].dt.floor("5min")
    df_sorted["is_5m_start"] = df_sorted["datetime"] == df_sorted["bucket_5m"]
    df_sorted["5m_Long_Pullback"] = df_sorted["bucket_5m"].map(htf_5m_completed["Long_Pullback"]).fillna(False).astype(bool)
    df_sorted["5m_Short_Pullback"] = df_sorted["bucket_5m"].map(htf_5m_completed["Short_Pullback"]).fillna(False).astype(bool)

    sig_a = pd.Series(0, index=df_sorted.index, dtype=int)
    cond_a_long = df_sorted["is_5m_start"] & (df_sorted.get("HTF_15m_TrendOK", 0) == 1) & df_sorted["5m_Long_Pullback"]
    cond_a_short = df_sorted["is_5m_start"] & (df_sorted.get("HTF_15m_TrendDownOK", 0) == 1) & df_sorted["5m_Short_Pullback"]
    sig_a[cond_a_long] = 1
    sig_a[cond_a_short] = -1

    # 2. SETUP B: OPENING_RANGE_BREAK (09:00-09:15, RVOL >= 1.2, fixed stop 4 pts)
    df_sorted["date_only"] = df_sorted["datetime"].dt.date
    or_bars = df_sorted[(df_sorted["datetime"].dt.hour == 9) & (df_sorted["datetime"].dt.minute <= 15)]
    or_stats = or_bars.groupby("date_only").agg(
        OR_High=("High", "max"),
        OR_Low=("Low", "min"),
    )
    df_sorted["OR_High"] = df_sorted["date_only"].map(or_stats["OR_High"])
    df_sorted["OR_Low"] = df_sorted["date_only"].map(or_stats["OR_Low"])

    after_or = (df_sorted["datetime"].dt.hour > 9) | ((df_sorted["datetime"].dt.hour == 9) & (df_sorted["datetime"].dt.minute > 15))
    rvol_ok = df_sorted.get("RVOL", 1.0) >= 1.2
    orb_long_raw = after_or & (df_sorted["Close"] > df_sorted["OR_High"]) & rvol_ok
    orb_short_raw = after_or & (df_sorted["Close"] < df_sorted["OR_Low"]) & rvol_ok

    first_either = df_sorted[orb_long_raw | orb_short_raw].groupby("date_only").head(1)
    sig_b = pd.Series(0, index=df_sorted.index, dtype=int)
    first_long_mask = first_either["Close"] > first_either["OR_High"]
    first_short_mask = first_either["Close"] < first_either["OR_Low"]
    sig_b.loc[first_either[first_long_mask].index] = 1
    sig_b.loc[first_either[first_short_mask].index] = -1

    return sig_a, sig_b


def run_shadow_simulation_stream(
    features: pd.DataFrame,
    signals: pd.Series,
    setup_name: str,
    oos_cutoff: pd.Timestamp,
    config: BacktestConfig = DEFAULT_BACKTEST_CONFIG,
) -> list[dict]:
    """Run sequential simulation for a candidate setup in forward OOS window."""
    oos_mask = features["datetime"] >= oos_cutoff
    df_oos = features[oos_mask].copy().reset_index(drop=True)
    sig_oos = signals[oos_mask].to_numpy(dtype=np.int8)

    if len(df_oos) == 0 or np.count_nonzero(sig_oos) == 0:
        return []

    timestamps = df_oos["datetime"].to_numpy()
    opens = df_oos["Open"].to_numpy(dtype=np.float64)
    highs = df_oos["High"].to_numpy(dtype=np.float64)
    lows = df_oos["Low"].to_numpy(dtype=np.float64)
    closes = df_oos["Close"].to_numpy(dtype=np.float64)
    atrs = df_oos["ATR"].to_numpy(dtype=np.float64)
    htf_5m_atrs = df_oos["HTF_5m_ATR"].to_numpy(dtype=np.float64) if "HTF_5m_ATR" in df_oos.columns else np.zeros(len(df_oos))
    trend_down_flags = df_oos["HTF_15m_TrendDownOK"].to_numpy(dtype=np.int8) if "HTF_15m_TrendDownOK" in df_oos.columns else np.zeros(len(df_oos), dtype=np.int8)
    trend_trans_flags = df_oos["HTF_15m_TrendTransitionDown"].to_numpy(dtype=np.int8) if "HTF_15m_TrendTransitionDown" in df_oos.columns else np.zeros(len(df_oos), dtype=np.int8)
    trend_up_flags = df_oos["HTF_15m_TrendOK"].to_numpy(dtype=np.int8) if "HTF_15m_TrendOK" in df_oos.columns else np.zeros(len(df_oos), dtype=np.int8)

    n = len(df_oos)
    sig_indices = np.flatnonzero(sig_oos)
    num_sigs = len(sig_indices)

    trades = []
    sig_ptr = 0
    curr_idx = 0

    while sig_ptr < num_sigs:
        idx = sig_indices[sig_ptr]
        if idx < curr_idx:
            sig_ptr += 1
            continue

        sig = sig_oos[idx]
        if sig == 0 or atrs[idx] <= 0:
            sig_ptr += 1
            continue

        position = sig
        entry_idx = idx
        entry_date = timestamps[entry_idx]
        expected_price = float(closes[entry_idx])
        realized_price = float(expected_price + position * config.slippage_points)

        # OpenNext
        open_next = float(opens[entry_idx + 1]) if entry_idx + 1 < n else expected_price
        open_next_slippage = round(abs(open_next - expected_price), 4)
        realized_slippage = round(abs(realized_price - expected_price), 4)

        htf_atr = float(htf_5m_atrs[entry_idx]) if htf_5m_atrs[entry_idx] > 0 else float(atrs[entry_idx] * 2.0)

        if setup_name.startswith("OPENING_RANGE_BREAK"):
            initial_sl = realized_price - position * 4.0
            hard_sl = initial_sl
            trailing_sl = initial_sl
        else:
            initial_sl = realized_price - position * config.stop_loss_atr * htf_atr
            trailing_sl = initial_sl
            hsl_mult = getattr(config, "hard_sl_atr_mult", 2.5)
            hard_sl = realized_price - position * hsl_mult * config.stop_loss_atr * htf_atr

        raw_exit = None
        reason = None
        exit_time = None
        i = entry_idx + 1

        while i < n:
            op = opens[i]
            h = highs[i]
            l = lows[i]
            c_bar = closes[i]
            atr_bar = atrs[i]
            htf_atr_bar = htf_5m_atrs[i] if htf_5m_atrs[i] > 0 else (atr_bar * 2.0)
            sig_bar = sig_oos[i]

            if position == 1:
                # LONG exits
                if l <= hard_sl:
                    raw_exit = hard_sl
                    reason = "Hard_SL"
                    exit_time = timestamps[i]
                elif trailing_sl >= realized_price and l <= trailing_sl:
                    raw_exit = trailing_sl
                    reason = "SL"
                    exit_time = timestamps[i]
                elif l <= trailing_sl:
                    if setup_name.startswith("OPENING_RANGE_BREAK"):
                        raw_exit = trailing_sl
                        reason = "SL"
                        exit_time = timestamps[i]
                    else:
                        if trend_down_flags[i] == 1 or trend_trans_flags[i] == 1:
                            raw_exit = trailing_sl
                            reason = "SL"
                            exit_time = timestamps[i]
                elif sig_bar == -1:
                    raw_exit = c_bar
                    reason = "Reversal"
                    exit_time = timestamps[i]
            else:
                # SHORT exits
                if h >= hard_sl:
                    raw_exit = hard_sl
                    reason = "Hard_SL"
                    exit_time = timestamps[i]
                elif trailing_sl <= realized_price and h >= trailing_sl:
                    raw_exit = trailing_sl
                    reason = "SL"
                    exit_time = timestamps[i]
                elif h >= trailing_sl:
                    if setup_name.startswith("OPENING_RANGE_BREAK"):
                        raw_exit = trailing_sl
                        reason = "SL"
                        exit_time = timestamps[i]
                    else:
                        if trend_up_flags[i] == 1 or (trend_down_flags[i] == 0 and trend_trans_flags[i] == 0):
                            raw_exit = trailing_sl
                            reason = "SL"
                            exit_time = timestamps[i]
                elif sig_bar == 1:
                    raw_exit = c_bar
                    reason = "Reversal"
                    exit_time = timestamps[i]

            if raw_exit is not None:
                # Gap-Aware calculation
                if position == 1:
                    gap_exit_raw = min(raw_exit, op) if op < raw_exit and reason in ("SL", "Hard_SL") else raw_exit
                else:
                    gap_exit_raw = max(raw_exit, op) if op > raw_exit and reason in ("SL", "Hard_SL") else raw_exit

                nominal_exit = raw_exit - position * config.slippage_points
                exit_gap_aware = gap_exit_raw - position * config.slippage_points

                pnl_nominal = (nominal_exit - realized_price) * position * config.point_multiplier - (2 * config.commission_per_contract)
                pnl_gap = (exit_gap_aware - realized_price) * position * config.point_multiplier - (2 * config.commission_per_contract)

                trades.append({
                    "SignalTime": pd.Timestamp(entry_date),
                    "Type": "LONG" if position == 1 else "SHORT",
                    "SignalDirection": int(position),
                    "Setup": setup_name,
                    "ExpectedPrice": round(expected_price, 2),
                    "OpenNext": round(open_next, 2),
                    "OpenNextSlippage": round(open_next_slippage, 4),
                    "RealizedPrice": round(realized_price, 2),
                    "RealizedSlippage": round(realized_slippage, 4),
                    "InitialStop": round(initial_sl, 4),
                    "TakeProfit": None,
                    "ATR": round(float(atrs[entry_idx]), 4),
                    "Status": "CLOSED",
                    "WyckoffScore": None,
                    "ExitTime": pd.Timestamp(exit_time),
                    "Exit": round(nominal_exit, 2),
                    "ExitPriceGapAware": round(exit_gap_aware, 2),
                    "ExitReason": reason,
                    "PnL": round(pnl_nominal, 2),
                    "PnLGapAware": round(pnl_gap, 2),
                })
                curr_idx = i + config.cooldown_bars
                break

            # Update trailing stop
            if atr_bar > 0:
                if position == 1:
                    trailing_sl = max(trailing_sl, c_bar - config.trailing_stop_atr * htf_atr_bar)
                else:
                    trailing_sl = min(trailing_sl, c_bar + config.trailing_stop_atr * htf_atr_bar)

            i += 1
        else:
            # Open position at end of data
            trades.append({
                "SignalTime": pd.Timestamp(entry_date),
                "Type": "LONG" if position == 1 else "SHORT",
                "SignalDirection": int(position),
                "Setup": setup_name,
                "ExpectedPrice": round(expected_price, 2),
                "OpenNext": round(open_next, 2),
                "OpenNextSlippage": round(open_next_slippage, 4),
                "RealizedPrice": round(realized_price, 2),
                "RealizedSlippage": round(realized_slippage, 4),
                "InitialStop": round(initial_sl, 4),
                "TakeProfit": None,
                "ATR": round(float(atrs[entry_idx]), 4),
                "Status": "OPEN",
                "WyckoffScore": None,
                "ExitTime": None,
                "Exit": None,
                "ExitPriceGapAware": None,
                "ExitReason": None,
                "PnL": None,
                "PnLGapAware": None,
            })
            curr_idx = n

        sig_ptr += 1

    return trades


def run_shadow_paper_trade(
    oos_from: str = "2026-10-20",
    config: BacktestConfig | None = None,
) -> dict:
    """Run shadow forward paper trading scan for candidate setups A & B."""
    if not FEATURES_PATH.exists():
        logger.error("Features parquet missing for shadow paper trade scan: %s", FEATURES_PATH)
        return {"error": "Missing features parquet", "new_signals": 0}

    cfg = config or BacktestConfig(slippage_points=0.30)

    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    features = features.sort_values("datetime").reset_index(drop=True)

    oos_cutoff = pd.Timestamp(oos_from)
    sig_a, sig_b = extract_candidate_signals(features)

    trades_a = run_shadow_simulation_stream(features, sig_a, "PULLBACK_15M_TREND", oos_cutoff, config=cfg)
    trades_b = run_shadow_simulation_stream(features, sig_b, "OPENING_RANGE_BREAK", oos_cutoff, config=cfg)

    all_records = trades_a + trades_b
    all_records.sort(key=lambda x: x["SignalTime"])

    journal_df = pd.DataFrame(all_records, columns=JOURNAL_COLUMNS)
    journal_df.to_csv(JOURNAL_SHADOW_PATH, index=False)

    state = {
        "last_seen": features["datetime"].max().isoformat(),
        "oos_cutoff": oos_cutoff.isoformat(),
        "total_trades": len(all_records),
        "setups": {
            "PULLBACK_15M_TREND": len(trades_a),
            "OPENING_RANGE_BREAK": len(trades_b),
        },
    }
    STATE_SHADOW_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    logger.info(
        "Shadow paper trade complete | Setup A trades=%d, Setup B trades=%d, total=%d",
        len(trades_a),
        len(trades_b),
        len(all_records),
    )
    return {
        "status": "SUCCESS",
        "total_trades": len(all_records),
        "setup_a_trades": len(trades_a),
        "setup_b_trades": len(trades_b),
        "journal": str(JOURNAL_SHADOW_PATH),
    }


def main():
    res = run_shadow_paper_trade()
    print("Shadow Paper Trade Result:", res)


if __name__ == "__main__":
    main()
