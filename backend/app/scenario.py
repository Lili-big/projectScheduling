from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .models import (
    ComponentModel,
    ComponentType,
    ControlLevel,
    GeneratedScheduleInput,
    LogicRule,
    MinResourcesSolveRequest,
    PrecedenceLink,
    ProcessTemplate,
    ProjectBridge,
    ProductivityOption,
    ProductivityRule,
    Resource,
    ResourceCostSolveRequest,
    ResourcePool,
    ScheduleInput,
    ScheduleResult,
    ScenarioAlternativeResult,
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
from .solver import (
    _apply_resource_limits,
    _critical_path_schedule,
    _resource_groups,
    solve_capacity_shortest_schedule,
    solve_control_priority_schedule,
    solve_min_resources_schedule,
    solve_resource_cost_schedule,
)
from .wbs import build_precedence_links, calculate_duration


CONTINUOUS_BEAM_STRUCTURE_CODE = "castInPlaceContinuousBoxGirder"
CONTINUOUS_BEAM_COMPONENT_TYPE = "cast_in_place_continuous_beam"
CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES = 18
CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE = "castInPlaceBoxGirder"
SIMPLE_BEAM_STRUCTURE_CODE = "precastTGirder"
FIXED_RESOURCE_SOLVE_MODE = "fixed_resources_shortest_control_balanced"
MINIMUM_RESOURCES_REFINED_SOURCE = "minimum_resources_control_priority_balanced"
MINIMUM_RESOURCES_FALLBACK_SOURCE = "minimum_resources_refinement_fallback"
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


class _FixedResourceSolveBudget:
    def __init__(self, time_limit_seconds: float) -> None:
        self.time_limit_seconds = time_limit_seconds

    def with_time_limit(self, schedule_input: ScheduleInput, **_: Any) -> ScheduleInput:
        return schedule_input.model_copy(update={"time_limit_seconds": self.time_limit_seconds})


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
        schedule_strategy=scenario.schedule_strategy,
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
    alternative_results: list[ScenarioAlternativeResult] = []
    if any(message.level == "error" for message in generated.validation):
        result = ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=scenario.project.start_date,
            validation=generated.validation,
            stats={"reason": "scenario_generation_error"},
            milestone_results=[],
        )
    else:
        result, alternative_results = _solve_fixed_resources_shortest_scenario(scenario, generated)

    diagnostics = _build_diagnostics(generated.validation, result)
    return ScenarioSolveResult(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.scenario_name,
        generated=generated,
        result=result,
        milestone_results=result.milestone_results,
        diagnostics=diagnostics,
        metrics=_scenario_metrics(generated, result),
        alternative_results=alternative_results,
    )


