from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.main as main_module  # noqa: E402
from app.main import (  # noqa: E402
    create_baseline_plan_endpoint,
    create_forecast_endpoint,
    create_progress_snapshot_endpoint,
    get_plan_control_project_endpoint,
)
from app.models import (  # noqa: E402
    CreateForecastRequest,
    CreateProgressSnapshotRequest,
    ProgressEntry,
    ResourceAssistantOptimizationStages,
    ResourceAssistantPrimaryStageSummary,
    ResourceAssistantSecondaryStageSummary,
)
from app.services.plan_control_repository import (  # noqa: E402
    PlanControlConflictError,
    default_plan_control_repository,
)
from plan_control_helpers import solved_baseline_request  # noqa: E402


def _drop_structure_parameter_labels(value) -> None:
    if isinstance(value, dict):
        value.pop("structure_parameter_label", None)
        for nested in value.values():
            _drop_structure_parameter_labels(nested)
    elif isinstance(value, list):
        for nested in value:
            _drop_structure_parameter_labels(nested)


def test_plan_control_baseline_and_project_summary_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    request = solved_baseline_request()

    baseline = create_baseline_plan_endpoint(request)
    assert baseline.version_no == 1

    summary = get_plan_control_project_endpoint(request.scenario.scenario_id)
    assert summary.active_plan is not None
    assert summary.active_plan.plan_version_id == baseline.plan_version_id
    planned_task = request.plan_result.generated.schedule_input.tasks[0]
    summary_task = summary.active_plan.generated_snapshot.schedule_input.tasks[0]
    assert summary_task.quantity == planned_task.quantity
    assert summary_task.quantity_label == planned_task.quantity_label
    if summary_task.structure_parameter_label:
        assert summary_task.structure_parameter_label not in summary_task.quantity_label


def test_plan_control_accepts_two_stage_plan_result_without_changing_snapshot_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control-two-stage.json")
    request = solved_baseline_request()
    request.plan_result.optimization_stages = ResourceAssistantOptimizationStages(
        primary=ResourceAssistantPrimaryStageSummary(
            solver_status="OPTIMAL",
            max_target_delay_days=0,
            makespan_days=request.plan_result.result.objective_days,
            optimality_proven=True,
            elapsed_seconds=3.0,
            configured_budget_seconds=30.0,
        ),
        secondary=ResourceAssistantSecondaryStageSummary(
            attempted=True,
            solver_status="FEASIBLE",
            resource_idle_days=10,
            continuity_penalty=4,
            elapsed_seconds=20.0,
            configured_budget_seconds=25.0,
        ),
        selected_stage="secondary",
        total_budget_seconds=30.0,
        total_elapsed_seconds=23.0,
    )

    baseline = create_baseline_plan_endpoint(request)
    summary = get_plan_control_project_endpoint(request.scenario.scenario_id)

    assert baseline.version_no == 1
    assert summary.active_plan is not None
    assert summary.active_plan.schedule_result_snapshot.objective_days == request.plan_result.result.objective_days


def _progress_status_date(baseline) -> date:
    return min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=30))


def test_plan_control_progress_api_normalizes_quantities_and_creates_correction_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    request = solved_baseline_request()
    baseline = create_baseline_plan_endpoint(request)
    task = baseline.generated_snapshot.schedule_input.tasks[0]
    status_date = _progress_status_date(baseline)

    first = create_progress_snapshot_endpoint(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人",
            entries=[
                ProgressEntry(
                    task_id=task.id,
                    status="in_progress",
                    actual_start_date=status_date - timedelta(days=1),
                    percent_complete=40,
                    completed_quantity=task.quantity * 0.4,
                    remaining_quantity=task.quantity * 0.6,
                    actual_productivity=task.quantity * 0.2,
                )
            ],
        )
    )
    first_entry = first.progress_snapshot.entries[0]
    assert first_entry.percent_complete == 40
    assert first_entry.completed_quantity == pytest.approx(task.quantity * 0.4)
    assert first_entry.remaining_quantity == pytest.approx(task.quantity * 0.6)
    assert first_entry.remaining_days == 3

    second = create_progress_snapshot_endpoint(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="复核人",
            correction_reason="现场复核后更正",
            expected_revision_no=1,
            entries=[
                first_entry.model_copy(
                    update={
                        "percent_complete": 50,
                        "completed_quantity": task.quantity * 0.5,
                        "remaining_quantity": task.quantity * 0.5,
                    }
                )
            ],
        )
    )
    summary = get_plan_control_project_endpoint(request.scenario.scenario_id)

    assert second.progress_snapshot.revision_no == 2
    assert second.progress_snapshot.entries[0].completed_quantity == pytest.approx(task.quantity * 0.5)
    assert summary.current_progress_snapshot is not None
    assert summary.current_progress_snapshot.progress_snapshot_id == second.progress_snapshot.progress_snapshot_id


