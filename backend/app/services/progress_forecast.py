from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..contracts import (
    AdoptAdjustmentRequest,
    AdoptAdjustmentResponse,
    AdjustmentComparisonResponse,
    AdjustmentProposal,
    CreateBaselinePlanRequest,
    CreateForecastRequest,
    CreateIntegratedScheduleRequest,
    CreateProgressSnapshotRequest,
    CreateProgressSnapshotResponse,
    CriticalNodeEvidence,
    CriticalNodeForecast,
    ForecastExecutionSummary,
    ForecastSchedule,
    ForecastStrategy,
    ForecastTaskState,
    GeneratedScheduleInput,
    MilestoneConstraint,
    PlanChangeRecord,
    PlanVersion,
    PrecedenceLink,
    ProgressCorrectionRecord,
    ProgressEntry,
    ProgressSnapshot,
    Resource,
    ScheduleInput,
    ScheduleResult,
    ScheduledTask,
    TaskExecutionConstraint,
    ValidationMessage,
)
from ..solver import evaluate_milestones_from_scheduled_tasks, solve_schedule, task_ids_for_milestone
from .plan_control_repository import (
    PlanControlConflictError,
    PlanControlRepository,
    default_plan_control_repository,
)
from .integrated_schedule import solve_integrated_schedule


class PlanControlValidationError(ValueError):
    status_code = 422


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def create_baseline_plan(
    request: CreateBaselinePlanRequest,
    repository: PlanControlRepository = default_plan_control_repository,
) -> PlanVersion:
    result = request.plan_result.result
    generated = request.plan_result.generated
    integrated_snapshot = None
    if request.scenario.girder_planning and request.scenario.girder_planning.enabled:
        if not request.integrated_snapshot_id:
            raise PlanControlValidationError("启用架梁专项时必须提供已收敛的联合计算快照。")
        integrated_snapshot = repository.get_integrated_snapshot(request.integrated_snapshot_id)
        if integrated_snapshot.status != "converged":
            raise PlanControlValidationError("只有已收敛的联合计算快照才能发布统一基线。")
        scenario_version = repository.get_planning_scenario_version(integrated_snapshot.scenario_version_id)
        if scenario_version.scenario_id != request.scenario.scenario_id:
            raise PlanControlValidationError("联合计算快照与当前场景不一致。")
        if integrated_snapshot.generated_snapshot is not None and integrated_snapshot.schedule_result is not None:
            generated = integrated_snapshot.generated_snapshot
            result = integrated_snapshot.schedule_result
    if result is None or generated is None or result.status not in {"OPTIMAL", "FEASIBLE"}:
        raise PlanControlValidationError("只能把已完成求解且可行或最优的方案设为基准计划。")
    if request.resource_plan.scenario_id != request.plan_result.scenario_id:
        raise PlanControlValidationError("资源方案与求解结果标识不一致。")
    if not request.confirmed_by.strip() or not request.confirmation_reason.strip():
        raise PlanControlValidationError("确认人和选择原因不能为空。")
    project_id = request.scenario.scenario_id
    version_no = repository.next_version_no(project_id)
    confirmed_at = _now()
    fingerprint = _stable_id(
        "plan-input",
        {
            "scenario": request.scenario.model_dump(mode="json"),
            "resource_plan": request.resource_plan.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        },
    )
    version = PlanVersion(
        plan_version_id=_stable_id("plan", {"project_id": project_id, "version_no": version_no, "at": confirmed_at}),
        project_id=project_id,
        project_name=request.scenario.project.project_name,
        version_no=version_no,
        version_kind="baseline",
        status="active",
        source_scenario_id=request.resource_plan.scenario_id,
        scenario_snapshot=request.scenario.model_copy(deep=True),
        generated_snapshot=generated.model_copy(deep=True),
        schedule_result_snapshot=result.model_copy(deep=True),
        resource_plan_snapshot=request.resource_plan.model_copy(deep=True),
        input_fingerprint=fingerprint,
        confirmed_by=request.confirmed_by.strip(),
        confirmed_at=confirmed_at,
        confirmation_reason=request.confirmation_reason.strip(),
        project_data_version_id=(
            integrated_snapshot.project_data_version_id
            if integrated_snapshot
            else request.scenario.project_data_version_id
        ),
        scenario_version_id=(integrated_snapshot.scenario_version_id if integrated_snapshot else None),
        integrated_snapshot_id=(integrated_snapshot.integrated_snapshot_id if integrated_snapshot else None),
        girder_result_snapshot=(integrated_snapshot.girder_result.model_copy(deep=True) if integrated_snapshot and integrated_snapshot.girder_result else None),
    )
    return repository.add_plan_version(version)


