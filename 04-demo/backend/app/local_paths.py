"""Repository-local path ownership and migration-compatible state lookup."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LOCAL_DATA_ROOT = REPOSITORY_ROOT / ".local-data"
STATE_ROOT = LOCAL_DATA_ROOT / "state"


def state_path(name: str) -> Path:
    """Prefer the lifecycle state partition while reading a legacy file if present."""

    target = STATE_ROOT / name
    legacy = LOCAL_DATA_ROOT / name
    if target.exists() or not legacy.exists():
        return target
    return legacy
