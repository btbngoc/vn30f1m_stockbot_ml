"""Quarterly walk-forward selection for pre-registered raw Short setups."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _metrics
from .short_distribution_audit import load_features, short_setups

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_distribution_walk_forward_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "short_distribution_walk_forward_trades_no_commission.csv"
MIN_PRIOR_TRADES = 3


def _run_quarter(features: pd.DataFrame, signal: pd.Series, quarter: pd.Period) -> pd.DataFrame:
    frame = features.loc[(features.index >= quarter.start_time) & (features.index < quarter.end_time + pd.Timedelta(days=1))].copy()
    frame["Signal"] = -signal.loc[frame.index].astype(int)
    return BacktestEngine(frame).run()


def _pf_value(metrics: dict) -> float:
    return float("inf") if metrics["profit_factor"] is None and metrics["net_pnl"] > 0 else float(metrics["profit_factor"] or 0)


def run_short_distribution_walk_forward() -> dict:
    features = load_features()
    setups = short_setups(features)
    quarters = pd.period_range(features.index.min().to_period("Q"), features.index.max().to_period("Q"), freq="Q")
    history: dict[str, list[dict]] = {name: [] for name in setups}
    rows = []
    selected_trades = []
    for quarter in quarters:
        candidates = []
        for setup, prior in history.items():
            prior_trades = sum(item["metrics"]["trades"] for item in prior)
            prior_pnl = sum(item["metrics"]["net_pnl"] for item in prior)
            prior_wins = sum(
                item["metrics"]["net_pnl"]
                for item in prior
                if item["metrics"]["net_pnl"] > 0
            )
            prior_losses = -sum(
                item["metrics"]["net_pnl"]
                for item in prior
                if item["metrics"]["net_pnl"] <= 0
            )
            prior_pf = float("inf") if prior_losses == 0 and prior_wins > 0 else (prior_wins / prior_losses if prior_losses else 0.0)
            # A walk-forward selector must be allowed to stand aside.  Having
            # enough historic trades alone is not evidence of an edge.
            if prior_trades >= MIN_PRIOR_TRADES and prior_pnl > 0 and prior_pf > 1:
                candidates.append((prior_pnl, setup))
        selected = max(candidates)[1] if candidates else None
        selection_reason = (
            "max prior cumulative net PnL; min 3 prior trades; prior PnL > 0 and PF > 1"
            if selected else "no prior setup passed min 3 trades + PnL > 0 + PF > 1; no OOS trade"
        )
        for setup, signal in setups.items():
            trades = _run_quarter(features, signal, quarter)
            metrics = _metrics(trades)
            history[setup].append({"quarter": str(quarter), "metrics": metrics})
            if setup == selected:
                if not trades.empty:
                    tagged = trades.copy()
                    tagged["Quarter"] = str(quarter)
                    tagged["Selected Setup"] = setup
                    selected_trades.append(tagged)
                rows.append({"quarter": str(quarter), "selected_setup": setup, "selection_reason": selection_reason, **metrics})
        if selected is None:
            rows.append({"quarter": str(quarter), "selected_setup": None, "selection_reason": selection_reason, **_metrics(pd.DataFrame())})
    result = pd.DataFrame(rows)
    selected_only = result[result["selected_setup"].notna()]
    aggregate_trades = pd.concat(selected_trades, ignore_index=True) if selected_trades else pd.DataFrame()
    if not aggregate_trades.empty:
        aggregate_trades.to_csv(TRADES_PATH, index=False)
    report = {
        "execution": "pre-registered raw Short candidates; each quarter selects only from prior-quarter results; no ML; commission=0 research mode with slippage and active ATR exits",
        "selection_rule": "maximum cumulative net PnL before the test quarter; minimum 3 prior trades, prior PnL > 0 and PF > 1",
        "quarterly_oos": rows,
        "summary": {
            "quarters_total": int(len(result)),
            "quarters_selected": int(len(selected_only)),
            "quarters_with_trades": int((selected_only["trades"] > 0).sum()),
            "quarters_positive_pnl": int((selected_only["net_pnl"] > 0).sum()),
            "aggregate": _metrics(aggregate_trades),
        },
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short distribution walk-forward written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_distribution_walk_forward()


if __name__ == "__main__":
    main()
