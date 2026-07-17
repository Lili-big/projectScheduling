from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import local_paths  # noqa: E402


def test_repository_root_points_to_lifecycle_workspace() -> None:
    assert (local_paths.REPOSITORY_ROOT / "04-demo/backend/app").is_dir()
    assert local_paths.LOCAL_DATA_ROOT == local_paths.REPOSITORY_ROOT / ".local-data"


def test_state_path_reads_legacy_until_target_exists(tmp_path: Path, monkeypatch) -> None:
    local_data = tmp_path / ".local-data"
    state = local_data / "state"
    local_data.mkdir()
    legacy = local_data / "scheduler-config.json"
    legacy.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(local_paths, "LOCAL_DATA_ROOT", local_data)
    monkeypatch.setattr(local_paths, "STATE_ROOT", state)

    assert local_paths.state_path("scheduler-config.json") == legacy
    state.mkdir()
    target = state / "scheduler-config.json"
    target.write_text("{}", encoding="utf-8")
    assert local_paths.state_path("scheduler-config.json") == target


def test_state_path_defaults_new_files_to_state_partition(tmp_path: Path, monkeypatch) -> None:
    local_data = tmp_path / ".local-data"
    state = local_data / "state"
    monkeypatch.setattr(local_paths, "LOCAL_DATA_ROOT", local_data)
    monkeypatch.setattr(local_paths, "STATE_ROOT", state)
    assert local_paths.state_path("project-master.db") == state / "project-master.db"