def _solve_fixed_resources_shortest_scenario(
    scenario: ScenarioInput,
    generated: GeneratedScheduleInput,
) -> tuple[ScheduleResult, list[ScenarioAlternativeResult]]:
    critical_path = _critical_path_schedule(generated.schedule_input)
    baseline_input = _schedule_input_with_strategy(generated.schedule_input, "shortest_duration")
    baseline_result = solve_capacity_shortest_schedule(baseline_input)
    if baseline_result.status not in {"OPTIMAL", "FEASIBLE"}:
        _apply_fixed_resource_metadata(
            baseline_result,
            baseline_makespan_days=baseline_result.objective_days,
            hard_milestone_feasible=False,
            resource_recommendation_status="not_evaluated",
            resource_recommendation_message="当前资源最短工期排程未得到可行求解结果，无法继续评估硬里程碑和资源增量建议。",
            performance_path="capacity_fast_path_failed",
            solver_call_count=baseline_result.stats.get("solver_call_count", 1),
            capacity_precheck_status=baseline_result.status,
            warm_start_used=False,
        )
        return baseline_result, []

    late_hard = _late_hard_milestones(baseline_result)
    if late_hard:
        result = baseline_result.model_copy(deep=True, update={"status": "INFEASIBLE"})
        result.validation = list(baseline_result.validation)
        result.validation.append(
            ValidationMessage(
                level="error",
                message="当前固定资源最短工期排程未满足强制里程碑；已保留当前资源排程供查看，并尝试测算资源增量建议。",
            )
        )
        for milestone in late_hard:
            result.validation.append(
                ValidationMessage(
                    level="error",
                    subject_id=milestone.id,
                    message=(
                        f"强制里程碑“{milestone.name}”目标 {milestone.target_date}，"
                        f"当前固定资源最短排程预计 {milestone.actual_date}，迟延 {milestone.lateness_days} 天。"
                    ),
                )
            )
        recommendation = _fixed_resource_recommendation(
            scenario,
            generated.schedule_input,
            critical_path=critical_path,
        )
        recommendation_metadata = {
            key: value
            for key, value in recommendation["metadata"].items()
            if key != "alternative_result"
        }
        skipped_reason = (
            "critical_path_infeasible"
            if recommendation_metadata.get("resource_recommendation_status") == "critical_path_infeasible"
            else "current_resources_late_hard_milestone"
        )
        _apply_fixed_resource_metadata(
            result,
            baseline_makespan_days=baseline_result.objective_days,
            hard_milestone_feasible=False,
            schedule_source="current_resources_capacity_shortest",
            performance_path="capacity_fast_path_resource_recommendation",
            solver_call_count=baseline_result.stats.get("solver_call_count", 1),
            capacity_precheck_status=baseline_result.status,
            warm_start_used=False,
            skipped_named_refinement_reason=skipped_reason,
            **recommendation_metadata,
        )
        result.validation.extend(recommendation["validation"])
        alternative = recommendation.get("alternative_result")
        alternatives = [alternative] if alternative is not None else []
        return result, alternatives

    final_input = _schedule_input_with_strategy(generated.schedule_input, "comprehensive")
    final_result = solve_control_priority_schedule(
        final_input,
        enforce_hard_milestones=True,
        baseline_result=baseline_result,
        warm_start_result=baseline_result,
    )
    if final_result.status in {"OPTIMAL", "FEASIBLE"}:
        _apply_fixed_resource_metadata(
            final_result,
            baseline_makespan_days=baseline_result.objective_days,
            hard_milestone_feasible=True,
            schedule_source="current_resources_control_priority_balanced",
            performance_path="capacity_fast_path_named_refinement",
            solver_call_count=int(baseline_result.stats.get("solver_call_count", 1) or 1) + 1,
            capacity_precheck_status=baseline_result.status,
            warm_start_used=bool(final_result.stats.get("warm_start_used")),
            resource_recommendation_status="not_needed",
            resource_recommendation_message="当前固定资源最短工期已满足强制里程碑，无需增加资源。",
        )
        return final_result, []

    fallback = baseline_result.model_copy(deep=True)
    fallback.validation = list(baseline_result.validation) + list(final_result.validation)
    fallback.validation.append(
        ValidationMessage(
            level="warning",
            message="控制优先+均衡推进在硬里程碑约束下未得到可行二次优化结果，已回退展示当前资源最短工期排程。",
        )
    )
    _apply_fixed_resource_metadata(
        fallback,
        baseline_makespan_days=baseline_result.objective_days,
        hard_milestone_feasible=True,
        schedule_source="current_resources_capacity_shortest_fallback",
        performance_path="capacity_fast_path_named_refinement_fallback",
        solver_call_count=int(baseline_result.stats.get("solver_call_count", 1) or 1) + 1,
        capacity_precheck_status=baseline_result.status,
        warm_start_used=bool(final_result.stats.get("warm_start_used")),
        skipped_named_refinement_reason=f"control_priority_{final_result.status.lower()}",
        resource_recommendation_status="not_needed",
        resource_recommendation_message="当前固定资源最短工期已满足强制里程碑，无需增加资源。",
    )
    fallback_reason = f"control_priority_{final_result.status.lower()}"
    fallback.stats["control_priority_analysis"] = {
        "fallback_reason": fallback_reason,
        "control_buffer_status": "not_evaluated",
        "normal_balance_status": "not_evaluated",
        "resource_path_status": "not_evaluated",
        "control_objects": [],
        "control_object_tasks": [],
        "control_chain_predecessors": [],
        "control_targets": [],
        "control_buffer_risks": [],
        "path_group_diagnostics": [],
    }
    fallback.objective_breakdown["control_priority_analysis"] = fallback.stats["control_priority_analysis"]
    return fallback, []


def _schedule_input_with_strategy(schedule_input: ScheduleInput, strategy: str) -> ScheduleInput:
    return schedule_input.model_copy(
        update={
            "schedule_strategy": schedule_input.schedule_strategy.model_copy(update={"strategy": strategy})
        }
    )


def _late_hard_milestones(result: ScheduleResult) -> list[Any]:
    return [
        milestone
        for milestone in result.milestone_results
        if milestone.mode == "hard" and milestone.lateness_days > 0
    ]


