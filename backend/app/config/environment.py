"""Local environment loading façade and typed runtime settings."""

from __future__ import annotations

import os
from pathlib import Path

from ..local_config import *  # noqa: F401,F403
from ..local_config import PROJECT_ROOT


DEFAULT_PROJECT_MASTER_DB_PATH = PROJECT_ROOT / ".local-data" / "project-master.db"
DEFAULT_PROJECT_MASTER_SQLITE_BUSY_TIMEOUT_MS = 5000
DEFAULT_PROJECT_MASTER_IMPORT_MAX_BYTES = 25 * 1024 * 1024


def project_master_db_path() -> Path:
    raw = os.getenv("PROJECT_MASTER_DB_PATH", "").strip()
    if not raw:
        return DEFAULT_PROJECT_MASTER_DB_PATH
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def project_master_sqlite_busy_timeout_ms() -> int:
    raw = os.getenv("PROJECT_MASTER_SQLITE_BUSY_TIMEOUT_MS", "").strip()
    try:
        return max(100, int(raw)) if raw else DEFAULT_PROJECT_MASTER_SQLITE_BUSY_TIMEOUT_MS
    except ValueError:
        return DEFAULT_PROJECT_MASTER_SQLITE_BUSY_TIMEOUT_MS


def project_master_import_max_bytes() -> int:
    raw = os.getenv("PROJECT_MASTER_IMPORT_MAX_BYTES", "").strip()
    try:
        return max(1024, int(raw)) if raw else DEFAULT_PROJECT_MASTER_IMPORT_MAX_BYTES
    except ValueError:
        return DEFAULT_PROJECT_MASTER_IMPORT_MAX_BYTES
