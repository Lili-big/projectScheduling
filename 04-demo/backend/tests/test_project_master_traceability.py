from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.project_master import ConfirmProjectMasterVersionRequest  # noqa: E402
from app.project_master.repository import ProjectMasterRepository  # noqa: E402
from app.project_master.service import ProjectMasterService  # noqa: E402
from project_master_fixture_helpers import large_project_master_workbook  # noqa: E402


def test_twenty_confirmed_workpoints_trace_to_batch_sheet_and_row(tmp_path: Path) -> None:
    service = ProjectMasterService(ProjectMasterRepository(tmp_path / "master.db"))
    batch = service.import_workbook(
        project_id="traceability",
        file_name="traceability.xlsx",
        content=large_project_master_workbook(workpoint_count=25, structure_count=50, component_count=100),
        created_by="tester",
        expected_current_version_id=None,
    )
    version_id = batch.created_version_id or ""
    service.confirm_version(version_id, ConfirmProjectMasterVersionRequest(confirmed_by="reviewer"))
    page = service.repository.list_workpoints(version_id, page=1, page_size=20)
    assert len(page.items) == 20
    for item in page.items:
        detail = service.repository.get_workpoint(version_id, item.workpoint_id)
        assert detail.source is not None
        assert detail.source.batch_id == batch.batch_id
        assert detail.source.sheet_name == "工点信息"
        assert detail.source.row_no >= 3
        assert detail.structures
        for structure in detail.structures:
            assert structure.source is not None
            assert structure.source.batch_id == batch.batch_id
            assert structure.source.sheet_name == "结构物信息"
            assert structure.source.row_no >= 3
