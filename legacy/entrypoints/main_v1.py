from datetime import datetime
from trading_engine.data.loader import DataLoader
from trading_engine.data.indicators import IndicatorEngine
from trading_engine.strategy.trend import TrendStrategy
from trading_engine.strategy.structure import StructureStrategy
from trading_engine.strategy.signal import SignalEngine
from trading_engine.backtest.engine import BacktestEngine
from trading_engine.backtest.report import ReportGenerator

from trading_engine.data.vci_api import fetch_vn30f1m_daily

def main():
    print("--- Starting VN30F1M Trading Bot Framework (V1) ---")
    
    # 1. Load Data
    print("Loading data from VCI API...")
    df = fetch_vn30f1m_daily(days=10000)
    print(f"Loaded {len(df)} daily candles.")
    
    # 2. Calculate Indicators
    print("Calculating indicators...")
    df = IndicatorEngine.calculate_all(df)
    
    # 3. Apply Strategies
    print("Applying Trend Strategy...")
    trend_strategy = TrendStrategy()
    df = trend_strategy.calculate_scores(df)
    
    print("Applying Structure Strategy...")
    structure_strategy = StructureStrategy()
    df = structure_strategy.calculate_scores(df)
    
    # 4. Generate Signals
    print("Generating Signals...")
    signal_engine = SignalEngine(buy_threshold=40, sell_threshold=-40)
    df = signal_engine.generate_signals(df)
    
    from trading_engine.strategy.risk import RiskEngine
    from trading_engine.ml.filter import MLFilter
    
    # 5. Apply ML Filter
    print("Applying ML Filter...")
    ml_filter = MLFilter(threshold=0.55) # E.g., 55% win probability
    df = ml_filter.filter_signals(df)
    
    # 6. Run Backtest
    print("Initializing Risk Engine and Running Backtest...")
    risk_engine = RiskEngine(risk_per_trade=0.01, sl_atr_multiplier=1.5, tp_atr_multiplier=3.0, trailing_sl_atr_multiplier=1.5)
    bt_engine = BacktestEngine(df, risk_engine=risk_engine, initial_capital=100000000.0)
    trade_log = bt_engine.run()
    metrics = bt_engine.get_metrics()
    
    # 6. Generate Report
    print("Generating Reports...")
    run_name = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    report_gen = ReportGenerator()
    report_gen.generate(run_name, trade_log, metrics, price_data=df)
    
    print("--- Backtest Complete ---")
    print(metrics)

if __name__ == "__main__":
    main()