def _fixed_resource_recommendation(
    scenario: ScenarioInput,
    current_schedule_input: ScheduleInput,
    *,
    critical_path: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if critical_path is None:
        critical_path = _critical_path_schedule(current_schedule_input)
    critical_metadata = _critical_path_metadata(critical_path)
    if critical_path.get("status") != "OK":
        return {
            "metadata": {
                **critical_metadata,
                "resource_recommendation_status": "critical_path_unknown",
                "resource_recommendation_message": "无法计算工艺逻辑关键路径，请先检查工艺逻辑是否存在闭环或不可满足约束。",
                "recommended_resource_counts": [],
            },
            "validation": [
                ValidationMessage(
                    level="error",
                    message="无法计算工艺逻辑关键路径，请检查工艺逻辑是否存在闭环或不可满足约束。",
                )
            ],
        }

    critical_late_hard = _late_hard_milestones_from_results(critical_path["milestone_results"])
    if critical_late_hard:
        messages = [
            ValidationMessage(
                level="error",
                message="不考虑资源排队时，工艺逻辑关键路径仍无法满足强制里程碑；增加资源也无法满足当前工期目标。",
            )
        ]
        for milestone in critical_late_hard:
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
        return {
            "metadata": {
                **critical_metadata,
                "resource_recommendation_status": "critical_path_infeasible",
                "resource_recommendation_message": "关键控制链理论最短工期已经突破强制里程碑，增加资源也无法满足当前工期目标。",
                "recommended_resource_counts": [],
            },
            "validation": messages,
        }

    max_generated = generate_schedule_input_from_scenario(scenario, use_max_resources=True)
    if any(message.level == "error" for message in max_generated.validation):
        return {
            "metadata": {
                **critical_metadata,
                "resource_recommendation_status": "max_resource_generation_error",
                "resource_recommendation_message": "资源增量建议生成失败：最大资源场景存在生成错误。",
                "recommended_resource_counts": [],
            },
            "validation": max_generated.validation,
        }

    max_schedule_input = max_generated.schedule_input
    resource_upper_bounds = _resource_upper_bound_counts(current_schedule_input, max_schedule_input)
    min_resource_result = solve_min_resources_schedule(max_schedule_input)
    if _min_resource_result_has_verified_recommendation(min_resource_result):
        fixed_counts = _resource_count_map(min_resource_result)
        recommendation = _enriched_resource_counts(
            current_schedule_input=current_schedule_input,
            max_schedule_input=max_schedule_input,
            fixed_counts=fixed_counts,
        )
        candidate_result = min_resource_result.model_copy(deep=True)
        recommendation_metadata = {
            "resource_recommendation_status": "recommended_resources_verified",
            "resource_recommendation_message": "已输出固定工期条件下的可行最少资源方案。",
            "recommended_resource_counts": recommendation,
            "resource_upper_bound_counts": resource_upper_bounds,
            "resource_solver_status": min_resource_result.status,
            **_min_resource_recommendation_metadata(min_resource_result),
        }
        limited_schedule_input = max_generated.schedule_input.model_copy(
            update={"resources": _apply_resource_limits(max_generated.schedule_input.resources, fixed_counts)}
        )
        alternative_generated = max_generated.model_copy(update={"schedule_input": limited_schedule_input})
        candidate_result = _minimum_resource_candidate_result(limited_schedule_input, candidate_result)
        candidate_result.stats.update(recommendation_metadata)
        candidate_result.objective_breakdown.update(recommendation_metadata)
        candidate_source = candidate_result.stats.get("schedule_source") or candidate_result.objective_breakdown.get("schedule_source")
        recommendation_metadata["recommended_schedule_source"] = candidate_source
        candidate_result.stats["recommended_schedule_source"] = candidate_source
        candidate_result.objective_breakdown["recommended_schedule_source"] = candidate_source
        alternative = ScenarioAlternativeResult(
            scenario_id=f"{scenario.scenario_id}-minimum-resources",
            scenario_name=f"{scenario.scenario_name} - 最少资源方案",
            role="minimum_resources",
            generated=alternative_generated,
            result=candidate_result,
            milestone_results=candidate_result.milestone_results,
            diagnostics=_build_diagnostics(alternative_generated.validation, candidate_result),
            metrics=_scenario_metrics(alternative_generated, candidate_result),
        )
        return {
            "metadata": {
                **critical_metadata,
                **recommendation_metadata,
                "alternative_result": alternative,
            },
            "alternative_result": alternative,
            "validation": [
                ValidationMessage(
                    level="warning",
                    message="已按固定工期最少资源模型生成方案2；推荐数量已通过固定数量排程验证。",
                )
            ],
        }

    if _min_resource_result_is_upper_bound_infeasible(min_resource_result):
        return {
            "metadata": {
                **critical_metadata,
                "resource_recommendation_status": "resource_upper_bound_infeasible",
                "resource_recommendation_message": "工艺逻辑关键路径可满足目标，但当前资源池最大数量或资源类型结构仍无法满足硬里程碑。",
                "recommended_resource_counts": [],
                "resource_upper_bound_counts": resource_upper_bounds,
                "resource_capacity_lower_bounds": min_resource_result.stats.get("resource_capacity_lower_bounds", []),
                "resource_solver_status": min_resource_result.status,
                **_min_resource_recommendation_metadata(min_resource_result),
            },
            "validation": [
                ValidationMessage(
                    level="error",
                    message="当前资源池最大数量仍无法满足强制里程碑；请提高资源上限或检查资源类型配置。",
                )
            ],
        }

    return {
        "metadata": {
            **critical_metadata,
            "resource_recommendation_status": "resource_recommendation_unresolved",
            "resource_recommendation_message": "最少资源模型未得到可验证结果；当前求解限时内无法确认推荐资源组合。",
            "recommended_resource_counts": [],
            "resource_upper_bound_counts": resource_upper_bounds,
            "resource_capacity_lower_bounds": min_resource_result.stats.get("resource_capacity_lower_bounds", []),
            "resource_solver_status": min_resource_result.status,
            **_min_resource_recommendation_metadata(min_resource_result),
        },
        "validation": [
            ValidationMessage(
                level="warning",
                message="最少资源模型未得到可验证结果；请提高求解限时或检查工作面并行约束、资源上限配置。",
            )
        ],
    }


def _critical_path_metadata(critical_path: dict[str, Any]) -> dict[str, Any]:
    if critical_path.get("status") != "OK":
        return {"critical_path_status": critical_path.get("status")}
    return {
        "critical_path_status": "OK",
        "critical_path_minimum_days": critical_path["objective_days"],
        "critical_path_plan_finish_date": critical_path["plan_finish_date"],
    }


def _late_hard_milestones_from_results(milestone_results: list[Any]) -> list[Any]:
    return [
        milestone
        for milestone in milestone_results
        if milestone.mode == "hard" and milestone.lateness_days > 0
    ]


def _resource_count_map(result: ScheduleResult) -> dict[str, int]:
    raw = result.stats.get("recommended_resource_counts") or result.objective_breakdown.get("recommended_resource_counts") or []
    fixed_counts: dict[str, int] = {}
    for item in raw:
        if isinstance(item, dict):
            fixed_counts[str(item.get("resource_pool_id"))] = int(item.get("recommended_quantity") or 0)
    return fixed_counts


def _min_resource_result_has_verified_recommendation(result: ScheduleResult) -> bool:
    recommended = result.stats.get("recommended_resource_counts") or result.objective_breakdown.get("recommended_resource_counts") or []
    capacity_status = result.stats.get("capacity_verification_status") or result.objective_breakdown.get("capacity_verification_status")
    return result.status in {"OPTIMAL", "FEASIBLE"} and bool(recommended) and capacity_status == "verified"


def _min_resource_result_is_upper_bound_infeasible(result: ScheduleResult) -> bool:
    reason = result.stats.get("reason")
    capacity_status = result.stats.get("capacity_model_status")
    global_status = result.stats.get("global_capacity_model_status")
    return result.status in {"INFEASIBLE", "MODEL_INVALID"} and (
        bool(result.stats.get("fixed_duration_precheck_failed"))
        or reason == "resource_upper_bound_or_deadline_infeasible"
        or capacity_status in {"INFEASIBLE", "MODEL_INVALID"}
        or global_status in {"INFEASIBLE", "MODEL_INVALID"}
    )


def _min_resource_recommendation_metadata(result: ScheduleResult) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        "capacity_verification_status",
        "balanced_reoptimization_status",
        "unbalanced_reoptimization_status",
        "recommended_schedule_source",
        "resource_count_optimality",
        "capacity_model_status",
        "global_capacity_model_status",
        "capacity_model_group_counts",
        "reoptimization_attempts",
        "parallel_reoptimization_used",
    ):
        if key in result.stats:
            metadata[key] = result.stats[key]
    return metadata


