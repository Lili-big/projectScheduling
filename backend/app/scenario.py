from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .models import (
    ComponentModel,
    ComponentType,
    GeneratedScheduleInput,
    LogicRule,
    MinResourcesSolveRequest,
    PrecedenceLink,
    ProcessTemplate,
    ProjectBridge,
    ProductivityOption,
    ProductivityRule,
    Resource,
    ResourcePool,
    ScheduleInput,
    ScheduleResult,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioInput,
    ScenarioSolveResult,
    StructureModel,
    Task,
    TaskOverride,
    UpperStructureComponent,
    UpperStructureLogicRule,
    ValidationMessage,
    WorkSection,
)
from .solver import solve_min_resources_schedule, solve_schedule
from .wbs import build_precedence_links, calculate_duration


CONTINUOUS_BEAM_STRUCTURE_CODE = "castInPlaceContinuousBoxGirder"
CONTINUOUS_BEAM_COMPONENT_TYPE = "cast_in_place_continuous_beam"
CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES = 18
CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE = "castInPlaceBoxGirder"
SIMPLE_BEAM_STRUCTURE_CODE = "precastTGirder"
UPPER_STRUCTURE_LOGIC_RULE_IDS = (
    "cast_in_place_box_beam_after_lower_structure",
    "continuous_beam_zero_block_after_main_pier_lower_structure",
    "continuous_beam_side_straight_after_edge_lower_structure",
    "continuous_beam_t_chain",
    "continuous_beam_side_closure",
    "continuous_beam_middle_closure",
    "continuous_beam_edge_before_middle_closure",
    "continuous_beam_middle_closure_sequence",
)
KEY_RESOURCE_COMPONENT_TYPES = {"pile", "cap", "pier_body", "cap_beam", CONTINUOUS_BEAM_COMPONENT_TYPE}
DEFAULT_RESOURCE_TYPE_BY_COMPONENT: dict[str, str] = {
    "cap": "cap_team",
    "pier_body": "pier_body_team",
    "cap_beam": "cap_beam_team",
    CONTINUOUS_BEAM_COMPONENT_TYPE: "cast_in_place_continuous_beam_team",
}
PILE_RESOURCE_TYPE_BY_PROCESS: dict[str, str] = {
    "pile_rotary_regular": "rotary_drill",
    "pile_circulation": "circulation_drill",
    "pile_impact": "impact_drill",
    "pile_manual": "manual_pile_team",
}
PILE_RESOURCE_TYPE_BY_METHOD: dict[str, str] = {
    "rotary_drill": "rotary_drill",
    "circulation_drill": "circulation_drill",
    "impact_drill": "impact_drill",
    "manual_pile": "manual_pile_team",
    "manual_excavation": "manual_pile_team",
}


def _upper_structure_logic_rule_by_id(rules: list[UpperStructureLogicRule]) -> dict[str, UpperStructureLogicRule]:
    merged = {rule_id: UpperStructureLogicRule(id=rule_id) for rule_id in UPPER_STRUCTURE_LOGIC_RULE_IDS}
    for rule in rules:
        merged[rule.id] = rule
    return merged


def _upper_structure_logic_rule(
    rules: dict[str, UpperStructureLogicRule] | None,
    rule_id: str,
) -> UpperStructureLogicRule:
    if rules and rule_id in rules:
        return rules[rule_id]
    return UpperStructureLogicRule(id=rule_id)


def generate_schedule_input_from_scenario(scenario: ScenarioInput, *, use_max_resources: bool = False) -> GeneratedScheduleInput:
    validation: list[ValidationMessage] = []
    tasks, generated_links = _build_tasks(scenario, validation)
    tasks = _apply_required_resource_types(tasks, scenario.resource_pools, validation)
    same_structure_rules = [rule for rule in scenario.logic_rules if rule.scope == "same_structure"]
    precedence_links, link_messages = build_precedence_links(tasks, same_structure_rules)
    precedence_links.extend(generated_links)
    validation.extend(link_messages)
    sequence_links, sequence_messages = _build_structure_sequence_links(
        scenario.logic_rules,
        tasks,
        start_index=len(precedence_links) + 1,
    )
    precedence_links.extend(sequence_links)
    validation.extend(sequence_messages)

    resources, resource_messages = expand_resource_pools(scenario.resource_pools, use_max_quantity=use_max_resources)
    validation.extend(resource_messages)
    validation.extend(_validate_calendars(scenario))

    if not tasks:
        validation.append(ValidationMessage(level="error", message="未生成任何启用的工作项。"))
    if not resources:
        validation.append(ValidationMessage(level="info", message="未生成受限命名资源，当前场景将按资源默认充足排程。"))

    schedule_input = ScheduleInput(
        project_name=scenario.project.project_name,
        start_date=scenario.project.start_date,
        tasks=tasks,
        precedence_links=precedence_links,
        resources=resources,
        milestones=scenario.milestones,
        time_limit_seconds=scenario.time_limit_seconds,
    )
    validation.append(
        ValidationMessage(
            level="info",
            message=(
                f"场景已生成 {len(tasks)} 个工作项、{len(precedence_links)} 条工艺逻辑关系、"
                f"{len(resources)} 个受限命名资源。"
            ),
        )
    )
    return GeneratedScheduleInput(
        schedule_input=schedule_input,
        validation=validation,
        source_summary={
            "bridge_count": len(scenario.project.bridges),
            "process_count": len(scenario.process_library),
            "resource_pool_count": len(scenario.resource_pools),
            "milestone_count": len(scenario.milestones),
            "continuous_beam_task_count": sum(1 for task in tasks if task.structure_type == "continuous_beam"),
        },
    )


def solve_scenario(scenario: ScenarioInput) -> ScenarioSolveResult:
    generated = generate_schedule_input_from_scenario(scenario)
    if any(message.level == "error" for message in generated.validation):
        result = ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=scenario.project.start_date,
            validation=generated.validation,
            stats={"reason": "scenario_generation_error"},
            milestone_results=[],
        )
    else:
        result = solve_schedule(generated.schedule_input)
        result.objective_breakdown.setdefault("solve_mode", "shortest_duration_fixed_resources")

    diagnostics = _build_diagnostics(generated.validation, result)
    return ScenarioSolveResult(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.scenario_name,
        generated=generated,
        result=result,
        milestone_results=result.milestone_results,
        diagnostics=diagnostics,
        metrics=_scenario_metrics(generated, result),
    )