def create_progress_snapshot(
    request: CreateProgressSnapshotRequest,
    repository: PlanControlRepository = default_plan_control_repository,
) -> CreateProgressSnapshotResponse:
    plan = repository.get_plan_version(request.plan_version_id)
    if request.status_date < plan.scenario_snapshot.project.start_date:
        raise PlanControlValidationError("状态日期不能早于项目计划开始日期。")
    if request.status_date > date.today():
        raise PlanControlValidationError("状态日期不能晚于今天。")
    if not request.submitted_by.strip():
        raise PlanControlValidationError("填报人不能为空。")
    task_by_id = {task.id: task for task in plan.generated_snapshot.schedule_input.tasks}
    normalized: list[ProgressEntry] = []
    messages: list[ValidationMessage] = []
    _validate_girder_actuals(plan, request)
    seen: set[str] = set()
    for entry in request.entries:
        if entry.task_id in seen:
            raise PlanControlValidationError(f"任务 {entry.task_id} 重复填报。")
        seen.add(entry.task_id)
        task = task_by_id.get(entry.task_id)
        if task is None:
            raise PlanControlValidationError(f"进度任务 {entry.task_id} 不属于当前计划版本。")
        normalized_entry = _normalize_progress_entry(entry, task, request.status_date)
        normalized.append(normalized_entry)
        if normalized_entry.status == "paused" and normalized_entry.expected_resume_date is None:
            messages.append(
                ValidationMessage(
                    level="warning",
                    subject_id=entry.task_id,
                    message="暂停任务尚未填写恢复日期；现场事实已保存，但暂不能生成确定性未来排程。",
                )
            )
    previous = repository.current_snapshot_for_date(request.plan_version_id, request.status_date)
    if previous and not (request.correction_reason or "").strip():
        raise PlanControlValidationError("更正同一状态日期的进度时必须填写更正原因。")
    prior_snapshots = sorted(
        (
            item
            for item in repository.load().progress_snapshots
            if item.plan_version_id == request.plan_version_id
            and item.is_current
            and item.status_date < request.status_date
        ),
        key=lambda item: item.status_date,
        reverse=True,
    )
    if prior_snapshots:
        prior_entries = {item.task_id: item for item in prior_snapshots[0].entries}
        for entry in normalized:
            prior = prior_entries.get(entry.task_id)
            if prior and entry.percent_complete < prior.percent_complete:
                raise PlanControlValidationError(
                    f"任务 {entry.task_id} 的完成比例不能低于上一状态日期；请更正原进度快照。"
                )
    entry_by_id = {item.task_id: item for item in normalized}
    for link in plan.generated_snapshot.schedule_input.precedence_links:
        predecessor = entry_by_id.get(link.predecessor_id)
        successor = entry_by_id.get(link.successor_id)
        if (
            predecessor
            and successor
            and predecessor.actual_finish_date
            and successor.actual_start_date
            and successor.actual_start_date < predecessor.actual_finish_date
        ):
            messages.append(
                ValidationMessage(
                    level="warning",
                    subject_id=link.successor_id,
                    message=f"现场实绩显示后续任务早于前置任务完成，预测将保留事实并降低可信度：{link.predecessor_id} → {link.successor_id}。",
                )
            )
    revision = (previous.revision_no + 1) if previous else 1
    submitted_at = _now()
    snapshot = ProgressSnapshot(
        progress_snapshot_id=_stable_id(
            "progress",
            {"plan": request.plan_version_id, "status_date": request.status_date, "revision": revision, "at": submitted_at},
        ),
        plan_version_id=request.plan_version_id,
        status_date=request.status_date,
        revision_no=revision,
        entries=normalized,
        data_quality_status="warning" if messages else "valid",
        validation_messages=messages,
        submitted_by=request.submitted_by.strip(),
        submitted_at=submitted_at,
        correction_reason=(request.correction_reason or "").strip() or None,
        yard_inventory_actuals=[item.model_copy(deep=True) for item in request.yard_inventory_actuals],
        girder_execution_actuals=[item.model_copy(deep=True) for item in request.girder_execution_actuals],
        girder_machine_actuals=[item.model_copy(deep=True) for item in request.girder_machine_actuals],
        passage_actuals=[item.model_copy(deep=True) for item in request.passage_actuals],
    )
    correction = None
    if previous:
        correction = ProgressCorrectionRecord(
            correction_id=_stable_id("correction", {"old": previous.progress_snapshot_id, "new": snapshot.progress_snapshot_id}),
            plan_version_id=request.plan_version_id,
            status_date=request.status_date,
            previous_snapshot_id=previous.progress_snapshot_id,
            new_snapshot_id=snapshot.progress_snapshot_id,
            changes=_progress_changes(previous.entries, snapshot.entries),
            correction_reason=snapshot.correction_reason or "",
            corrected_by=request.submitted_by.strip(),
            corrected_at=submitted_at,
        )
    saved, stale_ids, stale_integrated_ids = repository.add_progress_snapshot(
        snapshot,
        correction,
        expected_revision_no=request.expected_revision_no,
    )
    return CreateProgressSnapshotResponse(
        progress_snapshot=saved,
        stale_forecast_ids=stale_ids,
        stale_integrated_snapshot_ids=stale_integrated_ids,
        diagnostics=messages,
    )


def _validate_girder_actuals(plan: PlanVersion, request: CreateProgressSnapshotRequest) -> None:
    """校验架梁实绩的唯一性、日期和基本物料平衡。

    实绩是事实源：可以偏离原计划，但不能制造重复架梁、未来事实或无法解释的
    产耗关系。通过后才写入进度快照，避免错误数据进入滚动重排。
    """
    task_by_id = {task.id: task for task in plan.generated_snapshot.schedule_input.tasks}
    seen_tasks: set[str] = set()
    consumed_by_yard_type: defaultdict[tuple[str, str], float] = defaultdict(float)
    for actual in request.girder_execution_actuals:
        if actual.span_task_id in seen_tasks:
            raise PlanControlValidationError(f"架梁任务 {actual.span_task_id} 重复填报实际架梁。")
        seen_tasks.add(actual.span_task_id)
        task = task_by_id.get(actual.span_task_id)
        if task is None:
            raise PlanControlValidationError(f"架梁实绩任务 {actual.span_task_id} 不属于当前计划版本。")
        if actual.actual_start_date and actual.actual_start_date > request.status_date:
            raise PlanControlValidationError(f"架梁任务 {actual.span_task_id} 的实际开始日期晚于状态日期。")
        if actual.actual_finish_date and actual.actual_finish_date > request.status_date:
            raise PlanControlValidationError(f"架梁任务 {actual.span_task_id} 的实际完成日期晚于状态日期。")
        if actual.actual_start_date and actual.actual_finish_date and actual.actual_finish_date < actual.actual_start_date:
            raise PlanControlValidationError(f"架梁任务 {actual.span_task_id} 的实际日期倒置。")
        if actual.status == "completed" and actual.erected_beam_count <= 0:
            raise PlanControlValidationError(f"已完成架梁任务 {actual.span_task_id} 必须填写已架梁片数。")
        if actual.erected_beam_count > task.quantity + _quantity_tolerance(task.quantity):
            raise PlanControlValidationError(f"架梁任务 {actual.span_task_id} 的实际架梁数量超过计划工程量。")
        if actual.status == "completed":
            yard_id = str(task.properties.get("beam_yard_id") or "")
            beam_type = str(task.properties.get("beam_type") or "default")
            if yard_id:
                consumed_by_yard_type[(yard_id, beam_type)] += actual.erected_beam_count

    opening_by_yard_type: defaultdict[tuple[str, str], float] = defaultdict(float)
    if plan.girder_result_snapshot:
        for point in plan.girder_result_snapshot.yard_inventory_series:
            key = (point.beam_yard_id, point.beam_type)
            opening_by_yard_type[key] = max(opening_by_yard_type[key], point.opening_inventory)
    inventory_seen: set[tuple[str, str]] = set()
    for actual in request.yard_inventory_actuals:
        key = (actual.beam_yard_id, actual.beam_type)
        if key in inventory_seen:
            raise PlanControlValidationError(f"梁场 {actual.beam_yard_id}、梁型 {actual.beam_type} 的库存实绩重复填报。")
        inventory_seen.add(key)
        consumed = consumed_by_yard_type.get(key, 0.0)
        available = opening_by_yard_type.get(key, 0.0) + actual.cumulative_produced + actual.opening_inventory_adjustment
        if available + _quantity_tolerance(max(available, consumed, 1.0)) < consumed + actual.observed_inventory:
            raise PlanControlValidationError(
                f"梁场 {actual.beam_yard_id}、梁型 {actual.beam_type} 的产耗库存不平衡：产出与期初无法解释已消耗梁片。"
            )


_PERCENT_COMPLETE_TOLERANCE = 0.011


def _quantity_tolerance(total_quantity: float) -> float:
    return max(1e-6, abs(total_quantity) * 1e-9)


def _quantities_are_close(left: float, right: float, total_quantity: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=1e-9,
        abs_tol=_quantity_tolerance(total_quantity),
    )


