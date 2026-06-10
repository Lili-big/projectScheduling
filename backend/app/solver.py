from __future__ import annotations

import math
from collections import defaultdict
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
SAME_STRUCTURE_CRAFT_SPLIT_WEIGHT = 1_000
SPATIAL_RESOURCE_ASSIGNMENT_WEIGHT = 1

COMPONENT_TYPE_LABELS: dict[str, str] = {
    "pile": "桩基",
    "cap": "承台",
    "spread_foundation": "扩大基础",
    "ground_tie_beam": "地系梁",
    "middle_tie_beam": "中系梁",
    "pier_body": "墩柱",
    "cap_beam": "盖梁",
    "abutment_body": "桥台",
}


def solve_schedule(schedule_input: ScheduleInput) -> ScheduleResult:
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
        if link.relationship == "SS":
            model.Add(starts[successor.id] >= starts[predecessor.id] + link.lag_days)
        else:
            model.Add(starts[successor.id] >= ends[predecessor.id] + link.lag_days)

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
        if milestone.mode == "soft":
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
    solver.parameters.max_time_in_seconds = schedule_input.time_limit_seconds
    solver.parameters.num_search_workers = 8
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)

    stats = {
        "horizon_days": horizon,
        "wall_time_seconds": solver.WallTime(),
        "conflicts": solver.NumConflicts(),
        "branches": solver.NumBranches(),
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

    groups = _resource_groups(enabled_resources)
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

    capacity_optimization = _solve_capacity_model(
        schedule_input,
        cp_model=cp_model,
        groups=groups,
        counts=None,
        fallback_target_days=target_days if hard_match_count == 0 else None,
        enforce_fixed_duration=True,
        minimize_resource_count=True,
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
            },
        )

    fixed_counts = {key: int(value) for key, value in capacity_optimization["group_counts"].items()}
    phase_stats = [
        {"resource_pool_id": group["key"], "label": group["label"], "recommended_quantity": fixed_counts.get(group["key"], 0)}
        for group in groups
    ]

    final = _solve_resource_model(
        schedule_input,
        cp_model=cp_model,
        fixed_counts=fixed_counts,
        minimize_group_key=None,
        fallback_target_days=target_days if hard_match_count == 0 else None,
        enforce_fixed_duration=True,
        feasibility_only=False,
    )
    if final["status"] not in {"OPTIMAL", "FEASIBLE"}:
        return ScheduleResult(
            status=final["status"],
            plan_start_date=schedule_input.start_date,
            validation=validation
            + final["validation"]
            + [ValidationMessage(level="error", message="推荐资源数量固定后未找到可行排程。")],
            stats={
                **final["stats"],
                "reason": "recommended_resource_counts_infeasible",
                "solve_mode": "min_resources_fixed_duration",
                "target_days": target_days,
                "recommended_resource_counts": _recommended_resource_counts(groups, fixed_counts),
            },
        )

    result = _resource_model_result(schedule_input, final)
    recommended = _recommended_resource_counts(groups, fixed_counts)
    result.stats.update(
        {
            "solve_mode": "min_resources_fixed_duration",
            "target_days": target_days,
            "recommended_resource_counts": recommended,
            "resource_optimization_phases": phase_stats,
        }
    )
    result.objective_breakdown.update(
        {
            "solve_mode": "min_resources_fixed_duration",
            "target_days": target_days,
            "recommended_resource_counts": recommended,
        }
    )
    return result


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
        if link.relationship == "SS":
            model.Add(starts[successor.id] >= starts[predecessor.id] + link.lag_days)
        else:
            model.Add(starts[successor.id] >= ends[predecessor.id] + link.lag_days)

    for intervals in resource_intervals.values():
        model.AddNoOverlap(intervals)

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
    solver.parameters.max_time_in_seconds = schedule_input.time_limit_seconds
    solver.parameters.num_search_workers = 8
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
) -> dict[str, Any]:
    validation: list[ValidationMessage] = []
    model = cp_model.CpModel()
    horizon = _build_horizon(schedule_input)
    starts: dict[str, Any] = {}
    ends: dict[str, Any] = {}
    task_by_id = {task.id: task for task in schedule_input.tasks}
    group_by_type = {group["resource_type"]: group for group in groups}
    intervals_by_group: dict[str, list[Any]] = defaultdict(list)
    demands_by_group: dict[str, list[int]] = defaultdict(list)
    milestone_vars: dict[str, Any] = {}
    soft_lateness_vars: dict[str, Any] = {}
    count_vars: dict[str, Any] = {}

    for task in schedule_input.tasks:
        starts[task.id] = model.NewIntVar(0, horizon, f"start_{_safe(task.id)}")
        ends[task.id] = model.NewIntVar(0, horizon, f"end_{_safe(task.id)}")
        model.Add(ends[task.id] == starts[task.id] + task.duration_days)
        choices = []
        for resource_type in task.compatible_resource_types:
            group = group_by_type.get(resource_type)
            if not group:
                continue
            assigned = model.NewBoolVar(f"capacity_assign_{_safe(task.id)}_{_safe(group['key'])}")
            interval = model.NewOptionalIntervalVar(
                starts[task.id],
                task.duration_days,
                ends[task.id],
                assigned,
                f"capacity_interval_{_safe(task.id)}_{_safe(group['key'])}",
            )
            choices.append(assigned)
            intervals_by_group[group["key"]].append(interval)
            demands_by_group[group["key"]].append(1)
        if choices:
            model.AddExactlyOne(choices)
        else:
            validation.append(
                ValidationMessage(
                    level="error",
                    subject_id=task.id,
                    message=f"“{task.name}”没有可用于容量校验的兼容资源池。",
                )
            )

    for group in groups:
        intervals = intervals_by_group.get(group["key"], [])
        if counts is None:
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
        if link.relationship == "SS":
            model.Add(starts[successor.id] >= starts[predecessor.id] + link.lag_days)
        else:
            model.Add(starts[successor.id] >= ends[predecessor.id] + link.lag_days)

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
        event_var = model.NewIntVar(0, horizon, f"capacity_milestone_{_safe(milestone.id)}")
        event_vars = [ends[task_id] if milestone.target_event == "finish" else starts[task_id] for task_id in scoped_task_ids]
        if milestone.target_event == "finish":
            model.AddMaxEquality(event_var, event_vars)
        else:
            model.AddMinEquality(event_var, event_vars)

        target_offset = _target_offset(schedule_input.start_date, milestone)
        milestone_vars[milestone.id] = event_var
        if milestone.mode == "hard" and enforce_fixed_duration:
            hard_match_count += 1
            model.Add(event_var <= target_offset)
        else:
            lateness_upper = max(horizon - target_offset, horizon) + 365
            lateness_var = model.NewIntVar(0, lateness_upper, f"capacity_late_{_safe(milestone.id)}")
            model.Add(lateness_var >= event_var - target_offset)
            soft_lateness_vars[milestone.id] = lateness_var

    if enforce_fixed_duration and hard_match_count == 0 and fallback_target_days is not None:
        model.Add(makespan <= fallback_target_days)

    if minimize_resource_count:
        model.Minimize(sum(count_vars.values()) * (horizon + 1) + makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = schedule_input.time_limit_seconds
    solver.parameters.num_search_workers = 8
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)
    return {
        "status": status,
        "validation": validation,
        "stats": {
            "horizon_days": horizon,
            "wall_time_seconds": solver.WallTime(),
            "conflicts": solver.NumConflicts(),
            "branches": solver.NumBranches(),
        },
        "group_counts": (
            {key: solver.Value(count_var) for key, count_var in count_vars.items()}
            if counts is None and status in {"OPTIMAL", "FEASIBLE"}
            else (counts if counts is not None and status in {"OPTIMAL", "FEASIBLE"} else {})
        ),
    }


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

    stats = {
        **checked["stats"],
        "reason": "resource_upper_bound_or_deadline_infeasible",
        "solve_mode": "min_resources_fixed_duration",
        "target_days": target_days,
        "capacity_window_days": capacity_window_days,
        "max_resource_counts": [
            {
                "resource_pool_id": group["key"],
                "label": group["label"],
                "resource_type": group["resource_type"],
                "max_quantity": group["max_quantity"],
            }
            for group in groups
        ],
        "fixed_duration_precheck_failed": True,
    }
    objective_breakdown: dict[str, Any] = {
        "solve_mode": "min_resources_fixed_duration",
        "target_days": target_days,
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
            messages.extend(_resource_capacity_lower_bound_messages(schedule_input, groups, capacity_window_days))
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
        "continuity_score": continuity_score,
        "resource_paths": path_metrics["resource_paths"],
        "jump_transition_details": path_metrics["jump_transition_details"][:30],
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
    max_jump_distance = 0

    for resource_id, tasks in sorted(by_resource.items(), key=lambda item: _resource_sort_tuple(item[0], resource_meta[item[0]]["resource_name"])):
        ordered = sorted(tasks, key=lambda task: (task.start_offset, task.end_offset, *_task_spatial_sort_key(task)))
        path_jump_count = 0
        path_side_switch_count = 0
        path_cross_side_jump_count = 0
        previous_direction: int | None = None

        for previous, current in zip(ordered, ordered[1:]):
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
        "resource_paths": resource_paths,
        "jump_transition_details": jump_transition_details,
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
    if len(parts) >= 3 and parts[-2] in {"L", "R", "N"}:
        return parts[-2]
    return None


def _support_index_from_structure_id(structure_id: str) -> int | None:
    parts = structure_id.split("-")
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
        predecessor_end = predecessor_start + predecessor.duration_days
        for link in outgoing.get(task_id, []):
            if link.relationship == "SS":
                candidate_start = predecessor_start + link.lag_days
            else:
                candidate_start = predecessor_end + link.lag_days
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


def _resource_capacity_lower_bound_messages(
    schedule_input: ScheduleInput,
    groups: list[dict[str, Any]],
    capacity_window_days: int | None,
) -> list[ValidationMessage]:
    if not capacity_window_days or capacity_window_days <= 0:
        return []

    messages: list[ValidationMessage] = []
    for group in groups:
        resource_type = group["resource_type"]
        total_duration = sum(
            task.duration_days
            for task in schedule_input.tasks
            if resource_type in task.compatible_resource_types
        )
        if total_duration <= 0:
            continue
        required_minimum = math.ceil(total_duration / capacity_window_days)
        if required_minimum > group["max_quantity"]:
            messages.append(
                ValidationMessage(
                    level="error",
                    subject_id=group["key"],
                    message=(
                        f"按目标窗口 {capacity_window_days} 天粗算，资源池“{group['label']}”"
                        f"至少需要约 {required_minimum} 个并行资源，当前最大数量为 {group['max_quantity']}。"
                    ),
                )
            )
    if not messages:
        messages.append(
            ValidationMessage(
                level="warning",
                message="未发现单一资源池总工作量明显超过目标窗口，可能是多资源组合、里程碑范围或工艺逻辑局部约束导致不可行。",
            )
        )
    return messages


def _resource_groups(resources: list[Resource]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for resource in resources:
        key = resource.pool_id or resource.type
        if key not in groups:
            groups[key] = {
                "key": key,
                "label": resource.pool_label or resource.type,
                "resource_type": resource.type,
                "max_quantity": 0,
                "resources": [],
            }
        groups[key]["resources"].append(resource)
        groups[key]["max_quantity"] += 1
    return list(groups.values())


def _apply_resource_limits(resources: list[Resource], limits: dict[str, int]) -> list[Resource]:
    used_counts: dict[str, int] = defaultdict(int)
    limited: list[Resource] = []
    for resource in resources:
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
    for task in tasks:
        compatible_types = set(task.compatible_resource_types)
        candidates[task.id] = [resource for resource in resources if resource.type in compatible_types]
    return candidates


def _validate_resource_coverage(
    tasks: list[Task], candidates: dict[str, list[Resource]]
) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    for task in tasks:
        if not candidates.get(task.id):
            messages.append(
                ValidationMessage(
                    level="error",
                    subject_id=task.id,
                    message=(
                        f"“{task.name}”需要以下资源类型之一：{', '.join(task.compatible_resource_types)}，"
                        "但当前没有启用的兼容资源。"
                    ),
                )
            )
    if not messages:
        messages.append(
            ValidationMessage(
                level="info",
                message="所有工作项都至少有一个已启用的兼容资源。",
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
        if link.relationship == "SS":
            violated = successor.start_offset < predecessor.start_offset + link.lag_days
        else:
            violated = successor.start_offset < predecessor.end_offset + link.lag_days
        if violated:
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


def _task_ids_for_milestone(milestone: MilestoneConstraint, tasks: list[Task]) -> list[str]:
    if milestone.scope_type == "project":
        return [task.id for task in tasks]
    if milestone.scope_type == "bridge":
        return [task.id for task in tasks if task.bridge_id == milestone.scope_id]
    if milestone.scope_type == "work_section":
        return [task.id for task in tasks if task.work_section_id == milestone.scope_id]
    if milestone.scope_type == "structure":
        return [task.id for task in tasks if task.structure_id == milestone.scope_id]
    if milestone.scope_type == "component":
        if milestone.scope_id in get_args(ComponentType):
            return [task.id for task in tasks if task.component_type == milestone.scope_id]
        return [
            task.id
            for task in tasks
            if task.component_id == milestone.scope_id or task.id == milestone.scope_id
        ]
    return []


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
