"""Forward-only paper journal for the frozen Layer 1 Pure Rules strategy.

Evaluates forward paper entries for both Long and Short signals produced by
Layer 1 StrategySignal (Wyckoff setups without ML gating).
Enforces zero duplicate logging, strict forward-only cutoff (--oos-from),
and explicit logging of expected price, realized price, and realized slippage.
"""

import argparse
import json
from pathlib import Path
import pandas as pd

from .backtest.config import DEFAULT_BACKTEST_CONFIG, BacktestConfig
from .backtest.engine import BacktestEngine
from .logging_config import logger

BASE_DIR = Path(__file__).resolve().parent
FEATURES_PATH = BASE_DIR / "data" / "VN30F1M_features.parquet"
JOURNAL_PATH = BASE_DIR / "data" / "paper_trade_journal.csv"
STATE_PATH = BASE_DIR / "data" / "paper_trade_state.json"
JOURNAL_H01_PATH = BASE_DIR / "data" / "paper_trade_journal_h01.csv"
STATE_H01_PATH = BASE_DIR / "data" / "paper_trade_state_h01.json"

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


def _evaluate_paper_stream(
    features: pd.DataFrame,
    forward_df: pd.DataFrame,
    config: BacktestConfig,
    journal_path: Path,
    state_path: Path,
    oos_cutoff: pd.Timestamp,
) -> dict:
    """Run sequential forward simulation for a specific BacktestConfig and write journal."""
    engine = BacktestEngine(forward_df, config)
    raw_trades = engine.run()

    records = []
    feat_by_time = features.set_index("datetime")

    for _, trade in raw_trades.iterrows():
        entry_time = pd.Timestamp(trade["Entry Date"])
        exit_time = pd.Timestamp(trade["Exit Date"])
        reason = trade["Reason"]
        pos = 1 if trade["Type"] == "LONG" else -1

        row_feat = feat_by_time.loc[entry_time] if entry_time in feat_by_time.index else None
        expected_price = float(row_feat["Close"]) if row_feat is not None else float(trade["Entry"])

        # OpenNext: Open of the immediate subsequent 1m candle
        next_rows = features[features["datetime"] > entry_time]
        if not next_rows.empty:
            open_next = float(next_rows.iloc[0]["Open"])
            open_next_slippage = round(abs(open_next - expected_price), 4)
        else:
            open_next = expected_price
            open_next_slippage = 0.0

        realized_price = float(trade["Entry"])
        realized_slippage = round(abs(realized_price - expected_price), 4)
        setup = str(row_feat["EntrySetup"]) if row_feat is not None else ""
        atr = float(row_feat["ATR"]) if row_feat is not None else 0.0
        score = float(row_feat["WyckoffScore"]) if row_feat is not None else None

        is_open = (reason == "End of Data")
        status = "OPEN" if is_open else "CLOSED"

        exit_base = float(trade["Exit"]) if not is_open else None
        exit_gap_aware = None
        pnl_gap_aware = None

        if not is_open and exit_time in feat_by_time.index:
            exit_bar = feat_by_time.loc[exit_time]
            exit_open = float(exit_bar["Open"])
            raw_exit = float(trade["Exit"]) + pos * float(config.slippage_points)
            if pos == 1:
                gap_raw = min(raw_exit, exit_open) if exit_open < raw_exit and reason in ("SL", "Hard_SL") else raw_exit
            else:
                gap_raw = max(raw_exit, exit_open) if exit_open > raw_exit and reason in ("SL", "Hard_SL") else raw_exit

            exit_gap_aware = float(gap_raw - pos * config.slippage_points)
            gross_pnl_gap = (exit_gap_aware - realized_price) * pos * trade["Contracts"] * config.point_multiplier
            fees = 2 * trade["Contracts"] * config.commission_per_contract
            pnl_gap_aware = round(gross_pnl_gap - fees, 2)

        records.append({
            "SignalTime": entry_time,
            "Type": trade["Type"],
            "SignalDirection": pos,
            "Setup": setup,
            "ExpectedPrice": expected_price,
            "OpenNext": open_next,
            "OpenNextSlippage": open_next_slippage,
            "RealizedPrice": realized_price,
            "RealizedSlippage": realized_slippage,
            "InitialStop": trade["Initial Stop Loss"],
            "TakeProfit": trade["Take Profit"],
            "ATR": atr,
            "Status": status,
            "WyckoffScore": score,
            "ExitTime": None if is_open else exit_time,
            "Exit": exit_base,
            "ExitPriceGapAware": exit_gap_aware,
            "ExitReason": None if is_open else reason,
            "PnL": None if is_open else trade["PnL"],
            "PnLGapAware": pnl_gap_aware,
        })

    journal = pd.DataFrame(records, columns=JOURNAL_COLUMNS)
    journal.to_csv(journal_path, index=False)

    state_path.write_text(
        json.dumps({
            "last_seen": features["datetime"].max().isoformat(),
            "oos_cutoff": oos_cutoff.isoformat(),
            "total_trades": len(records),
            "flat_before_atc": getattr(config, "flat_before_atc", False),
        }, indent=2),
        encoding="utf-8",
    )
    return {"new_signals": len(records), "total_trades": len(records), "journal": str(journal_path)}


