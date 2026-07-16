from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.project_master import ConfirmProjectMasterVersionRequest  # noqa: E402
from app.project_master.repository import ProjectMasterRepository  # noqa: E402
from app.project_master.scheduling_adapter import project_model_from_master  # noqa: E402
from app.project_master.service import ProjectMasterService  # noqa: E402
from project_master_fixture_helpers import valid_project_master_workbook  # noqa: E402


BASELINE = Path(__file__).parent / "fixtures" / "project_master" / "bridge-projection-baseline.json"


def _confirmed(tmp_path: Path):
    repository = ProjectMasterRepository(tmp_path / "master.db")
    service = ProjectMasterService(repository)
    batch = service.import_workbook(
        project_id="demo",
        file_name="master.xlsx",
        content=valid_project_master_workbook(),
        created_by="tester",
        expected_current_version_id=None,
    )
    assert batch.created_version_id
    service.confirm_version(
        batch.created_version_id,
        ConfirmProjectMasterVersionRequest(confirmed_by="reviewer"),
    )
    version = repository.get_version_summary(batch.created_version_id)
    return repository, version


def test_confirmed_master_projects_to_existing_bridge_model(tmp_path: Path) -> None:
    repository, version = _confirmed(tmp_path)
    project, diagnostics = project_model_from_master(
        version=version,
        snapshot=repository.load_snapshot(version.version_id),
        project_name="测试项目",
        start_date=__import__("datetime").date(2026, 1, 1),
    )
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert [item.id for item in project.bridges] == expected["bridge_ids"]
    sections = project.bridges[0].work_sections
    assert sorted(item.id for item in sections) == expected["section_ids"]
    assert sorted(item.id for section in sections for item in section.structures) == expected["lower_structure_ids"]
    assert sorted(item.id for section in sections for item in section.upper_structures) == expected["upper_structure_ids"]
    assert sorted(
        item.id for section in sections for structure in section.structures for item in structure.components
    ) == expected["scheduled_component_ids"]
    assert sum(item.code == "PROJECT_MASTER_WORKPOINT_NOT_SCHEDULED" for item in diagnostics) == expected[
        "non_bridge_diagnostic_count"
    ]
    left = next(item for item in sections if item.side == "left")
    assert left.upper_structures[0].beam_count_per_span == 10
    assert left.upper_structures[0].support_range == "ST-S-A0~ST-L-P1"


def test_draft_version_cannot_be_projected(tmp_path: Path) -> None:
    repository = ProjectMasterRepository(tmp_path / "master.db")
    service = ProjectMasterService(repository)
    batch = service.import_workbook(
        project_id="demo",
        file_name="master.xlsx",
        content=valid_project_master_workbook(),
        created_by="tester",
        expected_current_version_id=None,
    )
    version = repository.get_version_summary(batch.created_version_id or "")
    import pytest

    with pytest.raises(ValueError, match="已确认"):
        project_model_from_master(
            version=version,
            snapshot=repository.load_snapshot(version.version_id),
            project_name="测试项目",
            start_date=__import__("datetime").date(2026, 1, 1),
        )
