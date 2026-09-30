"""Deterministic serial construction and independent numeric feasibility checks.

Dispatch order is only a calculation order: a successor on another fleet may
start earlier under FF/SF. Failed construction does not prove infeasibility.
"""
from collections import defaultdict
from dataclasses import dataclass
from graphlib import TopologicalSorter
from time import perf_counter

from ....project_master.validation import resolve_roadbed_handover, roadbed_start_offset
from ...domain.milestone_scope import task_ids_for_milestone
from ...domain.shift_regime import task_duration_for_start

STRATEGIES = ("earliest_start", "longest_chain", "least_transfer")


def pavement_duration(task, start, schedule):
    """Task duration when starting at `start`; baseline value without regimes."""
    if not schedule.shift_regimes:
        return task.duration_days
    return task_duration_for_start(task, start, schedule.shift_regimes, schedule.start_date)


class BudgetExpired(Exception):
    """Internal cancellation of construction/model building, never a business error."""


def check_deadline(deadline, clock=perf_counter):
    if clock() >= deadline:
        raise BudgetExpired


@dataclass
class Candidate:
    starts: dict[str, int]
    ends: dict[str, int]
    assignments: dict[str, str]
    routes: dict[str, list[str]]
    makespan: int
    strategy: str | None = None


def ready_offset(task, end):
    return max(end + task.properties.get("wait_days", 0), task.properties.get("accepted_available_offset", 0))


def terminal_task_ids(tasks):
    groups = defaultdict(list)
    for task in tasks:
        if task.pavement_context.task_kind == "construction":
            groups[task.pavement_context.position_id].append(task)
    return {max(group, key=lambda t: (t.sequence_order, t.id)).id for group in groups.values()}


def milestone_offsets(schedule, candidate):
    by_id = {t.id: t for t in schedule.tasks}
    terminals = terminal_task_ids(schedule.tasks)
    values = {}
    for milestone in schedule.milestones:
        ids = task_ids_for_milestone(milestone, schedule.tasks)
        if not ids:
            continue
        values[milestone.id] = (min(candidate.starts[t] for t in ids) if milestone.target_event == "start"
            else max(candidate.ends[t] - 1 if t in terminals else ready_offset(by_id[t], candidate.ends[t]) for t in ids))
    return values


def transfer_days(resource, first, second):
    return resource.transfer_days if first.pavement_context.position_id != second.pavement_context.position_id else 0


def idle_metrics(schedule, candidate):
    """Independently total actual inter-task gaps; call after feasibility validation."""
    tasks = {t.id: t for t in schedule.tasks}
    resources = {r.id: r for r in schedule.resources}
    idle, transfer = 0, 0
    for rid, route in candidate.routes.items():
        for a, b in zip(route, route[1:]):
            days = transfer_days(resources[rid], tasks[a], tasks[b])
            gap = candidate.starts[b] - candidate.ends[a] - days
            if gap < 0:
                raise ValueError("Invalid fleet gap")
            idle += gap
            transfer += days
    return idle, transfer


