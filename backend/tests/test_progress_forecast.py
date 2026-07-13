from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models import (  # noqa: E402
    AdoptAdjustmentRequest,
    CreateForecastRequest,
    CreateProgressSnapshotRequest,
    ProgressEntry,
)
from app.services.plan_control_repository import PlanControlConflictError, PlanControlRepository  # noqa: E402
from app.services.progress_forecast import (  # noqa: E402
    PlanControlValidationError,
    adopt_adjustment,
    create_adjustment_proposals,
    create_baseline_plan,
    create_forecast,
    create_progress_snapshot,
)
import app.services.progress_forecast as forecast_module  # noqa: E402
from plan_control_helpers import solved_baseline_request  # noqa: E402


def _repository_and_baseline(tmp_path: Path):
    repository = PlanControlRepository(tmp_path / "plan-control.json")
    baseline = create_baseline_plan(solved_baseline_request(), repository)
    return repository, baseline


def _repository_baseline_and_task_with_quantity(tmp_path: Path, quantity: float = 10):
    repository = PlanControlRepository(tmp_path / "plan-control-quantity.json")
    request = solved_baseline_request()
    source_task = request.plan_result.generated.schedule_input.tasks[0]
    source_task.quantity = quantity
    source_task.quantity_label = f"{quantity:g}m"
    baseline = create_baseline_plan(request, repository)
    task = baseline.generated_snapshot.schedule_input.tasks[0]
    return repository, baseline, task


def _progress_status_date(baseline) -> date:
    return min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=30))


def test_progress_snapshot_calculates_remaining_days_and_keeps_revision_audit(tmp_path: Path) -> None:
    repository, baseline = _repository_and_baseline(tmp_path)
    task = baseline.generated_snapshot.schedule_input.tasks[0]
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=30))
    actual_start = max(baseline.scenario_snapshot.project.start_date, status_date - timedelta(days=2))
    remaining_quantity = task.quantity * 0.6
    first = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人甲",
            entries=[
                ProgressEntry(
                    task_id=task.id,
                    status="in_progress",
                    actual_start_date=actual_start,
                    percent_complete=40,
                    completed_quantity=task.quantity * 0.4,
                    remaining_quantity=remaining_quantity,
                    actual_productivity=remaining_quantity / 3,
                )
            ],
        ),
        repository,
    )
    entry = first.progress_snapshot.entries[0]
    assert entry.remaining_days == 3
    assert entry.remaining_days_source == "calculated"

    second = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人乙",
            correction_reason="复核后修正完成比例",
            expected_revision_no=1,
            entries=[
                entry.model_copy(
                    update={
                        "percent_complete": 50,
                        "completed_quantity": task.quantity * 0.5,
                        "remaining_quantity": task.quantity * 0.5,
                    }
                )
            ],
        ),
        repository,
    )

    store = repository.load()
    assert second.progress_snapshot.revision_no == 2
    assert len(store.correction_records) == 1
    assert any(change["field"] == "percent_complete" for change in store.correction_records[0].changes)
    assert len([item for item in store.progress_snapshots if item.is_current]) == 1


def test_progress_quantity_normalizes_percent_only_and_calculates_remaining_days(tmp_path: Path) -> None:
    repository, baseline, task = _repository_baseline_and_task_with_quantity(tmp_path)
    status_date = _progress_status_date(baseline)
    response = create_progress_snapshot(
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
                    actual_productivity=2,
                )
            ],
        ),
        repository,
    )

    entry = response.progress_snapshot.entries[0]
    assert entry.percent_complete == 40
    assert entry.completed_quantity == 4
    assert entry.remaining_quantity == 6
    assert entry.remaining_days == 3
    assert entry.remaining_days_source == "calculated"


def test_progress_quantity_accepts_consistent_completed_quantity_and_display_percent(tmp_path: Path) -> None:
    repository, baseline, task = _repository_baseline_and_task_with_quantity(tmp_path, quantity=3)
    status_date = _progress_status_date(baseline)
    response = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人",
            entries=[
                ProgressEntry(
                    task_id=task.id,
                    status="in_progress",
                    actual_start_date=status_date - timedelta(days=1),
                    percent_complete=33.33,
                    completed_quantity=1,
                    remaining_quantity=2,
                    estimated_remaining_days=2,
                )
            ],
        ),
        repository,
    )

    entry = response.progress_snapshot.entries[0]
    assert entry.percent_complete == 33.33
    assert entry.completed_quantity == 1
    assert entry.remaining_quantity == 2


