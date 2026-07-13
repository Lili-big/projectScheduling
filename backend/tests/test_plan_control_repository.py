from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.plan_control_repository import (  # noqa: E402
    PlanControlRepository,
    PlanControlRepositoryError,
)
from app.models import CreateProgressSnapshotRequest, ProgressEntry  # noqa: E402
from app.services.progress_forecast import create_baseline_plan, create_progress_snapshot  # noqa: E402
from app.services.progress_forecast import PlanControlValidationError  # noqa: E402
from plan_control_helpers import solved_baseline_request  # noqa: E402


def _drop_structure_parameter_labels(value) -> None:
    if isinstance(value, dict):
        value.pop("structure_parameter_label", None)
        for nested in value.values():
            _drop_structure_parameter_labels(nested)
    elif isinstance(value, list):
        for nested in value:
            _drop_structure_parameter_labels(nested)


def test_repository_persists_unicode_and_returns_active_plan(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "计划管控.json")
    baseline = create_baseline_plan(solved_baseline_request(), repository)

    restored = PlanControlRepository(repository.path).project_summary(baseline.project_id)

    assert restored.active_plan is not None
    assert restored.active_plan.plan_version_id == baseline.plan_version_id
    assert restored.active_plan.project_name == baseline.project_name
    assert "测试计划工程师" in repository.path.read_text(encoding="utf-8")


def test_repository_rejects_corrupted_store(tmp_path: Path) -> None:
    path = tmp_path / "plan-control.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(PlanControlRepositoryError, match="读取失败"):
        PlanControlRepository(path).load()


def test_baseline_rejects_mismatched_plan_result_and_increments_versions(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "plan-control.json")
    request = solved_baseline_request()
    mismatched = request.model_copy(deep=True)
    mismatched.resource_plan.scenario_id = "another-plan"
    with pytest.raises(PlanControlValidationError, match="标识不一致"):
        create_baseline_plan(mismatched, repository)

    first = create_baseline_plan(request, repository)
    second_request = solved_baseline_request()
    second_request.confirmation_reason = "重新确认另一执行基准"
    second = create_baseline_plan(second_request, repository)
    store = repository.load()

    assert first.version_no == 1
    assert second.version_no == 2
    assert repository.get_plan_version(first.plan_version_id).status == "superseded"
    assert repository.project_summary(first.project_id).active_plan.plan_version_id == second.plan_version_id
    assert len(store.plan_versions) == 2


@pytest.mark.parametrize("legacy_status", ["met", "not_met", "unconfirmed", "infeasible"])
def test_repository_loads_legacy_target_status_without_rewriting_store(tmp_path: Path, legacy_status: str) -> None:
    path = tmp_path / f"plan-control-{legacy_status}.json"
    repository = PlanControlRepository(path)
    baseline = create_baseline_plan(solved_baseline_request(), repository)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for container_name in ("stats", "objective_breakdown"):
        target = payload["plan_versions"][0]["schedule_result_snapshot"][container_name].get("target_achievement")
        if isinstance(target, dict):
            target["target_status"] = legacy_status
            target.pop("schedule_outcome_status", None)
            target.pop("schedule_outcome_reason", None)
            target.pop("max_target_delay_days", None)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    restored = PlanControlRepository(path).project_summary(baseline.project_id)
    after = hashlib.sha256(path.read_bytes()).hexdigest()

    assert restored.active_plan is not None
    assert restored.active_plan.plan_version_id == baseline.plan_version_id
    assert before == after


def test_repository_loads_plan_without_structure_parameter_labels_without_rewriting_store(tmp_path: Path) -> None:
    path = tmp_path / "plan-control-legacy-task-fields.json"
    repository = PlanControlRepository(path)
    baseline = create_baseline_plan(solved_baseline_request(), repository)
    payload = json.loads(path.read_text(encoding="utf-8"))
    _drop_structure_parameter_labels(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    restored = PlanControlRepository(path).project_summary(baseline.project_id)
    after = hashlib.sha256(path.read_bytes()).hexdigest()

    assert restored.active_plan is not None
    assert restored.active_plan.plan_version_id == baseline.plan_version_id
    assert before == after


def test_repository_loads_legacy_progress_without_quantities_and_preserves_original_revision(tmp_path: Path) -> None:
    path = tmp_path / "plan-control-legacy-progress.json"
    repository = PlanControlRepository(path)
    baseline = create_baseline_plan(solved_baseline_request(), repository)
    task = baseline.generated_snapshot.schedule_input.tasks[0]
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=30))
    create_progress_snapshot(
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
                    estimated_remaining_days=3,
                )
            ],
        ),
        repository,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    legacy_entry = payload["progress_snapshots"][0]["entries"][0]
    legacy_entry.pop("completed_quantity", None)
    legacy_entry.pop("remaining_quantity", None)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    restored = repository.project_summary(baseline.project_id)
    after = hashlib.sha256(path.read_bytes()).hexdigest()

    assert restored.current_progress_snapshot is not None
    assert restored.current_progress_snapshot.entries[0].completed_quantity is None
    assert restored.current_progress_snapshot.entries[0].remaining_quantity is None
    assert before == after

    corrected = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="复核人",
            correction_reason="补齐历史工程量",
            expected_revision_no=1,
            entries=[
                ProgressEntry(
                    task_id=task.id,
                    status="in_progress",
                    actual_start_date=status_date - timedelta(days=1),
                    percent_complete=50,
                    completed_quantity=task.quantity * 0.5,
                    remaining_quantity=task.quantity * 0.5,
                    estimated_remaining_days=2,
                )
            ],
        ),
        repository,
    ).progress_snapshot
    snapshots = sorted(repository.load().progress_snapshots, key=lambda item: item.revision_no)

    assert corrected.revision_no == 2
    assert len(snapshots) == 2
    assert snapshots[0].revision_no == 1
    assert snapshots[0].is_current is False
    assert snapshots[0].entries[0].completed_quantity is None
    assert snapshots[1].is_current is True
    assert snapshots[1].entries[0].completed_quantity == pytest.approx(task.quantity * 0.5)


def test_repository_reads_conflicting_legacy_progress_without_rewriting_store(tmp_path: Path) -> None:
    path = tmp_path / "plan-control-conflicting-progress.json"
    repository = PlanControlRepository(path)
    baseline = create_baseline_plan(solved_baseline_request(), repository)
    task = baseline.generated_snapshot.schedule_input.tasks[0]
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=30))
    create_progress_snapshot(
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
                    estimated_remaining_days=3,
                )
            ],
        ),
        repository,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    legacy_entry = payload["progress_snapshots"][0]["entries"][0]
    legacy_entry["completed_quantity"] = task.quantity * 0.2
    legacy_entry["remaining_quantity"] = task.quantity * 0.2
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    restored = repository.project_summary(baseline.project_id)
    after = hashlib.sha256(path.read_bytes()).hexdigest()

    assert restored.current_progress_snapshot is not None
    assert restored.current_progress_snapshot.entries[0].completed_quantity == pytest.approx(task.quantity * 0.2)
    assert restored.current_progress_snapshot.entries[0].remaining_quantity == pytest.approx(task.quantity * 0.2)
    assert before == after
