from __future__ import annotations

import math
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, get_args

from .models import (
    ComponentType,
    MilestoneConstraint,
    MilestoneResult,
    PrecedenceLink,
    Resource,
    ResourceAllocation,
    ScheduleInput,
    ScheduleResult,
    ScheduledTask,
    Task,
    ValidationMessage,
)

CONTINUITY_PRIMARY_WEIGHT = 1_000_000
SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT = 100_000
SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT = 1
CONTROL_NODE_LATE_WEIGHT = 1_000_000_000
CONTROL_BUFFER_RISK_WEIGHT = 1_000_000
CONTROL_RESOURCE_WAIT_WEIGHT = 1_000_000
RESOURCE_WORKLOAD_BALANCE_WEIGHT = 20_000
RESOURCE_IDLE_WEIGHT = 2_000
RESOURCE_PATH_CONTINUITY_WEIGHT = 500
CONTROL_MAKESPAN_WEIGHT = 100
NORMAL_BALANCE_WEIGHT = 1
CONTROL_NECESSARY_BUFFER_DAYS = 7
CONTROL_BUFFER_NEAR_RISK_DAYS = 3
SCHEDULER_RANDOM_SEED = 0
CONTINUOUS_BEAM_SIDE_CLOSURE_RULE_ID = "continuous_beam_side_closure"
CONTINUOUS_BEAM_MIDDLE_CLOSURE_RULE_ID = "continuous_beam_middle_closure"
CONTINUOUS_BEAM_CLOSURE_RULE_IDS = {
    CONTINUOUS_BEAM_SIDE_CLOSURE_RULE_ID,
    CONTINUOUS_BEAM_MIDDLE_CLOSURE_RULE_ID,
}
DEFAULT_CONTINUOUS_CLOSURE_FINISH_GAP_DAYS = 7


def _default_scheduler_search_workers() -> int:
    return max(1, min(8, os.cpu_count() or 1))


SCHEDULER_SEARCH_WORKERS = _default_scheduler_search_workers()

COMPONENT_TYPE_LABELS: dict[str, str] = {
    "pile": "桩基",
    "cap": "承台",
    "spread_foundation": "扩大基础",
    "ground_tie_beam": "地系梁",
    "middle_tie_beam": "中系梁",
    "pier_body": "墩身",
    "cap_beam": "盖梁",
    "abutment_body": "桥台",
    "precast_beam": "制梁",
    "beam_erection": "架梁",
    "cast_in_place_continuous_beam": "现浇连续梁",
    "cast_in_place_box_beam": "现浇箱梁",
    "steel_box_beam": "钢箱梁",
    "bridge_deck_system": "桥面系",
}


def _add_precedence_constraint(model: Any, starts: dict[str, Any], ends: dict[str, Any], link: PrecedenceLink) -> None:
    if link.relationship == "SS":
        model.Add(starts[link.successor_id] >= starts[link.predecessor_id] + link.lag_days)
    elif link.relationship == "FF":
        model.Add(ends[link.successor_id] >= ends[link.predecessor_id] + link.lag_days)
    elif link.relationship == "SF":
        model.Add(ends[link.successor_id] >= starts[link.predecessor_id] + link.lag_days)
    else:
        model.Add(starts[link.successor_id] >= ends[link.predecessor_id] + link.lag_days)


def _task_properties(task: Task) -> dict[str, Any]:
    properties = getattr(task, "properties", {})
    return properties if isinstance(properties, dict) else {}


def _add_continuous_beam_v18_constraints(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    precedence_links: list[PrecedenceLink],
    horizon: int,
) -> None:
    tasks_by_id = {task.id: task for task in tasks}

    sync_groups: dict[str, dict[str, Task]] = defaultdict(dict)
    for task in tasks:
        props = _task_properties(task)
        if props.get("continuous_task_type") != "standard_segment_batch":
            continue
        if not props.get("synchronizes_left_right_cantilevers"):
            continue
        side = str(props.get("standard_side") or "")
        if side not in {"left", "right"}:
            continue
        group_id = str(
            props.get("standard_sync_group_id")
            or f"{task.bridge_id}:{task.work_section_id}:{task.structure_id}:standard"
        )
        sync_groups[group_id][side] = task

    for group in sync_groups.values():
        left_task = group.get("left")
        right_task = group.get("right")
        if left_task is None or right_task is None:
            continue
        model.Add(starts[left_task.id] == starts[right_task.id])
        model.Add(ends[left_task.id] == ends[right_task.id])

    closure_links: dict[tuple[str, str], list[PrecedenceLink]] = defaultdict(list)
    for link in precedence_links:
        if link.source_rule_id not in CONTINUOUS_BEAM_CLOSURE_RULE_IDS:
            continue
        if link.predecessor_id not in tasks_by_id or link.successor_id not in tasks_by_id:
            continue
        closure_links[(link.successor_id, link.source_rule_id)].append(link)

    for (successor_id, source_rule_id), links in closure_links.items():
        predecessor_ids: list[str] = []
        for link in links:
            if link.predecessor_id not in predecessor_ids:
                predecessor_ids.append(link.predecessor_id)
        if len(predecessor_ids) != 2:
            continue
        configured_gap = next((link.max_finish_gap_days for link in links if link.max_finish_gap_days is not None), None)
        max_gap = DEFAULT_CONTINUOUS_CLOSURE_FINISH_GAP_DAYS if configured_gap is None else int(configured_gap)
        if max_gap < 0:
            continue
        left_id, right_id = predecessor_ids
        finish_gap = model.NewIntVar(
            0,
            horizon,
            f"continuous_finish_gap_{_safe(source_rule_id)}_{_safe(successor_id)}",
        )
        model.AddAbsEquality(finish_gap, ends[left_id] - ends[right_id])
        model.Add(finish_gap <= max_gap)


def _resource_parallel_group_key(resource: Resource) -> str:
    return resource.pool_id or resource.type


def _same_structure_resource_rule_key(task: Task, resource_group_key: str) -> tuple[str, str, str, str]:
    return (
        resource_group_key,
        task.structure_id,
        task.component_type,
        task.process_name,
    )


def _configured_parallel_limit(values: list[int | None]) -> int | None:
    configured = [int(value) for value in values if value is not None]
    if not configured:
        return None
    return max(1, min(configured))


def _add_named_same_structure_resource_rules(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
) -> None:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for task in tasks:
        for resource in resource_candidates.get(task.id, []):
            if not resource.same_structure_resource_binding and resource.same_structure_parallel_limit is None:
                continue
            group_key = _resource_parallel_group_key(resource)
            rule_key = _same_structure_resource_rule_key(task, group_key)
            bucket = grouped.setdefault(rule_key, {"tasks": {}, "resources": {}})
            bucket["tasks"][task.id] = task
            bucket["resources"][resource.id] = resource

    for group_index, bucket in enumerate(grouped.values()):
        group_tasks = sorted(bucket["tasks"].values(), key=lambda item: (item.sequence_order, item.id))
        if len(group_tasks) <= 1:
            continue
        resources = sorted(bucket["resources"].values(), key=_resource_sort_key)
        task_active_vars: dict[str, Any] = {}
        for task in group_tasks:
            assignments = [
                assignment_vars[(task.id, resource.id)]
                for resource in resources
                if (task.id, resource.id) in assignment_vars
            ]
            if not assignments:
                continue
            active = model.NewBoolVar(f"same_structure_group_active_{group_index}_{_safe(task.id)}")
            model.Add(sum(assignments) == active)
            task_active_vars[task.id] = active

        if len(task_active_vars) <= 1:
            continue

        if any(resource.same_structure_resource_binding for resource in resources):
            group_used = model.NewBoolVar(f"same_structure_group_used_{group_index}")
            active_sum = sum(task_active_vars.values())
            model.Add(active_sum >= group_used)
            model.Add(active_sum <= len(task_active_vars) * group_used)
            selected_by_resource: dict[str, Any] = {}
            for resource in resources:
                selected = model.NewBoolVar(f"same_structure_selected_resource_{group_index}_{_safe(resource.id)}")
                selected_by_resource[resource.id] = selected
            model.Add(sum(selected_by_resource.values()) == group_used)
            for task in group_tasks:
                for resource in resources:
                    assignment = assignment_vars.get((task.id, resource.id))
                    if assignment is not None:
                        model.Add(assignment <= selected_by_resource[resource.id])

        parallel_limit = _configured_parallel_limit(
            [resource.same_structure_parallel_limit for resource in resources]
        )
        if parallel_limit is None or len(task_active_vars) <= parallel_limit:
            continue
        intervals = [
            model.NewOptionalIntervalVar(
                starts[task.id],
                task.duration_days,
                ends[task.id],
                task_active_vars[task.id],
                f"same_structure_parallel_{group_index}_{_safe(task.id)}",
            )
            for task in group_tasks
            if task.id in task_active_vars
        ]
        if parallel_limit == 1:
            model.AddNoOverlap(intervals)
        else:
            model.AddCumulative(intervals, [1] * len(intervals), parallel_limit)


def _add_capacity_same_structure_parallel_rules(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    groups_by_type: dict[str, list[dict[str, Any]]],
    assignment_vars: dict[tuple[str, str], Any],
) -> None:
    grouped: dict[tuple[str, str, str, str], list[tuple[Task, Any, int]]] = defaultdict(list)
    for task in tasks:
        seen_group_keys: set[str] = set()
        for resource_type in task.compatible_resource_types:
            for group in groups_by_type.get(resource_type, []):
                group_key = group["key"]
                if group_key in seen_group_keys:
                    continue
                seen_group_keys.add(group_key)
                parallel_limit = group.get("same_structure_parallel_limit")
                if parallel_limit is None:
                    continue
                assignment = assignment_vars.get((task.id, group_key))
                if assignment is None:
                    continue
                grouped[_same_structure_resource_rule_key(task, group_key)].append(
                    (task, assignment, int(parallel_limit))
                )

    for group_index, items in enumerate(grouped.values()):
        parallel_limit = _configured_parallel_limit([item[2] for item in items])
        if parallel_limit is None or len(items) <= parallel_limit:
            continue
        intervals = [
            model.NewOptionalIntervalVar(
                starts[task.id],
                task.duration_days,
                ends[task.id],
                assignment,
                f"capacity_same_structure_parallel_{group_index}_{_safe(task.id)}",
            )
            for task, assignment, _ in items
        ]
        if parallel_limit == 1:
            model.AddNoOverlap(intervals)
        else:
            model.AddCumulative(intervals, [1] * len(intervals), parallel_limit)


def _successor_earliest_start_from_link(
    *,
    predecessor_start: int,
    predecessor_duration: int,
    successor_duration: int,
    link: PrecedenceLink,
) -> int:
    predecessor_end = predecessor_start + predecessor_duration
    if link.relationship == "SS":
        return predecessor_start + link.lag_days
    if link.relationship == "FF":
        return predecessor_end + link.lag_days - successor_duration
    if link.relationship == "SF":
        return predecessor_start + link.lag_days - successor_duration
    return predecessor_end + link.lag_days


def _precedence_violated(predecessor: ScheduledTask, successor: ScheduledTask, link: PrecedenceLink) -> bool:
    if link.relationship == "SS":
        return successor.start_offset < predecessor.start_offset + link.lag_days
    if link.relationship == "FF":
        return successor.end_offset < predecessor.end_offset + link.lag_days
    if link.relationship == "SF":
        return successor.end_offset < predecessor.start_offset + link.lag_days
    return successor.start_offset < predecessor.end_offset + link.lag_days


def _configure_solver(solver: Any, time_limit_seconds: float) -> None:
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = _scheduler_search_workers()
    solver.parameters.random_seed = SCHEDULER_RANDOM_SEED
    solver.parameters.randomize_search = False


def _add_schedule_hints(
    model: Any,
    *,
    starts: dict[str, Any],
    ends: dict[str, Any],
    assignment_vars: dict[tuple[str, str], Any],
    warm_start_result: ScheduleResult | None,
) -> bool:
    if warm_start_result is None or warm_start_result.status not in {"OPTIMAL", "FEASIBLE"}:
        return False

    hinted = False
    assigned_resource_by_task_id: dict[str, str | None] = {}
    for task in warm_start_result.tasks:
        if task.id in starts:
            model.AddHint(starts[task.id], max(0, int(task.start_offset)))
            hinted = True
        if task.id in ends:
            model.AddHint(ends[task.id], max(0, int(task.end_offset)))
            hinted = True
        assigned_resource_by_task_id[task.id] = task.assigned_resource_id

    for (task_id, resource_id), assignment in assignment_vars.items():
        assigned_resource_id = assigned_resource_by_task_id.get(task_id)
        if assigned_resource_id is None:
            continue
        model.AddHint(assignment, 1 if assigned_resource_id == resource_id else 0)
        hinted = True
    return hinted


def _scheduler_search_workers() -> int:
    raw = os.getenv("SCHEDULER_SEARCH_WORKERS")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return max(1, int(SCHEDULER_SEARCH_WORKERS))


def _solve_task_parallelism(candidate_count: int) -> int:
    if candidate_count <= 1:
        return 1
    raw = os.getenv("SCHEDULER_PARALLEL_SOLVES")
    if raw:
        try:
            return max(1, min(candidate_count, int(raw)))
        except ValueError:
            pass
    cpu_budget = max(1, os.cpu_count() or 1)
    workers_per_solver = max(1, _scheduler_search_workers())
    return max(1, min(candidate_count, cpu_budget // workers_per_solver))


def _uses_control_priority_strategy(schedule_input: ScheduleInput) -> bool:
    return schedule_input.schedule_strategy.strategy in {"control_priority", "balanced_normal", "comprehensive"}


def solve_schedule(schedule_input: ScheduleInput, *, enforce_hard_milestones: bool = False) -> ScheduleResult:
    if _uses_control_priority_strategy(schedule_input):
        return solve_control_priority_schedule(schedule_input, enforce_hard_milestones=enforce_hard_milestones)

    enabled_resources = [resource for resource in schedule_input.resources if resource.enabled]
    resource_candidates = _resource_candidates_by_task(schedule_input.tasks, enabled_resources)
    validation = _validate_resource_coverage(schedule_input.tasks, resource_candidates)
    if any(message.level == "error" for message in validation):
        return ScheduleResult(
            status="INFEASIBLE",
            plan_start_date=schedule_input.start_date,
            validation=validation,
            stats={"reason": "missing_compatible_resource"},
        )

    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=schedule_input.start_date,
            validation=[
                ValidationMessage(
                    level="error",
                    message="未安装 OR-Tools，请先安装后端依赖再执行求解。",
                )
            ],
            stats={"reason": "ortools_missing"},
        )

    model = cp_model.CpModel()
    horizon = _build_horizon(schedule_input)
    starts: dict[str, Any] = {}
    ends: dict[str, Any] = {}
    task_by_id = {task.id: task for task in schedule_input.tasks}
    assignment_vars: dict[tuple[str, str], Any] = {}
    resource_intervals: dict[str, list[Any]] = defaultdict(list)
    milestone_vars: dict[str, Any] = {}
    milestone_target_offsets: dict[str, int] = {}
    soft_lateness_vars: dict[str, Any] = {}

    for task in schedule_input.tasks:
        starts[task.id] = model.NewIntVar(0, horizon, f"start_{_safe(task.id)}")
        ends[task.id] = model.NewIntVar(0, horizon, f"end_{_safe(task.id)}")
        model.Add(ends[task.id] == starts[task.id] + task.duration_days)

        choices = []
        for resource in resource_candidates[task.id]:
            assigned = model.NewBoolVar(f"assign_{_safe(task.id)}_{_safe(resource.id)}")
            interval = model.NewOptionalIntervalVar(
                starts[task.id],
                task.duration_days,
                ends[task.id],
                assigned,
                f"interval_{_safe(task.id)}_{_safe(resource.id)}",
            )
            choices.append(assigned)
            assignment_vars[(task.id, resource.id)] = assigned
            resource_intervals[resource.id].append(interval)
        if choices:
            model.AddExactlyOne(choices)

    for link in schedule_input.precedence_links:
        predecessor = task_by_id.get(link.predecessor_id)
        successor = task_by_id.get(link.successor_id)
        if not predecessor or not successor:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=link.id,
                    message=f"已跳过逻辑关系 {link.id}：前置或后续工作项不存在。",
                )
            )
            continue
        _add_precedence_constraint(model, starts, ends, link)

    _add_continuous_beam_v18_constraints(
        model,
        starts,
        ends,
        schedule_input.tasks,
        schedule_input.precedence_links,
        horizon,
    )

    _add_named_same_structure_resource_rules(
        model,
        starts,
        ends,
        schedule_input.tasks,
        resource_candidates,
        assignment_vars,
    )

    for intervals in resource_intervals.values():
        model.AddNoOverlap(intervals)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [ends[task.id] for task in schedule_input.tasks])

    for milestone in schedule_input.milestones:
        scoped_task_ids = _task_ids_for_milestone(milestone, schedule_input.tasks)
        if not scoped_task_ids:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=milestone.id,
                    message=f"里程碑“{milestone.name}”没有匹配的工作项，已跳过。",
                )
            )
            continue

        event_var = model.NewIntVar(0, horizon, f"milestone_{_safe(milestone.id)}")
        event_vars = [ends[task_id] if milestone.target_event == "finish" else starts[task_id] for task_id in scoped_task_ids]
        if milestone.target_event == "finish":
            model.AddMaxEquality(event_var, event_vars)
        else:
            model.AddMinEquality(event_var, event_vars)

        target_offset = _target_offset(schedule_input.start_date, milestone)
        milestone_vars[milestone.id] = event_var
        milestone_target_offsets[milestone.id] = target_offset
        if milestone.mode == "hard" and enforce_hard_milestones:
            model.Add(event_var <= target_offset)
        elif milestone.mode == "soft":
            lateness_upper = max(horizon - target_offset, horizon) + 365
            lateness_var = model.NewIntVar(0, lateness_upper, f"late_{_safe(milestone.id)}")
            model.Add(lateness_var >= event_var - target_offset)
            soft_lateness_vars[milestone.id] = lateness_var

    soft_penalty_terms = [
        late_var * _milestone_by_id(schedule_input.milestones, milestone_id).penalty_per_day
        for milestone_id, late_var in soft_lateness_vars.items()
    ]
    continuity_terms = _build_continuity_soft_terms(model, schedule_input.tasks, resource_candidates, assignment_vars)
    primary_objective = makespan + sum(soft_penalty_terms)
    continuity_objective = sum(continuity_terms["split_terms"]) * SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT + sum(
        continuity_terms["spatial_terms"]
    ) * SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT
    model.Minimize(primary_objective * CONTINUITY_PRIMARY_WEIGHT + continuity_objective)

    solver = cp_model.CpSolver()
    _configure_solver(solver, schedule_input.time_limit_seconds)
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)

    stats = {
        "horizon_days": horizon,
        "wall_time_seconds": solver.WallTime(),
        "conflicts": solver.NumConflicts(),
        "branches": solver.NumBranches(),
        "random_seed": SCHEDULER_RANDOM_SEED,
        "search_workers": _scheduler_search_workers(),
    }

    if status not in {"OPTIMAL", "FEASIBLE"}:
        return ScheduleResult(
            status=status,
            plan_start_date=schedule_input.start_date,
            milestone_results=_not_evaluated_milestones(schedule_input.milestones),
            validation=validation
            + [
                ValidationMessage(
                    level="error",
                    message=(
                        "在当前资源配置和工艺逻辑约束下，CP-SAT 未找到可行排程。"
                    ),
                )
            ],
            stats=stats,
        )

    resource_by_id = {resource.id: resource for resource in enabled_resources}
    predecessors_by_successor: dict[str, list[str]] = defaultdict(list)
    for link in schedule_input.precedence_links:
        predecessors_by_successor[link.successor_id].append(link.predecessor_id)

    scheduled_tasks: list[ScheduledTask] = []
    allocations: list[ResourceAllocation] = []

    for task in sorted(schedule_input.tasks, key=lambda item: (solver.Value(starts[item.id]), item.id)):
        assigned_resource = _assigned_resource_for_task(task, resource_candidates, assignment_vars, solver)
        start_offset = solver.Value(starts[task.id])
        end_offset = solver.Value(ends[task.id])
        start_day = _offset_date(schedule_input.start_date, start_offset)
        finish_day = _finish_date(schedule_input.start_date, end_offset)

        scheduled_task = ScheduledTask(
            **task.model_dump(),
            start_offset=start_offset,
            end_offset=end_offset,
            start_date=start_day,
            finish_date=finish_day,
            assigned_resource_id=assigned_resource.id if assigned_resource else None,
            assigned_resource_name=assigned_resource.name if assigned_resource else None,
            assigned_resource_type=assigned_resource.type if assigned_resource else None,
            predecessor_ids=predecessors_by_successor.get(task.id, []),
        )
        scheduled_tasks.append(scheduled_task)

        if assigned_resource:
            allocations.append(
                ResourceAllocation(
                    resource_id=assigned_resource.id,
                    resource_name=assigned_resource.name,
                    resource_type=assigned_resource.type,
                    task_id=task.id,
                    task_name=task.name,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_date=start_day,
                    finish_date=finish_day,
                )
            )

    objective_days = solver.Value(makespan)
    milestone_results = _build_milestone_results(
        schedule_input=schedule_input,
        milestone_vars=milestone_vars,
        milestone_target_offsets=milestone_target_offsets,
        soft_lateness_vars=soft_lateness_vars,
        solver=solver,
    )
    validation.extend(_validate_solution(schedule_input, scheduled_tasks, allocations))
    validation.extend(_validate_milestone_results(milestone_results))
    continuity_metrics = _build_continuity_metrics(scheduled_tasks)
    validation.extend(_continuity_validation_messages(continuity_metrics))
    soft_milestone_penalty = sum(result.penalty for result in milestone_results if result.mode == "soft")
    continuity_split_penalty = sum(solver.Value(term) for term in continuity_terms["split_terms"])
    spatial_assignment_penalty = sum(
        int(term["penalty"]) * solver.Value(term["assignment"]) for term in continuity_terms["spatial_term_details"]
    )
    stats["continuity_metrics"] = continuity_metrics
    stats["continuity_objective"] = {
        "same_structure_craft_split_penalty": continuity_split_penalty,
        "spatial_assignment_penalty": spatial_assignment_penalty,
        "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
        "same_structure_craft_split_weight": SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT,
        "spatial_resource_assignment_weight": SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT,
    }

    return ScheduleResult(
        status=status,
        objective_days=objective_days,
        plan_start_date=schedule_input.start_date,
        plan_finish_date=_finish_date(schedule_input.start_date, objective_days),
        tasks=scheduled_tasks,
        resource_allocations=sorted(
            allocations,
            key=lambda item: (item.resource_name, item.start_offset, item.task_name),
        ),
        milestone_results=milestone_results,
        validation=validation,
        stats=stats,
        objective_breakdown={
            "makespan_days": objective_days,
            "soft_milestone_penalty": soft_milestone_penalty,
            "same_structure_craft_split_penalty": continuity_split_penalty,
            "spatial_assignment_penalty": spatial_assignment_penalty,
            "continuity_score": continuity_metrics["continuity_score"],
            "weighted_objective": objective_days + soft_milestone_penalty,
        },
    )


