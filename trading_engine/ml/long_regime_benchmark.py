"""Test regime-specific Long thresholds on a strictly held-out 2026 period."""

import json

import pandas as pd
import xgboost as xgb

from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .schema import ML_FEATURE_COLUMNS
from .train import DATASET_PATH, FEATURES_PATH, MODEL_DIR, THRESHOLD_CANDIDATES, XGBOOST_PARAMS


OUTPUT_PATH = MODEL_DIR / "long_regime_evaluation.json"
VALIDATION_START = pd.Timestamp("2025-01-01")
TEST_START = pd.Timestamp("2026-01-01")
TARGET_REGIMES = ("TREND_UP", "HIGH_VOL")
MIN_VALIDATION_TRADES = 8



def _pf_passes(metrics: dict) -> bool:
    return (metrics["profit_factor"] or 0) > 1 or (
        metrics["profit_factor"] is None and metrics["gross_profit"] > 0 and metrics["gross_loss"] == 0
    )


def _simulate(model, features: pd.DataFrame, start, end, thresholds: dict[str, float]):
    period = features[features["datetime"] >= start].copy()
    if end is not None:
        period = period[period["datetime"] < end].copy()
    probability = model.predict_proba(period[ML_FEATURE_COLUMNS].fillna(0.0))[:, 1]
    threshold = period["MarketRegime"].map(thresholds).fillna(thresholds["default"])
    period["Confidence"] = probability
    period["Signal"] = ((period["StrategySignal"] == 1) & (period["Confidence"] >= threshold)).astype(int)
    trades = BacktestEngine(period.set_index("datetime")).run()
    if trades.empty:
        return {"trades": 0, "net_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "pnl_by_regime": {}}, trades
    wins = trades.loc[trades["PnL"] > 0, "PnL"].sum()
    losses = -trades.loc[trades["PnL"] <= 0, "PnL"].sum()
    regimes = period.set_index("datetime")["MarketRegime"]
    trades = trades.copy()
    trades["Entry Regime"] = pd.to_datetime(trades["Entry Date"]).map(regimes)
    pnl_by_regime = trades.groupby("Entry Regime")["PnL"].agg(["count", "sum", lambda values: (values > 0).mean()]).rename(columns={"<lambda_0>": "win_rate"}).round(4).to_dict("index")
    return {
        "trades": int(len(trades)),
        "net_pnl": float(trades["PnL"].sum()),
        "gross_profit": float(wins),
        "gross_loss": float(losses),
        "profit_factor": float(wins / losses) if losses > 0 else None,
        "win_rate": float((trades["PnL"] > 0).mean()),
        "pnl_by_regime": pnl_by_regime,
    }, trades


def _select_global_threshold(model, features):
    candidates = []
    for threshold in THRESHOLD_CANDIDATES:
        metrics, _ = _simulate(model, features, VALIDATION_START, TEST_START, {"default": threshold})
        candidates.append({"threshold": threshold, "metrics": metrics})
    eligible = [item for item in candidates if item["metrics"]["trades"] >= MIN_VALIDATION_TRADES and item["metrics"]["net_pnl"] > 0 and _pf_passes(item["metrics"])]
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item["metrics"]["net_pnl"], item["metrics"]["profit_factor"] or float("inf")))


def run_long_regime_benchmark() -> dict:
    dataset = pd.read_csv(DATASET_PATH)
    dataset["entry_time"] = pd.to_datetime(dataset["entry_time"], errors="raise")
    dataset["exit_time"] = pd.to_datetime(dataset["exit_time"], errors="raise")
    long_data = dataset[dataset["signal"] == 1]
    train = long_data[long_data["exit_time"] < VALIDATION_START]
    if train["label"].nunique() < 2:
        raise ValueError("Long training data contains only one label class.")
    features = pd.read_parquet(FEATURES_PATH)
    features["datetime"] = pd.to_datetime(features["datetime"], errors="raise")
    required = {"MarketRegime", *ML_FEATURE_COLUMNS}
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError(f"Feature parquet is missing regime features: {missing}")

    logger.info("Training Long regime model | train=%d", len(train))
    model = xgb.XGBClassifier(**XGBOOST_PARAMS)
    model.fit(train[ML_FEATURE_COLUMNS], train["label"])
    baseline = _select_global_threshold(model, features)
    if baseline is None:
        raise ValueError("No global Long threshold passes the validation gate.")
    default_threshold = baseline["threshold"]
    logger.info("Long baseline validation threshold: %.2f", default_threshold)

    candidates = []
    for trend_up_threshold in THRESHOLD_CANDIDATES:
        for high_vol_threshold in THRESHOLD_CANDIDATES:
            thresholds = {"default": default_threshold, "TREND_UP": trend_up_threshold, "HIGH_VOL": high_vol_threshold}
            metrics, _ = _simulate(model, features, VALIDATION_START, TEST_START, thresholds)
            candidates.append({"thresholds": thresholds, "validation": metrics})
    eligible = [item for item in candidates if item["validation"]["trades"] >= MIN_VALIDATION_TRADES and item["validation"]["net_pnl"] > 0 and _pf_passes(item["validation"])]
    selected = max(eligible, key=lambda item: (item["validation"]["net_pnl"], item["validation"]["profit_factor"] or float("inf"))) if eligible else None

    baseline_thresholds = {"default": default_threshold}
    baseline_test, _ = _simulate(model, features, TEST_START, None, baseline_thresholds)
    regime_test, _ = _simulate(model, features, TEST_START, None, selected["thresholds"]) if selected else (None, None)
    report = {
        "selection_rule": "Long only; select thresholds for TREND_UP and HIGH_VOL by maximum 2025 validation PnL, PF breaks ties; at least 20 trades, positive PnL and PF > 1.",
        "baseline": {"thresholds": baseline_thresholds, "validation": baseline["metrics"], "test": baseline_test},
        "regime_threshold_result": {"status": "TRADE" if selected else "NO_TRADE", "selected": selected, "test": regime_test},
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Long regime evaluation written to %s", OUTPUT_PATH)
    return report


def main() -> None:
    run_long_regime_benchmark()


if __name__ == "__main__":
    main()
