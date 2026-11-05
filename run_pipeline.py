import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from trading_engine.run_context import generate_run_id

# Imports for pipeline steps
from trading_engine.data.update_csv import main as update_csv_main
from trading_engine.data.indicators import main as indicators_main
from trading_engine.ml.predict import main as predict_main
from trading_engine.backtest.__main__ import main as backtest_main
from trading_engine.analysis import main as analysis_main
from trading_engine.visualize.__main__ import main as visualize_main
from trading_engine.report.report import main as report_main
# Training step (optional)
from trading_engine.ml.train import train_xgboost as train_main
from trading_engine.ml.dataset import build_ml_dataset
from trading_engine.ml.walk_forward import run_walk_forward
from trading_engine.ml.rolling_benchmark import run_rolling_benchmark
from trading_engine.ml.directional_benchmark import run_directional_benchmark
from trading_engine.ml.directional_walk_forward import run_directional_walk_forward
from trading_engine.ml.long_regime_benchmark import run_long_regime_benchmark
from trading_engine.ml.long_regime_walk_forward import run_long_regime_walk_forward
from trading_engine.strategy.audit import run_audit as run_trend_strategy_audit
from trading_engine.strategy.exit_audit import run_exit_audit as run_trend_exit_audit
from trading_engine.strategy.setup_audit import run_setup_audit
from trading_engine.strategy.setup_exit_audit import run_setup_exit_audit
from trading_engine.strategy.wyckoff_definition_audit import run_definition_audit
from trading_engine.strategy.state_machine_setup_audit import run_state_machine_setup_audit
from trading_engine.strategy.state_machine_visual_audit import run_visual_audit
from trading_engine.strategy.lps_quarterly_audit import run_lps_quarterly_audit
from trading_engine.strategy.lps_parameter_walk_forward import run_lps_parameter_walk_forward
from trading_engine.strategy.lps_oos_loss_audit import run_lps_oos_loss_audit
from trading_engine.strategy.lps_trend_gate_audit import run_lps_trend_gate_audit
from trading_engine.strategy.short_distribution_audit import run_short_distribution_audit
from trading_engine.strategy.short_distribution_visual_audit import run_short_distribution_visual_audit
from trading_engine.strategy.short_distribution_walk_forward import run_short_distribution_walk_forward
from trading_engine.strategy.short_lpsy_definition_audit import run_short_lpsy_definition_audit
from trading_engine.strategy.short_lpsy_timing_audit import run_short_lpsy_timing_audit
from trading_engine.strategy.short_lpsy_break_audit import run_short_lpsy_break_audit
from trading_engine.strategy.short_shadow_quarterly_audit import run_short_shadow_quarterly_audit
from trading_engine.strategy.short_htf_definition_audit import run_short_htf_definition_audit
from trading_engine.strategy.short_transition_gate_audit import run_short_transition_gate_audit
from trading_engine.strategy.short_transition_exit_audit import run_short_transition_exit_audit
from trading_engine.strategy.short_transition_breakeven_audit import run_short_transition_breakeven_audit
from trading_engine.strategy.short_lpsy_event_study import run_short_lpsy_event_study
from trading_engine.strategy.short_utad_sow_lpsy_audit import run_short_utad_sow_lpsy_audit
from trading_engine.strategy.short_narrow_range_audit import run_short_narrow_range_audit
from trading_engine.paper_trade import run_paper_trade
from trading_engine.short_shadow_paper import run_short_shadow_paper
from trading_engine.short_breakdown_weak_test_paper import run_short_breakdown_weak_test_paper
from trading_engine.monitor import main as monitor_main
from trading_engine.verify_freeze import verify_freeze

def run_daily():
    """Execute the daily pipeline: update data, generate features, predict, backtest, analysis, and visualization."""
    run_id = generate_run_id()
    update_csv_main()
    indicators_main()
    predict_main()
    backtest_main(["--run-id", run_id])
    analysis_main()
    visualize_main(["--run-id", run_id])
    report_main()

def run_retrain():
    """Rebuild features and labels before training a fresh model."""
    run_id = generate_run_id()
    update_csv_main()
    indicators_main()
    build_ml_dataset()
    train_main()
    predict_main()
    backtest_main(["--run-id", run_id])
    analysis_main()
    visualize_main(["--run-id", run_id])
    report_main()

def run_walk_forward_mode():
    """Evaluate independent historical train/validation/test folds."""
    run_walk_forward()