@pytest.mark.parametrize(
    ("percent_complete", "completed_quantity", "remaining_quantity", "message"),
    [
        (40, 5, 5, "完成比例与已完工程量不一致"),
        (40, 4, 5, "已完工程量与剩余工程量之和"),
        (40, 11, -1, "已完工程量超过计划总工程量"),
    ],
)
def test_progress_quantity_rejects_conflicting_values(
    tmp_path: Path,
    percent_complete: float,
    completed_quantity: float,
    remaining_quantity: float,
    message: str,
) -> None:
    repository, baseline, task = _repository_baseline_and_task_with_quantity(tmp_path)
    status_date = _progress_status_date(baseline)
    entry = ProgressEntry.model_construct(
        task_id=task.id,
        status="in_progress",
        actual_start_date=status_date - timedelta(days=1),
        actual_finish_date=None,
        percent_complete=percent_complete,
        completed_quantity=completed_quantity,
        remaining_quantity=remaining_quantity,
        actual_productivity=2,
        estimated_remaining_days=None,
        remaining_days=0,
        remaining_days_source="none",
        expected_resume_date=None,
        reason=None,
        notes="",
    )

    with pytest.raises(PlanControlValidationError, match=message):
        create_progress_snapshot(
            CreateProgressSnapshotRequest(
                plan_version_id=baseline.plan_version_id,
                status_date=status_date,
                submitted_by="填报人",
                entries=[entry],
            ),
            repository,
        )


def test_progress_quantity_invalid_total_uses_percent_and_manual_remaining_days(tmp_path: Path) -> None:
    repository, baseline, task = _repository_baseline_and_task_with_quantity(tmp_path, quantity=0)
    status_date = _progress_status_date(baseline)
    response = create_progress_snapshot(
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
                    estimated_remaining_days=5,
                )
            ],
        ),
        repository,
    )

    entry = response.progress_snapshot.entries[0]
    assert entry.completed_quantity is None
    assert entry.remaining_quantity is None
    assert entry.remaining_days == 5
    assert entry.remaining_days_source == "manual"


def test_progress_quantity_rejects_quantity_input_when_total_is_invalid(tmp_path: Path) -> None:
    repository, baseline, task = _repository_baseline_and_task_with_quantity(tmp_path, quantity=0)
    status_date = _progress_status_date(baseline)

    with pytest.raises(PlanControlValidationError, match="计划总工程量无效"):
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
                        completed_quantity=4,
                        remaining_quantity=6,
                        estimated_remaining_days=5,
                    )
                ],
            ),
            repository,
        )


@pytest.mark.parametrize(
    ("status", "percent_complete", "actual_start_offset", "actual_finish_offset", "reason", "manual_days", "expected"),
    [
        ("not_started", 0, None, None, None, None, (0, 0, 10, 3, "baseline")),
        ("completed", 100, -3, -1, None, None, (100, 10, 0, 0, "none")),
        ("paused", 40, -2, None, "等待复工", 7, (40, 4, 6, 7, "manual")),
        ("cancelled", 40, -2, None, "设计取消", None, (40, 4, 6, 0, "none")),
    ],
)
def test_progress_quantity_status_matrix(
    tmp_path: Path,
    status: str,
    percent_complete: float,
    actual_start_offset: int | None,
    actual_finish_offset: int | None,
    reason: str | None,
    manual_days: int | None,
    expected: tuple[float, float, float, int, str],
) -> None:
    repository, baseline, task = _repository_baseline_and_task_with_quantity(tmp_path)
    status_date = _progress_status_date(baseline)
    actual_start = status_date + timedelta(days=actual_start_offset) if actual_start_offset is not None else None
    actual_finish = status_date + timedelta(days=actual_finish_offset) if actual_finish_offset is not None else None
    entry = ProgressEntry(
        task_id=task.id,
        status=status,
        actual_start_date=actual_start,
        actual_finish_date=actual_finish,
        percent_complete=percent_complete,
        completed_quantity=None if status in {"not_started", "completed"} else 4,
        remaining_quantity=None if status in {"not_started", "completed"} else 6,
        estimated_remaining_days=manual_days,
        reason=reason,
    )
    response = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人",
            entries=[entry],
        ),
        repository,
    )

    normalized = response.progress_snapshot.entries[0]
    assert (
        normalized.percent_complete,
        normalized.completed_quantity,
        normalized.remaining_quantity,
        normalized.remaining_days,
        normalized.remaining_days_source,
    ) == expected