def solve_min_resources_scenario(request: MinResourcesSolveRequest) -> ScenarioSolveResult:
    scenario = request.scenario
    generated = generate_schedule_input_from_scenario(scenario, use_max_resources=True)
    if any(message.level == "error" for message in generated.validation):
        result = ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=scenario.project.start_date,
            validation=generated.validation,
            stats={"reason": "scenario_generation_error", "solve_mode": "min_resources_fixed_duration"},
            milestone_results=[],
        )
    else:
        result = solve_min_resources_schedule(generated.schedule_input, fallback_target_days=request.fallback_target_days)

    diagnostics = _build_diagnostics(generated.validation, result)
    return ScenarioSolveResult(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.scenario_name,
        generated=generated,
        result=result,
        milestone_results=result.milestone_results,
        diagnostics=diagnostics,
        metrics=_scenario_metrics(generated, result),
    )


def compare_scenarios(request: ScenarioCompareRequest) -> ScenarioCompareResponse:
    summaries: list[dict[str, Any]] = []
    best_scenario_id: str | None = None
    best_score: int | None = None

    for item in request.results:
        result = item.result
        penalty = sum(milestone.penalty for milestone in item.milestone_results)
        feasible = result.status in {"OPTIMAL", "FEASIBLE"}
        score = (result.objective_days or 0) + penalty if feasible else None
        soft_late = sum(1 for milestone in item.milestone_results if milestone.mode == "soft" and milestone.lateness_days > 0)
        hard_missed = sum(1 for milestone in item.milestone_results if milestone.mode == "hard" and milestone.lateness_days > 0)
        summaries.append(
            {
                "scenario_id": item.scenario_id,
                "scenario_name": item.scenario_name,
                "status": result.status,
                "total_days": result.objective_days,
                "plan_finish_date": result.plan_finish_date,
                "soft_late_count": soft_late,
                "hard_missed_count": hard_missed,
                "soft_penalty": penalty,
                "score": score,
                "resource_count": len(item.generated.schedule_input.resources),
            }
        )
        if score is not None and (best_score is None or score < best_score):
            best_score = score
            best_scenario_id = item.scenario_id

    notes = []
    if best_scenario_id:
        notes.append("推荐方案按总工期加软里程碑罚分综合选择。")
    return ScenarioCompareResponse(summaries=summaries, best_scenario_id=best_scenario_id, notes=notes)


def _apply_required_resource_types(
    tasks: list[Task],
    resource_pools: list[ResourcePool],
    validation: list[ValidationMessage],
) -> list[Task]:
    pools_by_type = {pool.type: pool for pool in resource_pools}
    warning_keys: set[str] = set()
    return [
        task.model_copy(
            update={
                "compatible_resource_types": _required_resource_types_for_task(
                    task,
                    pools_by_type,
                    validation,
                    warning_keys,
                )
            }
        )
        for task in tasks
    ]


def _required_resource_types_for_task(
    task: Task,
    pools_by_type: dict[str, ResourcePool],
    validation: list[ValidationMessage],
    warning_keys: set[str],
) -> list[str]:
    default_resource_type = _default_resource_type_for_task(task)
    if not default_resource_type:
        return []

    pool = pools_by_type.get(default_resource_type)
    if _is_limited_pool_available(pool):
        return [default_resource_type]

    if task.component_type in KEY_RESOURCE_COMPONENT_TYPES:
        _append_unbounded_resource_warning(task, default_resource_type, pool, validation, warning_keys)
        return []

    if pool is not None and pool.resource_mode == "LIMITED":
        _append_unbounded_resource_warning(task, default_resource_type, pool, validation, warning_keys)
    return []


def _default_resource_type_for_task(task: Task) -> str | None:
    fallback = task.compatible_resource_types[0] if task.compatible_resource_types else None
    process_id = task.productivity_rule_id.split(":", 1)[0]
    method_id = _method_id_from_process_id(process_id)
    if task.component_type == "pile":
        return (
            PILE_RESOURCE_TYPE_BY_PROCESS.get(process_id)
            or (PILE_RESOURCE_TYPE_BY_METHOD.get(method_id) if method_id else None)
            or fallback
        )
    return DEFAULT_RESOURCE_TYPE_BY_COMPONENT.get(task.component_type, fallback)


def _method_id_from_process_id(process_id: str) -> str | None:
    for method_id in PILE_RESOURCE_TYPE_BY_METHOD:
        if method_id in process_id:
            return method_id
    return None


def _is_limited_pool_available(pool: ResourcePool | None) -> bool:
    return bool(pool and pool.enabled and pool.resource_mode == "LIMITED" and (pool.quantity or 0) > 0)


def _append_unbounded_resource_warning(
    task: Task,
    resource_type: str,
    pool: ResourcePool | None,
    validation: list[ValidationMessage],
    warning_keys: set[str],
) -> None:
    reason = _resource_unbounded_reason(pool)
    key = f"{resource_type}:{reason}"
    if key in warning_keys:
        return
    warning_keys.add(key)
    label = pool.label if pool else resource_type
    validation.append(
        ValidationMessage(
            level="warning",
            subject_id=pool.id if pool else resource_type,
            message=f"资源“{label}”{reason}，相关工作项按资源默认充足处理，不产生资源等待。",
        )
    )


def _resource_unbounded_reason(pool: ResourcePool | None) -> str:
    if pool is None:
        return "未配置"
    if not pool.enabled:
        return "未启用"
    if pool.resource_mode == "UNLIMITED":
        return "设置为默认充足"
    if (pool.quantity or 0) <= 0:
        return "限制数量为 0"
    return "不可用"


def expand_resource_pools(resource_pools: list[ResourcePool], *, use_max_quantity: bool = False) -> tuple[list[Resource], list[ValidationMessage]]:
    resources: list[Resource] = []
    validation: list[ValidationMessage] = []
    for pool in resource_pools:
        if not pool.enabled or pool.resource_mode == "UNLIMITED":
            continue
        quantity = pool.max_quantity if use_max_quantity else pool.quantity
        quantity = quantity or 0
        for index in range(1, quantity + 1):
            resources.append(
                Resource(
                    id=f"{pool.type}_{index}",
                    name=f"{pool.label}{index}",
                    type=pool.type,
                    pool_id=pool.id,
                    pool_label=pool.label,
                    enabled=True,
                    calendar_id=pool.calendar_id,
                )
            )
        if quantity == 0:
            quantity_label = "最大数量" if use_max_quantity else "默认数量"
            validation.append(
                ValidationMessage(level="warning", subject_id=pool.id, message=f"资源池“{pool.label}”的{quantity_label}为 0。")
            )
    return resources, validation


