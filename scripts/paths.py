"""Canonical project and data paths."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_ROOT / "raw"
NORMALIZED_DATA_DIR = DATA_ROOT / "normalized"
ANALYTICS_DATA_DIR = DATA_ROOT / "analytics"