def solve_control_priority_schedule(
    schedule_input: ScheduleInput,
    *,
    enforce_hard_milestones: bool = False,
    baseline_result: ScheduleResult | None = None,
    max_makespan_days: int | None = None,
    warm_start_result: ScheduleResult | None = None,
) -> ScheduleResult:
    if baseline_result is None:
        baseline_input = schedule_input.model_copy(
            update={
                "schedule_strategy": schedule_input.schedule_strategy.model_copy(
                    update={"strategy": "shortest_duration"}
                )
            }
        )
        baseline_result = solve_schedule(baseline_input)
    if baseline_result.status not in {"OPTIMAL", "FEASIBLE"}:
        baseline_result.objective_breakdown.setdefault("solve_mode", "control_priority_baseline_failed")
        baseline_result.validation.append(
            ValidationMessage(
                level="warning",
                message="控制性工程优先策略未能进入二次优化：基础排程未得到可行解。",
            )
        )
        return baseline_result

    enabled_resources = [resource for resource in schedule_input.resources if resource.enabled]
    resource_candidates = _resource_candidates_by_task(schedule_input.tasks, enabled_resources)
    validation = _validate_resource_coverage(schedule_input.tasks, resource_candidates)
    if any(message.level == "error" for message in validation):
        return ScheduleResult(
            status="INFEASIBLE",
            plan_start_date=schedule_input.start_date,
            validation=validation,
            stats={"reason": "missing_compatible_resource", "solve_mode": "control_priority"},
        )

    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=schedule_input.start_date,
            validation=[
                ValidationMessage(
                    level="error",
                    message="未安装 OR-Tools，请先安装后端依赖后再执行求解。",
                )
            ],
            stats={"reason": "ortools_missing", "solve_mode": "control_priority"},
        )

    model = cp_model.CpModel()
    horizon = _build_horizon(schedule_input)
    starts: dict[str, Any] = {}
    ends: dict[str, Any] = {}
    task_by_id = {task.id: task for task in schedule_input.tasks}
    assignment_vars: dict[tuple[str, str], Any] = {}
    resource_intervals: dict[str, list[Any]] = defaultdict(list)
    milestone_vars: dict[str, Any] = {}
    milestone_target_offsets: dict[str, int] = {}
    soft_lateness_vars: dict[str, Any] = {}
    config = schedule_input.schedule_strategy
    control_chain_task_ids = _control_chain_task_ids(schedule_input)
    normal_tasks = _normal_balance_tasks(schedule_input.tasks, control_chain_task_ids)

    for task in schedule_input.tasks:
        starts[task.id] = model.NewIntVar(0, horizon, f"start_{_safe(task.id)}")
        ends[task.id] = model.NewIntVar(0, horizon, f"end_{_safe(task.id)}")
        model.Add(ends[task.id] == starts[task.id] + task.duration_days)

        choices = []
        for resource in resource_candidates[task.id]:
            assigned = model.NewBoolVar(f"assign_{_safe(task.id)}_{_safe(resource.id)}")
            interval = model.NewOptionalIntervalVar(
                starts[task.id],
                task.duration_days,
                ends[task.id],
                assigned,
                f"interval_{_safe(task.id)}_{_safe(resource.id)}",
            )
            choices.append(assigned)
            assignment_vars[(task.id, resource.id)] = assigned
            resource_intervals[resource.id].append(interval)
        if choices:
            model.AddExactlyOne(choices)

    for link in schedule_input.precedence_links:
        predecessor = task_by_id.get(link.predecessor_id)
        successor = task_by_id.get(link.successor_id)
        if not predecessor or not successor:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=link.id,
                    message=f"已跳过逻辑关系 {link.id}：前置或后续工作项不存在。",
                )
            )
            continue
        _add_precedence_constraint(model, starts, ends, link)

    _add_continuous_beam_v18_constraints(
        model,
        starts,
        ends,
        schedule_input.tasks,
        schedule_input.precedence_links,
        horizon,
    )

    for intervals in resource_intervals.values():
        model.AddNoOverlap(intervals)

    _add_normal_time_window_constraints(model, starts, ends, normal_tasks, config, horizon)
    _add_normal_workface_constraints(model, starts, ends, normal_tasks, config)
    if config.resource_guarantee == "strict":
        _add_strict_control_resource_constraints(model, starts, ends, schedule_input.tasks, control_chain_task_ids)

    _add_named_same_structure_resource_rules(
        model,
        starts,
        ends,
        schedule_input.tasks,
        resource_candidates,
        assignment_vars,
    )

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [ends[task.id] for task in schedule_input.tasks])
    if max_makespan_days is not None:
        model.Add(makespan <= max_makespan_days)

    for milestone in schedule_input.milestones:
        scoped_task_ids = _task_ids_for_milestone(milestone, schedule_input.tasks)
        if milestone.related_structure_ids:
            related_ids = {
                task.id
                for task in schedule_input.tasks
                if task.structure_id in set(milestone.related_structure_ids)
            }
            scoped_task_ids = sorted(set(scoped_task_ids) | related_ids)
        if not scoped_task_ids:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=milestone.id,
                    message=f"里程碑“{milestone.name}”没有匹配的工作项，已跳过。",
                )
            )
            continue

        event_var = model.NewIntVar(0, horizon, f"milestone_{_safe(milestone.id)}")
        event_vars = [ends[task_id] if milestone.target_event == "finish" else starts[task_id] for task_id in scoped_task_ids]
        if milestone.target_event == "finish":
            model.AddMaxEquality(event_var, event_vars)
        else:
            model.AddMinEquality(event_var, event_vars)

        target_offset = _target_offset(schedule_input.start_date, milestone)
        milestone_vars[milestone.id] = event_var
        milestone_target_offsets[milestone.id] = target_offset
        if milestone.mode == "hard" and enforce_hard_milestones:
            model.Add(event_var <= target_offset)
        else:
            lateness_upper = max(horizon - target_offset, horizon) + 365
            lateness_var = model.NewIntVar(0, lateness_upper, f"late_{_safe(milestone.id)}")
            model.Add(lateness_var >= event_var - target_offset)
            soft_lateness_vars[milestone.id] = lateness_var

    control_lateness_terms = [
        late_var
        for milestone_id, late_var in soft_lateness_vars.items()
        if _is_control_milestone(_milestone_by_id(schedule_input.milestones, milestone_id))
    ]
    soft_penalty_terms = [
        late_var * _milestone_by_id(schedule_input.milestones, milestone_id).penalty_per_day
        for milestone_id, late_var in soft_lateness_vars.items()
    ]
    control_buffer_terms = _build_control_buffer_terms(
        model,
        ends,
        schedule_input=schedule_input,
        control_chain_task_ids=control_chain_task_ids,
        horizon=horizon,
        fallback_deadline_days=baseline_result.objective_days,
    )
    control_wait_details = _build_control_wait_term_details(
        model,
        starts,
        ends,
        schedule_input.precedence_links,
        task_by_id,
        control_chain_task_ids,
        horizon,
    )
    risk_related_control_wait_terms = _risk_related_control_wait_terms(
        model,
        control_wait_details,
        control_buffer_terms["risk_by_task"],
        horizon,
    )
    normal_balance_terms = (
        _build_normal_balance_terms(model, starts, schedule_input.tasks, baseline_result, config, horizon)
        if config.enable_balance_objective
        else []
    )
    continuity_terms = _build_continuity_soft_terms(model, schedule_input.tasks, resource_candidates, assignment_vars)
    resource_organization_terms = _build_resource_organization_terms(
        model,
        starts,
        ends,
        schedule_input.tasks,
        enabled_resources,
        resource_candidates,
        assignment_vars,
        horizon,
    )
    continuity_objective = sum(continuity_terms["split_terms"]) * SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT + sum(
        continuity_terms["spatial_terms"]
    ) * SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT

    model.Minimize(
        sum(control_lateness_terms) * CONTROL_NODE_LATE_WEIGHT
        + sum(control_buffer_terms["terms"]) * CONTROL_BUFFER_RISK_WEIGHT
        + sum(risk_related_control_wait_terms) * CONTROL_RESOURCE_WAIT_WEIGHT
        + sum(resource_organization_terms["workload_balance_terms"]) * RESOURCE_WORKLOAD_BALANCE_WEIGHT
        + sum(resource_organization_terms["idle_terms"]) * RESOURCE_IDLE_WEIGHT
        + sum(resource_organization_terms["path_terms"]) * RESOURCE_PATH_CONTINUITY_WEIGHT
        + (makespan + sum(soft_penalty_terms)) * CONTROL_MAKESPAN_WEIGHT
        + sum(normal_balance_terms) * NORMAL_BALANCE_WEIGHT
        + continuity_objective
    )
    warm_start_used = _add_schedule_hints(
        model,
        starts=starts,
        ends=ends,
        assignment_vars=assignment_vars,
        warm_start_result=warm_start_result,
    )

    solver = cp_model.CpSolver()
    _configure_solver(solver, schedule_input.time_limit_seconds)
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)

    stats = {
        "horizon_days": horizon,
        "wall_time_seconds": solver.WallTime(),
        "conflicts": solver.NumConflicts(),
        "branches": solver.NumBranches(),
        "random_seed": SCHEDULER_RANDOM_SEED,
        "search_workers": _scheduler_search_workers(),
        "solve_mode": "control_priority",
        "baseline_objective_days": baseline_result.objective_days,
        "warm_start_used": warm_start_used,
    }
    if max_makespan_days is not None:
        stats["max_makespan_days"] = max_makespan_days

    if status not in {"OPTIMAL", "FEASIBLE"}:
        return ScheduleResult(
            status=status,
            plan_start_date=schedule_input.start_date,
            milestone_results=_not_evaluated_milestones(schedule_input.milestones),
            validation=validation
            + [
                ValidationMessage(
                    level="error",
                    message="控制性工程优先策略在当前工艺、资源、窗口和工作面约束下未找到可行排程。",
                )
            ],
            stats=stats,
        )

    resource_by_id = {resource.id: resource for resource in enabled_resources}
    predecessors_by_successor: dict[str, list[str]] = defaultdict(list)
    for link in schedule_input.precedence_links:
        predecessors_by_successor[link.successor_id].append(link.predecessor_id)

    scheduled_tasks: list[ScheduledTask] = []
    allocations: list[ResourceAllocation] = []
    for task in sorted(schedule_input.tasks, key=lambda item: (solver.Value(starts[item.id]), item.id)):
        assigned_resource = _assigned_resource_for_task(task, resource_candidates, assignment_vars, solver)
        start_offset = solver.Value(starts[task.id])
        end_offset = solver.Value(ends[task.id])
        start_day = _offset_date(schedule_input.start_date, start_offset)
        finish_day = _finish_date(schedule_input.start_date, end_offset)
        scheduled_task = ScheduledTask(
            **task.model_dump(),
            start_offset=start_offset,
            end_offset=end_offset,
            start_date=start_day,
            finish_date=finish_day,
            assigned_resource_id=assigned_resource.id if assigned_resource else None,
            assigned_resource_name=assigned_resource.name if assigned_resource else None,
            assigned_resource_type=assigned_resource.type if assigned_resource else None,
            predecessor_ids=predecessors_by_successor.get(task.id, []),
        )
        scheduled_tasks.append(scheduled_task)
        if assigned_resource:
            allocations.append(
                ResourceAllocation(
                    resource_id=assigned_resource.id,
                    resource_name=assigned_resource.name,
                    resource_type=assigned_resource.type,
                    task_id=task.id,
                    task_name=task.name,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_date=start_day,
                    finish_date=finish_day,
                )
            )

    objective_days = solver.Value(makespan)
    milestone_results = _build_milestone_results(
        schedule_input=schedule_input,
        milestone_vars=milestone_vars,
        milestone_target_offsets=milestone_target_offsets,
        soft_lateness_vars=soft_lateness_vars,
        solver=solver,
    )
    validation.extend(_validate_solution(schedule_input, scheduled_tasks, allocations))
    validation.extend(_validate_milestone_results(milestone_results))
    continuity_metrics = _build_continuity_metrics(scheduled_tasks)
    validation.extend(_continuity_validation_messages(continuity_metrics))
    soft_milestone_penalty = sum(result.penalty for result in milestone_results if result.mode == "soft")
    control_lateness_days = sum(
        result.lateness_days for result in milestone_results if _is_control_milestone_result(result)
    )
    soft_control_lateness_penalty = sum(
        result.lateness_days
        for result in milestone_results
        if result.mode == "soft" and _is_control_milestone_result(result)
    )
    control_buffer_risk_penalty = sum(solver.Value(term) for term in control_buffer_terms["terms"])
    risk_related_control_wait_penalty = sum(solver.Value(term) for term in risk_related_control_wait_terms)
    continuity_split_penalty = sum(solver.Value(term) for term in continuity_terms["split_terms"])
    spatial_assignment_penalty = sum(
        int(term["penalty"]) * solver.Value(term["assignment"]) for term in continuity_terms["spatial_term_details"]
    )
    resource_workload_balance_penalty = sum(solver.Value(term) for term in resource_organization_terms["workload_balance_terms"])
    resource_idle_penalty = sum(solver.Value(term) for term in resource_organization_terms["idle_terms"])
    resource_path_continuity_penalty = sum(solver.Value(term) for term in resource_organization_terms["path_terms"])
    continuity_preference_penalty = continuity_split_penalty + spatial_assignment_penalty
    normal_balance_metrics = _build_normal_balance_metrics(scheduled_tasks, config)
    resource_organization_analysis = _build_resource_organization_analysis(
        scheduled_tasks,
        enabled_resources,
        objective_days=objective_days,
        continuity_metrics=continuity_metrics,
    )
    control_buffer_risks = _control_buffer_risk_details(
        schedule_input=schedule_input,
        scheduled_tasks=scheduled_tasks,
        profiles=control_buffer_terms["profiles"],
    )
    control_priority_analysis = _build_control_priority_analysis(
        schedule_input=schedule_input,
        baseline_result=baseline_result,
        scheduled_tasks=scheduled_tasks,
        allocations=allocations,
        milestone_results=milestone_results,
        control_chain_task_ids=control_chain_task_ids,
        control_buffer_risks=control_buffer_risks,
        continuity_metrics=continuity_metrics,
        normal_balance_metrics=normal_balance_metrics,
        resource_organization_analysis=resource_organization_analysis,
    )
    stats["continuity_metrics"] = continuity_metrics
    stats["continuity_objective"] = {
        "same_structure_craft_split_penalty": continuity_split_penalty,
        "spatial_assignment_penalty": spatial_assignment_penalty,
        "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
        "same_structure_craft_split_weight": SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT,
        "spatial_resource_assignment_weight": SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT,
    }
    stats["normal_balance_metrics"] = normal_balance_metrics
    stats["resource_organization_analysis"] = resource_organization_analysis
    stats["control_priority_analysis"] = control_priority_analysis
    weighted_objective = (
        control_lateness_days * CONTROL_NODE_LATE_WEIGHT
        + control_buffer_risk_penalty * CONTROL_BUFFER_RISK_WEIGHT
        + risk_related_control_wait_penalty * CONTROL_RESOURCE_WAIT_WEIGHT
        + resource_workload_balance_penalty * RESOURCE_WORKLOAD_BALANCE_WEIGHT
        + resource_idle_penalty * RESOURCE_IDLE_WEIGHT
        + resource_path_continuity_penalty * RESOURCE_PATH_CONTINUITY_WEIGHT
        + (objective_days + soft_milestone_penalty) * CONTROL_MAKESPAN_WEIGHT
        + sum(solver.Value(term) for term in normal_balance_terms) * NORMAL_BALANCE_WEIGHT
        + continuity_split_penalty * SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT
        + spatial_assignment_penalty * SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT
    )
    validation.append(
        ValidationMessage(
            level="info",
            message=(
                f"控制性工程优先策略已完成：控制链工作项 {len(control_chain_task_ids)} 个，"
                f"控制缓冲状态 {control_priority_analysis['control_buffer_status']}，"
                f"普通工程均衡评分 {normal_balance_metrics['balance_score']}。"
            ),
        )
    )

    return ScheduleResult(
        status=status,
        objective_days=objective_days,
        plan_start_date=schedule_input.start_date,
        plan_finish_date=_finish_date(schedule_input.start_date, objective_days),
        tasks=scheduled_tasks,
        resource_allocations=sorted(
            allocations,
            key=lambda item: (item.resource_name, item.start_offset, item.task_name),
        ),
        milestone_results=milestone_results,
        validation=validation,
        stats=stats,
        objective_breakdown={
            "solve_mode": "control_priority",
            "strategy": config.strategy,
            "resource_guarantee": config.resource_guarantee,
            "makespan_days": objective_days,
            "baseline_makespan_days": baseline_result.objective_days,
            "control_lateness_days": control_lateness_days,
            "soft_control_lateness_penalty": soft_control_lateness_penalty,
            "control_buffer_risk_penalty": control_buffer_risk_penalty,
            "risk_related_control_wait_penalty": risk_related_control_wait_penalty,
            "control_resource_wait_penalty": risk_related_control_wait_penalty,
            "resource_workload_balance_penalty": resource_workload_balance_penalty,
            "resource_idle_penalty": resource_idle_penalty,
            "resource_path_continuity_penalty": resource_path_continuity_penalty,
            "resource_balance_weight": RESOURCE_WORKLOAD_BALANCE_WEIGHT,
            "resource_idle_weight": RESOURCE_IDLE_WEIGHT,
            "normal_balance_penalty": sum(solver.Value(term) for term in normal_balance_terms),
            "soft_milestone_penalty": soft_milestone_penalty,
            "same_structure_craft_split_penalty": continuity_split_penalty,
            "spatial_assignment_penalty": spatial_assignment_penalty,
            "continuity_preference_penalty": continuity_preference_penalty,
            "continuity_score": continuity_metrics["continuity_score"],
            "normal_balance_score": normal_balance_metrics["balance_score"],
            "resource_organization_analysis": resource_organization_analysis,
            "weighted_objective": weighted_objective,
            "objective_weights": {
                "control_node_late": CONTROL_NODE_LATE_WEIGHT,
                "control_buffer_risk": CONTROL_BUFFER_RISK_WEIGHT,
                "risk_related_control_wait": CONTROL_RESOURCE_WAIT_WEIGHT,
                "resource_workload_balance": RESOURCE_WORKLOAD_BALANCE_WEIGHT,
                "resource_idle": RESOURCE_IDLE_WEIGHT,
                "resource_path_continuity": RESOURCE_PATH_CONTINUITY_WEIGHT,
                "makespan_and_soft_milestone": CONTROL_MAKESPAN_WEIGHT,
                "normal_balance": NORMAL_BALANCE_WEIGHT,
                "same_structure_craft_split": SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT,
                "spatial_resource_assignment": SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT,
            },
            "control_priority_analysis": control_priority_analysis,
            "normal_balance_metrics": normal_balance_metrics,
        },
    )


def _control_chain_task_ids(schedule_input: ScheduleInput) -> set[str]:
    task_by_id = {task.id: task for task in schedule_input.tasks}
    target_ids = _control_target_task_ids(schedule_input)
    predecessors_by_successor: dict[str, list[str]] = defaultdict(list)
    for link in schedule_input.precedence_links:
        if link.predecessor_id in task_by_id and link.successor_id in task_by_id:
            predecessors_by_successor[link.successor_id].append(link.predecessor_id)

    chain = set(target_ids)
    stack = list(target_ids)
    while stack:
        task_id = stack.pop()
        for predecessor_id in predecessors_by_successor.get(task_id, []):
            if predecessor_id in chain:
                continue
            chain.add(predecessor_id)
            stack.append(predecessor_id)
    return chain


def _control_target_task_ids(schedule_input: ScheduleInput) -> set[str]:
    task_by_id = {task.id: task for task in schedule_input.tasks}
    broad_scope_types = {"project", "bridge", "work_section"}
    target_ids = {
        task.id
        for task in schedule_input.tasks
        if task.control_level in {"control", "key"}
    }
    for milestone in schedule_input.milestones:
        if milestone.related_structure_ids:
            related_structure_ids = set(milestone.related_structure_ids)
            target_ids.update(
                task.id for task in schedule_input.tasks if task.structure_id in related_structure_ids
            )
            continue
        if not _is_control_milestone(milestone):
            continue
        scoped_ids = set(_task_ids_for_milestone(milestone, schedule_input.tasks))
        if milestone.scope_type in broad_scope_types:
            scoped_ids = {
                task_id
                for task_id in scoped_ids
                if task_by_id[task_id].control_level in {"control", "key"}
            }
        target_ids.update(scoped_ids)
    return target_ids


def _normal_balance_tasks(tasks: list[Task], control_chain_task_ids: set[str]) -> list[Task]:
    return [
        task
        for task in tasks
        if task.id not in control_chain_task_ids and task.control_level == "normal"
    ]


def _add_normal_time_window_constraints(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    normal_tasks: list[Task],
    config: Any,
    horizon: int,
) -> None:
    earliest = config.normal_earliest_start_offset
    latest = config.normal_latest_finish_offset
    for task in normal_tasks:
        if earliest > 0:
            model.Add(starts[task.id] >= earliest)
        if latest is not None:
            bounded_latest = min(horizon, latest)
            model.Add(ends[task.id] <= bounded_latest)
            if config.normal_max_early_finish_days > 0:
                model.Add(ends[task.id] >= max(0, bounded_latest - config.normal_max_early_finish_days))


def _add_normal_workface_constraints(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    normal_tasks: list[Task],
    config: Any,
) -> None:
    if config.max_parallel_normal_per_work_section <= 0:
        return
    by_work_section: dict[tuple[str | None, str | None], list[Task]] = defaultdict(list)
    for task in normal_tasks:
        by_work_section[(task.bridge_id, task.work_section_id)].append(task)
    for group_index, group_tasks in enumerate(by_work_section.values()):
        if len(group_tasks) <= config.max_parallel_normal_per_work_section:
            continue
        intervals = [
            model.NewIntervalVar(
                starts[task.id],
                task.duration_days,
                ends[task.id],
                f"normal_workface_{group_index}_{_safe(task.id)}",
            )
            for task in group_tasks
        ]
        model.AddCumulative(intervals, [1] * len(intervals), config.max_parallel_normal_per_work_section)


def _add_strict_control_resource_constraints(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    control_chain_task_ids: set[str],
) -> None:
    control_tasks = [task for task in tasks if task.id in control_chain_task_ids]
    normal_tasks = [task for task in tasks if task.id not in control_chain_task_ids and task.control_level == "normal"]
    for control_task in control_tasks:
        control_types = set(control_task.compatible_resource_types)
        if not control_types:
            continue
        for normal_task in normal_tasks:
            if not control_types.intersection(normal_task.compatible_resource_types):
                continue
            model.Add(starts[normal_task.id] >= ends[control_task.id])


def _build_control_wait_terms(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    links: list[PrecedenceLink],
    task_by_id: dict[str, Task],
    control_chain_task_ids: set[str],
    horizon: int,
) -> list[Any]:
    return [
        detail["term"]
        for detail in _build_control_wait_term_details(
            model,
            starts,
            ends,
            links,
            task_by_id,
            control_chain_task_ids,
            horizon,
        )
    ]


def _build_control_wait_term_details(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    links: list[PrecedenceLink],
    task_by_id: dict[str, Task],
    control_chain_task_ids: set[str],
    horizon: int,
) -> list[dict[str, Any]]:
    terms = []
    for index, link in enumerate(links):
        predecessor = task_by_id.get(link.predecessor_id)
        successor = task_by_id.get(link.successor_id)
        if predecessor is None or successor is None or successor.id not in control_chain_task_ids:
            continue
        wait = model.NewIntVar(0, horizon, f"control_wait_{index}")
        if link.relationship == "SS":
            model.Add(wait >= starts[successor.id] - starts[predecessor.id] - link.lag_days)
        elif link.relationship == "FF":
            model.Add(wait >= ends[successor.id] - ends[predecessor.id] - link.lag_days)
        elif link.relationship == "SF":
            model.Add(wait >= ends[successor.id] - starts[predecessor.id] - link.lag_days)
        else:
            model.Add(wait >= starts[successor.id] - ends[predecessor.id] - link.lag_days)
        terms.append(
            {
                "term": wait,
                "predecessor_id": predecessor.id,
                "successor_id": successor.id,
            }
        )
    return terms


def _build_control_buffer_terms(
    model: Any,
    ends: dict[str, Any],
    *,
    schedule_input: ScheduleInput,
    control_chain_task_ids: set[str],
    horizon: int,
    fallback_deadline_days: int | None,
) -> dict[str, Any]:
    profiles = _control_buffer_profiles(
        schedule_input,
        control_chain_task_ids,
        fallback_deadline_days=fallback_deadline_days,
    )
    terms = []
    risk_by_task: dict[str, Any] = {}
    for task_id, profile in profiles.items():
        if task_id not in ends:
            continue
        risk = model.NewIntVar(
            0,
            horizon + profile["necessary_buffer_days"],
            f"control_buffer_risk_{_safe(task_id)}",
        )
        safe_boundary = profile["latest_safe_finish_offset"] - profile["necessary_buffer_days"]
        model.Add(risk >= ends[task_id] - safe_boundary)
        terms.append(risk)
        risk_by_task[task_id] = risk
    return {"terms": terms, "risk_by_task": risk_by_task, "profiles": profiles}


def _risk_related_control_wait_terms(
    model: Any,
    wait_details: list[dict[str, Any]],
    risk_by_task: dict[str, Any],
    horizon: int,
) -> list[Any]:
    terms = []
    for index, detail in enumerate(wait_details):
        risk = risk_by_task.get(detail["successor_id"])
        if risk is None:
            continue
        wait = detail["term"]
        at_risk = model.NewBoolVar(f"control_wait_at_risk_{index}")
        model.Add(risk >= 1).OnlyEnforceIf(at_risk)
        model.Add(risk == 0).OnlyEnforceIf(at_risk.Not())
        risk_wait = model.NewIntVar(0, horizon, f"risk_related_control_wait_{index}")
        model.Add(risk_wait <= wait)
        model.Add(risk_wait <= horizon * at_risk)
        model.Add(risk_wait >= wait - horizon * (1 - at_risk))
        terms.append(risk_wait)
    return terms