def _build_tasks(scenario: ScenarioInput, validation: list[ValidationMessage]) -> tuple[list[Task], list[PrecedenceLink]]:
    tasks: list[Task] = []
    generated_links: list[PrecedenceLink] = []
    upper_logic_rules = _upper_structure_logic_rule_by_id(scenario.upper_structure_logic_rules)
    task_overrides = scenario.task_overrides
    for bridge in sorted(scenario.project.bridges, key=lambda item: item.order):
        for section in sorted(bridge.work_sections, key=lambda item: item.order):
            section_lower_start = len(tasks)
            for structure in sorted(section.structures, key=lambda item: item.order):
                for component_index, component in enumerate(structure.components):
                    if not component.enabled:
                        continue
                    task = _task_from_component(
                        component=component,
                        process_library=scenario.process_library,
                        validation=validation,
                        bridge_id=bridge.id,
                        work_section_id=section.id,
                        sequence_order=structure.order * 100 + component_index,
                        structure_id=structure.id,
                        structure_name=structure.name,
                        structure_type=structure.structure_type,
                    )
                    if task is not None:
                        tasks.append(task)

            section_lower_tasks = tasks[section_lower_start:]
            upper_tasks, upper_links = _build_upper_structure_tasks(
                bridge=bridge,
                section=section,
                process_library=scenario.process_library,
                validation=validation,
                lower_tasks=section_lower_tasks,
                upper_logic_rules=upper_logic_rules,
                task_overrides=task_overrides,
            )
            tasks.extend(upper_tasks)
            generated_links.extend(upper_links)
    return tasks, generated_links


def _task_from_component(
    *,
    component: ComponentModel,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    bridge_id: str | None,
    work_section_id: str | None,
    sequence_order: int,
    structure_id: str,
    structure_name: str,
    structure_type: str,
) -> Task | None:
    process = _select_process(component, process_library)
    if process is None:
        validation.append(
            ValidationMessage(
                level="error",
                subject_id=component.id,
                message=f"构件“{component.name}”没有匹配的工艺模板。",
            )
        )
        return None
    if component.quantity <= 0:
        validation.append(
            ValidationMessage(
                level="warning",
                subject_id=component.id,
                message=f"构件“{component.name}”的工程量为 0，已跳过。",
            )
        )
        return None

    rule = _process_to_productivity_rule(process, component)
    quantity, quantity_label = _quantity_for_process(component, rule.quantity_source)
    return Task(
        id=component.id,
        name=component.name,
        bridge_id=bridge_id,
        work_section_id=work_section_id,
        component_id=component.id,
        sequence_order=sequence_order,
        structure_id=structure_id,
        structure_name=structure_name,
        structure_type=structure_type,
        component_type=component.component_type,
        process_name=process.process_name,
        productivity_rule_id=rule.id,
        quantity=quantity,
        quantity_label=quantity_label,
        duration_days=calculate_duration(quantity, rule),
        compatible_resource_types=[process.resource_type],
    )


def _apply_task_override(component: ComponentModel, task_overrides: dict[str, TaskOverride]) -> ComponentModel:
    override = task_overrides.get(component.id)
    if override is None:
        return component
    patch: dict[str, str | None] = {}
    if override.method_id is not None:
        patch["method_id"] = override.method_id
    if override.productivity_option_id is not None:
        patch["productivity_option_id"] = override.productivity_option_id
    return component.model_copy(update=patch) if patch else component


def _build_upper_structure_tasks(
    *,
    bridge: ProjectBridge,
    section: WorkSection,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    lower_tasks: list[Task],
    upper_logic_rules: dict[str, UpperStructureLogicRule],
    task_overrides: dict[str, TaskOverride] | None = None,
) -> tuple[list[Task], list[PrecedenceLink]]:
    support_completions = _lower_completion_tasks_by_support(section, lower_tasks)
    tasks: list[Task] = []
    links: list[PrecedenceLink] = []
    overrides = task_overrides or {}

    # 本期简支梁只保留为结构参数，不生成架梁排程任务。

    box_tasks, box_links = _build_cast_in_place_box_beam_tasks(
        bridge=bridge,
        section=section,
        process_library=process_library,
        validation=validation,
        support_completions=support_completions,
        link_start=len(links) + 1,
        upper_logic_rules=upper_logic_rules,
        task_overrides=overrides,
    )
    tasks.extend(box_tasks)
    links.extend(box_links)

    continuous_tasks, continuous_links = _build_continuous_beam_tasks(
        bridge=bridge,
        section=section,
        process_library=process_library,
        validation=validation,
        support_completions=support_completions,
        link_start=len(links) + 1,
        upper_logic_rules=upper_logic_rules,
        task_overrides=overrides,
    )
    tasks.extend(continuous_tasks)
    links.extend(continuous_links)
    return tasks, links


def _build_simple_beam_erection_tasks(
    *,
    bridge: ProjectBridge,
    section: WorkSection,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    support_completions: dict[str, list[Task]],
) -> tuple[list[Task], list[PrecedenceLink]]:
    tasks: list[Task] = []
    links: list[PrecedenceLink] = []
    side_code = _side_code(section.side)
    side_label = _side_label(section.side)
    for upper in sorted(section.upper_structures, key=lambda item: item.span_index):
        if not _is_simple_beam_upper(upper):
            continue
        task = _append_upper_task(
            tasks=tasks,
            component_id=f"{upper.id}-ERECTION",
            name=f"{side_label}第{upper.span_index}跨简支梁架梁",
            component_type="beam_erection",
            quantity=float(upper.beam_count_per_span or 1),
            quantity_label=f"{upper.beam_count_per_span}片" if upper.beam_count_per_span else "1跨",
            bridge_id=bridge.id,
            work_section_id=section.id,
            sequence_order=90000 + upper.span_index,
            structure_id=f"{bridge.id}-{side_code}-SPAN-{upper.span_index:02d}-ERECTION",
            structure_name=f"{side_label}第{upper.span_index}跨简支梁架梁",
            process_library=process_library,
            validation=validation,
            properties={
                "upper_structure_id": upper.id,
                "support_range": upper.support_range,
                "span_index": upper.span_index,
            },
        )
        links.extend(
            _build_lower_to_upper_links(
                successor=task,
                support_refs=_support_refs_from_upper(upper),
                support_completions=support_completions,
                source_rule_id="simple_beam_after_lower_structure",
                link_prefix=f"LUB-{bridge.id}-{section.id}-S{upper.span_index:02d}",
                validation=validation,
            )
        )
    return tasks, links


