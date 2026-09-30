"""Fixed named fleets, hard construction rules, earliest construction finish."""
from collections import defaultdict
from datetime import timedelta, date
from graphlib import TopologicalSorter, CycleError
import hashlib
import json
import math
import os
from threading import Event, Thread
from time import perf_counter

from ortools.sat.python import cp_model

from ....contracts import ScheduleResult, ScheduledTask, ResourceAllocation, ValidationMessage, MilestoneResult, ScheduleStrategyConfig
from ....contracts.pavement import (PavementSummary, PavementTransfer, PavementWaitInterval,
    PavementHandoverScope, PavementPendingSection, PavementPendingSectionDates, PavementOptimization, PavementIdleOptimization)
from ....process_library_defaults import PAVEMENT_PROCESSES
from ....project_master.validation import pavement_quantity_errors, resolve_roadbed_handover, roadbed_start_offset
from ...domain.milestone_scope import task_ids_for_milestone
from ...domain.resource_scope import pavement_resource_matches, PAVEMENT_SHARED_RESOURCE_TYPE
from ...domain.shift_regime import shift_config_errors, task_duration_for_start
from ..constraints.pavement import add_pavement_fleet_paths
from .pavement_heuristic import (Candidate, ready_offset, milestone_offsets, terminal_task_ids, transfer_days,
    generate_initial_candidates, validate_candidate, idle_metrics, Candidate, BudgetExpired, check_deadline,
    pavement_duration)


