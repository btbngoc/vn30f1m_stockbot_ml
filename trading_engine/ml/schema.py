"""Shared machine-learning feature schema."""

ML_FEATURE_COLUMNS = [
    "TrendScore", "StructureScore", "VolumeScore", "MomentumScore",
    "ATR", "ADX", "RSI", "VWAP_Distance", "EMA_Distance", "RVOL",
    "TimeOfDay", "DayOfWeek",
    "Return_5", "Return_15", "Return_30", "Return_60",
    "ATR_Percent", "RealizedVol_30", "EMA20_Slope_5", "EMA50_Slope_15",
    "Distance_DayHigh", "Distance_DayLow", "Volume_Spike", "Volume_Imbalance_20",
    "OpenSession", "LunchSession", "CloseSession", "HTF_5m_Trend",
    "HTF_15m_Trend", "HTF_1h_Trend", "ADX_Regime", "BB_Width",
    "RegimeCode", "WyckoffScore", "VSA_NoSupply", "HardWyckoffEventOK",
]


