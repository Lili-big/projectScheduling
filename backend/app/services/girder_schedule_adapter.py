from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..contracts import (
    ErectionMachineConfig,
    ErectionOwnership,
    GeneratedScheduleInput,
    GirderPlanningResult,
    GirderSpanPlan,
    PrecedenceLink,
    ProjectDataVersion,
    Resource,
    ScheduleResult,
    Task,
    TaskExecutionConstraint,
    ValidationMessage,
)
from ..scenario import generate_schedule_input_from_scenario
from ..girder_planning.backward_scheduler import calculate_latest_finish_controls
from ..girder_planning.models import RouteOccurrence
from ..girder_planning.ownership import resolve_ownership
from ..girder_planning.passage_service import calculate_passage_releases
from ..girder_planning.route_simulator import simulate_routes
from ..girder_planning.supply_simulator import SupplyDemand, simulate_supply, erection_duration_days
from ..girder_planning.fingerprints import stable_fingerprint, stable_id


def build_girder_schedule(
    scenario_version,
    project_version: ProjectDataVersion,
    *,
    previous_schedule_result: ScheduleResult | None = None,
    actuals=None,
) -> tuple[GeneratedScheduleInput, GirderPlanningResult]:
    """将架梁专项确定性计算适配为统一排程输入。

    该适配器只生成分跨级任务；梁片数量保留在任务工程量和供梁需求中，
    不拆成单片梁任务。路线节点顺序来自用户配置，日期和唯一架梁归属由
    专项计算派生后再交给通用 CP-SAT 求解器。
    """
    scenario = scenario_version.scenario
    config = scenario_version.girder_planning
    base = generate_schedule_input_from_scenario(scenario)
    diagnostics = list(base.validation)

    occurrences, _ = simulate_routes(project_version, config)
    ownerships, ownership_diagnostics = resolve_ownership(
        occurrences,
        overrides=config.owner_overrides,
        actuals=getattr(actuals, "girder_execution_actuals", None),
    )
    diagnostics.extend(ownership_diagnostics)

    workpoint_by_key = {
        (item.bridge_id, item.side): item
        for item in project_version.workpoints
        if item.bridge_id
    }
    route_by_id = {item.route_id: item for item in config.routes}
    machine_by_id = {item.erection_machine_id: item for item in config.erection_machines}
    upper_by_key: dict[tuple[str, str], list[tuple[object, object]]] = defaultdict(list)
    for bridge in project_version.project.bridges:
        for section in bridge.work_sections:
            if section.side not in {"left", "right"}:
                continue
            for upper in section.upper_structures:
                upper_by_key[(bridge.id, section.side)].append((section, upper))

    demands: list[SupplyDemand] = []
    owner_route_by_key: dict[tuple[str, str], object] = {}
    for ownership in ownerships:
        route = route_by_id.get(ownership.owner_route_id)
        if route is None:
            diagnostics.append(_message("error", "GIRDER_OWNER_ROUTE_MISSING", "架梁归属路线不存在。", ownership.owner_route_id))
            continue
        owner_route_by_key[(ownership.bridge_id, ownership.side)] = route
        for section, upper in upper_by_key.get((ownership.bridge_id, ownership.side), []):
            beam_count = int(upper.beam_count_per_span or 1)
            beam_type = str(upper.properties.get("beam_type") or upper.structure_type or "default")
            demands.append(
                SupplyDemand(
                    demand_id=f"beam-erection:{ownership.bridge_id}:{ownership.side}:{upper.id}",
                    beam_yard_id=route.beam_yard_id,
                    beam_type=beam_type,
                    quantity=beam_count,
                    required_date=ownership.arrival_date,
                )
            )

    allocations, inventory_points, supply_diagnostics = simulate_supply(
        config.beam_yards,
        demands,
        actuals=getattr(actuals, "yard_inventory_actuals", None),
    )
    diagnostics.extend(supply_diagnostics)
    allocation_by_id = {item.demand_id: item for item in allocations}

    span_plans: list[GirderSpanPlan] = []
    added_tasks: list[Task] = []
    added_links: list[PrecedenceLink] = []
    execution_constraints: list[TaskExecutionConstraint] = list(base.schedule_input.execution_constraints)
    machine_resources: list[Resource] = []
    existing_resource_ids = {item.id for item in base.schedule_input.resources}
    existing_task_ids = {item.id for item in base.schedule_input.tasks}
    lower_tasks_by_section: dict[str, list[Task]] = defaultdict(list)
    for task in base.schedule_input.tasks:
        if task.work_section_id and task.component_type != "beam_erection":
            lower_tasks_by_section[task.work_section_id].append(task)

    for machine in config.erection_machines:
        if not machine.enabled or machine.erection_machine_id in existing_resource_ids:
            continue
        machine_resources.append(
            Resource(
                id=machine.erection_machine_id,
                name=machine.name,
                type="girder_erection_machine",
                pool_id=machine.beam_yard_id,
                pool_label=machine.beam_yard_id,
                calendar_id=machine.calendar_id,
            )
        )

    for ownership in ownerships:
        route = owner_route_by_key.get((ownership.bridge_id, ownership.side))
        if route is None:
            continue
        machine = machine_by_id.get(route.erection_machine_id)
        if machine is None or not machine.enabled:
            diagnostics.append(_message("error", "GIRDER_MACHINE_MISSING", "架梁归属路线没有可用架桥机。", route.route_id))
            continue
        for section, upper in upper_by_key.get((ownership.bridge_id, ownership.side), []):
            task_id = f"beam-erection:{ownership.bridge_id}:{ownership.side}:{upper.id}"
            if task_id in existing_task_ids:
                continue
            beam_count = int(upper.beam_count_per_span or 1)
            beam_type = str(upper.properties.get("beam_type") or upper.structure_type or "default")
            demand_id = f"beam-erection:{ownership.bridge_id}:{ownership.side}:{upper.id}"
            allocation = allocation_by_id.get(demand_id)
            supply_date = allocation.available_date if allocation and allocation.available_date else ownership.arrival_date
            earliest = max(scenario.project.start_date, ownership.arrival_date, supply_date, machine.available_date)
            duration = erection_duration_days(beam_count, machine.daily_erection_capacity)
            planned_start, planned_finish = _scheduled_dates(previous_schedule_result, task_id, earliest, duration)
            span_plans.append(
                GirderSpanPlan(
                    task_id=task_id,
                    bridge_id=ownership.bridge_id,
                    work_section_id=section.id,
                    span_id=upper.id,
                    route_id=route.route_id,
                    beam_yard_id=route.beam_yard_id,
                    erection_machine_id=machine.erection_machine_id,
                    beam_type=beam_type,
                    beam_count=beam_count,
                    earliest_start_date=earliest,
                    planned_start_date=planned_start,
                    planned_finish_date=planned_finish,
                    inventory_before=allocation.inventory_before if allocation else None,
                    inventory_after=allocation.inventory_after if allocation else None,
                )
            )
            added_tasks.append(
                Task(
                    id=task_id,
                    name=f"{section.name}第{upper.span_index}跨架梁",
                    bridge_id=ownership.bridge_id,
                    work_section_id=section.id,
                    component_id=upper.id,
                    sequence_order=90000 + upper.span_index,
                    structure_id=f"{ownership.bridge_id}-{ownership.side}-SPAN-{upper.span_index:02d}-ERECTION",
                    structure_name=f"{section.name}第{upper.span_index}跨架梁",
                    structure_type="upper_structure",
                    control_level=upper.control_level or "normal",
                    component_type="beam_erection",
                    process_name="简支梁架设",
                    productivity_rule_id="girder-erection-daily-capacity",
                    quantity=beam_count,
                    quantity_label=f"{beam_count}片",
                    duration_days=duration,
                    compatible_resource_types=["girder_erection_machine"],
                    properties={
                        "upper_structure_id": upper.id,
                        "bridge_id": ownership.bridge_id,
                        "side": ownership.side,
                        "route_id": route.route_id,
                        "beam_yard_id": route.beam_yard_id,
                        "beam_type": beam_type,
                    },
                )
            )
            execution_constraints.append(
                TaskExecutionConstraint(
                    task_id=task_id,
                    earliest_start_offset=(earliest - scenario.project.start_date).days,
                    fixed_resource_id=machine.erection_machine_id,
                    source="girder_planning",
                )
            )
            for predecessor in sorted(lower_tasks_by_section.get(section.id, []), key=lambda item: (item.sequence_order, item.id)):
                added_links.append(
                    PrecedenceLink(
                        id=f"GIRDER-LINK-{predecessor.id}-{task_id}",
                        predecessor_id=predecessor.id,
                        successor_id=task_id,
                        relationship="FS",
                        lag_days=0,
                        source_rule_id="girder_after_substructure",
                        severity="error",
                    )
                )

    all_tasks = [*base.schedule_input.tasks, *added_tasks]
    all_links = [*base.schedule_input.precedence_links, *added_links]
    schedule_input = base.schedule_input.model_copy(
        update={
            "tasks": all_tasks,
            "precedence_links": all_links,
            "resources": [*base.schedule_input.resources, *machine_resources],
            "execution_constraints": execution_constraints,
        }
    )
    if added_tasks:
        diagnostics = [item for item in diagnostics if item.message != "未生成任何启用的工作项。"]
    generated = base.model_copy(
        update={
            "schedule_input": schedule_input,
            "validation": diagnostics,
            "source_summary": {
                **base.source_summary,
                "girder_span_task_count": len(added_tasks),
                "girder_ownership_count": len(ownerships),
            },
        }
    )

    owner_finish_by_workpoint = {
        item.workpoint_id: max(
            (plan.planned_finish_date for plan in span_plans if plan.bridge_id == item.bridge_id and plan.work_section_id == item.work_section_id and plan.planned_finish_date),
            default=None,
        )
        for item in project_version.workpoints
        if item.bridge_id
    }
    passages, passage_diagnostics = calculate_passage_releases(
        project_version,
        ownerships,
        span_plans,
        post_erection_buffer_days=config.parameters.post_erection_passage_buffer_days,
        generated=generated,
        schedule_result=previous_schedule_result,
        actuals=getattr(actuals, "passage_actuals", None),
    )
    diagnostics.extend(passage_diagnostics)
    _, route_runs = simulate_routes(
        project_version,
        config,
        ownerships=ownerships,
        passage_releases=passages,
        owner_finish_by_workpoint=owner_finish_by_workpoint,
    )
    latest_controls, backward_diagnostics = calculate_latest_finish_controls(project_version, route_runs, passages)
    diagnostics.extend(backward_diagnostics)
    result = GirderPlanningResult(
        result_id=stable_id("girder-result", {"scenario": scenario_version.input_fingerprint, "schedule": _schedule_fingerprint(previous_schedule_result)}),
        status="blocked" if any(item.level == "error" for item in diagnostics) else "ready",
        ownerships=ownerships,
        span_plans=span_plans,
        passage_releases=passages,
        yard_inventory_series=inventory_points,
        route_runs=route_runs,
        latest_finish_controls=latest_controls,
        diagnostics=diagnostics,
        input_fingerprint=stable_fingerprint({"scenario": scenario_version.input_fingerprint, "result": span_plans, "passages": passages}, prefix="girder-result"),
    )
    return generated, result