def validate_pavement_schedule(schedule):
    errors = []
    def error(code, text, subject=None):
        errors.append(ValidationMessage(level="error", code=code, message=text, subject_id=subject))
    if schedule.schedule_strategy != ScheduleStrategyConfig():
        error("PAVEMENT_STRATEGY_NOT_SUPPORTED", "路面首版仅支持固定机组、最早施工完成目标，不支持桥梁策略参数。")
    for issue in shift_config_errors(schedule.shift_regimes):
        error("PAVEMENT_SHIFT_INVALID", {"shift_range": "班制区间的结束日不能早于起始日。",
            "shift_overlap": "班制区间相互重叠或起点重复，请合并或调整区间。"}.get(issue.split(":", 1)[0], "班制区间配置无效。"))
    tasks = {t.id: t for t in schedule.tasks}
    if not tasks or len(tasks) != len(schedule.tasks): error("PAVEMENT_DATA_INCOMPLETE", "任务为空或ID重复。")
    if len({r.id for r in schedule.resources}) != len(schedule.resources): error("PAVEMENT_REFERENCE_INVALID", "机组ID重复。")
    candidates = {}
    positions = defaultdict(list)
    section_handover = {}
    scope = schedule.pavement_handover_scope
    if scope:
        if scope.pending_policy == "strict_last":
            error("PAVEMENT_INPUT_OUTDATED", "待移交段后置规则已调整为按机组后置，请重新生成任务后求解。")
        if scope.blocked_sections:
            error("PAVEMENT_INPUT_OUTDATED" if scope.pending_policy is None else "PAVEMENT_REFERENCE_INVALID",
                "待移交段现需纳入后置排程，请重新生成完整任务。")
        included_ids = {t.structure_id for t in schedule.tasks}
        core = [t for t in schedule.tasks if t.pavement_context and t.pavement_context.task_kind == "construction"]
        if (scope.total_section_count != scope.included_section_count
            or scope.included_section_count != len(included_ids) or scope.included_layer_count != len(core)):
            error("PAVEMENT_REFERENCE_INVALID", "路床移交范围与任务不一致，请重新生成任务。")
    for task in schedule.tasks:
        context = task.pavement_context
        candidates[task.id] = []
        if not context or task.structure_type != "pavement_section":
            error("PAVEMENT_SCOPE_NOT_SUPPORTED", "路面任务缺少明确的施工位置与来源。", task.id); continue
        try:
            status, available, _ = resolve_roadbed_handover(task.properties)
            if task.structure_id in section_handover and section_handover[task.structure_id] != (status, available):
                error("PAVEMENT_ROADBED_INVALID", "同一施工段的路床移交条件不一致。", task.id)
            section_handover[task.structure_id] = (status, available)
        except ValueError as exc: error("PAVEMENT_ROADBED_INVALID", str(exc), task.id)
        if context.task_kind == "construction":
            for code, text in pavement_quantity_errors(task.properties, task.quantity, task.properties.get("unit")):
                error(code, text, task.id)
            positions[context.position_id].append(task)
            expected = PAVEMENT_PROCESSES.get(task.component_type)
            if not expected or context.process_type != task.component_type or task.compatible_resource_types != [expected[1]]:
                error("PAVEMENT_RESOURCE_MISSING", "核心结构层的工艺类别与资源需求不一致。", task.id)
            else:
                if not context.process_id and any(r.enabled and r.compatible_process_ids is not None and task.bridge_id in r.eligible_workpoint_ids for r in schedule.resources):
                    error("PAVEMENT_REFERENCE_INVALID", "任务缺少实际工艺ID，请重新生成任务后求解。", task.id)
                candidates[task.id] = [r for r in schedule.resources if pavement_resource_matches(task, r)]
            if not candidates[task.id]: error("PAVEMENT_RESOURCE_MISSING", "结构层无可用命名机组。", task.id)
        elif task.component_type != "pavement_preparation" or task.compatible_resource_types:
            error("PAVEMENT_REFERENCE_INVALID", "配套任务类别或主机组配置无效。", task.id)
        else:
            for field in ("wait_days", "accepted_available_offset"):
                value = task.properties.get(field, 0)
                if type(value) is not int or value < 0:
                    error("PAVEMENT_DATA_INCOMPLETE", "配套步骤等待和可用日期边界必须为非负整数。", task.id)
    if scope:
        pending = scope.pending_sections or []
        pending_ids = [s.structure_id for s in pending]
        actual_ids = {sid for sid, (status, _) in section_handover.items() if status == "pending"}
        if (len(set(pending_ids)) != len(pending_ids) or set(pending_ids) != actual_ids
            or (scope.pending_policy is not None and scope.pending_sections is None)):
            error("PAVEMENT_REFERENCE_INVALID", "待移交段清单与任务状态不一致，请重新生成任务。")
        for section in pending:
            expected = {t.component_id for t in core if t.structure_id == section.structure_id}
            if len(set(section.component_ids)) != len(section.component_ids) or set(section.component_ids) != expected:
                error("PAVEMENT_REFERENCE_INVALID", "待移交段的结构层范围与任务不一致。", section.structure_id)
            section_tasks = [t for t in schedule.tasks if t.structure_id == section.structure_id]
            for task in section_tasks:
                try:
                    if resolve_roadbed_handover(task.properties)[2] != section.reason:
                        error("PAVEMENT_REFERENCE_INVALID", "待移交原因与任务来源不一致。", section.structure_id)
                        break
                except ValueError:
                    pass  # The task's invalid handover already has a diagnostic.
    for resource in schedule.resources:
        if not resource.enabled: continue
        ids = resource.compatible_process_ids
        if resource.type not in {v[1] for v in PAVEMENT_PROCESSES.values()} | {PAVEMENT_SHARED_RESOURCE_TYPE}:
            error("PAVEMENT_REFERENCE_INVALID", "机组类别无效。", resource.id)
        if (ids is not None and (not ids or any(not p.strip() for p in ids) or len(set(ids)) != len(ids))) or (ids is None and resource.type == PAVEMENT_SHARED_RESOURCE_TYPE):
            error("PAVEMENT_REFERENCE_INVALID", "机组缺少有效的适用工艺。", resource.id)
        if resource.transfer_days is None:
            error("PAVEMENT_TRANSFER_UNCONFIRMED", "机组转场天数未确认。", resource.id)
    graph = {t: set() for t in tasks}
    for link in schedule.precedence_links:
        if link.predecessor_id not in tasks or link.successor_id not in tasks:
            error("PAVEMENT_REFERENCE_INVALID", "路面关系须引用有效任务。", link.id)
        else: graph[link.successor_id].add(link.predecessor_id)
    try: order = list(TopologicalSorter(graph).static_order())
    except CycleError:
        error("PAVEMENT_LOGIC_CYCLE", "工序关系存在循环。"); order = []
    ancestors = {}
    for tid in order:
        ancestors[tid] = set(graph[tid])
        for parent in graph[tid]: ancestors[tid].update(ancestors.get(parent, set()))
    terminal_ids = set()
    for group in positions.values():
        group.sort(key=lambda t: (t.sequence_order, t.id))
        if len({t.sequence_order for t in group}) != len(group) or any(t.sequence_order <= 0 for t in group):
            error("PAVEMENT_DATA_INCOMPLETE", "实际层序缺失或重复。")
        terminal_ids.add(group[-1].id)
        for first, second in zip(group, group[1:]):
            if first.id not in ancestors.get(second.id, set()): error("PAVEMENT_REFERENCE_INVALID", "缺少实际层序的前置关系。", second.id)
    if schedule.readiness_conditions:
        error("PAVEMENT_INPUT_OUTDATED", "本轮不计算末尾养生，请按当前工序链重新生成任务。")
    for task in schedule.tasks:
        if not task.pavement_context or task.pavement_context.task_kind != "construction": continue
        if task.id in terminal_ids:
            if task.properties.get("wait_days", 0) != 0 or task.properties.get("accepted_available_offset", 0) != 0:
                error("PAVEMENT_INPUT_OUTDATED", "旧任务包含末尾养生或验收条件，请按当前工序链重新生成任务。", task.id)
        else:
            if not task.properties.get("wait_basis") or type(task.properties.get("wait_days")) is not int or task.properties["wait_days"] < 0:
                error("PAVEMENT_DATA_INCOMPLETE", "缺少已确认的层间技术间歇。", task.id)
            if type(task.properties.get("accepted_available_offset")) is not int or task.properties["accepted_available_offset"] < 0:
                error("PAVEMENT_DATA_INCOMPLETE", "验收可用日期边界无效。", task.id)
    return errors, candidates


