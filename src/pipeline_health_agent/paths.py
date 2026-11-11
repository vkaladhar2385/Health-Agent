"""Shared filesystem locations for this project."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / ".pha"
CHECKPOINT_DB = DATA_DIR / "checkpoints.sqlite"
INCIDENTS_DB = DATA_DIR / "incidents.sqlite"


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
