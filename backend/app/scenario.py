from __future__ import annotations

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
    ValidationMessage,
)
from .solver import solve_min_resources_schedule, solve_schedule
from .wbs import build_precedence_links, calculate_duration


def generate_schedule_input_from_scenario(scenario: ScenarioInput, *, use_max_resources: bool = False) -> GeneratedScheduleInput:
    validation: list[ValidationMessage] = []
    tasks = _build_tasks(scenario, validation)
    same_structure_rules = [rule for rule in scenario.logic_rules if rule.scope == "same_structure"]
    precedence_links, link_messages = build_precedence_links(tasks, same_structure_rules)
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
        validation.append(ValidationMessage(level="error", message="未生成任何启用的资源。"))

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
                f"{len(resources)} 个命名资源。"
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


def expand_resource_pools(resource_pools: list[ResourcePool], *, use_max_quantity: bool = False) -> tuple[list[Resource], list[ValidationMessage]]:
    resources: list[Resource] = []
    validation: list[ValidationMessage] = []
    for pool in resource_pools:
        if not pool.enabled:
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


def _build_tasks(scenario: ScenarioInput, validation: list[ValidationMessage]) -> list[Task]:
    tasks: list[Task] = []
    for bridge in sorted(scenario.project.bridges, key=lambda item: item.order):
        for section in sorted(bridge.work_sections, key=lambda item: item.order):
            for structure in sorted(section.structures, key=lambda item: item.order):
                for component_index, component in enumerate(structure.components):
                    if not component.enabled:
                        continue
                    process = _select_process(component, scenario.process_library)
                    if process is None:
                        validation.append(
                            ValidationMessage(
                                level="error",
                                subject_id=component.id,
                                message=f"构件“{component.name}”没有匹配的工艺模板。",
                            )
                        )
                        continue
                    if component.quantity <= 0:
                        validation.append(
                            ValidationMessage(
                                level="warning",
                                subject_id=component.id,
                                message=f"构件“{component.name}”的工程量为 0，已跳过。",
                            )
                        )
                        continue

                    rule = _process_to_productivity_rule(process, component)
                    quantity, quantity_label = _quantity_for_process(component, rule.quantity_source)
                    tasks.append(
                        Task(
                            id=component.id,
                            name=component.name,
                            bridge_id=bridge.id,
                            work_section_id=section.id,
                            component_id=component.id,
                            sequence_order=structure.order * 100 + component_index,
                            structure_id=structure.id,
                            structure_name=structure.name,
                            structure_type=structure.structure_type,
                            component_type=component.component_type,
                            process_name=process.process_name,
                            productivity_rule_id=rule.id,
                            quantity=quantity,
                            quantity_label=quantity_label,
                            duration_days=calculate_duration(quantity, rule),
                            compatible_resource_types=[process.resource_type],
                        )
                    )
    return tasks


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
    return ProductivityRule(
        id=f"{process.id}:{option.id}",
        component_type=process.component_type,
        process_name=process.process_name,
        group_name=option.name,
        duration_method=option.duration_method,
        quantity_source=option.quantity_source,
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
        return 1.0, "1根" if component.component_type == "pile" else "1个"
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