def _normalize_progress_quantities(entry: ProgressEntry, task) -> dict[str, float | None]:
    total_quantity = float(task.quantity)
    total_is_valid = math.isfinite(total_quantity) and total_quantity > 0
    if not total_is_valid:
        if entry.completed_quantity is not None or entry.remaining_quantity is not None:
            raise PlanControlValidationError(
                f"任务 {entry.task_id} 的计划总工程量无效，不能填写已完或剩余工程量。"
            )
        return {
            "percent_complete": entry.percent_complete,
            "completed_quantity": None,
            "remaining_quantity": None,
        }

    completed_quantity = entry.completed_quantity
    remaining_quantity = entry.remaining_quantity

    if completed_quantity is not None:
        if not math.isfinite(completed_quantity) or completed_quantity < 0:
            raise PlanControlValidationError(f"任务 {entry.task_id} 的已完工程量不能为负数或非有限数值。")
        if completed_quantity > total_quantity and not _quantities_are_close(
            completed_quantity, total_quantity, total_quantity
        ):
            raise PlanControlValidationError(f"任务 {entry.task_id} 的已完工程量超过计划总工程量。")
        completed_quantity = min(completed_quantity, total_quantity)

    if remaining_quantity is not None:
        if not math.isfinite(remaining_quantity) or remaining_quantity < 0:
            raise PlanControlValidationError(f"任务 {entry.task_id} 的剩余工程量不能为负数或非有限数值。")
        if remaining_quantity > total_quantity and not _quantities_are_close(
            remaining_quantity, total_quantity, total_quantity
        ):
            raise PlanControlValidationError(f"任务 {entry.task_id} 的剩余工程量超过计划总工程量。")
        remaining_quantity = min(remaining_quantity, total_quantity)

    if entry.status == "not_started":
        if completed_quantity is not None and not _quantities_are_close(completed_quantity, 0, total_quantity):
            raise PlanControlValidationError(f"未开始任务 {entry.task_id} 的已完工程量必须为 0。")
        if remaining_quantity is not None and not _quantities_are_close(
            remaining_quantity, total_quantity, total_quantity
        ):
            raise PlanControlValidationError(f"未开始任务 {entry.task_id} 的剩余工程量必须等于计划总工程量。")
        return {
            "percent_complete": 0,
            "completed_quantity": 0,
            "remaining_quantity": total_quantity,
        }

    if entry.status == "completed":
        if completed_quantity is not None and not _quantities_are_close(
            completed_quantity, total_quantity, total_quantity
        ):
            raise PlanControlValidationError(f"已完成任务 {entry.task_id} 的已完工程量必须等于计划总工程量。")
        if remaining_quantity is not None and not _quantities_are_close(remaining_quantity, 0, total_quantity):
            raise PlanControlValidationError(f"已完成任务 {entry.task_id} 的剩余工程量必须为 0。")
        return {
            "percent_complete": 100,
            "completed_quantity": total_quantity,
            "remaining_quantity": 0,
        }

    if completed_quantity is None and remaining_quantity is None:
        completed_quantity = total_quantity * entry.percent_complete / 100
        remaining_quantity = total_quantity - completed_quantity
        return {
            "percent_complete": round(entry.percent_complete, 2),
            "completed_quantity": completed_quantity,
            "remaining_quantity": remaining_quantity,
        }

    if completed_quantity is None:
        completed_quantity = total_quantity - remaining_quantity
    expected_percent_complete = round(completed_quantity / total_quantity * 100, 2)
    if abs(entry.percent_complete - expected_percent_complete) > _PERCENT_COMPLETE_TOLERANCE:
        raise PlanControlValidationError(f"任务 {entry.task_id} 的完成比例与已完工程量不一致。")

    expected_remaining_quantity = total_quantity - completed_quantity
    if remaining_quantity is not None and not _quantities_are_close(
        remaining_quantity, expected_remaining_quantity, total_quantity
    ):
        raise PlanControlValidationError(
            f"任务 {entry.task_id} 的已完工程量与剩余工程量之和不等于计划总工程量。"
        )
    return {
        "percent_complete": expected_percent_complete,
        "completed_quantity": completed_quantity,
        "remaining_quantity": expected_remaining_quantity,
    }


def _normalize_progress_entry(entry: ProgressEntry, task, status_date: date) -> ProgressEntry:
    values = entry.model_dump()
    for field in ("actual_start_date", "actual_finish_date"):
        value = values.get(field)
        if value and value > status_date:
            raise PlanControlValidationError(f"任务 {entry.task_id} 的实际日期不能晚于状态日期。")
    if entry.actual_start_date and entry.actual_finish_date and entry.actual_finish_date < entry.actual_start_date:
        raise PlanControlValidationError(f"任务 {entry.task_id} 的实际完成日期不能早于实际开始日期。")
    values.update(_normalize_progress_quantities(entry, task))

    if entry.status == "not_started":
        if entry.actual_start_date or entry.actual_finish_date or entry.percent_complete != 0:
            raise PlanControlValidationError(f"未开始任务 {entry.task_id} 不能填写实际日期或完成比例。")
        values.update(remaining_days=task.duration_days, remaining_days_source="baseline")
    elif entry.status == "in_progress":
        if entry.actual_start_date is None or not (0 < entry.percent_complete < 100):
            raise PlanControlValidationError(f"进行中任务 {entry.task_id} 必须填写实际开始日期和 0–100 之间的完成比例。")
        normalized_remaining_quantity = values["remaining_quantity"]
        if normalized_remaining_quantity is not None and entry.actual_productivity is not None:
            values.update(
                remaining_days=max(1, math.ceil(normalized_remaining_quantity / entry.actual_productivity)),
                remaining_days_source="calculated",
            )
        elif entry.estimated_remaining_days is not None and entry.estimated_remaining_days > 0:
            values.update(remaining_days=entry.estimated_remaining_days, remaining_days_source="manual")
        else:
            raise PlanControlValidationError(f"进行中任务 {entry.task_id} 缺少可计算数据或人工预计剩余工期。")
    elif entry.status == "completed":
        if entry.actual_start_date is None or entry.actual_finish_date is None or entry.percent_complete != 100:
            raise PlanControlValidationError(f"已完成任务 {entry.task_id} 必须填写实际起止日期且完成比例为 100%。")
        values.update(remaining_days=0, remaining_days_source="none")
    elif entry.status == "paused":
        if not (0 <= values["percent_complete"] < 100):
            raise PlanControlValidationError(f"暂停任务 {entry.task_id} 的完成比例必须小于 100%。")
        if entry.actual_start_date is None or not (entry.reason or "").strip():
            raise PlanControlValidationError(f"暂停任务 {entry.task_id} 必须填写实际开始日期和暂停原因。")
        if entry.estimated_remaining_days is None or entry.estimated_remaining_days <= 0:
            raise PlanControlValidationError(f"暂停任务 {entry.task_id} 必须填写预计剩余工期。")
        if entry.expected_resume_date and entry.expected_resume_date < status_date:
            raise PlanControlValidationError(f"暂停任务 {entry.task_id} 的恢复日期不能早于状态日期。")
        values.update(remaining_days=entry.estimated_remaining_days, remaining_days_source="manual")
    else:
        if not (0 <= values["percent_complete"] < 100):
            raise PlanControlValidationError(f"取消任务 {entry.task_id} 的完成比例必须小于 100%。")
        if not (entry.reason or "").strip():
            raise PlanControlValidationError(f"取消任务 {entry.task_id} 必须填写取消原因。")
        values.update(remaining_days=0, remaining_days_source="none")
    return ProgressEntry.model_validate(values)