def run_rolling_benchmark_mode():
    """Run repeated quarterly OOS checks for the annual-benchmark finalists."""
    run_rolling_benchmark()

def run_directional_benchmark_mode():
    """Evaluate Long and Short classifiers separately; does not alter production."""
    run_directional_benchmark()

def run_directional_walk_forward_mode():
    """Test the Long and Short experiments across independent years."""
    run_directional_walk_forward()

def run_long_regime_benchmark_mode():
    """Evaluate Long thresholds specific to trend-up and high-volatility regimes."""
    run_long_regime_benchmark()

def run_long_regime_walk_forward_mode():
    """Walk-forward validation for Long-RANGE and Long-HIGH_VOL setups."""
    run_long_regime_walk_forward()

def run_trend_strategy_audit_mode():
    """Audit raw score-based signals before ML filtering."""
    run_trend_strategy_audit()

def run_trend_exit_audit_mode():
    """Break down raw TrendStrategy PnL by exit reason and entry setup."""
    run_trend_exit_audit()

def run_wyckoff_setup_audit_mode():
    run_setup_audit()

def run_wyckoff_setup_exit_audit_mode():
    run_setup_exit_audit()

def run_wyckoff_definition_audit_mode():
    run_definition_audit()

def run_wyckoff_state_machine_audit_mode():
    run_state_machine_setup_audit()

def run_wyckoff_visual_audit_mode():
    run_visual_audit()

def run_lps_quarterly_audit_mode():
    run_lps_quarterly_audit()

def run_lps_parameter_walk_forward_mode():
    run_lps_parameter_walk_forward()

def run_lps_oos_loss_audit_mode():
    run_lps_oos_loss_audit()

def run_lps_trend_gate_audit_mode():
    run_lps_trend_gate_audit()

def run_paper_trade_mode(oos_from: str = "2026-10-20"):
    verify_freeze()
    update_csv_main()
    indicators_main()
    run_paper_trade(oos_from=oos_from)

def run_short_distribution_audit_mode():
    run_short_distribution_audit()

def run_short_distribution_visual_audit_mode():
    run_short_distribution_visual_audit()

def run_short_distribution_walk_forward_mode():
    run_short_distribution_walk_forward()

def run_short_lpsy_definition_audit_mode():
    run_short_lpsy_definition_audit()

def run_short_lpsy_timing_audit_mode():
    run_short_lpsy_timing_audit()

def run_short_lpsy_break_audit_mode():
    run_short_lpsy_break_audit()

def run_short_shadow_quarterly_audit_mode():
    run_short_shadow_quarterly_audit()

def run_short_shadow_paper_mode():
    update_csv_main()
    indicators_main()
    run_short_shadow_paper()

def run_short_breakdown_weak_test_paper_mode():
    """Update data/features and journal the frozen Short setup; no execution."""
    update_csv_main()
    indicators_main()
    run_short_breakdown_weak_test_paper()
def run_short_htf_definition_audit_mode():
    run_short_htf_definition_audit()

def run_short_transition_gate_audit_mode():
    run_short_transition_gate_audit()

def run_short_transition_exit_audit_mode():
    run_short_transition_exit_audit()

def run_short_transition_breakeven_audit_mode():
    run_short_transition_breakeven_audit()

def run_short_lpsy_event_study_mode():
    run_short_lpsy_event_study()

def run_short_utad_sow_lpsy_audit_mode():
    run_short_utad_sow_lpsy_audit()

def run_short_narrow_range_audit_mode():
    run_short_narrow_range_audit()