def _build_cast_in_place_box_beam_tasks(
    *,
    bridge: ProjectBridge,
    section: WorkSection,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    support_completions: dict[str, list[Task]],
    link_start: int,
    upper_logic_rules: dict[str, UpperStructureLogicRule],
    task_overrides: dict[str, TaskOverride],
) -> tuple[list[Task], list[PrecedenceLink]]:
    tasks: list[Task] = []
    links: list[PrecedenceLink] = []
    side_code = _side_code(section.side)
    side_label = _side_label(section.side)
    link_no = link_start
    for uppers in _cast_in_place_box_beam_groups(section.upper_structures):
        group_index = _upper_group_index(uppers)
        span_indices = [upper.span_index for upper in uppers]
        first_span = min(span_indices)
        last_span = max(span_indices)
        task = _append_upper_task(
            tasks=tasks,
            component_id=f"{bridge.id}-{side_code}-BOX-G{group_index:02d}-CAST",
            name=f"{side_label}第{group_index}联现浇箱梁",
            component_type="cast_in_place_box_beam",
            quantity=1,
            quantity_label="1联",
            bridge_id=bridge.id,
            work_section_id=section.id,
            sequence_order=95000 + group_index,
            structure_id=f"{bridge.id}-{side_code}-BOX-G{group_index:02d}",
            structure_name=f"{side_label}第{group_index}联现浇箱梁",
            process_library=process_library,
            validation=validation,
            task_overrides=task_overrides,
            properties={
                "upper_structure_ids": [upper.id for upper in uppers],
                "span_start_index": first_span,
                "span_end_index": last_span,
            },
        )
        next_links = _build_lower_to_upper_links(
            successor=task,
            support_refs=_support_refs_for_upper_group(uppers),
            support_completions=support_completions,
            source_rule_id="cast_in_place_box_beam_after_lower_structure",
            link_prefix=f"LUB-{bridge.id}-{section.id}-BOX-G{group_index:02d}",
            validation=validation,
            start_index=link_no,
            upper_logic_rules=upper_logic_rules,
        )
        links.extend(next_links)
        link_no += len(next_links)
    return tasks, links


def _append_upper_task(
    *,
    tasks: list[Task],
    component_id: str,
    name: str,
    component_type: ComponentType,
    quantity: float,
    quantity_label: str,
    bridge_id: str,
    work_section_id: str,
    sequence_order: int,
    structure_id: str,
    structure_name: str,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    properties: dict[str, Any],
    task_overrides: dict[str, TaskOverride],
    method_id: str | None = None,
) -> Task | None:
    component = _apply_task_override(ComponentModel(
        id=component_id,
        name=name,
        component_type=component_type,
        quantity=quantity,
        quantity_label=quantity_label,
        method_id=method_id,
        properties=properties,
    ), task_overrides or {})
    task = _task_from_component(
        component=component,
        process_library=process_library,
        validation=validation,
        bridge_id=bridge_id,
        work_section_id=work_section_id,
        sequence_order=sequence_order,
        structure_id=structure_id,
        structure_name=structure_name,
        structure_type="upper_structure",
    )
    if task is not None:
        tasks.append(task)
    return task


def _build_lower_to_upper_links(
    *,
    successor: Task | None,
    support_refs: list[str],
    support_completions: dict[str, list[Task]],
    source_rule_id: str,
    link_prefix: str,
    validation: list[ValidationMessage],
    start_index: int = 1,
    upper_logic_rules: dict[str, UpperStructureLogicRule] | None = None,
) -> list[PrecedenceLink]:
    if successor is None:
        return []
    links: list[PrecedenceLink] = []
    seen_refs: set[str] = set()
    link_no = start_index
    rule = _upper_structure_logic_rule(upper_logic_rules, source_rule_id)
    for support_ref in support_refs:
        normalized_ref = _normalize_support_label(support_ref)
        if not normalized_ref or normalized_ref in seen_refs:
            continue
        seen_refs.add(normalized_ref)
        predecessors = support_completions.get(normalized_ref, [])
        if not predecessors:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=successor.id,
                    message=f"{successor.name}未找到{normalized_ref}对应的下部结构完成任务，已跳过该前置关系。",
                )
            )
            continue
        for predecessor in predecessors:
            links.append(
                PrecedenceLink(
                    id=f"{link_prefix}-{link_no:04d}",
                    predecessor_id=predecessor.id,
                    successor_id=successor.id,
                    relationship=rule.relationship,
                    lag_days=rule.lag_days,
                    source_rule_id=source_rule_id,
                    severity=rule.severity,
                )
            )
            link_no += 1
    return links


def _lower_completion_tasks_by_support(section: WorkSection, lower_tasks: list[Task]) -> dict[str, list[Task]]:
    tasks_by_structure: dict[str, list[Task]] = defaultdict(list)
    for task in lower_tasks:
        tasks_by_structure[task.structure_id].append(task)

    result: dict[str, list[Task]] = {}
    for structure in section.structures:
        completion_tasks = _select_lower_completion_tasks(structure, tasks_by_structure.get(structure.id, []))
        if not completion_tasks:
            continue
        for key in _support_keys_for_structure(structure):
            result[key] = completion_tasks
    return result


def _select_lower_completion_tasks(structure: StructureModel, tasks: list[Task]) -> list[Task]:
    if not tasks:
        return []
    priority_by_structure = {
        "pier": ["cap_beam", "middle_tie_beam", "pier_body", "cap", "ground_tie_beam", "spread_foundation", "pile"],
        "abutment": ["abutment_body", "cap", "spread_foundation", "pile"],
    }
    for component_type in priority_by_structure.get(structure.structure_type, []):
        matches = [task for task in tasks if task.component_type == component_type]
        if matches:
            return matches
    return tasks


def _support_keys_for_structure(structure: StructureModel) -> set[str]:
    keys: set[str] = set()
    for value in (structure.support_no, structure.name):
        normalized = _normalize_support_label(value)
        if normalized:
            keys.add(normalized)
    if structure.support_index is not None:
        label = "墩" if structure.structure_type == "pier" else "台"
        keys.add(f"{structure.support_index}#{label}")
    return keys


def _support_refs_from_upper(upper: UpperStructureComponent) -> list[str]:
    refs = _parse_support_refs(upper.support_range)
    if refs:
        return refs
    left_index = upper.span_index - 1
    return [_support_label_from_index(left_index, is_left_edge=True), f"{upper.span_index}#墩"]


def _support_refs_for_upper_group(uppers: list[UpperStructureComponent]) -> list[str]:
    refs: list[str] = []
    for upper in sorted(uppers, key=lambda item: item.span_index):
        refs.extend(_support_refs_from_upper(upper))
    return _dedupe_support_refs(refs)


def _edge_support_refs(uppers: list[UpperStructureComponent], *, edge: str) -> list[str]:
    ordered = sorted(uppers, key=lambda item: item.span_index)
    if not ordered:
        return []
    edge_upper = ordered[0] if edge == "left" else ordered[-1]
    refs = _parse_support_refs(edge_upper.support_range)
    if refs:
        return [refs[0] if edge == "left" else refs[-1]]
    if edge == "left":
        return [_support_label_from_index(edge_upper.span_index - 1, is_left_edge=True)]
    return [f"{edge_upper.span_index}#墩"]


def _parse_support_refs(support_range: str) -> list[str]:
    refs: list[str] = []
    for match in re.finditer(r"(\d+)\s*(?:#|号)?\s*(墩|台)", support_range):
        refs.append(f"{int(match.group(1))}#{match.group(2)}")
    return _dedupe_support_refs(refs)