def _progress_changes(old_entries: list[ProgressEntry], new_entries: list[ProgressEntry]) -> list[dict[str, Any]]:
    old_by_id = {item.task_id: item.model_dump(mode="json") for item in old_entries}
    new_by_id = {item.task_id: item.model_dump(mode="json") for item in new_entries}
    changes: list[dict[str, Any]] = []
    for task_id in sorted(set(old_by_id) | set(new_by_id)):
        old = old_by_id.get(task_id, {})
        new = new_by_id.get(task_id, {})
        for field in sorted(set(old) | set(new)):
            if old.get(field) != new.get(field):
                changes.append({"task_id": task_id, "field": field, "old_value": old.get(field), "new_value": new.get(field)})
    return changes


def create_forecast(
    request: CreateForecastRequest,
    repository: PlanControlRepository = default_plan_control_repository,
) -> ForecastSchedule:
    plan = repository.get_plan_version(request.plan_version_id)
    snapshot = repository.get_progress_snapshot(request.progress_snapshot_id)
    if snapshot.plan_version_id != plan.plan_version_id or not snapshot.is_current:
        raise PlanControlConflictError("进度快照不属于当前计划版本或已经不是当前修订。")
    effective_plan = plan
    integrated_snapshot = None
    girder_config = plan.scenario_snapshot.girder_planning
    if plan.scenario_version_id and girder_config and girder_config.enabled:
        scenario_version = repository.get_planning_scenario_version(plan.scenario_version_id)
        if scenario_version.scenario_id != plan.source_scenario_id:
            raise PlanControlValidationError("计划引用的架梁方案版本与计划来源场景不一致。")
        if scenario_version.status != "specialty_confirmed":
            raise PlanControlValidationError("架梁专项必须先完成专业确认，才能进行实绩滚动联算。")
        integrated_snapshot = solve_integrated_schedule(
            CreateIntegratedScheduleRequest(
                scenario_version_id=scenario_version.scenario_version_id,
                progress_snapshot_id=snapshot.progress_snapshot_id,
                expected_input_fingerprint=scenario_version.input_fingerprint,
            ),
            repository,
        )
        if integrated_snapshot.status != "converged":
            raise PlanControlValidationError(
                f"实绩滚动后的联合计算未收敛（{integrated_snapshot.status}），不能生成确定性预测。"
            )
        if integrated_snapshot.generated_snapshot is None or integrated_snapshot.schedule_result is None:
            raise PlanControlValidationError("联合计算未返回可用于滚动预测的统一任务快照。")
        effective_plan = plan.model_copy(
            update={
                "generated_snapshot": integrated_snapshot.generated_snapshot,
                "schedule_result_snapshot": integrated_snapshot.schedule_result,
                "integrated_snapshot_id": integrated_snapshot.integrated_snapshot_id,
                "girder_result_snapshot": integrated_snapshot.girder_result,
            }
        )
    forecast = _solve_forecast(effective_plan, snapshot, "as_is", {})
    if integrated_snapshot is not None:
        forecast = forecast.model_copy(
            update={
                "metrics": {
                    **forecast.metrics,
                    "schedule_source": "integrated",
                    "integrated_snapshot_id": integrated_snapshot.integrated_snapshot_id,
                    "integrated_status": integrated_snapshot.status,
                },
                "diagnostics": [*integrated_snapshot.diagnostics, *forecast.diagnostics],
            }
        )
    return repository.add_forecast(forecast)