def _result_handover_scope(schedule):
    """After validation, derive direct-input scope without modifying the request."""
    if schedule.pavement_handover_scope:
        return schedule.pavement_handover_scope.model_copy(update={"pending_policy": "per_fleet_last",
            "pending_sections": schedule.pavement_handover_scope.pending_sections or []})
    groups = defaultdict(list)
    for task in schedule.tasks:
        groups[task.structure_id].append(task)
    pending = []
    for sid, tasks in groups.items():
        status, _, note = resolve_roadbed_handover(tasks[0].properties)
        if status == "pending":
            pending.append(PavementPendingSection(structure_id=sid, section_name=tasks[0].structure_name or sid,
                reason=note, component_ids=[t.component_id for t in tasks if t.pavement_context.task_kind == "construction"]))
    return PavementHandoverScope(total_section_count=len(groups), included_section_count=len(groups),
        included_layer_count=sum(t.pavement_context.task_kind == "construction" for t in schedule.tasks),
        pending_policy="per_fleet_last", pending_sections=pending)


def _build_model(schedule, candidates, initial, deadline, control=None, *, minimize_idle=False):
    from ..engine import _add_precedence_constraint, _add_execution_constraints
    def checkpoint():
        if control:
            control.check()
        check_deadline(deadline, perf_counter)
    checkpoint()
    latest = max([0] + [max(c.earliest_start_offset or 0, c.fixed_start_offset or 0) for c in schedule.execution_constraints]
        + [c.available_offset for c in schedule.readiness_conditions]
        + [int(t.properties.get("accepted_available_offset", 0)) for t in schedule.tasks]
        + [roadbed_start_offset(t.properties, schedule.start_date, allow_pending=True) for t in schedule.tasks])
    horizon = latest + sum(t.duration_days + int(t.properties.get("wait_days", 0)) for t in schedule.tasks) + sum(max(0, l.lag_days) for l in schedule.precedence_links) + max([0] + [r.transfer_days or 0 for r in schedule.resources]) * max(0, len(schedule.tasks)-1) + 1
    horizon = max(horizon, initial.makespan if initial else 0)
    model = cp_model.CpModel()
    starts, ends, dvars = {}, {}, {}
    for task in schedule.tasks:
        checkpoint()
        starts[task.id] = model.NewIntVar(0, horizon, f"start:{task.id}")
        ends[task.id] = model.NewIntVar(0, horizon, f"end:{task.id}")
        if schedule.shift_regimes:
            durations = [task_duration_for_start(task, offset, schedule.shift_regimes, schedule.start_date)
                         for offset in range(horizon + 1)]
            duration = model.NewIntVar(min(durations), max(durations), f"duration:{task.id}")
            model.AddAllowedAssignments([starts[task.id], duration], list(enumerate(durations)))
        else:
            duration = task.duration_days
        dvars[task.id] = duration
        model.Add(ends[task.id] == starts[task.id] + duration)
    # The selected route of each actual fleet enforces normal-before-pending.
    # Other fleets' normal tasks do not impose a global start boundary.
    assignments, arcs, route_vars = add_pavement_fleet_paths(model, schedule.tasks, schedule.resources, candidates, starts, ends, horizon, schedule.precedence_links, checkpoint, durations=dvars)
    _add_execution_constraints(model, schedule, starts, candidates, assignments)
    for link in schedule.precedence_links:
        checkpoint()
        _add_precedence_constraint(model, starts, ends, link)
    by_id = {t.id:t for t in schedule.tasks}
    # Reapply confirmed lower bounds, including on direct /solve payloads.
    ready_by_task = {}
    for task in schedule.tasks:
        checkpoint()
        wait = int(task.properties.get("wait_days", 0))
        available = int(task.properties.get("accepted_available_offset", 0))
        ready = model.NewIntVar(0, horizon, f"available:{task.id}")
        model.AddMaxEquality(ready, [ends[task.id]+wait, available])
        ready_by_task[task.id] = ready
        model.Add(starts[task.id] >= roadbed_start_offset(task.properties, schedule.start_date, allow_pending=True))
    for link in schedule.precedence_links:
        checkpoint()
        if link.source_rule_id == "pavement_layer_condition":
            if link.relationship == "FS":
                model.Add(starts[link.successor_id] >= ready_by_task[link.predecessor_id])
            else:
                model.Add(starts[link.successor_id] >= int(by_id[link.predecessor_id].properties.get("accepted_available_offset", 0)))
    whole_ready = model.NewIntVar(0,horizon,"whole_scope_ready")
    model.AddMaxEquality(whole_ready, list(ends.values()))
    terminal_ids = terminal_task_ids(schedule.tasks)
    milestone_vars = {}
    for milestone in schedule.milestones:
        checkpoint()
        ids = task_ids_for_milestone(milestone, schedule.tasks)
        value = model.NewIntVar(0,horizon,f"milestone:{milestone.id}")
        if milestone.target_event == "start": model.AddMinEquality(value,[starts[t] for t in ids])
        else: model.AddMaxEquality(value,[ends[t]-1 if t in terminal_ids else ready_by_task[t] for t in ids])
        milestone_vars[milestone.id] = value
        if milestone.mode == "hard": model.Add(value <= (milestone.target_date-schedule.start_date).days)
    if minimize_idle:
        idle_vars = []
        for resource in schedule.resources:
            checkpoint()
            empty = route_vars.get((resource.id, None, None))
            if empty is None:
                continue
            first = model.NewIntVar(0, horizon, f"fleet_first:{resource.id}")
            last = model.NewIntVar(0, horizon, f"fleet_last:{resource.id}")
            model.Add(first == 0).OnlyEnforceIf(empty)
            model.Add(last == 0).OnlyEnforceIf(empty)
            work = []
            for task in schedule.tasks:
                assigned = assignments.get((task.id, resource.id))
                if assigned is None:
                    continue
                model.Add(first == starts[task.id]).OnlyEnforceIf(route_vars[resource.id, None, task.id])
                model.Add(last == ends[task.id]).OnlyEnforceIf(route_vars[resource.id, task.id, None])
                # Variable shift durations cannot multiply into a BoolVar; linearize.
                work_var = model.NewIntVar(0, horizon, f"work:{resource.id}:{task.id}")
                model.Add(work_var == dvars[task.id]).OnlyEnforceIf(assigned)
                model.Add(work_var == 0).OnlyEnforceIf(assigned.Not())
                work.append(work_var)
            transfer = sum(days * arc for r, a, b, days, arc in arcs if r.id == resource.id)
            idle = model.NewIntVar(0, horizon, f"fleet_idle:{resource.id}")
            model.Add(idle == last - first - sum(work) - transfer)
            idle_vars.append(idle)
        model.Minimize(sum(idle_vars))
    else:
        model.Minimize(whole_ready)
    if initial:
        model.Add(whole_ready <= initial.makespan)
        for task in schedule.tasks:
            checkpoint()
            model.AddHint(starts[task.id], initial.starts[task.id])
            model.AddHint(ends[task.id], initial.ends[task.id])
            model.AddHint(ready_by_task[task.id], ready_offset(task, initial.ends[task.id]))
        for (tid, rid), var in assignments.items():
            checkpoint()
            model.AddHint(var, int(initial.assignments.get(tid) == rid))
        selected_edges = set()
        for rid, route in initial.routes.items():
            selected_edges.update((rid, a, b) for a, b in zip([None] + route, route + [None]))
        missing = selected_edges - set(route_vars)
        if missing:
            raise HintInconsistent(f"Initial route was pruned: {sorted(map(str, missing))}")
        for (rid, a, b), var in route_vars.items():
            checkpoint()
            selected = not initial.routes.get(rid) if a is None and b is None else (rid, a, b) in selected_edges
            model.AddHint(var, int(selected))
        for mid, offset in milestone_offsets(schedule, initial).items():
            model.AddHint(milestone_vars[mid], offset)
        model.AddHint(whole_ready, initial.makespan)
    checkpoint()
    return model, starts, ends, assignments, horizon


