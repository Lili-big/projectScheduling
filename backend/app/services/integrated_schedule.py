from __future__ import annotations

from datetime import datetime, timezone

from ..contracts import (
    CreateIntegratedScheduleRequest,
    IntegratedCalculationSnapshot,
    IntegratedIterationRecord,
    PlanningScenarioVersion,
    ProjectDataVersion,
    ScheduleResult,
    ValidationMessage,
)
from ..solver import solve_schedule
from ..girder_planning.fingerprints import stable_fingerprint, stable_id
from .girder_schedule_adapter import apply_schedule_dates, build_girder_schedule
from .plan_control_repository import PlanControlRepository, PlanControlConflictError


def preview_girder_planning(scenario_version: PlanningScenarioVersion, project_version: ProjectDataVersion):
    _, result = build_girder_schedule(scenario_version, project_version)
    return result


def solve_integrated_schedule(
    request: CreateIntegratedScheduleRequest,
    repository: PlanControlRepository,
) -> IntegratedCalculationSnapshot:
    scenario_version = repository.get_planning_scenario_version(request.scenario_version_id)
    project_version = repository.get_project_data_version(scenario_version.project_data_version_id)
    if scenario_version.input_fingerprint != request.expected_input_fingerprint:
        raise PlanControlConflictError("方案输入已变化，请刷新后重新计算。")
    if scenario_version.status != "specialty_confirmed":
        raise PlanControlConflictError("架梁专项必须先完成专业确认。")
    progress = repository.get_progress_snapshot(request.progress_snapshot_id) if request.progress_snapshot_id else None
    input_fingerprint = stable_fingerprint(
        {
            "project_data_version_id": project_version.project_data_version_id,
            "scenario_version_id": scenario_version.scenario_version_id,
            "scenario_fingerprint": scenario_version.input_fingerprint,
            "progress_snapshot_id": progress.progress_snapshot_id if progress else None,
        },
        prefix="integrated-input",
    )
    if not request.force_recompute:
        existing = repository.find_integrated_snapshot_by_fingerprint(input_fingerprint)
        if existing is not None:
            return existing

    iterations: list[IntegratedIterationRecord] = []
    previous_schedule: ScheduleResult | None = None
    final_generated = None
    final_girder = None
    final_schedule = None
    diagnostics: list[ValidationMessage] = []
    previous_state: str | None = None
    converged = False
    for iteration_no in range(1, scenario_version.girder_planning.parameters.max_iterations + 1):
        generated, girder = build_girder_schedule(
            scenario_version,
            project_version,
            previous_schedule_result=previous_schedule,
            actuals=progress,
        )
        diagnostics.extend(girder.diagnostics)
        if girder.status == "blocked":
            final_generated, final_girder = generated, girder
            break
        schedule_result = solve_schedule(generated.schedule_input)
        girder = apply_schedule_dates(girder, schedule_result)
        state = stable_fingerprint(
            {
                "ownerships": girder.ownerships,
                "span_plans": [(item.task_id, item.planned_start_date, item.planned_finish_date) for item in girder.span_plans],
            },
            prefix="integrated-state",
        )
        iterations.append(
            IntegratedIterationRecord(
                iteration_no=iteration_no,
                input_fingerprint=stable_fingerprint(generated.schedule_input, prefix="iteration-input"),
                ownership_fingerprint=stable_fingerprint(girder.ownerships, prefix="ownership"),
                date_state_fingerprint=state,
                girder_result_id=girder.result_id,
                schedule_status="feasible" if schedule_result.status in {"OPTIMAL", "FEASIBLE"} else "infeasible",
                changed_owner_refs=[] if previous_schedule is None else _changed_refs(final_girder, girder),
                changed_date_refs=[],
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        )
        final_generated, final_girder, final_schedule = generated, girder, schedule_result
        if schedule_result.status not in {"OPTIMAL", "FEASIBLE"}:
            diagnostics.extend(schedule_result.validation)
            break
        if state == previous_state:
            converged = True
            break
        previous_state = state
        previous_schedule = schedule_result

    if final_generated is None or final_girder is None:
        raise PlanControlConflictError("联合计算没有生成可保存的结果。")
    diagnostics.extend(final_schedule.validation if final_schedule else [])
    if final_girder.status == "blocked":
        status = "blocked"
    elif final_schedule and final_schedule.status not in {"OPTIMAL", "FEASIBLE"}:
        status = "infeasible"
    elif converged:
        status = "converged"
    else:
        status = "not_converged"
    snapshot = IntegratedCalculationSnapshot(
        integrated_snapshot_id=stable_id("integrated-snapshot", {"input": input_fingerprint}),
        project_data_version_id=project_version.project_data_version_id,
        scenario_version_id=scenario_version.scenario_version_id,
        progress_snapshot_id=progress.progress_snapshot_id if progress else None,
        status=status,
        iterations=iterations,
        girder_result=final_girder,
        generated_snapshot=final_generated,
        schedule_result=final_schedule,
        input_fingerprint=input_fingerprint,
        diagnostics=_dedupe_diagnostics(diagnostics),
        created_at=datetime.now(timezone.utc),
    )
    return repository.add_integrated_snapshot(snapshot)


def _changed_refs(previous, current) -> list[str]:
    if previous is None:
        return []
    before = {(item.bridge_id, item.side, item.owner_route_id) for item in previous.ownerships}
    after = {(item.bridge_id, item.side, item.owner_route_id) for item in current.ownerships}
    return [f"{bridge_id}:{side}" for bridge_id, side, _ in sorted(before ^ after)]


def _dedupe_diagnostics(items: list[ValidationMessage]) -> list[ValidationMessage]:
    seen: set[tuple[str | None, str]] = set()
    result: list[ValidationMessage] = []
    for item in items:
        key = (item.code, item.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
