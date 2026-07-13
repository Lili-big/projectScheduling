from __future__ import annotations

import math
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, get_args

from .models import (
    ComponentType,
    DEFAULT_OBJECTIVE_TERM_WEIGHTS,
    MilestoneConstraint,
    OBJECTIVE_METRIC_DEFINITIONS,
    MilestoneResult,
    PrecedenceLink,
    Resource,
    ResourceAllocation,
    ScheduleInput,
    ScheduleResult,
    ScheduledTask,
    Task,
    ValidationMessage,
    effective_objective_weights,
    objective_terms_used,
)

CONTINUITY_PRIMARY_WEIGHT = 1_000_000
CONTROL_NODE_LATE_WEIGHT = DEFAULT_OBJECTIVE_TERM_WEIGHTS["control_node_late"]
RESOURCE_IDLE_WEIGHT = DEFAULT_OBJECTIVE_TERM_WEIGHTS["resource_idle"]
CONTROL_MAKESPAN_WEIGHT = DEFAULT_OBJECTIVE_TERM_WEIGHTS["makespan_and_soft_milestone"]
CONTROL_NECESSARY_BUFFER_DAYS = 7
CONTROL_BUFFER_NEAR_RISK_DAYS = 3
SCHEDULER_RANDOM_SEED = 0
CONTINUOUS_BEAM_SIDE_CLOSURE_RULE_ID = "continuous_beam_side_closure"
CONTINUOUS_BEAM_MIDDLE_CLOSURE_RULE_ID = "continuous_beam_middle_closure"
CONTINUOUS_BEAM_CLOSURE_RULE_IDS = {
    CONTINUOUS_BEAM_SIDE_CLOSURE_RULE_ID,
    CONTINUOUS_BEAM_MIDDLE_CLOSURE_RULE_ID,
}
CONTINUOUS_BEAM_RESOURCE_TYPE = "cast_in_place_continuous_beam_team"
DEFAULT_CONTINUOUS_CLOSURE_FINISH_GAP_DAYS = 7
MINIMUM_RESOURCES_BEST_EFFORT_SOURCE = "minimum_resources_best_effort_refinement"
TARGET_SOLVE_TIME_LIMIT_SECONDS = 15.0
MECHANICAL_DRILL_RESOURCE_TYPES = frozenset({"rotary_drill", "circulation_drill", "impact_drill"})
MECHANICAL_DRILL_PATH_SUPPORT_WINDOW = 2
MECHANICAL_DRILL_CROSS_SIDE_SUPPORT_WINDOW = 1


class _SolveBudget:
    def __init__(self, time_limit_seconds: float) -> None:
        self.time_limit_seconds = min(TARGET_SOLVE_TIME_LIMIT_SECONDS, max(0.1, float(time_limit_seconds or TARGET_SOLVE_TIME_LIMIT_SECONDS)))
        self.started_at = time.perf_counter()

    def with_time_limit(self, schedule_input: ScheduleInput) -> ScheduleInput:
        return schedule_input.model_copy(update={"time_limit_seconds": self.remaining_seconds()})

    def remaining_seconds(self) -> float:
        elapsed = time.perf_counter() - self.started_at
        return max(0.1, self.time_limit_seconds - elapsed)

    def exhausted(self) -> bool:
        return self.remaining_seconds() <= 0.11


@dataclass(frozen=True)
class _DrillGroupNode:
    group_id: str
    group_key: tuple[str, str, str, str]
    resource_group_key: str
    structure_id: str
    component_type: str
    process_name: str
    child_task_ids: tuple[str, ...]
    duration_days: int
    sequence_order: int
    eligible_resource_ids: tuple[str, ...]
    representative_task: Task


@dataclass(frozen=True)
class _DrillGroupStage1RouteDecision:
    allowed: bool
    transition_kind: str
    penalty: int = 0
    rejection_reason: str | None = None
    same_side_sequence_distance: int | None = None
    cross_side_support_gap: int | None = None


@dataclass(frozen=True)
class _ContinuousBeamTeamSpan:
    span_group_id: str
    display_name: str
    bridge_id: str | None
    work_section_id: str | None
    group_index: int | None
    task_ids: tuple[str, ...]


@dataclass
class _ContinuousBeamTeamSpanModel:
    spans: list[_ContinuousBeamTeamSpan]
    assignment_vars: dict[tuple[str, str], Any]
    start_vars: dict[str, Any]
    end_vars: dict[str, Any]
    resources_by_id: dict[str, Resource]
    diagnostics: list[dict[str, Any]] | None = None
    resource_type: str = CONTINUOUS_BEAM_RESOURCE_TYPE


def _objective_weights_for_config(config: Any) -> dict[str, int]:
    return effective_objective_weights(config.objective_terms)


def _objective_terms_used_for_config(config: Any, weights: dict[str, int]) -> dict[str, dict[str, int | bool]]:
    terms_used = objective_terms_used(config.objective_terms)
    for term_id, effective_weight in weights.items():
        terms_used[term_id]["effective_weight"] = effective_weight
    return terms_used


