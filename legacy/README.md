# Legacy flow archive

These files belong to the pre-refactor daily-API / LightGBM / Triple-Barrier
flow. They are retained for reference only and are not imported by the current
`run_pipeline.py` entry point.

The active flow starts with `run_pipeline.py` and uses the CSV update,
feature-parquet, XGBoost prediction, backtest, analysis, visualization, and
report modules under `trading_engine`.

The archived files retain their original imports and are intentionally not a
supported executable pipeline. Restore or adapt them only if the legacy flow is
deliberately brought back.
