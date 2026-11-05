"""Exit and R-multiple audit for the transition-gated LPSY Short trades."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import _event_start
from .short_distribution_audit import load_features
from .short_lpsy_timing_audit import lpsy_break_confirm

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "models" / "short_transition_exit_audit"
INDEX_PATH = OUTPUT_DIR / "transition_trade_r_multiples.csv"
SUMMARY_PATH = BASE_DIR / "models" / "short_transition_exit_audit.json"


def _draw(axis, frame: pd.DataFrame, trade: pd.Series) -> None:
    x = np.arange(len(frame))
    axis.vlines(x, frame["Low"], frame["High"], color="#64748b", linewidth=0.7)
    up = frame["Close"] >= frame["Open"]
    axis.vlines(x[up], frame.loc[up, "Open"], frame.loc[up, "Close"], color="#0f766e", linewidth=2.0)
    axis.vlines(x[~up], frame.loc[~up, "Open"], frame.loc[~up, "Close"], color="#b91c1c", linewidth=2.0)
    for timestamp, marker, color, label in ((pd.Timestamp(trade["Entry Date"]), "v", "#2563eb", "Short entry"), (pd.Timestamp(trade["Exit Date"]), "^", "#dc2626", trade["Reason"])):
        pos = frame.index.get_indexer([timestamp], method="nearest")[0]
        axis.scatter(pos, frame.iloc[pos]["Close"], marker=marker, color=color, s=48, zorder=4, label=label)
    for column, color, label in (("Initial Stop Loss", "#dc2626", "initial SL"), ("Take Profit", "#16a34a", "TP"), ("Stop Loss at Exit", "#f97316", "exit stop")):
        axis.axhline(float(trade[column]), color=color, linestyle="--", linewidth=0.9, label=label)
    axis.grid(alpha=0.18)


def run_short_transition_exit_audit() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = load_features()
    if "HTF_15m_TrendTransitionDown" not in features:
        raise ValueError("Regenerate feature parquet before running this audit")
    event = _event_start((features["HTF_5m_LPSY"] == 1) & (features["HTF_15m_TrendTransitionDown"] == 1))
    features["Signal"] = -lpsy_break_confirm(event, features).astype(int)
    trades = BacktestEngine(features).run()
    rows = []
    for number, (_, trade) in enumerate(trades.iterrows(), start=1):
        entry, exit_ = pd.Timestamp(trade["Entry Date"]), pd.Timestamp(trade["Exit Date"])
        path = features.loc[entry:exit_]
        initial_r = float(trade["Initial Stop Loss"] - trade["Entry"])
        mfe = float(trade["Entry"] - path["Low"].min()) if not path.empty else 0.0
        mae = float(path["High"].max() - trade["Entry"]) if not path.empty else 0.0
        realized_r = float((trade["Entry"] - trade["Exit"]) / initial_r) if initial_r > 0 else None
        exit_stop = float(trade["Stop Loss at Exit"])
        is_trailing = trade["Reason"] == "SL" and exit_stop < float(trade["Initial Stop Loss"])
        chart_frame = features.loc[entry - pd.Timedelta(minutes=30): exit_ + pd.Timedelta(minutes=30)]
        figure, axis = plt.subplots(figsize=(14, 5))
        _draw(axis, chart_frame, trade)
        handles, labels = axis.get_legend_handles_labels()
        figure.legend(handles, labels, loc="lower center", ncol=4)
        figure.suptitle(f"Transition LPSY Short {number} | {entry:%Y-%m-%d %H:%M} | {trade['Reason']} | realized {realized_r:.2f}R", y=0.99)
        figure.tight_layout(rect=(0, 0.06, 1, 0.97))
        chart_file = f"transition_short_{number:02d}_{entry:%Y%m%d_%H%M}.png"
        figure.savefig(OUTPUT_DIR / chart_file, dpi=140)
        plt.close(figure)
        rows.append({
            "entry_date": entry, "exit_date": exit_, "reason": trade["Reason"], "pnl": trade["PnL"],
            "initial_r_points": initial_r, "realized_r": realized_r, "mfe_r": mfe / initial_r if initial_r > 0 else None,
            "mae_r": mae / initial_r if initial_r > 0 else None, "is_trailing_sl": is_trailing,
            "holding_minutes": int((exit_ - entry).total_seconds() // 60), "chart_file": chart_file,
        })
    index = pd.DataFrame(rows)
    index.to_csv(INDEX_PATH, index=False)
    report = {
        "execution": "raw transition-gated LPSY break-confirm trades only; no entry/exit configuration changes, ML or paper-trade changes",
        "trades": int(len(index)),
        "by_exit_reason": index["reason"].value_counts().to_dict() if not index.empty else {},
        "trailing_sl_exits": int(index["is_trailing_sl"].sum()) if not index.empty else 0,
        "mean_realized_r": float(index["realized_r"].mean()) if not index.empty else None,
        "mean_mfe_r": float(index["mfe_r"].mean()) if not index.empty else None,
        "mean_mae_r": float(index["mae_r"].mean()) if not index.empty else None,
        "index_csv": str(INDEX_PATH), "chart_directory": str(OUTPUT_DIR),
    }
    SUMMARY_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short transition exit audit written to %s", SUMMARY_PATH)
    return report


def main() -> None:
    run_short_transition_exit_audit()


if __name__ == "__main__":
    main()