def _solve_forecast(
    plan: PlanVersion,
    snapshot: ProgressSnapshot,
    strategy: ForecastStrategy,
    parameters: dict[str, Any],
) -> ForecastSchedule:
    generated = plan.generated_snapshot
    baseline_result = plan.schedule_result_snapshot
    baseline_tasks = {task.id: task for task in baseline_result.tasks}
    entries = {entry.task_id: entry for entry in snapshot.entries}
    residual_tasks = []
    historical: list[ForecastTaskState] = []
    constraints: list[TaskExecutionConstraint] = []
    diagnostics: list[ValidationMessage] = list(snapshot.validation_messages)
    diagnostics_by_task: dict[str, list[str]] = defaultdict(list)
    paused_without_resume: list[str] = []
    cancelled_task_ids: set[str] = set()

    for task in generated.schedule_input.tasks:
        entry = entries.get(task.id) or ProgressEntry(
            task_id=task.id,
            status="not_started",
            remaining_days=task.duration_days,
            remaining_days_source="baseline",
        )
        baseline = baseline_tasks.get(task.id)
        if entry.status in {"completed", "cancelled"}:
            historical.append(
                ForecastTaskState(
                    task_id=task.id,
                    task_name=task.name,
                    state="actual",
                    baseline_start_date=baseline.start_date if baseline else None,
                    baseline_finish_date=baseline.finish_date if baseline else None,
                    actual_start_date=entry.actual_start_date,
                    actual_finish_date=entry.actual_finish_date,
                    assigned_resource_type=baseline.assigned_resource_type if baseline else None,
                    assigned_resource_id=baseline.assigned_resource_id if baseline else None,
                    progress_status=entry.status,
                    execution_state="completed_locked" if entry.status == "completed" else "cancelled_excluded",
                    remaining_days=entry.remaining_days,
                )
            )
            if entry.status == "cancelled":
                cancelled_task_ids.add(task.id)
                message = "取消任务未进入剩余求解，其后续依赖需要人工确认。"
                diagnostics.append(ValidationMessage(level="warning", subject_id=task.id, message=message))
                diagnostics_by_task[task.id].append(message)
            continue
        remaining_days = entry.remaining_days or task.duration_days
        residual_tasks.append(task.model_copy(update={"duration_days": max(1, remaining_days)}))
        if entry.status == "in_progress":
            constraints.append(
                TaskExecutionConstraint(
                    task_id=task.id,
                    fixed_start_offset=0,
                    fixed_resource_id=baseline.assigned_resource_id if baseline else None,
                    source="progress_snapshot",
                )
            )
        elif entry.status == "paused":
            if entry.expected_resume_date:
                constraints.append(
                    TaskExecutionConstraint(
                        task_id=task.id,
                        earliest_start_offset=max(0, (entry.expected_resume_date - snapshot.status_date).days),
                        fixed_resource_id=baseline.assigned_resource_id if baseline else None,
                        source="progress_snapshot",
                    )
                )
            else:
                paused_without_resume.append(task.id)
                message = "暂停任务缺少恢复日期，无法确定剩余工作何时重新开始。"
                diagnostics_by_task[task.id].append(message)

    if cancelled_task_ids:
        for link in generated.schedule_input.precedence_links:
            if link.predecessor_id not in cancelled_task_ids:
                continue
            message = f"前置任务 {link.predecessor_id} 已取消，后续任务 {link.successor_id} 的工艺释放条件需要人工确认。"
            diagnostics.append(ValidationMessage(level="warning", subject_id=link.successor_id, message=message))
            diagnostics_by_task[link.predecessor_id].append(message)
            diagnostics_by_task[link.successor_id].append(message)

    residual_ids = {task.id for task in residual_tasks}
    residual_links = [
        link.model_copy(deep=True)
        for link in generated.schedule_input.precedence_links
        if link.predecessor_id in residual_ids and link.successor_id in residual_ids
    ]
    if strategy == "as_is":
        residual_links.extend(_baseline_resource_order_links(baseline_result.tasks, residual_ids, residual_links))

    resources = [item.model_copy(deep=True) for item in generated.schedule_input.resources]
    if strategy == "add_bottleneck_resources":
        resources = _expanded_resources(resources, residual_tasks, parameters)

    milestones = [item.model_copy(update={"mode": "soft"}) for item in generated.schedule_input.milestones]
    schedule_input = ScheduleInput(
        project_name=generated.schedule_input.project_name,
        start_date=snapshot.status_date,
        tasks=residual_tasks,
        precedence_links=residual_links,
        resources=resources,
        milestones=milestones,
        execution_constraints=constraints,
        schedule_strategy=generated.schedule_input.schedule_strategy,
        time_limit_seconds=generated.schedule_input.time_limit_seconds,
    )
    if not residual_tasks:
        residual_result = ScheduleResult(status="OPTIMAL", objective_days=0, plan_start_date=snapshot.status_date, plan_finish_date=snapshot.status_date)
    elif paused_without_resume:
        residual_result = ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=snapshot.status_date,
            plan_finish_date=None,
            validation=[
                ValidationMessage(
                    level="warning",
                    subject_id=task_id,
                    message="暂停任务缺少恢复日期，未执行确定性剩余计划求解。",
                )
                for task_id in paused_without_resume
            ],
        )
    else:
        residual_result = solve_schedule(schedule_input, enforce_hard_milestones=False)
    combined_result, predicted = _combined_result(plan, snapshot, historical, residual_result)
    predicted_ids = {item.task_id for item in predicted}
    for task in residual_tasks:
        if task.id in predicted_ids:
            continue
        entry = entries.get(task.id) or ProgressEntry(
            task_id=task.id,
            status="not_started",
            remaining_days=task.duration_days,
            remaining_days_source="baseline",
        )
        baseline = baseline_tasks.get(task.id)
        fallback_start = _fallback_prediction_start(entry, snapshot.status_date)
        predicted.append(
            ForecastTaskState(
                task_id=task.id,
                task_name=task.name,
                state="predicted",
                baseline_start_date=baseline.start_date if baseline else None,
                baseline_finish_date=baseline.finish_date if baseline else None,
                actual_start_date=entry.actual_start_date,
                predicted_start_date=fallback_start,
                predicted_finish_date=(fallback_start + timedelta(days=max(1, entry.remaining_days or task.duration_days) - 1) if fallback_start else None),
                assigned_resource_type=baseline.assigned_resource_type if baseline else None,
                assigned_resource_id=baseline.assigned_resource_id if baseline else None,
                progress_status=entry.status,
                execution_state=_execution_state(entry.status),
                remaining_days=entry.remaining_days or task.duration_days,
                related_diagnostics=diagnostics_by_task.get(task.id, []),
            )
        )
    for item in historical:
        item.related_diagnostics = diagnostics_by_task.get(item.task_id, [])
    for item in predicted:
        if not item.related_diagnostics:
            item.related_diagnostics = diagnostics_by_task.get(item.task_id, [])

    execution_summary = _execution_summary(generated.schedule_input.tasks, entries, strategy)
    critical_nodes = _forecast_critical_nodes(plan, snapshot, combined_result, entries)
    risk_status, evidence, confidence, metrics = _forecast_risk(
        plan,
        snapshot,
        combined_result,
        diagnostics,
        critical_nodes,
    )
    status = "feasible" if residual_result.status in {"OPTIMAL", "FEASIBLE"} else "infeasible"
    if risk_status == "insufficient_data":
        status = "failed" if residual_result.status not in {"OPTIMAL", "FEASIBLE"} else "feasible"
    created_at = _now()
    input_fingerprint = _stable_id(
        "forecast-input",
        {"plan": plan.input_fingerprint, "snapshot": snapshot.model_dump(mode="json"), "strategy": strategy, "parameters": parameters},
    )
    return ForecastSchedule(
        forecast_id=_stable_id("forecast", {"input": input_fingerprint, "at": created_at}),
        plan_version_id=plan.plan_version_id,
        progress_snapshot_id=snapshot.progress_snapshot_id,
        status_date=snapshot.status_date,
        strategy=strategy,
        status=status,
        input_fingerprint=input_fingerprint,
        historical_tasks=historical,
        predicted_tasks=predicted,
        schedule_result=combined_result,
        execution_summary=execution_summary,
        critical_nodes=critical_nodes,
        risk_status=risk_status,
        risk_evidence=evidence,
        confidence=confidence,
        metrics=metrics,
        diagnostics=diagnostics + list(residual_result.validation),
        created_at=created_at,
    )


def _fallback_prediction_start(entry: ProgressEntry, status_date: date) -> date | None:
    if entry.status == "in_progress":
        return max(status_date, entry.actual_start_date or status_date)
    if entry.status == "paused" and entry.expected_resume_date:
        return max(status_date, entry.expected_resume_date)
    return None


def _baseline_resource_order_links(
    baseline_tasks: list[ScheduledTask],
    residual_ids: set[str],
    existing: list[PrecedenceLink],
) -> list[PrecedenceLink]:
    by_resource: dict[str, list[ScheduledTask]] = defaultdict(list)
    for task in baseline_tasks:
        if task.id in residual_ids and task.assigned_resource_id:
            by_resource[task.assigned_resource_id].append(task)
    existing_pairs = {(item.predecessor_id, item.successor_id) for item in existing}
    links: list[PrecedenceLink] = []
    for resource_id, tasks in by_resource.items():
        ordered = sorted(tasks, key=lambda item: (item.start_offset, item.sequence_order, item.id))
        for left, right in zip(ordered, ordered[1:]):
            if (left.id, right.id) in existing_pairs:
                continue
            links.append(
                PrecedenceLink(
                    id=f"forecast-order:{resource_id}:{left.id}:{right.id}",
                    predecessor_id=left.id,
                    successor_id=right.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="forecast-baseline-resource-order",
                    severity="error",
                )
            )
    return links


def _execution_state(status: str) -> str:
    return {
        "completed": "completed_locked",
        "cancelled": "cancelled_excluded",
        "in_progress": "in_progress_remaining",
        "paused": "paused_remaining",
        "not_started": "not_started_future",
    }[status]


def _execution_summary(tasks, entries: dict[str, ProgressEntry], strategy: ForecastStrategy) -> ForecastExecutionSummary:
    counts = defaultdict(int)
    for task in tasks:
        status = entries.get(task.id).status if entries.get(task.id) else "not_started"
        counts[_execution_state(status)] += 1
    return ForecastExecutionSummary(
        completed_locked_count=counts["completed_locked"],
        cancelled_excluded_count=counts["cancelled_excluded"],
        in_progress_remaining_count=counts["in_progress_remaining"],
        paused_remaining_count=counts["paused_remaining"],
        not_started_future_count=counts["not_started_future"],
        resource_policy="bottleneck_expanded" if strategy == "add_bottleneck_resources" else "baseline_fixed",
        sequence_policy="critical_priority" if strategy == "prioritize_critical_tasks" else "baseline_order",
    )