def _control_buffer_profiles(
    schedule_input: ScheduleInput,
    control_chain_task_ids: set[str],
    *,
    fallback_deadline_days: int | None,
) -> dict[str, dict[str, Any]]:
    task_by_id = {task.id: task for task in schedule_input.tasks}
    target_ids = _control_target_task_ids(schedule_input)
    latest_finish, deadline_sources = _control_target_deadlines(
        schedule_input,
        target_ids,
        fallback_deadline_days=fallback_deadline_days,
    )
    if not latest_finish:
        return {}

    source_by_task = dict(deadline_sources)
    for _ in range(len(control_chain_task_ids) + 1):
        changed = False
        for link in reversed(schedule_input.precedence_links):
            if link.predecessor_id not in control_chain_task_ids or link.successor_id not in control_chain_task_ids:
                continue
            successor_deadline = latest_finish.get(link.successor_id)
            predecessor = task_by_id.get(link.predecessor_id)
            successor = task_by_id.get(link.successor_id)
            if successor_deadline is None or predecessor is None or successor is None:
                continue
            candidate = max(
                0,
                _predecessor_latest_finish_from_successor_deadline(
                    predecessor=predecessor,
                    successor=successor,
                    link=link,
                    successor_latest_finish=successor_deadline,
                ),
            )
            if link.predecessor_id not in latest_finish or candidate < latest_finish[link.predecessor_id]:
                latest_finish[link.predecessor_id] = candidate
                source_by_task[link.predecessor_id] = f"control_chain:{link.successor_id}"
                changed = True
        if not changed:
            break

    profiles: dict[str, dict[str, Any]] = {}
    for task_id in sorted(control_chain_task_ids):
        task = task_by_id.get(task_id)
        latest_safe_finish = latest_finish.get(task_id)
        if task is None or latest_safe_finish is None:
            continue
        profiles[task_id] = {
            "task_id": task_id,
            "task_name": _control_display_task_name(task),
            "control_level": task.control_level,
            "is_control_target": task_id in target_ids,
            "target_source": _control_target_source(task),
            "deadline_source": source_by_task.get(task_id, "unknown"),
            "latest_safe_finish_offset": latest_safe_finish,
            "latest_safe_finish_date": _finish_date(schedule_input.start_date, latest_safe_finish),
            "necessary_buffer_days": CONTROL_NECESSARY_BUFFER_DAYS,
        }
    return profiles


def _control_target_deadlines(
    schedule_input: ScheduleInput,
    target_ids: set[str],
    *,
    fallback_deadline_days: int | None,
) -> tuple[dict[str, int], dict[str, str]]:
    deadlines: dict[str, int] = {}
    sources: dict[str, str] = {}
    for milestone in schedule_input.milestones:
        if not _is_control_milestone(milestone):
            continue
        scoped_task_ids = set(_task_ids_for_milestone(milestone, schedule_input.tasks))
        if milestone.related_structure_ids:
            related_structure_ids = set(milestone.related_structure_ids)
            scoped_task_ids.update(
                task.id for task in schedule_input.tasks if task.structure_id in related_structure_ids
            )
        target_offset = _target_offset(schedule_input.start_date, milestone)
        for task_id in sorted(target_ids & scoped_task_ids):
            if task_id not in deadlines or target_offset < deadlines[task_id]:
                deadlines[task_id] = target_offset
                sources[task_id] = f"milestone:{milestone.id}"

    if fallback_deadline_days is not None:
        for task_id in sorted(target_ids):
            if task_id not in deadlines:
                deadlines[task_id] = fallback_deadline_days
                sources[task_id] = "baseline_makespan"
    return deadlines, sources


def _predecessor_latest_finish_from_successor_deadline(
    *,
    predecessor: Task,
    successor: Task,
    link: PrecedenceLink,
    successor_latest_finish: int,
) -> int:
    successor_latest_start = successor_latest_finish - successor.duration_days
    if link.relationship == "SS":
        return successor_latest_start - link.lag_days + predecessor.duration_days
    if link.relationship == "FF":
        return successor_latest_finish - link.lag_days
    if link.relationship == "SF":
        return successor_latest_finish - link.lag_days + predecessor.duration_days
    return successor_latest_start - link.lag_days


