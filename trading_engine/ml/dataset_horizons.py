"""Create comparable labelled datasets for multiple holding horizons."""

from pathlib import Path

from ..logging_config import logger
from .dataset import DATASET_PATH, build_ml_dataset

HORIZONS = (20, 50, 100)


def build_all_horizons() -> None:
    for horizon in HORIZONS:
        output = DATASET_PATH.with_name(f"ml_dataset_h{horizon}.csv")
        dataset = build_ml_dataset(output_path=output, horizon_bars=horizon)
        logger.info("Horizon %d dataset complete | rows=%d | path=%s", horizon, len(dataset), output)


def main() -> None:
    build_all_horizons()


if __name__ == "__main__":
    main()
