"""Helpers for keeping artifacts from one pipeline execution together."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
LATEST_RUN_PATH = PROJECT_ROOT / "trading_engine" / "data" / "latest_run.json"
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def generate_run_id(now: datetime | None = None) -> str:
    """Return a sortable run id compatible with the existing results folders."""
    return (now or datetime.now()).strftime("%Y_%m_%d_%H%M%S")


def validate_run_id(run_id: str) -> str:
    """Reject path-like run ids before using them as directory names."""
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(
            "run_id may only contain letters, numbers, dot, underscore, and hyphen"
        )
    return run_id


def get_run_dir(run_id: str, *, create: bool = False) -> Path:
    path = RESULTS_DIR / validate_run_id(run_id)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def read_latest_run_id() -> str | None:
    if not LATEST_RUN_PATH.exists():
        return None
    try:
        payload = json.loads(LATEST_RUN_PATH.read_text(encoding="utf-8"))
        return validate_run_id(str(payload["run_id"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def write_latest_run_id(run_id: str) -> None:
    run_id = validate_run_id(run_id)
    LATEST_RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_RUN_PATH.write_text(
        json.dumps({"run_id": run_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
