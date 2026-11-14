"""Canonical project and data paths."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_ROOT / "raw"
RAW_REQUEST_STATE_PATH = RAW_DATA_DIR / "request_state.json"
NORMALIZED_DATA_DIR = DATA_ROOT / "normalized"
ANALYTICS_DATA_DIR = DATA_ROOT / "analytics"