class HintInconsistent(Exception):
    """A validated seed must remain representable after safe pruning."""


class SolveCancelled(Exception):
    """The consumer no longer needs this request's solve."""


class SolveControl:
    def __init__(self):
        self.cancelled = Event()

    def cancel(self):
        self.cancelled.set()

    def check(self):
        if self.cancelled.is_set():
            raise SolveCancelled


def _search_workers():
    return min(8, max(1, os.cpu_count() or 1))


class _SolutionCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, accept):
        super().__init__()
        self.accept = accept
        self.error = None

    def on_solution_callback(self):
        try:
            if not self.accept(self):
                self.StopSearch()
        except Exception as exc:
            self.error = exc
            self.StopSearch()


def _optimize(model, remaining, callback=None, control=None):
    # Never pass zero: OR-Tools interprets some disabled limits as unbounded.
    if not math.isfinite(remaining) or remaining <= 0:
        raise ValueError("CP-SAT requires a positive remaining budget")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = _search_workers()
    solver.parameters.use_lns = True
    solver.parameters.random_seed = 0
    done = Event()
    def watch_cancel():
        # Repeat StopSearch until Solve has unwound: cancellation can race with
        # OR-Tools creating its internal solve wrapper, before StopSearch works.
        while not done.wait(.02):
            if control.cancelled.is_set():
                solver.StopSearch()
    watcher = None
    if control:
        control.check()
        watcher = Thread(target=watch_cancel, name="pavement-cancel", daemon=True)
        watcher.start()
    try:
        status = solver.Solve(model, callback)
    finally:
        done.set()
        if watcher:
            watcher.join()
    if control:
        control.check()
    if callback and callback.error:
        raise callback.error
    return solver, solver.StatusName(status), solver.WallTime()


