import sqlite3
import sys
from pathlib import Path

import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from app.project_master.repository import ProjectMasterRepository
from test_project_master_repository import _draft


def test_v2_upgrade_preserves_master_and_is_repeatable(tmp_path):
    path = tmp_path / "old.db"
    repo = ProjectMasterRepository(path)
    _, version = _draft(repo)
    before = repo.load_snapshot(version.version_id)
    with sqlite3.connect(path) as c:
        c.execute("DROP TABLE IF EXISTS pavement_daily_progress")
        c.execute("DROP TABLE IF EXISTS pavement_progress_revisions")
        c.execute("PRAGMA user_version=2")
    for _ in range(2):
        restored = ProjectMasterRepository(path)
        assert restored.load_snapshot(version.version_id) == before
        with restored.connection() as c:
            assert c.execute("PRAGMA user_version").fetchone()[0] == 3
            assert c.execute("SELECT COUNT(*) FROM pavement_daily_progress").fetchone()[0] == 0
            assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_newer_schema_is_not_downgraded(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as c:
        c.execute("PRAGMA user_version=999")
    with pytest.raises(RuntimeError, match="高于"):
        ProjectMasterRepository(path)