def _expanded_resources(resources: list[Resource], tasks, parameters: dict[str, Any]) -> list[Resource]:
    increments = {key: max(0, int(value)) for key, value in (parameters.get("max_resource_increments") or {}).items()}
    result = list(resources)
    template_by_type = {resource.type: resource for resource in resources if resource.enabled}
    for resource_type, count in increments.items():
        template = template_by_type.get(resource_type)
        if template is None:
            continue
        for index in range(min(count, 20)):
            result.append(template.model_copy(update={"id": f"{template.id}-forecast-extra-{index + 1}", "name": f"{template.name}（增配{index + 1}）"}))
    return result


def _combined_result(
    plan: PlanVersion,
    snapshot: ProgressSnapshot,
    historical: list[ForecastTaskState],
    residual_result: ScheduleResult,
) -> tuple[ScheduleResult, list[ForecastTaskState]]:
    baseline_by_id = {task.id: task for task in plan.schedule_result_snapshot.tasks}
    entry_by_id = {entry.task_id: entry for entry in snapshot.entries}
    actual_tasks: list[ScheduledTask] = []
    for state in historical:
        baseline = baseline_by_id.get(state.task_id)
        entry = entry_by_id.get(state.task_id)
        if baseline is None or entry is None or entry.status != "completed" or not entry.actual_start_date or not entry.actual_finish_date:
            continue
        start_offset = max(0, (entry.actual_start_date - plan.schedule_result_snapshot.plan_start_date).days)
        end_offset = max(start_offset + 1, (entry.actual_finish_date - plan.schedule_result_snapshot.plan_start_date).days + 1)
        actual_tasks.append(
            baseline.model_copy(
                update={
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "start_date": entry.actual_start_date,
                    "finish_date": entry.actual_finish_date,
                }
            )
        )
    predicted: list[ForecastTaskState] = []
    for task in residual_result.tasks:
        baseline = baseline_by_id.get(task.id)
        entry = entry_by_id.get(task.id)
        predicted.append(
            ForecastTaskState(
                task_id=task.id,
                task_name=task.name,
                state="predicted",
                baseline_start_date=baseline.start_date if baseline else None,
                baseline_finish_date=baseline.finish_date if baseline else None,
                actual_start_date=entry.actual_start_date if entry else None,
                predicted_start_date=task.start_date,
                predicted_finish_date=task.finish_date,
                assigned_resource_type=task.assigned_resource_type,
                assigned_resource_id=task.assigned_resource_id,
                progress_status=entry.status if entry else "not_started",
                execution_state=_execution_state(entry.status if entry else "not_started"),
                remaining_days=entry.remaining_days if entry else task.duration_days,
                variance_days=(task.finish_date - baseline.finish_date).days if baseline else None,
            )
        )
    all_tasks = [*actual_tasks, *residual_result.tasks]
    finish = max((task.finish_date for task in all_tasks), default=snapshot.status_date)
    plan_start = plan.schedule_result_snapshot.plan_start_date
    combined = residual_result.model_copy(
        update={
            "plan_start_date": plan_start,
            "plan_finish_date": finish,
            "objective_days": max(0, (finish - plan_start).days + 1),
            "tasks": all_tasks,
            "milestone_results": evaluate_milestones_from_scheduled_tasks(
                plan.generated_snapshot.schedule_input,
                all_tasks,
            ),
        }
    )
    return combined, predicted


def _critical_node_status(target_date: date, evaluated_date: date | None) -> tuple[str, int | None, int | None]:
    if evaluated_date is None:
        return "insufficient_data", None, None
    variance_days = (evaluated_date - target_date).days
    buffer_days = -variance_days
    if variance_days > 0:
        return "late", variance_days, buffer_days
    if buffer_days <= 3:
        return "at_risk", variance_days, buffer_days
    return "on_track", variance_days, buffer_days


def _critical_node_date_source(task_ids: list[str], entries: dict[str, ProgressEntry]) -> str:
    statuses = [entries.get(task_id).status if entries.get(task_id) else "not_started" for task_id in task_ids]
    if not statuses or any(status == "cancelled" for status in statuses):
        return "unavailable"
    completed_count = sum(status == "completed" for status in statuses)
    if completed_count == len(statuses):
        return "actual"
    if completed_count > 0:
        return "combined"
    return "predicted"


def _node_evidence(
    *,
    node_name: str,
    target_event: str,
    task_ids: list[str],
    scheduled_by_id: dict[str, ScheduledTask],
    evaluated_date: date | None,
    result: ScheduleResult,
) -> list[CriticalNodeEvidence]:
    if evaluated_date is None:
        message = "剩余任务未获得可用排程，无法计算节点日期。" if result.status not in {"OPTIMAL", "FEASIBLE"} else "节点范围任务不完整，无法计算节点日期。"
        return [CriticalNodeEvidence(type="solver", message=message, task_ids=task_ids)]
    scoped = [scheduled_by_id[task_id] for task_id in task_ids if task_id in scheduled_by_id]
    if not scoped:
        return [CriticalNodeEvidence(type="data_quality", message="节点没有可用于评估的任务。", task_ids=task_ids)]
    if target_event == "start":
        driving_date = min(task.start_date for task in scoped)
        driving = [task for task in scoped if task.start_date == driving_date]
    else:
        driving_date = max(task.finish_date for task in scoped)
        driving = [task for task in scoped if task.finish_date == driving_date]
    task_names = "、".join(task.name for task in driving[:3])
    resource_types = sorted({task.assigned_resource_type for task in driving if task.assigned_resource_type})
    return [
        CriticalNodeEvidence(
            type="driving_task",
            message=f"{task_names} 决定“{node_name}”的当前节点日期。",
            task_ids=[task.id for task in driving],
            resource_types=resource_types,
            variance_days=None,
        )
    ]


def _forecast_critical_nodes(
    plan: PlanVersion,
    snapshot: ProgressSnapshot,
    result: ScheduleResult,
    entries: dict[str, ProgressEntry],
) -> list[CriticalNodeForecast]:
    schedule_input = plan.generated_snapshot.schedule_input
    scheduled_by_id = {task.id: task for task in result.tasks}
    feasible = result.status in {"OPTIMAL", "FEASIBLE"}
    nodes: list[CriticalNodeForecast] = []

    project_task_ids = [task.id for task in schedule_input.tasks]
    project_source = _critical_node_date_source(project_task_ids, entries)
    project_target = plan.schedule_result_snapshot.plan_finish_date or plan.schedule_result_snapshot.plan_start_date
    project_evaluated = result.plan_finish_date if feasible and project_source != "unavailable" else None
    project_status, project_variance, project_buffer = _critical_node_status(project_target, project_evaluated)
    nodes.append(
        CriticalNodeForecast(
            node_id="project-finish",
            name="项目计划完工",
            node_type="project_finish",
            level="contract",
            mode="hard",
            target_date=project_target,
            evaluated_date=project_evaluated,
            date_source=project_source if project_evaluated else "unavailable",
            variance_days=project_variance,
            buffer_days=project_buffer,
            status=project_status,
            related_task_ids=project_task_ids,
            evidence=_node_evidence(
                node_name="项目计划完工",
                target_event="finish",
                task_ids=project_task_ids,
                scheduled_by_id=scheduled_by_id,
                evaluated_date=project_evaluated,
                result=result,
            ),
        )
    )

    milestone_results = {item.id: item for item in result.milestone_results}
    for milestone in schedule_input.milestones:
        task_ids = task_ids_for_milestone(milestone, schedule_input.tasks)
        source = _critical_node_date_source(task_ids, entries)
        milestone_result = milestone_results.get(milestone.id)
        evaluated = (
            milestone_result.actual_date
            if feasible and source != "unavailable" and milestone_result and milestone_result.status != "not_evaluated"
            else None
        )
        node_status, variance_days, buffer_days = _critical_node_status(milestone.target_date, evaluated)
        nodes.append(
            CriticalNodeForecast(
                node_id=milestone.id,
                name=milestone.name,
                node_type="milestone",
                level=milestone.level,
                mode=milestone.mode,
                target_date=milestone.target_date,
                evaluated_date=evaluated,
                date_source=source if evaluated else "unavailable",
                variance_days=variance_days,
                buffer_days=buffer_days,
                status=node_status,
                related_task_ids=task_ids,
                evidence=_node_evidence(
                    node_name=milestone.name,
                    target_event=milestone.target_event,
                    task_ids=task_ids,
                    scheduled_by_id=scheduled_by_id,
                    evaluated_date=evaluated,
                    result=result,
                ),
            )
        )
    status_order = {"late": 0, "at_risk": 1, "insufficient_data": 2, "on_track": 3}
    return sorted(
        nodes,
        key=lambda item: (
            status_order[item.status],
            0 if item.mode == "hard" else 1,
            item.target_date,
            item.node_id,
        ),
    )


