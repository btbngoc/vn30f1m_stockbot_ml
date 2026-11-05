"""Paper Trading Live Monitoring & Performance Tracker.

Tracks weekly/monthly paper trading metrics, consecutive losses,
and monitors safety thresholds before live capital deployment.
"""

from pathlib import Path
import json
import pandas as pd

from .logging_config import logger

BASE_DIR = Path(__file__).resolve().parent
JOURNAL_PATH = BASE_DIR / "data" / "paper_trade_journal.csv"
MONITOR_SUMMARY_PATH = BASE_DIR / "data" / "paper_trade_monitor_summary.json"


def evaluate_paper_trade_performance() -> dict:
    if not JOURNAL_PATH.exists():
        logger.info("Paper trade journal does not exist yet. Run paper-trade mode first.")
        return {"status": "NO_JOURNAL", "total_trades": 0}

    journal = pd.read_csv(JOURNAL_PATH)
    if journal.empty or "Status" not in journal.columns:
        logger.info("Paper trade journal is empty.")
        return {"status": "EMPTY", "total_trades": 0}

    closed_trades = journal[journal["Status"] == "CLOSED"].copy()
    if closed_trades.empty:
        logger.info("No closed paper trades recorded yet.")
        return {"status": "NO_CLOSED_TRADES", "total_trades": len(journal), "closed_trades": 0}

    closed_trades["PnL"] = pd.to_numeric(closed_trades["PnL"], errors="coerce").fillna(0.0)
    closed_trades["ExitTime"] = pd.to_datetime(closed_trades["ExitTime"], errors="coerce")
    closed_trades = closed_trades.sort_values("ExitTime")

    total_trades = len(closed_trades)
    winning_trades = (closed_trades["PnL"] > 0).sum()
    losing_trades = (closed_trades["PnL"] <= 0).sum()
    win_rate = float(winning_trades / total_trades) if total_trades > 0 else 0.0

    gross_profit = closed_trades.loc[closed_trades["PnL"] > 0, "PnL"].sum()
    gross_loss = abs(closed_trades.loc[closed_trades["PnL"] <= 0, "PnL"].sum())
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    total_net_pnl = float(closed_trades["PnL"].sum())

    # Calculate current consecutive losses
    current_consecutive_losses = 0
    for pnl in reversed(closed_trades["PnL"].tolist()):
        if pnl <= 0:
            current_consecutive_losses += 1
        else:
            break

    # Safety Alerts based on User Criteria
    alerts = []
    if current_consecutive_losses > 5:
        alerts.append("CRITICAL: Consecutive losses > 5 trades! Action: Pause Short, keep Long only.")

    if profit_factor < 0.8 and total_trades >= 5:
        alerts.append("WARNING: Monthly Profit Factor < 0.8! Action: Review strategy performance.")

    if win_rate < 0.25 and total_trades >= 10:
        alerts.append("CRITICAL: Win Rate < 25%! Action: Pause all paper trading.")

    readiness = "NOT_READY"
    if total_trades >= 50 and profit_factor >= 1.2:
        readiness = "READY_FOR_LIVE_DEPLOYMENT"
    elif total_trades >= 20:
        readiness = "EVALUATING_MONTH_1"

    summary = {
        "status": "ACTIVE",
        "total_closed_trades": total_trades,
        "win_rate": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "INF",
        "total_net_pnl": round(total_net_pnl, 2),
        "current_consecutive_losses": current_consecutive_losses,
        "alerts": alerts,
        "live_deployment_readiness": readiness,
    }

    MONITOR_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Paper Trade Monitor Summary: %s", summary)
    return summary


def main():
    summary = evaluate_paper_trade_performance()
    print("=" * 60)
    print("[REPORT] PAPER TRADING LIVE MONITORING REPORT")
    print("=" * 60)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("=" * 60)


if __name__ == "__main__":
    main()
