"""Pre-registered LPS parameter grid with quarterly walk-forward selection."""

import json
from itertools import product
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _event_start, _metrics

BASE_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
OUTPUT_PATH = BASE_DIR / "models" / "lps_parameter_walk_forward_no_commission.json"

TEST_WINDOWS = (6, 8)
LPS_WINDOWS = (6, 8)
TIMINGS = ("immediate", "pullback_reclaim", "ema_retest_reclaim")
MIN_SELECTION_TRADES = 5


def _build_5m(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    bucket = frame.index.floor("5min")
    htf = frame.groupby(bucket).agg(
        Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
        Close=("Close", "last"), Volume=("Volume", "sum"),
    )
    htf["EMA10"] = htf["Close"].ewm(span=10, adjust=False).mean()
    htf["EMA20"] = htf["Close"].ewm(span=20, adjust=False).mean()
    previous_close = htf["Close"].shift(1)
    true_range = pd.concat([
        htf["High"] - htf["Low"],
        (htf["High"] - previous_close).abs(),
        (htf["Low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    htf["ATR14"] = true_range.rolling(14).mean()
    htf["VolumeMA20"] = htf["Volume"].rolling(20).mean()
    htf["RangeHigh"] = htf["High"].rolling(24).max().shift(1)
    htf["RangeLow"] = htf["Low"].rolling(24).min().shift(1)
    htf["RangeWidth"] = htf["RangeHigh"] - htf["RangeLow"]
    htf["Accumulation"] = (
        (htf["Close"] >= htf["RangeLow"])
        & (htf["Close"] <= htf["RangeHigh"])
        & (htf["RangeWidth"] >= htf["ATR14"] * 2.0)
        & (htf["RangeWidth"] <= htf["ATR14"] * 10.0)
        & (htf["EMA20"].diff(12).abs() <= htf["ATR14"] * 1.5)
    )
    htf["Spring"] = (
        htf["Accumulation"].shift(1).fillna(False)
        & (htf["Low"] < htf["RangeLow"])
        & (htf["Close"] > htf["RangeLow"])
        & (htf["Close"] >= (htf["High"] + htf["Low"]) / 2)
        & (htf["Volume"] >= htf["VolumeMA20"] * 1.30)
    )
    return htf, bucket


def _lps_source(htf: pd.DataFrame, test_window: int, lps_window: int) -> pd.Series:
    lps = []
    state = "IDLE"
    spring_low = spring_volume = None
    spring_age = confirm_age = 0
    previous_timestamp = None
    for timestamp, row in htf.iterrows():
        if previous_timestamp is not None and timestamp - previous_timestamp > pd.Timedelta(minutes=10):
            state = "IDLE"
            spring_low = spring_volume = None
            spring_age = confirm_age = 0
        lps_now = False
        atr = row["ATR14"]
        if bool(row["Spring"]):
            state = "WAIT_TEST"
            spring_low, spring_volume = row["Low"], row["Volume"]
            spring_age = confirm_age = 0
        elif state == "WAIT_TEST":
            spring_age += 1
            test = False
            if 2 <= spring_age <= test_window and pd.notna(atr):
                test = (
                    row["Low"] >= spring_low - atr * 0.10
                    and row["Low"] <= spring_low + max(row["RangeWidth"] * 0.35, 0)
                    and row["Volume"] <= spring_volume * 0.75
                    and row["Close"] >= (row["High"] + row["Low"]) / 2
                )
            if test:
                state = "WAIT_LPS"
                confirm_age = 0
            elif spring_age > test_window:
                state = "IDLE"
                spring_low = spring_volume = None
        elif state == "WAIT_LPS":
            confirm_age += 1
            if pd.notna(atr) and 2 <= confirm_age <= lps_window:
                close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                lps_now = (
                    row["Low"] >= spring_low + atr * 0.10
                    and row["Low"] <= row["EMA10"]
                    and row["Volume"] <= row["VolumeMA20"]
                    and close_location >= 0.55
                )
            if lps_now or confirm_age > lps_window:
                state = "IDLE"
                spring_low = spring_volume = None
        lps.append(int(lps_now))
        previous_timestamp = timestamp
    return pd.Series(lps, index=htf.index, dtype=bool)


def _timing(event: pd.Series, frame: pd.DataFrame, name: str) -> pd.Series:
    starts = _event_start(event)
    if name == "immediate":
        return starts
    pending = starts.shift(1, fill_value=False).rolling(10, min_periods=1).max().astype(bool)
    reclaim = (
        (frame["Close"] > frame["High"].shift(1))
        & (frame["Close"] > frame["EMA10"])
        & (frame["Close"] >= (frame["High"] + frame["Low"]) / 2)
    )
    if name == "pullback_reclaim":
        trigger = pending & (frame["Close"].shift(1) <= frame["Open"].shift(1)) & reclaim
    elif name == "ema_retest_reclaim":
        retest = (frame["Low"] <= frame["EMA20"]).rolling(3, min_periods=1).max().shift(1).fillna(0).astype(bool)
        trigger = pending & retest & reclaim
    else:
        raise ValueError(f"Unsupported timing: {name}")
    return trigger & ~trigger.shift(1, fill_value=False)


def _config_id(test_window: int, lps_window: int, timing: str) -> str:
    return f"test{test_window}_lps{lps_window}_{timing}"


def run_lps_parameter_walk_forward() -> dict:
    frame = pd.read_parquet(FEATURES_PATH)
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="raise")
    frame = frame.sort_values("datetime").set_index("datetime")
    htf, bucket = _build_5m(frame)
    quarter_range = pd.period_range(frame.index.min().to_period("Q"), frame.index.max().to_period("Q"), freq="Q")
    results: list[dict] = []
    trend = frame["HTF_15m_TrendOK"] == 1
    for test_window, lps_window, timing in product(TEST_WINDOWS, LPS_WINDOWS, TIMINGS):
        source_lps = _lps_source(htf, test_window, lps_window)
        completed = source_lps.shift(1).fillna(False)
        event = pd.Series(bucket, index=frame.index).map(completed).fillna(False).astype(bool) & trend
        signal = _timing(event, frame, timing)
        config = _config_id(test_window, lps_window, timing)
        for quarter in quarter_range:
            start = quarter.start_time
            end = quarter.end_time + pd.Timedelta(days=1)
            period = frame.loc[(frame.index >= start) & (frame.index < end)].copy()
            period["Signal"] = signal.loc[period.index].astype(int)
            trades = BacktestEngine(period).run()
            results.append({
                "config": config, "test_window": test_window, "lps_window": lps_window, "timing": timing,
                "quarter": str(quarter), "raw_events": int(period["Signal"].sum()), **_metrics(trades),
            })
    table = pd.DataFrame(results)
    walk_forward = []
    for position, quarter in enumerate(quarter_range):
        previous = table[table["quarter"].isin([str(value) for value in quarter_range[:position]])]
        grouped = previous.groupby("config", as_index=False).agg(trades=("trades", "sum"), net_pnl=("net_pnl", "sum"))
        eligible = grouped[grouped["trades"] >= MIN_SELECTION_TRADES]
        if eligible.empty:
            walk_forward.append({"quarter": str(quarter), "selected_config": None, "selection_reason": "insufficient prior trades"})
            continue
        selected = eligible.sort_values(["net_pnl", "trades"], ascending=[False, False]).iloc[0]
        test_row = table[(table["quarter"] == str(quarter)) & (table["config"] == selected["config"])].iloc[0].to_dict()
        walk_forward.append({
            "quarter": str(quarter), "selected_config": selected["config"],
            "prior_trades": int(selected["trades"]), "prior_net_pnl": float(selected["net_pnl"]),
            "test": test_row,
        })
    oos_trades = [item["test"] for item in walk_forward if item.get("test") and item["test"]["trades"] > 0]
    report = {
        "pre_registered_grid": {"test_windows_5m_bars": TEST_WINDOWS, "lps_windows_5m_bars": LPS_WINDOWS, "timings_1m": TIMINGS},
        "selection_rule": f"maximum cumulative prior net PnL among configurations with at least {MIN_SELECTION_TRADES} prior trades",
        "quarterly_config_results": results,
        "walk_forward": walk_forward,
        "summary": {
            "configurations": int(len(TEST_WINDOWS) * len(LPS_WINDOWS) * len(TIMINGS)),
            "oos_quarters_with_trades": int(len(oos_trades)),
            "oos_trades": int(sum(item["trades"] for item in oos_trades)),
            "oos_net_pnl": float(sum(item["net_pnl"] for item in oos_trades)),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("LPS parameter walk-forward written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_lps_parameter_walk_forward()


if __name__ == "__main__":
    main()
