from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.api.routers import scheduling as scheduling_router  # noqa: E402
from app.bootstrap import create_app  # noqa: E402
from app.contracts.project_master import ConfirmProjectMasterVersionRequest  # noqa: E402
from app.main import app  # noqa: E402
from app.project_master.repository import ProjectMasterRepository  # noqa: E402
from app.project_master.scheduling_adapter import SCHEDULING_PROJECTION_VERSION  # noqa: E402
from app.project_master.service import ProjectMasterService  # noqa: E402
from app.services.process_library_service import default_scenario_with_process_library  # noqa: E402
from asgi_client import json_request  # noqa: E402
from project_master_fixture_helpers import valid_project_master_workbook  # noqa: E402


def test_scheduling_router_exposes_demo_and_task_generation() -> None:
    scenario_status, scenario = json_request(app, "GET", "/api/demo-scenario")
    assert scenario_status == 200
    generated_status, generated = json_request(app, "POST", "/api/generate-schedule-input", scenario)
    assert generated_status == 200
    assert generated["schedule_input"]["tasks"]


def test_scheduling_router_keeps_validation_error_shape() -> None:
    status, response = json_request(app, "POST", "/api/solve-min-resources", {})
    assert status == 422
    assert "detail" in response


def test_scheduling_router_keeps_compatibility_endpoints() -> None:
    schema = app.openapi()["paths"]
    assert "post" in schema["/api/generate-wbs"]
    assert "post" in schema["/api/solve"]


def test_project_master_generation_and_solve_reproject_each_entry_with_source_versions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository = ProjectMasterRepository(tmp_path / "master.db")
    service = ProjectMasterService(repository)
    batch = service.import_workbook(
        project_id="demo",
        file_name="historical-master.xlsx",
        content=valid_project_master_workbook(),
        created_by="tester",
        expected_current_version_id=None,
    )
    version_id = batch.created_version_id or ""
    service.confirm_version(version_id, ConfirmProjectMasterVersionRequest(confirmed_by="reviewer"))
    test_app = create_app()
    test_app.state.project_master_service = service
    scenario = default_scenario_with_process_library().model_copy(
        update={"project_data_version_id": version_id, "time_limit_seconds": 2.0}
    )
    projection_calls: list[str] = []
    original_projector = scheduling_router.project_model_from_master

    def project_with_trace(**kwargs):
        projection_calls.append(kwargs["version"].version_id)
        return original_projector(**kwargs)

    monkeypatch.setattr(scheduling_router, "project_model_from_master", project_with_trace)

    generated_status, generated = json_request(
        test_app,
        "POST",
        "/api/generate-schedule-input",
        scenario.model_dump(mode="json"),
    )
    solved_status, solved = json_request(
        test_app,
        "POST",
        "/api/solve-scenario",
        scenario.model_dump(mode="json"),
    )

    assert generated_status == 200
    assert solved_status == 200
    assert projection_calls == [version_id, version_id]
    for source_summary in (generated["source_summary"], solved["generated"]["source_summary"]):
        assert source_summary["project_data_version_id"] == version_id
        assert source_summary["scheduling_projection_version"] == SCHEDULING_PROJECTION_VERSION
