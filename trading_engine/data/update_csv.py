from pathlib import Path
import pandas as pd

from trading_engine.data.vci_api import fetch_vci_1m_one_shot
from trading_engine.data.loader_csv import load_base_csv, load_raw_csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "data" / "VN30F1M_since20180501.csv"

def load_csv() -> pd.DataFrame:
    """Load the raw CSV data for the pipeline."""
    return load_raw_csv()

SYMBOL = "VN30F1M"

COUNT_BACK = 500000

def save_csv(df):

    out = df.copy()

    out["date"] = out["datetime"].dt.strftime("%d/%m/%Y")
    out["time"] = out["datetime"].dt.strftime("%H:%M:%S")

    out = out[
        [
            "ticker",
            "date",
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    ]

    out.to_csv(CSV_PATH, index=False)


def main():

    print("Loading existing csv...")

    old_df = load_base_csv()

    print(f"Rows : {len(old_df)}")

    last_time = old_df["datetime"].max()

    print(f"Last candle : {last_time}")

    print("Downloading latest data from VCI...")

    new_df = fetch_vci_1m_one_shot(
        SYMBOL,
        count_back=COUNT_BACK,
    )

    if new_df.empty:
        print("VCI returned empty.")
        return

    new_df.rename(columns={"time": "datetime"}, inplace=True)

    # chỉ lấy dữ liệu mới
    new_df = new_df[
        new_df["datetime"] > last_time
    ].copy()

    print(f"New candles : {len(new_df)}")

    if new_df.empty:
        print("CSV already up to date.")
        return

    new_df["ticker"] = SYMBOL

    merged = pd.concat(
        [old_df, new_df],
        ignore_index=True,
    )

    merged = (
        merged
        .sort_values("datetime")
        .drop_duplicates(subset="datetime", keep="last")
        .reset_index(drop=True)
    )

    save_csv(merged)

    print("=" * 60)
    print("Update completed")
    print(f"Old rows : {len(old_df)}")
    print(f"Added    : {len(new_df)}")
    print(f"Total    : {len(merged)}")
    print(f"Last     : {merged['datetime'].max()}")
    print("=" * 60)


if __name__ == "__main__":
    main()