def _enriched_resource_counts(
    *,
    current_schedule_input: ScheduleInput,
    max_schedule_input: ScheduleInput,
    fixed_counts: dict[str, int],
) -> list[dict[str, Any]]:
    current_counts = {
        group["key"]: group["max_quantity"]
        for group in _resource_groups([resource for resource in current_schedule_input.resources if resource.enabled])
    }
    max_groups = _resource_groups([resource for resource in max_schedule_input.resources if resource.enabled])
    enriched = []
    for group in max_groups:
        current_quantity = current_counts.get(group["key"], 0)
        recommended_quantity = max(0, min(int(fixed_counts.get(group["key"], 0)), group["max_quantity"]))
        enriched.append(
            {
                "resource_pool_id": group["key"],
                "label": group["label"],
                "resource_type": group["resource_type"],
                "current_quantity": current_quantity,
                "recommended_quantity": recommended_quantity,
                "added_quantity": max(0, recommended_quantity - current_quantity),
                "max_quantity": group["max_quantity"],
            }
        )
    return enriched


def _resource_upper_bound_counts(
    current_schedule_input: ScheduleInput,
    max_schedule_input: ScheduleInput,
) -> list[dict[str, Any]]:
    current_counts = {
        group["key"]: group["max_quantity"]
        for group in _resource_groups([resource for resource in current_schedule_input.resources if resource.enabled])
    }
    upper_bounds = []
    for group in _resource_groups([resource for resource in max_schedule_input.resources if resource.enabled]):
        current_quantity = current_counts.get(group["key"], 0)
        upper_bound_quantity = group["max_quantity"]
        upper_bounds.append(
            {
                "resource_pool_id": group["key"],
                "label": group["label"],
                "resource_type": group["resource_type"],
                "current_quantity": current_quantity,
                "upper_bound_quantity": upper_bound_quantity,
                "additional_capacity": max(0, upper_bound_quantity - current_quantity),
                "max_quantity": upper_bound_quantity,
            }
        )
    return upper_bounds