def validate_candidate(schedule, candidates, candidate, checkpoint=lambda: None):
    """Check all hard rules against numbers, without a CP model or solver call."""
    checkpoint()
    tasks = {t.id: t for t in schedule.tasks}
    ids = set(tasks)
    errors = []
    if set(candidate.starts) != ids or set(candidate.ends) != ids:
        return ["task coverage"]
    for tid, task in tasks.items():
        checkpoint()
        s, e = candidate.starts[tid], candidate.ends[tid]
        if type(s) is not int or type(e) is not int or s < 0 or e != s + pavement_duration(task, s, schedule):
            errors.append(f"duration/time:{tid}")
    if errors:
        return errors
    if type(candidate.makespan) is not int or candidate.makespan != max(candidate.ends.values(), default=0):
        errors.append("makespan")
    core_ids = {t.id for t in schedule.tasks if t.pavement_context.task_kind == "construction"}
    if set(candidate.assignments) != core_ids:
        errors.append("assignment coverage")
    for tid in core_ids:
        if candidate.assignments.get(tid) not in {r.id for r in candidates[tid]}:
            errors.append(f"resource eligibility:{tid}")
    resources = {r.id: r for r in schedule.resources}
    pending = {t.id for t in schedule.tasks if resolve_roadbed_handover(t.properties)[0] == "pending"}
    routed = []
    for rid, route in candidate.routes.items():
        checkpoint()
        if rid not in resources or any(tid not in core_ids for tid in route):
            errors.append("route reference"); continue
        routed.extend(route)
        seen_pending = False
        for tid in route:
            if candidate.assignments.get(tid) != rid:
                errors.append(f"route assignment:{tid}")
            if tid in pending:
                seen_pending = True
            elif seen_pending:
                errors.append(f"pending:{tid}")
        for a, b in zip(route, route[1:]):
            if candidate.starts[b] < candidate.ends[a] + transfer_days(resources[rid], tasks[a], tasks[b]):
                errors.append(f"fleet overlap/transfer:{a}:{b}")
    if len(routed) != len(set(routed)) or set(routed) != core_ids:
        errors.append("route coverage")
    for link in schedule.precedence_links:
        checkpoint()
        a, b = link.predecessor_id, link.successor_id
        left = candidate.ends[a] if link.relationship[0] == "F" else candidate.starts[a]
        right = candidate.ends[b] if link.relationship[1] == "F" else candidate.starts[b]
        if right < left + link.lag_days:
            errors.append(f"precedence:{link.id}")
        if link.source_rule_id == "pavement_layer_condition":
            boundary = ready_offset(tasks[a], candidate.ends[a]) if link.relationship == "FS" else tasks[a].properties.get("accepted_available_offset", 0)
            if candidate.starts[b] < boundary:
                errors.append(f"available:{link.id}")
    for task in schedule.tasks:
        checkpoint()
        if candidate.starts[task.id] < roadbed_start_offset(task.properties, schedule.start_date, allow_pending=True):
            errors.append(f"roadbed:{task.id}")
    for constraint in schedule.execution_constraints:
        s = candidate.starts[constraint.task_id]
        if constraint.earliest_start_offset is not None and s < constraint.earliest_start_offset:
            errors.append("earliest start")
        if constraint.fixed_start_offset is not None and s != constraint.fixed_start_offset:
            errors.append("fixed start")
        if constraint.fixed_resource_id is not None and candidate.assignments.get(constraint.task_id) != constraint.fixed_resource_id:
            errors.append("fixed resource")
    values = milestone_offsets(schedule, candidate)
    for milestone in schedule.milestones:
        checkpoint()
        if milestone.id not in values:
            errors.append("milestone reference")
        elif milestone.mode == "hard" and values[milestone.id] > (milestone.target_date - schedule.start_date).days:
            errors.append(f"hard milestone:{milestone.id}")
    return errors