def _candidate_from_solver(solver, schedule, candidates, starts, ends, assignments):
    candidate = Candidate(
        starts={tid: solver.Value(value) for tid, value in starts.items()},
        ends={tid: solver.Value(value) for tid, value in ends.items()},
        assignments={t.id: r.id for t in schedule.tasks for r in candidates[t.id] if solver.Value(assignments[t.id, r.id])},
        routes={}, makespan=0)
    candidate.makespan = max(candidate.ends.values())
    for rid in sorted(set(candidate.assignments.values())):
        candidate.routes[rid] = sorted((tid for tid, assigned in candidate.assignments.items() if assigned == rid), key=lambda tid: (candidate.starts[tid], tid))
    return candidate


def solve_pavement_schedule(schedule, *, on_solution=None, control=None):
    from ..engine import _execution_constraint_validation
    if not math.isfinite(schedule.time_limit_seconds) or schedule.time_limit_seconds <= 0:
        raise ValueError("求解预算必须为大于0的有限秒数。")
    began = perf_counter()
    deadline = began + schedule.time_limit_seconds
    if control:
        control.check()
    errors, candidates = validate_pavement_schedule(schedule)
    errors.extend(_execution_constraint_validation(schedule, candidates))
    for milestone in schedule.milestones:
        if not task_ids_for_milestone(milestone, schedule.tasks):
            errors.append(ValidationMessage(level="error", code="PAVEMENT_REFERENCE_INVALID", message="里程碑未匹配任何路面任务。", subject_id=milestone.id))
    stats = {"pavement_handover": schedule.pavement_handover_scope.model_dump(mode="json")} if schedule.pavement_handover_scope else {}
    if errors:
        return ScheduleResult(status="MODEL_INVALID", plan_start_date=schedule.start_date, validation=errors, stats=stats)
    stats.update(pavement_handover=_result_handover_scope(schedule).model_dump(mode="json"),
        solve_mode="pavement_fixed_resources", hard_constraints_relaxed=False, wall_time_seconds=0.0)
    initial_began = perf_counter()
    valid = generate_initial_candidates(schedule, candidates, min(deadline, initial_began + min(1.0, schedule.time_limit_seconds * .1)))
    initial = min(valid, key=lambda c: c.makespan) if valid else None
    best = initial
    meta = PavementOptimization(outcome="no_plan", initial_strategy=initial.strategy if initial else None,
        valid_candidate_count=len(valid), initial_days=initial.makespan if initial else None,
        initial_plan_seconds=perf_counter() - initial_began, time_budget_seconds=schedule.time_limit_seconds,
        improvement_count=0)
    inconsistent = None

    def selected_meta():
        snapshot = meta.model_copy(deep=True)
        if best:
            snapshot.final_days = best.makespan
            snapshot.improvement_days = initial.makespan - best.makespan if initial else None
            snapshot.selected_source = "greedy" if best is initial else "cp_sat"
            snapshot.outcome = "initial_retained" if best is initial else "improved" if initial else "cp_sat_only"
        snapshot.total_seconds = perf_counter() - began
        return snapshot

    def publish():
        if control:
            control.check()
        if on_solution:
            result = result_from_candidate(schedule, candidates, best, "FEASIBLE", dict(stats))
            result.pavement_optimization = selected_meta()
            on_solution(result.model_copy(deep=True))

    def accept(candidate):
        nonlocal best, inconsistent
        violations = validate_candidate(schedule, candidates, candidate)
        if violations or initial and candidate.makespan > initial.makespan:
            inconsistent = "优化结果违反硬约束或超过初步计划上界。"
            stats["optimizer_violations"] = violations
            return False
        if best is None or candidate.makespan < best.makespan:
            if best is not None:
                meta.improvement_count += 1
            best = candidate
            publish()
        return True

    if best:
        publish()
    build_began = perf_counter()
    try:
        model, starts, ends, assignments, horizon = _build_model(schedule, candidates, initial, deadline, control)
        stats["horizon"] = horizon
        meta.model_build_seconds = perf_counter() - build_began
        remaining = deadline - perf_counter()
        if remaining <= 0:
            raise BudgetExpired
        meta.search_workers, meta.lns_enabled = _search_workers(), True
        def on_cp_solution(callback):
            if control:
                control.check()
            meta.cp_sat_seconds = callback.WallTime()
            if best and callback.ObjectiveValue() >= best.makespan:
                return True
            return accept(_candidate_from_solver(callback, schedule, candidates, starts, ends, assignments))
        callback = _SolutionCallback(on_cp_solution)
        solver, status, elapsed = _optimize(model, remaining, callback, control)
        meta.cp_sat_seconds = elapsed
        stats["wall_time_seconds"] = elapsed
        if status in {"FEASIBLE", "OPTIMAL"} and not inconsistent:
            # Validate the final solver values even when its objective matches a
            # published incumbent; a bad final response must not be hidden.
            accept(_candidate_from_solver(solver, schedule, candidates, starts, ends, assignments))
        elif best and status in {"INFEASIBLE", "MODEL_INVALID"}:
            inconsistent = "已有合法方案，但优化器报告模型无解或无效。"
        meta.optimizer_status = status
    except BudgetExpired:
        meta.model_build_seconds = perf_counter() - build_began
        meta.optimizer_not_run_reason = "budget_exhausted"
    except HintInconsistent as exc:
        meta.model_build_seconds = perf_counter() - build_began
        inconsistent = "初步计划路线与优化模型不一致。"
        stats["optimizer_violations"] = [str(exc)]
    if control:
        control.check()
    if inconsistent:
        meta.outcome = "inconsistent"
        result = ScheduleResult(status="MODEL_INVALID", plan_start_date=schedule.start_date, stats=stats,
            validation=[ValidationMessage(level="error", code="PAVEMENT_OPTIMIZER_INCONSISTENT", message=inconsistent)])
    elif best:
        status = "OPTIMAL" if meta.optimizer_status == "OPTIMAL" else "FEASIBLE"
        result = result_from_candidate(schedule, candidates, best, status, stats)
        meta = selected_meta()
    else:
        status = meta.optimizer_status or "UNKNOWN"
        result = ScheduleResult(status=status, plan_start_date=schedule.start_date, stats=stats,
            validation=[ValidationMessage(level="error" if status == "MODEL_INVALID" else "warning", code=f"PAVEMENT_{status}",
                message={"INFEASIBLE":"现有机组和硬条件下无可行计划。", "UNKNOWN":"限时内尚未找到可行计划。", "MODEL_INVALID":"排程模型无效。"}[status])])
    meta.total_seconds = perf_counter() - began
    result.pavement_optimization = meta
    return result