def test_plan_control_forecast_api_returns_execution_summary_and_critical_nodes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control-forecast.json")
    request = solved_baseline_request()
    baseline = create_baseline_plan_endpoint(request)
    snapshot = create_progress_snapshot_endpoint(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=_progress_status_date(baseline),
            submitted_by="填报人",
            entries=[],
        )
    ).progress_snapshot

    forecast = create_forecast_endpoint(
        CreateForecastRequest(
            plan_version_id=baseline.plan_version_id,
            progress_snapshot_id=snapshot.progress_snapshot_id,
        )
    )

    task_count = len(baseline.generated_snapshot.schedule_input.tasks)
    assert forecast.execution_summary.not_started_future_count == task_count
    assert forecast.execution_summary.resource_policy == "baseline_fixed"
    assert len(forecast.critical_nodes) == len(baseline.generated_snapshot.schedule_input.milestones) + 1
    project_node = next(item for item in forecast.critical_nodes if item.node_id == "project-finish")
    assert project_node.target_date == baseline.schedule_result_snapshot.plan_finish_date
    assert project_node.date_source == "predicted"
    assert project_node.evidence
    summary = get_plan_control_project_endpoint(request.scenario.scenario_id)
    assert summary.latest_forecast is not None
    assert summary.latest_forecast.forecast_id == forecast.forecast_id
    assert summary.latest_forecast.critical_nodes == forecast.critical_nodes


@pytest.mark.parametrize(
    ("completed_factor", "remaining_factor", "percent_complete", "message"),
    [
        (0.5, 0.5, 40, "完成比例与已完工程量不一致"),
        (0.4, 0.5, 40, "已完工程量与剩余工程量之和"),
        (1.1, -0.1, 40, "已完工程量超过计划总工程量"),
        (-0.1, 1.1, 40, "已完工程量不能为负数"),
    ],
)
def test_plan_control_progress_api_returns_locatable_quantity_error(
    tmp_path: Path,
    monkeypatch,
    completed_factor: float,
    remaining_factor: float,
    percent_complete: float,
    message: str,
) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    baseline = create_baseline_plan_endpoint(solved_baseline_request())
    task = baseline.generated_snapshot.schedule_input.tasks[0]
    status_date = _progress_status_date(baseline)
    entry = ProgressEntry.model_construct(
        task_id=task.id,
        status="in_progress",
        actual_start_date=status_date - timedelta(days=1),
        percent_complete=percent_complete,
        completed_quantity=task.quantity * completed_factor,
        remaining_quantity=task.quantity * remaining_factor,
        actual_productivity=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        create_progress_snapshot_endpoint(
            CreateProgressSnapshotRequest(
                plan_version_id=baseline.plan_version_id,
                status_date=status_date,
                submitted_by="填报人",
                entries=[entry],
            )
        )

    assert exc_info.value.status_code == 422
    assert task.id in str(exc_info.value.detail)
    assert message in str(exc_info.value.detail)


def test_plan_control_accepts_new_or_legacy_resource_plan_outcome_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    current = solved_baseline_request()
    current.plan_result.schedule_outcome_status = "duration_target_met"
    current.plan_result.schedule_outcome_reason = "target_met"
    first = create_baseline_plan_endpoint(current)

    legacy = solved_baseline_request()
    legacy.plan_result.schedule_outcome_status = None
    legacy.plan_result.schedule_outcome_reason = None
    legacy.confirmation_reason = "验证旧状态兼容"
    second = create_baseline_plan_endpoint(legacy)

    assert first.version_no == 1
    assert second.version_no == 2
    assert get_plan_control_project_endpoint(current.scenario.scenario_id).active_plan.plan_version_id == second.plan_version_id


def test_plan_control_api_accepts_legacy_payload_without_structure_parameter_labels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    request = solved_baseline_request()
    payload = request.model_dump(mode="json")
    _drop_structure_parameter_labels(payload)
    legacy_request = type(request).model_validate(payload)

    baseline = create_baseline_plan_endpoint(legacy_request)
    summary = get_plan_control_project_endpoint(request.scenario.scenario_id)

    assert baseline.version_no == 1
    assert summary.active_plan is not None
    assert summary.active_plan.plan_version_id == baseline.plan_version_id


def test_plan_control_api_rejects_unsolved_plan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    request = solved_baseline_request()
    request.plan_result.result = None

    with pytest.raises(HTTPException) as exc_info:
        create_baseline_plan_endpoint(request)

    assert exc_info.value.status_code == 422
    assert "可行或最优" in str(exc_info.value.detail)


def test_plan_control_api_maps_not_found_conflict_and_storage_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    with pytest.raises(HTTPException) as not_found:
        create_forecast_endpoint(CreateForecastRequest(plan_version_id="missing", progress_snapshot_id="missing"))
    assert not_found.value.status_code == 404

    def raise_conflict(_request):
        raise PlanControlConflictError("输入已经过期")

    monkeypatch.setattr(main_module, "create_forecast", raise_conflict)
    with pytest.raises(HTTPException) as conflict:
        create_forecast_endpoint(CreateForecastRequest(plan_version_id="plan", progress_snapshot_id="snapshot"))
    assert conflict.value.status_code == 409

    storage_directory = tmp_path / "store-directory"
    storage_directory.mkdir()
    monkeypatch.setattr(default_plan_control_repository, "path", storage_directory)
    with pytest.raises(HTTPException) as unavailable:
        get_plan_control_project_endpoint("project")
    assert unavailable.value.status_code == 503
