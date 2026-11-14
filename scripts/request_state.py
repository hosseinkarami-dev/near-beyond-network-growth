"""Persistent request cooldowns independent of raw dataset date coverage."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atomic_io import atomic_write_text
from paths import RAW_REQUEST_STATE_PATH
from sources import Source


DAILY_REQUEST_INTERVAL = timedelta(hours=24)
OTHER_REQUEST_INTERVAL = timedelta(hours=1)


def _read_state(path: Path = RAW_REQUEST_STATE_PATH) -> dict:
    if not path.exists():
        return {"schema_version": "1.0.0", "timezone": "UTC", "sources": {}}
    state = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(state, dict) or not isinstance(state.get("sources", {}), dict):
        raise ValueError(f"Invalid request state file: {path}")
    state.setdefault("sources", {})
    return state


def request_cooldown(source: Source, path: Path = RAW_REQUEST_STATE_PATH) -> timedelta | None:
    """Return remaining cooldown, based only on the last outbound request time."""
    entry = _read_state(path)["sources"].get(source.name.value)
    if not isinstance(entry, dict) or not entry.get("last_request_at"):
        return None
    # Failed fetches must be retried on the next pipeline run; cooldowns protect
    # successful snapshots and interrupted in-flight requests only.
    if entry.get("status") == "failed":
        return None
    requested_at = datetime.fromisoformat(entry["last_request_at"].replace("Z", "+00:00"))
    interval = DAILY_REQUEST_INTERVAL if source.frequency == "daily" else OTHER_REQUEST_INTERVAL
    remaining = interval - (datetime.now(timezone.utc) - requested_at)
    return remaining if remaining.total_seconds() > 0 else None


def request_started(source: Source, path: Path = RAW_REQUEST_STATE_PATH) -> None:
    """Record the time an outbound request actually starts."""
    state = _read_state(path)
    entry = state["sources"].setdefault(source.name.value, {})
    entry["last_request_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry["request_count"] = int(entry.get("request_count", 0)) + 1
    entry["status"] = "in_progress"
    atomic_write_text(path, json.dumps(state, indent=2) + "\n")


def request_finished(source: Source, error: BaseException | None = None,
                     path: Path = RAW_REQUEST_STATE_PATH) -> None:
    """Record request outcome without changing its timestamp."""
    state = _read_state(path)
    entry = state["sources"].setdefault(source.name.value, {})
    entry["status"] = "failed" if error else "succeeded"
    entry["last_error"] = f"{type(error).__name__}: {error}" if error else None
    atomic_write_text(path, json.dumps(state, indent=2) + "\n")


def request_failed_if_needed(source: Source, error: BaseException,
                             path: Path = RAW_REQUEST_STATE_PATH) -> None:
    """Mark an unsuccessful collection failed, including response-parse errors."""
    state = _read_state(path)
    entry = state["sources"].get(source.name.value)
    if isinstance(entry, dict) and entry.get("status") == "failed":
        return
    request_finished(source, error, path)
