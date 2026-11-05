import pandas as pd
from .base import BaseStrategy

class TrendStrategy(BaseStrategy):
    def __init__(self, name="TrendStrategy"):
        super().__init__(name)
        
    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates TrendScore based on EMA and VWAP.
        """
        df = df.copy()
        
        # Initialize scores
        df['TrendScore'] = 0
        df['TrendScore'] = df['TrendScore'].astype(float)
        
        # Rule 1: EMA20 > EMA50 (+20 points), EMA20 < EMA50 (-20 points)
        df.loc[df['EMA20'] > df['EMA50'], 'TrendScore'] += 20
        df.loc[df['EMA20'] < df['EMA50'], 'TrendScore'] -= 20
        
        # Rule 2: EMA50 > EMA200 (+20 points), EMA50 < EMA200 (-20 points)
        df.loc[df['EMA50'] > df['EMA200'], 'TrendScore'] += 20
        df.loc[df['EMA50'] < df['EMA200'], 'TrendScore'] -= 20
        
        # Rule 3: Close > VWAP (+20 points), Close < VWAP (-20 points)
        df.loc[df['Close'] > df['VWAP'], 'TrendScore'] += 20
        df.loc[df['Close'] < df['VWAP'], 'TrendScore'] -= 20
        
        # Basic Volume/Momentum for V1 placeholder
        df['VolumeScore'] = 0.0
        df.loc[df['RVOL'] > 1.5, 'VolumeScore'] += 20
        
        df['MomentumScore'] = 0.0
        df.loc[df['RSI'] > 55, 'MomentumScore'] += 10
        df.loc[df['RSI'] < 45, 'MomentumScore'] -= 10
        
        # Structure score placeholder
        df['StructureScore'] = 0.0
        
        return df

    def generate_entry_signals(
        self,
        df: pd.DataFrame,
        score_threshold: float = 40,
        adx_threshold: float = 25,
        breakout_window: int = 20,
        signal_cooldown_bars: int = 15,
    ) -> pd.DataFrame:
        """Convert scores into sparse, event-based trade candidates.

        A signal requires a score crossing, a confirmed EMA/ADX trend, and a
        breakout or pullback-reclaim.  After an entry the same direction stays
        locked until its EMA trend breaks; this prevents repeated entries while
        a score merely remains above/below its threshold.
        """
        df = df.copy()
        score_columns = ["TrendScore", "StructureScore", "VolumeScore", "MomentumScore"]
        df["TotalScore"] = df[score_columns].sum(axis=1)
        previous_score = df["TotalScore"].shift(1).fillna(0.0)
        long_cross = (df["TotalScore"] >= score_threshold) & (previous_score < score_threshold)
        short_cross = (df["TotalScore"] <= -score_threshold) & (previous_score > -score_threshold)

        prior_high = df["High"].rolling(breakout_window).max().shift(1)
        prior_low = df["Low"].rolling(breakout_window).min().shift(1)
        long_breakout = df["Close"] > prior_high
        short_breakout = df["Close"] < prior_low
        long_pullback = (df["Low"] <= df["EMA20"]) & (df["Close"] > df["EMA20"]) & (df["Close"] > df["Open"])
        short_pullback = (df["High"] >= df["EMA20"]) & (df["Close"] < df["EMA20"]) & (df["Close"] < df["Open"])
        long_trend = (df["EMA20"] > df["EMA50"]) & (df["EMA50"] > df["EMA200"]) & (df["Close"] > df["VWAP"]) & (df["ADX"] >= adx_threshold)
        short_trend = (df["EMA20"] < df["EMA50"]) & (df["EMA50"] < df["EMA200"]) & (df["Close"] < df["VWAP"]) & (df["ADX"] >= adx_threshold)
        long_candidate = long_cross & long_trend & (long_breakout | long_pullback)
        short_candidate = short_cross & short_trend & (short_breakout | short_pullback)

        signals = []
        setups = []
        long_armed = True
        short_armed = True
        cooldown = 0
        for is_long_trend, is_short_trend, is_long_candidate, is_short_candidate in zip(
            long_trend.fillna(False), short_trend.fillna(False), long_candidate.fillna(False), short_candidate.fillna(False), strict=True
        ):
            if cooldown > 0:
                cooldown -= 1
            if not is_long_trend:
                long_armed = True
            if not is_short_trend:
                short_armed = True
            signal = 0
            setup = ""
            if cooldown == 0 and is_long_candidate and long_armed:
                signal = 1
                setup = "LONG_BREAKOUT" if long_breakout.iloc[len(signals)] else "LONG_PULLBACK"
                long_armed = False
                cooldown = signal_cooldown_bars
            elif cooldown == 0 and is_short_candidate and short_armed:
                signal = -1
                setup = "SHORT_BREAKOUT" if short_breakout.iloc[len(signals)] else "SHORT_PULLBACK"
                short_armed = False
                cooldown = signal_cooldown_bars
            signals.append(signal)
            setups.append(setup)
        df["StrategySignal"] = signals
        df["EntrySetup"] = setups
        df["ScoreCrossLong"] = long_cross.astype(int)
        df["ScoreCrossShort"] = short_cross.astype(int)
        return df

    def generate_wyckoff_long_signals(
        self,
        df: pd.DataFrame,
        score_threshold: float = 40,
        adx_threshold: float = 25,
        spring_window: int = 20,
        max_bars_after_spring: int = 16,
    ) -> pd.DataFrame:
        """Create a conservative Phase-C-to-D Long candidate from OHLCV proxies.

        This is not a claim that OHLCV can identify institutional intent.  It
        encodes testable proxies for Spring -> low-volume Test -> Higher-Low /
        No-Supply LPS, then requires larger-trend, MA and BB confirmation.
        No breakout entry is emitted; the candidate is the LPS after a Spring.
        """
        df = df.copy()
        score_columns = ["TrendScore", "StructureScore", "VolumeScore", "MomentumScore"]
        df["TotalScore"] = df[score_columns].sum(axis=1)
        prior_support = df["Low"].rolling(spring_window).min().shift(1)
        prior_range_high = df["High"].rolling(10).max().shift(1)
        spread = (df["High"] - df["Low"]).mask(lambda values: values == 0, float("nan"))
        median_spread = spread.rolling(20).median()
        ma_cluster = (df[["EMA10", "EMA20", "EMA50", "EMA100"]].max(axis=1) - df[["EMA10", "EMA20", "EMA50", "EMA100"]].min(axis=1)) / df["Close"]
        ma_squeeze = ma_cluster <= ma_cluster.rolling(120, min_periods=60).quantile(0.35)
        bb_squeeze = df["BB_Width"] <= df["BB_Width"].rolling(120, min_periods=60).quantile(0.25)

        trend_filter = (
            (df["EMA200"].pct_change(20) > 0)
            & (df["EMA50"] > df["EMA200"])
            & (df["Close"] > df["EMA50"])
            & (df["TrendScore"] >= score_threshold)
            & (df["ADX"] >= adx_threshold)
        )
        spring = (
            (df["Low"] < prior_support)
            & (df["Close"] > prior_support)
            & (df["RVOL"] >= 1.5)
            & (df["Close"] >= df["Open"])
        )
        sos = (df["Close"] > prior_range_high) & (df["RVOL"] >= 1.2)
        df["WyckoffSpring"] = spring.astype(int)
        df["WyckoffSOS"] = sos.astype(int)
        df["WyckoffTest"] = 0
        df["WyckoffLPS"] = 0
        df["DemandZone"] = 0
        df["MASqueeze"] = ma_squeeze.astype(int)
        df["BBSqueeze"] = bb_squeeze.astype(int)
        df["StrategySignal"] = 0
        df["EntrySetup"] = ""

        spring_low = spring_volume = spring_atr = None
        spring_index = -max_bars_after_spring - 1
        test_seen = False
        squeeze_seen = False
        bb_squeeze_value = None
        locked_until_new_spring = False
        lps_index = -max_bars_after_spring - 1

        for position, (_, row) in enumerate(df.iterrows()):
            if bool(spring.iloc[position]):
                spring_low = row["Low"]
                spring_volume = row["Volume"]
                spring_atr = row["ATR"]
                spring_index = position
                test_seen = False
                squeeze_seen = bool(ma_squeeze.iloc[position] or bb_squeeze.iloc[position])
                bb_squeeze_value = row["BB_Width"] if bool(bb_squeeze.iloc[position]) else None
                locked_until_new_spring = False
                lps_index = -max_bars_after_spring - 1
                continue
            if spring_low is None or position - spring_index > max_bars_after_spring:
                continue
            if bool(ma_squeeze.iloc[position] or bb_squeeze.iloc[position]):
                squeeze_seen = True
                if bool(bb_squeeze.iloc[position]):
                    bb_squeeze_value = row["BB_Width"]
            atr = row["ATR"]
            if pd.isna(atr) or atr <= 0:
                continue
            in_demand_zone = row["Low"] >= spring_low and row["Close"] <= spring_low + 5.0 * atr
            df.iloc[position, df.columns.get_loc("DemandZone")] = int(in_demand_zone)
            # Test: low-volume retest above Spring low, closing in upper half.
            test = (
                in_demand_zone
                and row["Low"] <= spring_low + 1.5 * atr
                and row["Volume"] <= spring_volume * 0.70
                and row["Close"] >= (row["High"] + row["Low"]) / 2
            )
            if test:
                test_seen = True
                df.iloc[position, df.columns.get_loc("WyckoffTest")] = 1
                continue
            # LPS / No Supply after Test: higher low, narrow down-bar or a
            # quiet retest.  This is the intended entry, not an SOS breakout.
            no_supply = (
                row["Volume"] <= row["Volume_MA20"] * 0.80
                and spread.iloc[position] <= median_spread.iloc[position]
                and row["Close"] >= (row["High"] + row["Low"]) / 2
            )
            higher_low = row["Low"] > spring_low
            ma_cross_or_opening = (
                (df["EMA10"].iloc[position] > df["EMA20"].iloc[position])
                and (df["EMA20"].pct_change(3).iloc[position] > 0)
            )
            bb_expansion = bb_squeeze_value is not None and row["BB_Width"] >= bb_squeeze_value * 1.10
            lps = test_seen and in_demand_zone and higher_low and no_supply
            if lps:
                df.iloc[position, df.columns.get_loc("WyckoffLPS")] = 1
                lps_index = position
            # Phase C and Phase D normally span several candles.  Once LPS is
            # confirmed, allow a short confirmation window for MA/BB expansion
            # rather than incorrectly requiring every event on the LPS candle.
            lps_confirmed = 0 <= position - lps_index <= 6
            if (
                not locked_until_new_spring
                and lps_confirmed
                and bool(trend_filter.iloc[position])
                and in_demand_zone
                and squeeze_seen
                and ma_cross_or_opening
                and bb_expansion
            ):
                df.iloc[position, df.columns.get_loc("StrategySignal")] = 1
                df.iloc[position, df.columns.get_loc("EntrySetup")] = "WYCKOFF_LPS_LONG"
                locked_until_new_spring = True
        return df

    def generate_multitimeframe_wyckoff_long_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Use completed 5m/15m Phase-C context and 1m LPS timing.

        The 5m Spring/Test state supplies the event, 15m supplies the larger
        trend/demand context, and the 1m bar is used only for a quiet LPS
        reclaim.  There is deliberately no 1m breakout entry.
        """
        df = df.copy()
        score_columns = ["TrendScore", "StructureScore", "VolumeScore", "MomentumScore"]
        df["TotalScore"] = df[score_columns].sum(axis=1)
        required = [
            "HTF_5m_Ready", "HTF_5m_DemandZone", "HTF_15m_DemandZone", "HTF_15m_TrendOK",
        ]
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise ValueError(f"Missing higher-timeframe Wyckoff context: {missing}")
        htf_context = (
            (df["HTF_5m_Ready"] == 1)
            & (df["HTF_5m_DemandZone"] == 1)
            & (df["HTF_15m_DemandZone"] == 1)
            & (df["HTF_15m_TrendOK"] == 1)
        )
        spread = (df["High"] - df["Low"]).mask(lambda values: values == 0, float("nan"))
        no_supply = (
            (df["Volume"] <= df["Volume_MA20"] * 0.80)
            & (spread <= spread.rolling(20).median())
            & (df["Close"] >= (df["High"] + df["Low"]) / 2)
        )
        timing = (
            (df["EMA10"] > df["EMA20"])
            & (df["EMA20"] > df["EMA50"])
            & (df["Close"] > df["EMA20"])
            & no_supply
            & (df["TrendScore"] >= 40)
        )
        df["WyckoffHTFContext"] = htf_context.astype(int)
        df["Wyckoff1mLPS"] = timing.astype(int)
        df["StrategySignal"] = (htf_context & timing).astype(int)
        df["EntrySetup"] = ""
        df.loc[df["StrategySignal"] == 1, "EntrySetup"] = "HTF_WYCKOFF_LPS_LONG"
        return df

    def generate_scored_wyckoff_long_signals(self, df: pd.DataFrame, minimum_score: int = 35) -> pd.DataFrame:
        """4 Mirrored Wyckoff Long Setups (Spring, Demand Retest, LPS, SOS).

        Generates a balanced, high-quality candidate population of Long Wyckoff signals
        symmetric to the 4 Short setups for ML training and prediction.
        """
        df = df.copy()
        score_columns = ["TrendScore", "StructureScore", "VolumeScore", "MomentumScore"]
        df["TotalScore"] = df[score_columns].sum(axis=1)
        required = [
            "HTF_5m_Accumulation", "HTF_5m_DemandZone", "HTF_5m_LPS", "HTF_5m_Spring", "HTF_5m_Test", "HTF_5m_SOS", "HTF_15m_TrendOK",
        ]
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise ValueError(f"Missing higher-timeframe Wyckoff context: {missing}")

        spread = (df["High"] - df["Low"]).mask(lambda values: values == 0, float("nan"))

        # VSA No Supply / Absorption at Support (1m Timing):
        # Low tests EMA20/VWAP/EMA10, low volume, narrow spread or lower wick (rejection of selling).
        at_support = (df["Low"] <= df["EMA20"]) | (df["Low"] <= df["VWAP"]) | (df["Close"] > df["EMA10"])
        lower_wick_or_strong_close = (df["Close"] - df["Low"] >= spread * 0.35) | (df["Close"] >= df["Low"] + spread * 0.50)
        no_supply = (
            (df["Volume"] <= df["Volume_MA20"] * 0.85)
            & (spread <= spread.rolling(20).median() * 0.95)
            & at_support
            & lower_wick_or_strong_close
        )

        # Bộ lọc xu hướng lớn cho Long (Symmetric với hard_short_trend)
        hard_long_trend = (
            (df["MarketRegime"] == "TREND_UP")
            | (df["HTF_15m_TrendOK"] == 1)
            | ((df["Close"] > df["EMA50"]) & (df["EMA20"] > df["EMA50"]))
        )

        # 1. SETUP 1: SPRING PHASE C & TEST (WYCKOFF_SPRING_TEST_LONG)
        # Rũ bỏ thủng đáy giả trên 5m (Spring / Test). Khung 15m không phải Downtrend mạnh
        spring_candle = ((df["HTF_5m_Spring"] == 1) | (df["HTF_5m_Test"] == 1)) & (df["HTF_15m_TrendDownOK"] == 0)
        spring_start = spring_candle & ~spring_candle.shift(1, fill_value=False)
        spring_window = spring_start.shift(1, fill_value=False).rolling(6, min_periods=1).max().astype(bool)
        spring_reclaim = (df["Close"] > df["Open"]) & (df["Close"] > df["EMA10"])
        spring_timing = spring_window & (no_supply | spring_reclaim)

        # 2. SETUP 2: DEMAND ZONE RETEST (DEMAND_ZONE_RETEST)
        # Retest vùng cầu khi 15m Uptrend + nến 1m rút chân và đóng cửa trên EMA10
        demand_event = (df["HTF_5m_DemandZone"] == 1) & hard_long_trend
        demand_start = demand_event & ~demand_event.shift(1, fill_value=False)
        demand_window = demand_start.shift(1, fill_value=False).rolling(6, min_periods=1).max().astype(bool)
        demand_timing = demand_window & no_supply & (df["Close"] > df["Open"]) & (df["Close"] > df["EMA10"])

        # 3. SETUP 3: LPS RECLAIM (LPS_SUPPORT_RECLAIM)
        # Last Point of Support - nến hẹp volume cạn kiệt trên hỗ trợ
        lps_event = (df["HTF_5m_LPS"] == 1) & hard_long_trend
        lps_start = lps_event & ~lps_event.shift(1, fill_value=False)
        lps_window_1_3 = lps_start.shift(1, fill_value=False).rolling(3, min_periods=1).max().astype(bool)
        lps_timing = lps_window_1_3 & no_supply

        # 4. SETUP 4: SOS BREAKOUT PULLBACK (SOS_BREAKOUT_PULLBACK)
        # Sign of Strength kiểm tra lại đỉnh cũ
        sos_event = (df["HTF_5m_SOS"] == 1) & hard_long_trend
        sos_start = sos_event & ~sos_event.shift(1, fill_value=False)
        sos_pending = sos_start.shift(1, fill_value=False).rolling(12, min_periods=1).max().astype(bool)
        strong_pullback = (df["Low"] >= df["Low"].shift(1)) & (df["Close"] > df["EMA10"])
        sos_timing = sos_pending & (strong_pullback | no_supply)

        # 4 Nhóm Setup Long Chuẩn Mực
        long_candidate_event = spring_timing | demand_timing | lps_timing | sos_timing
        long_candidate = (hard_long_trend | spring_timing) & long_candidate_event

        # Score calculation for ML feature diagnostic
        atr_stable = df["ATR_Percent"] <= df["ATR_Percent"].rolling(120, min_periods=60).quantile(0.80)
        bb_expanding = df["BB_Width"] > df["BB_Width"].rolling(60, min_periods=30).median()
        wyckoff_score = pd.Series(0, index=df.index, dtype=float)
        wyckoff_score += (df["EMA10"] > df["EMA20"]).astype(int) * 8
        wyckoff_score += (df["EMA20"] > df["EMA50"]).astype(int) * 8
        wyckoff_score += (df["Close"] > df["VWAP"]).astype(int) * 7
        wyckoff_score += (df["TrendScore"] >= 40).astype(int) * 7
        wyckoff_score += no_supply.astype(int) * 12
        wyckoff_score += (df["RVOL"] >= 1.0).astype(int) * 5
        wyckoff_score += atr_stable.astype(int) * 5
        wyckoff_score += bb_expanding.astype(int) * 5
        wyckoff_score += (df["HTF_5m_LPS"] == 1).astype(int) * 12
        wyckoff_score += (df["HTF_5m_Spring"] == 1).astype(int) * 10
        wyckoff_score += (df["HTF_5m_DemandZone"] == 1).astype(int) * 10
        wyckoff_score += (df["HTF_5m_SOS"] == 1).astype(int) * 10

        df["WyckoffScore"] = wyckoff_score
        df["VSA_NoSupply"] = no_supply.astype(int)
        df["LPS1mPullbackReclaim"] = lps_timing.astype(int)
        df["DemandZoneRetestTiming"] = demand_timing.astype(int)
        df["SpringTestTiming"] = spring_timing.astype(int)
        df["SOSTiming"] = sos_timing.astype(int)
        df["HardTrendOK"] = hard_long_trend.astype(int)
        df["HardDemandOrAccumulationOK"] = (demand_window | spring_window).astype(int)
        df["HardWyckoffEventOK"] = long_candidate_event.astype(int)

        # Signal generation trigger
        signal_trigger = long_candidate & ~long_candidate.shift(1, fill_value=False)
        df["StrategySignal"] = signal_trigger.astype(int)
        df["EntrySetup"] = ""
        df.loc[spring_timing & signal_trigger, "EntrySetup"] = "WYCKOFF_SPRING_TEST_LONG"
        df.loc[demand_timing & signal_trigger, "EntrySetup"] = "DEMAND_ZONE_RETEST"
        df.loc[lps_timing & signal_trigger, "EntrySetup"] = "LPS_SUPPORT_RECLAIM"
        df.loc[sos_timing & signal_trigger, "EntrySetup"] = "SOS_BREAKOUT_PULLBACK"

        return df

    def generate_scored_wyckoff_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate high-quality Long (1) and Short (-1) Wyckoff candidate signals.

        Architecture 2 (Two-Way Execution):
        - Longs: HTF 15m Trend + (LPS + 1-3 bar NO_SUPPLY | SPRING/TEST + Reclaim | SOS).
        - Shorts: HTF 15m Downtrend + (LPSY + 1-3 bar NO_DEMAND | UTAD/SOW + Re-break | NARROW_RANGE_BREAKDOWN).
        """
        df = self.generate_scored_wyckoff_long_signals(df)

        # --- SHORT SIGNAL GENERATION (Option 2: Upthrust Rejection & No-Demand Retest) ---

        required_short = ["HTF_15m_TrendDownOK", "HTF_15m_TrendTransitionDown", "HTF_5m_Distribution", "HTF_5m_SupplyZone", "HTF_5m_LPSY", "HTF_5m_SequenceLPSY", "HTF_5m_UTAD", "HTF_5m_SOW", "HTF_5m_BreakdownWeakTest"]
        missing = [col for col in required_short if col not in df.columns]
        if missing:
            raise ValueError(f"Missing higher-timeframe Wyckoff Short context: {missing}")

        spread = (df["High"] - df["Low"]).mask(lambda values: values == 0, float("nan"))
        
        # No Demand / Upthrust Rejection at Resistance:
        # High tests EMA20/VWAP/EMA10, low volume, narrow spread or upper wick (rejection).
        at_resistance = (df["High"] >= df["EMA20"]) | (df["High"] >= df["VWAP"]) | (df["Close"] < df["EMA10"])
        upper_wick_or_weak_close = (df["High"] - df["Close"] >= spread * 0.35) | (df["Close"] <= df["Low"] + spread * 0.50)
        
        no_demand = (
            (df["Volume"] <= df["Volume_MA20"] * 0.85)
            & (spread <= spread.rolling(20).median() * 0.95)
            & at_resistance
            & upper_wick_or_weak_close
        )

        # --- BỘ LỌC XU HƯỚNG 15M (BỎ HOÀN TOÀN EMA 1M NHIỄU) ---
        hard_short_trend = (
            (df["MarketRegime"] == "TREND_DOWN")
            | (df["HTF_15m_TrendDownOK"] == 1)
            | (df["HTF_15m_TrendTransitionDown"] == 1)
        )

        # 1. PURE UTAD BULL TRAP TRIGGER (Phase C)
        # Bắt cú rướn vượt đỉnh giả chuẩn mực trên 5m (High > RangeHigh, Vol >= 1.3x MA20, râu trên dài, đóng ở 40% đáy nến);
        # Khung 15m không được là Uptrend mạnh (HTF_15m_TrendOK == 0) để tránh bắt đỉnh ngược sóng tăng lớn
        utad_candle = (df["HTF_5m_UTAD"] == 1) & (df["HTF_15m_TrendOK"] == 0)
        utad_start = utad_candle & ~utad_candle.shift(1, fill_value=False)
        utad_window = utad_start.shift(1, fill_value=False).rolling(6, min_periods=1).max().astype(bool)
        utad_timing = utad_window & no_demand

        # 2. RETEST ĐỈNH HỘP VÙNG CUNG (SupplyZone) - Yêu cầu xác nhận nến 1m gãy dưới EMA10
        supply_event = (df["HTF_5m_SupplyZone"] == 1) & hard_short_trend
        supply_start = supply_event & ~supply_event.shift(1, fill_value=False)
        supply_window = supply_start.shift(1, fill_value=False).rolling(6, min_periods=1).max().astype(bool)
        supply_timing = supply_window & no_demand & (df["Close"] < df["Open"]) & (df["Close"] < df["EMA10"])

        # 3. LPSY Resistance Retest (Phase D)
        lpsy_event = ((df["HTF_5m_LPSY"] == 1) | (df["HTF_5m_SequenceLPSY"] == 1)) & hard_short_trend
        lpsy_start = lpsy_event & ~lpsy_event.shift(1, fill_value=False)
        lpsy_window_1_3 = lpsy_start.shift(1, fill_value=False).rolling(3, min_periods=1).max().astype(bool)
        lpsy_timing = lpsy_window_1_3 & no_demand

        # 4. SOW Weak Pullback Rejection (Phase D/E)
        sow_event = ((df["HTF_5m_SOW"] == 1) | (df["HTF_5m_BreakdownWeakTest"] == 1)) & hard_short_trend
        sow_start = sow_event & ~sow_event.shift(1, fill_value=False)
        sow_pending = sow_start.shift(1, fill_value=False).rolling(12, min_periods=1).max().astype(bool)
        weak_pullback = (df["High"] <= df["High"].shift(1)) & (df["Close"] < df["EMA10"])
        sow_timing = sow_pending & (weak_pullback | no_demand)

        # 4 Nhóm Setup Wyckoff Chuẩn Mực theo Spec README.md (Đã loại bỏ setup Distribution đại trà)
        short_candidate_event = utad_timing | supply_timing | lpsy_timing | sow_timing
        short_candidate = (hard_short_trend | utad_timing) & short_candidate_event

        short_signal_trigger = short_candidate & ~short_candidate.shift(1, fill_value=False)

        # Assign Short (-1) to StrategySignal where Long (1) is not already present
        short_mask = short_signal_trigger & (df["StrategySignal"] == 0)
        df.loc[short_mask, "StrategySignal"] = -1
        df.loc[utad_timing & short_mask, "EntrySetup"] = "UTAD_UPTHRUST_REJECTION"
        df.loc[supply_timing & short_mask, "EntrySetup"] = "SUPPLY_ZONE_RETEST"
        df.loc[lpsy_timing & short_mask, "EntrySetup"] = "LPSY_RESISTANCE_RETEST"
        df.loc[sow_timing & short_mask, "EntrySetup"] = "SOW_WEAK_PULLBACK_SHORT"
        return df