def _shift_assumption(regimes):
    spans = "；".join(f"{regime.start_date} ~ {regime.end_date or '长期'}{'双班' if regime.shifts == 2 else '单班'}"
        for regime in sorted(regimes, key=lambda r: r.start_date))
    return f"已配置班制区间（{spans}）：双班日按基准工效×2计算日产出，区间外按单班。"


def result_from_candidate(schedule, candidates, candidate, status_name, stats):
    """One conversion path for optimized and fallback plans, including all dates."""
    by_id = {t.id: t for t in schedule.tasks}
    scope_stats = stats
    scheduled, allocations = [], []
    for task in schedule.tasks:
        s,e = candidate.starts[task.id],candidate.ends[task.id]
        resource = next((r for r in candidates[task.id] if candidate.assignments.get(task.id) == r.id),None)
        scheduled.append(ScheduledTask(**task.model_dump(),start_offset=s,end_offset=e,start_date=schedule.start_date+timedelta(days=s),
            finish_date=schedule.start_date+timedelta(days=e-1),assigned_resource_id=resource.id if resource else None,
            assigned_resource_name=resource.name if resource else None,assigned_resource_type=resource.type if resource else None,
            predecessor_ids=[l.predecessor_id for l in schedule.precedence_links if l.successor_id==task.id]))
        if resource: allocations.append(ResourceAllocation(resource_id=resource.id,resource_name=resource.name,resource_type=resource.type,
            task_id=task.id,task_name=task.name,start_offset=s,end_offset=e,start_date=scheduled[-1].start_date,finish_date=scheduled[-1].finish_date))
    transfers = []
    resources = {r.id: r for r in schedule.resources}
    for rid, route in candidate.routes.items():
        for first, second in zip(route, route[1:]):
            a, b = by_id[first], by_id[second]
            days = transfer_days(resources[rid], a, b)
            if days:
                transfers.append(PavementTransfer(resource_id=rid,from_task_id=first,to_task_id=second,
                    from_position_id=a.pavement_context.position_id,to_position_id=b.pavement_context.position_id,
                    start_offset=candidate.ends[first],end_offset=candidate.ends[first]+days))
    waits = [PavementWaitInterval(source_component_id=t.pavement_context.source_component_id,start_offset=t.end_offset,
        end_offset=ready_offset(t, candidate.ends[t.id]),reason="养生/冷却及验收可用条件") for t in scheduled if ready_offset(t, candidate.ends[t.id])>t.end_offset]
    for link in schedule.precedence_links:
        own_wait = int(by_id[link.predecessor_id].properties.get("wait_days", 0))
        if link.source_rule_id == "pavement_layer_condition" and link.relationship == "FS" and link.lag_days > own_wait:
            end = candidate.ends[link.predecessor_id]
            waits.append(PavementWaitInterval(source_component_id=by_id[link.successor_id].component_id,
                start_offset=end+own_wait, end_offset=end+link.lag_days, reason="零天配套步骤的附加等待"))
    construction_finish = max(t.end_offset for t in scheduled)
    ready = candidate.makespan
    pending_dates = []
    for section in scope_stats["pavement_handover"]["pending_sections"]:
        section_tasks = [t for t in scheduled if t.structure_id == section["structure_id"]]
        pending_dates.append(PavementPendingSectionDates(structure_id=section["structure_id"],
            required_handover_date=min(t.start_date for t in section_tasks),
            estimated_finish_date=max(t.finish_date for t in section_tasks)))
    summary = PavementSummary(input_kind="demo" if any(t.pavement_context.input_kind=="demo" for t in scheduled) else "customer",
        input_fingerprint=schedule_fingerprint(schedule),
        project_data_version_id=schedule.project_data_version_id,construction_finish_offset=construction_finish,
        construction_finish_date=schedule.start_date+timedelta(days=construction_finish-1),ready_offset=ready,
        ready_date=schedule.start_date+timedelta(days=ready),readiness=[],wait_intervals=waits,transfers=transfers,
        pending_section_dates=pending_dates,
        resource_assumptions=["透层/封层/黏层等辅助班组及养生管理资源按充足考虑。", "工效为每套机组综合日工效；连续日历天，不含天气和温度窗口优化。"]
            + ([_shift_assumption(schedule.shift_regimes)] if schedule.shift_regimes else []))
    milestones = []
    milestone_values = milestone_offsets(schedule, candidate)
    for m in schedule.milestones:
        actual = milestone_values[m.id]; lateness=max(0,actual-(m.target_date-schedule.start_date).days)
        milestones.append(MilestoneResult(**m.model_dump(exclude={"related_structure_ids"}),actual_offset=actual,
            actual_date=schedule.start_date+timedelta(days=actual),lateness_days=lateness,penalty=lateness*m.penalty_per_day,status="late" if lateness else "met"))
    return ScheduleResult(status=status_name,objective_days=ready,plan_start_date=schedule.start_date,
        plan_finish_date=summary.construction_finish_date,tasks=sorted(scheduled,key=lambda t:(t.start_offset,t.id)),resource_allocations=allocations,
        milestone_results=milestones,pavement_summary=summary,stats=stats,objective_breakdown={"objective":"earliest_construction_finish","ready_offset":ready})


