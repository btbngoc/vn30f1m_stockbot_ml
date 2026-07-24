"""VCI (Vietcap) market-data helpers for the VN30F1M backtest."""

import time
import pandas as pd
import requests


VCI_BASE = "https://trading.vietcap.com.vn/api"
VCI_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://trading.vietcap.com.vn/",
    "Origin": "https://trading.vietcap.com.vn",
    "Content-Type": "application/json",
}
_OHLC_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
# VCI's one-shot endpoint is reliable with this request size; a larger request
# (such as 1,000 calendar days × 1,440 minutes) can take several minutes.
MAX_VCI_COUNT_BACK = 500_000


def _convert_vci_time(values) -> pd.Series:
    """Convert VCI epoch timestamps to timezone-naive Vietnam local times."""
    timestamps = pd.to_numeric(pd.Series(values), errors="coerce")
    valid = timestamps.dropna()
    if valid.empty:
        return pd.Series(pd.NaT, index=timestamps.index, dtype="datetime64[ns]")

    unit = "ms" if valid.max() > 1e12 else "s"
    converted = pd.to_datetime(timestamps, unit=unit, utc=True, errors="coerce")
    return converted.dt.tz_convert("Asia/Ho_Chi_Minh").dt.tz_localize(None)


def fetch_vci_1m_one_shot(
    symbol: str,
    count_back: int = 500_000,
    timeout: int = 60,
    to_epoch: int | None = None,
) -> pd.DataFrame:
    """Fetch one batch of one-minute OHLCV candles from VCI's chart endpoint."""
    if count_back <= 0:
        raise ValueError("count_back must be positive")

    response = requests.post(
        f"{VCI_BASE}/chart/OHLCChart/gap-chart",
        json={
            "timeFrame": "ONE_MINUTE",
            "symbols": [symbol.upper()],
            "to": int(to_epoch if to_epoch is not None else time.time()),
            "countBack": int(count_back),
        },
        headers=VCI_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, list) or not payload:
        return pd.DataFrame(columns=_OHLC_COLUMNS)

    item = payload[0]
    required = ("t", "o", "h", "l", "c", "v")
    if not isinstance(item, dict) or not all(key in item for key in required):
        return pd.DataFrame(columns=_OHLC_COLUMNS)
    if not all(hasattr(item[key], "__len__") for key in required):
        return pd.DataFrame(columns=_OHLC_COLUMNS)
    if len({len(item[key]) for key in required}) != 1:
        return pd.DataFrame(columns=_OHLC_COLUMNS)

    data = pd.DataFrame(
        {
            "time": _convert_vci_time(item["t"]),
            "open": pd.to_numeric(item["o"], errors="coerce"),
            "high": pd.to_numeric(item["h"], errors="coerce"),
            "low": pd.to_numeric(item["l"], errors="coerce"),
            "close": pd.to_numeric(item["c"], errors="coerce"),
            "volume": pd.to_numeric(item["v"], errors="coerce"),
        }
    )
    return (
        data.dropna(subset=["time"])
        .sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .reset_index(drop=True)
    )


def fetch_vci_1m_history(
    symbol: str,
    days: int,
    chunk_size: int = MAX_VCI_COUNT_BACK,
    timeout: int = 60,
) -> pd.DataFrame:
    """Fetch up to ``days`` calendar days of minute candles in VCI-sized batches.

    VCI's one-shot endpoint becomes unreliable for very large ``countBack``
    values.  Each request therefore retrieves at most ``chunk_size`` bars, and
    the next request ends one second before the oldest bar already received.
    """
    if days <= 0:
        raise ValueError("days must be positive")
    if not 0 < chunk_size <= MAX_VCI_COUNT_BACK:
        raise ValueError(f"chunk_size must be between 1 and {MAX_VCI_COUNT_BACK}")

    end_time = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    start_time = (end_time - pd.Timedelta(days=days)).normalize()
    # VN30F1M has roughly 4.5--5 trading hours per session.  This is a small
    # first request for short periods, while long periods use full batches.
    request_size = min(chunk_size, max(1, days * 300))
    to_epoch = int(time.time())
    batches: list[pd.DataFrame] = []
    previous_oldest = None

    while True:
        batch = fetch_vci_1m_one_shot(
            symbol=symbol,
            count_back=request_size,
            timeout=timeout,
            to_epoch=to_epoch,
        )
        if batch.empty:
            break

        batches.append(batch)
        oldest = batch["time"].min()
        if oldest <= start_time:
            break
        if previous_oldest is not None and oldest >= previous_oldest:
            # Avoid an infinite loop if VCI ignores an old ``to`` value.
            break
        if len(batch) < request_size:
            # A short batch means VCI has no older candles available.
            break

        previous_oldest = oldest
        to_epoch = int(pd.Timestamp(oldest).tz_localize("Asia/Ho_Chi_Minh").timestamp()) - 1

    if not batches:
        return pd.DataFrame(columns=_OHLC_COLUMNS)

    history = pd.concat(batches, ignore_index=True)
    history = (
        history.sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .reset_index(drop=True)
    )
    return history[history["time"] >= start_time].reset_index(drop=True)


def resample_to_daily(df_1m: pd.DataFrame) -> pd.DataFrame:
    """Aggregate minute candles into daily OHLCV candles for the backtest."""
    if df_1m.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    minute_data = df_1m.copy()
    minute_data["time"] = pd.to_datetime(minute_data["time"], errors="coerce")
    minute_data = minute_data.dropna(subset=["time"]).set_index("time").sort_index()
    if minute_data.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    daily = minute_data.resample("1D").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["open"])
    print(f"Daily rows: {len(daily)}")
    print(daily.head())
    print(daily.tail())
    daily.index.name = "Date"
    return daily.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    )


def fetch_vn30f1m_daily(days: int = 1000) -> pd.DataFrame:
    """Fetch VN30F1M minute history and return daily OHLCV candles."""
    if days <= 0:
        raise ValueError("days must be positive")

    print("=" * 60)
    print(f"Request days: {days}")

    try:
        minute_data = fetch_vci_1m_history("VN30F1M", days=days)

        print(f"Minute rows : {len(minute_data)}")

        if not minute_data.empty:
            print(f"Minute from : {minute_data['time'].min()}")
            print(f"Minute to   : {minute_data['time'].max()}")

        daily = resample_to_daily(minute_data)

        print(f"Daily rows  : {len(daily)}")

        if not daily.empty:
            print(f"Daily from  : {daily.index.min()}")
            print(f"Daily to    : {daily.index.max()}")

        print("=" * 60)

        return daily

    except Exception as exc:
        print(f"Could not download VN30F1M data from VCI: {exc}")
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])