@pytest.mark.parametrize(("status", "reason"), [("paused", "等待复工"), ("cancelled", "设计取消")])
def test_progress_quantity_rejects_finished_percentage_for_noncompleted_status(
    tmp_path: Path,
    status: str,
    reason: str,
) -> None:
    repository, baseline, task = _repository_baseline_and_task_with_quantity(tmp_path)
    status_date = _progress_status_date(baseline)

    with pytest.raises(PlanControlValidationError, match="完成比例必须小于 100%"):
        create_progress_snapshot(
            CreateProgressSnapshotRequest(
                plan_version_id=baseline.plan_version_id,
                status_date=status_date,
                submitted_by="填报人",
                entries=[
                    ProgressEntry(
                        task_id=task.id,
                        status=status,
                        actual_start_date=status_date - timedelta(days=1),
                        percent_complete=100,
                        estimated_remaining_days=3 if status == "paused" else None,
                        reason=reason,
                    )
                ],
            ),
            repository,
        )


def test_same_day_correction_requires_reason_and_revision_match(tmp_path: Path) -> None:
    repository, baseline = _repository_and_baseline(tmp_path)
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=1))
    request = CreateProgressSnapshotRequest(
        plan_version_id=baseline.plan_version_id,
        status_date=status_date,
        submitted_by="填报人",
        entries=[],
    )
    create_progress_snapshot(request, repository)

    with pytest.raises(PlanControlValidationError, match="更正原因"):
        create_progress_snapshot(request, repository)

    with pytest.raises(PlanControlConflictError, match="已被更新"):
        create_progress_snapshot(
            request.model_copy(update={"correction_reason": "更正", "expected_revision_no": 99}),
            repository,
        )


def test_forecast_freezes_completed_task_and_adoption_creates_new_version(tmp_path: Path) -> None:
    repository, baseline = _repository_and_baseline(tmp_path)
    task = baseline.generated_snapshot.schedule_input.tasks[0]
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=30))
    actual_finish = status_date - timedelta(days=1)
    actual_start = max(baseline.scenario_snapshot.project.start_date, actual_finish - timedelta(days=2))
    snapshot = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人",
            entries=[
                ProgressEntry(
                    task_id=task.id,
                    status="completed",
                    actual_start_date=actual_start,
                    actual_finish_date=actual_finish,
                    percent_complete=100,
                )
            ],
        ),
        repository,
    ).progress_snapshot

    forecast = create_forecast(
        CreateForecastRequest(
            plan_version_id=baseline.plan_version_id,
            progress_snapshot_id=snapshot.progress_snapshot_id,
        ),
        repository,
    )
    actual = next(item for item in forecast.historical_tasks if item.task_id == task.id)
    assert actual.actual_finish_date == actual_finish
    assert all(item.predicted_start_date >= status_date for item in forecast.predicted_tasks)

    comparison = create_adjustment_proposals(forecast.forecast_id, {}, repository)
    assert {item.strategy for item in comparison.proposals} == {
        "as_is",
        "add_bottleneck_resources",
        "prioritize_critical_tasks",
    }
    proposal = next(item for item in comparison.proposals if item.proposal_id == comparison.recommended_proposal_id)
    adopted = adopt_adjustment(
        proposal.proposal_id,
        AdoptAdjustmentRequest(
            confirmed_by="总计划工程师",
            adoption_reason="接受系统推荐并形成滚动执行版",
            source_plan_fingerprint=baseline.input_fingerprint,
        ),
        repository,
    )
    assert adopted.new_plan_version.version_no == 2
    assert adopted.new_plan_version.parent_version_id == baseline.plan_version_id
    assert adopted.previous_plan_version.status == "superseded"
    with pytest.raises(PlanControlConflictError, match="已经采用|来源计划已经变化"):
        adopt_adjustment(
            proposal.proposal_id,
            AdoptAdjustmentRequest(
                confirmed_by="总计划工程师",
                adoption_reason="重复采用",
                source_plan_fingerprint=baseline.input_fingerprint,
            ),
            repository,
        )


