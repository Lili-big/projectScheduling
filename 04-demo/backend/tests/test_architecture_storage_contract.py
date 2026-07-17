from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.girder_planning.fingerprints import stable_fingerprint, stable_id  # noqa: E402


def test_local_storage_paths_remain_under_the_repository_local_data_directory() -> None:
    local_paths = (BACKEND_ROOT / "app/local_paths.py").read_text(encoding="utf-8")
    assert 'LOCAL_DATA_ROOT = REPOSITORY_ROOT / ".local-data"' in local_paths
    sources = {
        "scheduler-config.json": (BACKEND_ROOT / "app/local_scenario_config.py").read_text(encoding="utf-8"),
        "project-structure-params.json": (BACKEND_ROOT / "app/project_structure_params.py").read_text(encoding="utf-8"),
        "plan-control-store.json": (BACKEND_ROOT / "app/services/plan_control_repository.py").read_text(encoding="utf-8"),
    }
    for filename, source in sources.items():
        assert "state_path" in source
        assert filename in source


def test_bundled_then_local_scenario_merge_order_is_explicit() -> None:
    source = (BACKEND_ROOT / "app/services/process_library_service.py").read_text(encoding="utf-8")
    bundled = source.find("scenario = apply_bundled_scenario_config(scenario)")
    local = source.find("return apply_local_scenario_config(scenario)")
    assert bundled >= 0 and local > bundled


def test_stable_ids_and_fingerprints_are_deterministic() -> None:
    value = {"project": "P-001", "version": 2}
    assert stable_fingerprint(value) == stable_fingerprint(value)
    assert stable_id("project", value) == stable_id("project", value)
    assert stable_id("project", value) != stable_id("scenario", value)