def run_paper_trade(oos_from: str = "2026-10-20") -> dict:
    """Run forward paper trading scan for Layer 1 Wyckoff signals.

    Maintains two separate, parallel streams:
    1. Primary Frozen Baseline (paper_trade_journal.csv): strict frozen rules (flat_before_atc=False).
    2. Parallel H-01 Research Journal (paper_trade_journal_h01.csv): tested rules (flat_before_atc=True).

    Args:
        oos_from: ISO date string (YYYY-MM-DD) defining the uncontaminated
                  forward testing boundary.
    """
    if not FEATURES_PATH.exists():
        logger.error("Features parquet missing for paper trade scan: %s", FEATURES_PATH)
        return {"error": "Missing features parquet", "new_signals": 0}

    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    features = features.sort_values("datetime").reset_index(drop=True)

    oos_cutoff = pd.Timestamp(oos_from)
    forward_df = features[features["datetime"] >= oos_cutoff].copy().set_index("datetime")
    if forward_df.empty:
        logger.info("No forward data found since %s", oos_cutoff)
        return {"new_signals": 0, "total_trades": 0}

    forward_df["Signal"] = forward_df["StrategySignal"].astype(int)

    # Realistic execution model matching backtest: Gap-Aware and 0.3 pt slippage
    cfg_primary = BacktestConfig(slippage_points=0.30, flat_before_atc=False)
    cfg_h01 = BacktestConfig(slippage_points=0.30, flat_before_atc=True)

    # 1. Primary frozen baseline journal (flat_before_atc=False, slip=0.30)
    res_primary = _evaluate_paper_stream(
        features=features,
        forward_df=forward_df,
        config=cfg_primary,
        journal_path=JOURNAL_PATH,
        state_path=STATE_PATH,
        oos_cutoff=oos_cutoff,
    )

    # 2. Parallel H-01 journal (flat_before_atc=True, slip=0.30)
    res_h01 = _evaluate_paper_stream(
        features=features,
        forward_df=forward_df,
        config=cfg_h01,
        journal_path=JOURNAL_H01_PATH,
        state_path=STATE_H01_PATH,
        oos_cutoff=oos_cutoff,
    )

    # 3. Shadow candidate journal (Setup A & Setup B, slip=0.30)
    from .shadow_paper import run_shadow_paper_trade, JOURNAL_SHADOW_PATH
    res_shadow = run_shadow_paper_trade(oos_from=str(oos_cutoff.date()), config=cfg_primary)


    logger.info(
        "Paper trade complete | primary trades=%d, h01 trades=%d, shadow trades=%d",
        res_primary["total_trades"],
        res_h01["total_trades"],
        res_shadow["total_trades"],
    )
    return {
        "new_signals": res_primary["new_signals"],
        "total_trades": res_primary["total_trades"],
        "journal": str(JOURNAL_PATH),
        "journal_h01": str(JOURNAL_H01_PATH),
        "journal_shadow": str(JOURNAL_SHADOW_PATH),
        "oos_from": str(oos_cutoff),
        "h01_trades": res_h01["total_trades"],
        "shadow_trades": res_shadow["total_trades"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward-only paper trade runner for Layer 1 Wyckoff strategy.")
    parser.add_argument("--oos-from", type=str, default="2026-10-20", help="OOS boundary start date (YYYY-MM-DD)")
    args = parser.parse_args()
    run_paper_trade(oos_from=args.oos_from)


if __name__ == "__main__":
    main()