def _control_buffer_risk_details(
    *,
    schedule_input: ScheduleInput,
    scheduled_tasks: list[ScheduledTask],
    profiles: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    scheduled_by_id = {task.id: task for task in scheduled_tasks}
    details: list[dict[str, Any]] = []
    for task_id, profile in profiles.items():
        task = scheduled_by_id.get(task_id)
        if task is None:
            continue
        remaining_buffer = profile["latest_safe_finish_offset"] - task.end_offset
        risk_days = max(0, profile["necessary_buffer_days"] - remaining_buffer)
        if remaining_buffer < 0:
            status = "affected_node"
        elif risk_days > 0:
            status = "buffer_insufficient"
        elif remaining_buffer <= profile["necessary_buffer_days"] + CONTROL_BUFFER_NEAR_RISK_DAYS:
            status = "near_risk"
        else:
            status = "normal"
        details.append(
            {
                **profile,
                "start_date": task.start_date,
                "finish_date": task.finish_date,
                "finish_offset": task.end_offset,
                "remaining_buffer_days": remaining_buffer,
                "buffer_risk_days": risk_days,
                "status": status,
            }
        )
    return sorted(
        details,
        key=lambda item: (
            -int(item["buffer_risk_days"]),
            int(item["remaining_buffer_days"]),
            str(item["task_id"]),
        ),
    )


def _control_buffer_status(buffer_risks: list[dict[str, Any]]) -> str:
    if not buffer_risks:
        return "not_evaluated"
    statuses = {item["status"] for item in buffer_risks}
    if "affected_node" in statuses:
        return "affected_node"
    if "buffer_insufficient" in statuses:
        return "buffer_insufficient"
    if "near_risk" in statuses:
        return "near_risk"
    return "normal"


def _control_target_source(task: Task) -> str:
    if task.component_type == "cast_in_place_continuous_beam" or task.structure_type == "continuous_beam":
        return "cast_in_place_continuous_beam_rule"
    if task.control_level in {"control", "key"}:
        return "task_control_level"
    return "milestone_scope"


def _control_source_label(source: str) -> str:
    labels = {
        "cast_in_place_continuous_beam_rule": "现浇连续梁规则",
        "continuous_main_pier_inherited": "连续梁主墩继承",
        "task_control_level": "任务控制属性",
        "milestone_scope": "节点范围纳入",
        "control_chain_predecessor": "控制链前置追溯",
    }
    return labels.get(source, source)


def _control_object_ref(task: Task, continuous_linked_structure_ids: set[str]) -> dict[str, Any]:
    location = _task_location(task)
    structure_display_name = location["label"]
    if task.component_type == "cast_in_place_continuous_beam" or task.structure_type == "continuous_beam":
        source = "cast_in_place_continuous_beam_rule"
        return {
            "id": f"continuous:{task.structure_id}",
            "name": structure_display_name,
            "object_type": "continuous_beam",
            "source": source,
            "source_label": _control_source_label(source),
            "bridge_id": task.bridge_id,
            "work_section_id": task.work_section_id,
            "structure_id": task.structure_id,
            "structure_name": task.structure_name,
            "side": location["side"] or "N",
            "side_label": location["side_label"],
        }

    if task.structure_id in continuous_linked_structure_ids and task.control_level in {"control", "key"}:
        source = "continuous_main_pier_inherited"
        return {
            "id": f"lower:{task.structure_id}",
            "name": f"{structure_display_name}下部结构",
            "object_type": "main_pier_lower_structure",
            "source": source,
            "source_label": _control_source_label(source),
            "bridge_id": task.bridge_id,
            "work_section_id": task.work_section_id,
            "structure_id": task.structure_id,
            "structure_name": task.structure_name,
            "side": location["side"] or "N",
            "side_label": location["side_label"],
        }

    source = _control_target_source(task)
    return {
        "id": f"structure:{task.structure_id}",
        "name": structure_display_name,
        "object_type": "control_structure",
        "source": source,
        "source_label": _control_source_label(source),
        "bridge_id": task.bridge_id,
        "work_section_id": task.work_section_id,
        "structure_id": task.structure_id,
        "structure_name": task.structure_name,
        "side": location["side"] or "N",
        "side_label": location["side_label"],
    }


def _control_task_role(task: Task, object_type: str) -> str:
    if object_type == "main_pier_lower_structure":
        return "inherited_control_task"
    if task.component_type == "cast_in_place_continuous_beam" or task.structure_type == "continuous_beam":
        return "control_object_task"
    return "control_object_task"


def _control_display_task_name(task: Task) -> str:
    location = _task_location(task)
    structure_display_name = location["label"]
    if not location["side"] or location["side"] == "N":
        return task.name
    if task.name.startswith(structure_display_name):
        return task.name
    if task.structure_name and task.name.startswith(task.structure_name):
        return f"{structure_display_name}{task.name[len(task.structure_name):]}"
    side_label = location["side_label"]
    if task.name.startswith(side_label):
        return task.name
    return f"{side_label}{task.name}"


def _risk_number(risk: dict[str, Any] | None, key: str) -> int | None:
    if not risk:
        return None
    value = risk.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _risk_string(risk: dict[str, Any] | None, key: str, default: str = "") -> str:
    if not risk:
        return default
    value = risk.get(key)
    return value if isinstance(value, str) else default


def _worst_control_status(statuses: list[str]) -> str:
    if not statuses:
        return "not_evaluated"
    rank = {
        "not_evaluated": 0,
        "normal": 1,
        "near_risk": 2,
        "buffer_insufficient": 3,
        "affected_node": 4,
    }
    return max(statuses, key=lambda status: rank.get(status, 0))


def _downstream_control_targets(
    *,
    task_id: str,
    successors_by_predecessor: dict[str, list[str]],
    target_ids: set[str],
    control_chain_task_ids: set[str],
) -> list[str]:
    visited = {task_id}
    stack = list(successors_by_predecessor.get(task_id, []))
    targets: set[str] = set()
    while stack:
        current_id = stack.pop()
        if current_id in visited:
            continue
        visited.add(current_id)
        if current_id in target_ids:
            targets.add(current_id)
        if current_id not in control_chain_task_ids:
            continue
        stack.extend(successors_by_predecessor.get(current_id, []))
    return sorted(targets)


def _build_layered_control_diagnostics(
    *,
    schedule_input: ScheduleInput,
    scheduled_by_id: dict[str, ScheduledTask],
    target_ids: set[str],
    control_chain_task_ids: set[str],
    control_buffer_risks: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    task_by_id = {task.id: task for task in schedule_input.tasks}
    risk_by_task_id = {str(item.get("task_id")): item for item in control_buffer_risks if item.get("task_id")}
    successors_by_predecessor: dict[str, list[str]] = defaultdict(list)
    continuous_linked_structure_ids: set[str] = set()
    for link in schedule_input.precedence_links:
        if link.predecessor_id in task_by_id and link.successor_id in task_by_id:
            successors_by_predecessor[link.predecessor_id].append(link.successor_id)
        predecessor = task_by_id.get(link.predecessor_id)
        successor = task_by_id.get(link.successor_id)
        if (
            predecessor is not None
            and successor is not None
            and (successor.component_type == "cast_in_place_continuous_beam" or successor.structure_type == "continuous_beam")
        ):
            continuous_linked_structure_ids.add(predecessor.structure_id)

    object_by_id: dict[str, dict[str, Any]] = {}
    object_ref_by_target_id: dict[str, dict[str, Any]] = {}
    ordered_target_tasks = sorted(
        (scheduled_by_id[task_id] for task_id in target_ids if task_id in scheduled_by_id),
        key=lambda item: (item.start_offset, item.id),
    )
    for task in ordered_target_tasks:
        ref = _control_object_ref(task, continuous_linked_structure_ids)
        object_ref_by_target_id[task.id] = ref
        item = object_by_id.setdefault(
            ref["id"],
            {
                **ref,
                "task_ids": [],
                "start_offset": task.start_offset,
                "finish_offset": task.end_offset,
                "start_date": task.start_date,
                "finish_date": task.finish_date,
            },
        )
        item["task_ids"].append(task.id)
        if task.start_offset < item["start_offset"]:
            item["start_offset"] = task.start_offset
            item["start_date"] = task.start_date
        if task.end_offset > item["finish_offset"]:
            item["finish_offset"] = task.end_offset
            item["finish_date"] = task.finish_date

    control_object_tasks: list[dict[str, Any]] = []
    for task in ordered_target_tasks:
        ref = object_ref_by_target_id[task.id]
        risk = risk_by_task_id.get(task.id)
        role = _control_task_role(task, ref["object_type"])
        source = ref["source"]
        control_object_tasks.append(
            {
                "task_id": task.id,
                "task_name": _control_display_task_name(task),
                "object_id": ref["id"],
                "object_name": ref["name"],
                "task_role": role,
                "source": source,
                "source_label": _control_source_label(source),
                "control_level": task.control_level,
                "component_type": task.component_type,
                "start_date": task.start_date,
                "finish_date": task.finish_date,
                "latest_safe_finish_date": risk.get("latest_safe_finish_date") if risk else None,
                "remaining_buffer_days": _risk_number(risk, "remaining_buffer_days"),
                "buffer_risk_days": _risk_number(risk, "buffer_risk_days") or 0,
                "status": _risk_string(risk, "status", "not_evaluated"),
            }
        )

    control_objects: list[dict[str, Any]] = []
    for item in object_by_id.values():
        task_risks = [risk_by_task_id.get(task_id) for task_id in item["task_ids"]]
        remaining_values = [
            value
            for value in (_risk_number(risk, "remaining_buffer_days") for risk in task_risks)
            if value is not None
        ]
        risk_values = [_risk_number(risk, "buffer_risk_days") or 0 for risk in task_risks]
        statuses = [_risk_string(risk, "status", "not_evaluated") for risk in task_risks if risk]
        control_objects.append(
            {
                **{key: value for key, value in item.items() if key not in {"task_ids"}},
                "task_count": len(item["task_ids"]),
                "task_ids": list(item["task_ids"]),
                "remaining_buffer_days": min(remaining_values) if remaining_values else None,
                "buffer_risk_days": max(risk_values, default=0),
                "status": _worst_control_status(statuses),
            }
        )

    control_chain_predecessors: list[dict[str, Any]] = []
    for task in sorted(
        (scheduled_by_id[task_id] for task_id in control_chain_task_ids - target_ids if task_id in scheduled_by_id),
        key=lambda item: (item.start_offset, item.id),
    ):
        impacted_targets = _downstream_control_targets(
            task_id=task.id,
            successors_by_predecessor=successors_by_predecessor,
            target_ids=target_ids,
            control_chain_task_ids=control_chain_task_ids,
        )
        impacted_objects = []
        seen_object_ids: set[str] = set()
        for target_id in impacted_targets:
            ref = object_ref_by_target_id.get(target_id)
            if ref is None or ref["id"] in seen_object_ids:
                continue
            impacted_objects.append({"id": ref["id"], "name": ref["name"]})
            seen_object_ids.add(ref["id"])
        risk = risk_by_task_id.get(task.id)
        source = "control_chain_predecessor"
        control_chain_predecessors.append(
            {
                "task_id": task.id,
                "task_name": _control_display_task_name(task),
                "source": source,
                "source_label": _control_source_label(source),
                "control_level": task.control_level,
                "component_type": task.component_type,
                "start_date": task.start_date,
                "finish_date": task.finish_date,
                "latest_safe_finish_date": risk.get("latest_safe_finish_date") if risk else None,
                "remaining_buffer_days": _risk_number(risk, "remaining_buffer_days"),
                "buffer_risk_days": _risk_number(risk, "buffer_risk_days") or 0,
                "status": _risk_string(risk, "status", "not_evaluated"),
                "deadline_source": _risk_string(risk, "deadline_source"),
                "impacted_control_objects": impacted_objects,
            }
        )

    return {
        "control_objects": sorted(control_objects, key=lambda item: (item["start_offset"], item["id"])),
        "control_object_tasks": control_object_tasks,
        "control_chain_predecessors": control_chain_predecessors,
    }


def _normal_balance_status(metrics: dict[str, Any]) -> str:
    if metrics.get("normal_task_count", 0) <= 0:
        return "not_evaluated"
    score = int(metrics.get("balance_score", 0))
    if score >= 80:
        return "balanced"
    bucket_loads = metrics.get("bucket_loads") or []
    if len(bucket_loads) >= 2:
        first = int(bucket_loads[0].get("task_count", 0))
        last = int(bucket_loads[-1].get("task_count", 0))
        peak = int(metrics.get("peak_task_count", 0))
        if last == peak and last > first:
            return "backloaded"
    return "concentrated"


def _resource_path_status(metrics: dict[str, Any]) -> str:
    if metrics.get("resource_path_count", 0) <= 0:
        return "not_evaluated"
    abnormal = int(metrics.get("cross_side_jump_count", 0)) + int(metrics.get("direction_reversal_count", 0))
    if abnormal > 0:
        return "abnormal_jump"
    jumps = int(metrics.get("jump_pier_count", 0)) + int(metrics.get("side_switch_count", 0)) + int(metrics.get("path_group_switch_count", 0))
    if jumps > 0:
        return "reasonable_jump"
    return "smooth"


def _build_normal_balance_terms(
    model: Any,
    starts: dict[str, Any],
    tasks: list[Task],
    baseline_result: ScheduleResult,
    config: Any,
    horizon: int,
) -> list[Any]:
    normal_tasks = sorted(
        [task for task in tasks if task.control_level == "normal"],
        key=_task_spatial_sort_key,
    )
    if len(normal_tasks) <= 1:
        return []
    baseline_by_id = {task.id: task for task in baseline_result.tasks}
    earliest = config.normal_earliest_start_offset
    baseline_latest = max((baseline_by_id[task.id].end_offset for task in normal_tasks if task.id in baseline_by_id), default=0)
    latest = config.normal_latest_finish_offset or max(
        baseline_latest,
        earliest + max(1, len(normal_tasks) - 1) * max(1, math.ceil(sum(task.duration_days for task in normal_tasks) / len(normal_tasks))),
    )
    latest = min(horizon, max(latest, earliest + 1))
    span = max(1, latest - earliest)
    terms = []
    for rank, task in enumerate(normal_tasks):
        target = earliest + round(rank * span / max(1, len(normal_tasks) - 1))
        deviation = model.NewIntVar(0, horizon, f"normal_balance_dev_{rank}_{_safe(task.id)}")
        model.AddAbsEquality(deviation, starts[task.id] - target)
        terms.append(deviation)
    return terms


def _build_resource_organization_terms(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    enabled_resources: list[Resource],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
    horizon: int,
) -> dict[str, list[Any]]:
    assignments_by_resource: dict[str, list[tuple[Task, Any]]] = defaultdict(list)
    for task in tasks:
        for resource in resource_candidates.get(task.id, []):
            assignment = assignment_vars.get((task.id, resource.id))
            if assignment is not None:
                assignments_by_resource[resource.id].append((task, assignment))

    resources_with_assignments = [
        resource for resource in sorted(enabled_resources, key=_resource_sort_key) if assignments_by_resource.get(resource.id)
    ]
    resources_by_type: dict[str, list[Resource]] = defaultdict(list)
    workload_by_resource: dict[str, Any] = {}
    used_by_resource: dict[str, Any] = {}
    idle_terms: list[Any] = []

    for resource in resources_with_assignments:
        task_assignments = assignments_by_resource[resource.id]
        assignment_bools = [assignment for _, assignment in task_assignments]
        total_work = sum(task.duration_days for task, _ in task_assignments)
        workload = model.NewIntVar(0, total_work, f"resource_workload_{_safe(resource.id)}")
        model.Add(workload == sum(task.duration_days * assignment for task, assignment in task_assignments))

        used = model.NewBoolVar(f"resource_used_{_safe(resource.id)}")
        for assignment in assignment_bools:
            model.Add(assignment <= used)
        model.Add(sum(assignment_bools) >= used)

        first_start = model.NewIntVar(0, horizon, f"resource_first_start_{_safe(resource.id)}")
        last_end = model.NewIntVar(0, horizon, f"resource_last_end_{_safe(resource.id)}")
        active_span = model.NewIntVar(0, horizon, f"resource_active_span_{_safe(resource.id)}")
        idle_days = model.NewIntVar(0, horizon, f"resource_idle_days_{_safe(resource.id)}")
        for task, assignment in task_assignments:
            model.Add(first_start <= starts[task.id]).OnlyEnforceIf(assignment)
            model.Add(last_end >= ends[task.id]).OnlyEnforceIf(assignment)
        model.Add(first_start == 0).OnlyEnforceIf(used.Not())
        model.Add(last_end == 0).OnlyEnforceIf(used.Not())
        model.Add(last_end >= first_start)
        model.Add(active_span == last_end - first_start)
        model.Add(idle_days == active_span - workload)

        resources_by_type[resource.type].append(resource)
        workload_by_resource[resource.id] = workload
        used_by_resource[resource.id] = used
        idle_terms.append(idle_days)

    workload_balance_terms: list[Any] = []
    for resource_type, resources in resources_by_type.items():
        workloads = [workload_by_resource[resource.id] for resource in resources if resource.id in workload_by_resource]
        if len(workloads) <= 1:
            continue
        total_work = sum(
            task.duration_days
            for task in tasks
            if any(resource.type == resource_type for resource in resource_candidates.get(task.id, []))
        )
        max_workload = model.NewIntVar(0, total_work, f"resource_max_workload_{_safe(resource_type)}")
        min_workload = model.NewIntVar(0, total_work, f"resource_min_workload_{_safe(resource_type)}")
        workload_range = model.NewIntVar(0, total_work, f"resource_workload_range_{_safe(resource_type)}")
        model.AddMaxEquality(max_workload, workloads)
        model.AddMinEquality(min_workload, workloads)
        model.Add(workload_range == max_workload - min_workload)
        workload_balance_terms.append(workload_range)

    path_terms = _build_resource_path_continuity_terms(
        model,
        assignments_by_resource,
        used_by_resource,
    )

    return {
        "workload_balance_terms": workload_balance_terms,
        "idle_terms": idle_terms,
        "path_terms": path_terms["path_terms"],
        "path_group_terms": path_terms["path_group_terms"],
        "spatial_gap_terms": path_terms["spatial_gap_terms"],
    }


def _build_resource_path_continuity_terms(
    model: Any,
    assignments_by_resource: dict[str, list[tuple[Task, Any]]],
    used_by_resource: dict[str, Any],
) -> dict[str, list[Any]]:
    path_group_terms: list[Any] = []
    spatial_gap_terms: list[Any] = []

    for resource_id, task_assignments in assignments_by_resource.items():
        resource_used = used_by_resource.get(resource_id)
        if resource_used is None:
            continue
        task_assignments_by_group: dict[str, list[tuple[Task, Any]]] = defaultdict(list)
        for task, assignment in task_assignments:
            task_assignments_by_group[_task_path_group_key_for_resource(task, resource_id)].append((task, assignment))

        group_used_vars = []
        for group_index, group_task_assignments in enumerate(task_assignments_by_group.values()):
            group_assignments = [assignment for _, assignment in group_task_assignments]
            group_used = model.NewBoolVar(f"resource_path_group_used_{_safe(resource_id)}_{group_index}")
            for assignment in group_assignments:
                model.Add(assignment <= group_used)
            model.Add(sum(group_assignments) >= group_used)
            group_used_vars.append(group_used)
            spatial_gap = _resource_path_group_spatial_gap_term(
                model,
                resource_id=resource_id,
                group_index=group_index,
                group_used=group_used,
                task_assignments=group_task_assignments,
            )
            if spatial_gap is not None:
                spatial_gap_terms.append(spatial_gap)

        if len(group_used_vars) > 1:
            excess_groups = model.NewIntVar(0, len(group_used_vars) - 1, f"resource_path_group_excess_{_safe(resource_id)}")
            model.Add(excess_groups == sum(group_used_vars) - resource_used)
            path_group_terms.append(excess_groups)

    return {
        "path_terms": path_group_terms + spatial_gap_terms,
        "path_group_terms": path_group_terms,
        "spatial_gap_terms": spatial_gap_terms,
    }


def _resource_path_group_spatial_gap_term(
    model: Any,
    *,
    resource_id: str,
    group_index: int,
    group_used: Any,
    task_assignments: list[tuple[Task, Any]],
) -> Any | None:
    tasks_by_structure: dict[str, list[tuple[Task, Any]]] = defaultdict(list)
    sort_key_by_structure: dict[str, tuple[Any, ...]] = {}
    for task, assignment in task_assignments:
        location = _task_location(task)
        if location["support_index"] is None:
            continue
        tasks_by_structure[task.structure_id].append((task, assignment))
        sort_key_by_structure.setdefault(
            task.structure_id,
            _continuity_location_sort_key(task, location, include_side=True),
        )

    if len(tasks_by_structure) <= 1:
        return None

    ranked_structure_ids = sorted(sort_key_by_structure, key=lambda item: (sort_key_by_structure[item], item))
    rank_by_structure = {structure_id: rank for rank, structure_id in enumerate(ranked_structure_ids)}
    location_used_vars = []
    for structure_id in ranked_structure_ids:
        assignments = [assignment for _, assignment in tasks_by_structure[structure_id]]
        location_used = model.NewBoolVar(
            f"resource_path_location_used_{_safe(resource_id)}_{group_index}_{_safe(structure_id)}"
        )
        for assignment in assignments:
            model.Add(assignment <= location_used)
        model.Add(sum(assignments) >= location_used)
        location_used_vars.append(location_used)

    max_rank_value = len(ranked_structure_ids) - 1
    min_rank = model.NewIntVar(0, max_rank_value, f"resource_path_min_rank_{_safe(resource_id)}_{group_index}")
    max_rank = model.NewIntVar(0, max_rank_value, f"resource_path_max_rank_{_safe(resource_id)}_{group_index}")
    for structure_id, location_used in zip(ranked_structure_ids, location_used_vars):
        rank = rank_by_structure[structure_id]
        model.Add(min_rank <= rank).OnlyEnforceIf(location_used)
        model.Add(max_rank >= rank).OnlyEnforceIf(location_used)
    model.Add(min_rank == 0).OnlyEnforceIf(group_used.Not())
    model.Add(max_rank == 0).OnlyEnforceIf(group_used.Not())
    model.Add(max_rank >= min_rank)

    location_span = model.NewIntVar(0, len(ranked_structure_ids), f"resource_path_location_span_{_safe(resource_id)}_{group_index}")
    gap = model.NewIntVar(0, len(ranked_structure_ids), f"resource_path_location_gap_{_safe(resource_id)}_{group_index}")
    model.Add(location_span == max_rank - min_rank + group_used)
    model.Add(gap == location_span - sum(location_used_vars))
    return gap


def _task_path_group_key_for_resource(task: Task, resource_id: str) -> str:
    location = _task_location(task)
    resource_type = "|".join(sorted(task.compatible_resource_types))
    if "_" in resource_id:
        resource_type = resource_id.rsplit("_", 1)[0]
    key_parts = (
        task.bridge_id or "",
        task.work_section_id or "",
        location["side"] or "N",
        resource_type,
        task.component_type,
        task.process_name,
    )
    return "|".join(str(part) for part in key_parts)


def _is_control_milestone(milestone: MilestoneConstraint) -> bool:
    return milestone.level == "control" or milestone.mode == "hard" or bool(milestone.related_structure_ids)


def _is_control_milestone_result(milestone: MilestoneResult) -> bool:
    return milestone.level == "control" or milestone.mode == "hard"


def _build_normal_balance_metrics(scheduled_tasks: list[ScheduledTask], config: Any) -> dict[str, Any]:
    normal_tasks = [task for task in scheduled_tasks if task.control_level == "normal"]
    bucket_size = 7 if config.normal_balance_bucket == "week" else 30
    if not normal_tasks:
        return {
            "bucket": config.normal_balance_bucket,
            "bucket_size_days": bucket_size,
            "normal_task_count": 0,
            "bucket_loads": [],
            "peak_task_count": 0,
            "min_task_count": 0,
            "balance_score": 100,
        }
    min_bucket = min(task.start_offset // bucket_size for task in normal_tasks)
    max_bucket = max(task.start_offset // bucket_size for task in normal_tasks)
    bucket_loads = []
    task_counts = []
    for bucket in range(min_bucket, max_bucket + 1):
        bucket_tasks = [task for task in normal_tasks if task.start_offset // bucket_size == bucket]
        count = len(bucket_tasks)
        task_counts.append(count)
        bucket_loads.append(
            {
                "bucket_index": bucket,
                "start_offset": bucket * bucket_size,
                "finish_offset": (bucket + 1) * bucket_size,
                "task_count": count,
                "duration_days": sum(task.duration_days for task in bucket_tasks),
                "resource_types": sorted({task.assigned_resource_type or "" for task in bucket_tasks if task.assigned_resource_type}),
            }
        )
    peak = max(task_counts, default=0)
    low = min(task_counts, default=0)
    score = max(0, 100 - (peak - low) * 10)
    return {
        "bucket": config.normal_balance_bucket,
        "bucket_size_days": bucket_size,
        "normal_task_count": len(normal_tasks),
        "bucket_loads": bucket_loads,
        "peak_task_count": peak,
        "min_task_count": low,
        "balance_score": score,
    }


def _build_resource_organization_analysis(
    scheduled_tasks: list[ScheduledTask],
    enabled_resources: list[Resource],
    *,
    objective_days: int | None,
    continuity_metrics: dict[str, Any],
) -> dict[str, Any]:
    tasks_by_resource: dict[str, list[ScheduledTask]] = defaultdict(list)
    for task in scheduled_tasks:
        if task.assigned_resource_id:
            tasks_by_resource[task.assigned_resource_id].append(task)

    path_by_resource = {
        str(path.get("resource_id")): path
        for path in continuity_metrics.get("resource_paths", [])
        if isinstance(path, dict) and path.get("resource_id")
    }
    resource_items: list[dict[str, Any]] = []
    resources_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    project_days = max(1, int(objective_days or 0))

    for resource in sorted(enabled_resources, key=_resource_sort_key):
        ordered = sorted(
            tasks_by_resource.get(resource.id, []),
            key=lambda task: (task.start_offset, task.end_offset, *_task_spatial_sort_key(task)),
        )
        active_days = sum(task.end_offset - task.start_offset for task in ordered)
        first_start = ordered[0].start_offset if ordered else None
        last_end = ordered[-1].end_offset if ordered else None
        active_span = (last_end - first_start) if first_start is not None and last_end is not None else 0
        positive_gaps = [
            max(0, current.start_offset - previous.end_offset)
            for previous, current in zip(ordered, ordered[1:])
            if current.start_offset > previous.end_offset
        ]
        idle_days = sum(positive_gaps)
        path = path_by_resource.get(resource.id, {})
        item = {
            "resource_id": resource.id,
            "resource_name": resource.name,
            "resource_type": resource.type,
            "same_structure_resource_binding": resource.same_structure_resource_binding,
            "same_structure_parallel_limit": resource.same_structure_parallel_limit,
            "parallel_rule_description": resource.parallel_rule_description,
            "task_count": len(ordered),
            "active_days": active_days,
            "first_start_offset": first_start,
            "last_end_offset": last_end,
            "active_span_days": active_span,
            "idle_days": idle_days,
            "max_idle_gap_days": max(positive_gaps) if positive_gaps else 0,
            "idle_gap_count": len(positive_gaps),
            "utilization_within_span": round(active_days / active_span, 4) if active_span else 0,
            "project_utilization": round(active_days / project_days, 4) if project_days else 0,
            "jump_pier_count": int(path.get("jump_pier_count") or 0),
            "side_switch_count": int(path.get("side_switch_count") or 0),
            "cross_side_jump_count": int(path.get("cross_side_jump_count") or 0),
            "path_group_switch_count": int(path.get("path_group_switch_count") or 0),
        }
        resource_items.append(item)
        resources_by_type[resource.type].append(item)

    type_items: list[dict[str, Any]] = []
    balance_statuses: list[str] = []
    idle_statuses: list[str] = []
    for resource_type, resources in sorted(resources_by_type.items()):
        workloads = [int(item["active_days"]) for item in resources]
        used = [item for item in resources if int(item["active_days"]) > 0]
        total_workload = sum(workloads)
        max_workload = max(workloads) if workloads else 0
        min_workload = min(workloads) if workloads else 0
        average_workload = total_workload / len(workloads) if workloads else 0
        workload_range = max_workload - min_workload
        parallel_limits = [
            int(item["same_structure_parallel_limit"])
            for item in resources
            if item.get("same_structure_parallel_limit") is not None
        ]
        balance_status = _resource_workload_balance_status(
            resource_count=len(resources),
            used_resource_count=len(used),
            average_workload=average_workload,
            workload_range=workload_range,
        )
        idle_status = _resource_idle_status(resources)
        balance_statuses.append(balance_status)
        idle_statuses.append(idle_status)
        type_items.append(
            {
                "resource_type": resource_type,
                "resource_count": len(resources),
                "used_resource_count": len(used),
                "same_structure_resource_binding": any(
                    bool(item.get("same_structure_resource_binding")) for item in resources
                ),
                "same_structure_parallel_limit": min(parallel_limits) if parallel_limits else None,
                "parallel_rule_description": next(
                    (str(item.get("parallel_rule_description")) for item in resources if item.get("parallel_rule_description")),
                    "",
                ),
                "task_count": sum(int(item["task_count"]) for item in resources),
                "active_days": total_workload,
                "min_workload_days": min_workload,
                "max_workload_days": max_workload,
                "average_workload_days": round(average_workload, 2),
                "workload_range_days": workload_range,
                "idle_days": sum(int(item["idle_days"]) for item in resources),
                "max_idle_gap_days": max((int(item["max_idle_gap_days"]) for item in resources), default=0),
                "jump_pier_count": sum(int(item["jump_pier_count"]) for item in resources),
                "side_switch_count": sum(int(item["side_switch_count"]) for item in resources),
                "path_group_switch_count": sum(int(item["path_group_switch_count"]) for item in resources),
                "balance_status": balance_status,
                "idle_status": idle_status,
            }
        )

    return {
        "resource_count": len(resource_items),
        "used_resource_count": sum(1 for item in resource_items if int(item["active_days"]) > 0),
        "resource_balance_status": _worst_resource_status(balance_statuses),
        "resource_idle_status": _worst_resource_status(idle_statuses),
        "resources": resource_items,
        "resource_types": type_items,
    }


def _resource_workload_balance_status(
    *,
    resource_count: int,
    used_resource_count: int,
    average_workload: float,
    workload_range: int,
) -> str:
    if resource_count <= 1 or average_workload <= 0:
        return "not_evaluated"
    if used_resource_count < resource_count:
        return "under_used"
    if workload_range <= max(1, math.ceil(average_workload * 0.25)):
        return "balanced"
    if workload_range <= max(2, math.ceil(average_workload * 0.5)):
        return "slightly_unbalanced"
    return "unbalanced"


def _resource_idle_status(resources: list[dict[str, Any]]) -> str:
    active_resources = [item for item in resources if int(item["active_days"]) > 0]
    if not active_resources:
        return "not_evaluated"
    worst_ratio = max(
        (
            (float(item["idle_days"]) / float(item["active_span_days"]))
            if float(item["active_span_days"] or 0) > 0
            else 0
        )
        for item in active_resources
    )
    max_gap = max(int(item["max_idle_gap_days"]) for item in active_resources)
    if max_gap >= 30 or worst_ratio >= 0.35:
        return "idle_risk"
    if max_gap >= 7 or worst_ratio >= 0.15:
        return "minor_idle"
    return "continuous"


def _worst_resource_status(statuses: list[str]) -> str:
    if not statuses:
        return "not_evaluated"
    rank = {
        "not_evaluated": 0,
        "balanced": 1,
        "continuous": 1,
        "slightly_unbalanced": 2,
        "minor_idle": 2,
        "under_used": 3,
        "unbalanced": 4,
        "idle_risk": 4,
    }
    return max(statuses, key=lambda status: rank.get(status, 0))


def _build_control_priority_analysis(
    *,
    schedule_input: ScheduleInput,
    baseline_result: ScheduleResult,
    scheduled_tasks: list[ScheduledTask],
    allocations: list[ResourceAllocation],
    milestone_results: list[MilestoneResult],
    control_chain_task_ids: set[str],
    control_buffer_risks: list[dict[str, Any]],
    continuity_metrics: dict[str, Any],
    normal_balance_metrics: dict[str, Any],
    resource_organization_analysis: dict[str, Any],
) -> dict[str, Any]:
    baseline_by_id = {task.id: task for task in baseline_result.tasks}
    scheduled_by_id = {task.id: task for task in scheduled_tasks}
    target_ids = _control_target_task_ids(schedule_input)
    level_counts: dict[str, int] = defaultdict(int)
    for task in scheduled_tasks:
        level_counts[task.control_level] += 1
    control_allocations = [
        allocation
        for allocation in allocations
        if allocation.task_id in control_chain_task_ids
    ]
    resource_stats: dict[str, dict[str, Any]] = {}
    for allocation in control_allocations:
        item = resource_stats.setdefault(
            allocation.resource_type,
            {"resource_type": allocation.resource_type, "task_count": 0, "duration_days": 0, "resource_names": set()},
        )
        item["task_count"] += 1
        item["duration_days"] += allocation.end_offset - allocation.start_offset
        item["resource_names"].add(allocation.resource_name)
    bottlenecks = [
        {
            **item,
            "resource_names": sorted(item["resource_names"]),
        }
        for item in resource_stats.values()
    ]
    bottlenecks.sort(key=lambda item: (-item["duration_days"], item["resource_type"]))

    explanations = []
    for task in scheduled_tasks:
        baseline_task = baseline_by_id.get(task.id)
        if not baseline_task:
            continue
        delta = task.start_offset - baseline_task.start_offset
        if delta >= 1 and task.control_level == "normal":
            explanations.append(
                {
                    "task_id": task.id,
                    "task_name": _control_display_task_name(task),
                    "change_days": delta,
                    "direction": "delayed",
                    "reason": "普通工程让位于控制性工程资源保障，并按均衡节奏推进。",
                }
            )
        elif delta <= -1 and task.id in control_chain_task_ids:
            explanations.append(
                {
                    "task_id": task.id,
                    "task_name": _control_display_task_name(task),
                    "change_days": abs(delta),
                    "direction": "advanced",
                    "reason": "该工作项属于控制性工程链，策略优先压缩其资源等待和节点风险。",
                }
            )
        if len(explanations) >= 30:
            break

    milestone_summaries = []
    for result in milestone_results:
        slack_days = None
        if result.actual_offset is not None:
            slack_days = _target_offset(schedule_input.start_date, result) - result.actual_offset
        milestone_summaries.append(
            {
                "id": result.id,
                "name": result.name,
                "target_date": result.target_date,
                "actual_date": result.actual_date,
                "slack_days": slack_days,
                "lateness_days": result.lateness_days,
                "status": result.status,
                "is_control": _is_control_milestone_result(result),
            }
        )

    late_control = [item for item in milestone_summaries if item["is_control"] and item["lateness_days"] > 0]
    resource_increment_suggestions = [
        {
            "resource_type": item["resource_type"],
            "suggested_added_quantity": 1,
            "reason": "控制性节点仍有延期风险，建议优先测算该瓶颈资源增量。",
        }
        for item in bottlenecks[:3]
    ] if late_control else []
    layered_control = _build_layered_control_diagnostics(
        schedule_input=schedule_input,
        scheduled_by_id=scheduled_by_id,
        target_ids=target_ids,
        control_chain_task_ids=control_chain_task_ids,
        control_buffer_risks=control_buffer_risks,
    )

    return {
        "control_task_count": len(control_chain_task_ids),
        "control_level_counts": dict(level_counts),
        **layered_control,
        "control_targets": [
            {
                "task_id": task.id,
                "task_name": _control_display_task_name(task),
                "control_level": task.control_level,
                "component_type": task.component_type,
                "source": _control_target_source(task),
            }
            for task in sorted(
                (scheduled_by_id[task_id] for task_id in target_ids if task_id in scheduled_by_id),
                key=lambda item: (item.start_offset, item.id),
            )
        ],
        "control_buffer_risks": control_buffer_risks[:50],
        "control_buffer_status": _control_buffer_status(control_buffer_risks),
        "normal_balance_status": _normal_balance_status(normal_balance_metrics),
        "resource_path_status": _resource_path_status(continuity_metrics),
        "resource_balance_status": resource_organization_analysis.get("resource_balance_status", "not_evaluated"),
        "resource_idle_status": resource_organization_analysis.get("resource_idle_status", "not_evaluated"),
        "resource_organization_analysis": resource_organization_analysis,
        "path_group_diagnostics": continuity_metrics.get("path_group_diagnostics", [])[:50],
        "milestones": milestone_summaries,
        "bottleneck_resources": bottlenecks[:10],
        "resource_increment_suggestions": resource_increment_suggestions,
        "adjustment_explanations": explanations,
        "baseline_objective_days": baseline_result.objective_days,
        "baseline_finish_date": baseline_result.plan_finish_date,
        "strategy_task_finish_delta_days": (
            max((task.end_offset for task in scheduled_tasks), default=0)
            - (baseline_result.objective_days or 0)
        ),
        "control_task_ids": sorted(control_chain_task_ids),
        "scheduled_control_tasks": [
            {
                "task_id": task.id,
                "task_name": _control_display_task_name(task),
                "control_level": task.control_level,
                "start_date": task.start_date,
                "finish_date": task.finish_date,
                "resource_name": task.assigned_resource_name,
            }
            for task in sorted(
                (scheduled_by_id[task_id] for task_id in control_chain_task_ids if task_id in scheduled_by_id),
                key=lambda item: (item.start_offset, item.id),
            )[:50]
        ],
    }


def solve_capacity_shortest_schedule(schedule_input: ScheduleInput) -> ScheduleResult:
    enabled_resources = [resource for resource in schedule_input.resources if resource.enabled]
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=schedule_input.start_date,
            validation=[
                ValidationMessage(
                    level="error",
                    message="未安装 OR-Tools，请先安装后端依赖后再执行求解。",
                )
            ],
            stats={
                "reason": "ortools_missing",
                "solve_mode": "fixed_resource_capacity_shortest",
                "performance_path": "capacity_fast_path",
                "solver_call_count": 0,
                "capacity_precheck_status": "MODEL_INVALID",
                "warm_start_used": False,
            },
        )

    groups = _resource_groups(enabled_resources)
    fixed_counts = {group["key"]: int(group["max_quantity"]) for group in groups}
    solved = _solve_capacity_model(
        schedule_input,
        cp_model=cp_model,
        groups=groups,
        counts=fixed_counts,
        fallback_target_days=None,
        enforce_fixed_duration=False,
        minimize_makespan=True,
    )
    metadata = {
        "solve_mode": "fixed_resource_capacity_shortest",
        "schedule_source": "current_resources_capacity_shortest",
        "performance_path": "capacity_fast_path",
        "solver_call_count": 1,
        "capacity_precheck_status": solved["status"],
        "capacity_model_status": solved["status"],
        "capacity_model_group_counts": fixed_counts,
        "warm_start_used": False,
    }
    if solved["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return ScheduleResult(
            status=solved["status"],
            plan_start_date=schedule_input.start_date,
            milestone_results=_not_evaluated_milestones(schedule_input.milestones),
            validation=solved["validation"]
            + [
                ValidationMessage(
                    level="error",
                    message="池级固定资源最短工期快排未得到可行求解结果。",
                )
            ],
            stats={**solved["stats"], **metadata},
            objective_breakdown=metadata.copy(),
        )

    result = _capacity_model_result(schedule_input, solved, fixed_counts)
    result.stats.update(metadata)
    result.objective_breakdown.update(metadata)
    return result


def solve_min_resources_schedule(schedule_input: ScheduleInput, fallback_target_days: int | None = None) -> ScheduleResult:
    enabled_resources = [resource for resource in schedule_input.resources if resource.enabled]
    resource_candidates = _resource_candidates_by_task(schedule_input.tasks, enabled_resources)
    validation = _validate_resource_coverage(schedule_input.tasks, resource_candidates)
    if any(message.level == "error" for message in validation):
        return ScheduleResult(
            status="INFEASIBLE",
            plan_start_date=schedule_input.start_date,
            validation=validation,
            stats={"reason": "missing_compatible_resource", "solve_mode": "min_resources_fixed_duration"},
        )

    hard_match_count = _matched_hard_milestone_count(schedule_input)
    target_days = _min_resource_target_days(schedule_input, fallback_target_days)
    groups = _resource_groups(enabled_resources)
    capacity_window_days = _capacity_window_days(schedule_input, target_days)
    lower_bound_prune = _resource_capacity_exclusive_lower_bound_diagnostics(
        schedule_input,
        groups,
        capacity_window_days,
    )
    if any(item["exceeds_upper_bound"] for item in lower_bound_prune):
        critical_path = _critical_path_schedule(schedule_input)
        checked = {
            "status": "INFEASIBLE",
            "validation": [],
            "stats": {
                "capacity_precheck_status": "exclusive_lower_bound_infeasible",
                "lower_bound_prune_used": True,
                "solver_call_count": 0,
                "wall_time_seconds": 0.0,
                "conflicts": 0,
                "branches": 0,
                "random_seed": SCHEDULER_RANDOM_SEED,
                "search_workers": _scheduler_search_workers(),
            },
        }
        result = _fixed_duration_infeasible_result(
            schedule_input=schedule_input,
            checked=checked,
            critical_path=critical_path,
            validation=validation,
            groups=groups,
            target_days=target_days,
            capacity_window_days=capacity_window_days,
        )
        metadata = {
            "capacity_precheck_status": "exclusive_lower_bound_infeasible",
            "lower_bound_prune_used": True,
            "solver_call_count": 0,
        }
        result.stats.update(metadata)
        result.objective_breakdown.update(metadata)
        return result
    if hard_match_count == 0 and target_days is None:
        return ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=schedule_input.start_date,
            validation=validation
            + _unmatched_hard_milestone_warnings(schedule_input)
            + [
                ValidationMessage(
                    level="error",
                    message="固定工期推算最少资源需要至少一个可匹配的强制里程碑目标，或先运行固定资源最短工期作为目标工期。",
                )
            ],
            stats={"reason": "missing_target_duration", "solve_mode": "min_resources_fixed_duration"},
        )

    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=schedule_input.start_date,
            validation=[ValidationMessage(level="error", message="未安装 OR-Tools，请先安装后端依赖再执行求解。")],
            stats={"reason": "ortools_missing", "solve_mode": "min_resources_fixed_duration"},
        )

    fixed_duration_check = _solve_capacity_model(
        schedule_input,
        cp_model=cp_model,
        groups=groups,
        counts={group["key"]: group["max_quantity"] for group in groups},
        fallback_target_days=target_days if hard_match_count == 0 else None,
        enforce_fixed_duration=True,
    )
    if fixed_duration_check["status"] in {"INFEASIBLE", "MODEL_INVALID"}:
        critical_path = _critical_path_schedule(schedule_input)
        capacity_window_days = _capacity_window_days(schedule_input, target_days)
        return _fixed_duration_infeasible_result(
            schedule_input=schedule_input,
            checked=fixed_duration_check,
            critical_path=critical_path,
            validation=validation,
            groups=groups,
            target_days=target_days,
            capacity_window_days=capacity_window_days,
        )
    if fixed_duration_check["status"] == "UNKNOWN":
        validation.append(
            ValidationMessage(
                level="warning",
                message="最大资源可行性预检在限定时间内未完成，已改用逐资源池二分搜索继续推算。",
            )
        )

    global_capacity_optimization = _solve_capacity_model(
        schedule_input,
        cp_model=cp_model,
        groups=groups,
        counts=None,
        fallback_target_days=target_days if hard_match_count == 0 else None,
        enforce_fixed_duration=True,
        minimize_resource_count=True,
    )
    capacity_optimization = global_capacity_optimization
    if global_capacity_optimization["status"] == "UNKNOWN":
        validation.append(
            ValidationMessage(
                level="warning",
                message="全局最少资源优化在限定时间内未完成，已改用逐资源池二分搜索继续推算。",
            )
        )
        capacity_optimization = _solve_min_resource_counts_by_group_fallback(
            schedule_input,
            cp_model=cp_model,
            groups=groups,
            fixed_duration_check=fixed_duration_check,
            fallback_target_days=target_days if hard_match_count == 0 else None,
        )
    if capacity_optimization["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return ScheduleResult(
            status=capacity_optimization["status"],
            plan_start_date=schedule_input.start_date,
            validation=validation
            + capacity_optimization["validation"]
            + [
                ValidationMessage(
                    level="error",
                    message="在资源最大数量和目标工期约束下，未能联合推算可行的最少资源组合。",
                )
            ],
            stats={
                **capacity_optimization["stats"],
                "reason": "resource_count_optimization_failed",
                "solve_mode": "min_resources_fixed_duration",
                "target_days": target_days,
                "global_capacity_model_status": global_capacity_optimization["status"],
                "global_capacity_model_stats": global_capacity_optimization["stats"],
                "workface_parallelism_diagnostics": _workface_parallelism_diagnostics(schedule_input),
            },
        )

    fixed_counts = {key: int(value) for key, value in capacity_optimization["group_counts"].items()}
    phase_stats = [
        {"resource_pool_id": group["key"], "label": group["label"], "recommended_quantity": fixed_counts.get(group["key"], 0)}
        for group in groups
    ]

    recommended = _recommended_resource_counts(groups, fixed_counts)
    capacity_result = _capacity_model_result(schedule_input, capacity_optimization, fixed_counts)
    capacity_verified = _schedule_result_verified(
        capacity_result,
        target_days=target_days,
        hard_match_count=hard_match_count,
    )
    reoptimization_attempts = _run_min_resource_reoptimizations(
        schedule_input,
        fixed_counts,
        target_days=target_days,
        hard_match_count=hard_match_count,
        capacity_hint_result=capacity_result,
    )
    selected_attempt = _select_verified_reoptimization(
        reoptimization_attempts,
        target_days=target_days,
        hard_match_count=hard_match_count,
    )

    if selected_attempt is not None:
        result = selected_attempt["result"].model_copy(deep=True)
        selected_source = selected_attempt["source"]
        result.validation = validation + capacity_optimization["validation"] + result.validation
    elif capacity_verified:
        result = capacity_result.model_copy(deep=True)
        selected_source = "capacity_model_verified_schedule"
        result.validation = validation + result.validation
        result.validation.append(
            ValidationMessage(
                level="warning",
                message=(
                    "Minimum resource counts were verified by the capacity model. "
                    "Control-priority balanced reoptimization did not return a verified schedule within the solve limit, "
                    "so the verified capacity schedule is kept."
                ),
            )
        )
    else:
        result = capacity_result.model_copy(deep=True, update={"status": "INFEASIBLE"})
        selected_source = "capacity_model_unverified"
        result.validation = validation + result.validation
        result.validation.append(
            ValidationMessage(
                level="error",
                message=(
                    "Minimum resource counts were found, but neither the capacity-model schedule "
                    "nor control-priority reoptimization produced a verified executable schedule."
                ),
            )
        )

    metadata = {
        "solve_mode": "min_resources_fixed_duration",
        "target_days": target_days,
        "recommended_resource_counts": recommended,
        "resource_optimization_phases": phase_stats,
        "schedule_source": selected_source,
        "recommended_schedule_source": selected_source,
        "capacity_model_status": capacity_optimization["status"],
        "global_capacity_model_status": global_capacity_optimization["status"],
        "capacity_model_group_counts": fixed_counts,
        "capacity_model_stats": capacity_optimization["stats"],
        "capacity_verification_status": "verified" if capacity_verified else "failed",
        "balanced_reoptimization_status": _reoptimization_status(
            reoptimization_attempts,
            "control_priority_balanced_reoptimization",
        ),
        "unbalanced_reoptimization_status": _reoptimization_status(
            reoptimization_attempts,
            "control_priority_reoptimization_no_balance",
        ),
        "reoptimization_attempts": _reoptimization_attempt_summaries(
            reoptimization_attempts,
            target_days=target_days,
            hard_match_count=hard_match_count,
        ),
        "parallel_reoptimization_used": _reoptimization_parallelism(reoptimization_attempts) > 1,
        "resource_count_optimality": "optimal" if capacity_optimization["status"] == "OPTIMAL" else "feasible",
    }

    result.stats.update(metadata)
    result.objective_breakdown.update(metadata)
    return result


def _run_min_resource_reoptimizations(
    schedule_input: ScheduleInput,
    fixed_counts: dict[str, int],
    *,
    target_days: int | None,
    hard_match_count: int,
    capacity_hint_result: ScheduleResult | None = None,
) -> list[dict[str, Any]]:
    candidates = _min_resource_reoptimization_candidates(schedule_input, fixed_counts)
    parallelism = _solve_task_parallelism(len(candidates))

    def run(candidate: dict[str, Any]) -> dict[str, Any]:
        result = solve_control_priority_schedule(
            candidate["schedule_input"],
            enforce_hard_milestones=True,
            max_makespan_days=target_days if hard_match_count == 0 else None,
            warm_start_result=capacity_hint_result,
        )
        return {
            "source": candidate["source"],
            "result": result,
            "parallelism": parallelism,
        }

    if parallelism <= 1:
        results = []
        for candidate in sorted(candidates, key=lambda item: _reoptimization_priority(item["source"])):
            attempt = run(candidate)
            results.append(attempt)
            if _schedule_result_verified(
                attempt["result"],
                target_days=target_days,
                hard_match_count=hard_match_count,
            ):
                break
        return results

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = [executor.submit(run, candidate) for candidate in candidates]
        results = [future.result() for future in futures]
    return sorted(results, key=lambda item: _reoptimization_priority(item["source"]))


def _min_resource_reoptimization_candidates(
    schedule_input: ScheduleInput,
    fixed_counts: dict[str, int],
) -> list[dict[str, Any]]:
    resource_guarantee = schedule_input.schedule_strategy.resource_guarantee
    if resource_guarantee == "off":
        resource_guarantee = "priority"
    limited_resources = _apply_resource_limits(schedule_input.resources, fixed_counts)
    base_strategy = schedule_input.schedule_strategy.model_copy(
        update={
            "strategy": "comprehensive",
            "resource_guarantee": resource_guarantee,
        }
    )
    candidates = [
        {
            "source": "control_priority_balanced_reoptimization",
            "schedule_input": schedule_input.model_copy(
                update={
                    "resources": limited_resources,
                    "schedule_strategy": base_strategy,
                }
            ),
        }
    ]
    if base_strategy.enable_balance_objective:
        candidates.append(
            {
                "source": "control_priority_reoptimization_no_balance",
                "schedule_input": schedule_input.model_copy(
                    update={
                        "resources": limited_resources,
                        "schedule_strategy": base_strategy.model_copy(update={"enable_balance_objective": False}),
                    }
                ),
            }
        )
    return candidates


def _select_verified_reoptimization(
    attempts: list[dict[str, Any]],
    *,
    target_days: int | None,
    hard_match_count: int,
) -> dict[str, Any] | None:
    for attempt in sorted(attempts, key=lambda item: _reoptimization_priority(item["source"])):
        if _schedule_result_verified(attempt["result"], target_days=target_days, hard_match_count=hard_match_count):
            return attempt
    return None


def _schedule_result_verified(
    result: ScheduleResult,
    *,
    target_days: int | None,
    hard_match_count: int,
) -> bool:
    if result.status not in {"OPTIMAL", "FEASIBLE"}:
        return False
    if any(milestone.mode == "hard" and milestone.lateness_days > 0 for milestone in result.milestone_results):
        return False
    if hard_match_count == 0 and target_days is not None and (result.objective_days is None or result.objective_days > target_days):
        return False
    return not any(message.level == "error" for message in result.validation)


def _reoptimization_priority(source: str) -> int:
    priorities = {
        "control_priority_balanced_reoptimization": 0,
        "control_priority_reoptimization_no_balance": 1,
    }
    return priorities.get(source, 99)


def _reoptimization_status(attempts: list[dict[str, Any]], source: str) -> str:
    for attempt in attempts:
        if attempt["source"] == source:
            return attempt["result"].status
    return "not_attempted"


def _reoptimization_parallelism(attempts: list[dict[str, Any]]) -> int:
    return max((int(attempt.get("parallelism") or 1) for attempt in attempts), default=1)


def _reoptimization_attempt_summaries(
    attempts: list[dict[str, Any]],
    *,
    target_days: int | None,
    hard_match_count: int,
) -> list[dict[str, Any]]:
    summaries = []
    for attempt in attempts:
        result = attempt["result"]
        summaries.append(
            {
                "source": attempt["source"],
                "status": result.status,
                "verified": _schedule_result_verified(result, target_days=target_days, hard_match_count=hard_match_count),
                "objective_days": result.objective_days,
                "wall_time_seconds": result.stats.get("wall_time_seconds"),
                "conflicts": result.stats.get("conflicts"),
                "branches": result.stats.get("branches"),
                "search_workers": result.stats.get("search_workers"),
                "warm_start_used": result.stats.get("warm_start_used", False),
            }
        )
    return summaries


def _solve_min_resource_counts_by_group_fallback(
    schedule_input: ScheduleInput,
    *,
    cp_model: Any,
    groups: list[dict[str, Any]],
    fixed_duration_check: dict[str, Any],
    fallback_target_days: int | None,
) -> dict[str, Any]:
    max_counts = {group["key"]: int(group["max_quantity"]) for group in groups}
    attempts: list[dict[str, Any]] = []
    total_wall_time = 0.0
    total_conflicts = 0
    total_branches = 0

    def remember(label: str, solved: dict[str, Any], counts: dict[str, int]) -> None:
        nonlocal total_wall_time, total_conflicts, total_branches
        stats = solved.get("stats", {})
        total_wall_time += float(stats.get("wall_time_seconds", 0.0) or 0.0)
        total_conflicts += int(stats.get("conflicts", 0) or 0)
        total_branches += int(stats.get("branches", 0) or 0)
        attempts.append(
            {
                "phase": label,
                "status": solved.get("status"),
                "counts": dict(counts),
                "wall_time_seconds": stats.get("wall_time_seconds"),
                "conflicts": stats.get("conflicts"),
                "branches": stats.get("branches"),
            }
        )

    if fixed_duration_check["status"] in {"OPTIMAL", "FEASIBLE"}:
        best_counts = max_counts.copy()
        best_solution = fixed_duration_check
        remember("max_resources_precheck", fixed_duration_check, best_counts)
    else:
        max_check = _solve_capacity_model(
            schedule_input,
            cp_model=cp_model,
            groups=groups,
            counts=max_counts,
            fallback_target_days=fallback_target_days,
            enforce_fixed_duration=True,
        )
        remember("max_resources_retry", max_check, max_counts)
        if max_check["status"] not in {"OPTIMAL", "FEASIBLE"}:
            return {
                **max_check,
                "validation": max_check["validation"]
                + [
                    ValidationMessage(
                        level="error",
                        message="最大资源组合在回退搜索中仍未得到可验证排程，无法继续压缩资源数量。",
                    )
                ],
                "stats": {
                    **max_check["stats"],
                    "fallback_search_used": True,
                    "fallback_search_status": "max_resources_not_verified",
                    "fallback_search_attempts": attempts,
                    "wall_time_seconds": total_wall_time,
                    "conflicts": total_conflicts,
                    "branches": total_branches,
                },
            }
        best_counts = max_counts.copy()
        best_solution = max_check

    for group in groups:
        key = group["key"]
        low = 0
        high = int(best_counts.get(key, group["max_quantity"]))
        while low < high:
            mid = (low + high) // 2
            trial_counts = {**best_counts, key: mid}
            trial = _solve_capacity_model(
                schedule_input,
                cp_model=cp_model,
                groups=groups,
                counts=trial_counts,
                fallback_target_days=fallback_target_days,
                enforce_fixed_duration=True,
            )
            remember(f"binary_{key}_{mid}", trial, trial_counts)
            if trial["status"] in {"OPTIMAL", "FEASIBLE"}:
                best_counts = trial_counts
                best_solution = trial
                high = mid
            else:
                low = mid + 1

    return {
        **best_solution,
        "status": best_solution["status"],
        "group_counts": best_counts,
        "validation": best_solution["validation"]
        + [
            ValidationMessage(
                level="warning",
                message="已通过逐资源池二分搜索得到可验证的最少资源候选组合。",
            )
        ],
        "stats": {
            **best_solution["stats"],
            "fallback_search_used": True,
            "fallback_search_status": "verified",
            "fallback_search_attempts": attempts,
            "wall_time_seconds": total_wall_time,
            "conflicts": total_conflicts,
            "branches": total_branches,
        },
    }


def solve_resource_cost_schedule(
    schedule_input: ScheduleInput,
    resource_linear_costs_by_pool: dict[str, dict[str, Any]],
    fallback_target_days: int | None = None,
) -> ScheduleResult:
    enabled_resources = [resource for resource in schedule_input.resources if resource.enabled]
    resource_candidates = _resource_candidates_by_task(schedule_input.tasks, enabled_resources)
    validation = _validate_resource_coverage(schedule_input.tasks, resource_candidates)
    if any(message.level == "error" for message in validation):
        return ScheduleResult(
            status="INFEASIBLE",
            plan_start_date=schedule_input.start_date,
            validation=validation,
            stats={"reason": "missing_compatible_resource", "solve_mode": "resource_cost_optimization"},
        )

    hard_match_count = _matched_hard_milestone_count(schedule_input)
    target_days = _min_resource_target_days(schedule_input, fallback_target_days)
    if hard_match_count == 0 and target_days is None:
        return ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=schedule_input.start_date,
            validation=validation
            + _unmatched_hard_milestone_warnings(schedule_input)
            + [
                ValidationMessage(
                    level="error",
                    message="资源成本优化排程需要至少一个可匹配的强制里程碑目标，或先运行固定资源最短工期作为固定工期目标。",
                )
            ],
            stats={"reason": "missing_target_duration", "solve_mode": "resource_cost_optimization"},
        )

    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=schedule_input.start_date,
            validation=[ValidationMessage(level="error", message="未安装 OR-Tools，请先安装后端依赖再执行求解。")],
            stats={"reason": "ortools_missing", "solve_mode": "resource_cost_optimization"},
        )

    groups = _resource_groups(enabled_resources)
    normalized_costs = _normalized_resource_linear_costs(groups, resource_linear_costs_by_pool)
    fixed_duration_check = _solve_capacity_model(
        schedule_input,
        cp_model=cp_model,
        groups=groups,
        counts={group["key"]: group["max_quantity"] for group in groups},
        fallback_target_days=target_days if hard_match_count == 0 else None,
        enforce_fixed_duration=True,
    )
    if fixed_duration_check["status"] in {"INFEASIBLE", "MODEL_INVALID"}:
        critical_path = _critical_path_schedule(schedule_input)
        capacity_window_days = _capacity_window_days(schedule_input, target_days)
        result = _fixed_duration_infeasible_result(
            schedule_input=schedule_input,
            checked=fixed_duration_check,
            critical_path=critical_path,
            validation=validation,
            groups=groups,
            target_days=target_days,
            capacity_window_days=capacity_window_days,
        )
        result.stats.update(
            {
                "reason": "resource_cost_upper_bound_or_deadline_infeasible",
                "solve_mode": "resource_cost_optimization",
                "target_days": target_days,
            }
        )
        result.objective_breakdown.update(
            {
                "solve_mode": "resource_cost_optimization",
                "target_days": target_days,
            }
        )
        return result
    if fixed_duration_check["status"] == "UNKNOWN":
        validation.append(
            ValidationMessage(
                level="warning",
                message="最大资源固定工期可行性预检在限定时间内未完成，已继续尝试资源成本优化。",
            )
        )

    cost_optimization = _solve_capacity_model(
        schedule_input,
        cp_model=cp_model,
        groups=groups,
        counts=None,
        fallback_target_days=target_days if hard_match_count == 0 else None,
        enforce_fixed_duration=True,
        minimize_total_cost=True,
        resource_linear_costs_by_group=normalized_costs,
    )
    if cost_optimization["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return ScheduleResult(
            status=cost_optimization["status"],
            plan_start_date=schedule_input.start_date,
            validation=validation
            + cost_optimization["validation"]
            + [
                ValidationMessage(
                    level="error",
                    message="在线性资源成本、资源上限、工艺逻辑和固定工期约束下，未能找到可行的资源成本优化排程。",
                )
            ],
            stats={
                **cost_optimization["stats"],
                "reason": "resource_cost_optimization_failed",
                "solve_mode": "resource_cost_optimization",
                "target_days": target_days,
            },
        )

    fixed_counts = {key: int(value) for key, value in cost_optimization["group_counts"].items()}
    result = _capacity_model_result(schedule_input, cost_optimization, fixed_counts)
    result.validation = validation + result.validation

    selected_costs = cost_optimization.get("selected_resource_costs", [])
    resource_incremental_cost = int(cost_optimization.get("resource_incremental_cost", 0))
    soft_milestone_penalty = sum(item.penalty for item in result.milestone_results if item.mode == "soft")
    total_cost = resource_incremental_cost + soft_milestone_penalty
    recommended = _recommended_resource_counts(groups, fixed_counts)
    explanation = _resource_cost_business_explanation(
        selected_resources=selected_costs,
        resource_incremental_cost=resource_incremental_cost,
        soft_milestone_penalty=soft_milestone_penalty,
        total_cost=total_cost,
        milestone_results=result.milestone_results,
    )

    result.stats.update(
        {
            "solve_mode": "resource_cost_optimization",
            "target_days": target_days,
            "recommended_resource_counts": recommended,
            "selected_resource_costs": selected_costs,
            "resource_incremental_cost": resource_incremental_cost,
            "soft_milestone_penalty": soft_milestone_penalty,
            "total_cost": total_cost,
            "business_explanation": explanation,
            "schedule_source": "resource_cost_capacity_model",
        }
    )
    result.objective_breakdown.update(
        {
            "solve_mode": "resource_cost_optimization",
            "target_days": target_days,
            "recommended_resource_counts": recommended,
            "selected_resource_costs": selected_costs,
            "resource_incremental_cost": resource_incremental_cost,
            "soft_milestone_penalty": soft_milestone_penalty,
            "total_cost": total_cost,
            "business_explanation": explanation,
            "weighted_objective": total_cost,
        }
    )
    return result