def _objective_contributions_for_result(
    *,
    objective_terms_used_payload: dict[str, dict[str, int | bool]],
    raw_penalties: dict[str, int],
    active_terms: dict[str, bool] | None = None,
    notes_by_term: dict[str, str] | None = None,
    effective_weight_overrides: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    active_terms = active_terms or {}
    notes_by_term = notes_by_term or {}
    effective_weight_overrides = effective_weight_overrides or {}
    contributions: list[dict[str, Any]] = []
    for term_id in DEFAULT_OBJECTIVE_TERM_WEIGHTS:
        term_payload = objective_terms_used_payload.get(term_id, {})
        effective_weight = int(effective_weight_overrides.get(term_id, term_payload.get("effective_weight", 0)) or 0)
        configured_weight = int(term_payload.get("weight", DEFAULT_OBJECTIVE_TERM_WEIGHTS[term_id]) or 0)
        enabled = bool(term_payload.get("enabled", effective_weight > 0))
        raw_penalty = int(raw_penalties.get(term_id, 0) or 0)
        active = bool(active_terms.get(term_id, effective_weight > 0))
        definition = OBJECTIVE_METRIC_DEFINITIONS.get(term_id, {})
        weighted_contribution = raw_penalty * effective_weight if active else 0
        contributions.append(
            {
                "term_id": term_id,
                "label": definition.get("label", term_id),
                "group": definition.get("group", ""),
                "source": definition.get("source", "objective"),
                "enabled": enabled,
                "active": active,
                "configured_weight": configured_weight,
                "effective_weight": effective_weight,
                "weight": effective_weight,
                "raw_penalty": raw_penalty,
                "raw_value": raw_penalty,
                "unit": "days",
                "weighted_contribution": weighted_contribution,
                "weighted_value": weighted_contribution,
                "applies_to": list(definition.get("applies_to", [])),
                "parent_term_id": definition.get("parent_term_id"),
                "notes": notes_by_term.get(term_id, ""),
            }
        )
    return contributions


def _objective_term_enabled(objective_weights: dict[str, int], term_id: str) -> bool:
    return int(objective_weights.get(term_id, 0) or 0) > 0


def _objective_modeling_gates(
    objective_terms_used_payload: dict[str, dict[str, int | bool]],
    *,
    modeled_terms: set[str],
    reason_overrides: dict[str, str] | None = None,
    effective_weight_overrides: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    reason_overrides = reason_overrides or {}
    effective_weight_overrides = effective_weight_overrides or {}
    gates: dict[str, dict[str, Any]] = {}
    for term_id in DEFAULT_OBJECTIVE_TERM_WEIGHTS:
        term_payload = objective_terms_used_payload.get(term_id, {})
        requested_enabled = bool(term_payload.get("enabled", False))
        requested_weight = int(term_payload.get("weight", DEFAULT_OBJECTIVE_TERM_WEIGHTS[term_id]) or 0)
        effective_weight = int(
            effective_weight_overrides.get(
                term_id,
                int(term_payload.get("effective_weight", 0) or 0),
            )
        )
        modeling_enabled = term_id in modeled_terms
        if modeling_enabled:
            status = "enabled"
            reason = reason_overrides.get(term_id, "objective term enabled")
        elif not requested_enabled or effective_weight <= 0:
            status = "not_enabled"
            reason = reason_overrides.get(term_id, "effective weight is 0")
        else:
            status = "not_evaluated"
            reason = reason_overrides.get(term_id, "not evaluated by this solve path")
        gates[term_id] = {
            "term_id": term_id,
            "requested_enabled": requested_enabled,
            "requested_weight": requested_weight,
            "effective_weight": effective_weight,
            "modeling_enabled": modeling_enabled,
            "status": status,
            "reason": reason,
        }
    return gates


def _empty_control_buffer_terms() -> dict[str, Any]:
    return {"terms": [], "risk_by_task": {}, "profiles": {}}


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


def _is_continuous_beam_task(task: Task) -> bool:
    return task.component_type == "cast_in_place_continuous_beam" or task.structure_type == "continuous_beam"


def _continuous_span_group_index(task: Task) -> int | None:
    raw = _task_properties(task).get("group_index")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def _continuous_span_group_id(task: Task) -> str | None:
    props = _task_properties(task)
    configured = props.get("continuous_span_group_id")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    group_index = _continuous_span_group_index(task)
    if not task.bridge_id or not task.work_section_id or group_index is None:
        return None
    return f"{task.bridge_id}:{task.work_section_id}:continuous-beam:{group_index}"


def _continuous_span_display_name(task: Task, group_index: int | None) -> str:
    props = _task_properties(task)
    configured = props.get("continuous_span_group_name")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    prefix = task.structure_name.split("#", 1)[0].rstrip("-") or task.structure_name
    return f"{prefix}组 {group_index}" if group_index is not None else prefix


def _continuous_beam_team_spans(
    tasks: list[Task],
) -> tuple[list[_ContinuousBeamTeamSpan], list[ValidationMessage], list[dict[str, Any]]]:
    grouped: dict[str, dict[str, Any]] = {}
    messages: list[ValidationMessage] = []
    diagnostics: list[dict[str, Any]] = []
    for task in tasks:
        if not _is_continuous_beam_task(task):
            continue
        group_index = _continuous_span_group_index(task)
        span_group_id = _continuous_span_group_id(task)
        missing = []
        if not task.bridge_id:
            missing.append("bridge_id")
        if not task.work_section_id:
            missing.append("work_section_id")
        if group_index is None:
            missing.append("group_index")
        if not span_group_id:
            diagnostics.append(
                {
                    "level": "warning",
                    "task_id": task.id,
                    "task_name": task.name,
                    "reason": "continuous_span_group_missing",
                    "missing_fields": missing,
                }
            )
            messages.append(
                ValidationMessage(
                    level="warning",
                    subject_id=task.id,
                    message=f"现浇连续梁任务“{task.name}”缺少联级识别字段：{', '.join(missing)}，未纳入连续梁班组联级占用。",
                )
            )
            continue
        bucket = grouped.setdefault(
            span_group_id,
            {
                "span_group_id": span_group_id,
                "display_name": _continuous_span_display_name(task, group_index),
                "bridge_id": task.bridge_id,
                "work_section_id": task.work_section_id,
                "group_index": group_index,
                "tasks": [],
            },
        )
        bucket["tasks"].append(task)

    spans = [
        _ContinuousBeamTeamSpan(
            span_group_id=str(item["span_group_id"]),
            display_name=str(item["display_name"]),
            bridge_id=item["bridge_id"],
            work_section_id=item["work_section_id"],
            group_index=item["group_index"],
            task_ids=tuple(task.id for task in sorted(item["tasks"], key=lambda value: (value.sequence_order, value.id))),
        )
        for item in sorted(grouped.values(), key=lambda value: (str(value["bridge_id"] or ""), str(value["work_section_id"] or ""), int(value["group_index"] or 0), str(value["span_group_id"])))
    ]
    return spans, messages, diagnostics


def _is_continuous_beam_team_task_resource(task: Task, resource: Resource) -> bool:
    return _is_continuous_beam_task(task) and resource.type == CONTINUOUS_BEAM_RESOURCE_TYPE


def _continuous_beam_team_resources(resources: list[Resource]) -> list[Resource]:
    return [resource for resource in sorted(resources, key=_resource_sort_key) if resource.type == CONTINUOUS_BEAM_RESOURCE_TYPE]


def _add_named_continuous_beam_team_span_constraints(
    model: Any,
    *,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    enabled_resources: list[Resource],
    resource_intervals: dict[str, list[Any]],
    validation: list[ValidationMessage],
    horizon: int,
) -> _ContinuousBeamTeamSpanModel | None:
    spans, span_messages, diagnostics = _continuous_beam_team_spans(tasks)
    validation.extend(span_messages)
    resources = _continuous_beam_team_resources(enabled_resources)
    if not spans:
        return None
    if not resources:
        validation.append(
            ValidationMessage(
                level="warning",
                message="已识别现浇连续梁联，但当前没有启用的连续梁班组资源，联级班组占用约束未启用。",
            )
        )
        return _ContinuousBeamTeamSpanModel(spans, {}, {}, {}, {}, diagnostics)

    assignment_vars: dict[tuple[str, str], Any] = {}
    start_vars: dict[str, Any] = {}
    end_vars: dict[str, Any] = {}
    resources_by_id = {resource.id: resource for resource in resources}
    for index, span in enumerate(spans):
        start_var = model.NewIntVar(0, horizon, f"continuous_span_start_{index}_{_safe(span.span_group_id)}")
        end_var = model.NewIntVar(0, horizon, f"continuous_span_end_{index}_{_safe(span.span_group_id)}")
        duration_var = model.NewIntVar(0, horizon, f"continuous_span_duration_{index}_{_safe(span.span_group_id)}")
        model.AddMinEquality(start_var, [starts[task_id] for task_id in span.task_ids])
        model.AddMaxEquality(end_var, [ends[task_id] for task_id in span.task_ids])
        model.Add(duration_var == end_var - start_var)
        start_vars[span.span_group_id] = start_var
        end_vars[span.span_group_id] = end_var

        choices = []
        for resource in resources:
            assigned = model.NewBoolVar(f"assign_continuous_span_{index}_{_safe(resource.id)}")
            assignment_vars[(span.span_group_id, resource.id)] = assigned
            choices.append(assigned)
            interval = model.NewOptionalIntervalVar(
                start_var,
                duration_var,
                end_var,
                assigned,
                f"interval_continuous_span_{index}_{_safe(resource.id)}",
            )
            resource_intervals[resource.id].append(interval)
        model.AddExactlyOne(choices)

    return _ContinuousBeamTeamSpanModel(spans, assignment_vars, start_vars, end_vars, resources_by_id, diagnostics)


def _continuous_span_resource(
    span: _ContinuousBeamTeamSpan,
    span_model: _ContinuousBeamTeamSpanModel | None,
    solver: Any,
) -> Resource | None:
    if span_model is None:
        return None
    for resource_id, resource in span_model.resources_by_id.items():
        assignment = span_model.assignment_vars.get((span.span_group_id, resource_id))
        if assignment is not None and solver.BooleanValue(assignment):
            return resource
    return None


def _continuous_span_result_payload(
    *,
    schedule_input: ScheduleInput,
    span_model: _ContinuousBeamTeamSpanModel | None,
    solver: Any | None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if span_model is not None:
        spans = span_model.spans
        if diagnostics is None:
            diagnostics = span_model.diagnostics or []
    else:
        spans, _, span_diagnostics = _continuous_beam_team_spans(schedule_input.tasks)
        if diagnostics is None:
            diagnostics = span_diagnostics
    resource_quantity = len(span_model.resources_by_id) if span_model is not None else 0
    payload_spans: list[dict[str, Any]] = []
    for span in spans:
        resource = _continuous_span_resource(span, span_model, solver) if solver is not None else None
        start_offset = solver.Value(span_model.start_vars[span.span_group_id]) if solver is not None and span_model and span.span_group_id in span_model.start_vars else None
        end_offset = solver.Value(span_model.end_vars[span.span_group_id]) if solver is not None and span_model and span.span_group_id in span_model.end_vars else None
        payload_spans.append(
            {
                "span_group_id": span.span_group_id,
                "display_name": span.display_name,
                "bridge_id": span.bridge_id,
                "work_section_id": span.work_section_id,
                "group_index": span.group_index,
                "resource_id": resource.id if resource else None,
                "resource_name": resource.name if resource else None,
                "resource_type": CONTINUOUS_BEAM_RESOURCE_TYPE,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "start_date": _offset_date(schedule_input.start_date, start_offset) if start_offset is not None else None,
                "finish_date": _finish_date(schedule_input.start_date, end_offset) if end_offset is not None else None,
                "task_ids": list(span.task_ids),
            }
        )
    return {
        "enabled": bool(span_model and span_model.assignment_vars),
        "span_count": len(spans),
        "resource_type": CONTINUOUS_BEAM_RESOURCE_TYPE,
        "resource_quantity": resource_quantity,
        "spans": payload_spans,
        "diagnostics": diagnostics or [],
    }


def _continuous_span_by_task_id(span_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_task_id: dict[str, dict[str, Any]] = {}
    for span in span_payload.get("spans", []):
        if not isinstance(span, dict):
            continue
        for task_id in span.get("task_ids", []):
            if isinstance(task_id, str):
                by_task_id[task_id] = span
    return by_task_id


def _scheduled_continuous_fields(task: Task, span_by_task_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    span = span_by_task_id.get(task.id)
    if not span:
        return {}
    return {
        "continuous_span_group_id": span.get("span_group_id"),
        "continuous_span_group_name": span.get("display_name"),
        "continuous_span_resource_id": span.get("resource_id"),
        "continuous_span_resource_name": span.get("resource_name"),
    }


def _continuous_span_allocations(schedule_input: ScheduleInput, span_payload: dict[str, Any]) -> list[ResourceAllocation]:
    allocations: list[ResourceAllocation] = []
    for span in span_payload.get("spans", []):
        if not isinstance(span, dict) or not span.get("resource_id"):
            continue
        start_offset = span.get("start_offset")
        end_offset = span.get("end_offset")
        if not isinstance(start_offset, int) or not isinstance(end_offset, int):
            continue
        span_group_id = str(span.get("span_group_id") or "")
        display_name = str(span.get("display_name") or span_group_id)
        allocations.append(
            ResourceAllocation(
                resource_id=str(span["resource_id"]),
                resource_name=str(span.get("resource_name") or span["resource_id"]),
                resource_type=CONTINUOUS_BEAM_RESOURCE_TYPE,
                task_id=f"continuous-span:{span_group_id}",
                task_name=f"{display_name}（联级占用）",
                start_offset=start_offset,
                end_offset=end_offset,
                start_date=_offset_date(schedule_input.start_date, start_offset),
                finish_date=_finish_date(schedule_input.start_date, end_offset),
            )
        )
    return allocations


def _add_capacity_continuous_beam_team_span_constraints(
    model: Any,
    *,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    groups_by_type: dict[str, list[dict[str, Any]]],
    intervals_by_group: dict[str, list[Any]],
    demands_by_group: dict[str, list[int]],
    validation: list[ValidationMessage],
    horizon: int,
) -> dict[str, Any] | None:
    spans, span_messages, diagnostics = _continuous_beam_team_spans(tasks)
    validation.extend(span_messages)
    groups = groups_by_type.get(CONTINUOUS_BEAM_RESOURCE_TYPE, [])
    if not spans:
        return None
    if not groups:
        validation.append(
            ValidationMessage(
                level="warning",
                message="已识别现浇连续梁联，但当前容量模型没有可用的连续梁班组资源池，联级班组容量约束未启用。",
            )
        )
        return {
            "spans": spans,
            "assignment_vars": {},
            "start_vars": {},
            "end_vars": {},
            "groups_by_key": {},
            "diagnostics": diagnostics,
        }

    assignment_vars: dict[tuple[str, str], Any] = {}
    start_vars: dict[str, Any] = {}
    end_vars: dict[str, Any] = {}
    groups_by_key = {str(group["key"]): group for group in groups}
    for index, span in enumerate(spans):
        start_var = model.NewIntVar(0, horizon, f"capacity_continuous_span_start_{index}_{_safe(span.span_group_id)}")
        end_var = model.NewIntVar(0, horizon, f"capacity_continuous_span_end_{index}_{_safe(span.span_group_id)}")
        duration_var = model.NewIntVar(0, horizon, f"capacity_continuous_span_duration_{index}_{_safe(span.span_group_id)}")
        model.AddMinEquality(start_var, [starts[task_id] for task_id in span.task_ids])
        model.AddMaxEquality(end_var, [ends[task_id] for task_id in span.task_ids])
        model.Add(duration_var == end_var - start_var)
        start_vars[span.span_group_id] = start_var
        end_vars[span.span_group_id] = end_var

        choices = []
        for group in groups:
            group_key = str(group["key"])
            assigned = model.NewBoolVar(f"capacity_assign_continuous_span_{index}_{_safe(group_key)}")
            assignment_vars[(span.span_group_id, group_key)] = assigned
            choices.append(assigned)
            interval = model.NewOptionalIntervalVar(
                start_var,
                duration_var,
                end_var,
                assigned,
                f"capacity_interval_continuous_span_{index}_{_safe(group_key)}",
            )
            intervals_by_group[group_key].append(interval)
            demands_by_group[group_key].append(1)
        model.AddExactlyOne(choices)

    return {
        "spans": spans,
        "assignment_vars": assignment_vars,
        "start_vars": start_vars,
        "end_vars": end_vars,
        "groups_by_key": groups_by_key,
        "diagnostics": diagnostics,
    }


def _capacity_continuous_span_payload(
    *,
    schedule_input: ScheduleInput,
    solved: dict[str, Any],
    fixed_counts: dict[str, int],
) -> dict[str, Any]:
    model_payload = solved.get("continuous_span_model")
    if not model_payload:
        return _continuous_span_result_payload(schedule_input=schedule_input, span_model=None, solver=None)
    spans: list[_ContinuousBeamTeamSpan] = list(model_payload.get("spans", []))
    solver = solved["solver"]
    limited_resources = _apply_resource_limits(
        [resource for resource in schedule_input.resources if resource.enabled],
        fixed_counts,
    )
    resources_by_group = {
        group["key"]: sorted(group["resources"], key=_resource_sort_key)
        for group in _resource_groups(limited_resources)
        if group["resource_type"] == CONTINUOUS_BEAM_RESOURCE_TYPE
    }
    resource_ready = {
        resource.id: 0
        for resources in resources_by_group.values()
        for resource in resources
    }
    selected_resource_by_span_id: dict[str, Resource] = {}
    ordered_spans = sorted(
        spans,
        key=lambda span: (
            solver.Value(model_payload["start_vars"][span.span_group_id])
            if span.span_group_id in model_payload.get("start_vars", {})
            else 0,
            span.span_group_id,
        ),
    )
    for span in ordered_spans:
        selected_group_key = None
        for (span_group_id, group_key), assignment in model_payload.get("assignment_vars", {}).items():
            if span_group_id == span.span_group_id and solver.BooleanValue(assignment):
                selected_group_key = group_key
                break
        if selected_group_key is None:
            continue
        candidates = resources_by_group.get(selected_group_key, [])
        start_offset = solver.Value(model_payload["start_vars"][span.span_group_id])
        end_offset = solver.Value(model_payload["end_vars"][span.span_group_id])
        assigned_resource = next((resource for resource in candidates if resource_ready[resource.id] <= start_offset), None)
        if not assigned_resource and candidates:
            assigned_resource = min(candidates, key=lambda resource: resource_ready[resource.id])
        if assigned_resource:
            selected_resource_by_span_id[span.span_group_id] = assigned_resource
            resource_ready[assigned_resource.id] = end_offset

    payload_spans: list[dict[str, Any]] = []
    for span in spans:
        resource = selected_resource_by_span_id.get(span.span_group_id)
        start_offset = (
            solver.Value(model_payload["start_vars"][span.span_group_id])
            if span.span_group_id in model_payload.get("start_vars", {})
            else None
        )
        end_offset = (
            solver.Value(model_payload["end_vars"][span.span_group_id])
            if span.span_group_id in model_payload.get("end_vars", {})
            else None
        )
        payload_spans.append(
            {
                "span_group_id": span.span_group_id,
                "display_name": span.display_name,
                "bridge_id": span.bridge_id,
                "work_section_id": span.work_section_id,
                "group_index": span.group_index,
                "resource_id": resource.id if resource else None,
                "resource_name": resource.name if resource else None,
                "resource_type": CONTINUOUS_BEAM_RESOURCE_TYPE,
                "start_offset": start_offset,
                "end_offset": end_offset,
                "start_date": _offset_date(schedule_input.start_date, start_offset) if start_offset is not None else None,
                "finish_date": _finish_date(schedule_input.start_date, end_offset) if end_offset is not None else None,
                "task_ids": list(span.task_ids),
            }
        )
    return {
        "enabled": bool(model_payload.get("assignment_vars")),
        "span_count": len(spans),
        "resource_type": CONTINUOUS_BEAM_RESOURCE_TYPE,
        "resource_quantity": sum(len(resources) for resources in resources_by_group.values()),
        "spans": payload_spans,
        "diagnostics": model_payload.get("diagnostics", []),
    }


def _resource_parallel_group_key(resource: Resource) -> str:
    return resource.pool_id or resource.type


def _same_structure_resource_rule_key(task: Task, resource_group_key: str) -> tuple[str, str, str, str]:
    return (
        resource_group_key,
        task.structure_id,
        task.component_type,
        task.process_name,
    )


def _drill_group_id(rule_key: tuple[str, str, str, str]) -> str:
    return "drill_group:" + ":".join(str(part) for part in rule_key)


def _drill_group_child_sort_key(task: Task) -> tuple[Any, ...]:
    pile_sequence = _pile_sequence_number(task)
    return (
        pile_sequence is None,
        pile_sequence if pile_sequence is not None else 0,
        task.sequence_order,
        _component_rank(task.component_type),
        task.id,
    )


def _drill_group_node_sort_key(group: _DrillGroupNode) -> tuple[Any, ...]:
    task = group.representative_task
    location = _task_location(task)
    side_rank = {"L": 0, "R": 1, "N": 2}.get(location["side"] or "N", 2)
    support_index = location["support_index"] if location["support_index"] is not None else 9999
    return (
        task.bridge_id or "",
        group.resource_group_key,
        group.component_type,
        group.process_name,
        support_index,
        side_rank,
        task.work_section_id or "",
        group.sequence_order,
        group.group_id,
    )


def _pile_sequence_number(task: Task) -> int | None:
    for value in (task.id, task.name):
        match = re.search(r"(?:^|[-_\s])PILE[-_\s]*(\d+)(?:$|[-_\s])", value, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d+)\s*#\s*pile", value, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _build_drill_group_nodes(
    tasks: list[Task],
    resource_candidates: dict[str, list[Resource]],
    enabled_resources: list[Resource],
) -> list[_DrillGroupNode]:
    resources_by_group_key: dict[str, list[Resource]] = defaultdict(list)
    for resource in enabled_resources:
        resources_by_group_key[_resource_parallel_group_key(resource)].append(resource)

    eligible_group_keys = {
        group_key
        for group_key, resources in resources_by_group_key.items()
        if resources
        and all(resource.type in MECHANICAL_DRILL_RESOURCE_TYPES for resource in resources)
    }
    if not eligible_group_keys:
        return []

    grouped: dict[tuple[str, str, str, str], list[Task]] = defaultdict(list)
    for task in tasks:
        if task.component_type != "pile":
            continue
        candidates = resource_candidates.get(task.id, [])
        if not candidates or not all(resource.type in MECHANICAL_DRILL_RESOURCE_TYPES for resource in candidates):
            continue
        candidate_group_keys = {_resource_parallel_group_key(resource) for resource in candidates}
        if len(candidate_group_keys) != 1:
            continue
        resource_group_key = next(iter(candidate_group_keys))
        if resource_group_key not in eligible_group_keys:
            continue
        grouped[_same_structure_resource_rule_key(task, resource_group_key)].append(task)

    nodes: list[_DrillGroupNode] = []
    for rule_key, group_tasks in grouped.items():
        ordered_tasks = sorted(group_tasks, key=_drill_group_child_sort_key)
        if not ordered_tasks:
            continue
        candidate_sets = [
            {resource.id for resource in resource_candidates.get(task.id, [])}
            for task in ordered_tasks
        ]
        eligible_resource_ids = set.intersection(*candidate_sets) if candidate_sets else set()
        if not eligible_resource_ids:
            continue
        representative_task = ordered_tasks[0]
        nodes.append(
            _DrillGroupNode(
                group_id=_drill_group_id(rule_key),
                group_key=rule_key,
                resource_group_key=rule_key[0],
                structure_id=rule_key[1],
                component_type=rule_key[2],
                process_name=rule_key[3],
                child_task_ids=tuple(task.id for task in ordered_tasks),
                duration_days=sum(task.duration_days for task in ordered_tasks),
                sequence_order=min(task.sequence_order for task in ordered_tasks),
                eligible_resource_ids=tuple(sorted(eligible_resource_ids)),
                representative_task=representative_task,
            )
        )
    return sorted(nodes, key=_drill_group_node_sort_key)


def _drill_group_task_ids(groups: list[_DrillGroupNode]) -> set[str]:
    return {task_id for group in groups for task_id in group.child_task_ids}


def _expand_drill_group_scope(task_ids: list[str], groups: list[_DrillGroupNode]) -> list[str]:
    scoped = set(task_ids)
    if not scoped:
        return task_ids
    for group in groups:
        if scoped.intersection(group.child_task_ids):
            scoped.update(group.child_task_ids)
    return sorted(scoped)


def _add_drill_group_contiguity_constraints(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    groups: list[_DrillGroupNode],
) -> None:
    for group in groups:
        child_ids = [task_id for task_id in group.child_task_ids if task_id in starts and task_id in ends]
        for previous_id, current_id in zip(child_ids, child_ids[1:]):
            model.Add(starts[current_id] == ends[previous_id])


def _add_drill_group_boundary_precedence_constraints(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    groups: list[_DrillGroupNode],
    precedence_links: list[PrecedenceLink],
) -> None:
    group_by_task_id = {
        task_id: group
        for group in groups
        for task_id in group.child_task_ids
    }

    def boundary_ids(task_id: str) -> tuple[str, str]:
        group = group_by_task_id.get(task_id)
        if group is None:
            return task_id, task_id
        return group.child_task_ids[0], group.child_task_ids[-1]

    for link in precedence_links:
        predecessor_group = group_by_task_id.get(link.predecessor_id)
        successor_group = group_by_task_id.get(link.successor_id)
        if predecessor_group is None and successor_group is None:
            continue
        if predecessor_group is not None and predecessor_group == successor_group:
            continue
        predecessor_start_id, predecessor_end_id = boundary_ids(link.predecessor_id)
        successor_start_id, successor_end_id = boundary_ids(link.successor_id)
        if (
            predecessor_start_id not in starts
            or predecessor_end_id not in ends
            or successor_start_id not in starts
            or successor_end_id not in ends
        ):
            continue
        if link.relationship == "SS":
            model.Add(starts[successor_start_id] >= starts[predecessor_start_id] + link.lag_days)
        elif link.relationship == "FF":
            model.Add(ends[successor_end_id] >= ends[predecessor_end_id] + link.lag_days)
        elif link.relationship == "SF":
            model.Add(ends[successor_end_id] >= starts[predecessor_start_id] + link.lag_days)
        else:
            model.Add(starts[successor_start_id] >= ends[predecessor_end_id] + link.lag_days)


def _add_fixed_task_resource_constraints(
    model: Any,
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
    fixed_resource_by_task_id: dict[str, str],
) -> None:
    for task_id, fixed_resource_id in fixed_resource_by_task_id.items():
        for resource in resource_candidates.get(task_id, []):
            assignment = assignment_vars.get((task_id, resource.id))
            if assignment is None:
                continue
            model.Add(assignment == (1 if resource.id == fixed_resource_id else 0))


def _execution_constraint_validation(
    schedule_input: ScheduleInput,
    resource_candidates: dict[str, list[Resource]],
) -> list[ValidationMessage]:
    task_ids = {task.id for task in schedule_input.tasks}
    messages: list[ValidationMessage] = []
    seen: set[str] = set()
    for constraint in schedule_input.execution_constraints:
        if constraint.task_id in seen:
            messages.append(ValidationMessage(level="error", subject_id=constraint.task_id, message="同一任务存在重复执行约束。"))
            continue
        seen.add(constraint.task_id)
        if constraint.task_id not in task_ids:
            messages.append(ValidationMessage(level="error", subject_id=constraint.task_id, message="执行约束引用了不存在的任务。"))
            continue
        if constraint.fixed_resource_id is not None and constraint.fixed_resource_id not in {
            resource.id for resource in resource_candidates.get(constraint.task_id, [])
        }:
            messages.append(
                ValidationMessage(
                    level="error",
                    subject_id=constraint.task_id,
                    message=f"固定资源 {constraint.fixed_resource_id} 不是该任务的可用资源。",
                )
            )
    return messages


def _add_execution_constraints(
    model: Any,
    schedule_input: ScheduleInput,
    starts: dict[str, Any],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
) -> None:
    fixed_resources: dict[str, str] = {}
    for constraint in schedule_input.execution_constraints:
        if constraint.task_id not in starts:
            continue
        if constraint.earliest_start_offset is not None:
            model.Add(starts[constraint.task_id] >= constraint.earliest_start_offset)
        if constraint.fixed_start_offset is not None:
            model.Add(starts[constraint.task_id] == constraint.fixed_start_offset)
        if constraint.fixed_resource_id is not None:
            fixed_resources[constraint.task_id] = constraint.fixed_resource_id
    _add_fixed_task_resource_constraints(model, resource_candidates, assignment_vars, fixed_resources)


def _drill_line_sequences(groups: list[_DrillGroupNode]) -> list[list[_DrillGroupNode]]:
    buckets: dict[tuple[Any, ...], list[_DrillGroupNode]] = defaultdict(list)
    for group in groups:
        task = group.representative_task
        location = _task_location(task)
        sequence_key = (
            task.bridge_id or "",
            task.work_section_id or "",
            location["side"] or "N",
            group.resource_group_key,
            group.component_type,
            group.process_name,
        )
        buckets[sequence_key].append(group)
    return [
        sorted(items, key=lambda group: (_task_spatial_sort_key(group.representative_task), group.group_id))
        for _, items in sorted(buckets.items(), key=lambda item: item[0])
        if items
    ]


def _bool_and_var(model: Any, name: str, literals: list[Any]) -> Any:
    both = model.NewBoolVar(name)
    for literal in literals:
        model.Add(both <= literal)
    model.Add(both >= sum(literals) - (len(literals) - 1))
    return both


def _empty_drill_group_stage1_route_terms(status: str = "not_applicable") -> dict[str, Any]:
    return {
        "route_terms": [],
        "same_side_terms": [],
        "cross_side_terms": [],
        "metadata": {
            "stage1_route_status": status,
            "stage1_route_candidate_mode": None,
            "stage1_route_node_count": 0,
            "stage1_route_unique_group_count": 0,
            "stage1_route_candidate_arc_count": 0,
            "stage1_route_rejected_arc_counts": {
                "same_side_window_exceeded": 0,
                "cross_side_gap_exceeded": 0,
                "missing_location": 0,
                "scope_mismatch": 0,
            },
            "stage1_same_side_penalty": 0,
            "stage1_cross_side_penalty": 0,
            "stage1_route_penalty": 0,
            "stage1_route_failure_reason": None,
            "stage1_route_sparse_same_side_window": MECHANICAL_DRILL_PATH_SUPPORT_WINDOW,
            "stage1_route_sparse_cross_side_window": MECHANICAL_DRILL_CROSS_SIDE_SUPPORT_WINDOW,
        },
    }


def _stage1_route_metadata_from_path(path_metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not path_metadata:
        return _empty_drill_group_stage1_route_terms("not_applicable")["metadata"]
    empty = _empty_drill_group_stage1_route_terms("not_applicable")["metadata"]
    return {
        key: path_metadata.get(key, value)
        for key, value in empty.items()
    }


def _with_stage1_route_failure(metadata: dict[str, Any], reason: str) -> dict[str, Any]:
    next_metadata = dict(metadata)
    if next_metadata.get("stage1_route_status") == "enabled":
        next_metadata["stage1_route_status"] = "infeasible"
        next_metadata["stage1_route_failure_reason"] = reason
    return next_metadata


def _drill_group_stage1_route_context(
    groups: list[_DrillGroupNode],
) -> dict[str, dict[tuple[Any, ...], dict[str, int]]]:
    same_side_positions: dict[tuple[Any, ...], dict[str, int]] = {}
    buckets: dict[tuple[Any, ...], list[_DrillGroupNode]] = defaultdict(list)
    for group in groups:
        task = group.representative_task
        location = _task_location(task)
        support_index = location["support_index"]
        side = location["side"]
        if location["structure_type"] != "pier" or support_index is None or side not in {"L", "R"}:
            continue
        key = (
            task.bridge_id or "",
            group.resource_group_key,
            group.component_type,
            group.process_name,
            side,
        )
        buckets[key].append(group)

    for key, items in buckets.items():
        ordered = sorted(
            items,
            key=lambda group: (
                _task_location(group.representative_task)["support_index"],
                group.sequence_order,
                group.group_id,
            ),
        )
        same_side_positions[key] = {
            group.group_id: position
            for position, group in enumerate(ordered)
        }
    return {"same_side": same_side_positions}


def _drill_group_stage1_routable(group: _DrillGroupNode) -> bool:
    location = _task_location(group.representative_task)
    return (
        location["structure_type"] == "pier"
        and location["support_index"] is not None
        and location["side"] in {"L", "R"}
    )


def _drill_group_stage1_transition_decision(
    previous_group: _DrillGroupNode,
    current_group: _DrillGroupNode,
    route_context: dict[str, dict[tuple[Any, ...], dict[str, int]]],
) -> _DrillGroupStage1RouteDecision:
    previous_task = previous_group.representative_task
    current_task = current_group.representative_task
    previous_location = _task_location(previous_task)
    current_location = _task_location(current_task)
    if (
        previous_location["structure_type"] != "pier"
        or current_location["structure_type"] != "pier"
        or previous_location["support_index"] is None
        or current_location["support_index"] is None
        or previous_location["side"] not in {"L", "R"}
        or current_location["side"] not in {"L", "R"}
    ):
        return _DrillGroupStage1RouteDecision(
            allowed=False,
            transition_kind="unknown",
            rejection_reason="missing_location",
        )
    if (
        previous_task.bridge_id != current_task.bridge_id
        or previous_group.resource_group_key != current_group.resource_group_key
        or previous_group.component_type != current_group.component_type
        or previous_group.process_name != current_group.process_name
    ):
        return _DrillGroupStage1RouteDecision(
            allowed=False,
            transition_kind="unknown",
            rejection_reason="scope_mismatch",
        )

    previous_side = previous_location["side"]
    current_side = current_location["side"]
    previous_support_index = previous_location["support_index"]
    current_support_index = current_location["support_index"]
    if previous_side == current_side:
        key = (
            previous_task.bridge_id or "",
            previous_group.resource_group_key,
            previous_group.component_type,
            previous_group.process_name,
            previous_side,
        )
        positions = route_context["same_side"].get(key, {})
        previous_position = positions.get(previous_group.group_id)
        current_position = positions.get(current_group.group_id)
        if previous_position is None or current_position is None:
            return _DrillGroupStage1RouteDecision(
                allowed=False,
                transition_kind="same_side",
                rejection_reason="missing_location",
            )
        sequence_distance = abs(current_position - previous_position)
        return _DrillGroupStage1RouteDecision(
            allowed=sequence_distance > 0,
            transition_kind="same_side",
            penalty=0,
            rejection_reason=None if sequence_distance > 0 else "missing_location",
            same_side_sequence_distance=sequence_distance,
        )

    support_gap = abs(current_support_index - previous_support_index)
    return _DrillGroupStage1RouteDecision(
        allowed=True,
        transition_kind="cross_side",
        penalty=0,
        cross_side_support_gap=support_gap,
    )


def _build_drill_group_stage1_route_terms(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    groups: list[_DrillGroupNode],
    enabled_resources: list[Resource],
    assignment_vars: dict[tuple[str, str], Any],
) -> dict[str, Any]:
    result = _empty_drill_group_stage1_route_terms("not_applicable")
    if not groups:
        return result

    routable_groups = [group for group in groups if _drill_group_stage1_routable(group)]
    if not routable_groups:
        return result

    metadata = result["metadata"]
    metadata["stage1_route_status"] = "enabled"
    metadata["stage1_route_candidate_mode"] = "unbounded"
    metadata["stage1_route_unique_group_count"] = len(routable_groups)
    rejected_counts = metadata["stage1_route_rejected_arc_counts"]
    same_side_terms: list[Any] = []
    cross_side_terms: list[Any] = []
    resources_by_id = {
        resource.id: resource
        for resource in enabled_resources
        if resource.type in MECHANICAL_DRILL_RESOURCE_TYPES
    }

    for resource in sorted(resources_by_id.values(), key=_resource_sort_key):
        resource_groups = [
            group
            for group in routable_groups
            if resource.id in group.eligible_resource_ids
            and group.child_task_ids
            and assignment_vars.get((group.child_task_ids[0], resource.id)) is not None
        ]
        if not resource_groups:
            continue
        resource_groups = sorted(
            resource_groups,
            key=lambda group: (_task_spatial_sort_key(group.representative_task), group.group_id),
        )
        metadata["stage1_route_node_count"] += len(resource_groups)
        if len(resource_groups) <= 1:
            continue

        assignments = [
            assignment_vars[(group.child_task_ids[0], resource.id)]
            for group in resource_groups
        ]
        resource_used = model.NewBoolVar(f"drill_stage1_resource_used_{_safe(resource.id)}")
        for assignment in assignments:
            model.Add(assignment <= resource_used)
        model.Add(sum(assignments) >= resource_used)

        indexed_groups = list(enumerate(resource_groups, start=1))
        arcs = [(0, 0, resource_used.Not())]
        for node_index, group in indexed_groups:
            presence = assignment_vars[(group.child_task_ids[0], resource.id)]
            arcs.append((node_index, node_index, presence.Not()))
            arcs.append((0, node_index, model.NewBoolVar(f"drill_stage1_start_{_safe(resource.id)}_{node_index}")))
            arcs.append((node_index, 0, model.NewBoolVar(f"drill_stage1_end_{_safe(resource.id)}_{node_index}")))

        route_context = _drill_group_stage1_route_context(resource_groups)
        for previous_index, previous_group in indexed_groups:
            for current_index, current_group in indexed_groups:
                if previous_index == current_index:
                    continue
                decision = _drill_group_stage1_transition_decision(
                    previous_group,
                    current_group,
                    route_context,
                )
                if not decision.allowed:
                    reason = decision.rejection_reason or "scope_mismatch"
                    rejected_counts[reason] = int(rejected_counts.get(reason, 0)) + 1
                    continue

                transition = model.NewBoolVar(
                    f"drill_stage1_arc_{_safe(resource.id)}_{previous_index}_{current_index}"
                )
                arcs.append((previous_index, current_index, transition))
                metadata["stage1_route_candidate_arc_count"] += 1
                model.Add(starts[current_group.child_task_ids[0]] >= ends[previous_group.child_task_ids[-1]]).OnlyEnforceIf(transition)
                if decision.penalty:
                    if decision.transition_kind == "same_side":
                        same_side_terms.append(decision.penalty * transition)
                    elif decision.transition_kind == "cross_side":
                        cross_side_terms.append(decision.penalty * transition)

        model.AddCircuit(arcs)

    result["same_side_terms"] = same_side_terms
    result["cross_side_terms"] = cross_side_terms
    result["route_terms"] = same_side_terms + cross_side_terms
    return result


def _build_drill_group_coarse_jump_terms(
    model: Any,
    groups: list[_DrillGroupNode],
    assignment_vars: dict[tuple[str, str], Any],
) -> dict[str, list[Any]]:
    adjacent_terms: list[Any] = []
    hole_terms: list[Any] = []
    if not groups:
        return {"adjacent_terms": adjacent_terms, "hole_terms": hole_terms}

    representative_task_id_by_group = {
        group.group_id: group.child_task_ids[0]
        for group in groups
        if group.child_task_ids
    }
    for sequence_index, sequence in enumerate(_drill_line_sequences(groups)):
        for pair_index, (left, right) in enumerate(zip(sequence, sequence[1:])):
            left_task_id = representative_task_id_by_group.get(left.group_id)
            right_task_id = representative_task_id_by_group.get(right.group_id)
            if left_task_id is None or right_task_id is None:
                continue
            for left_resource_id in left.eligible_resource_ids:
                left_assignment = assignment_vars.get((left_task_id, left_resource_id))
                if left_assignment is None:
                    continue
                for right_resource_id in right.eligible_resource_ids:
                    if left_resource_id == right_resource_id:
                        continue
                    right_assignment = assignment_vars.get((right_task_id, right_resource_id))
                    if right_assignment is None:
                        continue
                    adjacent_terms.append(
                        _bool_and_var(
                            model,
                            "drill_adjacent_switch_"
                            f"{sequence_index}_{pair_index}_{_safe(left_resource_id)}_{_safe(right_resource_id)}",
                            [left_assignment, right_assignment],
                        )
                    )

        for triple_index, (left, middle, right) in enumerate(zip(sequence, sequence[1:], sequence[2:])):
            left_task_id = representative_task_id_by_group.get(left.group_id)
            middle_task_id = representative_task_id_by_group.get(middle.group_id)
            right_task_id = representative_task_id_by_group.get(right.group_id)
            if left_task_id is None or middle_task_id is None or right_task_id is None:
                continue
            shared_outer_resources = set(left.eligible_resource_ids).intersection(right.eligible_resource_ids)
            for outer_resource_id in sorted(shared_outer_resources):
                left_assignment = assignment_vars.get((left_task_id, outer_resource_id))
                right_assignment = assignment_vars.get((right_task_id, outer_resource_id))
                if left_assignment is None or right_assignment is None:
                    continue
                for middle_resource_id in middle.eligible_resource_ids:
                    if middle_resource_id == outer_resource_id:
                        continue
                    middle_assignment = assignment_vars.get((middle_task_id, middle_resource_id))
                    if middle_assignment is None:
                        continue
                    hole_terms.append(
                        _bool_and_var(
                            model,
                            "drill_hole_jump_"
                            f"{sequence_index}_{triple_index}_{_safe(outer_resource_id)}_{_safe(middle_resource_id)}",
                            [left_assignment, middle_assignment, right_assignment],
                        )
                    )
    return {"adjacent_terms": adjacent_terms, "hole_terms": hole_terms}


def _drill_group_assignment_by_group(
    groups: list[_DrillGroupNode],
    scheduled_tasks: list[ScheduledTask],
) -> dict[str, str]:
    scheduled_by_id = {task.id: task for task in scheduled_tasks}
    assignments: dict[str, str] = {}
    for group in groups:
        resource_ids = {
            scheduled_by_id[task_id].assigned_resource_id
            for task_id in group.child_task_ids
            if task_id in scheduled_by_id and scheduled_by_id[task_id].assigned_resource_id
        }
        if len(resource_ids) == 1:
            assignments[group.group_id] = next(iter(resource_ids))
    return assignments


def _fixed_resources_from_drill_groups(
    groups: list[_DrillGroupNode],
    scheduled_tasks: list[ScheduledTask],
) -> dict[str, str]:
    scheduled_by_id = {task.id: task for task in scheduled_tasks}
    fixed: dict[str, str] = {}
    for group in groups:
        resource_ids = {
            scheduled_by_id[task_id].assigned_resource_id
            for task_id in group.child_task_ids
            if task_id in scheduled_by_id and scheduled_by_id[task_id].assigned_resource_id
        }
        if len(resource_ids) != 1:
            continue
        resource_id = next(iter(resource_ids))
        for task_id in group.child_task_ids:
            fixed[task_id] = resource_id
    return fixed


def _drill_group_path_filter_by_resource(
    groups: list[_DrillGroupNode],
    fixed_resource_by_task_id: dict[str, str],
) -> dict[str, set[str]]:
    filter_by_resource: dict[str, set[str]] = defaultdict(set)
    for group in groups:
        resource_ids = {
            fixed_resource_by_task_id.get(task_id)
            for task_id in group.child_task_ids
            if fixed_resource_by_task_id.get(task_id)
        }
        if len(resource_ids) != 1:
            continue
        resource_id = next(iter(resource_ids))
        filter_by_resource[resource_id].update(group.child_task_ids)
    return dict(filter_by_resource)


def _drill_group_assignment_penalties(
    groups: list[_DrillGroupNode],
    assignment_by_group_id: dict[str, str],
) -> dict[str, int]:
    adjacent_switches = 0
    hole_jumps = 0
    for sequence in _drill_line_sequences(groups):
        for left, right in zip(sequence, sequence[1:]):
            left_resource = assignment_by_group_id.get(left.group_id)
            right_resource = assignment_by_group_id.get(right.group_id)
            if left_resource and right_resource and left_resource != right_resource:
                adjacent_switches += 1
        for left, middle, right in zip(sequence, sequence[1:], sequence[2:]):
            left_resource = assignment_by_group_id.get(left.group_id)
            middle_resource = assignment_by_group_id.get(middle.group_id)
            right_resource = assignment_by_group_id.get(right.group_id)
            if (
                left_resource
                and middle_resource
                and right_resource
                and left_resource == right_resource
                and middle_resource != left_resource
            ):
                hole_jumps += 1
    return {
        "adjacent_resource_switch_penalty": adjacent_switches,
        "hole_jump_penalty": hole_jumps,
    }


def _drill_group_baseline_candidate_arc_count(groups: list[_DrillGroupNode]) -> int:
    group_ids_by_resource: dict[str, set[str]] = defaultdict(set)
    for group in groups:
        for resource_id in group.eligible_resource_ids:
            group_ids_by_resource[resource_id].add(group.group_id)
    return sum(len(group_ids) * (len(group_ids) - 1) for group_ids in group_ids_by_resource.values())


def _drill_group_stage2_path_diagnostics_by_resource(
    groups: list[_DrillGroupNode],
    scheduled_tasks: list[ScheduledTask],
    enabled_resources: list[Resource],
) -> list[dict[str, Any]]:
    scheduled_by_id = {task.id: task for task in scheduled_tasks}
    resource_by_id = {
        resource.id: resource
        for resource in enabled_resources
        if resource.type in MECHANICAL_DRILL_RESOURCE_TYPES
    }
    groups_by_resource: dict[str, list[tuple[_DrillGroupNode, int, int]]] = defaultdict(list)
    for group in groups:
        resource_ids = {
            scheduled_by_id[task_id].assigned_resource_id
            for task_id in group.child_task_ids
            if task_id in scheduled_by_id and scheduled_by_id[task_id].assigned_resource_id
        }
        if len(resource_ids) != 1:
            continue
        resource_id = next(iter(resource_ids))
        if resource_id not in resource_by_id:
            continue
        starts = [
            scheduled_by_id[task_id].start_offset
            for task_id in group.child_task_ids
            if task_id in scheduled_by_id
        ]
        ends = [
            scheduled_by_id[task_id].end_offset
            for task_id in group.child_task_ids
            if task_id in scheduled_by_id
        ]
        groups_by_resource[resource_id].append((group, min(starts or [0]), max(ends or [0])))

    diagnostics: list[dict[str, Any]] = []
    for resource in sorted(resource_by_id.values(), key=_resource_sort_key):
        assigned_groups = sorted(
            groups_by_resource.get(resource.id, []),
            key=lambda item: (item[1], item[2], item[0].group_id),
        )
        path_nodes = [
            {
                "representative_task": group.representative_task,
                "group": group,
                "start_offset": start_offset,
                "end_offset": end_offset,
            }
            for group, start_offset, end_offset in assigned_groups
        ]
        indexed_nodes = list(enumerate(path_nodes, start=1))
        node_count = len(indexed_nodes)
        allowed_pairs = (
            _resource_path_allowed_transition_pairs(resource, indexed_nodes)
            if node_count > 1
            else set()
        )
        coarse_order_transition_count = max(0, node_count - 1)
        coarse_order_allowed_count = 0
        violation_examples: list[dict[str, Any]] = []
        for (previous_index, previous_node), (current_index, current_node) in zip(
            indexed_nodes,
            indexed_nodes[1:],
        ):
            if (previous_index, current_index) in allowed_pairs:
                coarse_order_allowed_count += 1
                continue
            if len(violation_examples) < 5:
                previous_group = previous_node["group"]
                current_group = current_node["group"]
                violation_examples.append(
                    {
                        "from_group_id": previous_group.group_id,
                        "to_group_id": current_group.group_id,
                        "from_structure_id": previous_group.structure_id,
                        "to_structure_id": current_group.structure_id,
                        "from_start_offset": previous_node["start_offset"],
                        "to_start_offset": current_node["start_offset"],
                    }
                )

        child_task_count = sum(len(group.child_task_ids) for group, _, _ in assigned_groups)
        diagnostics.append(
            {
                "resource_id": resource.id,
                "resource_name": resource.name,
                "resource_type": resource.type,
                "path_node_count": node_count,
                "assigned_child_task_count": child_task_count,
                "all_directed_transition_pair_count": node_count * (node_count - 1),
                "candidate_transition_arc_count": len(allowed_pairs),
                "coarse_order_transition_count": coarse_order_transition_count,
                "coarse_order_allowed_transition_count": coarse_order_allowed_count,
                "coarse_order_violation_count": coarse_order_transition_count - coarse_order_allowed_count,
                "coarse_order_violation_examples": violation_examples,
            }
        )
    return diagnostics


def _drill_group_refinement_payload(
    *,
    status: str,
    groups: list[_DrillGroupNode],
    scheduled_tasks: list[ScheduledTask],
    path_metadata: dict[str, Any] | None = None,
    stage2_path_diagnostics_by_resource: list[dict[str, Any]] | None = None,
    fallback_reason: str | None = None,
    makespan_tolerance: int = 0,
) -> dict[str, Any]:
    path_metadata = path_metadata or {}
    assignment_by_group = _drill_group_assignment_by_group(groups, scheduled_tasks)
    penalties = _drill_group_assignment_penalties(groups, assignment_by_group)
    baseline_arc_count = _drill_group_baseline_candidate_arc_count(groups)
    diagnostic_node_count = sum(
        int(item.get("path_node_count") or 0)
        for item in stage2_path_diagnostics_by_resource or []
    )
    diagnostic_arc_count = sum(
        int(item.get("candidate_transition_arc_count") or 0)
        for item in stage2_path_diagnostics_by_resource or []
    )
    stage2_node_count = int(path_metadata.get("resource_path_node_count") or diagnostic_node_count)
    stage2_arc_count = int(path_metadata.get("resource_path_transition_arc_count") or diagnostic_arc_count)
    arc_reduction_ratio = (
        round((baseline_arc_count - stage2_arc_count) / baseline_arc_count, 4)
        if baseline_arc_count > 0
        else 0.0
    )
    payload = {
        "status": status,
        "coarse_group_count": len(groups),
        "coarse_child_task_count": len(_drill_group_task_ids(groups)),
        "stage2_node_count": stage2_node_count,
        "stage2_arc_count": stage2_arc_count,
        "baseline_candidate_arc_count": baseline_arc_count,
        "arc_reduction_ratio": arc_reduction_ratio,
        "adjacent_resource_switch_penalty": penalties["adjacent_resource_switch_penalty"],
        "hole_jump_penalty": penalties["hole_jump_penalty"],
        "makespan_tolerance": makespan_tolerance,
        "fallback_reason": fallback_reason,
    }
    payload.update(_stage1_route_metadata_from_path(path_metadata))
    if stage2_path_diagnostics_by_resource is not None:
        payload["stage2_path_diagnostics_by_resource"] = stage2_path_diagnostics_by_resource
    return payload


def _attach_drill_group_refinement_metadata(
    result: ScheduleResult,
    payload: dict[str, Any],
) -> ScheduleResult:
    result.stats["drill_group_refinement"] = payload
    result.objective_breakdown["drill_group_refinement"] = payload
    result.objective_breakdown["drill_group_refinement_status"] = payload.get("status")
    return result


def _has_late_hard_milestone(result: ScheduleResult) -> bool:
    return any(
        milestone.mode == "hard" and milestone.lateness_days > 0
        for milestone in result.milestone_results
    )


def _attach_stage2_makespan_delta(
    result: ScheduleResult,
    *,
    stage1_makespan_days: int | None,
    stage2_makespan_days: int | None,
) -> ScheduleResult:
    if stage1_makespan_days is None or stage2_makespan_days is None:
        return result
    delta_payload = {
        "stage1_makespan_days": int(stage1_makespan_days),
        "stage2_makespan_days": int(stage2_makespan_days),
        "stage2_makespan_delta_days": int(stage2_makespan_days) - int(stage1_makespan_days),
    }
    for container in (result.stats, result.objective_breakdown):
        payload = container.get("drill_group_refinement")
        if isinstance(payload, dict):
            payload.update(delta_payload)
    return result


def _configured_parallel_limit(values: list[int | None]) -> int | None:
    configured = [int(value) for value in values if value is not None and int(value) > 0]
    if not configured:
        return None
    return min(configured)


def _effective_same_structure_resource_binding_limit(resources: list[Resource]) -> int | None:
    if any(resource.same_structure_resource_binding for resource in resources):
        return 1
    return None


def _add_named_same_structure_resource_rules(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
) -> None:
    resources_by_group_key: dict[str, dict[str, Resource]] = defaultdict(dict)
    for resources in resource_candidates.values():
        for resource in resources:
            resources_by_group_key[_resource_parallel_group_key(resource)][resource.id] = resource
    limit_by_group_key = {
        group_key: limit
        for group_key, resources_by_id in resources_by_group_key.items()
        if (limit := _effective_same_structure_resource_binding_limit(list(resources_by_id.values()))) is not None
    }
    if not limit_by_group_key:
        return

    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for task in tasks:
        for resource in resource_candidates.get(task.id, []):
            group_key = _resource_parallel_group_key(resource)
            if group_key not in limit_by_group_key:
                continue
            rule_key = _same_structure_resource_rule_key(task, group_key)
            bucket = grouped.setdefault(rule_key, {"tasks": {}, "resources": {}, "limit": limit_by_group_key[group_key]})
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

        parallel_limit = int(bucket["limit"])
        if len(resources) <= parallel_limit:
            continue

        selected_by_resource: dict[str, Any] = {}
        for resource in resources:
            assignments = [
                assignment_vars[(task.id, resource.id)]
                for task in group_tasks
                if (task.id, resource.id) in assignment_vars
            ]
            if not assignments:
                continue
            selected = model.NewBoolVar(f"same_structure_selected_resource_{group_index}_{_safe(resource.id)}")
            selected_by_resource[resource.id] = selected
            for assignment in assignments:
                model.Add(assignment <= selected)
            model.Add(sum(assignments) >= selected)
        if selected_by_resource:
            model.Add(sum(selected_by_resource.values()) <= parallel_limit)


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
                parallel_limit = 1 if group.get("same_structure_resource_binding") else None
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
    solver.parameters.max_time_in_seconds = max(0.1, float(time_limit_seconds or 20.0))
    solver.parameters.num_search_workers = _scheduler_search_workers()
    solver.parameters.random_seed = SCHEDULER_RANDOM_SEED
    solver.parameters.randomize_search = False


def _solver_timing_stats(
    started_at: float,
    solver: Any,
    *,
    configured_time_limit_seconds: float,
    model_built_at: float | None = None,
) -> dict[str, Any]:
    elapsed = time.perf_counter() - started_at
    stats: dict[str, Any] = {
        "elapsed_seconds": elapsed,
        "wall_time_seconds": elapsed,
        "cp_sat_wall_time_seconds": solver.WallTime(),
        "solver_time_limit_enabled": True,
        "configured_time_limit_seconds": configured_time_limit_seconds,
    }
    if model_built_at is not None:
        stats["model_build_seconds"] = max(0.0, model_built_at - started_at)
        stats["solve_elapsed_seconds"] = max(0.0, elapsed - stats["model_build_seconds"])
    return stats


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

    hinted_assignments: dict[int, int] = {}
    for (task_id, resource_id), assignment in assignment_vars.items():
        assigned_resource_id = assigned_resource_by_task_id.get(task_id)
        if assigned_resource_id is None:
            continue
        hint_value = 1 if assigned_resource_id == resource_id else 0
        hint_key = assignment.Index() if hasattr(assignment, "Index") else id(assignment)
        if hint_key in hinted_assignments:
            if hinted_assignments[hint_key] != hint_value:
                continue
            continue
        hinted_assignments[hint_key] = hint_value
        model.AddHint(assignment, hint_value)
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


def _build_named_resource_assignment_model(
    model: Any,
    *,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    enabled_resources: list[Resource],
    resource_candidates: dict[str, list[Resource]],
    horizon: int,
    assignment_prefix: str = "assign",
    interval_prefix: str = "interval",
) -> tuple[dict[tuple[str, str], Any], dict[str, list[Any]]]:
    assignment_vars: dict[tuple[str, str], Any] = {}
    resource_intervals: dict[str, list[Any]] = defaultdict(list)
    resources_by_id = {resource.id: resource for resource in enabled_resources}
    limits_by_group_key = _resource_path_parallel_limits_by_group(enabled_resources)
    fallback_tasks: list[Task] = []
    grouped_tasks: dict[tuple[tuple[str, str, str, str], tuple[str, ...], int], list[Task]] = defaultdict(list)

    def add_task_resource_interval(task: Task, resource: Resource, assignment: Any) -> None:
        assignment_vars[(task.id, resource.id)] = assignment
        interval = model.NewOptionalIntervalVar(
            starts[task.id],
            task.duration_days,
            ends[task.id],
            assignment,
            f"{interval_prefix}_{_safe(task.id)}_{_safe(resource.id)}",
        )
        resource_intervals[resource.id].append(interval)

    for task in tasks:
        candidates = resource_candidates.get(task.id, [])
        assignment_candidates = [
            resource for resource in candidates if not _is_continuous_beam_team_task_resource(task, resource)
        ]
        candidate_group_keys = {_resource_parallel_group_key(resource) for resource in assignment_candidates}
        if len(candidate_group_keys) == 1:
            group_key = next(iter(candidate_group_keys))
            limit = limits_by_group_key.get(group_key)
            if limit is not None and limit > 0:
                resource_ids = tuple(resource.id for resource in sorted(assignment_candidates, key=_resource_sort_key))
                grouped_tasks[(_same_structure_resource_rule_key(task, group_key), resource_ids, int(limit))].append(task)
                continue
        fallback_tasks.append(task)

    for task in fallback_tasks:
        choices = []
        for resource in resource_candidates.get(task.id, []):
            if _is_continuous_beam_team_task_resource(task, resource):
                continue
            assigned = model.NewBoolVar(f"{assignment_prefix}_{_safe(task.id)}_{_safe(resource.id)}")
            choices.append(assigned)
            add_task_resource_interval(task, resource, assigned)
        if choices:
            model.AddExactlyOne(choices)

    for group_index, ((_, resource_ids, limit), group_tasks) in enumerate(grouped_tasks.items()):
        resources = [resources_by_id[resource_id] for resource_id in resource_ids if resource_id in resources_by_id]
        if not resources:
            continue
        ordered_tasks = sorted(group_tasks, key=lambda item: (item.sequence_order, item.id))
        slot_count = min(max(1, int(limit)), len(ordered_tasks), len(resources))
        if slot_count <= 1:
            resource_choices = {
                resource.id: model.NewBoolVar(
                    f"{assignment_prefix}_same_structure_{group_index}_{_safe(resource.id)}"
                )
                for resource in resources
                if not any(_is_continuous_beam_team_task_resource(task, resource) for task in ordered_tasks)
            }
            if not resource_choices:
                continue
            model.AddExactlyOne(resource_choices.values())
            for task in ordered_tasks:
                for resource in resources:
                    if resource.id not in resource_choices:
                        continue
                    add_task_resource_interval(task, resource, resource_choices[resource.id])
            continue

        task_slots = _balanced_same_structure_task_slots(ordered_tasks, slot_count)
        slot_resource_choices: list[dict[str, Any]] = []
        for slot_index, slot_tasks in enumerate(task_slots):
            if not slot_tasks:
                continue
            choices = {
                resource.id: model.NewBoolVar(
                    f"{assignment_prefix}_same_structure_slot_{group_index}_{slot_index}_{_safe(resource.id)}"
                )
                for resource in resources
                if not any(_is_continuous_beam_team_task_resource(task, resource) for task in slot_tasks)
            }
            if not choices:
                continue
            model.AddExactlyOne(choices.values())
            slot_resource_choices.append(choices)
            for task in slot_tasks:
                for resource in resources:
                    if resource.id not in choices:
                        continue
                    add_task_resource_interval(task, resource, choices[resource.id])

        for resource in resources:
            resource_slot_choices = [
                choices[resource.id]
                for choices in slot_resource_choices
                if resource.id in choices
            ]
            if len(resource_slot_choices) > 1:
                model.Add(sum(resource_slot_choices) <= 1)

    return assignment_vars, resource_intervals


def _balanced_same_structure_task_slots(tasks: list[Task], slot_count: int) -> list[list[Task]]:
    slots: list[list[Task]] = [[] for _ in range(slot_count)]
    workloads = [0 for _ in range(slot_count)]
    for task in sorted(tasks, key=lambda item: (-item.duration_days, item.sequence_order, item.id)):
        slot_index = min(range(slot_count), key=lambda index: (workloads[index], len(slots[index]), index))
        slots[slot_index].append(task)
        workloads[slot_index] += task.duration_days
    return [sorted(slot_tasks, key=lambda item: (item.sequence_order, item.id)) for slot_tasks in slots]


def solve_shortest_duration_schedule(
    schedule_input: ScheduleInput,
    *,
    enforce_hard_milestones: bool = False,
) -> ScheduleResult:
    started_at = time.perf_counter()
    enabled_resources = [resource for resource in schedule_input.resources if resource.enabled]
    resource_candidates = _resource_candidates_by_task(schedule_input.tasks, enabled_resources)
    validation = _validate_resource_coverage(schedule_input.tasks, resource_candidates)
    validation.extend(_execution_constraint_validation(schedule_input, resource_candidates))
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

    assignment_vars, resource_intervals = _build_named_resource_assignment_model(
        model,
        starts=starts,
        ends=ends,
        tasks=schedule_input.tasks,
        enabled_resources=enabled_resources,
        resource_candidates=resource_candidates,
        horizon=horizon,
    )
    _add_execution_constraints(model, schedule_input, starts, resource_candidates, assignment_vars)
    continuous_span_model = _add_named_continuous_beam_team_span_constraints(
        model,
        starts=starts,
        ends=ends,
        tasks=schedule_input.tasks,
        enabled_resources=enabled_resources,
        resource_intervals=resource_intervals,
        validation=validation,
        horizon=horizon,
    )

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
    primary_objective = makespan + sum(soft_penalty_terms)
    model.Minimize(primary_objective * CONTINUITY_PRIMARY_WEIGHT)

    solver = cp_model.CpSolver()
    model_built_at = time.perf_counter()
    _configure_solver(solver, schedule_input.time_limit_seconds)
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)

    stats = {
        "horizon_days": horizon,
        **_solver_timing_stats(
            started_at,
            solver,
            configured_time_limit_seconds=schedule_input.time_limit_seconds,
            model_built_at=model_built_at,
        ),
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
    continuous_span_payload = _continuous_span_result_payload(
        schedule_input=schedule_input,
        span_model=continuous_span_model,
        solver=solver,
    )
    continuous_span_by_task_id = _continuous_span_by_task_id(continuous_span_payload)

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
            **_scheduled_continuous_fields(task, continuous_span_by_task_id),
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
    allocations.extend(_continuous_span_allocations(schedule_input, continuous_span_payload))

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
    stats["continuity_metrics"] = continuity_metrics
    stats["continuity_objective"] = {
        "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
    }
    stats["continuous_beam_team_spans"] = continuous_span_payload

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
            "continuity_score": continuity_metrics["continuity_score"],
            "weighted_objective": objective_days + soft_milestone_penalty,
        },
    )


def solve_schedule(schedule_input: ScheduleInput, *, enforce_hard_milestones: bool = False) -> ScheduleResult:
    return solve_control_priority_schedule(schedule_input, enforce_hard_milestones=enforce_hard_milestones)


def solve_control_priority_schedule_once(
    schedule_input: ScheduleInput,
    *,
    enforce_hard_milestones: bool = False,
    max_makespan_days: int | None = None,
    relax_target_constraints: bool = False,
) -> ScheduleResult:
    """Run the full control-priority objective once without a baseline CP-SAT solve."""
    result = solve_control_priority_schedule(
        schedule_input,
        enforce_hard_milestones=enforce_hard_milestones,
        max_makespan_days=max_makespan_days,
        relax_target_constraints=relax_target_constraints,
        _use_baseline=False,
    )
    result.stats.update(
        {
            "solver_call_count": 1,
            "baseline_status": "not_evaluated",
            "performance_path": "ai_strict_fixed_resource_one_pass",
            "resource_expansion_attempted": False,
        }
    )
    result.objective_breakdown.update(
        {
            "solver_call_count": 1,
            "baseline_status": "not_evaluated",
            "performance_path": "ai_strict_fixed_resource_one_pass",
            "resource_expansion_attempted": False,
        }
    )
    analysis = result.stats.get("control_priority_analysis")
    if isinstance(analysis, dict):
        analysis["resource_increment_suggestions"] = []
    return result


def solve_control_priority_schedule(
    schedule_input: ScheduleInput,
    *,
    enforce_hard_milestones: bool = False,
    baseline_result: ScheduleResult | None = None,
    max_makespan_days: int | None = None,
    warm_start_result: ScheduleResult | None = None,
    relax_target_constraints: bool = False,
    _drill_group_stage: str = "auto",
    _fixed_resource_by_task_id: dict[str, str] | None = None,
    _path_task_filter_by_resource: dict[str, set[str]] | None = None,
    _path_filter_task_ids: set[str] | None = None,
    _use_baseline: bool = True,
) -> ScheduleResult:
    started_at = time.perf_counter()
    if baseline_result is None and _use_baseline:
        baseline_result = solve_shortest_duration_schedule(schedule_input)
    if baseline_result is not None and baseline_result.status not in {"OPTIMAL", "FEASIBLE"}:
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
    validation.extend(_execution_constraint_validation(schedule_input, resource_candidates))
    if any(message.level == "error" for message in validation):
        return ScheduleResult(
            status="INFEASIBLE",
            plan_start_date=schedule_input.start_date,
            validation=validation,
            stats={"reason": "missing_compatible_resource", "solve_mode": "control_priority"},
        )

    config = schedule_input.schedule_strategy
    objective_weights = _objective_weights_for_config(config)
    objective_terms_used_payload = _objective_terms_used_for_config(config, objective_weights)
    drill_groups = _build_drill_group_nodes(schedule_input.tasks, resource_candidates, enabled_resources)

    if _drill_group_stage == "auto" and drill_groups:
        coarse_result = solve_control_priority_schedule(
            schedule_input,
            enforce_hard_milestones=enforce_hard_milestones,
            baseline_result=baseline_result,
            max_makespan_days=max_makespan_days,
            warm_start_result=warm_start_result,
            relax_target_constraints=relax_target_constraints,
            _drill_group_stage="coarse",
            _use_baseline=_use_baseline,
        )
        if coarse_result.status not in {"OPTIMAL", "FEASIBLE"}:
            return coarse_result
        return coarse_result

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
    relaxed_hard_lateness_vars: dict[str, Any] = {}
    fixed_duration_overrun_var: Any | None = None
    config = schedule_input.schedule_strategy
    objective_weights = _objective_weights_for_config(config)
    objective_terms_used_payload = _objective_terms_used_for_config(config, objective_weights)
    control_node_late_enabled = _objective_term_enabled(objective_weights, "control_node_late")
    resource_idle_enabled = _objective_term_enabled(objective_weights, "resource_idle")
    drill_group_constraints_enabled = _drill_group_stage in {"coarse", "refined"} and bool(drill_groups)
    drill_group_path_circuit_enabled = False
    inherited_stage1_route_metadata = (
        _stage1_route_metadata_from_path(warm_start_result.stats.get("continuity_objective"))
        if _drill_group_stage == "refined" and warm_start_result is not None
        else _empty_drill_group_stage1_route_terms("not_applicable")["metadata"]
    )
    makespan_objective_enabled = _objective_term_enabled(objective_weights, "makespan_and_soft_milestone")
    control_chain_task_ids = _control_chain_task_ids(schedule_input)
    normal_tasks = _normal_balance_tasks(schedule_input.tasks, control_chain_task_ids)
    normal_resource_groups = _split_normal_tasks_by_resource_configuration(normal_tasks, resource_candidates)

    for task in schedule_input.tasks:
        starts[task.id] = model.NewIntVar(0, horizon, f"start_{_safe(task.id)}")
        ends[task.id] = model.NewIntVar(0, horizon, f"end_{_safe(task.id)}")
        model.Add(ends[task.id] == starts[task.id] + task.duration_days)
    if drill_group_constraints_enabled:
        _add_drill_group_contiguity_constraints(model, starts, ends, drill_groups)

    assignment_vars, resource_intervals = _build_named_resource_assignment_model(
        model,
        starts=starts,
        ends=ends,
        tasks=schedule_input.tasks,
        enabled_resources=enabled_resources,
        resource_candidates=resource_candidates,
        horizon=horizon,
    )
    _add_execution_constraints(model, schedule_input, starts, resource_candidates, assignment_vars)
    continuous_span_model = _add_named_continuous_beam_team_span_constraints(
        model,
        starts=starts,
        ends=ends,
        tasks=schedule_input.tasks,
        enabled_resources=enabled_resources,
        resource_intervals=resource_intervals,
        validation=validation,
        horizon=horizon,
    )
    if _fixed_resource_by_task_id:
        _add_fixed_task_resource_constraints(
            model,
            resource_candidates,
            assignment_vars,
            _fixed_resource_by_task_id,
        )

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
    if drill_group_constraints_enabled:
        _add_drill_group_boundary_precedence_constraints(
            model,
            starts,
            ends,
            drill_groups,
            schedule_input.precedence_links,
        )

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
        if relax_target_constraints:
            overrun_upper = max(horizon - max_makespan_days, horizon) + 365
            fixed_duration_overrun_var = model.NewIntVar(0, overrun_upper, "fixed_duration_overrun")
            model.Add(fixed_duration_overrun_var >= makespan - max_makespan_days)
        else:
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
        if drill_group_constraints_enabled and milestone.mode == "hard":
            scoped_task_ids = _expand_drill_group_scope(scoped_task_ids, drill_groups)
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
        if milestone.mode == "hard":
            if relax_target_constraints:
                lateness_upper = max(horizon - target_offset, horizon) + 365
                lateness_var = model.NewIntVar(0, lateness_upper, f"relaxed_hard_late_{_safe(milestone.id)}")
                model.Add(lateness_var >= event_var - target_offset)
                relaxed_hard_lateness_vars[milestone.id] = lateness_var
            else:
                model.Add(event_var <= target_offset)
        else:
            lateness_upper = max(horizon - target_offset, horizon) + 365
            is_control_soft_milestone = _is_soft_control_milestone(milestone)
            if (is_control_soft_milestone and control_node_late_enabled) or (
                not is_control_soft_milestone and makespan_objective_enabled
            ):
                lateness_var = model.NewIntVar(0, lateness_upper, f"late_{_safe(milestone.id)}")
                model.Add(lateness_var >= event_var - target_offset)
                soft_lateness_vars[milestone.id] = lateness_var

    soft_control_milestone_ids = {
        milestone_id
        for milestone_id in soft_lateness_vars
        if _is_soft_control_milestone(_milestone_by_id(schedule_input.milestones, milestone_id))
    }
    control_lateness_terms = [
        late_var
        for milestone_id, late_var in soft_lateness_vars.items()
        if milestone_id in soft_control_milestone_ids
    ]
    resource_organization_terms = _build_resource_organization_terms(
        model,
        starts,
        ends,
        schedule_input.tasks,
        enabled_resources,
        resource_candidates,
        assignment_vars,
        horizon,
        include_workload_balance=False,
        include_idle=resource_idle_enabled,
        include_path_continuity=drill_group_path_circuit_enabled,
        include_slot_balance=False,
        path_task_filter_by_resource=_path_task_filter_by_resource,
        path_filter_task_ids=_path_filter_task_ids,
    )
    drill_group_stage1_route_terms = _empty_drill_group_stage1_route_terms("not_enabled")
    if _drill_group_stage == "refined":
        drill_group_stage1_route_terms["metadata"] = inherited_stage1_route_metadata
    relaxed_target_terms = list(relaxed_hard_lateness_vars.values())
    if fixed_duration_overrun_var is not None:
        relaxed_target_terms.append(fixed_duration_overrun_var)
    relaxed_target_enabled = relax_target_constraints and bool(relaxed_target_terms)
    relaxed_target_weight = objective_weights["control_node_late"]
    modeled_terms = {
        term_id
        for term_id, enabled in {
            "control_node_late": control_node_late_enabled and bool(control_lateness_terms or relaxed_target_terms),
            "makespan_and_soft_milestone": makespan_objective_enabled,
            "resource_idle": resource_idle_enabled and bool(resource_organization_terms["idle_terms"]),
        }.items()
        if enabled
    }
    objective_modeling_gates = _objective_modeling_gates(
        objective_terms_used_payload,
        modeled_terms=modeled_terms,
    )
    model.Minimize(
        sum(control_lateness_terms) * objective_weights["control_node_late"]
        + sum(relaxed_target_terms) * relaxed_target_weight
        + sum(resource_organization_terms["idle_terms"]) * objective_weights["resource_idle"]
        + makespan * (objective_weights["makespan_and_soft_milestone"] if makespan_objective_enabled else 0)
    )
    warm_start_used = _add_schedule_hints(
        model,
        starts=starts,
        ends=ends,
        assignment_vars=assignment_vars,
        warm_start_result=warm_start_result,
    )

    solver = cp_model.CpSolver()
    model_built_at = time.perf_counter()
    _configure_solver(solver, schedule_input.time_limit_seconds)
    status_code = solver.Solve(model)
    status = _status_name(status_code, cp_model)

    stats = {
        "horizon_days": horizon,
        **_solver_timing_stats(
            started_at,
            solver,
            configured_time_limit_seconds=schedule_input.time_limit_seconds,
            model_built_at=model_built_at,
        ),
        "conflicts": solver.NumConflicts(),
        "branches": solver.NumBranches(),
        "random_seed": SCHEDULER_RANDOM_SEED,
        "search_workers": _scheduler_search_workers(),
        "solve_mode": "control_priority",
        "baseline_objective_days": baseline_result.objective_days if baseline_result is not None else None,
        "baseline_status": baseline_result.status if baseline_result is not None else "not_evaluated",
        "warm_start_used": warm_start_used,
        "relax_target_constraints": relax_target_constraints,
        "objective_modeling_gates": objective_modeling_gates,
    }
    if max_makespan_days is not None:
        stats["max_makespan_days"] = max_makespan_days
    if relax_target_constraints:
        stats["relaxed_target_constraint_count"] = len(relaxed_hard_lateness_vars) + (
            1 if fixed_duration_overrun_var is not None else 0
        )
    stage2_path_diagnostics_by_resource: list[dict[str, Any]] | None = None
    if (
        _drill_group_stage == "refined"
        and drill_groups
        and warm_start_result is not None
        and warm_start_result.status in {"OPTIMAL", "FEASIBLE"}
    ):
        stage2_path_diagnostics_by_resource = _drill_group_stage2_path_diagnostics_by_resource(
            drill_groups,
            warm_start_result.tasks,
            enabled_resources,
        )
        stats["stage2_path_diagnostics_by_resource"] = stage2_path_diagnostics_by_resource
        stats["stage2_path_node_count"] = sum(
            int(item.get("path_node_count") or 0)
            for item in stage2_path_diagnostics_by_resource
        )
        stats["stage2_path_candidate_arc_count"] = sum(
            int(item.get("candidate_transition_arc_count") or 0)
            for item in stage2_path_diagnostics_by_resource
        )
        stats["stage2_coarse_order_violation_count"] = sum(
            int(item.get("coarse_order_violation_count") or 0)
            for item in stage2_path_diagnostics_by_resource
        )

    stage1_route_metadata = dict(drill_group_stage1_route_terms["metadata"])
    if status not in {"OPTIMAL", "FEASIBLE"}:
        if _drill_group_stage == "coarse":
            stage1_route_metadata = _with_stage1_route_failure(
                stage1_route_metadata,
                "stage1_route_infeasible",
            )
        failed_continuity_objective = {
            "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
            "drill_group_adjacent_resource_switch_penalty": 0,
            "drill_group_hole_jump_penalty": 0,
            "stage1_same_side_penalty": 0,
            "stage1_cross_side_penalty": 0,
            "stage1_route_penalty": 0,
            "resource_path_status": "not_evaluated",
            **resource_organization_terms["path_metadata"],
            **stage1_route_metadata,
        }
        stats["continuity_objective"] = failed_continuity_objective
        drill_group_status = "not_applicable"
        if drill_groups:
            drill_group_status = "coarse_infeasible" if _drill_group_stage == "coarse" else "stage2_infeasible"
        drill_group_payload = _drill_group_refinement_payload(
            status=drill_group_status,
            groups=drill_groups,
            scheduled_tasks=[],
            path_metadata=failed_continuity_objective,
            stage2_path_diagnostics_by_resource=stage2_path_diagnostics_by_resource,
        )
        stats["drill_group_refinement"] = drill_group_payload
        failure_messages = [
            ValidationMessage(
                level="error",
                message="控制性工程优先策略在当前工艺、资源、里程碑和工作面约束下未找到可行排程。",
            )
        ]
        if stage1_route_metadata.get("stage1_route_status") == "infeasible":
            failure_messages.append(
                ValidationMessage(
                    level="error",
                    message="第一阶段钻机组路径未找到可行排程，候选路径已按无顺序罚分模式进入模型。",
                )
            )
        return ScheduleResult(
            status=status,
            plan_start_date=schedule_input.start_date,
            milestone_results=_not_evaluated_milestones(schedule_input.milestones),
            validation=validation + failure_messages,
            stats=stats,
            objective_breakdown={
                "objective_weights": objective_weights,
                "objective_terms_used": objective_terms_used_payload,
                "objective_modeling_gates": objective_modeling_gates,
                "continuity_objective": failed_continuity_objective,
                "drill_group_refinement": drill_group_payload,
                "drill_group_refinement_status": drill_group_payload["status"],
            },
        )

    resource_by_id = {resource.id: resource for resource in enabled_resources}
    predecessors_by_successor: dict[str, list[str]] = defaultdict(list)
    for link in schedule_input.precedence_links:
        predecessors_by_successor[link.successor_id].append(link.predecessor_id)

    scheduled_tasks: list[ScheduledTask] = []
    allocations: list[ResourceAllocation] = []
    continuous_span_payload = _continuous_span_result_payload(
        schedule_input=schedule_input,
        span_model=continuous_span_model,
        solver=solver,
    )
    continuous_span_by_task_id = _continuous_span_by_task_id(continuous_span_payload)
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
            **_scheduled_continuous_fields(task, continuous_span_by_task_id),
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
    allocations.extend(_continuous_span_allocations(schedule_input, continuous_span_payload))

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
    soft_milestone_penalty = sum(
        result.penalty
        for result in milestone_results
        if result.mode == "soft" and result.id not in soft_control_milestone_ids
    )
    control_lateness_days = sum(
        result.lateness_days for result in milestone_results if result.id in soft_control_milestone_ids
    )
    relaxed_hard_milestone_lateness_days = sum(
        result.lateness_days for result in milestone_results if result.id in relaxed_hard_lateness_vars
    )
    fixed_duration_overrun_days = (
        solver.Value(fixed_duration_overrun_var) if fixed_duration_overrun_var is not None else 0
    )
    relaxed_target_penalty_days = relaxed_hard_milestone_lateness_days + fixed_duration_overrun_days
    soft_control_lateness_penalty = sum(
        result.lateness_days
        for result in milestone_results
        if result.id in soft_control_milestone_ids
    )
    reported_control_lateness_days = control_lateness_days if control_node_late_enabled else 0
    reported_control_target_lateness_days = (
        reported_control_lateness_days + relaxed_target_penalty_days
        if control_node_late_enabled
        else 0
    )
    reported_soft_control_lateness_penalty = (
        soft_control_lateness_penalty if control_node_late_enabled else 0
    )
    resource_idle_penalty = sum(solver.Value(term) for term in resource_organization_terms["idle_terms"])
    drill_group_adjacent_penalty = 0
    drill_group_hole_penalty = 0
    stage1_same_side_penalty = sum(solver.Value(term) for term in drill_group_stage1_route_terms["same_side_terms"])
    stage1_cross_side_penalty = sum(solver.Value(term) for term in drill_group_stage1_route_terms["cross_side_terms"])
    stage1_route_penalty = stage1_same_side_penalty + stage1_cross_side_penalty
    stage1_route_metadata = {
        **stage1_route_metadata,
        "stage1_same_side_penalty": stage1_same_side_penalty,
        "stage1_cross_side_penalty": stage1_cross_side_penalty,
        "stage1_route_penalty": stage1_route_penalty,
    }
    normal_balance_metrics = _build_normal_balance_metrics(
        scheduled_tasks,
        config,
        normal_task_ids={task.id for task in normal_tasks},
        configured_resource_task_ids={task.id for task in normal_resource_groups["configured"]},
        unconfigured_resource_task_ids={task.id for task in normal_resource_groups["unconfigured"]},
    )
    resource_organization_analysis = _build_resource_organization_analysis(
        scheduled_tasks,
        enabled_resources,
        objective_days=objective_days,
        continuity_metrics=continuity_metrics,
        workload_balance_enabled=False,
        idle_enabled=resource_idle_enabled,
        path_continuity_enabled=drill_group_path_circuit_enabled,
    )
    control_buffer_risks: list[dict[str, Any]] = []
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
        control_buffer_enabled=False,
        path_continuity_enabled=drill_group_path_circuit_enabled,
    )
    stats["continuity_metrics"] = continuity_metrics
    stats["continuity_objective"] = {
        "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
        "drill_group_adjacent_resource_switch_penalty": drill_group_adjacent_penalty,
        "drill_group_hole_jump_penalty": drill_group_hole_penalty,
        "stage1_same_side_penalty": stage1_same_side_penalty,
        "stage1_cross_side_penalty": stage1_cross_side_penalty,
        "stage1_route_penalty": stage1_route_penalty,
        "resource_path_status": "enabled" if drill_group_path_circuit_enabled else "not_evaluated",
        **resource_organization_terms["path_metadata"],
        **stage1_route_metadata,
    }
    drill_group_status = "not_applicable"
    if drill_groups:
        if _drill_group_stage == "refined":
            drill_group_status = "stage2_refined"
        else:
            drill_group_status = "coarse_only"
    drill_group_payload = _drill_group_refinement_payload(
        status=drill_group_status,
        groups=drill_groups,
        scheduled_tasks=scheduled_tasks,
        path_metadata=stats["continuity_objective"],
        stage2_path_diagnostics_by_resource=stage2_path_diagnostics_by_resource,
    )
    stats["drill_group_refinement"] = drill_group_payload
    stats["normal_balance_metrics"] = normal_balance_metrics
    stats["resource_organization_analysis"] = resource_organization_analysis
    stats["control_priority_analysis"] = control_priority_analysis
    stats["objective_modeling_gates"] = objective_modeling_gates
    stats["continuous_beam_team_spans"] = continuous_span_payload
    if relax_target_constraints:
        stats["relaxed_target_constraints"] = {
            "relaxed_hard_milestone_lateness_days": relaxed_hard_milestone_lateness_days,
            "fixed_duration_overrun_days": fixed_duration_overrun_days,
            "penalty_days": relaxed_target_penalty_days,
            "weight": relaxed_target_weight,
        }
    objective_contributions = _objective_contributions_for_result(
        objective_terms_used_payload=objective_terms_used_payload,
        raw_penalties={
            "control_node_late": reported_control_target_lateness_days,
            "makespan_and_soft_milestone": objective_days if makespan_objective_enabled else 0,
            "resource_idle": resource_idle_penalty,
        },
        active_terms={
            term_id: term_id in modeled_terms for term_id in DEFAULT_OBJECTIVE_TERM_WEIGHTS
        },
    )
    weighted_objective = sum(item["weighted_contribution"] for item in objective_contributions)
    validation.append(
        ValidationMessage(
            level="info",
            message=(
                f"控制性工程优先策略已完成：控制链工作项 {len(control_chain_task_ids)} 个，"
                f"普通工程分布评分 {normal_balance_metrics['balance_score']}。"
            ),
        )
    )
    if relax_target_constraints:
        if relaxed_target_penalty_days > 0:
            validation.append(
                ValidationMessage(
                    level="warning",
                    message=(
                        "最佳努力精排已放松强制节点或固定工期目标："
                        f"强制节点迟延合计 {relaxed_hard_milestone_lateness_days} 天，"
                        f"固定工期超期 {fixed_duration_overrun_days} 天。"
                    ),
                )
            )
        else:
            validation.append(
                ValidationMessage(
                    level="info",
                    message="最佳努力精排已按目标放松模式求解，当前结果未产生目标迟延。",
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
            "makespan_days": objective_days,
            "baseline_makespan_days": baseline_result.objective_days if baseline_result is not None else None,
            "control_lateness_days": reported_control_lateness_days,
            "control_target_lateness_days": reported_control_target_lateness_days,
            "relaxed_hard_milestone_lateness_days": relaxed_hard_milestone_lateness_days,
            "fixed_duration_overrun_days": fixed_duration_overrun_days,
            "relaxed_target_penalty_days": relaxed_target_penalty_days,
            "relaxed_target_weight": relaxed_target_weight,
            "relaxed_target_weighted_penalty": relaxed_target_penalty_days * relaxed_target_weight,
            "soft_control_lateness_penalty": reported_soft_control_lateness_penalty,
            "resource_idle_penalty": resource_idle_penalty,
            "drill_group_adjacent_resource_switch_penalty": drill_group_adjacent_penalty,
            "drill_group_hole_jump_penalty": drill_group_hole_penalty,
            "stage1_same_side_penalty": stage1_same_side_penalty,
            "stage1_cross_side_penalty": stage1_cross_side_penalty,
            "stage1_route_penalty": stage1_route_penalty,
            "resource_idle_weight": objective_weights["resource_idle"],
            "soft_milestone_penalty": soft_milestone_penalty,
            "continuity_score": continuity_metrics["continuity_score"],
            "normal_balance_score": normal_balance_metrics["balance_score"],
            "resource_organization_analysis": resource_organization_analysis,
            "weighted_objective": weighted_objective,
            "best_effort_score": weighted_objective if relax_target_constraints else None,
            "relax_target_constraints": relax_target_constraints,
            "objective_weights": objective_weights,
            "objective_terms_used": objective_terms_used_payload,
            "objective_modeling_gates": objective_modeling_gates,
            "objective_contributions": objective_contributions,
            "control_priority_analysis": control_priority_analysis,
            "normal_balance_metrics": normal_balance_metrics,
            "drill_group_refinement": drill_group_payload,
            "drill_group_refinement_status": drill_group_payload["status"],
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


def _split_normal_tasks_by_resource_configuration(
    normal_tasks: list[Task],
    resource_candidates: dict[str, list[Resource]],
) -> dict[str, list[Task]]:
    configured: list[Task] = []
    unconfigured: list[Task] = []
    for task in normal_tasks:
        if resource_candidates.get(task.id):
            configured.append(task)
        else:
            unconfigured.append(task)
    return {
        "configured": configured,
        "unconfigured": unconfigured,
    }


def _normal_balance_bucket_definitions(config: Any, horizon: int) -> list[dict[str, int]]:
    bucket_size = 7 if config.normal_balance_bucket == "week" else 30
    window_start = max(0, int(config.normal_earliest_start_offset or 0))
    latest = config.normal_latest_finish_offset
    window_finish = min(horizon, int(latest)) if latest is not None else horizon
    window_finish = max(window_start + 1, window_finish)
    bucket_count = max(1, math.ceil((window_finish - window_start) / bucket_size))
    return [
        {
            "bucket_index": bucket_index,
            "start_offset": window_start + bucket_index * bucket_size,
            "finish_offset": min(window_finish, window_start + (bucket_index + 1) * bucket_size),
        }
        for bucket_index in range(bucket_count)
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
    include_penalty_terms: bool = True,
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
        if include_penalty_terms:
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
    if metrics.get("unconfigured_resource_normal_task_count", metrics.get("normal_task_count", 0)) <= 0:
        return "not_evaluated"
    score = int(metrics.get("balance_score", 0))
    if score >= 80:
        return "balanced"
    bucket_loads = metrics.get("bucket_loads") or []
    if len(bucket_loads) >= 2:
        first = int(bucket_loads[0].get("duration_days", 0))
        last = int(bucket_loads[-1].get("duration_days", 0))
        peak = int(metrics.get("peak_duration_days", metrics.get("peak_task_count", 0)))
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


def _build_resource_organization_terms(
    model: Any,
    starts: dict[str, Any],
    ends: dict[str, Any],
    tasks: list[Task],
    enabled_resources: list[Resource],
    resource_candidates: dict[str, list[Resource]],
    assignment_vars: dict[tuple[str, str], Any],
    horizon: int,
    *,
    include_workload_balance: bool = True,
    include_idle: bool = True,
    include_path_continuity: bool = True,
    include_slot_balance: bool = True,
    path_task_filter_by_resource: dict[str, set[str]] | None = None,
    path_filter_task_ids: set[str] | None = None,
) -> dict[str, list[Any]]:
    assignments_by_resource: dict[str, list[tuple[Task, Any]]] = defaultdict(list)
    for task in tasks:
        for resource in resource_candidates.get(task.id, []):
            assignment = assignment_vars.get((task.id, resource.id))
            if assignment is not None:
                assignments_by_resource[resource.id].append((task, assignment))

    path_assignments_by_resource = assignments_by_resource
    if path_task_filter_by_resource is not None and path_filter_task_ids:
        filtered: dict[str, list[tuple[Task, Any]]] = defaultdict(list)
        for resource_id, task_assignments in assignments_by_resource.items():
            allowed_task_ids = path_task_filter_by_resource.get(resource_id, set())
            for task, assignment in task_assignments:
                if task.id not in path_filter_task_ids or task.id in allowed_task_ids:
                    filtered[resource_id].append((task, assignment))
        path_assignments_by_resource = filtered

    empty_path_terms = _empty_resource_path_terms(path_assignments_by_resource)
    if not (include_workload_balance or include_idle or include_path_continuity or include_slot_balance):
        return {
            "workload_balance_terms": [],
            "idle_terms": [],
            "path_terms": [],
            "slot_balance_terms": [],
            "path_group_terms": [],
            "spatial_gap_terms": [],
            "same_side_gap_terms": [],
            "side_switch_terms": [],
            "path_metadata": empty_path_terms["path_metadata"],
        }

    resources_with_assignments = [
        resource for resource in sorted(enabled_resources, key=_resource_sort_key) if assignments_by_resource.get(resource.id)
    ]
    resources_by_type: dict[str, list[Resource]] = defaultdict(list)
    workload_by_resource: dict[str, Any] = {}
    used_by_resource: dict[str, Any] = {}
    idle_terms: list[Any] = []
    needs_workload = include_workload_balance or include_idle
    needs_used = include_idle or include_path_continuity or include_slot_balance

    for resource in resources_with_assignments:
        task_assignments = assignments_by_resource[resource.id]
        assignment_bools = [assignment for _, assignment in task_assignments]
        total_work = sum(task.duration_days for task, _ in task_assignments)
        workload = None
        if needs_workload:
            workload = model.NewIntVar(0, total_work, f"resource_workload_{_safe(resource.id)}")
            model.Add(workload == sum(task.duration_days * assignment for task, assignment in task_assignments))
            workload_by_resource[resource.id] = workload
            if include_workload_balance:
                resources_by_type[resource.type].append(resource)

        used = None
        if needs_used:
            used = model.NewBoolVar(f"resource_used_{_safe(resource.id)}")
            for assignment in assignment_bools:
                model.Add(assignment <= used)
            model.Add(sum(assignment_bools) >= used)
            used_by_resource[resource.id] = used

        if include_idle and workload is not None and used is not None:
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
            idle_terms.append(idle_days)

    workload_balance_terms: list[Any] = []
    if include_workload_balance:
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

    path_terms = (
        _build_resource_path_diagnostic_terms(
            model,
            path_assignments_by_resource,
            enabled_resources,
            used_by_resource,
            starts,
            ends,
            horizon,
            include_slot_balance=include_slot_balance,
        )
        if include_path_continuity
        else empty_path_terms
    )

    return {
        "workload_balance_terms": workload_balance_terms,
        "idle_terms": idle_terms,
        "path_terms": path_terms["path_terms"],
        "slot_balance_terms": path_terms["slot_balance_terms"],
        "path_group_terms": path_terms["path_group_terms"],
        "spatial_gap_terms": path_terms["spatial_gap_terms"],
        "same_side_gap_terms": path_terms["same_side_gap_terms"],
        "side_switch_terms": path_terms["side_switch_terms"],
        "path_metadata": path_terms["path_metadata"],
    }


def _empty_resource_path_terms(
    assignments_by_resource: dict[str, list[tuple[Task, Any]]] | None = None,
) -> dict[str, Any]:
    assignments_by_resource = assignments_by_resource or {}
    return {
        "path_terms": [],
        "path_group_terms": [],
        "spatial_gap_terms": [],
        "same_side_gap_terms": [],
        "side_switch_terms": [],
        "slot_balance_terms": [],
        "path_metadata": {
            "resource_path_granularity_counts": {
                "task": 0,
                "same_structure": 0,
                "same_structure_slot": 0,
            },
            "resource_path_node_count": 0,
            "resource_path_transition_arc_count": 0,
            "resource_path_task_candidate_count": sum(len(items) for items in assignments_by_resource.values()),
            "slot_balance_term_count": 0,
            "resource_path_sparse_support_window": MECHANICAL_DRILL_PATH_SUPPORT_WINDOW,
            "resource_path_sparse_same_side_window": MECHANICAL_DRILL_PATH_SUPPORT_WINDOW,
            "resource_path_sparse_cross_side_window": MECHANICAL_DRILL_CROSS_SIDE_SUPPORT_WINDOW,
        },
    }


def _build_resource_path_diagnostic_terms(
    model: Any,
    assignments_by_resource: dict[str, list[tuple[Task, Any]]],
    enabled_resources: list[Resource],
    used_by_resource: dict[str, Any],
    starts: dict[str, Any],
    ends: dict[str, Any],
    horizon: int,
    *,
    include_slot_balance: bool = True,
) -> dict[str, Any]:
    same_side_gap_terms: list[Any] = []
    side_switch_terms: list[Any] = []
    slot_balance_terms: list[Any] = []
    resources_by_id = {resource.id: resource for resource in enabled_resources}
    limits_by_group_key = _resource_path_parallel_limits_by_group(enabled_resources)
    metadata: dict[str, Any] = {
        "resource_path_granularity_counts": {
            "task": 0,
            "same_structure": 0,
            "same_structure_slot": 0,
        },
        "resource_path_node_count": 0,
        "resource_path_transition_arc_count": 0,
        "resource_path_task_candidate_count": sum(len(items) for items in assignments_by_resource.values()),
        "resource_path_sparse_support_window": MECHANICAL_DRILL_PATH_SUPPORT_WINDOW,
        "resource_path_sparse_same_side_window": MECHANICAL_DRILL_PATH_SUPPORT_WINDOW,
        "resource_path_sparse_cross_side_window": MECHANICAL_DRILL_CROSS_SIDE_SUPPORT_WINDOW,
    }

    for resource_id, task_assignments in assignments_by_resource.items():
        resource = resources_by_id.get(resource_id)
        resource_used = used_by_resource.get(resource_id)
        if resource is None or resource_used is None:
            continue

        nodes = _resource_path_nodes_for_resource(
            model,
            resource,
            task_assignments,
            limits_by_group_key,
            starts,
            ends,
            horizon,
        )
        for node in nodes:
            metadata["resource_path_granularity_counts"][node["granularity"]] += 1
        metadata["resource_path_node_count"] += len(nodes)
        if len(nodes) <= 1:
            continue

        indexed_assignments = list(enumerate(nodes, start=1))
        arcs = [(0, 0, resource_used.Not())]
        for node_index, node in indexed_assignments:
            arcs.append((node_index, node_index, node["presence"].Not()))
            arcs.append((0, node_index, model.NewBoolVar(f"resource_path_start_{_safe(resource_id)}_{node_index}")))
            arcs.append((node_index, 0, model.NewBoolVar(f"resource_path_end_{_safe(resource_id)}_{node_index}")))

        allowed_transition_pairs = _resource_path_allowed_transition_pairs(resource, indexed_assignments)
        for previous_index, previous_node in indexed_assignments:
            for current_index, current_node in indexed_assignments:
                if (previous_index, current_index) not in allowed_transition_pairs:
                    continue
                transition = model.NewBoolVar(
                    f"resource_path_arc_{_safe(resource_id)}_{previous_index}_{current_index}"
                )
                arcs.append((previous_index, current_index, transition))
                metadata["resource_path_transition_arc_count"] += 1
                model.Add(current_node["start"] >= previous_node["end"]).OnlyEnforceIf(transition)

        model.AddCircuit(arcs)

    slot_balance_terms = (
        _build_same_structure_slot_balance_terms(
            model,
            assignments_by_resource,
            resources_by_id,
            limits_by_group_key,
        )
        if include_slot_balance
        else []
    )
    metadata["slot_balance_term_count"] = len(slot_balance_terms)

    return {
        "path_terms": same_side_gap_terms + side_switch_terms + slot_balance_terms,
        "path_group_terms": [],
        "spatial_gap_terms": [],
        "same_side_gap_terms": same_side_gap_terms,
        "side_switch_terms": side_switch_terms,
        "slot_balance_terms": slot_balance_terms,
        "path_metadata": metadata,
    }


def _resource_path_parallel_limits_by_group(resources: list[Resource]) -> dict[str, int]:
    resources_by_group: dict[str, list[Resource]] = defaultdict(list)
    for resource in resources:
        resources_by_group[_resource_parallel_group_key(resource)].append(resource)
    limits: dict[str, int] = {}
    for group_key, group_resources in resources_by_group.items():
        if group_resources and all(
            resource.type in MECHANICAL_DRILL_RESOURCE_TYPES for resource in group_resources
        ):
            limits[group_key] = 1
            continue
        if (limit := _effective_same_structure_resource_binding_limit(group_resources)) is not None:
            limits[group_key] = limit
    return limits


def _resource_path_granularity(resource: Resource, limits_by_group_key: dict[str, int]) -> tuple[str, int | None]:
    limit = limits_by_group_key.get(_resource_parallel_group_key(resource))
    if limit is None:
        return "task", None
    if limit <= 1:
        return "same_structure", limit
    return "same_structure_slot", limit


def _resource_path_nodes_for_resource(
    model: Any,
    resource: Resource,
    task_assignments: list[tuple[Task, Any]],
    limits_by_group_key: dict[str, int],
    starts: dict[str, Any],
    ends: dict[str, Any],
    horizon: int,
) -> list[dict[str, Any]]:
    granularity, _ = _resource_path_granularity(resource, limits_by_group_key)
    if granularity == "task":
        return [
            {
                "presence": assignment,
                "start": starts[task.id],
                "end": ends[task.id],
                "representative_task": task,
                "granularity": "task",
            }
            for task, assignment in task_assignments
        ]

    group_key = _resource_parallel_group_key(resource)
    grouped: dict[tuple[str, str, str, str], list[tuple[Task, Any]]] = defaultdict(list)
    for task, assignment in task_assignments:
        grouped[_same_structure_resource_rule_key(task, group_key)].append((task, assignment))

    nodes: list[dict[str, Any]] = []
    for index, grouped_assignments in enumerate(grouped.values()):
        representative_task = min(grouped_assignments, key=lambda item: (item[0].sequence_order, item[0].id))[0]
        assignments = [assignment for _, assignment in grouped_assignments]
        if len(assignments) == 1:
            task, assignment = grouped_assignments[0]
            presence = assignment
            node_start = starts[task.id]
            node_end = ends[task.id]
        else:
            presence = model.NewBoolVar(f"resource_path_group_present_{_safe(resource.id)}_{index}")
            for assignment in assignments:
                model.Add(assignment <= presence)
            model.Add(sum(assignments) >= presence)

            start_candidates = []
            end_candidates = []
            for task_index, (task, assignment) in enumerate(grouped_assignments):
                start_candidate = model.NewIntVar(
                    0,
                    horizon,
                    f"resource_path_group_start_candidate_{_safe(resource.id)}_{index}_{task_index}",
                )
                end_candidate = model.NewIntVar(
                    0,
                    horizon,
                    f"resource_path_group_end_candidate_{_safe(resource.id)}_{index}_{task_index}",
                )
                model.Add(start_candidate == starts[task.id]).OnlyEnforceIf(assignment)
                model.Add(start_candidate == horizon).OnlyEnforceIf(assignment.Not())
                model.Add(end_candidate == ends[task.id]).OnlyEnforceIf(assignment)
                model.Add(end_candidate == 0).OnlyEnforceIf(assignment.Not())
                start_candidates.append(start_candidate)
                end_candidates.append(end_candidate)

            node_start = model.NewIntVar(0, horizon, f"resource_path_group_start_{_safe(resource.id)}_{index}")
            node_end = model.NewIntVar(0, horizon, f"resource_path_group_end_{_safe(resource.id)}_{index}")
            model.AddMinEquality(node_start, start_candidates)
            model.AddMaxEquality(node_end, end_candidates)

        nodes.append(
            {
                "presence": presence,
                "start": node_start,
                "end": node_end,
                "representative_task": representative_task,
                "granularity": granularity,
            }
        )
    return nodes


def _build_same_structure_slot_balance_terms(
    model: Any,
    assignments_by_resource: dict[str, list[tuple[Task, Any]]],
    resources_by_id: dict[str, Resource],
    limits_by_group_key: dict[str, int],
) -> list[Any]:
    grouped: dict[tuple[str, str, str, str], dict[str, list[tuple[Task, Any]]]] = defaultdict(lambda: defaultdict(list))
    for resource_id, task_assignments in assignments_by_resource.items():
        resource = resources_by_id.get(resource_id)
        if resource is None:
            continue
        group_key = _resource_parallel_group_key(resource)
        limit = limits_by_group_key.get(group_key)
        if limit is None or limit <= 1:
            continue
        for task, assignment in task_assignments:
            grouped[_same_structure_resource_rule_key(task, group_key)][resource_id].append((task, assignment))

    terms: list[Any] = []
    for group_index, resources in enumerate(grouped.values()):
        if len(resources) <= 1:
            continue
        unique_task_ids = {task.id for assignments in resources.values() for task, _ in assignments}
        if len(unique_task_ids) <= 1:
            continue
        task_duration_by_id = {
            task.id: task.duration_days
            for assignments in resources.values()
            for task, _ in assignments
        }
        total_work = sum(task_duration_by_id[task_id] for task_id in unique_task_ids)
        workloads: dict[str, Any] = {}
        selected_by_resource: dict[str, Any] = {}
        for resource_id, assignments in sorted(resources.items()):
            workload = model.NewIntVar(0, total_work, f"same_structure_slot_workload_{group_index}_{_safe(resource_id)}")
            model.Add(workload == sum(task.duration_days * assignment for task, assignment in assignments))
            selected = model.NewBoolVar(f"same_structure_slot_selected_{group_index}_{_safe(resource_id)}")
            assignment_bools = [assignment for _, assignment in assignments]
            for assignment in assignment_bools:
                model.Add(assignment <= selected)
            model.Add(sum(assignment_bools) >= selected)
            workloads[resource_id] = workload
            selected_by_resource[resource_id] = selected

        resource_ids = sorted(workloads)
        for previous_index, previous_resource_id in enumerate(resource_ids):
            for current_index, current_resource_id in enumerate(resource_ids[previous_index + 1:], start=previous_index + 1):
                both_selected = model.NewBoolVar(
                    f"same_structure_slot_pair_selected_{group_index}_{_safe(previous_resource_id)}_{_safe(current_resource_id)}"
                )
                model.AddImplication(both_selected, selected_by_resource[previous_resource_id])
                model.AddImplication(both_selected, selected_by_resource[current_resource_id])
                model.AddBoolOr(
                    [
                        selected_by_resource[previous_resource_id].Not(),
                        selected_by_resource[current_resource_id].Not(),
                        both_selected,
                    ]
                )
                difference = model.NewIntVar(
                    0,
                    total_work,
                    f"same_structure_slot_diff_{group_index}_{previous_index}_{current_index}",
                )
                model.AddAbsEquality(difference, workloads[previous_resource_id] - workloads[current_resource_id])
                active_difference = model.NewIntVar(
                    0,
                    total_work,
                    f"same_structure_slot_active_diff_{group_index}_{previous_index}_{current_index}",
                )
                model.Add(active_difference == difference).OnlyEnforceIf(both_selected)
                model.Add(active_difference == 0).OnlyEnforceIf(both_selected.Not())
                terms.append(active_difference)
    return terms


def _resource_path_allowed_transition_pairs(
    resource: Resource,
    indexed_nodes: list[tuple[int, dict[str, Any]]],
) -> set[tuple[int, int]]:
    all_pairs = {
        (previous_index, current_index)
        for previous_index, _ in indexed_nodes
        for current_index, _ in indexed_nodes
        if previous_index != current_index
    }
    if resource.type not in MECHANICAL_DRILL_RESOURCE_TYPES:
        return all_pairs

    node_by_index = {node_index: node for node_index, node in indexed_nodes}
    visible_support_context = _resource_path_visible_support_context(indexed_nodes)
    allowed_pairs = {
        (previous_index, current_index)
        for previous_index, current_index in all_pairs
        if _resource_path_transition_candidate_allowed(
            resource,
            node_by_index[previous_index],
            node_by_index[current_index],
            visible_support_context,
        )
    }
    return allowed_pairs


def _resource_path_visible_support_context(
    indexed_nodes: list[tuple[int, dict[str, Any]]],
) -> dict[str, dict[tuple[Any, ...], dict[int, int]]]:
    same_side_supports: dict[tuple[Any, ...], set[int]] = defaultdict(set)
    cross_side_supports: dict[tuple[Any, ...], set[int]] = defaultdict(set)
    for _, node in indexed_nodes:
        task = node["representative_task"]
        location = _task_location(task)
        support_index = location["support_index"]
        if location["structure_type"] != "pier" or support_index is None:
            continue
        side = location["side"] or "N"
        base_key = (task.bridge_id or "", task.component_type, task.process_name)
        same_side_supports[(*base_key, side)].add(support_index)
        if side in {"L", "R"}:
            cross_side_supports[base_key].add(support_index)

    return {
        "same_side": {
            key: {support_index: position for position, support_index in enumerate(sorted(supports))}
            for key, supports in same_side_supports.items()
        },
        "cross_side": {
            key: {support_index: position for position, support_index in enumerate(sorted(supports))}
            for key, supports in cross_side_supports.items()
        },
    }


def _visible_support_distance(
    positions_by_key: dict[tuple[Any, ...], dict[int, int]],
    key: tuple[Any, ...],
    previous_support_index: int,
    current_support_index: int,
) -> int:
    positions = positions_by_key.get(key)
    if not positions:
        return abs(current_support_index - previous_support_index)
    previous_position = positions.get(previous_support_index)
    current_position = positions.get(current_support_index)
    if previous_position is None or current_position is None:
        return abs(current_support_index - previous_support_index)
    return abs(current_position - previous_position)


def _resource_path_transition_candidate_allowed(
    resource: Resource,
    previous_node: dict[str, Any],
    current_node: dict[str, Any],
    visible_support_context: dict[str, dict[tuple[Any, ...], dict[int, int]]],
) -> bool:
    previous_task = previous_node["representative_task"]
    current_task = current_node["representative_task"]
    previous_location = _task_location(previous_task)
    current_location = _task_location(current_task)
    if (
        previous_location["structure_type"] != "pier"
        or current_location["structure_type"] != "pier"
        or previous_location["support_index"] is None
        or current_location["support_index"] is None
    ):
        return True
    if previous_task.bridge_id != current_task.bridge_id:
        return False
    if previous_task.component_type != current_task.component_type:
        return False
    if previous_task.process_name != current_task.process_name:
        return False

    previous_side = previous_location["side"] or "N"
    current_side = current_location["side"] or "N"
    previous_support_index = previous_location["support_index"]
    current_support_index = current_location["support_index"]
    base_key = (previous_task.bridge_id or "", previous_task.component_type, previous_task.process_name)
    if previous_side == current_side:
        same_side_distance = _visible_support_distance(
            visible_support_context["same_side"],
            (*base_key, previous_side),
            previous_support_index,
            current_support_index,
        )
        return 0 < same_side_distance <= MECHANICAL_DRILL_PATH_SUPPORT_WINDOW
    if previous_side in {"L", "R"} and current_side in {"L", "R"}:
        cross_side_gap = abs(current_support_index - previous_support_index)
        return cross_side_gap <= MECHANICAL_DRILL_CROSS_SIDE_SUPPORT_WINDOW
    return False


def _resource_path_transition_penalties(previous_task: Task, current_task: Task) -> tuple[int, int]:
    previous_location = _task_location(previous_task)
    current_location = _task_location(current_task)
    previous_side = previous_location["side"]
    current_side = current_location["side"]

    side_switch_penalty = (
        1
        if previous_side in {"L", "R"} and current_side in {"L", "R"} and previous_side != current_side
        else 0
    )
    same_side_gap_penalty = 0
    if (
        previous_task.bridge_id == current_task.bridge_id
        and previous_side in {"L", "R"}
        and previous_side == current_side
        and previous_location["support_index"] is not None
        and current_location["support_index"] is not None
    ):
        support_gap = abs(current_location["support_index"] - previous_location["support_index"])
        same_side_gap_penalty = support_gap
    return same_side_gap_penalty, side_switch_penalty


def _is_control_milestone(milestone: MilestoneConstraint) -> bool:
    return milestone.level == "control" or milestone.mode == "hard" or bool(milestone.related_structure_ids)


def _is_soft_control_milestone(milestone: MilestoneConstraint) -> bool:
    return milestone.mode == "soft" and (milestone.level == "control" or bool(milestone.related_structure_ids))


def _is_control_milestone_result(milestone: MilestoneResult) -> bool:
    return milestone.level == "control" or milestone.mode == "hard"


def _build_normal_balance_metrics(
    scheduled_tasks: list[ScheduledTask],
    config: Any,
    *,
    normal_task_ids: set[str] | None = None,
    configured_resource_task_ids: set[str] | None = None,
    unconfigured_resource_task_ids: set[str] | None = None,
    bucket_definitions: list[dict[str, int]] | None = None,
    balance_penalty: int | None = None,
    balance_weight: int = 0,
) -> dict[str, Any]:
    normal_tasks = [
        task
        for task in scheduled_tasks
        if task.control_level == "normal" and (normal_task_ids is None or task.id in normal_task_ids)
    ]
    if configured_resource_task_ids is None:
        configured_resource_task_ids = {task.id for task in normal_tasks if task.assigned_resource_id}
    if unconfigured_resource_task_ids is None:
        unconfigured_resource_task_ids = {task.id for task in normal_tasks if not task.assigned_resource_id}

    configured_tasks = [task for task in normal_tasks if task.id in configured_resource_task_ids]
    unconfigured_tasks = [task for task in normal_tasks if task.id in unconfigured_resource_task_ids]
    bucket_size = 7 if config.normal_balance_bucket == "week" else 30
    bucket_definitions = bucket_definitions or _normal_balance_bucket_definitions(
        config,
        max((task.end_offset for task in scheduled_tasks), default=bucket_size),
    )
    total_workload = sum(task.duration_days for task in unconfigured_tasks)
    bucket_count = len(bucket_definitions)
    ideal_floor = total_workload // bucket_count if bucket_count else 0
    ideal_ceiling = math.ceil(total_workload / bucket_count) if bucket_count else 0
    bucket_loads = []
    task_counts = []
    duration_loads = []
    for bucket in bucket_definitions:
        bucket_tasks = [
            task
            for task in unconfigured_tasks
            if bucket["start_offset"] <= task.start_offset < bucket["finish_offset"]
        ]
        count = len(bucket_tasks)
        duration_days = sum(task.duration_days for task in bucket_tasks)
        deviation_days = max(0, duration_days - ideal_ceiling, ideal_floor - duration_days)
        task_counts.append(count)
        duration_loads.append(duration_days)
        bucket_loads.append(
            {
                "bucket_index": bucket["bucket_index"],
                "start_offset": bucket["start_offset"],
                "finish_offset": bucket["finish_offset"],
                "task_count": count,
                "duration_days": duration_days,
                "ideal_workload_floor_days": ideal_floor,
                "ideal_workload_ceiling_days": ideal_ceiling,
                "deviation_days": deviation_days,
                "task_ids": [task.id for task in sorted(bucket_tasks, key=lambda item: (item.start_offset, item.id))],
                "resource_types": sorted({task.assigned_resource_type or "" for task in bucket_tasks if task.assigned_resource_type}),
            }
        )

    peak_task_count = max(task_counts, default=0)
    min_task_count = min(task_counts, default=0)
    peak_duration = max(duration_loads, default=0)
    min_duration = min(duration_loads, default=0)
    diagnostic_balance_penalty = (
        sum(int(bucket["deviation_days"]) for bucket in bucket_loads)
        if balance_penalty is None
        else int(balance_penalty)
    )
    score = 100 if not unconfigured_tasks else max(0, 100 - diagnostic_balance_penalty * 10)
    return {
        "bucket": config.normal_balance_bucket,
        "bucket_size_days": bucket_size,
        "normal_task_count": len(normal_tasks),
        "configured_resource_normal_task_count": len(configured_tasks),
        "unconfigured_resource_normal_task_count": len(unconfigured_tasks),
        "bucket_loads": bucket_loads if unconfigured_tasks else [],
        "peak_task_count": peak_task_count,
        "min_task_count": min_task_count,
        "peak_duration_days": peak_duration,
        "min_duration_days": min_duration,
        "total_unconfigured_workload_days": total_workload,
        "ideal_workload_floor_days": ideal_floor,
        "ideal_workload_ceiling_days": ideal_ceiling,
        "balance_penalty": diagnostic_balance_penalty,
        "balance_weight": balance_weight,
        "balance_score": score,
        "metric_scope": "unconfigured_resource_normal_work",
    }


def _build_resource_organization_analysis(
    scheduled_tasks: list[ScheduledTask],
    enabled_resources: list[Resource],
    *,
    objective_days: int | None,
    continuity_metrics: dict[str, Any],
    workload_balance_enabled: bool = True,
    idle_enabled: bool = True,
    path_continuity_enabled: bool = True,
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
        balance_status = (
            _resource_workload_balance_status(
                resource_count=len(resources),
                used_resource_count=len(used),
                average_workload=average_workload,
                workload_range=workload_range,
            )
            if workload_balance_enabled
            else "not_evaluated"
        )
        idle_status = _resource_idle_status(resources) if idle_enabled else "not_evaluated"
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
                "jump_pier_count": sum(int(item["jump_pier_count"]) for item in resources) if path_continuity_enabled else 0,
                "side_switch_count": sum(int(item["side_switch_count"]) for item in resources) if path_continuity_enabled else 0,
                "path_group_switch_count": sum(int(item["path_group_switch_count"]) for item in resources)
                if path_continuity_enabled
                else 0,
                "balance_status": balance_status,
                "idle_status": idle_status,
            }
        )

    return {
        "resource_count": len(resource_items),
        "used_resource_count": sum(1 for item in resource_items if int(item["active_days"]) > 0),
        "resource_balance_status": _worst_resource_status(balance_statuses) if workload_balance_enabled else "not_evaluated",
        "resource_idle_status": _worst_resource_status(idle_statuses) if idle_enabled else "not_evaluated",
        "resource_path_status": _resource_path_status(continuity_metrics) if path_continuity_enabled else "not_evaluated",
        "workload_balance_enabled": workload_balance_enabled,
        "idle_enabled": idle_enabled,
        "path_continuity_enabled": path_continuity_enabled,
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
    baseline_result: ScheduleResult | None,
    scheduled_tasks: list[ScheduledTask],
    allocations: list[ResourceAllocation],
    milestone_results: list[MilestoneResult],
    control_chain_task_ids: set[str],
    control_buffer_risks: list[dict[str, Any]],
    continuity_metrics: dict[str, Any],
    normal_balance_metrics: dict[str, Any],
    resource_organization_analysis: dict[str, Any],
    control_buffer_enabled: bool = True,
    path_continuity_enabled: bool = True,
) -> dict[str, Any]:
    baseline_by_id = {task.id: task for task in baseline_result.tasks} if baseline_result is not None else {}
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
        "control_buffer_risks": control_buffer_risks[:50] if control_buffer_enabled else [],
        "control_buffer_status": _control_buffer_status(control_buffer_risks) if control_buffer_enabled else "not_evaluated",
        "normal_balance_status": _normal_balance_status(normal_balance_metrics),
        "resource_path_status": _resource_path_status(continuity_metrics)
        if path_continuity_enabled
        else "not_evaluated",
        "resource_balance_status": resource_organization_analysis.get("resource_balance_status", "not_evaluated"),
        "resource_idle_status": resource_organization_analysis.get("resource_idle_status", "not_evaluated"),
        "resource_organization_analysis": resource_organization_analysis,
        "path_group_diagnostics": continuity_metrics.get("path_group_diagnostics", [])[:50],
        "milestones": milestone_summaries,
        "bottleneck_resources": bottlenecks[:10],
        "resource_increment_suggestions": resource_increment_suggestions,
        "adjustment_explanations": explanations,
        "baseline_objective_days": baseline_result.objective_days if baseline_result is not None else None,
        "baseline_finish_date": baseline_result.plan_finish_date if baseline_result is not None else None,
        "strategy_task_finish_delta_days": (
            max((task.end_offset for task in scheduled_tasks), default=0)
            - (baseline_result.objective_days or 0)
        ) if baseline_result is not None else None,
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


def solve_min_resources_schedule(
    schedule_input: ScheduleInput,
    fallback_target_days: int | None = None,
    minimum_resource_counts: dict[str, int] | None = None,
    verify_with_full_objective: bool = True,
) -> ScheduleResult:
    def new_budget() -> _SolveBudget:
        return _SolveBudget(schedule_input.time_limit_seconds)

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
    minimum_counts = _normalized_minimum_resource_counts(groups, minimum_resource_counts)
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

    max_resource_precheck_budget = new_budget()
    max_resource_hard_precheck = _solve_capacity_model(
        max_resource_precheck_budget.with_time_limit(schedule_input),
        cp_model=cp_model,
        groups=groups,
        counts={group["key"]: group["max_quantity"] for group in groups},
        fallback_target_days=target_days if hard_match_count == 0 else None,
        enforce_fixed_duration=True,
    )
    if max_resource_hard_precheck["status"] == "UNKNOWN" or max_resource_precheck_budget.exhausted():
        result = ScheduleResult(
            status="UNKNOWN",
            plan_start_date=schedule_input.start_date,
            milestone_results=_not_evaluated_milestones(schedule_input.milestones),
            validation=validation + max_resource_hard_precheck["validation"],
            stats={**max_resource_hard_precheck["stats"]},
            objective_breakdown={},
        )
        _annotate_target_achievement(
            result,
            evaluated_at_source="max_resources",
            forced_status="unconfirmed",
            fixed_duration_target=target_days,
            time_budget_seconds=max_resource_precheck_budget.time_limit_seconds,
            time_budget_exhausted=True,
        )
        metadata = {
            "solve_mode": "min_resources_fixed_duration",
            "target_days": target_days,
            "schedule_source": "target_unconfirmed",
            "recommended_schedule_source": "target_unconfirmed",
            "resource_recommendation_status": "unconfirmed",
            "resource_recommendation_message": "最大资源硬里程碑快速预检在限定时间内无法确认，未判断资源上限不足。",
            "max_resource_precheck_mode": "hard_milestone_fast",
            "capacity_precheck_status": max_resource_hard_precheck["status"],
        }
        result.stats.update(metadata)
        result.objective_breakdown.update(metadata)
        return result
    if max_resource_hard_precheck["status"] in {"INFEASIBLE", "MODEL_INVALID"}:
        critical_path = _critical_path_schedule(schedule_input)
        capacity_window_days = _capacity_window_days(schedule_input, target_days)
        result = _fixed_duration_infeasible_result(
            schedule_input=schedule_input,
            checked=max_resource_hard_precheck,
            critical_path=critical_path,
            validation=validation,
            groups=groups,
            target_days=target_days,
            capacity_window_days=capacity_window_days,
        )
        _annotate_target_achievement(
            result,
            evaluated_at_source="max_resources",
            forced_status="max_resources_target_failed"
            if max_resource_hard_precheck["status"] == "INFEASIBLE"
            else "physical_infeasible",
            fixed_duration_target=target_days,
            time_budget_seconds=max_resource_precheck_budget.time_limit_seconds,
            time_budget_exhausted=max_resource_precheck_budget.exhausted(),
        )
        metadata = {
            "solve_mode": "min_resources_fixed_duration",
            "target_days": target_days,
            "schedule_source": result.stats["target_achievement"]["target_status"],
            "recommended_schedule_source": result.stats["target_achievement"]["target_status"],
            "resource_recommendation_status": result.stats["target_achievement"]["target_status"],
            "resource_recommendation_message": "当前最大资源硬里程碑快速预检未满足硬里程碑或固定工期目标。",
            "max_resource_precheck_mode": "hard_milestone_fast",
            "capacity_precheck_status": max_resource_hard_precheck["status"],
        }
        result.stats.update(metadata)
        result.objective_breakdown.update(metadata)
        return result
    fixed_duration_check = max_resource_hard_precheck

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

    global_capacity_budget = new_budget()
    global_capacity_optimization = _solve_capacity_model(
        global_capacity_budget.with_time_limit(schedule_input),
        cp_model=cp_model,
        groups=groups,
        counts=None,
        minimum_resource_counts=minimum_counts,
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
        fallback_budget = new_budget()
        capacity_optimization = _solve_min_resource_counts_by_group_fallback(
            fallback_budget.with_time_limit(schedule_input),
            cp_model=cp_model,
            groups=groups,
            minimum_resource_counts=minimum_counts,
            fixed_duration_check=fixed_duration_check,
            fallback_target_days=target_days if hard_match_count == 0 else None,
            budget=fallback_budget,
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
                "minimum_resource_counts": minimum_counts,
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
    if not verify_with_full_objective:
        selected_source = "capacity_model_verified_schedule" if capacity_verified else "capacity_model_unverified"
        result = capacity_result.model_copy(deep=True)
        if not capacity_verified:
            result.status = "INFEASIBLE"
        metadata = {
            "solve_mode": "min_resources_fixed_duration",
            "target_days": target_days,
            "minimum_resource_counts": minimum_counts,
            "recommended_resource_counts": recommended,
            "resource_optimization_phases": phase_stats,
            "schedule_source": selected_source,
            "recommended_schedule_source": selected_source,
            "capacity_model_status": capacity_optimization["status"],
            "global_capacity_model_status": global_capacity_optimization["status"],
            "capacity_model_group_counts": fixed_counts,
            "capacity_model_stats": capacity_optimization["stats"],
            "independent_solve_time_limit_seconds": TARGET_SOLVE_TIME_LIMIT_SECONDS,
            "max_resource_precheck_mode": "hard_milestone_fast",
            "capacity_precheck_status": fixed_duration_check["status"],
            "capacity_verification_status": "verified" if capacity_verified else "failed",
            "balanced_reoptimization_status": "not_run",
            "unbalanced_reoptimization_status": "not_run",
            "reoptimization_attempts": [],
            "parallel_reoptimization_used": False,
            "resource_count_optimality": "optimal" if capacity_optimization["status"] == "OPTIMAL" else "feasible",
            "capacity_model_role": "internal_candidate_search",
            "capacity_model_retention_reason": (
                "保留为固定工期最大资源硬里程碑快速预检和候选资源数量搜索的内部加速器；业务结论仍以快速预检状态和候选复排的 target_achievement 为准。"
            ),
            "full_objective_verification_skipped": True,
        }
        result.stats.update(metadata)
        result.objective_breakdown.update(metadata)
        _annotate_target_achievement(
            result,
            evaluated_at_source="candidate_resources",
            forced_status="unconfirmed" if capacity_verified else "candidate_resources_target_failed",
            fixed_duration_target=target_days,
            time_budget_seconds=TARGET_SOLVE_TIME_LIMIT_SECONDS,
            time_budget_exhausted=False,
        )
        return result

    reoptimization_budget = new_budget()
    reoptimization_attempts = _run_min_resource_reoptimizations(
        reoptimization_budget.with_time_limit(schedule_input),
        fixed_counts,
        target_days=target_days,
        hard_match_count=hard_match_count,
        capacity_hint_result=capacity_result,
        budget=reoptimization_budget,
    )
    selected_attempt = _select_verified_reoptimization(
        reoptimization_attempts,
        target_days=target_days,
        hard_match_count=hard_match_count,
    )
    best_effort_metadata: dict[str, Any] | None = None

    if selected_attempt is not None:
        result = selected_attempt["result"].model_copy(deep=True)
        selected_source = selected_attempt["source"]
        result.validation = validation + capacity_optimization["validation"] + result.validation
        target_time_budget_seconds = float(selected_attempt.get("time_limit_seconds") or TARGET_SOLVE_TIME_LIMIT_SECONDS)
        target_time_budget_exhausted = False
    elif capacity_verified:
        best_effort_budget = new_budget()
        best_effort_attempt = _run_min_resource_best_effort_reoptimization(
            best_effort_budget.with_time_limit(schedule_input),
            fixed_counts,
            target_days=target_days,
            hard_match_count=hard_match_count,
            capacity_hint_result=capacity_result,
            strict_attempts=reoptimization_attempts,
            budget=best_effort_budget,
        )
        reoptimization_attempts.append(best_effort_attempt)
        if best_effort_attempt["result"].status in {"OPTIMAL", "FEASIBLE"}:
            result = best_effort_attempt["result"].model_copy(deep=True)
            selected_source = MINIMUM_RESOURCES_BEST_EFFORT_SOURCE
            target_time_budget_seconds = float(best_effort_attempt.get("time_limit_seconds") or TARGET_SOLVE_TIME_LIMIT_SECONDS)
            target_time_budget_exhausted = bool(best_effort_attempt.get("time_budget_exhausted", False))
            result.validation = validation + capacity_optimization["validation"] + result.validation
            result.validation.append(
                ValidationMessage(
                    level="warning",
                    message="最少资源严格重排未得到满足目标的结果，已放松强制节点和固定工期目标返回最佳努力精排。",
                )
            )
            strict_attempt = _first_reoptimization_result(
                reoptimization_attempts,
                exclude_source=MINIMUM_RESOURCES_BEST_EFFORT_SOURCE,
            )
            best_effort_metadata = _best_effort_reoptimization_metadata(
                result,
                schedule_source=MINIMUM_RESOURCES_BEST_EFFORT_SOURCE,
                fallback_from=strict_attempt["source"] if strict_attempt else "control_priority_balanced_reoptimization",
                strict_result=strict_attempt["result"] if strict_attempt else None,
            )
        else:
            result = capacity_result.model_copy(deep=True)
            selected_source = "capacity_model_verified_schedule"
            target_time_budget_seconds = float(best_effort_attempt.get("time_limit_seconds") or TARGET_SOLVE_TIME_LIMIT_SECONDS)
            target_time_budget_exhausted = True
            result.validation = validation + result.validation + best_effort_attempt["result"].validation
            result.validation.append(
                ValidationMessage(
                    level="warning",
                    message=(
                        "Minimum resource counts were verified by the capacity model. "
                        "Control-priority balanced reoptimization and best-effort reoptimization did not return "
                        "a usable schedule within the solve limit, so the verified capacity schedule is kept."
                    ),
                )
            )
    else:
        result = capacity_result.model_copy(deep=True, update={"status": "INFEASIBLE"})
        selected_source = "capacity_model_unverified"
        target_time_budget_seconds = TARGET_SOLVE_TIME_LIMIT_SECONDS
        target_time_budget_exhausted = False
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
        "minimum_resource_counts": minimum_counts,
        "recommended_resource_counts": recommended,
        "resource_optimization_phases": phase_stats,
        "schedule_source": selected_source,
        "recommended_schedule_source": selected_source,
        "capacity_model_status": capacity_optimization["status"],
        "global_capacity_model_status": global_capacity_optimization["status"],
        "capacity_model_group_counts": fixed_counts,
        "capacity_model_stats": capacity_optimization["stats"],
        "independent_solve_time_limit_seconds": TARGET_SOLVE_TIME_LIMIT_SECONDS,
        "max_resource_precheck_mode": "hard_milestone_fast",
        "capacity_precheck_status": fixed_duration_check["status"],
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
        "capacity_model_role": "internal_candidate_search",
        "capacity_model_retention_reason": (
            "保留为固定工期最大资源硬里程碑快速预检和候选资源数量搜索的内部加速器；业务结论仍以快速预检状态和候选复排的 target_achievement 为准。"
        ),
    }

    result.stats.update(metadata)
    result.objective_breakdown.update(metadata)
    _annotate_target_achievement(
        result,
        evaluated_at_source="candidate_resources",
        default_failed_status="candidate_resources_target_failed",
        success_status="candidate_resources_target_met",
        fixed_duration_target=target_days,
        time_budget_seconds=target_time_budget_seconds,
        time_budget_exhausted=target_time_budget_exhausted,
    )
    if best_effort_metadata is not None:
        result.stats["best_effort_refinement"] = best_effort_metadata
        result.objective_breakdown["best_effort_refinement"] = {
            "enabled": True,
            "schedule_source": best_effort_metadata["schedule_source"],
            "target_lateness_days": best_effort_metadata["target_lateness_days"],
            "fixed_duration_overrun_days": best_effort_metadata["fixed_duration_overrun_days"],
            "best_effort_score": best_effort_metadata["best_effort_score"],
            "relaxed_constraints": best_effort_metadata["relaxed_constraints"],
        }
    return result


def _run_min_resource_reoptimizations(
    schedule_input: ScheduleInput,
    fixed_counts: dict[str, int],
    *,
    target_days: int | None,
    hard_match_count: int,
    capacity_hint_result: ScheduleResult | None = None,
    budget: _SolveBudget | None = None,
) -> list[dict[str, Any]]:
    budget = budget or _SolveBudget(schedule_input.time_limit_seconds)
    candidates = _min_resource_reoptimization_candidates(schedule_input, fixed_counts)
    parallelism = _solve_task_parallelism(len(candidates))

    def run(candidate: dict[str, Any]) -> dict[str, Any]:
        attempt_budget = _SolveBudget(schedule_input.time_limit_seconds)
        result = solve_control_priority_schedule(
            attempt_budget.with_time_limit(candidate["schedule_input"]),
            enforce_hard_milestones=True,
            max_makespan_days=target_days if hard_match_count == 0 else None,
            warm_start_result=capacity_hint_result,
            relax_target_constraints=True,
        )
        return {
            "source": candidate["source"],
            "result": result,
            "parallelism": parallelism,
            "time_limit_seconds": attempt_budget.time_limit_seconds,
            "time_budget_exhausted": attempt_budget.exhausted(),
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


def _run_min_resource_best_effort_reoptimization(
    schedule_input: ScheduleInput,
    fixed_counts: dict[str, int],
    *,
    target_days: int | None,
    hard_match_count: int,
    capacity_hint_result: ScheduleResult | None,
    strict_attempts: list[dict[str, Any]],
    budget: _SolveBudget | None = None,
) -> dict[str, Any]:
    budget = budget or _SolveBudget(schedule_input.time_limit_seconds)
    strict_source = strict_attempts[0]["source"] if strict_attempts else "control_priority_balanced_reoptimization"
    candidate = _min_resource_reoptimization_candidates(schedule_input, fixed_counts)[0]
    attempt_budget = _SolveBudget(schedule_input.time_limit_seconds)
    result = solve_control_priority_schedule(
        attempt_budget.with_time_limit(candidate["schedule_input"]),
        enforce_hard_milestones=True,
        max_makespan_days=target_days if hard_match_count == 0 else None,
        warm_start_result=capacity_hint_result,
        relax_target_constraints=True,
    )
    return {
        "source": MINIMUM_RESOURCES_BEST_EFFORT_SOURCE,
        "result": result,
        "parallelism": 1,
        "fallback_from": strict_source,
        "time_limit_seconds": attempt_budget.time_limit_seconds,
        "time_budget_exhausted": attempt_budget.exhausted(),
    }


def _min_resource_reoptimization_candidates(
    schedule_input: ScheduleInput,
    fixed_counts: dict[str, int],
) -> list[dict[str, Any]]:
    limited_resources = _apply_resource_limits(schedule_input.resources, fixed_counts)
    candidates = [
        {
            "source": "control_priority_balanced_reoptimization",
            "schedule_input": schedule_input.model_copy(
                update={
                    "resources": limited_resources,
                }
            ),
        }
    ]
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


def _annotate_target_achievement(
    result: ScheduleResult,
    *,
    evaluated_at_source: str,
    default_failed_status: str = "current_resources_target_failed",
    success_status: str = "met",
    forced_status: str | None = None,
    fixed_duration_target: int | None = None,
    time_budget_seconds: float = TARGET_SOLVE_TIME_LIMIT_SECONDS,
    time_budget_exhausted: bool = False,
) -> dict[str, Any]:
    hard_milestone_late_days = sum(
        int(milestone.lateness_days or 0)
        for milestone in result.milestone_results
        if milestone.mode == "hard"
    )
    fixed_duration_overrun_days = _target_fixed_duration_overrun_days(
        result,
        fixed_duration_target=fixed_duration_target,
    )
    status = forced_status or _target_status_for_result(
        result,
        hard_milestone_late_days=hard_milestone_late_days,
        fixed_duration_overrun_days=fixed_duration_overrun_days,
        default_failed_status=default_failed_status,
        success_status=success_status,
        time_budget_exhausted=time_budget_exhausted,
    )
    failure_reasons = _target_failure_reasons(
        status=status,
        hard_milestone_late_days=hard_milestone_late_days,
        fixed_duration_overrun_days=fixed_duration_overrun_days,
        time_budget_exhausted=time_budget_exhausted,
    )
    payload = {
        "business_success": status in {"met", "candidate_resources_target_met"},
        "target_status": status,
        "solver_status": result.status,
        "hard_milestone_late_days": hard_milestone_late_days,
        "fixed_duration_overrun_days": fixed_duration_overrun_days,
        "failure_reasons": failure_reasons,
        "time_budget_seconds": time_budget_seconds,
        "time_budget_exhausted": time_budget_exhausted,
        "evaluated_at_source": evaluated_at_source,
    }
    result.stats["target_achievement"] = payload
    result.objective_breakdown["target_achievement"] = payload
    result.stats["hard_milestone_late_days"] = hard_milestone_late_days
    result.stats["fixed_duration_overrun_days"] = fixed_duration_overrun_days
    result.objective_breakdown["hard_milestone_late_days"] = hard_milestone_late_days
    result.objective_breakdown["fixed_duration_overrun_days"] = fixed_duration_overrun_days
    return payload


def _target_fixed_duration_overrun_days(
    result: ScheduleResult,
    *,
    fixed_duration_target: int | None,
) -> int:
    direct = _int_or_none(result.objective_breakdown.get("fixed_duration_overrun_days"))
    if direct is not None:
        return max(0, direct)
    relaxed = result.stats.get("relaxed_target_constraints")
    if isinstance(relaxed, dict):
        relaxed_overrun = _int_or_none(relaxed.get("fixed_duration_overrun_days"))
        if relaxed_overrun is not None:
            return max(0, relaxed_overrun)
    target = fixed_duration_target
    if target is None:
        target = _int_or_none(result.stats.get("max_makespan_days") or result.objective_breakdown.get("max_makespan_days"))
    if target is None or result.objective_days is None:
        return 0
    return max(0, int(result.objective_days) - target)


def _target_status_for_result(
    result: ScheduleResult,
    *,
    hard_milestone_late_days: int,
    fixed_duration_overrun_days: int,
    default_failed_status: str,
    success_status: str,
    time_budget_exhausted: bool,
) -> str:
    if time_budget_exhausted or result.status == "UNKNOWN":
        return "unconfirmed"
    if result.status not in {"OPTIMAL", "FEASIBLE"}:
        return "physical_infeasible"
    if hard_milestone_late_days == 0 and fixed_duration_overrun_days == 0:
        return success_status
    return default_failed_status


def _target_failure_reasons(
    *,
    status: str,
    hard_milestone_late_days: int,
    fixed_duration_overrun_days: int,
    time_budget_exhausted: bool,
) -> list[str]:
    reasons: list[str] = []
    if hard_milestone_late_days > 0:
        reasons.append("hard_milestone_late")
    if fixed_duration_overrun_days > 0:
        reasons.append("fixed_duration_overrun")
    if status == "physical_infeasible":
        reasons.append("physical_infeasible")
    if status == "max_resources_target_failed":
        reasons.append("max_resources_target_failed")
    if status == "unconfirmed":
        reasons.append("unconfirmed")
    if time_budget_exhausted:
        reasons.append("time_budget_exhausted")
    return list(dict.fromkeys(reasons))


def _first_reoptimization_result(
    attempts: list[dict[str, Any]],
    *,
    exclude_source: str,
) -> dict[str, Any] | None:
    for attempt in attempts:
        if attempt["source"] != exclude_source:
            return attempt
    return None


def _best_effort_reoptimization_metadata(
    result: ScheduleResult,
    *,
    schedule_source: str,
    fallback_from: str,
    strict_result: ScheduleResult | None,
) -> dict[str, Any]:
    target_lateness_days = sum(
        milestone.lateness_days
        for milestone in result.milestone_results
        if milestone.mode == "hard"
    )
    fixed_duration_overrun_days = int(
        result.objective_breakdown.get("fixed_duration_overrun_days")
        or result.stats.get("relaxed_target_constraints", {}).get("fixed_duration_overrun_days", 0)
        or 0
    )
    strict_status = strict_result.status if strict_result is not None else "not_attempted"
    fixed_duration_target = _int_or_none(result.stats.get("max_makespan_days"))
    best_effort_score = result.objective_breakdown.get("best_effort_score")
    if best_effort_score is None:
        best_effort_score = result.objective_breakdown.get("weighted_objective")
    return {
        "enabled": True,
        "schedule_source": schedule_source,
        "fallback_from": fallback_from,
        "strict_refinement_status": strict_status,
        "strict_refinement_failure_reason": f"minimum_resource_refinement_{strict_status.lower()}",
        "objective_status": result.status,
        "target_lateness_days": target_lateness_days,
        "fixed_duration_overrun_days": fixed_duration_overrun_days,
        "best_effort_score": best_effort_score,
        "wall_time_seconds": result.stats.get("wall_time_seconds"),
        "strict_wall_time_seconds": strict_result.stats.get("wall_time_seconds") if strict_result is not None else None,
        "relaxed_constraints": _best_effort_relaxed_constraints(
            result,
            fixed_duration_target=fixed_duration_target,
            fixed_duration_overrun_days=fixed_duration_overrun_days,
        ),
    }


def _best_effort_relaxed_constraints(
    result: ScheduleResult,
    *,
    fixed_duration_target: int | None,
    fixed_duration_overrun_days: int,
) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    for milestone in result.milestone_results:
        if milestone.mode != "hard" or milestone.actual_date is None:
            continue
        constraints.append(
            {
                "type": "hard_milestone",
                "id": milestone.id,
                "name": milestone.name,
                "target": milestone.target_date.isoformat(),
                "actual": milestone.actual_date.isoformat(),
                "lateness_days": milestone.lateness_days,
                "scope": milestone.scope_id or milestone.scope_type,
            }
        )
    if fixed_duration_target is not None:
        constraints.append(
            {
                "type": "fixed_duration",
                "name": "固定工期目标",
                "target": fixed_duration_target,
                "actual": result.objective_days,
                "lateness_days": fixed_duration_overrun_days,
            }
        )
    return constraints


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _reoptimization_priority(source: str) -> int:
    priorities = {
        "control_priority_balanced_reoptimization": 0,
        "control_priority_reoptimization_no_balance": 1,
        MINIMUM_RESOURCES_BEST_EFFORT_SOURCE: 2,
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
                "time_limit_seconds": attempt.get("time_limit_seconds"),
                "time_budget_exhausted": attempt.get("time_budget_exhausted"),
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
    minimum_resource_counts: dict[str, int],
    fixed_duration_check: dict[str, Any],
    fallback_target_days: int | None = None,
    budget: _SolveBudget | None = None,
) -> dict[str, Any]:
    budget = budget or _SolveBudget(schedule_input.time_limit_seconds)
    max_counts = {group["key"]: int(group["max_quantity"]) for group in groups}
    attempts: list[dict[str, Any]] = []
    total_wall_time = 0.0
    total_conflicts = 0
    total_branches = 0

    def attempt_input() -> ScheduleInput:
        return _SolveBudget(schedule_input.time_limit_seconds).with_time_limit(schedule_input)

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
            attempt_input(),
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
        low = int(minimum_resource_counts.get(key, 0))
        high = int(best_counts.get(key, group["max_quantity"]))
        while low < high:
            mid = (low + high) // 2
            trial_counts = {**best_counts, key: mid}
            trial = _solve_capacity_model(
                attempt_input(),
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
    started_at = time.perf_counter()
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

    assignment_vars, resource_intervals = _build_named_resource_assignment_model(
        model,
        starts=starts,
        ends=ends,
        tasks=schedule_input.tasks,
        enabled_resources=enabled_resources,
        resource_candidates=resource_candidates,
        horizon=horizon,
    )
    for (_, resource_id), assignment in assignment_vars.items():
        assignments_by_resource[resource_id].append(assignment)

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
    if feasibility_only:
        pass
    elif minimize_group_key:
        model.Minimize(group_count_exprs.get(minimize_group_key, 0))
    else:
        primary_objective = makespan + sum(soft_penalty_terms)
        model.Minimize(primary_objective * CONTINUITY_PRIMARY_WEIGHT)

    solver = cp_model.CpSolver()
    model_built_at = time.perf_counter()
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
        "makespan": makespan,
        "validation": validation,
        "group_counts": group_counts,
        "stats": {
            "horizon_days": horizon,
            **_solver_timing_stats(
                started_at,
                solver,
                configured_time_limit_seconds=schedule_input.time_limit_seconds,
                model_built_at=model_built_at,
            ),
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
    minimum_resource_counts: dict[str, int] | None = None,
    fallback_target_days: int | None = None,
    enforce_fixed_duration: bool = True,
    minimize_resource_count: bool = False,
    minimize_total_cost: bool = False,
    minimize_makespan: bool = False,
    resource_linear_costs_by_group: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
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
                if _is_continuous_beam_task(task) and resource_type == CONTINUOUS_BEAM_RESOURCE_TYPE:
                    continue
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
        elif task.compatible_resource_types and not (
            _is_continuous_beam_task(task)
            and CONTINUOUS_BEAM_RESOURCE_TYPE in task.compatible_resource_types
        ):
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=task.id,
                    message=f"“{task.name}”没有可用于容量校验的受限资源池，已按资源默认充足处理。",
                )
            )

    continuous_span_model = _add_capacity_continuous_beam_team_span_constraints(
        model,
        starts=starts,
        ends=ends,
        tasks=schedule_input.tasks,
        groups_by_type=groups_by_type,
        intervals_by_group=intervals_by_group,
        demands_by_group=demands_by_group,
        validation=validation,
        horizon=horizon,
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
        minimum_count = int((minimum_resource_counts or {}).get(group["key"], 0) or 0)
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
                lower_bound = 0
                lower_bound = max(lower_bound, minimum_count)
                lower_bound = min(lower_bound, group["max_quantity"])
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
    model_built_at = time.perf_counter()
    _configure_solver(solver, schedule_input.time_limit_seconds)
    status_code = solver.Solve(model)
    solve_pass_count = 1
    status = _status_name(status_code, cp_model)
    if minimize_total_cost and status in {"OPTIMAL", "FEASIBLE"}:
        best_resource_cost = solver.Value(total_resource_cost)
        model.Add(total_resource_cost == best_resource_cost)
        model.Minimize(total_soft_penalty)
        status_code = solver.Solve(model)
        solve_pass_count += 1
        status = _status_name(status_code, cp_model)
    if minimize_total_cost and status in {"OPTIMAL", "FEASIBLE"}:
        best_soft_penalty = solver.Value(total_soft_penalty)
        model.Add(total_soft_penalty == best_soft_penalty)
        model.Minimize(makespan)
        status_code = solver.Solve(model)
        solve_pass_count += 1
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
        "continuous_span_model": continuous_span_model,
        "validation": validation,
        "selected_resource_costs": selected_resource_costs,
        "resource_incremental_cost": sum(int(resource["incremental_cost"]) for resource in selected_resource_costs),
        "stats": {
            "horizon_days": horizon,
            **_solver_timing_stats(
                started_at,
                solver,
                configured_time_limit_seconds=schedule_input.time_limit_seconds,
                model_built_at=model_built_at,
            ),
            "solve_pass_count": solve_pass_count,
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
    continuous_span_payload = _capacity_continuous_span_payload(
        schedule_input=schedule_input,
        solved=solved,
        fixed_counts=fixed_counts,
    )
    continuous_span_by_task_id = _continuous_span_by_task_id(continuous_span_payload)
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
                **_scheduled_continuous_fields(task, continuous_span_by_task_id),
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
    allocations.extend(_continuous_span_allocations(schedule_input, continuous_span_payload))

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
            "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
        },
        "continuous_beam_team_spans": continuous_span_payload,
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
    stats = {
        **solved["stats"],
        "continuity_metrics": continuity_metrics,
        "continuity_objective": {
            "primary_weight": CONTINUITY_PRIMARY_WEIGHT,
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
            "continuity_score": continuity_metrics["continuity_score"],
            "weighted_objective": objective_days + soft_milestone_penalty,
        },
    )


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
                "parallel_rule_description": "",
            }
        groups[key]["resources"].append(resource)
        groups[key]["max_quantity"] += 1
        groups[key]["same_structure_resource_binding"] = (
            groups[key]["same_structure_resource_binding"] or resource.same_structure_resource_binding
        )
        if not groups[key]["parallel_rule_description"] and resource.parallel_rule_description:
            groups[key]["parallel_rule_description"] = resource.parallel_rule_description
    return sorted(groups.values(), key=lambda group: (group["resource_type"], group["key"], group["label"]))


def _normalized_minimum_resource_counts(
    groups: list[dict[str, Any]],
    minimum_resource_counts: dict[str, int] | None,
) -> dict[str, int]:
    if not minimum_resource_counts:
        return {}
    normalized: dict[str, int] = {}
    for group in groups:
        raw_count = int(minimum_resource_counts.get(group["key"], 0) or 0)
        normalized[group["key"]] = max(0, min(raw_count, int(group["max_quantity"])))
    return normalized


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