def _minimum_resource_candidate_result(
    limited_schedule_input: ScheduleInput,
    min_resource_result: ScheduleResult,
) -> ScheduleResult:
    refined_input = _schedule_input_with_strategy(limited_schedule_input, "comprehensive")
    refined_result = solve_control_priority_schedule(
        refined_input,
        enforce_hard_milestones=True,
        baseline_result=min_resource_result,
        warm_start_result=min_resource_result,
    )
    if _result_meets_hard_milestones(refined_result):
        result = refined_result.model_copy(deep=True)
        metadata = {
            "schedule_source": MINIMUM_RESOURCES_REFINED_SOURCE,
            "recommended_schedule_source": MINIMUM_RESOURCES_REFINED_SOURCE,
            "minimum_resource_refinement_status": refined_result.status,
            "minimum_resource_refinement_source": refined_result.stats.get("schedule_source")
            or refined_result.objective_breakdown.get("schedule_source")
            or "control_priority",
            "warm_start_used": bool(refined_result.stats.get("warm_start_used")),
        }
        result.stats.update(metadata)
        result.objective_breakdown.update(metadata)
        return result

    result = min_resource_result.model_copy(deep=True)
    fallback_reason = f"minimum_resource_refinement_{refined_result.status.lower()}"
    result.validation = list(min_resource_result.validation) + list(refined_result.validation)
    result.validation.append(
        ValidationMessage(
            level="warning",
            message="最少资源候选方案的二次精排未在当前时限内返回可用结果，已保留已验证的可行候选排程。",
        )
    )
    metadata = {
        "schedule_source": MINIMUM_RESOURCES_FALLBACK_SOURCE,
        "recommended_schedule_source": MINIMUM_RESOURCES_FALLBACK_SOURCE,
        "minimum_resource_refinement_status": refined_result.status,
        "minimum_resource_refinement_fallback_reason": fallback_reason,
        "skipped_named_refinement_reason": fallback_reason,
    }
    result.stats.update(metadata)
    result.objective_breakdown.update(metadata)
    result.stats.setdefault(
        "control_priority_analysis",
        {
            "fallback_reason": fallback_reason,
            "control_buffer_status": "not_evaluated",
            "normal_balance_status": "not_evaluated",
            "resource_path_status": "not_evaluated",
            "control_objects": [],
            "control_object_tasks": [],
            "control_chain_predecessors": [],
            "control_targets": [],
            "control_buffer_risks": [],
            "path_group_diagnostics": [],
        },
    )
    result.objective_breakdown["control_priority_analysis"] = result.stats["control_priority_analysis"]
    return result