def construct_candidate(schedule, candidates, strategy, deadline, clock=perf_counter):
    checkpoint = lambda: check_deadline(deadline, clock)
    try:
        checkpoint()
        tasks = {t.id: t for t in schedule.tasks}
        incoming, following = defaultdict(list), defaultdict(list)
        for link in schedule.precedence_links:
            incoming[link.successor_id].append(link)
            following[link.predecessor_id].append(link)
        order = list(TopologicalSorter({tid: {l.predecessor_id for l in incoming[tid]} for tid in tasks}).static_order())
        chain = {}
        for tid in reversed(order):
            checkpoint()
            chain[tid] = tasks[tid].duration_days + max([0] + [max(0, l.lag_days) + chain[l.successor_id] for l in following[tid]])
        execution = {c.task_id: c for c in schedule.execution_constraints}
        pending = {t.id for t in schedule.tasks if resolve_roadbed_handover(t.properties)[0] == "pending"}
        normal = set(tasks) - pending
        plan = Candidate({}, {}, {}, {}, 0, strategy)
        todo = set(tasks)
        while todo:
            checkpoint()
            options = []
            for tid in sorted(todo):
                checkpoint()
                if any(l.predecessor_id not in plan.starts for l in incoming[tid]):
                    continue
                task = tasks[tid]
                lower = roadbed_start_offset(task.properties, schedule.start_date, allow_pending=True)
                for link in incoming[tid]:
                    a = link.predecessor_id
                    bound = plan.ends[a] if link.relationship[0] == "F" else plan.starts[a]
                    bound += link.lag_days - (task.duration_days if link.relationship[1] == "F" else 0)
                    lower = max(lower, bound)
                    if link.source_rule_id == "pavement_layer_condition":
                        lower = max(lower, ready_offset(tasks[a], plan.ends[a]) if link.relationship == "FS" else tasks[a].properties.get("accepted_available_offset", 0))
                constraint = execution.get(tid)
                if constraint:
                    lower = max(lower, constraint.earliest_start_offset or 0)
                choices = candidates[tid] if task.pavement_context.task_kind == "construction" else [None]
                for resource in sorted(choices, key=lambda r: r.id if r else ""):
                    checkpoint()
                    rid = resource.id if resource else ""
                    if constraint and constraint.fixed_resource_id and rid != constraint.fixed_resource_id:
                        continue
                    s, transfer = lower, 0
                    if resource and plan.routes.get(rid):
                        previous = plan.routes[rid][-1]
                        if previous in pending and tid in normal:
                            continue
                        transfer = transfer_days(resource, tasks[previous], task)
                        s = max(s, plan.ends[previous] + transfer)
                    if constraint and constraint.fixed_start_offset is not None:
                        if constraint.fixed_start_offset < s:
                            continue
                        s = constraint.fixed_start_offset
                    # Variable shift durations: the F-successor bounds above are
                    # only a floor computed with the baseline duration; push the
                    # start until every F boundary holds at the actual duration.
                    if schedule.shift_regimes:
                        for link in incoming[tid]:
                            if link.relationship[1] != "F":
                                continue
                            required = (plan.ends[link.predecessor_id] if link.relationship[0] == "F"
                                        else plan.starts[link.predecessor_id]) + link.lag_days
                            while s + pavement_duration(task, s, schedule) < required:
                                checkpoint()
                                s += 1
                        if constraint and constraint.fixed_start_offset is not None and s != constraint.fixed_start_offset:
                            continue
                    e = s + pavement_duration(task, s, schedule)
                    if strategy == "earliest_start": key = (s, e, transfer, tid, rid)
                    elif strategy == "longest_chain": key = (-chain[tid], s, transfer, tid, rid)
                    elif strategy == "least_transfer": key = (transfer, s, -chain[tid], tid, rid)
                    else: raise ValueError(f"Unknown pavement strategy: {strategy}")
                    options.append((key, tid, rid, s, e))
            if not options:
                return None
            # Construction order is a heuristic, not a global calendar barrier.
            # A real cross-fleet dependency may require scheduling pending work
            # first; its fleet must then remain in the pending phase.
            normal_options = [option for option in options if option[1] in normal]
            _, tid, rid, s, e = min(normal_options or options)
            plan.starts[tid], plan.ends[tid] = s, e
            if rid:
                plan.assignments[tid] = rid
                plan.routes.setdefault(rid, []).append(tid)
            todo.remove(tid)
        plan.makespan = max(plan.ends.values(), default=0)
        return None if validate_candidate(schedule, candidates, plan, checkpoint) else plan
    except BudgetExpired:
        return None


def generate_initial_candidates(schedule, candidates, deadline, clock=perf_counter):
    valid = []
    for strategy in STRATEGIES:
        if clock() >= deadline:
            break
        candidate = construct_candidate(schedule, candidates, strategy, deadline, clock)
        if candidate is not None:
            valid.append(candidate)
    return valid