def _normalized_resource_linear_costs(
    groups: list[dict[str, Any]],
    resource_linear_costs_by_pool: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    costs: dict[str, dict[str, Any]] = {}
    for group in groups:
        raw = resource_linear_costs_by_pool.get(group["key"], {})
        try:
            current_quantity = int(raw.get("current_quantity", group["max_quantity"]))
            max_quantity = int(raw.get("max_quantity", group["max_quantity"]))
            unit_cost = int(raw.get("incremental_unit_cost", 0))
            billing_period_days = int(raw.get("billing_period_days", 30))
        except (TypeError, ValueError):
            current_quantity = group["max_quantity"]
            max_quantity = group["max_quantity"]
            unit_cost = 0
            billing_period_days = 30
        current_quantity = max(0, min(current_quantity, group["max_quantity"]))
        max_quantity = max(current_quantity, min(max_quantity, group["max_quantity"]))
        unit_cost = max(0, unit_cost)
        billing_period_days = max(1, billing_period_days)
        cost_type = str(raw.get("cost_type", "none"))
        if cost_type not in {"none", "monthly_rental", "one_time_purchase"}:
            cost_type = "none"
        costs[group["key"]] = {
            "resource_pool_id": group["key"],
            "label": raw.get("label") or group["label"],
            "resource_type": group["resource_type"],
            "current_quantity": current_quantity,
            "max_quantity": max_quantity,
            "cost_type": cost_type,
            "incremental_unit_cost": unit_cost,
            "billing_period_days": billing_period_days,
        }
    return costs


def _resource_cost_business_explanation(
    *,
    selected_resources: list[dict[str, Any]],
    resource_incremental_cost: int,
    soft_milestone_penalty: int,
    total_cost: int,
    milestone_results: list[MilestoneResult],
) -> str:
    selected_increases = [
        resource
        for resource in selected_resources
        if int(resource.get("added_quantity", 0)) > 0
    ]
    kept_resources = [
        resource
        for resource in selected_resources
        if int(resource.get("added_quantity", 0)) <= 0
    ]
    if selected_increases:
        resource_text = "、".join(
            f"{resource['label']} {resource['selected_quantity']} 个"
            for resource in selected_resources
        )
        increase_text = "、".join(
            f"{resource['label']}新增 {resource['added_quantity']} 个，线性成本 {_yuan(resource['incremental_cost'])}"
            for resource in selected_increases
        )
        first_sentence = f"系统选择配置 {resource_text}。{increase_text}。"
    else:
        kept_text = "、".join(f"{resource['label']}保持 {resource['selected_quantity']} 个" for resource in kept_resources)
        first_sentence = f"系统选择保持现有资源配置{f'：{kept_text}' if kept_text else ''}。"

    late_milestones = [milestone for milestone in milestone_results if milestone.mode == "soft" and milestone.lateness_days > 0]
    if late_milestones:
        milestone_text = "；".join(
            f"{milestone.name}预计迟延 {milestone.lateness_days} 天，延误成本 {_yuan(milestone.penalty)}"
            for milestone in late_milestones
        )
    else:
        milestone_text = "已评估的软节点未发生延误成本。"

    return (
        f"{first_sentence}"
        f"线性资源成本 {_yuan(resource_incremental_cost)}，参考节点延误成本 {_yuan(soft_milestone_penalty)}。"
        f"{milestone_text}"
        f"在固定工期约束下，展示综合成本为 {_yuan(total_cost)}。"
    )


def _yuan(value: Any) -> str:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,} 元"


def _solve_resource_model(
    schedule_input: ScheduleInput,
    *,
    cp_model: Any,
    fixed_counts: dict[str, int],
    minimize_group_key: str | None,
    fallback_target_days: int | None,
    enforce_fixed_duration: bool = True,
    resource_limits: dict[str, int] | None = None,
    feasibility_only: bool = False,
) -> dict[str, Any]:
    enabled_resources = [resource for resource in schedule_input.resources if resource.enabled]
    effective_limits = {**fixed_counts, **(resource_limits or {})}
    if effective_limits:
        enabled_resources = _apply_resource_limits(enabled_resources, effective_limits)
    resource_candidates = _resource_candidates_by_task(schedule_input.tasks, enabled_resources)
    validation = _validate_resource_coverage(schedule_input.tasks, resource_candidates)

    model = cp_model.CpModel()
    horizon = _build_horizon(schedule_input)
    starts: dict[str, Any] = {}
    ends: dict[str, Any] = {}
    task_by_id = {task.id: task for task in schedule_input.tasks}
    assignment_vars: dict[tuple[str, str], Any] = {}
    assignments_by_resource: dict[str, list[Any]] = defaultdict(list)
    resource_used_vars: dict[str, Any] = {}
    resource_intervals: dict[str, list[Any]] = defaultdict(list)
    milestone_vars: dict[str, Any] = {}
    milestone_target_offsets: dict[str, int] = {}
    soft_lateness_vars: dict[str, Any] = {}

    for task in schedule_input.tasks:
        starts[task.id] = model.NewIntVar(0, horizon, f"start_{_safe(task.id)}")
        ends[task.id] = model.NewIntVar(0, horizon, f"end_{_safe(task.id)}")
        model.Add(ends[task.id] == starts[task.id] + task.duration_days)

        choices = []
        for resource in resource_candidates.get(task.id, []):
            assigned = model.NewBoolVar(f"assign_{_safe(task.id)}_{_safe(resource.id)}")
            interval = model.NewOptionalIntervalVar(
                starts[task.id],
                task.duration_days,
                ends[task.id],
                assigned,
                f"interval_{_safe(task.id)}_{_safe(resource.id)}",
            )
            choices.append(assigned)
            assignment_vars[(task.id, resource.id)] = assigned
            assignments_by_resource[resource.id].append(assigned)
            resource_intervals[resource.id].append(interval)
        if choices:
            model.AddExactlyOne(choices)

    for resource in enabled_resources:
        used = model.NewBoolVar(f"used_{_safe(resource.id)}")
        assignments = assignments_by_resource.get(resource.id, [])
        if assignments:
            for assigned in assignments:
                model.Add(assigned <= used)
            model.Add(sum(assignments) >= used)
        else:
            model.Add(used == 0)
        resource_used_vars[resource.id] = used

    group_resources = _resource_groups(enabled_resources)
    group_count_exprs: dict[str, Any] = {}
    for group in group_resources:
        count_expr = sum(resource_used_vars[resource.id] for resource in group["resources"])
        group_count_exprs[group["key"]] = count_expr

    for link in schedule_input.precedence_links:
        predecessor = task_by_id.get(link.predecessor_id)
        successor = task_by_id.get(link.successor_id)
        if not predecessor or not successor:
            validation.append(
                ValidationMessage(level="warning", subject_id=link.id, message=f"已跳过逻辑关系 {link.id}：前置或后续工作项不存在。")
            )
            continue
        _add_precedence_constraint(model, starts, ends, link)

    _add_continuous_beam_v18_constraints(
        model,
        starts,
        ends,
        schedule_input.tasks,
        schedule_input.precedence_links,
        horizon,
    )

    for intervals in resource_intervals.values():
        model.AddNoOverlap(intervals)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [ends[task.id] for task in schedule_input.tasks])

    hard_match_count = 0
    for milestone in schedule_input.milestones:
        scoped_task_ids = _task_ids_for_milestone(milestone, schedule_input.tasks)
        if milestone.related_structure_ids:
            related_ids = {
                task.id
                for task in schedule_input.tasks
                if task.structure_id in set(milestone.related_structure_ids)
            }
            scoped_task_ids = sorted(set(scoped_task_ids) | related_ids)
        if not scoped_task_ids:
            validation.append(
                ValidationMessage(level="warning", subject_id=milestone.id, message=f"里程碑“{milestone.name}”没有匹配的工作项，已跳过。")
            )
            continue
        event_var = model.NewIntVar(0, horizon, f"milestone_{_safe(milestone.id)}")
        event_vars = [ends[task_id] if milestone.target_event == "finish" else starts[task_id] for task_id in scoped_task_ids]
        if milestone.target_event == "finish":
            model.AddMaxEquality(event_var, event_vars)
        else:
            model.AddMinEquality(event_var, event_vars)

        target_offset = _target_offset(schedule_input.start_date, milestone)
        milestone_vars[milestone.id] = event_var
        milestone_target_offsets[milestone.id] = target_offset
        if milestone.mode == "hard" and enforce_fixed_duration:
            hard_match_count += 1
            model.Add(event_var <= target_offset)
        else:
            lateness_upper = max(horizon - target_offset, horizon) + 365
            lateness_var = model.NewIntVar(0, lateness_upper, f"late_{_safe(milestone.id)}")
            model.Add(lateness_var >= event_var - target_offset)
            soft_lateness_vars[milestone.id] = lateness_var

    if enforce_fixed_duration and hard_match_count == 0 and fallback_target_days is not None:
        model.Add(makespan <= fallback_target_days)

    soft_penalty_terms = [
        late_var * _milestone_by_id(schedule_input.milestones, milestone_id).penalty_per_day
        for milestone_id, late_var in soft_lateness_vars.items()
    ]
    continuity_terms = {"split_terms": [], "spatial_terms": [], "spatial_term_details": []}
    if not feasibility_only:
        continuity_terms = _build_continuity_soft_terms(model, schedule_input.tasks, resource_candidates, assignment_vars)
    if feasibility_only:
        pass
    elif minimize_group_key:
        model.Minimize(group_count_exprs.get(minimize_group_key, 0))
    else:
        primary_objective = makespan + sum(soft_penalty_terms)
        continuity_objective = sum(continuity_terms["split_terms"]) * SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT + sum(
            continuity_terms["spatial_terms"]
        ) * SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT
        model.Minimize(primary_objective * CONTINUITY_PRIMARY_WEIGHT + continuity_objective)

    solver = cp_model.CpSolver()
    _configure_solver(solver, schedule_input.time_limit_seconds)
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)
    group_counts = {
        group["key"]: sum(solver.Value(resource_used_vars[resource.id]) for resource in group["resources"])
        for group in group_resources
        if status in {"OPTIMAL", "FEASIBLE"}
    }
    return {
        "status": status,
        "solver": solver,
        "starts": starts,
        "ends": ends,
        "assignment_vars": assignment_vars,
        "resource_candidates": resource_candidates,
        "milestone_vars": milestone_vars,
        "milestone_target_offsets": milestone_target_offsets,
        "soft_lateness_vars": soft_lateness_vars,
        "continuity_terms": continuity_terms,
        "makespan": makespan,
        "validation": validation,
        "group_counts": group_counts,
        "stats": {
            "horizon_days": horizon,
            "wall_time_seconds": solver.WallTime(),
            "conflicts": solver.NumConflicts(),
            "branches": solver.NumBranches(),
            "random_seed": SCHEDULER_RANDOM_SEED,
            "search_workers": _scheduler_search_workers(),
        },
    }