def _verify_recommended_resources(
    max_schedule_input: ScheduleInput,
    fixed_counts: dict[str, int],
    budget: _FixedResourceSolveBudget,
) -> ScheduleResult:
    verification_input = budget.with_time_limit(
        _schedule_input_with_strategy(max_schedule_input, "comprehensive").model_copy(
            update={"resources": _apply_resource_limits(max_schedule_input.resources, fixed_counts)}
        )
    )
    return solve_control_priority_schedule(verification_input, enforce_hard_milestones=True)


def _result_meets_hard_milestones(result: ScheduleResult) -> bool:
    return result.status in {"OPTIMAL", "FEASIBLE"} and not _late_hard_milestones(result)


def _apply_fixed_resource_metadata(
    result: ScheduleResult,
    *,
    baseline_makespan_days: int | None,
    hard_milestone_feasible: bool,
    resource_recommendation_status: str,
    resource_recommendation_message: str,
    recommended_resource_counts: list[dict[str, Any]] | None = None,
    **extra_metadata: Any,
) -> None:
    metadata = {
        "solve_mode": FIXED_RESOURCE_SOLVE_MODE,
        "baseline_makespan_days": baseline_makespan_days,
        "hard_milestone_feasible": hard_milestone_feasible,
        "resource_recommendation_status": resource_recommendation_status,
        "resource_recommendation_message": resource_recommendation_message,
        **extra_metadata,
    }
    if recommended_resource_counts is not None:
        metadata["recommended_resource_counts"] = recommended_resource_counts
    result.stats.update(metadata)
    result.objective_breakdown.update(metadata)


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


def solve_resource_cost_scenario(request: ResourceCostSolveRequest) -> ScenarioSolveResult:
    scenario = request.scenario
    generated = generate_schedule_input_from_scenario(scenario, use_max_resources=True)
    if any(message.level == "error" for message in generated.validation):
        result = ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=scenario.project.start_date,
            validation=generated.validation,
            stats={"reason": "scenario_generation_error", "solve_mode": "resource_cost_optimization"},
            milestone_results=[],
        )
    else:
        result = solve_resource_cost_schedule(
            generated.schedule_input,
            _resource_linear_costs_by_pool(scenario.resource_pools),
            fallback_target_days=request.fallback_target_days,
        )

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
        total_cost = result.objective_breakdown.get("total_cost")
        score = int(total_cost) if feasible and isinstance(total_cost, (int, float)) else ((result.objective_days or 0) + penalty if feasible else None)
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
                "total_cost": total_cost,
                "score": score,
                "resource_count": len(item.generated.schedule_input.resources),
            }
        )
        if score is not None and (best_score is None or score < best_score):
            best_score = score
            best_scenario_id = item.scenario_id

    notes = []
    if best_scenario_id:
        notes.append("推荐方案按资源成本优化的综合成本优先；其他方案按总工期加软里程碑罚分综合选择。")
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
    if task.properties.get("resource_neutral"):
        return []

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
    if not pool or not pool.enabled or pool.resource_mode != "LIMITED":
        return False
    usable_limit = pool.max_quantity if pool.max_quantity is not None else pool.quantity
    return (usable_limit or 0) > 0


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
    usable_limit = pool.max_quantity if pool.max_quantity is not None else pool.quantity
    if (usable_limit or 0) <= 0:
        return "资源上限为 0"
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
                    same_structure_resource_binding=pool.same_structure_resource_binding,
                    same_structure_parallel_limit=pool.same_structure_parallel_limit,
                    parallel_rule_description=pool.parallel_rule_description,
                )
            )
        if quantity == 0:
            quantity_label = "最大数量" if use_max_quantity else "默认数量"
            validation.append(
                ValidationMessage(level="warning", subject_id=pool.id, message=f"资源池“{pool.label}”的{quantity_label}为 0。")
            )
    return resources, validation


def _resource_linear_costs_by_pool(resource_pools: list[ResourcePool]) -> dict[str, dict[str, Any]]:
    costs_by_pool: dict[str, dict[str, Any]] = {}
    for pool in resource_pools:
        if not pool.enabled or pool.resource_mode == "UNLIMITED":
            continue
        current_quantity = pool.quantity or 0
        costs_by_pool[pool.id] = {
            "resource_pool_id": pool.id,
            "label": pool.label,
            "resource_type": pool.type,
            "current_quantity": current_quantity,
            "max_quantity": pool.max_quantity if pool.max_quantity is not None else current_quantity,
            "cost_type": pool.cost_type,
            "incremental_unit_cost": pool.incremental_unit_cost,
            "billing_period_days": pool.billing_period_days,
        }
    return costs_by_pool