def main():
    parser = argparse.ArgumentParser(description="Run the VN30F1M stock bot pipeline.")
    parser.add_argument(
        "--mode",
        choices=["daily", "retrain", "walk-forward", "rolling-benchmark", "directional-benchmark", "directional-walk-forward", "long-regime-benchmark", "long-regime-walk-forward", "strategy-audit", "strategy-exit-audit", "wyckoff-setup-audit", "wyckoff-setup-exit-audit", "wyckoff-definition-audit", "wyckoff-state-machine-audit", "wyckoff-visual-audit", "lps-quarterly-audit", "lps-parameter-walk-forward", "lps-oos-loss-audit", "lps-trend-gate-audit", "short-distribution-audit", "short-distribution-visual-audit", "short-distribution-walk-forward", "short-lpsy-definition-audit", "short-lpsy-timing-audit", "short-lpsy-break-audit", "short-shadow-quarterly-audit", "short-shadow-paper", "short-breakdown-weak-test-paper", "short-htf-definition-audit", "short-transition-gate-audit", "short-transition-exit-audit", "short-transition-breakeven-audit", "short-lpsy-event-study", "short-utad-sow-lpsy-audit", "short-narrow-range-audit", "paper-trade", "verify-freeze", "monitor"],
        required=True,
        help="Pipeline mode: 'daily' runs standard workflow, 'verify-freeze' tests frozen code integrity, 'paper-trade' runs forward paper simulation, 'monitor' tracks paper trade live metrics.",
    )
    parser.add_argument(
        "--oos-from",
        type=str,
        default="2026-10-20",
        help="Out-of-sample forward test starting date (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    if args.mode == "daily":
        run_daily()
    elif args.mode == "retrain":
        run_retrain()
    elif args.mode == "walk-forward":
        run_walk_forward_mode()
    elif args.mode == "rolling-benchmark":
        run_rolling_benchmark_mode()
    elif args.mode == "directional-benchmark":
        run_directional_benchmark_mode()
    elif args.mode == "directional-walk-forward":
        run_directional_walk_forward_mode()
    elif args.mode == "long-regime-benchmark":
        run_long_regime_benchmark_mode()
    elif args.mode == "long-regime-walk-forward":
        run_long_regime_walk_forward_mode()
    elif args.mode == "strategy-audit":
        run_trend_strategy_audit_mode()
    elif args.mode == "strategy-exit-audit":
        run_trend_exit_audit_mode()
    elif args.mode == "wyckoff-setup-audit":
        run_wyckoff_setup_audit_mode()
    elif args.mode == "wyckoff-setup-exit-audit":
        run_wyckoff_setup_exit_audit_mode()
    elif args.mode == "wyckoff-definition-audit":
        run_wyckoff_definition_audit_mode()
    elif args.mode == "wyckoff-state-machine-audit":
        run_wyckoff_state_machine_audit_mode()
    elif args.mode == "wyckoff-visual-audit":
        run_wyckoff_visual_audit_mode()
    elif args.mode == "lps-quarterly-audit":
        run_lps_quarterly_audit_mode()
    elif args.mode == "lps-parameter-walk-forward":
        run_lps_parameter_walk_forward_mode()
    elif args.mode == "lps-oos-loss-audit":
        run_lps_oos_loss_audit_mode()
    elif args.mode == "lps-trend-gate-audit":
        run_lps_trend_gate_audit_mode()
    elif args.mode == "short-distribution-audit":
        run_short_distribution_audit_mode()
    elif args.mode == "short-distribution-visual-audit":
        run_short_distribution_visual_audit_mode()
    elif args.mode == "short-distribution-walk-forward":
        run_short_distribution_walk_forward_mode()
    elif args.mode == "short-lpsy-definition-audit":
        run_short_lpsy_definition_audit_mode()
    elif args.mode == "short-lpsy-timing-audit":
        run_short_lpsy_timing_audit_mode()
    elif args.mode == "short-lpsy-break-audit":
        run_short_lpsy_break_audit_mode()
    elif args.mode == "short-shadow-quarterly-audit":
        run_short_shadow_quarterly_audit_mode()
    elif args.mode == "short-shadow-paper":
        run_short_shadow_paper_mode()
    elif args.mode == "short-breakdown-weak-test-paper":
        run_short_breakdown_weak_test_paper_mode()
    elif args.mode == "short-htf-definition-audit":
        run_short_htf_definition_audit_mode()
    elif args.mode == "short-transition-gate-audit":
        run_short_transition_gate_audit_mode()
    elif args.mode == "short-transition-exit-audit":
        run_short_transition_exit_audit_mode()
    elif args.mode == "short-transition-breakeven-audit":
        run_short_transition_breakeven_audit_mode()
    elif args.mode == "short-lpsy-event-study":
        run_short_lpsy_event_study_mode()
    elif args.mode == "short-utad-sow-lpsy-audit":
        run_short_utad_sow_lpsy_audit_mode()
    elif args.mode == "short-narrow-range-audit":
        run_short_narrow_range_audit_mode()
    elif args.mode == "paper-trade":
        run_paper_trade_mode(oos_from=args.oos_from)
    elif args.mode == "verify-freeze":
        verify_freeze()
    elif args.mode == "monitor":
        monitor_main()
    else:
        raise ValueError(f"Unsupported mode: {args.mode}")

if __name__ == "__main__":
    main()