def apply_schedule_dates(result: GirderPlanningResult, schedule_result: ScheduleResult) -> GirderPlanningResult:
    scheduled = {item.id: item for item in schedule_result.tasks}
    plans = [
        plan.model_copy(
            update={
                "planned_start_date": scheduled[plan.task_id].start_date if plan.task_id in scheduled else plan.planned_start_date,
                "planned_finish_date": scheduled[plan.task_id].finish_date if plan.task_id in scheduled else plan.planned_finish_date,
            }
        )
        for plan in result.span_plans
    ]
    return result.model_copy(update={"span_plans": plans})


def _scheduled_dates(schedule_result: ScheduleResult | None, task_id: str, earliest: date, duration: int) -> tuple[date, date]:
    if schedule_result:
        task = next((item for item in schedule_result.tasks if item.id == task_id), None)
        if task:
            return task.start_date, task.finish_date
    return earliest, earliest.fromordinal(earliest.toordinal() + duration - 1)


def _schedule_fingerprint(schedule_result: ScheduleResult | None) -> str | None:
    if schedule_result is None:
        return None
    return stable_fingerprint(
        [(item.id, item.start_date, item.finish_date, item.assigned_resource_id) for item in schedule_result.tasks],
        prefix="schedule-state",
    )


def _message(level: str, code: str, message: str, *refs: str) -> ValidationMessage:
    return ValidationMessage(level=level, code=code, message=message, subject_id=refs[0] if refs else None, entity_refs=list(refs))
