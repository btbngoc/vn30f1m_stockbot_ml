"""Raw audit of the strict UTAD -> failed Test -> SOW -> LPSY Short setup."""

import json
from pathlib import Path

import pandas as pd

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics
from .short_distribution_audit import load_features

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BASE_DIR / "models" / "short_utad_sow_lpsy_raw_audit_no_commission.json"
TRADES_PATH = BASE_DIR / "models" / "short_utad_sow_lpsy_raw_trades_no_commission.csv"


def _rule_score(features: pd.DataFrame) -> pd.Series:
    """Diagnostic evidence only; it is deliberately not an entry gate yet."""
    bearish_ma = (features["EMA10"] < features["EMA20"]) & (features["EMA20"] < features["EMA50"])
    ma_turning = features["EMA20"].diff(3) < 0
    no_demand = (features["Volume"] <= features["Volume_MA20"] * 0.85) & (features["Close"] <= (features["High"] + features["Low"]) / 2)
    bb_expansion = features["BB_Width"] > features["BB_Width"].rolling(60, min_periods=30).median()
    score = pd.Series(0.0, index=features.index)
    score += bearish_ma.astype(int) * 25
    score += ma_turning.astype(int) * 15
    score += no_demand.astype(int) * 25
    score += bb_expansion.astype(int) * 15
    score += (features["RVOL"] >= 1.0).astype(int) * 10
    score += (features["Close"] < features["VWAP"]).astype(int) * 10
    return score


def run_short_utad_sow_lpsy_audit() -> dict:
    features = load_features()
    required = ["HTF_5m_SequenceTest", "HTF_5m_SequenceSOW", "HTF_5m_SequenceLPSY", "HTF_15m_TrendDownOK"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Regenerate feature parquet before this audit; missing {missing}")
    features["ShortRuleScore"] = _rule_score(features)
    event = _event_start((features["HTF_5m_SequenceLPSY"] == 1) & (features["HTF_15m_TrendDownOK"] == 1))
    features["Signal"] = -event.astype(int)
    all_trades = BacktestEngine(features).run()
    if not all_trades.empty:
        all_trades.to_csv(TRADES_PATH, index=False)
    yearly = []
    for name, start, end in PERIODS:
        frame = features.loc[features.index >= start].copy()
        if end:
            frame = frame.loc[frame.index < end]
        trades = BacktestEngine(frame).run()
        yearly.append({"period": name, "raw_events": int(event.loc[frame.index].sum()), **_metrics(trades)})
    report = {
        "execution": "strict completed 5m UTAD -> failed Test -> SOW -> LPSY, 15m slow downtrend hard gate, entry on first actionable 1m bar; raw only; no ML; commission=0 research mode with slippage and active ATR exits",
        "soft_evidence": "MA, BB, VSA/No-Demand, RVOL and VWAP are recorded as ShortRuleScore diagnostics only; no score or ML threshold is used to select trades",
        "stage_counts": {
            "sequence_test": int(_event_start(features["HTF_5m_SequenceTest"] == 1).sum()),
            "sequence_sow": int(_event_start(features["HTF_5m_SequenceSOW"] == 1).sum()),
            "sequence_lpsy": int(_event_start(features["HTF_5m_SequenceLPSY"] == 1).sum()),
            "entry_events": int(event.sum()),
        },
        "all_history": _metrics(all_trades), "years": yearly,
        "mean_rule_score_at_entry": float(features.loc[event, "ShortRuleScore"].mean()) if event.any() else None,
        "trades_csv": str(TRADES_PATH),
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Short UTAD/SOW/LPSY raw audit written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_short_utad_sow_lpsy_audit()


if __name__ == "__main__":
    main()