class IdleBaselineError(ValueError):
    def __init__(self, message, code="PAVEMENT_BASELINE_INVALID"):
        super().__init__(message)
        self.code = code


def schedule_fingerprint(schedule):
    return hashlib.sha256(json.dumps(schedule.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_idle_baseline(schedule, baseline):
    """Rebuild only timing/assignments from the client; definitions stay authoritative."""
    from ..engine import _execution_constraint_validation
    from ....contracts import Task
    errors, candidates = validate_pavement_schedule(schedule)
    errors.extend(_execution_constraint_validation(schedule, candidates))
    if errors:
        raise IdleBaselineError(errors[0].message, errors[0].code)
    summary = baseline.pavement_summary
    if baseline.status not in {"FEASIBLE", "OPTIMAL"} or summary is None:
        raise IdleBaselineError("请先获得完整的可行排程方案。")
    if summary.input_fingerprint != schedule_fingerprint(schedule):
        raise IdleBaselineError("当前输入与原方案不一致，请重新求解。", "PAVEMENT_BASELINE_OUTDATED")
    tasks = {t.id:t for t in schedule.tasks}
    if len(baseline.tasks) != len(tasks) or {t.id for t in baseline.tasks} != set(tasks):
        raise IdleBaselineError("基准方案任务缺失或重复，请重新求解。")
    for task in baseline.tasks:
        original = tasks[task.id]
        if any(getattr(task, field) != getattr(original, field) for field in Task.model_fields):
            raise IdleBaselineError("基准任务定义与当前输入不一致。")
        if (type(task.start_offset) is not int or type(task.end_offset) is not int
                or task.start_offset < 0
                or task.end_offset != task.start_offset + pavement_duration(original, task.start_offset, schedule)):
            raise IdleBaselineError("基准任务时刻或工期无效。")
        if (task.start_date != schedule.start_date + timedelta(days=task.start_offset)
                or task.finish_date != schedule.start_date + timedelta(days=task.end_offset-1)):
            raise IdleBaselineError("基准任务日期与偏移不一致。")
    initial = Candidate(starts={t.id:t.start_offset for t in baseline.tasks},
        ends={t.id:t.end_offset for t in baseline.tasks},
        assignments={t.id:t.assigned_resource_id for t in baseline.tasks if t.assigned_resource_id},
        routes={}, makespan=max(t.end_offset for t in baseline.tasks))
    for rid in sorted(set(initial.assignments.values())):
        initial.routes[rid] = sorted((t for t,r in initial.assignments.items() if r == rid), key=lambda t:(initial.starts[t],t))
    violations = validate_candidate(schedule, candidates, initial)
    finish = schedule.start_date + timedelta(days=initial.makespan-1)
    if (violations or baseline.objective_days != initial.makespan or baseline.plan_start_date != schedule.start_date
            or baseline.plan_finish_date != finish or summary.construction_finish_offset != initial.makespan
            or summary.construction_finish_date != finish or summary.project_data_version_id != schedule.project_data_version_id):
        raise IdleBaselineError("基准方案违反当前约束或完工摘要不一致，请重新求解。")
    return candidates, initial


def solve_pavement_idle(schedule, baseline, *, on_solution=None, control=None, began=None, prepared=None,
                        time_budget_seconds=None):
    """Optimize internal fleet idle time under an immutable, verified makespan cap."""
    budget = schedule.time_limit_seconds if time_budget_seconds is None else time_budget_seconds
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError("求解预算必须为大于0的有限秒数。")
    began = perf_counter() if began is None else began
    deadline = began + budget
    if control:
        control.check()
    candidates, initial = prepared if prepared is not None else validate_idle_baseline(schedule, baseline)
    initial_idle, initial_transfer = idle_metrics(schedule, initial)
    best, best_idle = initial, initial_idle
    meta = PavementIdleOptimization(baseline_input_fingerprint=schedule_fingerprint(schedule),
        makespan_cap_days=initial.makespan, baseline_idle_days=initial_idle, final_idle_days=initial_idle,
        baseline_transfer_days=initial_transfer, final_transfer_days=initial_transfer,
        time_budget_seconds=budget)
    stats = {"pavement_handover": _result_handover_scope(schedule).model_dump(mode="json"),
        "solve_mode":"pavement_idle_optimization", "hard_constraints_relaxed":False}

    def snapshot(final=False):
        current = meta.model_copy(deep=True)
        current.final_idle_days, current.final_transfer_days = idle_metrics(schedule, best)
        current.improvement_idle_days = initial_idle - current.final_idle_days
        current.selected_source = "baseline" if best is initial else "cp_sat"
        current.outcome = "baseline_retained" if best is initial else "improved"
        current.total_seconds = perf_counter() - began
        current.proved_optimal = final and (current.optimizer_status == "OPTIMAL" or current.optimizer_not_run_reason == "zero_idle")
        result = result_from_candidate(schedule, candidates, best, "OPTIMAL" if current.proved_optimal else "FEASIBLE", dict(stats))
        result.pavement_optimization = baseline.pavement_optimization.model_copy(deep=True) if baseline.pavement_optimization else None
        result.pavement_idle_optimization = current
        result.objective_breakdown = {"objective":"min_idle_with_makespan_cap", "makespan_cap_days":initial.makespan,
            "idle_days":current.final_idle_days, "ready_offset":best.makespan}
        return result

    def publish():
        if control:
            control.check()
        if on_solution:
            on_solution(snapshot())

    def accept(candidate, objective):
        nonlocal best, best_idle
        violations = validate_candidate(schedule, candidates, candidate)
        if violations or candidate.makespan > initial.makespan:
            raise HintInconsistent("窝工优化方案违反硬约束或超过基准工期。")
        idle, _ = idle_metrics(schedule, candidate)
        if idle != round(objective) or abs(idle-objective) > 1e-6:
            raise HintInconsistent("窝工模型目标与实际路线空闲不一致。")
        if idle < best_idle:
            best, best_idle = candidate, idle
            meta.improvement_count += 1
            publish()
        return True

    publish()
    if initial_idle == 0:
        meta.optimizer_not_run_reason = "zero_idle"
        return snapshot(final=True)
    build_began = perf_counter()
    try:
        model, starts, ends, assignments, horizon = _build_model(schedule, candidates, initial, deadline, control, minimize_idle=True)
        meta.model_build_seconds = perf_counter() - build_began
        remaining = deadline - perf_counter()
        if remaining <= 0:
            raise BudgetExpired
        meta.search_workers, meta.lns_enabled = _search_workers(), True
        def receive(callback):
            if control:
                control.check()
            meta.cp_sat_seconds = callback.WallTime()
            # The solver's incumbent may be worse than the retained seed; never publish it.
            return accept(_candidate_from_solver(callback, schedule, candidates, starts, ends, assignments), callback.ObjectiveValue())
        solver, status, elapsed = _optimize(model, remaining, _SolutionCallback(receive), control)
        meta.cp_sat_seconds, meta.optimizer_status = elapsed, status
        if status in {"FEASIBLE", "OPTIMAL"}:
            accept(_candidate_from_solver(solver, schedule, candidates, starts, ends, assignments), solver.ObjectiveValue())
            if status == "OPTIMAL" and abs(solver.ObjectiveValue()-best_idle) > 1e-6:
                raise HintInconsistent("窝工优化证明与保留方案不一致。")
        elif status in {"INFEASIBLE", "MODEL_INVALID"}:
            raise HintInconsistent("已有合法基准，但窝工优化模型报告无解或无效。")
    except BudgetExpired:
        meta.model_build_seconds = perf_counter() - build_began
        meta.optimizer_not_run_reason = "budget_exhausted"
    if control:
        control.check()
    return snapshot(final=True)
