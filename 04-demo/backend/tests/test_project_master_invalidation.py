from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.bootstrap import create_app  # noqa: E402
from app.contracts.project_master import ConfirmProjectMasterVersionRequest  # noqa: E402
from app.project_master.repository import ProjectMasterRepository  # noqa: E402
from app.project_master.service import ProjectMasterService  # noqa: E402
from app.services.process_library_service import default_scenario_with_process_library  # noqa: E402
from app.services.plan_control_repository import PlanControlRepository  # noqa: E402
from app.services.progress_forecast import create_baseline_plan  # noqa: E402
from asgi_client import request  # noqa: E402
from plan_control_helpers import solved_baseline_request  # noqa: E402
from project_master_fixture_helpers import valid_project_master_workbook  # noqa: E402


def test_schedule_generation_resolves_confirmed_version_reference(tmp_path: Path) -> None:
    repository = ProjectMasterRepository(tmp_path / "master.db")
    service = ProjectMasterService(repository)
    batch = service.import_workbook(
        project_id="demo",
        file_name="master.xlsx",
        content=valid_project_master_workbook(),
        created_by="tester",
        expected_current_version_id=None,
    )
    version_id = batch.created_version_id or ""
    service.confirm_version(version_id, ConfirmProjectMasterVersionRequest(confirmed_by="reviewer"))
    app = create_app()
    app.state.project_master_service = service
    scenario = default_scenario_with_process_library().model_copy(
        update={"project_data_version_id": version_id}
    )
    status, _, body = request(app, "POST", "/api/generate-schedule-input", scenario.model_dump(mode="json"))
    assert status == 200
    import json

    payload = json.loads(body.decode("utf-8"))
    assert payload["source_summary"]["bridge_count"] == 1
    assert {task["component_id"] for task in payload["schedule_input"]["tasks"]} >= {
        "CP-L-P1-PILE",
        "CP-R-P1-PILE",
    }
    assert sum(item["code"] == "PROJECT_MASTER_WORKPOINT_NOT_SCHEDULED" for item in payload["validation"]) == 2


def test_schedule_generation_rejects_draft_version(tmp_path: Path) -> None:
    repository = ProjectMasterRepository(tmp_path / "master.db")
    service = ProjectMasterService(repository)
    batch = service.import_workbook(
        project_id="demo",
        file_name="master.xlsx",
        content=valid_project_master_workbook(),
        created_by="tester",
        expected_current_version_id=None,
    )
    app = create_app()
    app.state.project_master_service = service
    scenario = default_scenario_with_process_library().model_copy(
        update={"project_data_version_id": batch.created_version_id}
    )
    status, _, body = request(app, "POST", "/api/generate-schedule-input", scenario.model_dump(mode="json"))
    assert status == 409
    assert b"PROJECT_MASTER_VERSION_NOT_CONFIRMED" in body


def test_superseded_master_reference_marks_plan_artifacts_stale(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "plan-control.json")
    plan = create_baseline_plan(solved_baseline_request(), repository)
    store = repository.load()
    store.plan_versions = [
        item.model_copy(update={"project_data_version_id": "pmv-old"})
        if item.plan_version_id == plan.plan_version_id
        else item
        for item in store.plan_versions
    ]
    repository.path.write_text(store.model_dump_json(indent=2), encoding="utf-8")

    repository.invalidate_project_master_reference("pmv-old")

    restored = repository.load()
    assert restored.plan_versions[0].status == "stale"