def _solve_capacity_model(
    schedule_input: ScheduleInput,
    *,
    cp_model: Any,
    groups: list[dict[str, Any]],
    counts: dict[str, int] | None,
    fallback_target_days: int | None,
    enforce_fixed_duration: bool = True,
    minimize_resource_count: bool = False,
    minimize_total_cost: bool = False,
    minimize_makespan: bool = False,
    resource_linear_costs_by_group: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validation: list[ValidationMessage] = []
    model = cp_model.CpModel()
    horizon = _build_horizon(schedule_input)
    starts: dict[str, Any] = {}
    ends: dict[str, Any] = {}
    task_by_id = {task.id: task for task in schedule_input.tasks}
    groups_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        groups_by_type[group["resource_type"]].append(group)
    intervals_by_group: dict[str, list[Any]] = defaultdict(list)
    demands_by_group: dict[str, list[int]] = defaultdict(list)
    assignment_vars: dict[tuple[str, str], Any] = {}
    milestone_vars: dict[str, Any] = {}
    milestone_target_offsets: dict[str, int] = {}
    soft_lateness_vars: dict[str, Any] = {}
    count_vars: dict[str, Any] = {}
    resource_cost_terms: list[Any] = []
    resource_cost_option_details_by_group: dict[str, list[dict[str, Any]]] = {}
    assignments_by_group: dict[str, list[tuple[str, Any]]] = defaultdict(list)

    for task in schedule_input.tasks:
        starts[task.id] = model.NewIntVar(0, horizon, f"start_{_safe(task.id)}")
        ends[task.id] = model.NewIntVar(0, horizon, f"end_{_safe(task.id)}")
        model.Add(ends[task.id] == starts[task.id] + task.duration_days)
        choices = []
        seen_group_keys: set[str] = set()
        for resource_type in task.compatible_resource_types:
            for group in groups_by_type.get(resource_type, []):
                if group["key"] in seen_group_keys:
                    continue
                seen_group_keys.add(group["key"])
                assigned = model.NewBoolVar(f"capacity_assign_{_safe(task.id)}_{_safe(group['key'])}")
                interval = model.NewOptionalIntervalVar(
                    starts[task.id],
                    task.duration_days,
                    ends[task.id],
                    assigned,
                    f"capacity_interval_{_safe(task.id)}_{_safe(group['key'])}",
                )
                choices.append(assigned)
                assignment_vars[(task.id, group["key"])] = assigned
                assignments_by_group[group["key"]].append((task.id, assigned))
                intervals_by_group[group["key"]].append(interval)
                demands_by_group[group["key"]].append(1)
        if choices:
            model.AddExactlyOne(choices)
        elif task.compatible_resource_types:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=task.id,
                    message=f"“{task.name}”没有可用于容量校验的受限资源池，已按资源默认充足处理。",
                )
            )

    _add_capacity_same_structure_parallel_rules(
        model,
        starts,
        ends,
        schedule_input.tasks,
        groups_by_type,
        assignment_vars,
    )

    for group in groups:
        intervals = intervals_by_group.get(group["key"], [])
        if counts is None:
            cost_config = (resource_linear_costs_by_group or {}).get(group["key"]) if minimize_total_cost else None
            if cost_config:
                current_quantity = int(cost_config.get("current_quantity", 0))
                max_quantity = int(cost_config.get("max_quantity", group["max_quantity"]))
                if not intervals:
                    current_quantity = 0
                    max_quantity = 0
                capacity = model.NewIntVar(current_quantity, max_quantity, f"resource_count_{_safe(group['key'])}")
                selected_quantity_vars = []
                resource_cost_option_details_by_group[group["key"]] = []
                active_days = None
                if cost_config.get("cost_type") == "monthly_rental" and intervals:
                    active_start = model.NewIntVar(0, horizon, f"active_start_{_safe(group['key'])}")
                    active_end = model.NewIntVar(0, horizon, f"active_end_{_safe(group['key'])}")
                    active_days = model.NewIntVar(0, horizon, f"active_days_{_safe(group['key'])}")
                    group_used = model.NewBoolVar(f"group_used_{_safe(group['key'])}")
                    assignment_sum = sum(assigned for _, assigned in assignments_by_group.get(group["key"], []))
                    model.Add(assignment_sum >= 1).OnlyEnforceIf(group_used)
                    model.Add(assignment_sum == 0).OnlyEnforceIf(group_used.Not())
                    for task_id, assigned in assignments_by_group.get(group["key"], []):
                        model.Add(active_start <= starts[task_id]).OnlyEnforceIf(assigned)
                        model.Add(active_end >= ends[task_id]).OnlyEnforceIf(assigned)
                    model.Add(active_end >= active_start).OnlyEnforceIf(group_used)
                    model.Add(active_days == active_end - active_start).OnlyEnforceIf(group_used)
                    model.Add(active_start == 0).OnlyEnforceIf(group_used.Not())
                    model.Add(active_end == 0).OnlyEnforceIf(group_used.Not())
                    model.Add(active_days == 0).OnlyEnforceIf(group_used.Not())

                for quantity in range(current_quantity, max_quantity + 1):
                    selected = model.NewBoolVar(f"resource_quantity_{_safe(group['key'])}_{quantity}")
                    selected_quantity_vars.append(selected)
                    added_quantity = quantity - current_quantity
                    fixed_cost = 0
                    cost_var = None
                    daily_unit_cost = 0
                    if cost_config.get("cost_type") == "one_time_purchase":
                        fixed_cost = added_quantity * int(cost_config.get("incremental_unit_cost", 0))
                        if fixed_cost:
                            resource_cost_terms.append(selected * fixed_cost)
                    elif cost_config.get("cost_type") == "monthly_rental" and active_days is not None:
                        daily_unit_cost = math.ceil(
                            int(cost_config.get("incremental_unit_cost", 0)) / int(cost_config.get("billing_period_days", 30))
                        )
                        max_cost = added_quantity * daily_unit_cost * horizon
                        cost_var = model.NewIntVar(0, max_cost, f"resource_cost_{_safe(group['key'])}_{quantity}")
                        if added_quantity and daily_unit_cost:
                            model.Add(cost_var == active_days * added_quantity * daily_unit_cost).OnlyEnforceIf(selected)
                            model.Add(cost_var == 0).OnlyEnforceIf(selected.Not())
                        else:
                            model.Add(cost_var == 0)
                        resource_cost_terms.append(cost_var)
                    resource_cost_option_details_by_group[group["key"]].append(
                        {
                            **cost_config,
                            "current_quantity": current_quantity,
                            "max_quantity": max_quantity,
                            "selected": selected,
                            "selected_quantity": quantity,
                            "added_quantity": added_quantity,
                            "incremental_cost": fixed_cost,
                            "daily_unit_cost": daily_unit_cost,
                            "active_days_var": active_days,
                            "cost_var": cost_var,
                        }
                    )
                model.AddExactlyOne(selected_quantity_vars)
                model.Add(capacity == sum(quantity * selected for quantity, selected in zip(range(current_quantity, max_quantity + 1), selected_quantity_vars)))
            else:
                lower_bound = 1 if intervals else 0
                capacity = model.NewIntVar(lower_bound, group["max_quantity"], f"resource_count_{_safe(group['key'])}")
            count_vars[group["key"]] = capacity
        else:
            capacity = counts.get(group["key"], group["max_quantity"])
        if intervals:
            model.AddCumulative(intervals, demands_by_group[group["key"]], capacity)

    for link in schedule_input.precedence_links:
        predecessor = task_by_id.get(link.predecessor_id)
        successor = task_by_id.get(link.successor_id)
        if not predecessor or not successor:
            validation.append(
                ValidationMessage(level="warning", subject_id=link.id, message=f"已跳过逻辑关系 {link.id}：前置或后续工作项不存在。")
            )
            continue
        _add_precedence_constraint(model, starts, ends, link)

    _add_continuous_beam_v18_constraints(
        model,
        starts,
        ends,
        schedule_input.tasks,
        schedule_input.precedence_links,
        horizon,
    )

    config = schedule_input.schedule_strategy
    control_chain_task_ids = _control_chain_task_ids(schedule_input)
    normal_tasks = _normal_balance_tasks(schedule_input.tasks, control_chain_task_ids)
    _add_normal_time_window_constraints(model, starts, ends, normal_tasks, config, horizon)
    _add_normal_workface_constraints(model, starts, ends, normal_tasks, config)
    if config.resource_guarantee == "strict":
        _add_strict_control_resource_constraints(model, starts, ends, schedule_input.tasks, control_chain_task_ids)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [ends[task.id] for task in schedule_input.tasks])

    hard_match_count = 0
    for milestone in schedule_input.milestones:
        scoped_task_ids = _task_ids_for_milestone(milestone, schedule_input.tasks)
        if not scoped_task_ids:
            validation.append(
                ValidationMessage(level="warning", subject_id=milestone.id, message=f"里程碑“{milestone.name}”没有匹配的工作项，已跳过。")
            )
            continue
        if milestone.related_structure_ids:
            related_ids = {
                task.id
                for task in schedule_input.tasks
                if task.structure_id in set(milestone.related_structure_ids)
            }
            scoped_task_ids = sorted(set(scoped_task_ids) | related_ids)
        event_var = model.NewIntVar(0, horizon, f"capacity_milestone_{_safe(milestone.id)}")
        event_vars = [ends[task_id] if milestone.target_event == "finish" else starts[task_id] for task_id in scoped_task_ids]
        if milestone.target_event == "finish":
            model.AddMaxEquality(event_var, event_vars)
        else:
            model.AddMinEquality(event_var, event_vars)

        target_offset = _target_offset(schedule_input.start_date, milestone)
        milestone_vars[milestone.id] = event_var
        milestone_target_offsets[milestone.id] = target_offset
        if milestone.mode == "hard" and enforce_fixed_duration:
            hard_match_count += 1
            model.Add(event_var <= target_offset)
        elif milestone.mode == "soft":
            lateness_upper = max(horizon - target_offset, horizon) + 365
            lateness_var = model.NewIntVar(0, lateness_upper, f"capacity_late_{_safe(milestone.id)}")
            model.Add(lateness_var >= event_var - target_offset)
            soft_lateness_vars[milestone.id] = lateness_var

    if enforce_fixed_duration and hard_match_count == 0 and fallback_target_days is not None:
        model.Add(makespan <= fallback_target_days)

    soft_penalty_terms = [
        late_var * _milestone_by_id(schedule_input.milestones, milestone_id).penalty_per_day
        for milestone_id, late_var in soft_lateness_vars.items()
    ]
    total_resource_cost = sum(resource_cost_terms)
    total_soft_penalty = sum(soft_penalty_terms)
    if minimize_resource_count:
        model.Minimize(sum(count_vars.values()) * (horizon + 1) + makespan)
    elif minimize_total_cost:
        model.Minimize(total_resource_cost)
    elif minimize_makespan:
        model.Minimize(makespan + total_soft_penalty)

    solver = cp_model.CpSolver()
    _configure_solver(solver, schedule_input.time_limit_seconds)
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)
    if minimize_total_cost and status in {"OPTIMAL", "FEASIBLE"}:
        best_resource_cost = solver.Value(total_resource_cost)
        model.Add(total_resource_cost == best_resource_cost)
        model.Minimize(total_soft_penalty)
        status_code = solver.Solve(model)
        status = _status_name(status_code, cp_model)
    if minimize_total_cost and status in {"OPTIMAL", "FEASIBLE"}:
        best_soft_penalty = solver.Value(total_soft_penalty)
        model.Add(total_soft_penalty == best_soft_penalty)
        model.Minimize(makespan)
        status_code = solver.Solve(model)
        status = _status_name(status_code, cp_model)

    selected_resource_costs: list[dict[str, Any]] = []
    if status in {"OPTIMAL", "FEASIBLE"}:
        for group in groups:
            for option in resource_cost_option_details_by_group.get(group["key"], []):
                if solver.BooleanValue(option["selected"]):
                    cost_var = option.get("cost_var")
                    active_days_var = option.get("active_days_var")
                    selected_resource_costs.append(
                        {
                            key: value
                            for key, value in option.items()
                            if key not in {"selected", "cost_var", "active_days_var"}
                        }
                        | {
                            "incremental_cost": solver.Value(cost_var) if cost_var is not None else int(option.get("incremental_cost", 0)),
                            "active_days": solver.Value(active_days_var) if active_days_var is not None else 0,
                        }
                    )
    return {
        "status": status,
        "solver": solver,
        "starts": starts,
        "ends": ends,
        "assignment_vars": assignment_vars,
        "milestone_vars": milestone_vars,
        "milestone_target_offsets": milestone_target_offsets,
        "soft_lateness_vars": soft_lateness_vars,
        "makespan": makespan,
        "validation": validation,
        "selected_resource_costs": selected_resource_costs,
        "resource_incremental_cost": sum(int(resource["incremental_cost"]) for resource in selected_resource_costs),
        "stats": {
            "horizon_days": horizon,
            "wall_time_seconds": solver.WallTime(),
            "conflicts": solver.NumConflicts(),
            "branches": solver.NumBranches(),
            "random_seed": SCHEDULER_RANDOM_SEED,
            "search_workers": _scheduler_search_workers(),
        },
        "group_counts": (
            {key: solver.Value(count_var) for key, count_var in count_vars.items()}
            if counts is None and status in {"OPTIMAL", "FEASIBLE"}
            else (counts if counts is not None and status in {"OPTIMAL", "FEASIBLE"} else {})
        ),
    }


def _capacity_model_result(
    schedule_input: ScheduleInput,
    solved: dict[str, Any],
    fixed_counts: dict[str, int],
) -> ScheduleResult:
    solver = solved["solver"]
    starts = solved["starts"]
    ends = solved["ends"]
    assignment_vars = solved.get("assignment_vars", {})
    validation = list(solved["validation"])

    selected_group_by_task_id: dict[str, str] = {}
    for (task_id, group_key), assignment in assignment_vars.items():
        if solver.Value(assignment):
            selected_group_by_task_id[task_id] = group_key

    limited_resources = _apply_resource_limits(
        [resource for resource in schedule_input.resources if resource.enabled],
        fixed_counts,
    )
    resources_by_group = {
        group["key"]: sorted(group["resources"], key=_resource_sort_key)
        for group in _resource_groups(limited_resources)
    }
    resource_ready = {resource.id: 0 for resource in limited_resources}
    assigned_resource_by_task_id: dict[str, Resource] = {}

    ordered_tasks = sorted(schedule_input.tasks, key=lambda item: (solver.Value(starts[item.id]), item.id))
    for task in ordered_tasks:
        group_key = selected_group_by_task_id.get(task.id)
        if not group_key:
            continue
        candidates = resources_by_group.get(group_key, [])
        start_offset = solver.Value(starts[task.id])
        end_offset = solver.Value(ends[task.id])
        assigned_resource = next((resource for resource in candidates if resource_ready[resource.id] <= start_offset), None)
        if not assigned_resource and candidates:
            assigned_resource = min(candidates, key=lambda resource: resource_ready[resource.id])
        if not assigned_resource:
            validation.append(
                ValidationMessage(
                    level="error",
                    subject_id=task.id,
                    message=f"“{task.name}”已选择资源池 {group_key}，但推荐数量中没有可用命名资源。",
                )
            )
            continue
        assigned_resource_by_task_id[task.id] = assigned_resource
        resource_ready[assigned_resource.id] = end_offset

    predecessors_by_successor: dict[str, list[str]] = defaultdict(list)
    for link in schedule_input.precedence_links:
        predecessors_by_successor[link.successor_id].append(link.predecessor_id)

    scheduled_tasks: list[ScheduledTask] = []
    allocations: list[ResourceAllocation] = []
    for task in ordered_tasks:
        assigned_resource = assigned_resource_by_task_id.get(task.id)
        start_offset = solver.Value(starts[task.id])
        end_offset = solver.Value(ends[task.id])
        scheduled_tasks.append(
            ScheduledTask(
                **task.model_dump(),
                start_offset=start_offset,
                end_offset=end_offset,
                start_date=_offset_date(schedule_input.start_date, start_offset),
                finish_date=_finish_date(schedule_input.start_date, end_offset),
                assigned_resource_id=assigned_resource.id if assigned_resource else None,
                assigned_resource_name=assigned_resource.name if assigned_resource else None,
                assigned_resource_type=assigned_resource.type if assigned_resource else None,
                predecessor_ids=predecessors_by_successor.get(task.id, []),
            )
        )
        if assigned_resource:
            allocations.append(
                ResourceAllocation(
                    resource_id=assigned_resource.id,
                    resource_name=assigned_resource.name,
                    resource_type=assigned_resource.type,
                    task_id=task.id,
                    task_name=task.name,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_date=_offset_date(schedule_input.start_date, start_offset),
                    finish_date=_finish_date(schedule_input.start_date, end_offset),
                )
            )

    objective_days = solver.Value(solved["makespan"])
    milestone_results = _build_milestone_results(
        schedule_input=schedule_input,
        milestone_vars=solved["milestone_vars"],
        milestone_target_offsets=solved["milestone_target_offsets"],
        soft_lateness_vars=solved["soft_lateness_vars"],
        solver=solver,
    )
    validation.extend(_validate_solution(schedule_input, scheduled_tasks, allocations))
    validation.extend(_validate_milestone_results(milestone_results))
    continuity_metrics = _build_continuity_metrics(scheduled_tasks)
    validation.extend(_continuity_validation_messages(continuity_metrics))
    soft_milestone_penalty = sum(result.penalty for result in milestone_results if result.mode == "soft")

    stats = {
        **solved["stats"],
        "capacity_model_schedule": True,
        "continuity_metrics": continuity_metrics,
        "continuity_objective": {
            "same_structure_craft_split_penalty": 0,
            "spatial_assignment_penalty": 0,
            "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
            "same_structure_craft_split_weight": SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT,
            "spatial_resource_assignment_weight": SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT,
        },
    }
    return ScheduleResult(
        status=solved["status"],
        objective_days=objective_days,
        plan_start_date=schedule_input.start_date,
        plan_finish_date=_finish_date(schedule_input.start_date, objective_days),
        tasks=scheduled_tasks,
        resource_allocations=sorted(allocations, key=lambda item: (item.resource_name, item.start_offset, item.task_name)),
        milestone_results=milestone_results,
        validation=validation,
        stats=stats,
        objective_breakdown={
            "makespan_days": objective_days,
            "soft_milestone_penalty": soft_milestone_penalty,
            "same_structure_craft_split_penalty": 0,
            "spatial_assignment_penalty": 0,
            "continuity_score": continuity_metrics["continuity_score"],
            "weighted_objective": objective_days + soft_milestone_penalty,
        },
    )


def _fixed_duration_infeasible_result(
    *,
    schedule_input: ScheduleInput,
    checked: dict[str, Any],
    critical_path: dict[str, Any],
    validation: list[ValidationMessage],
    groups: list[dict[str, Any]],
    target_days: int | None,
    capacity_window_days: int | None,
) -> ScheduleResult:
    messages = list(validation)
    resource_upper_bound_counts = [
        {
            "resource_pool_id": group["key"],
            "label": group["label"],
            "resource_type": group["resource_type"],
            "upper_bound_quantity": group["max_quantity"],
            "max_quantity": group["max_quantity"],
        }
        for group in groups
    ]
    resource_capacity_lower_bounds = _resource_capacity_lower_bound_diagnostics(
        schedule_input,
        groups,
        capacity_window_days,
    )

    stats = {
        **checked["stats"],
        "reason": "resource_upper_bound_or_deadline_infeasible",
        "solve_mode": "min_resources_fixed_duration",
        "target_days": target_days,
        "capacity_window_days": capacity_window_days,
        "resource_upper_bound_counts": resource_upper_bound_counts,
        "max_resource_counts": [
            {
                "resource_pool_id": group["key"],
                "label": group["label"],
                "resource_type": group["resource_type"],
                "max_quantity": group["max_quantity"],
            }
            for group in groups
        ],
        "resource_capacity_lower_bounds": resource_capacity_lower_bounds,
        "workface_parallelism_diagnostics": _workface_parallelism_diagnostics(schedule_input),
        "fixed_duration_precheck_failed": True,
    }
    objective_breakdown: dict[str, Any] = {
        "solve_mode": "min_resources_fixed_duration",
        "target_days": target_days,
        "resource_upper_bound_counts": resource_upper_bound_counts,
        "resource_capacity_lower_bounds": resource_capacity_lower_bounds,
    }

    if critical_path.get("status") == "OK":
        objective_days = int(critical_path["objective_days"])
        plan_finish_date = critical_path["plan_finish_date"]
        milestone_results = critical_path["milestone_results"]
        critical_path_late_hard = [milestone for milestone in milestone_results if milestone.mode == "hard" and milestone.lateness_days > 0]
        fallback_target_missed = not critical_path_late_hard and target_days is not None and objective_days > target_days
        stats.update(
            {
                "critical_path_minimum_days": objective_days,
                "critical_path_plan_finish_date": plan_finish_date,
                "critical_path_blocks_target": bool(critical_path_late_hard or fallback_target_missed),
            }
        )
        objective_breakdown.update(
            {
                "critical_path_minimum_days": objective_days,
                "critical_path_plan_finish_date": plan_finish_date,
            }
        )
        if critical_path_late_hard or fallback_target_missed:
            messages.append(
                ValidationMessage(
                    level="error",
                    message=(
                        "在资源最大数量下仍无法满足固定工期或强制里程碑目标；"
                        "当前瓶颈不是资源数量上限，而是目标日期与工艺逻辑关键路径不匹配。"
                    ),
                )
            )
        else:
            messages.append(
                ValidationMessage(
                    level="error",
                    message=(
                        "不考虑资源排队时，工艺逻辑关键路径可以满足固定工期；"
                        "但加入当前资源最大数量后仍不可行，请检查各资源池最大数量和资源类型结构。"
                    ),
                )
            )
        messages.append(
            ValidationMessage(
                level="error",
                message=(
                    f"不考虑资源排队、仅按工艺逻辑关键路径计算，理论最早仍需 {objective_days} 天，"
                    f"预计完工 {plan_finish_date}。"
                ),
            )
        )
        for milestone in milestone_results:
            if milestone.mode == "hard" and milestone.lateness_days > 0:
                messages.append(
                    ValidationMessage(
                        level="error",
                        subject_id=milestone.id,
                        message=(
                            f"强制里程碑“{milestone.name}”目标 {milestone.target_date}，"
                            f"工艺逻辑理论最早 {milestone.actual_date}，迟延 {milestone.lateness_days} 天。"
                        ),
                    )
                )
        if not critical_path_late_hard and not fallback_target_missed:
            messages.extend(_resource_capacity_lower_bound_messages(resource_capacity_lower_bounds))
    else:
        objective_days = None
        plan_finish_date = None
        milestone_results = _not_evaluated_milestones(schedule_input.milestones)
        messages.append(
            ValidationMessage(
                level="error",
                message="无法计算工艺逻辑关键路径，请检查工艺逻辑是否存在闭环或不可满足约束。",
            )
        )

    return ScheduleResult(
        status=checked["status"],
        objective_days=objective_days,
        plan_start_date=schedule_input.start_date,
        plan_finish_date=plan_finish_date,
        milestone_results=milestone_results,
        validation=messages,
        stats=stats,
        objective_breakdown=objective_breakdown,
    )