def test_progress_calculates_percent_and_warns_for_actual_logic_conflict(tmp_path: Path) -> None:
    repository, baseline = _repository_and_baseline(tmp_path)
    link = baseline.generated_snapshot.schedule_input.precedence_links[0]
    tasks = {item.id: item for item in baseline.generated_snapshot.schedule_input.tasks}
    predecessor = tasks[link.predecessor_id]
    successor = tasks[link.successor_id]
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=30))
    response = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人",
            entries=[
                ProgressEntry(
                    task_id=predecessor.id,
                    status="completed",
                    actual_start_date=status_date - timedelta(days=4),
                    actual_finish_date=status_date - timedelta(days=1),
                    percent_complete=100,
                ),
                ProgressEntry(
                    task_id=successor.id,
                    status="in_progress",
                    actual_start_date=status_date - timedelta(days=2),
                    percent_complete=50,
                    completed_quantity=successor.quantity / 2,
                    estimated_remaining_days=2,
                ),
            ],
        ),
        repository,
    )

    successor_entry = next(item for item in response.progress_snapshot.entries if item.task_id == successor.id)
    assert successor_entry.percent_complete == 50
    assert response.progress_snapshot.data_quality_status == "warning"
    assert any("后续任务早于前置任务完成" in item.message for item in response.diagnostics)


def test_forecast_is_deduplicated_and_new_progress_marks_it_stale(tmp_path: Path) -> None:
    repository, baseline = _repository_and_baseline(tmp_path)
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=1))
    snapshot = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人",
            entries=[],
        ),
        repository,
    ).progress_snapshot
    request = CreateForecastRequest(
        plan_version_id=baseline.plan_version_id,
        progress_snapshot_id=snapshot.progress_snapshot_id,
    )
    first = create_forecast(request, repository)
    second = create_forecast(request, repository)
    assert second.forecast_id == first.forecast_id

    correction = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="复核人",
            correction_reason="补充复核记录",
            expected_revision_no=1,
            entries=[],
        ),
        repository,
    )
    assert correction.stale_forecast_ids == [first.forecast_id]
    assert repository.get_forecast(first.forecast_id).status == "stale"


def test_adjustment_strategies_isolate_failure_and_only_expand_bottleneck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, baseline = _repository_and_baseline(tmp_path)
    status_date = min(date.today(), baseline.scenario_snapshot.project.start_date + timedelta(days=1))
    snapshot = create_progress_snapshot(
        CreateProgressSnapshotRequest(
            plan_version_id=baseline.plan_version_id,
            status_date=status_date,
            submitted_by="填报人",
            entries=[],
        ),
        repository,
    ).progress_snapshot
    forecast = create_forecast(
        CreateForecastRequest(plan_version_id=baseline.plan_version_id, progress_snapshot_id=snapshot.progress_snapshot_id),
        repository,
    )
    original = forecast_module._solve_forecast

    def fail_one_strategy(plan, progress, strategy, parameters):
        if strategy == "prioritize_critical_tasks":
            raise RuntimeError("模拟策略求解失败")
        return original(plan, progress, strategy, parameters)

    monkeypatch.setattr(forecast_module, "_solve_forecast", fail_one_strategy)
    requested = {pool.type: 2 for pool in baseline.resource_plan_snapshot.resource_pools}
    comparison = create_adjustment_proposals(forecast.forecast_id, requested, repository)

    by_strategy = {item.strategy: item for item in comparison.proposals}
    assert by_strategy["as_is"].status == "feasible"
    assert by_strategy["prioritize_critical_tasks"].status == "failed"
    increments = by_strategy["add_bottleneck_resources"].metrics["resource_increments"]
    assert increments
    assert all(count <= 2 for count in increments.values())
    assert set(increments) < set(requested) or len(requested) == 1
