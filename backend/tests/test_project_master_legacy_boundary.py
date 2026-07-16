from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_new_project_master_runtime_does_not_read_legacy_json_or_importers() -> None:
    files = [
        ROOT / "backend/app/project_master/repository.py",
        ROOT / "backend/app/project_master/service.py",
        ROOT / "backend/app/project_master/scheduling_adapter.py",
        ROOT / "backend/app/api/routers/project_master.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "project-structure-params.json" not in source
    assert "project_data_versions" not in source
    assert "bridge_import" not in source
    assert "import_workpoints" not in source


def test_sqlite_is_the_only_project_master_business_store() -> None:
    schema = (ROOT / "backend/app/project_master/schema.py").read_text(encoding="utf-8")
    repository = (ROOT / "backend/app/project_master/repository.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS workpoints" in schema
    assert "CREATE TABLE IF NOT EXISTS structures" in schema
    assert "CREATE TABLE IF NOT EXISTS components" in schema
    assert "json.dump(" not in repository and "write_text(" not in repository