def _dedupe_support_refs(refs: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        normalized = _normalize_support_label(ref)
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped


def _normalize_support_label(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace(" ", "").replace("号", "#")
    for match in re.finditer(r"(\d+)\s*#?\s*(墩|台)", text):
        return f"{int(match.group(1))}#{match.group(2)}"
    return text or None


def _support_label_from_index(index: int, *, is_left_edge: bool = False) -> str:
    if index == 0 and is_left_edge:
        return "0#台"
    return f"{index}#墩"


def _cast_in_place_box_beam_groups(upper_structures: list[UpperStructureComponent]) -> list[list[UpperStructureComponent]]:
    groups: dict[int, list[UpperStructureComponent]] = defaultdict(list)
    for upper in upper_structures:
        if not _is_cast_in_place_box_beam_upper(upper):
            continue
        groups[_upper_group_index([upper])].append(upper)
    return [
        sorted(group, key=lambda item: item.span_index)
        for _, group in sorted(groups.items(), key=lambda item: (min(upper.span_index for upper in item[1]), item[0]))
    ]


def _is_simple_beam_upper(upper: UpperStructureComponent) -> bool:
    structure_code = upper.properties.get("structure_code")
    if structure_code == SIMPLE_BEAM_STRUCTURE_CODE:
        return True
    if _is_continuous_beam_upper(upper) or _is_cast_in_place_box_beam_upper(upper):
        return False
    return "简支" in upper.structure_type or "T梁" in upper.structure_type


def _is_cast_in_place_box_beam_upper(upper: UpperStructureComponent) -> bool:
    structure_code = upper.properties.get("structure_code")
    if structure_code == CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE:
        return True
    return "现浇" in upper.structure_type and "箱梁" in upper.structure_type and not _is_continuous_beam_upper(upper)


def _upper_group_index(uppers: list[UpperStructureComponent]) -> int:
    value = uppers[0].properties.get("group_index")
    try:
        return int(value)
    except (TypeError, ValueError):
        return uppers[0].span_index


def _build_continuous_beam_tasks(
    *,
    bridge: ProjectBridge,
    section: WorkSection,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    support_completions: dict[str, list[Task]],
    link_start: int,
    upper_logic_rules: dict[str, UpperStructureLogicRule],
    task_overrides: dict[str, TaskOverride],
) -> tuple[list[Task], list[PrecedenceLink]]:
    tasks: list[Task] = []
    links: list[PrecedenceLink] = []
    for uppers in _continuous_beam_groups(section.upper_structures):
        group_index = _continuous_group_index(uppers)
        span_indices = sorted({upper.span_index for upper in uppers})
        main_supports = _continuous_main_supports(uppers, span_indices)
        if not main_supports:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=uppers[0].id,
                    message=f"{section.name}连续梁组 {group_index} 未识别到主墩，已跳过现浇连续梁任务生成。",
                )
            )
            continue

        standard_cycles, used_default_cycles = _continuous_int_setting(
            uppers,
            ["standard_segment_cycles", "standard_block_cycles", "standard_blocks_per_side"],
            default=CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES,
            minimum=0,
        )
        if used_default_cycles:
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=uppers[0].id,
                    message=(
                        f"{section.name}连续梁组 {group_index} 未配置标准块循环数，"
                        f"已按 {standard_cycles} 个挂篮循环生成。"
                    ),
                )
            )

        group_tasks, group_links = _build_continuous_beam_group_tasks(
            bridge=bridge,
            section=section,
            uppers=uppers,
            group_index=group_index,
            main_supports=main_supports,
            standard_cycles=standard_cycles,
            process_library=process_library,
            validation=validation,
            support_completions=support_completions,
            link_start=link_start + len(links),
            upper_logic_rules=upper_logic_rules,
            task_overrides=task_overrides,
        )
        tasks.extend(group_tasks)
        links.extend(group_links)
    return tasks, links


