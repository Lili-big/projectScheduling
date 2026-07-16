from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.project_master.repository import ProjectMasterRepository  # noqa: E402
from app.project_master.service import ProjectMasterService  # noqa: E402
from project_master_fixture_helpers import large_project_master_workbook  # noqa: E402


@pytest.mark.skipif(os.getenv("RUN_PROJECT_MASTER_PERFORMANCE") != "1", reason="set RUN_PROJECT_MASTER_PERFORMANCE=1")
def test_500_workpoints_10000_structures_50000_components_import_within_30_seconds(tmp_path: Path) -> None:
    content = large_project_master_workbook()
    service = ProjectMasterService(ProjectMasterRepository(tmp_path / "master.db"), import_max_bytes=100 * 1024 * 1024)
    started = time.perf_counter()
    batch = service.import_workbook(
        project_id="performance",
        file_name="large.xlsx",
        content=content,
        created_by="benchmark",
        expected_current_version_id=None,
    )
    elapsed = time.perf_counter() - started
    assert batch.status == "ready"
    assert batch.counts.workpoints == 500
    assert batch.counts.structures == 10_000
    assert batch.counts.components == 50_000
    assert elapsed < 30
    page = service.repository.list_workpoints(batch.created_version_id or "", page=1, page_size=50)
    assert page.total == 500 and len(page.items) == 50