def _resource_model_result(schedule_input: ScheduleInput, solved: dict[str, Any]) -> ScheduleResult:
    solver = solved["solver"]
    starts = solved["starts"]
    ends = solved["ends"]
    assignment_vars = solved["assignment_vars"]
    resource_candidates = solved["resource_candidates"]
    validation = list(solved["validation"])
    predecessors_by_successor: dict[str, list[str]] = defaultdict(list)
    for link in schedule_input.precedence_links:
        predecessors_by_successor[link.successor_id].append(link.predecessor_id)

    scheduled_tasks: list[ScheduledTask] = []
    allocations: list[ResourceAllocation] = []
    for task in sorted(schedule_input.tasks, key=lambda item: (solver.Value(starts[item.id]), item.id)):
        assigned_resource = _assigned_resource_for_task(task, resource_candidates, assignment_vars, solver)
        start_offset = solver.Value(starts[task.id])
        end_offset = solver.Value(ends[task.id])
        scheduled_tasks.append(
            ScheduledTask(
                **task.model_dump(),
                start_offset=start_offset,
                end_offset=end_offset,
                start_date=_offset_date(schedule_input.start_date, start_offset),
                finish_date=_finish_date(schedule_input.start_date, end_offset),
                assigned_resource_id=assigned_resource.id if assigned_resource else None,
                assigned_resource_name=assigned_resource.name if assigned_resource else None,
                assigned_resource_type=assigned_resource.type if assigned_resource else None,
                predecessor_ids=predecessors_by_successor.get(task.id, []),
            )
        )
        if assigned_resource:
            allocations.append(
                ResourceAllocation(
                    resource_id=assigned_resource.id,
                    resource_name=assigned_resource.name,
                    resource_type=assigned_resource.type,
                    task_id=task.id,
                    task_name=task.name,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    start_date=_offset_date(schedule_input.start_date, start_offset),
                    finish_date=_finish_date(schedule_input.start_date, end_offset),
                )
            )

    objective_days = solver.Value(solved["makespan"])
    milestone_results = _build_milestone_results(
        schedule_input=schedule_input,
        milestone_vars=solved["milestone_vars"],
        milestone_target_offsets=solved["milestone_target_offsets"],
        soft_lateness_vars=solved["soft_lateness_vars"],
        solver=solver,
    )
    validation.extend(_validate_solution(schedule_input, scheduled_tasks, allocations))
    validation.extend(_validate_milestone_results(milestone_results))
    continuity_metrics = _build_continuity_metrics(scheduled_tasks)
    validation.extend(_continuity_validation_messages(continuity_metrics))
    soft_milestone_penalty = sum(result.penalty for result in milestone_results if result.mode == "soft")
    continuity_terms = solved.get("continuity_terms", {"split_terms": [], "spatial_term_details": []})
    continuity_split_penalty = sum(solver.Value(term) for term in continuity_terms["split_terms"])
    spatial_assignment_penalty = sum(
        int(term["penalty"]) * solver.Value(term["assignment"]) for term in continuity_terms["spatial_term_details"]
    )
    stats = {
        **solved["stats"],
        "continuity_metrics": continuity_metrics,
        "continuity_objective": {
            "same_structure_craft_split_penalty": continuity_split_penalty,
            "spatial_assignment_penalty": spatial_assignment_penalty,
            "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
            "same_structure_craft_split_weight": SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT,
            "spatial_resource_assignment_weight": SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT,
        },
    }
    return ScheduleResult(
        status=solved["status"],
        objective_days=objective_days,
        plan_start_date=schedule_input.start_date,
        plan_finish_date=_finish_date(schedule_input.start_date, objective_days),
        tasks=scheduled_tasks,
        resource_allocations=sorted(allocations, key=lambda item: (item.resource_name, item.start_offset, item.task_name)),
        milestone_results=milestone_results,
        validation=validation,
        stats=stats,
        objective_breakdown={
            "makespan_days": objective_days,
            "soft_milestone_penalty": soft_milestone_penalty,
            "same_structure_craft_split_penalty": continuity_split_penalty,
            "spatial_assignment_penalty": spatial_assignment_penalty,
            "continuity_score": continuity_metrics["continuity_score"],
            "weighted_objective": objective_days + soft_milestone_penalty,
        },
    )


def _build_continuity_soft_terms(
    model: Any,
    tasks: list[Task],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
) -> dict[str, list[Any]]:
    split_terms = _same_structure_craft_split_terms(model, tasks, resource_candidates, assignment_vars)
    spatial_term_details = _spatial_resource_assignment_term_details(tasks, resource_candidates, assignment_vars)
    return {
        "split_terms": split_terms,
        "spatial_terms": [detail["assignment"] * detail["penalty"] for detail in spatial_term_details],
        "spatial_term_details": spatial_term_details,
    }


def _same_structure_craft_split_terms(
    model: Any,
    tasks: list[Task],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
) -> list[Any]:
    grouped_tasks: dict[tuple[str, str, str], list[Task]] = defaultdict(list)
    for task in tasks:
        grouped_tasks[(task.structure_id, task.component_type, task.process_name)].append(task)

    terms: list[Any] = []
    for group_index, group_tasks in enumerate(grouped_tasks.values()):
        if len(group_tasks) <= 1:
            continue
        resource_ids = sorted(
            {
                resource.id
                for task in group_tasks
                for resource in resource_candidates.get(task.id, [])
                if (task.id, resource.id) in assignment_vars
            }
        )
        if len(resource_ids) <= 1:
            continue

        used_vars = []
        for resource_id in resource_ids:
            assignments = [
                assignment_vars[(task.id, resource_id)]
                for task in group_tasks
                if (task.id, resource_id) in assignment_vars
            ]
            if not assignments:
                continue
            used = model.NewBoolVar(f"continuity_used_{group_index}_{_safe(resource_id)}")
            for assigned in assignments:
                model.Add(assigned <= used)
            model.Add(sum(assignments) >= used)
            used_vars.append(used)

        if len(used_vars) <= 1:
            continue
        excess = model.NewIntVar(0, len(used_vars) - 1, f"continuity_split_{group_index}")
        model.Add(excess == sum(used_vars) - 1)
        terms.append(excess)
    return terms