def _build_continuous_beam_group_tasks(
    *,
    bridge: ProjectBridge,
    section: WorkSection,
    uppers: list[UpperStructureComponent],
    group_index: int,
    main_supports: list[int],
    standard_cycles: int,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    support_completions: dict[str, list[Task]],
    link_start: int,
    upper_logic_rules: dict[str, UpperStructureLogicRule],
    task_overrides: dict[str, TaskOverride],
) -> tuple[list[Task], list[PrecedenceLink]]:
    side_code = _side_code(section.side)
    side_label = _side_label(section.side)
    prefix = f"{bridge.id}-{side_code}-CB-G{group_index:02d}"
    group_label = f"{side_label}连续梁" if side_label else "连续梁"
    base_order = 100000 + group_index * 10000
    tasks: list[Task] = []
    links: list[PrecedenceLink] = []
    link_no = link_start

    def add_link(predecessor: Task | None, successor: Task | None, source_rule_id: str) -> None:
        nonlocal link_no
        if predecessor is None or successor is None:
            return
        rule = _upper_structure_logic_rule(upper_logic_rules, source_rule_id)
        links.append(
            PrecedenceLink(
                id=f"LCB-{bridge.id}-{section.id}-{group_index:02d}-{link_no:04d}",
                predecessor_id=predecessor.id,
                successor_id=successor.id,
                relationship=rule.relationship,
                lag_days=rule.lag_days,
                source_rule_id=source_rule_id,
                severity=rule.severity,
            )
        )
        link_no += 1

    t_completion_tasks: list[Task | None] = []
    for t_index, support_index in enumerate(main_supports, start=1):
        structure_id = f"{prefix}-T{t_index:02d}-P{support_index:02d}"
        structure_name = f"{group_label}{support_index}#墩T构"
        previous = _append_continuous_task(
            tasks=tasks,
            component_id=f"{structure_id}-ZERO",
            name=f"{structure_name}-0号块",
            method_id="zero_block",
            quantity_label="1块",
            bridge_id=bridge.id,
            work_section_id=section.id,
            sequence_order=base_order + t_index * 1000,
            structure_id=structure_id,
            structure_name=structure_name,
            process_library=process_library,
            validation=validation,
            task_overrides=task_overrides,
            properties={
                "continuous_task_type": "zero_block",
                "group_index": group_index,
                "support_index": support_index,
                "t_index": t_index,
            },
        )
        zero_block_links = _build_lower_to_upper_links(
            successor=previous,
            support_refs=[f"{support_index}#墩"],
            support_completions=support_completions,
            source_rule_id="continuous_beam_zero_block_after_main_pier_lower_structure",
            link_prefix=f"LUB-{bridge.id}-{section.id}-CB-G{group_index:02d}-T{t_index:02d}",
            validation=validation,
            start_index=link_no,
            upper_logic_rules=upper_logic_rules,
        )
        links.extend(zero_block_links)
        link_no += len(zero_block_links)
        if standard_cycles > 0:
            current = _append_continuous_task(
                tasks=tasks,
                component_id=f"{structure_id}-STD",
                name=f"{structure_name}-标准段{standard_cycles}块",
                method_id="standard_segment",
                quantity=standard_cycles,
                quantity_label=f"{standard_cycles}块",
                bridge_id=bridge.id,
                work_section_id=section.id,
                sequence_order=base_order + t_index * 1000 + 1,
                structure_id=structure_id,
                structure_name=structure_name,
                process_library=process_library,
                validation=validation,
                task_overrides=task_overrides,
                properties={
                    "continuous_task_type": "standard_segment_batch",
                    "group_index": group_index,
                    "support_index": support_index,
                    "t_index": t_index,
                    "standard_block_count": standard_cycles,
                    "synchronizes_left_right_cantilevers": True,
                },
            )
            add_link(previous, current, "continuous_beam_t_chain")
            if current is not None:
                previous = current
        t_completion_tasks.append(previous)

    left_edge_structure_name = f"{group_label}{main_supports[0]}#墩T构"
    right_edge_structure_name = f"{group_label}{main_supports[-1]}#墩T构"

    left_straight = _append_continuous_task(
        tasks=tasks,
        component_id=f"{prefix}-LEFT-STRAIGHT",
        name=f"{left_edge_structure_name}-边跨连续段",
        method_id="straight_segment",
        quantity_label="1段",
        bridge_id=bridge.id,
        work_section_id=section.id,
        sequence_order=base_order + 9000,
        structure_id=f"{prefix}-LEFT-P{main_supports[0]:02d}",
        structure_name=left_edge_structure_name,
        process_library=process_library,
        validation=validation,
        task_overrides=task_overrides,
        properties={"continuous_task_type": "side_straight_segment", "group_index": group_index, "side": "left"},
    )
    left_closure = _append_continuous_task(
        tasks=tasks,
        component_id=f"{prefix}-LEFT-CLOSURE",
        name=f"{left_edge_structure_name}-边跨合龙段",
        method_id="closure_segment",
        quantity_label="1段",
        bridge_id=bridge.id,
        work_section_id=section.id,
        sequence_order=base_order + 9100,
        structure_id=f"{prefix}-LEFT-P{main_supports[0]:02d}",
        structure_name=left_edge_structure_name,
        process_library=process_library,
        validation=validation,
        task_overrides=task_overrides,
        properties={"continuous_task_type": "side_closure_segment", "group_index": group_index, "side": "left"},
    )
    right_straight = _append_continuous_task(
        tasks=tasks,
        component_id=f"{prefix}-RIGHT-STRAIGHT",
        name=f"{right_edge_structure_name}-边跨连续段",
        method_id="straight_segment",
        quantity_label="1段",
        bridge_id=bridge.id,
        work_section_id=section.id,
        sequence_order=base_order + 9200,
        structure_id=f"{prefix}-RIGHT-P{main_supports[-1]:02d}",
        structure_name=right_edge_structure_name,
        process_library=process_library,
        validation=validation,
        task_overrides=task_overrides,
        properties={"continuous_task_type": "side_straight_segment", "group_index": group_index, "side": "right"},
    )
    right_closure = _append_continuous_task(
        tasks=tasks,
        component_id=f"{prefix}-RIGHT-CLOSURE",
        name=f"{right_edge_structure_name}-边跨合龙段",
        method_id="closure_segment",
        quantity_label="1段",
        bridge_id=bridge.id,
        work_section_id=section.id,
        sequence_order=base_order + 9300,
        structure_id=f"{prefix}-RIGHT-P{main_supports[-1]:02d}",
        structure_name=right_edge_structure_name,
        process_library=process_library,
        validation=validation,
        task_overrides=task_overrides,
        properties={"continuous_task_type": "side_closure_segment", "group_index": group_index, "side": "right"},
    )
    add_link(left_straight, left_closure, "continuous_beam_side_closure")
    left_boundary_refs = _edge_support_refs(uppers, edge="left")
    left_straight_links = _build_lower_to_upper_links(
        successor=left_straight,
        support_refs=left_boundary_refs,
        support_completions=support_completions,
        source_rule_id="continuous_beam_side_straight_after_edge_lower_structure",
        link_prefix=f"LUB-{bridge.id}-{section.id}-CB-G{group_index:02d}-LEFT",
        validation=validation,
        start_index=link_no,
        upper_logic_rules=upper_logic_rules,
    )
    links.extend(left_straight_links)
    link_no += len(left_straight_links)
    add_link(t_completion_tasks[0], left_closure, "continuous_beam_side_closure")
    add_link(right_straight, right_closure, "continuous_beam_side_closure")
    right_boundary_refs = _edge_support_refs(uppers, edge="right")
    right_straight_links = _build_lower_to_upper_links(
        successor=right_straight,
        support_refs=right_boundary_refs,
        support_completions=support_completions,
        source_rule_id="continuous_beam_side_straight_after_edge_lower_structure",
        link_prefix=f"LUB-{bridge.id}-{section.id}-CB-G{group_index:02d}-RIGHT",
        validation=validation,
        start_index=link_no,
        upper_logic_rules=upper_logic_rules,
    )
    links.extend(right_straight_links)
    link_no += len(right_straight_links)
    add_link(t_completion_tasks[-1], right_closure, "continuous_beam_side_closure")

    mid_closures: list[Task | None] = []
    for closure_index, (left_support, right_support) in enumerate(zip(main_supports, main_supports[1:]), start=1):
        mid_closure = _append_continuous_task(
            tasks=tasks,
            component_id=f"{prefix}-MID-{closure_index:02d}-CLOSURE",
            name=f"{group_label}{left_support}#墩-{right_support}#墩-中跨合龙{closure_index}",
            method_id="closure_segment",
            quantity_label="1段",
            bridge_id=bridge.id,
            work_section_id=section.id,
            sequence_order=base_order + 9400 + closure_index,
            structure_id=f"{prefix}-MID-{closure_index:02d}-P{left_support:02d}-P{right_support:02d}",
            structure_name=f"{group_label}{left_support}#墩-{right_support}#墩中跨",
            process_library=process_library,
            validation=validation,
            task_overrides=task_overrides,
            properties={
                "continuous_task_type": "middle_closure_segment",
                "group_index": group_index,
                "closure_index": closure_index,
                "left_support_index": left_support,
                "right_support_index": right_support,
            },
        )
        add_link(t_completion_tasks[closure_index - 1], mid_closure, "continuous_beam_middle_closure")
        add_link(t_completion_tasks[closure_index], mid_closure, "continuous_beam_middle_closure")
        add_link(left_closure, mid_closure, "continuous_beam_edge_before_middle_closure")
        add_link(right_closure, mid_closure, "continuous_beam_edge_before_middle_closure")
        mid_closures.append(mid_closure)

    middle_closure_levels = _middle_closure_levels(uppers, len(mid_closures))
    for previous_level, current_level in zip(middle_closure_levels, middle_closure_levels[1:]):
        for predecessor_index in previous_level:
            for successor_index in current_level:
                add_link(
                    mid_closures[predecessor_index - 1],
                    mid_closures[successor_index - 1],
                    "continuous_beam_middle_closure_sequence",
                )

    return tasks, links