def _forecast_risk(
    plan: PlanVersion,
    snapshot: ProgressSnapshot,
    result: ScheduleResult,
    diagnostics: list[ValidationMessage],
    critical_nodes: list[CriticalNodeForecast],
) -> tuple[str, list[dict[str, Any]], str, dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    baseline_finish = plan.schedule_result_snapshot.plan_finish_date
    predicted_finish = result.plan_finish_date
    finish_variance = (predicted_finish - baseline_finish).days if baseline_finish and predicted_finish else None
    if finish_variance and finish_variance > 0:
        evidence.append({"type": "project_finish", "message": f"项目预测完成日期较基准晚 {finish_variance} 天。", "variance_days": finish_variance})
    primary_nodes = [item for item in critical_nodes if item.node_type == "project_finish" or item.mode == "hard"]
    milestone_late = [item for item in primary_nodes if item.node_type == "milestone" and item.status == "late"]
    for item in milestone_late:
        evidence.append({"type": "milestone", "milestone_id": item.node_id, "message": f"{item.name} 预测迟延 {item.variance_days} 天。"})
    if result.status not in {"OPTIMAL", "FEASIBLE"}:
        risk = "insufficient_data"
        evidence.append({"type": "solver", "message": "剩余任务未得到可行预测。"})
    elif any(item.status == "insufficient_data" for item in primary_nodes):
        risk = "insufficient_data"
        evidence.append({"type": "data_quality", "message": "至少一个关键节点缺少可判断日期。"})
    elif any(item.status == "late" for item in primary_nodes):
        risk = "late"
    elif any(item.status == "at_risk" for item in primary_nodes):
        risk = "at_risk"
        evidence.append({"type": "buffer", "message": "至少一个关键节点剩余缓冲不超过 3 天。"})
    else:
        risk = "on_track"
        evidence.append({"type": "project_finish", "message": "当前预测未超过基准完成日期。"})
    confidence = "high" if snapshot.data_quality_status == "valid" and not diagnostics else "medium"
    if risk == "insufficient_data":
        confidence = "low"
    metrics = {
        "baseline_finish_date": baseline_finish,
        "predicted_finish_date": predicted_finish,
        "finish_variance_days": finish_variance,
        "late_milestone_count": len(milestone_late),
        "resource_count": len({item.resource_id for item in result.resource_allocations}),
    }
    control_analysis = result.stats.get("control_priority_analysis", {})
    continuity = result.stats.get("continuity_metrics", {})
    metrics.update(
        critical_path_candidates=list(control_analysis.get("control_task_ids", []))[:20],
        bottleneck_resources=list(control_analysis.get("bottleneck_resources", []))[:10],
        resource_increment_suggestions=list(control_analysis.get("resource_increment_suggestions", []))[:10],
        transfer_impact={
            "jump_pier_count": continuity.get("jump_pier_count", 0),
            "side_switch_count": continuity.get("side_switch_count", 0),
            "path_group_switch_count": continuity.get("path_group_switch_count", 0),
        },
        waiting_impact=control_analysis.get("resource_idle_status", {}),
        data_quality_status=snapshot.data_quality_status,
    )
    return risk, evidence, confidence, metrics


def create_adjustment_proposals(
    forecast_id: str,
    max_resource_increments: dict[str, int],
    repository: PlanControlRepository = default_plan_control_repository,
) -> AdjustmentComparisonResponse:
    base = repository.get_forecast(forecast_id)
    if base.status == "stale":
        raise PlanControlConflictError("预测已经过期，请重新生成。")
    plan = repository.get_plan_version(base.plan_version_id)
    snapshot = repository.get_progress_snapshot(base.progress_snapshot_id)
    bottleneck_types = _bottleneck_resource_types(plan, snapshot)
    effective_increments = {
        resource_type: min(20, max(0, int(count)))
        for resource_type, count in max_resource_increments.items()
        if resource_type in bottleneck_types and int(count) > 0
    }
    strategies: tuple[ForecastStrategy, ...] = ("as_is", "add_bottleneck_resources", "prioritize_critical_tasks")
    proposals: list[AdjustmentProposal] = []
    for strategy in strategies:
        parameters = {"max_resource_increments": effective_increments} if strategy == "add_bottleneck_resources" else {}
        try:
            solved = base if strategy == "as_is" else _solve_forecast(plan, snapshot, strategy, parameters)
        except Exception as exc:  # 每个策略必须独立失败，不能阻断其余策略
            solved = _failed_strategy_forecast(plan, snapshot, strategy, parameters, exc)
        metrics = dict(solved.metrics)
        added_count = sum(effective_increments.values()) if strategy == "add_bottleneck_resources" else 0
        predicted_finish = _metric_date(solved.metrics.get("predicted_finish_date"))
        base_finish = _metric_date(base.metrics.get("predicted_finish_date"))
        finish_improvement = (
            (base_finish - predicted_finish).days
            if isinstance(base_finish, date) and isinstance(predicted_finish, date)
            else 0
        )
        demo_cost_change = sum(
            pool.incremental_unit_cost * effective_increments.get(pool.type, 0)
            for pool in plan.resource_plan_snapshot.resource_pools
        ) if strategy == "add_bottleneck_resources" else 0
        metrics.update(
            resource_increments=effective_increments if strategy == "add_bottleneck_resources" else {},
            added_resource_count=added_count,
            demo_cost_change=demo_cost_change,
            finish_improvement_days=finish_improvement,
        )
        proposal = AdjustmentProposal(
            proposal_id=_stable_id("proposal", {"forecast": forecast_id, "strategy": strategy, "input": solved.input_fingerprint}),
            forecast_id=forecast_id,
            plan_version_id=plan.plan_version_id,
            strategy=strategy,
            status=solved.status,
            strategy_parameters=parameters,
            forecast=solved,
            metrics=metrics,
            explanation=_local_adjustment_explanation(strategy, solved, metrics),
            diagnostics=solved.diagnostics,
            created_at=_now(),
        )
        proposals.append(proposal)
    recommended = _recommended_proposal(proposals)
    proposals = [
        item.model_copy(
            update={
                "recommended": item.proposal_id == recommended,
                "recommendation_reason": "优先满足里程碑和完工目标；收益相近时选择资源与扰动更小的方案。" if item.proposal_id == recommended else "",
            }
        )
        for item in proposals
    ]
    repository.add_proposals(proposals)
    return AdjustmentComparisonResponse(forecast_id=forecast_id, proposals=proposals, recommended_proposal_id=recommended)


def _metric_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _bottleneck_resource_types(plan: PlanVersion, snapshot: ProgressSnapshot) -> set[str]:
    entries = {item.task_id: item for item in snapshot.entries}
    workload: dict[str, int] = defaultdict(int)
    for task in plan.generated_snapshot.schedule_input.tasks:
        entry = entries.get(task.id)
        if entry and entry.status in {"completed", "cancelled"}:
            continue
        duration = entry.remaining_days if entry and entry.remaining_days > 0 else task.duration_days
        for resource_type in task.compatible_resource_types:
            workload[resource_type] += duration
    if not workload:
        return set()
    peak = max(workload.values())
    return {resource_type for resource_type, value in workload.items() if value == peak}


def _failed_strategy_forecast(
    plan: PlanVersion,
    snapshot: ProgressSnapshot,
    strategy: ForecastStrategy,
    parameters: dict[str, Any],
    exc: Exception,
) -> ForecastSchedule:
    created_at = _now()
    fingerprint = _stable_id(
        "forecast-input",
        {"plan": plan.input_fingerprint, "snapshot": snapshot.progress_snapshot_id, "strategy": strategy, "parameters": parameters},
    )
    message = ValidationMessage(level="error", message=f"{strategy} 策略求解失败：{exc}")
    return ForecastSchedule(
        forecast_id=_stable_id("forecast", {"input": fingerprint, "at": created_at}),
        plan_version_id=plan.plan_version_id,
        progress_snapshot_id=snapshot.progress_snapshot_id,
        status_date=snapshot.status_date,
        strategy=strategy,
        status="failed",
        input_fingerprint=fingerprint,
        risk_status="insufficient_data",
        risk_evidence=[{"type": "solver", "message": message.message}],
        confidence="low",
        diagnostics=[message],
        created_at=created_at,
    )


def _recommended_proposal(proposals: list[AdjustmentProposal]) -> str | None:
    feasible = [item for item in proposals if item.status == "feasible" and item.forecast.schedule_result]
    if not feasible:
        return None
    ranked = sorted(
        feasible,
        key=lambda item: (
            1 if item.forecast.risk_status == "late" else 0,
            item.forecast.metrics.get("late_milestone_count", 0),
            str(item.forecast.metrics.get("predicted_finish_date") or "9999-12-31"),
            int(item.metrics.get("added_resource_count", 0) or 0),
            0 if item.strategy == "as_is" else 1,
        ),
    )
    return ranked[0].proposal_id


def _local_adjustment_explanation(
    strategy: ForecastStrategy,
    forecast: ForecastSchedule,
    metrics: dict[str, Any],
) -> str:
    labels = {
        "as_is": "保持现有资源和未来执行顺序",
        "add_bottleneck_resources": "增加当前诊断识别的瓶颈资源",
        "prioritize_critical_tasks": "保持资源数量并优先安排关键任务",
    }
    suffix = ""
    if strategy == "add_bottleneck_resources" and metrics.get("finish_improvement_days", 0) <= 0:
        suffix = " 当前资源增配未带来完工日期改善，边际收益不足。"
    return f"{labels[strategy]}；预测状态为 {forecast.risk_status}，预计完成日期为 {forecast.metrics.get('predicted_finish_date') or '不可用'}。{suffix}"


def adopt_adjustment(
    proposal_id: str,
    request: AdoptAdjustmentRequest,
    repository: PlanControlRepository = default_plan_control_repository,
) -> AdoptAdjustmentResponse:
    proposal = repository.get_proposal(proposal_id)
    source = repository.get_plan_version(proposal.plan_version_id)
    if not request.adoption_reason.strip() or not request.confirmed_by.strip():
        raise PlanControlValidationError("采用原因和确认人不能为空。")
    if proposal.forecast.schedule_result is None:
        raise PlanControlValidationError("调整方案没有可采用的排程结果。")
    version_no = repository.next_version_no(source.project_id)
    confirmed_at = _now()
    result = proposal.forecast.schedule_result
    generated_snapshot = source.generated_snapshot.model_copy(deep=True)
    resource_plan_snapshot = source.resource_plan_snapshot.model_copy(deep=True)
    if proposal.strategy == "add_bottleneck_resources":
        increments = proposal.strategy_parameters.get("max_resource_increments") or {}
        generated_snapshot.schedule_input.resources = _expanded_resources(
            generated_snapshot.schedule_input.resources,
            generated_snapshot.schedule_input.tasks,
            proposal.strategy_parameters,
        )
        resource_plan_snapshot.resource_pools = [
            pool.model_copy(
                update={
                    "quantity": (pool.quantity or 0) + int(increments.get(pool.type, 0)),
                    "max_quantity": max(
                        pool.max_quantity or pool.quantity or 0,
                        (pool.quantity or 0) + int(increments.get(pool.type, 0)),
                    ),
                }
            )
            for pool in resource_plan_snapshot.resource_pools
        ]
    new_version = PlanVersion(
        plan_version_id=_stable_id("plan", {"project": source.project_id, "version": version_no, "proposal": proposal_id}),
        project_id=source.project_id,
        project_name=source.project_name,
        version_no=version_no,
        version_kind="execution",
        status="active",
        parent_version_id=source.plan_version_id,
        source_scenario_id=f"{source.source_scenario_id}-{proposal.strategy}",
        scenario_snapshot=source.scenario_snapshot.model_copy(deep=True),
        generated_snapshot=generated_snapshot,
        schedule_result_snapshot=result.model_copy(deep=True),
        resource_plan_snapshot=resource_plan_snapshot,
        input_fingerprint=_stable_id("plan-input", {"source": source.input_fingerprint, "proposal": proposal.model_dump(mode="json")}),
        confirmed_by=request.confirmed_by.strip(),
        confirmed_at=confirmed_at,
        confirmation_reason=request.adoption_reason.strip(),
    )
    change = PlanChangeRecord(
        change_id=_stable_id("change", {"proposal": proposal_id, "new": new_version.plan_version_id}),
        source_plan_version_id=source.plan_version_id,
        source_forecast_id=proposal.forecast_id,
        proposal_id=proposal_id,
        new_plan_version_id=new_version.plan_version_id,
        adoption_reason=request.adoption_reason.strip(),
        confirmed_by=request.confirmed_by.strip(),
        confirmed_at=confirmed_at,
    )
    saved, previous = repository.adopt(
        proposal_id=proposal_id,
        expected_plan_fingerprint=request.source_plan_fingerprint,
        new_version=new_version,
        change_record=change,
    )
    return AdoptAdjustmentResponse(new_plan_version=saved, previous_plan_version=previous, change_record=change)