def _spatial_resource_assignment_term_details(
    tasks: list[Task],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
) -> list[dict[str, Any]]:
    resources_by_type: dict[str, dict[str, Resource]] = defaultdict(dict)
    tasks_by_type: dict[str, dict[str, Task]] = defaultdict(dict)
    for task in tasks:
        for resource in resource_candidates.get(task.id, []):
            if (task.id, resource.id) not in assignment_vars:
                continue
            resources_by_type[resource.type][resource.id] = resource
            tasks_by_type[resource.type][task.id] = task

    details: list[dict[str, Any]] = []
    for resource_type, typed_tasks_by_id in tasks_by_type.items():
        typed_resources = sorted(resources_by_type[resource_type].values(), key=_resource_sort_key)
        if len(typed_resources) <= 1:
            continue
        resource_rank = {resource.id: index for index, resource in enumerate(typed_resources)}
        ordered_tasks = sorted(typed_tasks_by_id.values(), key=_task_spatial_sort_key)
        total_tasks = len(ordered_tasks)
        if total_tasks <= 1:
            continue
        target_rank_by_task = {
            task.id: min(len(typed_resources) - 1, index * len(typed_resources) // total_tasks)
            for index, task in enumerate(ordered_tasks)
        }
        for task in ordered_tasks:
            target_rank = target_rank_by_task[task.id]
            for resource in resource_candidates.get(task.id, []):
                if resource.type != resource_type:
                    continue
                assignment = assignment_vars.get((task.id, resource.id))
                if assignment is None:
                    continue
                penalty = abs(resource_rank[resource.id] - target_rank)
                if penalty <= 0:
                    continue
                details.append({"assignment": assignment, "penalty": penalty})
    return details


def _build_continuity_metrics(scheduled_tasks: list[ScheduledTask]) -> dict[str, Any]:
    split_details = _same_structure_craft_split_details(scheduled_tasks)
    path_metrics = _resource_path_metrics(scheduled_tasks)
    same_structure_craft_split_count = sum(detail["split_excess"] for detail in split_details)
    jump_pier_count = path_metrics["jump_pier_count"]
    side_switch_count = path_metrics["side_switch_count"]
    cross_side_jump_count = path_metrics["cross_side_jump_count"]
    direction_reversal_count = path_metrics["direction_reversal_count"]
    penalty = (
        same_structure_craft_split_count * 8
        + jump_pier_count * 4
        + side_switch_count * 2
        + cross_side_jump_count * 6
        + direction_reversal_count * 4
    )
    continuity_score = max(0, 100 - penalty)
    return {
        "same_structure_craft_split_count": same_structure_craft_split_count,
        "same_structure_craft_split_details": split_details[:30],
        "resource_path_count": path_metrics["resource_path_count"],
        "jump_pier_count": jump_pier_count,
        "max_jump_distance": path_metrics["max_jump_distance"],
        "side_switch_count": side_switch_count,
        "cross_side_jump_count": cross_side_jump_count,
        "direction_reversal_count": direction_reversal_count,
        "path_group_switch_count": path_metrics["path_group_switch_count"],
        "continuity_score": continuity_score,
        "resource_paths": path_metrics["resource_paths"],
        "jump_transition_details": path_metrics["jump_transition_details"][:30],
        "path_group_switch_details": path_metrics["path_group_switch_details"][:30],
        "path_group_diagnostics": path_metrics["path_group_diagnostics"][:50],
    }


def _same_structure_craft_split_details(scheduled_tasks: list[ScheduledTask]) -> list[dict[str, Any]]:
    grouped_tasks: dict[tuple[str, str, str], list[ScheduledTask]] = defaultdict(list)
    for task in scheduled_tasks:
        grouped_tasks[(task.structure_id, task.component_type, task.process_name)].append(task)

    details: list[dict[str, Any]] = []
    for group_tasks in grouped_tasks.values():
        if len(group_tasks) <= 1:
            continue
        resource_names = sorted(
            {
                task.assigned_resource_name or task.assigned_resource_id or "未分配资源"
                for task in group_tasks
            }
        )
        if len(resource_names) <= 1:
            continue
        first = min(group_tasks, key=lambda task: (task.start_offset, task.id))
        details.append(
            {
                "structure_id": first.structure_id,
                "structure_name": first.structure_name,
                "component_type": first.component_type,
                "component_label": _component_type_label(first.component_type),
                "process_name": first.process_name,
                "task_count": len(group_tasks),
                "resource_count": len(resource_names),
                "split_excess": len(resource_names) - 1,
                "resource_names": resource_names,
                "task_names": [task.name for task in sorted(group_tasks, key=lambda item: (item.start_offset, item.id))[:20]],
                "reason": "为满足工艺前置、资源不可冲突和里程碑目标，当前解存在穿插；可通过提高连续性偏好或调整节点目标减少拆分。",
            }
        )
    return sorted(details, key=lambda item: (-item["split_excess"], item["structure_id"], item["component_type"]))


def _resource_path_metrics(scheduled_tasks: list[ScheduledTask]) -> dict[str, Any]:
    by_resource: dict[str, list[ScheduledTask]] = defaultdict(list)
    resource_meta: dict[str, dict[str, str | None]] = {}
    for task in scheduled_tasks:
        if not task.assigned_resource_id:
            continue
        by_resource[task.assigned_resource_id].append(task)
        resource_meta[task.assigned_resource_id] = {
            "resource_name": task.assigned_resource_name,
            "resource_type": task.assigned_resource_type,
        }

    location_orders = _continuity_location_orders(scheduled_tasks)
    resource_paths: list[dict[str, Any]] = []
    jump_transition_details: list[dict[str, Any]] = []
    jump_pier_count = 0
    side_switch_count = 0
    cross_side_jump_count = 0
    direction_reversal_count = 0
    path_group_switch_count = 0
    max_jump_distance = 0
    path_group_switch_details: list[dict[str, Any]] = []

    for resource_id, tasks in sorted(by_resource.items(), key=lambda item: _resource_sort_tuple(item[0], resource_meta[item[0]]["resource_name"])):
        ordered = sorted(tasks, key=lambda task: (task.start_offset, task.end_offset, *_task_spatial_sort_key(task)))
        path_jump_count = 0
        path_side_switch_count = 0
        path_cross_side_jump_count = 0
        path_group_switches = 0
        previous_direction: int | None = None

        for previous, current in zip(ordered, ordered[1:]):
            previous_group = _task_path_group(previous)
            current_group = _task_path_group(current)
            if previous_group["key"] != current_group["key"]:
                path_group_switch_count += 1
                path_group_switches += 1
                path_group_switch_details.append(
                    {
                        "resource_id": resource_id,
                        "resource_name": resource_meta[resource_id]["resource_name"] or resource_id,
                        "resource_type": resource_meta[resource_id]["resource_type"],
                        "from_task_id": previous.id,
                        "from_task_name": previous.name,
                        "to_task_id": current.id,
                        "to_task_name": current.name,
                        "from_group": previous_group,
                        "to_group": current_group,
                        "reason": "资源切换了业务路径组；本期仅作为路径解释诊断，不参与转场目标惩罚。",
                    }
                )
            if previous.structure_id == current.structure_id:
                continue
            from_location = _task_location(previous)
            to_location = _task_location(current)
            distance = (
                abs(to_location["support_index"] - from_location["support_index"])
                if from_location["support_index"] is not None and to_location["support_index"] is not None
                else None
            )
            side_switch = (
                from_location["side"] is not None
                and to_location["side"] is not None
                and from_location["side"] != to_location["side"]
            )
            pier_jump, ordered_distance = _is_ordered_pier_jump(
                previous,
                current,
                from_location,
                to_location,
                location_orders,
                side_switch,
            )
            cross_side_jump = side_switch and pier_jump
            direction_reversal = False
            if (
                not side_switch
                and from_location["support_index"] is not None
                and to_location["support_index"] is not None
            ):
                delta = to_location["support_index"] - from_location["support_index"]
                if delta != 0:
                    direction = 1 if delta > 0 else -1
                    direction_reversal = previous_direction is not None and direction != previous_direction
                    previous_direction = direction

            if pier_jump and ordered_distance is not None:
                max_jump_distance = max(max_jump_distance, ordered_distance)
            if pier_jump:
                jump_pier_count += 1
                path_jump_count += 1
            if side_switch:
                side_switch_count += 1
                path_side_switch_count += 1
            if cross_side_jump:
                cross_side_jump_count += 1
                path_cross_side_jump_count += 1
            if direction_reversal:
                direction_reversal_count += 1

            if pier_jump or side_switch or cross_side_jump or direction_reversal:
                jump_transition_details.append(
                    {
                        "resource_id": resource_id,
                        "resource_name": resource_meta[resource_id]["resource_name"] or resource_id,
                        "resource_type": resource_meta[resource_id]["resource_type"],
                        "from_task_id": previous.id,
                        "from_task_name": previous.name,
                        "from_location": from_location["label"],
                        "to_task_id": current.id,
                        "to_task_name": current.name,
                        "to_location": to_location["label"],
                        "jump_distance": ordered_distance,
                        "is_jump_pier": pier_jump,
                        "is_side_switch": side_switch,
                        "is_cross_side_jump": cross_side_jump,
                        "is_direction_reversal": direction_reversal,
                        "reason": "为满足工艺前置、资源不可冲突和里程碑目标，当前解存在资源转场；后续可结合工作面、架梁通道或自定义路径进一步约束。",
                    }
                )

        resource_paths.append(
            {
                "resource_id": resource_id,
                "resource_name": resource_meta[resource_id]["resource_name"] or resource_id,
                "resource_type": resource_meta[resource_id]["resource_type"],
                "task_count": len(ordered),
                "start_date": ordered[0].start_date if ordered else None,
                "finish_date": ordered[-1].finish_date if ordered else None,
                "jump_pier_count": path_jump_count,
                "side_switch_count": path_side_switch_count,
                "cross_side_jump_count": path_cross_side_jump_count,
                "path_group_switch_count": path_group_switches,
                "path": [
                    {
                        "task_id": task.id,
                        "task_name": task.name,
                        "location": _task_location(task)["label"],
                        "component_type": task.component_type,
                        "component_label": _component_type_label(task.component_type),
                        "start_date": task.start_date,
                        "finish_date": task.finish_date,
                    }
                    for task in ordered[:80]
                ],
            }
        )

    return {
        "resource_path_count": sum(1 for path in resource_paths if path["task_count"] > 0),
        "jump_pier_count": jump_pier_count,
        "max_jump_distance": max_jump_distance,
        "side_switch_count": side_switch_count,
        "cross_side_jump_count": cross_side_jump_count,
        "direction_reversal_count": direction_reversal_count,
        "path_group_switch_count": path_group_switch_count,
        "resource_paths": resource_paths,
        "jump_transition_details": jump_transition_details,
        "path_group_switch_details": path_group_switch_details,
        "path_group_diagnostics": _path_group_diagnostics(scheduled_tasks),
    }


def _continuity_location_orders(scheduled_tasks: list[ScheduledTask]) -> dict[tuple[Any, ...], dict[str, int]]:
    buckets: dict[tuple[Any, ...], dict[str, tuple[Any, ...]]] = defaultdict(dict)
    for task in scheduled_tasks:
        location = _task_location(task)
        if location["structure_type"] != "pier" or location["support_index"] is None:
            continue
        for include_side in (True, False):
            scope_key = _continuity_scope_key(task, location, include_side=include_side)
            buckets[scope_key][task.structure_id] = _continuity_location_sort_key(task, location, include_side=include_side)

    return {
        scope_key: {
            structure_id: index
            for index, structure_id in enumerate(
                sorted(structure_sort_keys, key=lambda item: (structure_sort_keys[item], item))
            )
        }
        for scope_key, structure_sort_keys in buckets.items()
    }


def _is_ordered_pier_jump(
    previous: ScheduledTask,
    current: ScheduledTask,
    from_location: dict[str, Any],
    to_location: dict[str, Any],
    location_orders: dict[tuple[Any, ...], dict[str, int]],
    side_switch: bool,
) -> tuple[bool, int | None]:
    if from_location["structure_type"] != "pier" or to_location["structure_type"] != "pier":
        return False, None

    include_side = not side_switch
    from_scope = _continuity_scope_key(previous, from_location, include_side=include_side)
    to_scope = _continuity_scope_key(current, to_location, include_side=include_side)
    if from_scope != to_scope:
        return False, None

    rank_by_structure = location_orders.get(from_scope)
    if not rank_by_structure:
        return False, None
    from_rank = rank_by_structure.get(previous.structure_id)
    to_rank = rank_by_structure.get(current.structure_id)
    if from_rank is None or to_rank is None:
        return False, None

    ordered_distance = abs(to_rank - from_rank)
    return ordered_distance > 1, ordered_distance


def _continuity_scope_key(task: ScheduledTask, location: dict[str, Any], *, include_side: bool) -> tuple[Any, ...]:
    resource_type = task.assigned_resource_type or "|".join(sorted(task.compatible_resource_types))
    work_section_id = (task.work_section_id or "") if include_side else ""
    side = location["side"] if include_side else "*"
    return (
        task.bridge_id or "",
        work_section_id,
        side,
        location["structure_type"],
        task.component_type,
        task.process_name,
        resource_type,
    )


def _task_path_group(task: ScheduledTask) -> dict[str, Any]:
    location = _task_location(task)
    resource_type = task.assigned_resource_type or "|".join(sorted(task.compatible_resource_types))
    key_parts = (
        task.bridge_id or "",
        task.work_section_id or "",
        location["side"] or "N",
        resource_type,
        task.component_type,
        task.process_name,
    )
    return {
        "key": "|".join(str(part) for part in key_parts),
        "bridge_id": task.bridge_id,
        "work_section_id": task.work_section_id,
        "side": location["side"] or "N",
        "side_label": location["side_label"],
        "resource_type": resource_type,
        "component_type": task.component_type,
        "component_label": _component_type_label(task.component_type),
        "process_name": task.process_name,
    }


def _path_group_diagnostics(scheduled_tasks: list[ScheduledTask]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for task in sorted(scheduled_tasks, key=_task_spatial_sort_key):
        if not task.assigned_resource_id:
            continue
        group = _task_path_group(task)
        item = groups.setdefault(
            group["key"],
            {
                **group,
                "task_count": 0,
                "resource_ids": set(),
                "resource_names": set(),
                "actual_sequence": [],
                "structure_ids": set(),
            },
        )
        item["task_count"] += 1
        item["resource_ids"].add(task.assigned_resource_id)
        item["resource_names"].add(task.assigned_resource_name or task.assigned_resource_id)
        item["structure_ids"].add(task.structure_id)
        location_label = _task_location(task)["label"]
        if location_label not in item["actual_sequence"]:
            item["actual_sequence"].append(location_label)

    diagnostics = []
    for item in groups.values():
        diagnostics.append(
            {
                **{key: value for key, value in item.items() if key not in {"resource_ids", "resource_names", "structure_ids"}},
                "resource_count": len(item["resource_ids"]),
                "resource_names": sorted(item["resource_names"]),
                "structure_count": len(item["structure_ids"]),
            }
        )
    return sorted(
        diagnostics,
        key=lambda item: (
            str(item["bridge_id"] or ""),
            str(item["work_section_id"] or ""),
            str(item["side"]),
            str(item["resource_type"]),
            str(item["component_type"]),
            str(item["process_name"]),
        ),
    )


def _continuity_location_sort_key(task: ScheduledTask, location: dict[str, Any], *, include_side: bool) -> tuple[Any, ...]:
    side_rank = {"L": 0, "R": 1, "N": 2}.get(location["side"] or "N", 2)
    side_and_support = (
        (side_rank, location["support_index"])
        if include_side
        else (location["support_index"], side_rank)
    )
    return (
        task.bridge_id or "",
        *side_and_support,
        task.sequence_order,
        task.structure_id,
    )


def _continuity_validation_messages(metrics: dict[str, Any]) -> list[ValidationMessage]:
    messages = [
        ValidationMessage(
            level="info",
            message=(
                f"施工连续性评分 {metrics['continuity_score']}；"
                f"同墩同工艺拆分 {metrics['same_structure_craft_split_count']} 次，"
                f"跳墩 {metrics['jump_pier_count']} 次，跳幅 {metrics['side_switch_count']} 次，"
                f"跨幅跳墩 {metrics['cross_side_jump_count']} 次。"
            ),
        )
    ]
    split_details = metrics.get("same_structure_craft_split_details") or []
    if split_details:
        example = split_details[0]
        messages.append(
            ValidationMessage(
                level="warning",
                subject_id=example["structure_id"],
                message=(
                    f"发现 {metrics['same_structure_craft_split_count']} 次同墩同工艺拆分；"
                    f"示例：{example['structure_name']}的{example['component_label']}由 "
                    f"{example['resource_count']} 个资源序列承担（{', '.join(example['resource_names'])}）。"
                    "原因初判：为满足工艺前置、资源不可冲突和里程碑目标，当前解存在穿插。"
                ),
            )
        )

    jump_details = metrics.get("jump_transition_details") or []
    if jump_details:
        example = jump_details[0]
        messages.append(
            ValidationMessage(
                level="warning",
                subject_id=example["resource_id"],
                message=(
                    f"发现资源路径不连续：跳墩 {metrics['jump_pier_count']} 次、跳幅 {metrics['side_switch_count']} 次；"
                    f"示例：{example['resource_name']} 从 {example['from_location']} 转到 {example['to_location']}。"
                    "原因初判：为满足工艺前置、资源不可冲突和里程碑目标，当前解存在转场。"
                ),
            )
        )
    return messages


def _task_spatial_sort_key(task: Task) -> tuple[Any, ...]:
    location = _task_location(task)
    side_rank = {"L": 0, "R": 1, "N": 2}.get(location["side"] or "N", 2)
    support_index = location["support_index"] if location["support_index"] is not None else 9999
    return (
        task.bridge_id or "",
        task.work_section_id or "",
        side_rank,
        support_index,
        task.sequence_order,
        _component_rank(task.component_type),
        task.id,
    )


def _task_location(task: Task) -> dict[str, Any]:
    side = _side_code_from_structure_id(task.structure_id)
    support_index = _support_index_from_structure_id(task.structure_id)
    if support_index is None:
        support_index = _extract_first_int(task.structure_name)
    side_label = {"L": "左幅", "R": "右幅", "N": "不分幅"}.get(side or "N", "不分幅")
    if side in {"L", "R"} and not task.structure_name.startswith(side_label):
        label = f"{side_label}{task.structure_name}"
    else:
        label = task.structure_name
    return {
        "structure_id": task.structure_id,
        "structure_type": task.structure_type,
        "side": side,
        "side_label": side_label,
        "support_index": support_index,
        "label": label,
    }


def _side_code_from_structure_id(structure_id: str) -> str | None:
    parts = structure_id.split("-")
    if len(parts) >= 2 and parts[1] in {"L", "R", "N"}:
        return parts[1]
    if len(parts) >= 3 and parts[-2] in {"L", "R", "N"}:
        return parts[-2]
    return None


def _support_index_from_structure_id(structure_id: str) -> int | None:
    parts = structure_id.split("-")
    if len(parts) >= 2 and parts[1] in {"L", "R", "N"}:
        for part in reversed(parts[2:]):
            support_index = _extract_first_int(part)
            if support_index is not None:
                return support_index
        return None
    if len(parts) >= 3 and parts[-2] in {"L", "R", "N"}:
        return _extract_first_int(parts[-1])
    return _extract_first_int(parts[-1] if parts else structure_id)


def _extract_first_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = ""
    for char in value:
        if char.isdigit():
            digits += char
        elif digits:
            break
    return int(digits) if digits else None


def _component_rank(component_type: str) -> int:
    order = {
        "pile": 0,
        "spread_foundation": 1,
        "cap": 2,
        "ground_tie_beam": 3,
        "pier_body": 4,
        "middle_tie_beam": 5,
        "cap_beam": 6,
        "abutment_body": 7,
        "precast_beam": 8,
        "beam_erection": 9,
        "cast_in_place_continuous_beam": 10,
        "cast_in_place_box_beam": 11,
        "steel_box_beam": 12,
        "bridge_deck_system": 13,
    }
    return order.get(component_type, 99)


def _component_type_label(component_type: str) -> str:
    return COMPONENT_TYPE_LABELS.get(component_type, component_type)


def _resource_sort_key(resource: Resource) -> tuple[Any, ...]:
    return _resource_sort_tuple(resource.id, resource.name)


def _resource_sort_tuple(resource_id: str, resource_name: str | None) -> tuple[Any, ...]:
    index = _extract_first_int(resource_id) or _extract_first_int(resource_name) or 9999
    return (resource_id.split("_")[0], index, resource_name or "", resource_id)


def _critical_path_schedule(schedule_input: ScheduleInput) -> dict[str, Any]:
    task_by_id = {task.id: task for task in schedule_input.tasks}
    starts = {task.id: 0 for task in schedule_input.tasks}
    incoming_count = {task.id: 0 for task in schedule_input.tasks}
    outgoing: dict[str, list[PrecedenceLink]] = defaultdict(list)

    for link in schedule_input.precedence_links:
        if link.predecessor_id not in task_by_id or link.successor_id not in task_by_id:
            continue
        outgoing[link.predecessor_id].append(link)
        incoming_count[link.successor_id] += 1

    ready = sorted(task_id for task_id, count in incoming_count.items() if count == 0)
    processed_count = 0
    while ready:
        task_id = ready.pop(0)
        processed_count += 1
        predecessor = task_by_id[task_id]
        predecessor_start = starts[task_id]
        for link in outgoing.get(task_id, []):
            successor = task_by_id[link.successor_id]
            candidate_start = _successor_earliest_start_from_link(
                predecessor_start=predecessor_start,
                predecessor_duration=predecessor.duration_days,
                successor_duration=successor.duration_days,
                link=link,
            )
            if candidate_start > starts[link.successor_id]:
                starts[link.successor_id] = candidate_start
            incoming_count[link.successor_id] -= 1
            if incoming_count[link.successor_id] == 0:
                ready.append(link.successor_id)
                ready.sort()

    if processed_count != len(task_by_id):
        return {"status": "CYCLE"}

    ends = {task_id: starts[task_id] + task.duration_days for task_id, task in task_by_id.items()}
    objective_days = max(ends.values(), default=0)
    milestone_results = _critical_path_milestone_results(schedule_input, starts, ends)
    return {
        "status": "OK",
        "objective_days": objective_days,
        "plan_finish_date": _finish_date(schedule_input.start_date, objective_days),
        "milestone_results": milestone_results,
    }


def _critical_path_milestone_results(
    schedule_input: ScheduleInput,
    starts: dict[str, int],
    ends: dict[str, int],
) -> list[MilestoneResult]:
    results: list[MilestoneResult] = []
    for milestone in schedule_input.milestones:
        scoped_task_ids = _task_ids_for_milestone(milestone, schedule_input.tasks)
        if not scoped_task_ids:
            results.append(_not_evaluated_milestone(milestone))
            continue
        if milestone.target_event == "finish":
            actual_offset = max(ends[task_id] for task_id in scoped_task_ids)
            actual_date = _finish_date(schedule_input.start_date, actual_offset)
        else:
            actual_offset = min(starts[task_id] for task_id in scoped_task_ids)
            actual_date = _offset_date(schedule_input.start_date, actual_offset)
        target_offset = _target_offset(schedule_input.start_date, milestone)
        lateness_days = max(0, actual_offset - target_offset)
        results.append(
            MilestoneResult(
                **milestone.model_dump(),
                actual_date=actual_date,
                actual_offset=actual_offset,
                lateness_days=lateness_days,
                penalty=lateness_days * milestone.penalty_per_day if milestone.mode == "soft" else 0,
                status="late" if lateness_days > 0 else "met",
            )
        )
    return results


def _capacity_window_days(schedule_input: ScheduleInput, fallback_target_days: int | None) -> int | None:
    hard_targets = [
        _target_offset(schedule_input.start_date, milestone)
        for milestone in schedule_input.milestones
        if milestone.mode == "hard" and _task_ids_for_milestone(milestone, schedule_input.tasks)
    ]
    if hard_targets:
        return min(hard_targets)
    return fallback_target_days


def _capacity_window_scope_task_ids(schedule_input: ScheduleInput) -> set[str]:
    hard_scopes: list[tuple[int, set[str]]] = []
    for milestone in schedule_input.milestones:
        if milestone.mode != "hard":
            continue
        task_ids = set(_task_ids_for_milestone(milestone, schedule_input.tasks))
        if task_ids:
            hard_scopes.append((_target_offset(schedule_input.start_date, milestone), task_ids))
    if hard_scopes:
        earliest_target = min(target for target, _ in hard_scopes)
        return set().union(*(task_ids for target, task_ids in hard_scopes if target == earliest_target))
    return {task.id for task in schedule_input.tasks}


def _resource_capacity_lower_bound_diagnostics(
    schedule_input: ScheduleInput,
    groups: list[dict[str, Any]],
    capacity_window_days: int | None,
) -> list[dict[str, Any]]:
    if not capacity_window_days or capacity_window_days <= 0:
        return []

    scoped_task_ids = _capacity_window_scope_task_ids(schedule_input)
    diagnostics: list[dict[str, Any]] = []
    for group in groups:
        resource_type = group["resource_type"]
        scoped_tasks = [
            task
            for task in schedule_input.tasks
            if task.id in scoped_task_ids and resource_type in task.compatible_resource_types
        ]
        total_duration = sum(task.duration_days for task in scoped_tasks)
        if total_duration <= 0:
            continue
        required_minimum = math.ceil(total_duration / capacity_window_days)
        diagnostics.append(
            {
                "resource_pool_id": group["key"],
                "label": group["label"],
                "resource_type": resource_type,
                "window_days": capacity_window_days,
                "scoped_task_count": len(scoped_tasks),
                "workload_days": total_duration,
                "required_minimum": required_minimum,
                "max_quantity": group["max_quantity"],
                "upper_bound_gap": max(0, required_minimum - group["max_quantity"]),
                "exceeds_upper_bound": required_minimum > group["max_quantity"],
            }
        )
    return diagnostics


def _resource_capacity_exclusive_lower_bound_diagnostics(
    schedule_input: ScheduleInput,
    groups: list[dict[str, Any]],
    capacity_window_days: int | None,
) -> list[dict[str, Any]]:
    if not capacity_window_days or capacity_window_days <= 0:
        return []

    scoped_task_ids = _capacity_window_scope_task_ids(schedule_input)
    diagnostics: list[dict[str, Any]] = []
    for group in groups:
        resource_type = group["resource_type"]
        scoped_tasks = [
            task
            for task in schedule_input.tasks
            if task.id in scoped_task_ids and set(task.compatible_resource_types) == {resource_type}
        ]
        total_duration = sum(task.duration_days for task in scoped_tasks)
        if total_duration <= 0:
            continue
        required_minimum = math.ceil(total_duration / capacity_window_days)
        diagnostics.append(
            {
                "resource_pool_id": group["key"],
                "label": group["label"],
                "resource_type": resource_type,
                "window_days": capacity_window_days,
                "scoped_task_count": len(scoped_tasks),
                "workload_days": total_duration,
                "required_minimum": required_minimum,
                "max_quantity": group["max_quantity"],
                "upper_bound_gap": max(0, required_minimum - group["max_quantity"]),
                "exceeds_upper_bound": required_minimum > group["max_quantity"],
                "exclusive_resource_lower_bound": True,
            }
        )
    return diagnostics


def _resource_capacity_lower_bound_messages(
    diagnostics: list[dict[str, Any]],
) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    for item in diagnostics:
        if not item["exceeds_upper_bound"]:
            continue
        messages.append(
            ValidationMessage(
                level="error",
                subject_id=item["resource_pool_id"],
                message=(
                    f"按目标窗口 {item['window_days']} 天和关联任务范围粗算，资源池“{item['label']}”"
                    f"至少需要约 {item['required_minimum']} 个并行资源，当前最大数量为 {item['max_quantity']}。"
                ),
            )
        )
    return messages


def _workface_parallelism_diagnostics(schedule_input: ScheduleInput) -> list[dict[str, Any]]:
    limit = int(schedule_input.schedule_strategy.max_parallel_normal_per_work_section or 0)
    if limit <= 0:
        return []
    control_chain_task_ids = _control_chain_task_ids(schedule_input)
    normal_tasks = _normal_balance_tasks(schedule_input.tasks, control_chain_task_ids)
    by_workface: dict[tuple[str | None, str | None], list[Task]] = defaultdict(list)
    for task in normal_tasks:
        by_workface[(task.bridge_id, task.work_section_id)].append(task)

    diagnostics: list[dict[str, Any]] = []
    for (bridge_id, work_section_id), tasks in by_workface.items():
        if len(tasks) <= limit:
            continue
        total_duration = sum(task.duration_days for task in tasks)
        diagnostics.append(
            {
                "bridge_id": bridge_id,
                "work_section_id": work_section_id,
                "normal_task_count": len(tasks),
                "total_duration_days": total_duration,
                "max_parallel_normal_per_work_section": limit,
                "minimum_workface_days": math.ceil(total_duration / limit),
            }
        )
    return sorted(
        diagnostics,
        key=lambda item: (
            -int(item["minimum_workface_days"]),
            str(item["bridge_id"] or ""),
            str(item["work_section_id"] or ""),
        ),
    )


def _resource_groups(resources: list[Resource]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for resource in sorted(resources, key=_resource_sort_key):
        key = resource.pool_id or resource.type
        if key not in groups:
            groups[key] = {
                "key": key,
                "label": resource.pool_label or resource.type,
                "resource_type": resource.type,
                "max_quantity": 0,
                "resources": [],
                "same_structure_resource_binding": False,
                "same_structure_parallel_limit": None,
                "parallel_rule_description": "",
            }
        groups[key]["resources"].append(resource)
        groups[key]["max_quantity"] += 1
        groups[key]["same_structure_resource_binding"] = (
            groups[key]["same_structure_resource_binding"] or resource.same_structure_resource_binding
        )
        groups[key]["same_structure_parallel_limit"] = _configured_parallel_limit(
            [groups[key]["same_structure_parallel_limit"], resource.same_structure_parallel_limit]
        )
        if not groups[key]["parallel_rule_description"] and resource.parallel_rule_description:
            groups[key]["parallel_rule_description"] = resource.parallel_rule_description
    return sorted(groups.values(), key=lambda group: (group["resource_type"], group["key"], group["label"]))


def _apply_resource_limits(resources: list[Resource], limits: dict[str, int]) -> list[Resource]:
    used_counts: dict[str, int] = defaultdict(int)
    limited: list[Resource] = []
    for resource in sorted(resources, key=_resource_sort_key):
        key = resource.pool_id or resource.type
        limit = limits.get(key)
        if limit is None:
            limited.append(resource)
            continue
        if used_counts[key] < limit:
            limited.append(resource)
            used_counts[key] += 1
    return limited


def _recommended_resource_counts(groups: list[dict[str, Any]], fixed_counts: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {
            "resource_pool_id": group["key"],
            "label": group["label"],
            "resource_type": group["resource_type"],
            "recommended_quantity": fixed_counts.get(group["key"], 0),
            "max_quantity": group["max_quantity"],
        }
        for group in groups
    ]


def _resource_candidates_by_task(
    tasks: list[Task], resources: list[Resource]
) -> dict[str, list[Resource]]:
    candidates: dict[str, list[Resource]] = {}
    ordered_resources = sorted(resources, key=_resource_sort_key)
    for task in tasks:
        compatible_types = set(task.compatible_resource_types)
        candidates[task.id] = [resource for resource in ordered_resources if resource.type in compatible_types]
    return candidates


def _validate_resource_coverage(
    tasks: list[Task], candidates: dict[str, list[Resource]]
) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    constrained_task_count = 0
    missing_candidate_count = 0
    for task in tasks:
        if not task.compatible_resource_types:
            continue
        constrained_task_count += 1
        if not candidates.get(task.id):
            missing_candidate_count += 1
            messages.append(
                ValidationMessage(
                    level="warning",
                    subject_id=task.id,
                    message=(
                        f"“{task.name}”需要以下资源类型之一：{', '.join(task.compatible_resource_types)}，"
                        "但当前没有启用的受限兼容资源，已按资源默认充足处理。"
                    ),
                )
            )
    if constrained_task_count == 0:
        messages.append(
            ValidationMessage(
                level="info",
                message="当前没有工作项需要受限资源，排程仅受工艺逻辑、工期和里程碑影响。",
            )
        )
    elif missing_candidate_count == 0:
        messages.append(
            ValidationMessage(
                level="info",
                message="所有需要受限资源的工作项都至少有一个已启用的兼容资源。",
            )
        )
    return messages


def _validate_solution(
    schedule_input: ScheduleInput,
    scheduled_tasks: list[ScheduledTask],
    allocations: list[ResourceAllocation],
) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    by_task = {task.id: task for task in scheduled_tasks}

    logic_violations = 0
    for link in schedule_input.precedence_links:
        predecessor = by_task.get(link.predecessor_id)
        successor = by_task.get(link.successor_id)
        if not predecessor or not successor:
            continue
        if _precedence_violated(predecessor, successor, link):
            logic_violations += 1

    overlap_violations = 0
    by_resource: dict[str, list[ResourceAllocation]] = defaultdict(list)
    for allocation in allocations:
        by_resource[allocation.resource_id].append(allocation)
    for resource_allocations in by_resource.values():
        ordered = sorted(resource_allocations, key=lambda item: item.start_offset)
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_offset < previous.end_offset:
                overlap_violations += 1

    if logic_violations:
        messages.append(
            ValidationMessage(
                level="error",
                message=f"发现 {logic_violations} 处工艺逻辑未满足，请检查前后关系设置。",
            )
        )
    else:
        messages.append(ValidationMessage(level="info", message="所有工艺逻辑关系均已满足。"))

    if overlap_violations:
        messages.append(
            ValidationMessage(
                level="error", message=f"发现 {overlap_violations} 处资源任务重叠冲突。"
            )
        )
    else:
        messages.append(ValidationMessage(level="info", message="所有启用资源均不存在任务时间重叠。"))

    return messages


def _build_horizon(schedule_input: ScheduleInput) -> int:
    total_duration = sum(task.duration_days for task in schedule_input.tasks)
    total_lag = sum(link.lag_days for link in schedule_input.precedence_links)
    return max(1, total_duration + total_lag + 30)


def _is_lower_or_cast_in_place_beam_task(task: Task) -> bool:
    return task.structure_type in {"pier", "abutment"} or task.component_type in {
        "cast_in_place_continuous_beam",
        "cast_in_place_box_beam",
    }


def _task_ids_for_milestone(milestone: MilestoneConstraint, tasks: list[Task]) -> list[str]:
    related_ids = {
        task.id
        for task in tasks
        if task.structure_id in set(milestone.related_structure_ids)
    }
    if milestone.scope_type == "project":
        return sorted(related_ids | {task.id for task in tasks if _is_lower_or_cast_in_place_beam_task(task)})
    if milestone.scope_type == "bridge":
        return sorted(related_ids | {
            task.id
            for task in tasks
            if task.bridge_id == milestone.scope_id and _is_lower_or_cast_in_place_beam_task(task)
        })
    if milestone.scope_type == "work_section":
        return sorted(related_ids | {
            task.id
            for task in tasks
            if task.work_section_id == milestone.scope_id and _is_lower_or_cast_in_place_beam_task(task)
        })
    if milestone.scope_type == "structure":
        return sorted(related_ids | {task.id for task in tasks if task.structure_id == milestone.scope_id})
    if milestone.scope_type == "component":
        if milestone.scope_id in get_args(ComponentType):
            return sorted(related_ids | {task.id for task in tasks if task.component_type == milestone.scope_id})
        return sorted(related_ids | {
            task.id
            for task in tasks
            if task.component_id == milestone.scope_id or task.id == milestone.scope_id
        })
    return sorted(related_ids)


def _matched_hard_milestone_count(schedule_input: ScheduleInput) -> int:
    return sum(
        1
        for milestone in schedule_input.milestones
        if milestone.mode == "hard" and _task_ids_for_milestone(milestone, schedule_input.tasks)
    )


def _unmatched_hard_milestone_warnings(schedule_input: ScheduleInput) -> list[ValidationMessage]:
    return [
        ValidationMessage(level="warning", subject_id=milestone.id, message=f"强制里程碑目标“{milestone.name}”没有匹配的工作项，不能作为固定工期目标。")
        for milestone in schedule_input.milestones
        if milestone.mode == "hard" and not _task_ids_for_milestone(milestone, schedule_input.tasks)
    ]


def _min_resource_target_days(schedule_input: ScheduleInput, fallback_target_days: int | None) -> int | None:
    matched_targets = [
        _target_offset(schedule_input.start_date, milestone)
        for milestone in schedule_input.milestones
        if milestone.mode == "hard" and _task_ids_for_milestone(milestone, schedule_input.tasks)
    ]
    if matched_targets:
        return max(matched_targets)
    return fallback_target_days


def _target_offset(start_date: date, milestone: MilestoneConstraint) -> int:
    offset = (milestone.target_date - start_date).days
    if milestone.target_event == "finish":
        return offset + 1
    return offset


def _milestone_by_id(milestones: list[MilestoneConstraint], milestone_id: str) -> MilestoneConstraint:
    return next(milestone for milestone in milestones if milestone.id == milestone_id)


def _build_milestone_results(
    schedule_input: ScheduleInput,
    milestone_vars: dict[str, Any],
    milestone_target_offsets: dict[str, int],
    soft_lateness_vars: dict[str, Any],
    solver: Any,
) -> list[MilestoneResult]:
    results: list[MilestoneResult] = []
    for milestone in schedule_input.milestones:
        event_var = milestone_vars.get(milestone.id)
        if event_var is None:
            results.append(_not_evaluated_milestone(milestone))
            continue

        actual_offset = solver.Value(event_var)
        target_offset = milestone_target_offsets[milestone.id]
        if milestone.mode == "soft" and milestone.id in soft_lateness_vars:
            lateness_days = solver.Value(soft_lateness_vars[milestone.id])
        else:
            lateness_days = max(0, actual_offset - target_offset)
        penalty = lateness_days * milestone.penalty_per_day if milestone.mode == "soft" else 0
        actual_date = (
            _finish_date(schedule_input.start_date, actual_offset)
            if milestone.target_event == "finish"
            else _offset_date(schedule_input.start_date, actual_offset)
        )
        results.append(
            MilestoneResult(
                id=milestone.id,
                name=milestone.name,
                level=milestone.level,
                mode=milestone.mode,
                scope_type=milestone.scope_type,
                scope_id=milestone.scope_id,
                target_event=milestone.target_event,
                target_date=milestone.target_date,
                actual_date=actual_date,
                actual_offset=actual_offset,
                lateness_days=lateness_days,
                penalty=penalty,
                status="late" if lateness_days > 0 else "met",
            )
        )
    return results


def _validate_milestone_results(results: list[MilestoneResult]) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    late_soft = [result for result in results if result.mode == "soft" and result.lateness_days > 0]
    late_hard = [result for result in results if result.mode == "hard" and result.lateness_days > 0]
    if late_hard:
        messages.append(
            ValidationMessage(level="error", message=f"{len(late_hard)} 个强制里程碑目标发生迟延。")
        )
    if late_soft:
        messages.append(
            ValidationMessage(level="warning", message=f"{len(late_soft)} 个提醒里程碑目标发生迟延。")
        )
    if results and not late_hard and not late_soft:
        messages.append(ValidationMessage(level="info", message="所有已评估里程碑均已满足。"))
    return messages


def _not_evaluated_milestones(milestones: list[MilestoneConstraint]) -> list[MilestoneResult]:
    return [_not_evaluated_milestone(milestone) for milestone in milestones]


def _not_evaluated_milestone(milestone: MilestoneConstraint) -> MilestoneResult:
    return MilestoneResult(
        id=milestone.id,
        name=milestone.name,
        level=milestone.level,
        mode=milestone.mode,
        scope_type=milestone.scope_type,
        scope_id=milestone.scope_id,
        target_event=milestone.target_event,
        target_date=milestone.target_date,
    )


def _status_name(status_code: int, cp_model: Any) -> str:
    status_names = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }
    return status_names.get(status_code, "UNKNOWN")


def _assigned_resource_for_task(
    task: Task,
    candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
    solver: Any,
) -> Resource | None:
    for resource in candidates.get(task.id, []):
        assignment = assignment_vars.get((task.id, resource.id))
        if assignment is not None and solver.BooleanValue(assignment):
            return resource
    return None


def _offset_date(start_date: date, offset: int) -> date:
    return start_date + timedelta(days=offset)


def _finish_date(start_date: date, end_offset: int) -> date:
    return start_date + timedelta(days=max(0, end_offset - 1))


def _safe(value: str) -> str:
    return value.replace("-", "_").replace("#", "_")
