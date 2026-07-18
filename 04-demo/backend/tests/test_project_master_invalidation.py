from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.bootstrap import create_app  # noqa: E402
from app.contracts import IntegratedCalculationSnapshot  # noqa: E402
from app.contracts.project_master import ConfirmProjectMasterVersionRequest  # noqa: E402
from app.project_master.repository import ProjectMasterRepository  # noqa: E402
from app.project_master.scheduling_adapter import SCHEDULING_PROJECTION_VERSION  # noqa: E402
from app.project_master.service import ProjectMasterService  # noqa: E402
from app.services.process_library_service import default_scenario_with_process_library  # noqa: E402
from app.services.plan_control_repository import PlanControlRepository  # noqa: E402
from app.services.progress_forecast import create_baseline_plan  # noqa: E402
from asgi_client import request  # noqa: E402
from plan_control_helpers import solved_baseline_request  # noqa: E402
from project_master_fixture_helpers import valid_project_master_workbook  # noqa: E402


def _integrated_snapshot(
    *,
    snapshot_id: str,
    project_data_version_id: str,
    projection_version: str | None,
) -> IntegratedCalculationSnapshot:
    request_payload = solved_baseline_request()
    generated = request_payload.plan_result.generated
    result = request_payload.plan_result.result
    assert generated is not None
    assert result is not None
    source_summary = {
        **generated.source_summary,
        "project_data_version_id": project_data_version_id,
    }
    if projection_version is not None:
        source_summary["scheduling_projection_version"] = projection_version
    return IntegratedCalculationSnapshot(
        integrated_snapshot_id=snapshot_id,
        project_data_version_id=project_data_version_id,
        scenario_version_id=f"scenario-{snapshot_id}",
        status="converged",
        generated_snapshot=generated.model_copy(update={"source_summary": source_summary}),
        schedule_result=result.model_copy(deep=True),
        input_fingerprint=f"fingerprint-{snapshot_id}",
        created_at=datetime.now(timezone.utc),
    )


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


def test_current_project_master_projection_snapshot_can_be_reused(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "plan-control-current.json")
    snapshot = _integrated_snapshot(
        snapshot_id="current",
        project_data_version_id="pmv-current",
        projection_version=SCHEDULING_PROJECTION_VERSION,
    )

    repository.add_integrated_snapshot(snapshot)

    reused = repository.find_integrated_snapshot_by_fingerprint(snapshot.input_fingerprint)
    assert reused is not None
    assert reused.integrated_snapshot_id == snapshot.integrated_snapshot_id
    assert reused.status == "converged"


@pytest.mark.parametrize("projection_version", [None, "project-master-scheduling/legacy"])
def test_old_project_master_projection_snapshot_is_persisted_stale_and_not_reused(
    tmp_path: Path,
    projection_version: str | None,
) -> None:
    repository = PlanControlRepository(tmp_path / f"plan-control-{projection_version or 'missing'}.json")
    snapshot = _integrated_snapshot(
        snapshot_id=projection_version or "missing",
        project_data_version_id="pmv-historical",
        projection_version=projection_version,
    )

    repository.add_integrated_snapshot(snapshot)

    assert repository.find_integrated_snapshot_by_fingerprint(snapshot.input_fingerprint) is None
    persisted = next(
        item
        for item in repository.load().integrated_calculation_snapshots
        if item.integrated_snapshot_id == snapshot.integrated_snapshot_id
    )
    assert persisted.status == "stale"
    assert persisted.generated_snapshot is not None


def test_non_project_master_snapshot_without_projection_version_remains_compatible(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "plan-control-legacy.json")
    snapshot = _integrated_snapshot(
        snapshot_id="legacy",
        project_data_version_id="legacy-project-data",
        projection_version=None,
    )

    repository.add_integrated_snapshot(snapshot)

    reused = repository.find_integrated_snapshot_by_fingerprint(snapshot.input_fingerprint)
    assert reused is not None
    assert reused.status == "converged"


def test_loading_existing_old_project_master_snapshot_persists_stale_status(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "plan-control-existing-old.json")
    snapshot = _integrated_snapshot(
        snapshot_id="existing-old",
        project_data_version_id="pmv-existing-old",
        projection_version=None,
    )
    repository.add_integrated_snapshot(snapshot)
    payload = json.loads(repository.path.read_text(encoding="utf-8"))
    payload["integrated_calculation_snapshots"][0]["status"] = "converged"
    repository.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = repository.load()

    assert loaded.integrated_calculation_snapshots[0].status == "stale"
    persisted = json.loads(repository.path.read_text(encoding="utf-8"))
    assert persisted["integrated_calculation_snapshots"][0]["status"] == "stale"


def test_project_master_plan_version_without_current_projection_is_stale_on_write(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "plan-control-plan-version.json")
    request_payload = solved_baseline_request()
    request_payload = request_payload.model_copy(
        update={
            "scenario": request_payload.scenario.model_copy(
                update={"project_data_version_id": "pmv-plan-historical"}
            )
        }
    )

    plan = create_baseline_plan(request_payload, repository)

    assert plan.status == "stale"
    assert repository.get_plan_version(plan.plan_version_id).status == "stale"