def _inferred_control_levels(scenario: ScenarioInput) -> dict[str, ControlLevel]:
    levels: dict[str, ControlLevel] = {}
    highest_pier_id: str | None = None
    highest_pier_height = -1.0

    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            main_supports: set[int] = set()
            for uppers in _continuous_beam_groups(section.upper_structures):
                for upper in uppers:
                    levels[upper.id] = "control"
                span_indices = sorted({upper.span_index for upper in uppers})
                main_supports.update(_continuous_main_supports(uppers, span_indices))

            for structure in section.structures:
                configured = structure.control_level
                if configured is not None:
                    levels[structure.id] = configured
                    continue
                if structure.structure_type == "pier" and _structure_support_index(structure) in main_supports:
                    levels[structure.id] = "control"
                else:
                    levels.setdefault(structure.id, "normal")

                if structure.structure_type != "pier":
                    continue
                height = _structure_pier_height(structure)
                if height is not None and height > highest_pier_height:
                    highest_pier_height = height
                    highest_pier_id = structure.id

    if highest_pier_id and levels.get(highest_pier_id) == "normal":
        levels[highest_pier_id] = "key"
    return levels


def _structure_control_level(structure: StructureModel, inferred_levels: dict[str, ControlLevel]) -> ControlLevel:
    return structure.control_level or inferred_levels.get(structure.id, "normal")


def _upper_group_control_level(
    uppers: list[UpperStructureComponent],
    inferred_levels: dict[str, ControlLevel],
    *,
    default: ControlLevel,
) -> ControlLevel:
    rank = {"control": 0, "key": 1, "normal": 2, "rough": 3}
    candidates = [
        upper.control_level or inferred_levels.get(upper.id)
        for upper in uppers
        if upper.control_level or inferred_levels.get(upper.id)
    ]
    return min(candidates, key=lambda item: rank[item]) if candidates else default


def _structure_support_index(structure: StructureModel) -> int | None:
    if structure.support_index is not None:
        return structure.support_index
    if structure.structure_type == "pier":
        return structure.order
    return None


def _structure_pier_height(structure: StructureModel) -> float | None:
    heights: list[float] = []
    for component in structure.components:
        if component.component_type != "pier_body":
            continue
        for key in ("height_m", "heightM", "pier_height_m", "pierHeightM"):
            raw_value = component.properties.get(key)
            if isinstance(raw_value, (int, float)):
                heights.append(float(raw_value))
        dimensions = component.properties.get("dimensions_m")
        if isinstance(dimensions, dict):
            for key in ("heightM", "height_m"):
                raw_value = dimensions.get(key)
                if isinstance(raw_value, (int, float)):
                    heights.append(float(raw_value))
        if component.quantity > 0:
            heights.append(float(component.quantity))
    return max(heights) if heights else None