def _append_continuous_task(
    *,
    tasks: list[Task],
    component_id: str,
    name: str,
    method_id: str,
    quantity_label: str,
    quantity: float = 1,
    bridge_id: str,
    work_section_id: str,
    sequence_order: int,
    structure_id: str,
    structure_name: str,
    process_library: list[ProcessTemplate],
    validation: list[ValidationMessage],
    properties: dict[str, Any],
    task_overrides: dict[str, TaskOverride] | None = None,
) -> Task | None:
    component = _apply_task_override(ComponentModel(
        id=component_id,
        name=name,
        component_type=CONTINUOUS_BEAM_COMPONENT_TYPE,
        quantity=quantity,
        quantity_label=quantity_label,
        method_id=method_id,
        properties=properties,
    ), task_overrides or {})
    task = _task_from_component(
        component=component,
        process_library=process_library,
        validation=validation,
        bridge_id=bridge_id,
        work_section_id=work_section_id,
        sequence_order=sequence_order,
        structure_id=structure_id,
        structure_name=structure_name,
        structure_type="continuous_beam",
    )
    if task is not None:
        tasks.append(task)
    return task


def _continuous_beam_groups(upper_structures: list[UpperStructureComponent]) -> list[list[UpperStructureComponent]]:
    groups: dict[int, list[UpperStructureComponent]] = defaultdict(list)
    for upper in upper_structures:
        if not _is_continuous_beam_upper(upper):
            continue
        groups[_continuous_group_index([upper])].append(upper)
    return [
        sorted(group, key=lambda item: item.span_index)
        for _, group in sorted(groups.items(), key=lambda item: (min(upper.span_index for upper in item[1]), item[0]))
    ]


def _is_continuous_beam_upper(upper: UpperStructureComponent) -> bool:
    structure_code = upper.properties.get("structure_code")
    if structure_code == CONTINUOUS_BEAM_STRUCTURE_CODE:
        return True
    return any(keyword in upper.structure_type for keyword in ("连续", "刚构"))


def _continuous_group_index(uppers: list[UpperStructureComponent]) -> int:
    value = uppers[0].properties.get("group_index")
    try:
        return int(value)
    except (TypeError, ValueError):
        return uppers[0].span_index


def _continuous_main_supports(uppers: list[UpperStructureComponent], span_indices: list[int]) -> list[int]:
    configured = _continuous_list_setting(uppers, ["main_support_indices", "main_pier_indices"])
    if configured:
        return sorted(configured)
    if len(span_indices) < 2:
        return []
    return list(range(min(span_indices), max(span_indices)))


def _middle_closure_levels(uppers: list[UpperStructureComponent], middle_count: int) -> list[list[int]]:
    if middle_count <= 1:
        return [[index] for index in range(1, middle_count + 1)]
    configured = _continuous_nested_list_setting(uppers, ["middle_closure_sequence", "mid_span_closure_sequence"])
    if configured:
        return _valid_middle_closure_levels(configured, middle_count)
    strategy = str(_continuous_setting(uppers, ["middle_closure_order", "mid_span_closure_order", "closure_order"]) or "side_to_center")
    if strategy in {"left_to_right", "one_side_to_other"}:
        return [[index] for index in range(1, middle_count + 1)]
    if strategy == "right_to_left":
        return [[index] for index in range(middle_count, 0, -1)]

    levels: list[list[int]] = []
    left = 1
    right = middle_count
    while left <= right:
        if left == right:
            levels.append([left])
        else:
            levels.append([left, right])
        left += 1
        right -= 1
    return levels


def _valid_middle_closure_levels(levels: list[list[int]], middle_count: int) -> list[list[int]]:
    valid_levels: list[list[int]] = []
    seen: set[int] = set()
    for level in levels:
        valid_level = []
        for index in level:
            if 1 <= index <= middle_count and index not in seen:
                valid_level.append(index)
                seen.add(index)
        if valid_level:
            valid_levels.append(valid_level)
    for index in range(1, middle_count + 1):
        if index not in seen:
            valid_levels.append([index])
    return valid_levels


def _continuous_int_setting(
    uppers: list[UpperStructureComponent],
    keys: list[str],
    *,
    default: int,
    minimum: int,
) -> tuple[int, bool]:
    value = _continuous_setting(uppers, keys)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default, True
    return max(minimum, parsed), False


def _continuous_list_setting(uppers: list[UpperStructureComponent], keys: list[str]) -> list[int]:
    value = _continuous_setting(uppers, keys)
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _continuous_nested_list_setting(uppers: list[UpperStructureComponent], keys: list[str]) -> list[list[int]]:
    value = _continuous_setting(uppers, keys)
    if not isinstance(value, list):
        return []
    if all(not isinstance(item, list) for item in value):
        return [[item] for item in _continuous_list_setting_from_value(value)]
    result: list[list[int]] = []
    for level in value:
        if isinstance(level, list):
            parsed = _continuous_list_setting_from_value(level)
            if parsed:
                result.append(parsed)
    return result


def _continuous_list_setting_from_value(value: list[Any]) -> list[int]:
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _continuous_setting(uppers: list[UpperStructureComponent], keys: list[str]) -> Any:
    for upper in uppers:
        nested = upper.properties.get("continuous_beam")
        if isinstance(nested, dict):
            for key in keys:
                if key in nested and nested[key] is not None:
                    return nested[key]
        for key in keys:
            if key in upper.properties and upper.properties[key] is not None:
                return upper.properties[key]
    return None


def _side_code(side: str) -> str:
    return {"left": "L", "right": "R", "none": "N"}.get(side, "N")


def _side_label(side: str) -> str:
    return {"left": "左幅", "right": "右幅", "none": ""}.get(side, "")


def _select_process(component: ComponentModel, process_library: list[ProcessTemplate]) -> ProcessTemplate | None:
    candidates = [process for process in process_library if process.component_type == component.component_type]
    if component.method_id:
        for process in candidates:
            if process.id == component.method_id or process.method_id == component.method_id:
                return process
        return None
    defaults = [process for process in candidates if process.is_default]
    return defaults[0] if defaults else (candidates[0] if candidates else None)


