import pandas as pd
import pandas_ta as ta
from ..strategy.trend import TrendStrategy

class IndicatorEngine:
    """
    Computes technical indicators without generating trading signals.
    """
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Moving Averages
        df['EMA10'] = ta.ema(df['Close'], length=10)
        df['EMA20'] = ta.ema(df['Close'], length=20)
        df['EMA50'] = ta.ema(df['Close'], length=50)
        df['EMA100'] = ta.ema(df['Close'], length=100)
        df['EMA200'] = ta.ema(df['Close'], length=200)
        df['EMA_Distance'] = (df['Close'] - df['EMA20']) / df['EMA20']
        
        # VWAP
        df['VWAP'] = ta.vwap(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'])
        df['VWAP_Distance'] = (df['Close'] - df['VWAP']) / df['VWAP']
        
        # Volatility / Risk
        df['ATR'] = ta.atr(high=df['High'], low=df['Low'], close=df['Close'], length=14)
        
        # Momentum
        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_Signal'] = macd['MACDs_12_26_9']
            df['MACD_Hist'] = macd['MACDh_12_26_9']
            
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # Bollinger Bands
        bb = ta.bbands(df['Close'], length=20, std=2)
        if bb is not None:
            df['BB_Lower'] = bb.iloc[:, 0]
            df['BB_Mid'] = bb.iloc[:, 1]
            df['BB_Upper'] = bb.iloc[:, 2]
            
        # Trend Strength
        adx = ta.adx(high=df['High'], low=df['Low'], close=df['Close'], length=14)
        if adx is not None:
            df['ADX'] = adx['ADX_14']
            
        # Volume
        df['Volume_MA20'] = ta.sma(df['Volume'], length=20)
        df['RVOL'] = df['Volume'] / df['Volume_MA20']
        df['Return_5'] = df['Close'].pct_change(5)
        df['Return_15'] = df['Close'].pct_change(15)
        df['Return_30'] = df['Close'].pct_change(30)
        df['Return_60'] = df['Close'].pct_change(60)
        df['ATR_Percent'] = df['ATR'] / df['Close']
        df['RealizedVol_30'] = df['Close'].pct_change().rolling(30).std()
        df['EMA20_Slope_5'] = df['EMA20'].pct_change(5)
        df['EMA50_Slope_15'] = df['EMA50'].pct_change(15)
        trading_day = pd.Series(df.index.date, index=df.index)
        day_high = df['High'].groupby(trading_day).cummax()
        day_low = df['Low'].groupby(trading_day).cummin()
        df['Distance_DayHigh'] = (df['Close'] - day_high) / day_high
        df['Distance_DayLow'] = (df['Close'] - day_low) / day_low
        df['Volume_Spike'] = df['RVOL']
        signed_volume = df['Volume'].where(df['Close'] >= df['Open'], -df['Volume'])
        df['Volume_Imbalance_20'] = signed_volume.rolling(20).sum() / df['Volume'].rolling(20).sum()
        df['OpenSession'] = (df.index.hour == 9).astype(int)
        df['LunchSession'] = ((df.index.hour == 11) | (df.index.hour == 13)).astype(int)
        df['CloseSession'] = (df.index.hour >= 14).astype(int)
        # Equivalent 5m/15m/1h regimes from 1-minute EMA spans.  Using
        # resample() across overnight/weekend gaps creates millions of empty
        # time bins and can exhaust memory on the full historical dataset.
        for minutes, column in [(5, 'HTF_5m_Trend'), (15, 'HTF_15m_Trend'), (60, 'HTF_1h_Trend')]:
            higher_fast = df['Close'].ewm(span=10 * minutes, adjust=False).mean()
            higher_slow = df['Close'].ewm(span=30 * minutes, adjust=False).mean()
            df[column] = (higher_fast > higher_slow).astype(int).replace(0, -1)
        df['ADX_Regime'] = (df['ADX'] >= 25).astype(int)
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']
        # Exclusive market regimes.  The rolling median is backward-looking,
        # so a row never uses future volatility to classify itself.
        atr_baseline = df['ATR_Percent'].rolling(240, min_periods=60).median()
        high_volatility = df['ATR_Percent'] > (atr_baseline * 1.5)
        trend_up = (df['ADX'] >= 25) & (df['EMA20'] > df['EMA50'])
        trend_down = (df['ADX'] >= 25) & (df['EMA20'] < df['EMA50'])
        df['RegimeCode'] = 0  # range / neutral
        df.loc[trend_up, 'RegimeCode'] = 1
        df.loc[trend_down, 'RegimeCode'] = -1
        df.loc[high_volatility, 'RegimeCode'] = 2
        df['MarketRegime'] = df['RegimeCode'].map({
            -1: 'TREND_DOWN', 0: 'RANGE', 1: 'TREND_UP', 2: 'HIGH_VOL',
        })
        # Time features (dùng DatetimeIndex sẵn có)
        df['TimeOfDay'] = df.index.hour + df.index.minute / 60
        df['DayOfWeek'] = df.index.dayofweek
        df = IndicatorEngine._add_htf_wyckoff_context(df)

        return df

    @staticmethod
    def _add_htf_wyckoff_context(df: pd.DataFrame) -> pd.DataFrame:
        """Map completed 5m/15m Wyckoff proxies to one-minute bars.

        ``groupby(index.floor())`` creates only observed buckets, unlike
        resample which previously expanded overnight/weekend gaps in memory.
        Every value is shifted by one HTF bar before mapping back, preventing
        the 1m signal from seeing an unfinished higher-timeframe candle.
        """
        df = df.copy()
        for minutes in (5, 15):
            frequency = f"{minutes}min"
            bucket = df.index.floor(frequency)
            htf = df.groupby(bucket).agg(
                Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"),
                Close=("Close", "last"), Volume=("Volume", "sum"),
            )
            htf["EMA10"] = htf["Close"].ewm(span=10, adjust=False).mean()
            htf["EMA20"] = htf["Close"].ewm(span=20, adjust=False).mean()
            htf["EMA50"] = htf["Close"].ewm(span=50, adjust=False).mean()
            htf["EMA200"] = htf["Close"].ewm(span=200, adjust=False).mean()
            htf["VolumeMA20"] = htf["Volume"].rolling(20).mean()
            previous_close = htf["Close"].shift(1)
            true_range = pd.concat([
                htf["High"] - htf["Low"],
                (htf["High"] - previous_close).abs(),
                (htf["Low"] - previous_close).abs(),
            ], axis=1).max(axis=1)
            htf["ATR14"] = true_range.rolling(14).mean()
            htf["RangeHigh"] = htf["High"].rolling(24).max().shift(1)
            htf["RangeLow"] = htf["Low"].rolling(24).min().shift(1)
            htf["RangeWidth"] = htf["RangeHigh"] - htf["RangeLow"]
            htf["Accumulation"] = (
                (htf["Close"] >= htf["RangeLow"])
                & (htf["Close"] <= htf["RangeHigh"])
                & (htf["RangeWidth"] >= htf["ATR14"] * 2.0)
                & (htf["RangeWidth"] <= htf["ATR14"] * 10.0)
                & (htf["EMA20"].diff(12).abs() <= htf["ATR14"] * 1.5)
            )
            htf["DemandZone"] = (
                htf["Accumulation"]
                & (htf["Close"] <= htf["RangeLow"] + htf["RangeWidth"] * 0.40)
            )
            # A distinct narrow-range breakdown setup for Short research.
            # It is not reused by either Long or the earlier UTAD/LPSY tests.
            htf["NarrowRange"] = (
                (htf["Close"] >= htf["RangeLow"])
                & (htf["Close"] <= htf["RangeHigh"])
                & (htf["RangeWidth"] >= htf["ATR14"] * 2.0)
                & (htf["RangeWidth"] <= htf["ATR14"] * 5.0)
                & (htf["EMA20"].diff(12).abs() <= htf["ATR14"] * 0.75)
            )
            # Short research uses a separate, mirrored state machine.  These
            # are deliberately separate fields: changing the definition of a
            # distribution must never change the already-fixed Long setup.
            htf["Distribution"] = htf["Accumulation"].copy()
            htf["SupplyZone"] = (
                htf["Distribution"]
                & (htf["Close"] >= htf["RangeHigh"] - htf["RangeWidth"] * 0.40)
            )
            htf["Spring"] = (
                htf["Accumulation"].shift(1).fillna(False)
                & (htf["Low"] < htf["RangeLow"])
                & (htf["Close"] > htf["RangeLow"])
                & (htf["Close"] >= htf["Low"] + (htf["High"] - htf["Low"]) * 0.60)
                & (htf["Volume"] >= htf["VolumeMA20"] * 1.30)
            )
            htf["TrendOK"] = (
                (htf["EMA200"].pct_change(10) > 0)
                & (htf["EMA50"] > htf["EMA200"])
                & (htf["Close"] > htf["EMA50"])
            )
            htf["TrendDownOK"] = (
                (htf["EMA200"].pct_change(10) < 0)
                & (htf["EMA50"] < htf["EMA200"])
                & (htf["Close"] < htf["EMA50"])
            )
            # Faster 15m transition gate for Short research.  Unlike
            # TrendDownOK it does not wait for the slow EMA50/EMA200 cross;
            # it is mapped only after the 15m candle has completed.
            htf["TrendTransitionDown"] = (
                (htf["Close"] < htf["EMA20"])
                & (htf["EMA10"] < htf["EMA20"])
                & (htf["EMA20"].diff(3) < 0)
            )
            previous_distribution = htf["Distribution"].shift(1).fillna(False)
            previous_narrow_range = htf["NarrowRange"].shift(1).fillna(False)
            spring_low = spring_volume = None
            state = "IDLE"
            spring_age = confirm_age = 0
            previous_timestamp = None
            ready = []
            tests = []
            lps_values = []
            sos_values = []
            utad_values = []
            short_tests = []
            lpsy_values = []
            sow_values = []
            sequence_tests = []
            sequence_sows = []
            sequence_lpsys = []
            utad_high = utad_volume = None
            short_state = "IDLE"
            utad_age = short_confirm_age = 0
            # New, stricter Short research sequence.  Keep it independent of
            # the legacy Short fields so prior experiments remain reproducible.
            sequence_state = "IDLE"
            sequence_utad_high = sequence_utad_volume = sequence_sow_high = None
            sequence_age = sequence_confirm_age = 0
            narrow_state = "IDLE"
            breakdown_high = breakdown_volume = None
            breakdown_age = 0
            breakdown_state = "IDLE"
            any_breakdown_high = any_breakdown_volume = None
            any_breakdown_age = 0
            narrow_sows = []
            narrow_tests = []
            breakdown_sows = []
            breakdown_tests = []
            for timestamp, row in htf.iterrows():
                # A Spring/Test sequence is intraday context.  Never carry it
                # through the overnight or lunch/session gap into a new market
                # auction; doing so created false LPS/SOS entries at the open.
                if previous_timestamp is not None and timestamp - previous_timestamp > pd.Timedelta(minutes=minutes * 2):
                    state = "IDLE"
                    spring_low = spring_volume = None
                    spring_age = confirm_age = 0
                    short_state = "IDLE"
                    utad_high = utad_volume = None
                    utad_age = short_confirm_age = 0
                    sequence_state = "IDLE"
                    sequence_utad_high = sequence_utad_volume = sequence_sow_high = None
                    sequence_age = sequence_confirm_age = 0
                    narrow_state = "IDLE"
                    breakdown_high = breakdown_volume = None
                    breakdown_age = 0
                    breakdown_state = "IDLE"
                    any_breakdown_high = any_breakdown_volume = None
                    any_breakdown_age = 0
                test = lps = sos = False
                utad = short_test = lpsy = sow = False
                sequence_test = sequence_sow = sequence_lpsy = False
                narrow_sow = narrow_test = False
                breakdown_sow = breakdown_test = False
                atr = row["ATR14"]
                if bool(row["Spring"]):
                    spring_low, spring_volume = row["Low"], row["Volume"]
                    state = "WAIT_TEST"
                    spring_age = 0
                    confirm_age = 0
                elif state == "WAIT_TEST":
                    spring_age += 1
                    # A Test is meaningful only shortly after its Spring.  The
                    # old implementation kept this state forever.
                    if 2 <= spring_age <= 6 and pd.notna(atr):
                        test = (
                            row["Low"] >= spring_low
                            and row["Low"] <= spring_low + max(row["RangeWidth"] * 0.35, atr * 0.50)
                            and row["Volume"] <= spring_volume * 0.80
                            and row["Close"] >= (row["High"] + row["Low"]) / 2
                        )
                    if test:
                        state = "WAIT_CONFIRM"
                        confirm_age = 0
                    elif spring_age > 6:
                        state = "IDLE"
                        spring_low = spring_volume = None
                elif state == "WAIT_CONFIRM":
                    confirm_age += 1
                    if pd.notna(atr):
                        close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                        lps = (
                            2 <= confirm_age <= 6
                            and row["Low"] >= spring_low + atr * 0.10
                            and row["Low"] <= row["EMA10"]
                            and row["Volume"] <= row["VolumeMA20"]
                            and close_location >= 0.55
                        )
                        sos = (
                            confirm_age <= 12
                            and row["Close"] > row["RangeHigh"] + atr * 0.10
                            and close_location >= 0.65
                            and (row["High"] - row["Low"]) >= atr * 0.80
                            and row["Volume"] >= row["VolumeMA20"] * 1.20
                        )
                    if lps or sos or confirm_age > 12:
                        state = "IDLE"
                        spring_low = spring_volume = None
                tests.append(int(test))
                lps_values.append(int(lps))
                sos_values.append(int(sos))
                ready.append(int(lps or sos))

                # Distribution -> UTAD -> Test -> LPSY/SOW.  As with the
                # Long state machine, every stage has a short expiry so a
                # historic UTAD cannot trigger a Short days later.
                # `Distribution` needs to be established before the UTAD
                # candle, not merely true after its close.
                prior_distribution = bool(previous_distribution.loc[timestamp])
                if prior_distribution and pd.notna(atr):
                    close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                    utad = (
                        row["High"] > row["RangeHigh"]
                        and row["Close"] < row["RangeHigh"]
                        and close_location <= 0.40
                        and row["Volume"] >= row["VolumeMA20"] * 1.30
                    )
                if utad:
                    utad_high, utad_volume = row["High"], row["Volume"]
                    short_state = "WAIT_TEST"
                    utad_age = short_confirm_age = 0
                elif short_state == "WAIT_TEST":
                    utad_age += 1
                    if 2 <= utad_age <= 6 and pd.notna(atr):
                        short_test = (
                            row["High"] <= utad_high + atr * 0.10
                            and row["High"] >= utad_high - max(row["RangeWidth"] * 0.35, 0)
                            and row["Volume"] <= utad_volume * 0.75
                            and row["Close"] <= (row["High"] + row["Low"]) / 2
                        )
                    if short_test:
                        short_state = "WAIT_CONFIRM"
                        short_confirm_age = 0
                    elif utad_age > 6:
                        short_state = "IDLE"
                        utad_high = utad_volume = None
                elif short_state == "WAIT_CONFIRM":
                    short_confirm_age += 1
                    if pd.notna(atr):
                        close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                        lpsy = (
                            2 <= short_confirm_age <= 6
                            and row["High"] <= utad_high - atr * 0.10
                            and row["High"] >= row["EMA10"]
                            and row["Volume"] <= row["VolumeMA20"]
                            and close_location <= 0.45
                        )
                        sow = (
                            short_confirm_age <= 12
                            and row["Close"] < row["RangeLow"] - atr * 0.10
                            and close_location <= 0.35
                            and (row["High"] - row["Low"]) >= atr * 0.80
                            and row["Volume"] >= row["VolumeMA20"] * 1.20
                        )
                    if lpsy or sow or short_confirm_age > 12:
                        short_state = "IDLE"
                        utad_high = utad_volume = None
                utad_values.append(int(utad))
                short_tests.append(int(short_test))
                lpsy_values.append(int(lpsy))
                sow_values.append(int(sow))

                # UT/UTAD -> failed Test -> SOW -> LPSY.  SOW is mandatory
                # before LPSY here; the legacy state machine allowed LPSY or
                # SOW as alternative confirmation paths.
                if utad:
                    sequence_utad_high, sequence_utad_volume = row["High"], row["Volume"]
                    sequence_state = "WAIT_TEST"
                    sequence_age = sequence_confirm_age = 0
                elif sequence_state == "WAIT_TEST":
                    sequence_age += 1
                    if 2 <= sequence_age <= 6 and pd.notna(atr):
                        sequence_test = (
                            row["High"] <= sequence_utad_high + atr * 0.10
                            and row["High"] >= sequence_utad_high - max(row["RangeWidth"] * 0.35, 0)
                            and row["Volume"] <= sequence_utad_volume * 0.75
                            and row["Close"] <= (row["High"] + row["Low"]) / 2
                        )
                    if sequence_test:
                        sequence_state = "WAIT_SOW"
                        sequence_confirm_age = 0
                    elif sequence_age > 6:
                        sequence_state = "IDLE"
                        sequence_utad_high = sequence_utad_volume = None
                elif sequence_state == "WAIT_SOW":
                    sequence_confirm_age += 1
                    if pd.notna(atr):
                        close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                        sequence_sow = (
                            2 <= sequence_confirm_age <= 12
                            and row["Close"] < row["RangeLow"] - atr * 0.10
                            and close_location <= 0.35
                            and (row["High"] - row["Low"]) >= atr * 0.80
                            and row["Volume"] >= row["VolumeMA20"] * 1.20
                        )
                    if sequence_sow:
                        sequence_sow_high = row["High"]
                        sequence_state = "WAIT_LPSY"
                        sequence_confirm_age = 0
                    elif sequence_confirm_age > 12:
                        sequence_state = "IDLE"
                        sequence_utad_high = sequence_utad_volume = None
                elif sequence_state == "WAIT_LPSY":
                    sequence_confirm_age += 1
                    if pd.notna(atr):
                        close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                        sequence_lpsy = (
                            2 <= sequence_confirm_age <= 6
                            # Lower-high retest after SOW, below the short MA
                            # structure and on reduced supply-test volume.
                            and row["High"] <= sequence_sow_high
                            and row["High"] >= row["RangeLow"] - row["RangeWidth"] * 0.35
                            and row["Close"] < row["EMA10"]
                            and row["Volume"] <= row["VolumeMA20"]
                            and close_location <= 0.45
                        )
                    if sequence_lpsy or sequence_confirm_age > 6:
                        sequence_state = "IDLE"
                        sequence_utad_high = sequence_utad_volume = sequence_sow_high = None
                sequence_tests.append(int(sequence_test))
                sequence_sows.append(int(sequence_sow))
                sequence_lpsys.append(int(sequence_lpsy))

                # Narrow range -> high-volume breakdown (SOW) -> low-volume,
                # weak-closing test.  The entry event is the completed Test.
                if bool(previous_narrow_range.loc[timestamp]) and pd.notna(atr):
                    close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                    narrow_sow = (
                        row["Close"] < row["RangeLow"] - atr * 0.10
                        and close_location <= 0.35
                        and (row["High"] - row["Low"]) >= atr * 0.80
                        and row["Volume"] >= row["VolumeMA20"] * 1.30
                    )
                if narrow_sow:
                    breakdown_high, breakdown_volume = row["High"], row["Volume"]
                    narrow_state, breakdown_age = "WAIT_WEAK_TEST", 0
                elif narrow_state == "WAIT_WEAK_TEST":
                    breakdown_age += 1
                    if 2 <= breakdown_age <= 6 and pd.notna(atr):
                        narrow_test = (
                            row["High"] <= breakdown_high + atr * 0.10
                            and row["High"] >= row["RangeLow"] - row["RangeWidth"] * 0.35
                            and row["Close"] < row["RangeLow"]
                            and row["Close"] <= (row["High"] + row["Low"]) / 2
                            and row["Volume"] <= breakdown_volume * 0.75
                        )
                    if narrow_test or breakdown_age > 6:
                        narrow_state = "IDLE"
                        breakdown_high = breakdown_volume = None
                narrow_sows.append(int(narrow_sow))
                narrow_tests.append(int(narrow_test))

                # Same breakdown/Test definition without the narrow-range
                # prerequisite.  It lets the audit isolate the contribution
                # of the range-compression filter from the VSA sequence.
                if pd.notna(atr):
                    close_location = (row["Close"] - row["Low"]) / max(row["High"] - row["Low"], 1e-9)
                    breakdown_sow = (
                        row["Close"] < row["RangeLow"] - atr * 0.10
                        and close_location <= 0.35
                        and (row["High"] - row["Low"]) >= atr * 0.80
                        and row["Volume"] >= row["VolumeMA20"] * 1.30
                    )
                if breakdown_sow:
                    any_breakdown_high, any_breakdown_volume = row["High"], row["Volume"]
                    breakdown_state, any_breakdown_age = "WAIT_WEAK_TEST", 0
                elif breakdown_state == "WAIT_WEAK_TEST":
                    any_breakdown_age += 1
                    if 2 <= any_breakdown_age <= 6 and pd.notna(atr):
                        breakdown_test = (
                            row["High"] <= any_breakdown_high + atr * 0.10
                            and row["High"] >= row["RangeLow"] - row["RangeWidth"] * 0.35
                            and row["Close"] < row["RangeLow"]
                            and row["Close"] <= (row["High"] + row["Low"]) / 2
                            and row["Volume"] <= any_breakdown_volume * 0.75
                        )
                    if breakdown_test or any_breakdown_age > 6:
                        breakdown_state = "IDLE"
                        any_breakdown_high = any_breakdown_volume = None
                breakdown_sows.append(int(breakdown_sow))
                breakdown_tests.append(int(breakdown_test))
                previous_timestamp = timestamp
            htf["Test"] = tests
            htf["LPS"] = lps_values
            htf["SOS"] = sos_values
            htf["Ready"] = ready
            htf["UTAD"] = utad_values
            htf["ShortTest"] = short_tests
            htf["LPSY"] = lpsy_values
            htf["SOW"] = sow_values
            htf["SequenceTest"] = sequence_tests
            htf["SequenceSOW"] = sequence_sows
            htf["SequenceLPSY"] = sequence_lpsys
            htf["NarrowRangeSOW"] = narrow_sows
            htf["NarrowRangeWeakTest"] = narrow_tests
            htf["BreakdownSOW"] = breakdown_sows
            htf["BreakdownWeakTest"] = breakdown_tests
            completed = htf[[
                "Accumulation", "DemandZone", "NarrowRange", "Spring", "Test", "LPS", "SOS", "Ready", "TrendOK",
                "Distribution", "SupplyZone", "UTAD", "ShortTest", "LPSY", "SOW", "SequenceTest", "SequenceSOW", "SequenceLPSY", "NarrowRangeSOW", "NarrowRangeWeakTest", "BreakdownSOW", "BreakdownWeakTest", "TrendDownOK", "TrendTransitionDown",
            ]].shift(1).fillna(0).astype(int)
            for column in completed.columns:
                df[f"HTF_{minutes}m_{column}"] = pd.Series(bucket, index=df.index).map(completed[column]).fillna(0).astype(int)
            completed_atr = htf["ATR14"].shift(1).bfill()
            df[f"HTF_{minutes}m_ATR"] = pd.Series(bucket, index=df.index).map(completed_atr).fillna(df["ATR"]).astype(float)
            completed_range_high = htf["RangeHigh"].shift(1).bfill()
            df[f"HTF_{minutes}m_RangeHigh"] = pd.Series(bucket, index=df.index).map(completed_range_high).fillna(df["High"]).astype(float)
        return df

from .loader_csv import load_raw_csv
from ..logging_config import logger
from pathlib import Path
from uuid import uuid4


def main():
    """
    Generate master feature dataset (VN30F1M_features.parquet).
    """

    logger.info("Loading raw CSV data for indicator generation.")

    raw_df = load_raw_csv()

    logger.info("Calculating technical indicators.")

    features_df = IndicatorEngine.calculate_all(raw_df)

    logger.info("Calculating strategy scores.")

    features_df = TrendStrategy().calculate_scores(features_df)
    features_df = TrendStrategy().generate_scored_wyckoff_signals(features_df)


    output_path = (
        Path(__file__).resolve().parents[2]
        / "trading_engine"
        / "data"
        / "VN30F1M_features.parquet"
    )

    # `load_raw_csv` uses datetime as the index; persist it as a regular column
    # because downstream consumers use it as the feature-file timestamp.
    features_df = features_df.reset_index()

    # Write to a sibling temporary file first.  This prevents a failed write
    # from corrupting the previous feature artifact and avoids writing directly
    # to a parquet file that another Windows process may still be reading.
    temp_path = output_path.with_name(
        f".{output_path.stem}.{uuid4().hex}.tmp{output_path.suffix}"
    )
    try:
        features_df.to_parquet(temp_path, index=False)
        temp_path.replace(output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    logger.info(
        "Features parquet written to %s",
        output_path,
    )


    

if __name__ == "__main__":
    main()