def _build_tasks(scenario: ScenarioInput, validation: list[ValidationMessage]) -> tuple[list[Task], list[PrecedenceLink]]:
    tasks: list[Task] = []
    generated_links: list[PrecedenceLink] = []
    upper_logic_rules = _upper_structure_logic_rule_by_id(scenario.upper_structure_logic_rules)
    task_overrides = scenario.task_overrides
    inferred_levels = _inferred_control_levels(scenario)
    for bridge in sorted(scenario.project.bridges, key=lambda item: item.order):
        for section in sorted(bridge.work_sections, key=lambda item: item.order):
            section_lower_start = len(tasks)
            for structure in sorted(section.structures, key=lambda item: item.order):
                control_level = _structure_control_level(structure, inferred_levels)
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
                        control_level=control_level,
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
                inferred_levels=inferred_levels,
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
    control_level: ControlLevel,
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
        control_level=control_level,
        component_type=component.component_type,
        process_name=process.process_name,
        productivity_rule_id=rule.id,
        quantity=quantity,
        quantity_label=quantity_label,
        duration_days=calculate_duration(quantity, rule),
        compatible_resource_types=[process.resource_type],
        properties=component.properties,
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
    inferred_levels: dict[str, ControlLevel] | None = None,
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
        inferred_levels=inferred_levels or {},
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
        inferred_levels=inferred_levels or {},
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
    inferred_levels: dict[str, ControlLevel],
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
        control_level = _upper_group_control_level(uppers, inferred_levels, default="normal")
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
            control_level=control_level,
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
    task_overrides: dict[str, TaskOverride] | None = None,
    control_level: ControlLevel = "normal",
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
        control_level=control_level,
    )
    if task is not None:
        if properties.get("resource_neutral"):
            task.compatible_resource_types = []
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
                    max_finish_gap_days=rule.max_finish_gap_days,
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
        "pier": ["cap_beam", "pier_body", "middle_tie_beam", "cap", "ground_tie_beam", "spread_foundation", "pile"],
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
    inferred_levels: dict[str, ControlLevel],
) -> tuple[list[Task], list[PrecedenceLink]]:
    tasks: list[Task] = []
    links: list[PrecedenceLink] = []
    for uppers in _continuous_beam_groups(section.upper_structures):
        group_index = _continuous_group_index(uppers)
        span_indices = sorted({upper.span_index for upper in uppers})
        main_supports = _continuous_main_supports(uppers, span_indices)
        control_level: ControlLevel = "control"
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
            control_level=control_level,
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
    control_level: ControlLevel,
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
                max_finish_gap_days=rule.max_finish_gap_days,
                source_rule_id=source_rule_id,
                severity=rule.severity,
            )
        )
        link_no += 1

    left_standard_end_tasks: list[Task | None] = []
    right_standard_end_tasks: list[Task | None] = []
    for t_index, support_index in enumerate(main_supports, start=1):
        structure_id = f"{prefix}-T{t_index:02d}-P{support_index:02d}"
        structure_name = f"{group_label}{support_index}#墩T构"
        zero_block = _append_continuous_task(
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
            control_level=control_level,
            properties={
                "continuous_task_type": "zero_block",
                "group_index": group_index,
                "support_index": support_index,
                "t_index": t_index,
            },
        )
        zero_block_links = _build_lower_to_upper_links(
            successor=zero_block,
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
        left_ready = zero_block
        right_ready = zero_block
        if standard_cycles > 0:
            sync_group_id = f"{structure_id}-STD-SYNC"
            left_standard = _append_continuous_task(
                tasks=tasks,
                component_id=f"{structure_id}-STD-L",
                name=f"{structure_name}-左侧标准段{standard_cycles}块",
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
                control_level=control_level,
                properties={
                    "continuous_task_type": "standard_segment_batch",
                    "group_index": group_index,
                    "support_index": support_index,
                    "t_index": t_index,
                    "standard_side": "left",
                    "standard_sync_group_id": sync_group_id,
                    "standard_block_count": standard_cycles,
                    "synchronizes_left_right_cantilevers": True,
                },
            )
            right_standard = _append_continuous_task(
                tasks=tasks,
                component_id=f"{structure_id}-STD-R",
                name=f"{structure_name}-右侧标准段{standard_cycles}块",
                method_id="standard_segment",
                quantity=standard_cycles,
                quantity_label=f"{standard_cycles}块",
                bridge_id=bridge.id,
                work_section_id=section.id,
                sequence_order=base_order + t_index * 1000 + 2,
                structure_id=structure_id,
                structure_name=structure_name,
                process_library=process_library,
                validation=validation,
                task_overrides=task_overrides,
                control_level=control_level,
                properties={
                    "continuous_task_type": "standard_segment_batch",
                    "group_index": group_index,
                    "support_index": support_index,
                    "t_index": t_index,
                    "standard_side": "right",
                    "standard_sync_group_id": sync_group_id,
                    "standard_block_count": standard_cycles,
                    "synchronizes_left_right_cantilevers": True,
                    "resource_neutral": True,
                },
            )
            add_link(zero_block, left_standard, "continuous_beam_t_chain")
            add_link(zero_block, right_standard, "continuous_beam_t_chain")
            left_ready = left_standard or zero_block
            right_ready = right_standard or zero_block
        left_standard_end_tasks.append(left_ready)
        right_standard_end_tasks.append(right_ready)

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
        control_level=control_level,
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
        control_level=control_level,
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
        control_level=control_level,
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
        control_level=control_level,
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
    add_link(left_standard_end_tasks[0], left_closure, "continuous_beam_side_closure")
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
    add_link(right_standard_end_tasks[-1], right_closure, "continuous_beam_side_closure")

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
            control_level=control_level,
            properties={
                "continuous_task_type": "middle_closure_segment",
                "group_index": group_index,
                "closure_index": closure_index,
                "left_support_index": left_support,
                "right_support_index": right_support,
            },
        )
        add_link(right_standard_end_tasks[closure_index - 1], mid_closure, "continuous_beam_middle_closure")
        add_link(left_standard_end_tasks[closure_index], mid_closure, "continuous_beam_middle_closure")
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
    control_level: ControlLevel,
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
        control_level="control",
    )
    if task is not None:
        if task.properties.get("resource_neutral"):
            task.compatible_resource_types = []
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