def _process_to_productivity_rule(process: ProcessTemplate, component: ComponentModel) -> ProductivityRule:
    option = _select_productivity_option(process, component)
    duration_method = option.duration_method
    quantity_source = option.quantity_source
    if component.component_type == CONTINUOUS_BEAM_COMPONENT_TYPE and component.method_id == "standard_segment":
        duration_method = "days_per_unit"
        quantity_source = "count"
    return ProductivityRule(
        id=f"{process.id}:{option.id}",
        component_type=process.component_type,
        process_name=process.process_name,
        group_name=option.name,
        duration_method=duration_method,
        quantity_source=quantity_source,
        productivity_value=option.productivity_value,
        productivity_unit=option.productivity_unit,
        standard_section_height_m=option.standard_section_height_m,
        resource_type=process.resource_type,
        is_default=process.is_default,
    )


def _select_productivity_option(process: ProcessTemplate, component: ComponentModel) -> ProductivityOption:
    if component.productivity_option_id:
        for option in process.productivity_options:
            if option.id == component.productivity_option_id:
                return option
    return _default_productivity_option(process)


def _default_productivity_option(process: ProcessTemplate) -> ProductivityOption:
    return next((option for option in process.productivity_options if option.is_default), process.productivity_options[0])


def _quantity_for_process(component: ComponentModel, quantity_source: str) -> tuple[float, str]:
    if quantity_source == "count":
        if component.component_type == CONTINUOUS_BEAM_COMPONENT_TYPE and component.method_id == "standard_segment":
            return float(component.quantity), component.quantity_label or f"{component.quantity:g}块"
        if component.component_type == "pile":
            return 1.0, "1根"
        return 1.0, component.quantity_label or ("1根" if component.component_type == "pile" else "1个")
    if quantity_source == "pile_length_m":
        length = _dimension_value(component, "lengthM") or component.quantity
        return float(length), component.quantity_label or f"{length:g}m"
    if quantity_source == "pier_height_m":
        height = _dimension_value(component, "heightM") or component.quantity
        return float(height), component.quantity_label or f"{height:g}m"
    if quantity_source == "deck_length_m":
        length = (
            _dimension_value(component, "lengthM")
            or _dimension_value(component, "totalLengthM")
            or component.quantity
        )
        return float(length), component.quantity_label or f"{length:g}m"
    return component.quantity, component.quantity_label


def _dimension_value(component: ComponentModel, key: str) -> float | None:
    dimensions = component.properties.get("dimensions_m")
    if isinstance(dimensions, dict) and dimensions.get(key) is not None:
        return float(dimensions[key])
    return None


def _build_structure_sequence_links(
    logic_rules: list[LogicRule],
    tasks: list[Task],
    start_index: int,
) -> tuple[list[PrecedenceLink], list[ValidationMessage]]:
    sequence_rules = [rule for rule in logic_rules if rule.scope == "structure_sequence"]
    if not sequence_rules:
        return [], []

    by_section: dict[tuple[str | None, str | None], dict[str, list[Task]]] = defaultdict(lambda: defaultdict(list))
    for task in tasks:
        by_section[(task.bridge_id, task.work_section_id)][task.structure_id].append(task)

    links: list[PrecedenceLink] = []
    validation: list[ValidationMessage] = []
    link_no = start_index
    for structures in by_section.values():
        ordered_structures = sorted(
            structures.items(),
            key=lambda item: min(task.sequence_order for task in item[1]),
        )
        for previous, current in zip(ordered_structures, ordered_structures[1:]):
            previous_tasks = previous[1]
            current_tasks = current[1]
            for rule in sequence_rules:
                predecessors = _select_tasks_by_components(previous_tasks, rule.predecessor_candidates, rule.predecessor_strategy)
                successors = [task for task in current_tasks if task.component_type == rule.to_component]
                if not predecessors or not successors:
                    validation.append(
                        ValidationMessage(
                            level="warning",
                            subject_id=rule.id,
                            message=f"已跳过顺序规则 {rule.id}：未找到对应的前置或后续工作项。",
                        )
                    )
                    continue
                for predecessor in predecessors:
                    for successor in successors:
                        links.append(
                            PrecedenceLink(
                                id=f"L{link_no:04d}",
                                predecessor_id=predecessor.id,
                                successor_id=successor.id,
                                relationship=rule.relationship,
                                lag_days=rule.lag_days,
                                source_rule_id=rule.id,
                                severity=rule.severity,
                            )
                        )
                        link_no += 1
    return links, validation


def _select_tasks_by_components(
    tasks: list[Task],
    component_types: list[ComponentType],
    strategy: str,
) -> list[Task]:
    if strategy == "all":
        return [task for task in tasks if task.component_type in component_types]
    for component_type in component_types:
        matches = [task for task in tasks if task.component_type == component_type]
        if matches:
            return matches
    return []


def _validate_calendars(scenario: ScenarioInput) -> list[ValidationMessage]:
    calendar_ids = {calendar.id for calendar in scenario.resource_calendars}
    messages: list[ValidationMessage] = []
    for pool in scenario.resource_pools:
        if pool.calendar_id not in calendar_ids:
            messages.append(
                ValidationMessage(
                    level="warning",
                    subject_id=pool.id,
                    message=f"资源池“{pool.label}”引用的日历 {pool.calendar_id} 不存在，已按连续日历处理。",
                )
            )
    return messages


def _build_diagnostics(
    generation_messages: list[ValidationMessage],
    result: ScheduleResult,
) -> list[ValidationMessage]:
    diagnostics = list(generation_messages)
    diagnostics.extend(result.validation)
    if result.status in {"OPTIMAL", "FEASIBLE"}:
        diagnostics.append(
            ValidationMessage(
                level="info",
                message="场景已基于生成的任务图、资源池和里程碑约束完成求解。",
            )
        )
    return diagnostics


def _scenario_metrics(generated: GeneratedScheduleInput, result: ScheduleResult) -> dict[str, Any]:
    soft_penalty = sum(milestone.penalty for milestone in result.milestone_results if milestone.mode == "soft")
    soft_late = sum(1 for milestone in result.milestone_results if milestone.mode == "soft" and milestone.lateness_days > 0)
    hard_count = sum(1 for milestone in result.milestone_results if milestone.mode == "hard")
    hard_met = sum(1 for milestone in result.milestone_results if milestone.mode == "hard" and milestone.status == "met")
    resource_types = sorted({resource.type for resource in generated.schedule_input.resources})
    return {
        "task_count": len(generated.schedule_input.tasks),
        "logic_link_count": len(generated.schedule_input.precedence_links),
        "resource_count": len(generated.schedule_input.resources),
        "resource_types": resource_types,
        "total_days": result.objective_days,
        "soft_late_count": soft_late,
        "soft_penalty": soft_penalty,
        "hard_milestones_met": hard_met,
        "hard_milestone_count": hard_count,
    }
