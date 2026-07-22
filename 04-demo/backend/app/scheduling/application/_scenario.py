from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import timedelta
from typing import Any

from ...contracts import (
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
    SolveScope,
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
from ..solver.engine import (
    _apply_resource_limits,
    _critical_path_schedule,
    _resource_groups,
    solve_capacity_shortest_schedule,
    solve_control_priority_schedule,
    solve_control_priority_schedule_once,
    solve_min_resources_schedule,
    solve_resource_cost_schedule,
)
from ...wbs import build_precedence_links, calculate_duration
from ..domain.resource_scope import (
    RESOURCE_SCOPE_RULE_VERSION,
    EffectiveResourcePool,
    EffectiveResourceResolution,
    resolve_effective_resource_pools,
)
from ..domain.milestone_scope import task_ids_for_milestone


CONTINUOUS_BEAM_STRUCTURE_CODE = "castInPlaceContinuousBoxGirder"
CONTINUOUS_BEAM_COMPONENT_TYPE = "cast_in_place_continuous_beam"
CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES = 18
CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE = "castInPlaceBoxGirder"
SIMPLE_BEAM_STRUCTURE_CODE = "precastTGirder"
FIXED_RESOURCE_SOLVE_MODE = "fixed_resources_shortest_control_balanced"
TARGET_SOLVE_TIME_LIMIT_SECONDS = 15.0
CURRENT_RESOURCES_TARGET_FAILED_SOURCE = "current_resources_target_failed"
TARGET_UNCONFIRMED_SOURCE = "target_unconfirmed"
PHYSICAL_INFEASIBLE_SOURCE = "physical_infeasible"
MAX_RESOURCES_TARGET_FAILED_SOURCE = "max_resources_target_failed"
MINIMUM_RESOURCE_SEARCH_SOURCE = "minimum_resources_candidate_search"
CURRENT_RESOURCES_REFINEMENT_FAILED_SOURCE = "current_resources_refinement_failed"
MINIMUM_RESOURCES_REFINED_SOURCE = "minimum_resources_control_priority_balanced"
MINIMUM_RESOURCES_BEST_EFFORT_SOURCE = "minimum_resources_best_effort_refinement"
MINIMUM_RESOURCES_FALLBACK_SOURCE = "minimum_resources_refinement_fallback"
MAX_RESOURCE_RECOMMENDATION_ATTEMPTS = 5
ALTERNATIVE_OUTPUT_NOT_APPLICABLE = "not_applicable"
ALTERNATIVE_OUTPUT_OUTPUT = "output"
ALTERNATIVE_OUTPUT_NOT_OUTPUT = "not_output"
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
        self.time_limit_seconds = min(TARGET_SOLVE_TIME_LIMIT_SECONDS, max(0.1, float(time_limit_seconds or TARGET_SOLVE_TIME_LIMIT_SECONDS)))
        self.started_at = time.perf_counter()

    def with_time_limit(self, schedule_input: ScheduleInput, **_: Any) -> ScheduleInput:
        return schedule_input.model_copy(update={"time_limit_seconds": self.remaining_seconds()})

    def remaining_seconds(self) -> float:
        elapsed = time.perf_counter() - self.started_at
        return max(0.1, self.time_limit_seconds - elapsed)

    def exhausted(self) -> bool:
        return self.remaining_seconds() <= 0.11


def _alternative_output_metadata(status: str, *, reason: str, message: str) -> dict[str, Any]:
    return {
        "alternative_output_status": status,
        "alternative_output_reason": reason,
        "alternative_output_message": message,
    }


def _alternative_output_not_applicable(reason: str, message: str) -> dict[str, Any]:
    return _alternative_output_metadata(
        ALTERNATIVE_OUTPUT_NOT_APPLICABLE,
        reason=reason,
        message=message,
    )


def _alternative_output_from_recommendation(
    recommendation_metadata: dict[str, Any],
    *,
    has_alternative: bool,
) -> dict[str, Any]:
    reason = str(recommendation_metadata.get("resource_recommendation_status") or "resource_recommendation_unresolved")
    if has_alternative:
        return _alternative_output_metadata(
            ALTERNATIVE_OUTPUT_OUTPUT,
            reason=reason,
            message="已输出方案2：新增资源分支形成可展示候选方案。",
        )
    detail = str(recommendation_metadata.get("resource_recommendation_message") or "").strip()
    if not detail:
        detail = "新增资源分支未形成可展示候选方案。"
    return _alternative_output_metadata(
        ALTERNATIVE_OUTPUT_NOT_OUTPUT,
        reason=reason,
        message=f"方案2未输出：{detail}",
    )


def generate_schedule_input_from_scenario(
    scenario: ScenarioInput,
    *,
    use_max_resources: bool = False,
    include_girder_erection: bool = False,
    workpoint_id: str | None = None,
) -> GeneratedScheduleInput:
    solve_scope = resolve_solve_scope(scenario, workpoint_id)
    validation: list[ValidationMessage] = []
    tasks, generated_links = _build_tasks(
        scenario,
        validation,
        include_girder_erection=include_girder_erection,
        workpoint_id=solve_scope.workpoint_id,
    )
    resource_resolution = resolve_effective_resource_pools(
        project_data_version_id=scenario.project_data_version_id,
        bridges=scenario.project.bridges,
        resource_pools=scenario.resource_pools,
    )
    validation.extend(resource_resolution.diagnostics)
    tasks = _apply_required_resource_types(
        tasks,
        resource_resolution,
        validation,
        use_max_quantity=use_max_resources,
    )
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

    scoped_effective_pools = tuple(
        pool
        for pool in resource_resolution.pools
        if solve_scope.mode == "ALL" or solve_scope.workpoint_id in pool.eligible_workpoint_ids
    )
    resources, resource_messages = expand_effective_resource_pools(
        scoped_effective_pools,
        use_max_quantity=use_max_resources,
    )
    validation.extend(resource_messages)
    validation.extend(_validate_calendars(scenario))

    if not tasks:
        validation.append(
            ValidationMessage(
                level="error",
                code="SOLVE_SCOPE_NO_TASKS" if solve_scope.mode == "WORKPOINT" else None,
                subject_id=solve_scope.workpoint_id,
                entity_refs=[solve_scope.workpoint_id] if solve_scope.workpoint_id else [],
                message=(
                    f"所选工点“{solve_scope.workpoint_name}”（{solve_scope.workpoint_id}）未生成任何启用的工作项。"
                    if solve_scope.mode == "WORKPOINT"
                    else "未生成任何启用的工作项。"
                ),
            )
        )
    if not resources:
        validation.append(ValidationMessage(level="info", message="未生成受限命名资源，当前场景将按资源默认充足排程。"))

    scoped_milestones = (
        scenario.milestones
        if solve_scope.mode == "ALL"
        else [milestone for milestone in scenario.milestones if task_ids_for_milestone(milestone, tasks)]
    )
    schedule_input = ScheduleInput(
        project_name=scenario.project.project_name,
        start_date=scenario.project.start_date,
        tasks=tasks,
        precedence_links=precedence_links,
        resources=resources,
        milestones=scoped_milestones,
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
        solve_scope=solve_scope,
        source_summary={
            "bridge_count": len(scenario.project.bridges) if solve_scope.mode == "ALL" else 1,
            "process_count": len(scenario.process_library),
            "resource_pool_count": len(scenario.resource_pools),
            "milestone_count": len(scoped_milestones),
            "continuous_beam_task_count": sum(1 for task in tasks if task.structure_type == "continuous_beam"),
            "resource_scope_rule_version": RESOURCE_SCOPE_RULE_VERSION,
            "shared_effective_pool_count": resource_resolution.shared_effective_pool_count,
            "exclusive_effective_pool_count": resource_resolution.exclusive_effective_pool_count,
            "inherited_workpoint_count": resource_resolution.inherited_workpoint_count,
            "project_shared_transfer_time_days": 0,
            **_project_master_source_summary(scenario.project.bridges),
        },
    )


def resolve_solve_scope(scenario: ScenarioInput, workpoint_id: str | None = None) -> SolveScope:
    if workpoint_id is None:
        return SolveScope()
    normalized_id = workpoint_id.strip()
    if not normalized_id:
        raise ValueError("求解工点 ID 不能为空。")
    bridge = next((item for item in scenario.project.bridges if item.id == normalized_id), None)
    if bridge is None or bridge.workpoint_type != "bridge":
        raise ValueError(f"求解工点 {normalized_id} 不存在、不属于当前项目版本或不是桥梁工点。")
    return SolveScope(mode="WORKPOINT", workpoint_id=bridge.id, workpoint_name=bridge.name)


def _project_master_source_summary(bridges: list[ProjectBridge]) -> dict[str, str]:
    source_values = {
        key: {
            str(bridge.import_source[key])
            for bridge in bridges
            if bridge.import_source.get(key) not in {None, ""}
        }
        for key in ("project_data_version_id", "scheduling_projection_version")
    }
    return {
        key: next(iter(values))
        for key, values in source_values.items()
        if len(values) == 1
    }


def solve_scenario(scenario: ScenarioInput, *, workpoint_id: str | None = None) -> ScenarioSolveResult:
    started_at = time.perf_counter()
    generated = generate_schedule_input_from_scenario(scenario, workpoint_id=workpoint_id)
    alternative_results: list[ScenarioAlternativeResult] = []
    if any(message.level == "error" for message in generated.validation):
        alternative_output = _alternative_output_not_applicable(
            "scenario_generation_error",
            "场景生成失败，未进入方案2输出判断。",
        )
        result = ScheduleResult(
            status="MODEL_INVALID",
            plan_start_date=scenario.project.start_date,
            validation=generated.validation,
            stats={"reason": "scenario_generation_error", **alternative_output},
            objective_breakdown=alternative_output,
            milestone_results=[],
        )
    else:
        result, alternative_results = _solve_fixed_resources_shortest_scenario(
            scenario,
            generated,
            workpoint_id=workpoint_id,
        )

    _apply_resource_scope_diagnostics(result, scenario, generated)
    _apply_request_timing(result, started_at)
    for alternative in alternative_results:
        _apply_resource_scope_diagnostics(alternative.result, scenario, alternative.generated)
        _apply_request_timing(alternative.result, started_at)
        alternative.metrics.update(_scenario_metrics(alternative.generated, alternative.result))
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


def solve_ai_strict_fixed_resource_scenario(scenario: ScenarioInput) -> ScenarioSolveResult:
    """Solve one AI plan once with exact named resources and no expansion branch."""
    started_at = time.perf_counter()
    generated = generate_schedule_input_from_scenario(scenario)
    generation_errors = [message.message for message in generated.validation if message.level == "error"]
    if generation_errors:
        raise ValueError("；".join(generation_errors))

    total_budget_seconds = max(0.1, float(scenario.time_limit_seconds))
    stages_started_at = time.perf_counter()
    primary_input = generated.schedule_input.model_copy(update={"time_limit_seconds": total_budget_seconds})
    primary_result = solve_control_priority_schedule_once(
        primary_input,
        enforce_hard_milestones=True,
        relax_target_constraints=True,
        optimization_stage="primary",
    )
    if primary_result.status == "MODEL_INVALID":
        detail = next((message.message for message in primary_result.validation if message.level == "error"), "模型构建失败。")
        raise RuntimeError(detail)

    primary_elapsed_seconds = max(0.0, time.perf_counter() - stages_started_at)
    primary_max_target_delay_days = _ai_result_max_target_delay_days(primary_result)
    primary_makespan_days = primary_result.objective_days
    primary_idle_days = _ai_result_resource_idle_days(primary_result)
    primary_continuity_penalty = _ai_result_continuity_penalty(primary_result)
    primary_summary = {
        "attempted": True,
        "solver_status": primary_result.status,
        "max_target_delay_days": primary_max_target_delay_days,
        "makespan_days": primary_makespan_days,
        "optimality_proven": primary_result.status == "OPTIMAL",
        "elapsed_seconds": primary_elapsed_seconds,
        "configured_budget_seconds": total_budget_seconds,
    }
    secondary_summary: dict[str, Any] = {
        "attempted": False,
        "solver_status": None,
        "resource_idle_days": None,
        "continuity_penalty": None,
        "optimality_proven": False,
        "elapsed_seconds": 0.0,
        "configured_budget_seconds": 0.0,
        "skipped_reason": "not_applicable",
        "validation_failure_reason": None,
    }

    total_elapsed_seconds = max(0.0, time.perf_counter() - stages_started_at)
    optimization_stages = {
        "primary": primary_summary,
        "secondary": secondary_summary,
        "selected_stage": "primary",
        "fallback_reason": None,
        "total_budget_seconds": total_budget_seconds,
        "total_elapsed_seconds": total_elapsed_seconds,
    }
    result = primary_result
    solver_call_count = 1
    result.stats.update(
        {
            "optimization_stages": optimization_stages,
            "primary_solver_status": primary_result.status,
            "primary_max_target_delay_days": primary_max_target_delay_days,
            "primary_makespan_days": primary_makespan_days,
            "primary_resource_idle_days": primary_idle_days,
            "primary_continuity_penalty": primary_continuity_penalty,
            "solver_call_count": solver_call_count,
            "performance_path": "ai_strict_fixed_resource_single_stage",
        }
    )
    result.objective_breakdown.update(
        {
            "optimization_stages": optimization_stages,
            "primary_solver_status": primary_result.status,
            "solver_call_count": solver_call_count,
            "performance_path": "ai_strict_fixed_resource_single_stage",
        }
    )

    _apply_ai_strict_target_achievement(result, generated.schedule_input)
    result.stats.update(
        {
            "schedule_source": "ai_strict_fixed_resources",
            "recommended_schedule_source": "ai_strict_fixed_resources",
            "resource_recommendation_status": "not_applicable",
            "resource_recommendation_message": "AI 方案严格按当前资源求解，不进入新增资源分支。",
            "alternative_output_status": ALTERNATIVE_OUTPUT_NOT_APPLICABLE,
            "alternative_output_reason": "ai_strict_fixed_resources",
            "alternative_output_message": "AI 方案严格按当前资源求解，不输出新增资源候选。",
            "resource_expansion_attempted": False,
        }
    )
    result.objective_breakdown.update(
        {
            "schedule_source": "ai_strict_fixed_resources",
            "recommended_schedule_source": "ai_strict_fixed_resources",
            "resource_recommendation_status": "not_applicable",
            "resource_expansion_attempted": False,
        }
    )
    _apply_resource_scope_diagnostics(result, scenario, generated)
    _apply_request_timing(result, started_at)
    diagnostics = _build_diagnostics(generated.validation, result)
    return ScenarioSolveResult(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.scenario_name,
        generated=generated,
        result=result,
        milestone_results=result.milestone_results,
        diagnostics=diagnostics,
        metrics=_scenario_metrics(generated, result),
        alternative_results=[],
    )


def _ai_result_max_target_delay_days(result: ScheduleResult) -> int | None:
    hard_lateness = [
        max(0, int(milestone.lateness_days or 0))
        for milestone in result.milestone_results
        if milestone.mode == "hard" and milestone.status != "not_evaluated"
    ]
    fixed_duration_overrun = _fixed_duration_overrun_days(result)
    target_present = bool(hard_lateness) or _int_or_none(result.stats.get("max_makespan_days")) is not None
    if not target_present:
        return None
    return max([fixed_duration_overrun, *hard_lateness], default=0)


def _ai_result_resource_idle_days(result: ScheduleResult) -> int:
    analysis = result.stats.get("resource_organization_analysis")
    if not isinstance(analysis, dict):
        return 0
    resources = analysis.get("resources")
    if not isinstance(resources, list):
        return 0
    return sum(
        max(0, int(item.get("idle_days") or 0))
        for item in resources
        if isinstance(item, dict) and int(item.get("task_count") or 0) > 0
    )


def _ai_result_continuity_penalty(result: ScheduleResult) -> int:
    continuity = result.stats.get("continuity_metrics")
    if not isinstance(continuity, dict):
        return 0
    return (
        max(0, int(continuity.get("jump_pier_count") or 0)) * 4
        + max(0, int(continuity.get("side_switch_count") or 0)) * 2
        + max(0, int(continuity.get("cross_side_jump_count") or 0)) * 6
        + max(0, int(continuity.get("path_group_switch_count") or 0))
    )


def _apply_ai_strict_target_achievement(result: ScheduleResult, schedule_input: ScheduleInput) -> dict[str, Any]:
    hard_milestone_lateness = [
        max(0, int(milestone.lateness_days or 0))
        for milestone in result.milestone_results
        if milestone.mode == "hard"
    ]
    hard_milestone_late_days = sum(hard_milestone_lateness)
    fixed_duration_overrun_days = _fixed_duration_overrun_days(result)
    max_target_delay_days = max([fixed_duration_overrun_days, *hard_milestone_lateness], default=0)
    target_present = any(milestone.mode == "hard" for milestone in schedule_input.milestones)
    has_schedule = bool(result.tasks)
    primary_solver_status = str(result.stats.get("primary_solver_status") or result.status)
    optimality_proven = primary_solver_status == "OPTIMAL"

    if primary_solver_status == "INFEASIBLE":
        plan_status = "infeasible"
    elif primary_solver_status == "UNKNOWN":
        plan_status = "unconfirmed"
    elif primary_solver_status not in {"OPTIMAL", "FEASIBLE"}:
        plan_status = "infeasible"
    elif not target_present:
        plan_status = "unconfirmed"
    elif hard_milestone_late_days == 0 and fixed_duration_overrun_days == 0:
        plan_status = "met"
    elif optimality_proven:
        plan_status = "not_met"
    else:
        plan_status = "unconfirmed"

    schedule_outcome_status, schedule_outcome_reason = _ai_strict_schedule_outcome(
        result,
        target_present=target_present,
        has_schedule=has_schedule,
        max_target_delay_days=max_target_delay_days,
        solver_status=primary_solver_status,
    )

    failure_reasons: list[str] = []
    if hard_milestone_late_days > 0:
        failure_reasons.append("hard_milestone_late")
    if fixed_duration_overrun_days > 0:
        failure_reasons.append("fixed_duration_overrun")
    if not target_present and primary_solver_status in {"OPTIMAL", "FEASIBLE"}:
        failure_reasons.append("target_missing")
    if plan_status == "unconfirmed" and primary_solver_status == "FEASIBLE" and hard_milestone_late_days > 0:
        failure_reasons.append("optimality_unproven")
    if primary_solver_status == "UNKNOWN":
        failure_reasons.extend(["unconfirmed", "time_budget_exhausted"])
    if plan_status == "infeasible":
        failure_reasons.append(str(result.stats.get("reason") or "physical_infeasible"))

    payload = {
        "business_success": plan_status == "met",
        "target_status": plan_status,
        "schedule_outcome_status": schedule_outcome_status,
        "schedule_outcome_reason": schedule_outcome_reason,
        "solver_status": primary_solver_status,
        "selected_schedule_solver_status": result.status,
        "target_present": target_present,
        "has_schedule": has_schedule,
        "optimality_proven": optimality_proven,
        "hard_milestone_late_days": hard_milestone_late_days,
        "fixed_duration_overrun_days": fixed_duration_overrun_days,
        "max_target_delay_days": max_target_delay_days,
        "failure_reasons": list(dict.fromkeys(failure_reasons)),
        "time_budget_seconds": schedule_input.time_limit_seconds,
        "time_budget_exhausted": primary_solver_status in {"FEASIBLE", "UNKNOWN"},
        "evaluated_at_source": "ai_strict_fixed_resources",
    }
    result.stats["target_achievement"] = payload
    result.objective_breakdown["target_achievement"] = payload
    result.stats["hard_milestone_late_days"] = hard_milestone_late_days
    result.stats["fixed_duration_overrun_days"] = fixed_duration_overrun_days
    result.stats["max_target_delay_days"] = max_target_delay_days
    result.objective_breakdown["hard_milestone_late_days"] = hard_milestone_late_days
    result.objective_breakdown["fixed_duration_overrun_days"] = fixed_duration_overrun_days
    result.objective_breakdown["max_target_delay_days"] = max_target_delay_days

    if plan_status == "not_met":
        result.validation.append(
            ValidationMessage(
                level="warning",
                message=f"当前固定资源的已证明最优排程仍延期 {hard_milestone_late_days + fixed_duration_overrun_days} 天，不自动增加资源。",
            )
        )
    elif plan_status == "unconfirmed" and primary_solver_status == "FEASIBLE":
        result.validation.append(
            ValidationMessage(
                level="warning",
                message="当前限时内已有可行排程但尚未证明最优，不据此断言资源不足。",
            )
        )
    elif plan_status == "unconfirmed" and not target_present:
        result.validation.append(ValidationMessage(level="warning", message="当前方案缺少可评估的强制目标，无法判断目标是否满足。"))
    return payload


def _ai_strict_schedule_outcome(
    result: ScheduleResult,
    *,
    target_present: bool,
    has_schedule: bool,
    max_target_delay_days: int,
    solver_status: str | None = None,
) -> tuple[str | None, str | None]:
    effective_status = solver_status or result.status
    if effective_status in {"OPTIMAL", "FEASIBLE"} and has_schedule:
        if not target_present:
            return None, "target_missing"
        if max_target_delay_days == 0:
            return "duration_target_met", "target_met"
        if effective_status == "OPTIMAL":
            return "duration_target_not_met", "proven_late"
        return "duration_target_not_met", "late_unconfirmed"
    if effective_status == "UNKNOWN" or (effective_status in {"OPTIMAL", "FEASIBLE"} and not has_schedule):
        return "no_feasible_schedule", "time_limit_no_schedule"
    if effective_status == "INFEASIBLE":
        reason = str(result.stats.get("reason") or "").lower()
        messages = " ".join(item.message for item in result.validation).lower()
        resource_markers = ("resource_coverage", "missing_resource", "compatible_resource", "resource_type", "资源", "兼容")
        outcome_reason = "resource_coverage_missing" if any(marker in f"{reason} {messages}" for marker in resource_markers) else "proven_infeasible"
        return "no_feasible_schedule", outcome_reason
    return None, None


def _solve_fixed_resources_shortest_scenario(
    scenario: ScenarioInput,
    generated: GeneratedScheduleInput,
    *,
    workpoint_id: str | None = None,
) -> tuple[ScheduleResult, list[ScenarioAlternativeResult]]:
    budget = _FixedResourceSolveBudget(scenario.time_limit_seconds)
    critical_path = _critical_path_schedule(generated.schedule_input)
    final_input = budget.with_time_limit(generated.schedule_input)
    final_result = solve_control_priority_schedule(
        final_input,
        enforce_hard_milestones=True,
        relax_target_constraints=True,
    )
    baseline_makespan_days = final_result.stats.get("baseline_objective_days") or final_result.objective_days
    solver_call_count = _int_or_none(final_result.stats.get("solver_call_count")) or 1
    _apply_target_achievement(
        final_result,
        evaluated_at_source="current_resources",
        default_failed_status=CURRENT_RESOURCES_TARGET_FAILED_SOURCE,
        time_budget_seconds=budget.time_limit_seconds,
        time_budget_exhausted=budget.exhausted(),
    )
    target_achievement = final_result.stats.get("target_achievement", {})

    if final_result.status in {"OPTIMAL", "FEASIBLE"} and target_achievement.get("business_success") is True:
        _apply_fixed_resource_metadata(
            final_result,
            baseline_makespan_days=baseline_makespan_days,
            hard_milestone_feasible=True,
            schedule_source="current_resources_control_priority_balanced",
            performance_path="direct_named_refinement",
            solver_call_count=solver_call_count,
            capacity_precheck_status="not_run",
            warm_start_used=bool(final_result.stats.get("warm_start_used")),
            resource_recommendation_status="not_needed",
            resource_recommendation_message="当前固定资源精排已满足硬里程碑，无需增加资源。",
            **_alternative_output_not_applicable(
                "not_needed",
                "当前固定资源精排已满足硬里程碑，无需进入方案2输出判断。",
            ),
        )
        return final_result, []

    if final_result.status == "UNKNOWN":
        result = final_result.model_copy(deep=True)
        _apply_target_achievement(
            result,
            evaluated_at_source="current_resources",
            forced_status="unconfirmed",
            time_budget_seconds=budget.time_limit_seconds,
            time_budget_exhausted=True,
        )
        _apply_fixed_resource_metadata(
            result,
            baseline_makespan_days=baseline_makespan_days,
            hard_milestone_feasible=False,
            schedule_source=TARGET_UNCONFIRMED_SOURCE,
            performance_path="current_resources_full_objective_unconfirmed",
            solver_call_count=solver_call_count,
            capacity_precheck_status="not_run",
            warm_start_used=bool(final_result.stats.get("warm_start_used")),
            resource_recommendation_status="unconfirmed",
            resource_recommendation_message="当前资源完整目标函数求解在限定时间内无法确认，未进入确定性资源不足判断。",
            **_alternative_output_not_applicable(
                "unconfirmed",
                "当前资源完整目标函数求解未确认，未进入方案2输出判断。",
            ),
        )
        return result, []

    if final_result.status not in {"OPTIMAL", "FEASIBLE"}:
        result = final_result.model_copy(deep=True)
        _apply_target_achievement(
            result,
            evaluated_at_source="current_resources",
            forced_status="physical_infeasible",
            time_budget_seconds=budget.time_limit_seconds,
            time_budget_exhausted=budget.exhausted(),
        )
        _apply_fixed_resource_metadata(
            result,
            baseline_makespan_days=baseline_makespan_days,
            hard_milestone_feasible=False,
            schedule_source=PHYSICAL_INFEASIBLE_SOURCE,
            performance_path="current_resources_full_objective_physical_infeasible",
            solver_call_count=solver_call_count,
            capacity_precheck_status="not_run",
            warm_start_used=bool(final_result.stats.get("warm_start_used")),
            resource_recommendation_status="physical_infeasible",
            resource_recommendation_message="当前资源、施工硬规则或资源覆盖未得到物理可行排程。",
            **_alternative_output_not_applicable(
                "physical_infeasible",
                "当前资源没有物理可行排程，未进入方案2输出判断。",
            ),
        )
        return result, []

    failure_reason = (
        "current_resources_target_failed"
        if target_achievement
        else f"control_priority_{final_result.status.lower()}"
    )
    result = final_result.model_copy(deep=True)

    result.validation = list(final_result.validation)
    result.validation.append(
        ValidationMessage(
            level="warning",
            message="当前固定资源已得到可查看排程，但未满足业务目标，已进入资源增量建议。",
        )
    )
    late_hard = _late_hard_milestones(final_result)
    for milestone in late_hard:
        result.validation.append(
            ValidationMessage(
                level="warning",
                subject_id=milestone.id,
                message=(
                    f"硬里程碑“{milestone.name}”目标 {milestone.target_date}，"
                    f"当前固定资源精排预计 {milestone.actual_date}，迟延 {milestone.lateness_days} 天。"
                ),
            )
        )

    recommendation = _fixed_resource_recommendation(
        scenario,
        generated.schedule_input,
        workpoint_id=workpoint_id,
        critical_path=critical_path,
        current_result=final_result,
        budget=_FixedResourceSolveBudget(scenario.time_limit_seconds),
    )
    recommendation_metadata = {
        key: value
        for key, value in recommendation["metadata"].items()
        if key != "alternative_result"
    }
    alternative = recommendation.get("alternative_result")
    recommendation_metadata.update(
        _alternative_output_from_recommendation(
            recommendation_metadata,
            has_alternative=alternative is not None,
        )
    )
    _apply_fixed_resource_metadata(
        result,
        baseline_makespan_days=baseline_makespan_days,
        hard_milestone_feasible=False,
        schedule_source=CURRENT_RESOURCES_TARGET_FAILED_SOURCE,
        performance_path="current_resources_full_objective_target_failed_resource_recommendation",
        solver_call_count=solver_call_count,
        capacity_precheck_status="not_run",
        warm_start_used=bool(final_result.stats.get("warm_start_used")),
        skipped_named_refinement_reason=failure_reason,
        **recommendation_metadata,
    )
    result.validation.extend(recommendation["validation"])
    alternatives = [alternative] if alternative is not None else []
    return result, alternatives

def _late_hard_milestones(result: ScheduleResult) -> list[Any]:
    return [
        milestone
        for milestone in result.milestone_results
        if milestone.mode == "hard" and milestone.lateness_days > 0
    ]


def _apply_target_achievement(
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
    fixed_duration_overrun_days = _fixed_duration_overrun_days(
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


def _fixed_duration_overrun_days(
    result: ScheduleResult,
    *,
    fixed_duration_target: int | None = None,
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
    if result.status == "UNKNOWN":
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
    if status == "unconfirmed" and time_budget_exhausted:
        reasons.append("time_budget_exhausted")
    return list(dict.fromkeys(reasons))


def _apply_best_effort_refinement_metadata(
    result: ScheduleResult,
    *,
    schedule_source: str,
    fallback_from: str,
    strict_result: ScheduleResult,
    strict_failure_reason: str,
) -> None:
    fixed_duration_target = _int_or_none(
        result.stats.get("max_makespan_days")
        or result.objective_breakdown.get("max_makespan_days")
    )
    fixed_duration_overrun_days = max(0, (result.objective_days or 0) - fixed_duration_target) if fixed_duration_target is not None else 0
    target_lateness_days = sum(
        milestone.lateness_days
        for milestone in result.milestone_results
        if milestone.mode == "hard"
    )
    metadata = {
        "enabled": True,
        "schedule_source": schedule_source,
        "fallback_from": fallback_from,
        "strict_refinement_status": strict_result.status,
        "strict_refinement_failure_reason": strict_failure_reason,
        "objective_status": result.status,
        "target_lateness_days": target_lateness_days,
        "fixed_duration_overrun_days": fixed_duration_overrun_days,
        "best_effort_score": result.objective_breakdown.get("best_effort_score")
        or result.objective_breakdown.get("weighted_objective"),
        "wall_time_seconds": result.stats.get("wall_time_seconds"),
        "strict_wall_time_seconds": strict_result.stats.get("wall_time_seconds"),
        "relaxed_constraints": _best_effort_relaxed_constraints(
            result,
            fixed_duration_target=fixed_duration_target,
            fixed_duration_overrun_days=fixed_duration_overrun_days,
        ),
    }
    result.stats["best_effort_refinement"] = metadata
    result.objective_breakdown["best_effort_refinement"] = {
        "enabled": True,
        "schedule_source": schedule_source,
        "target_lateness_days": target_lateness_days,
        "fixed_duration_overrun_days": fixed_duration_overrun_days,
        "best_effort_score": metadata["best_effort_score"],
        "relaxed_constraints": metadata["relaxed_constraints"],
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


def _fixed_resource_recommendation(
    scenario: ScenarioInput,
    current_schedule_input: ScheduleInput,
    *,
    workpoint_id: str | None = None,
    critical_path: dict[str, Any] | None = None,
    current_result: ScheduleResult | None = None,
    budget: _FixedResourceSolveBudget | None = None,
) -> dict[str, Any]:
    recommendation_time_limit_seconds = (
        budget.time_limit_seconds if budget is not None else current_schedule_input.time_limit_seconds
    )
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

    max_generated = generate_schedule_input_from_scenario(
        scenario,
        use_max_resources=True,
        workpoint_id=workpoint_id,
    )
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
    minimum_resource_counts = _resource_minimum_counts(current_schedule_input)
    recommendation_attempts: list[dict[str, Any]] = []
    last_min_resource_result: ScheduleResult | None = None
    last_candidate_result: ScheduleResult | None = None
    last_recommendation: list[dict[str, Any]] = []
    overdue_days = _target_overdue_days_for_pressure(current_result)
    last_pressure_context: dict[str, Any] | None = None
    pressure_stop_reason = "not_started"
    pressure_status = "not_run"

    for attempt_index in range(1, MAX_RESOURCE_RECOMMENDATION_ATTEMPTS + 1):
        search_budget = _FixedResourceSolveBudget(recommendation_time_limit_seconds)
        pressure_context = _pressure_target_context(
            max_schedule_input,
            critical_path=critical_path,
            overdue_days=overdue_days,
            attempt_index=attempt_index,
            current_result=current_result,
        )
        last_pressure_context = pressure_context
        pressure_schedule_input = _schedule_input_with_pressure_target(max_schedule_input, pressure_context)
        fallback_target_days = (
            _int_or_none(pressure_context.get("pressure_target_days"))
            if not pressure_context.get("hard_milestone_count")
            else None
        )
        min_resource_result = solve_min_resources_schedule(
            search_budget.with_time_limit(pressure_schedule_input),
            fallback_target_days=fallback_target_days,
            minimum_resource_counts=minimum_resource_counts,
            verify_with_full_objective=False,
        )
        last_min_resource_result = min_resource_result

        if _min_resource_result_is_upper_bound_infeasible(min_resource_result):
            pressure_status = "upper_bound_infeasible"
            pressure_stop_reason = "upper_bound_infeasible"
            recommendation_attempts.append(
                _resource_recommendation_attempt_summary(
                    attempt_index=attempt_index,
                    minimum_resource_counts=minimum_resource_counts,
                    min_resource_result=min_resource_result,
                    fixed_counts={},
                    candidate_result=None,
                    time_limit_seconds=search_budget.time_limit_seconds,
                    pressure_context=pressure_context,
                    stop_reason=pressure_stop_reason,
                )
            )
            return {
                "metadata": {
                    **critical_metadata,
                    "resource_recommendation_status": "resource_upper_bound_infeasible",
                    "resource_recommendation_message": "工艺逻辑关键路径可满足目标，但当前资源池最大数量或资源类型结构仍无法满足硬里程碑。",
                    "recommended_resource_counts": [],
                    "resource_upper_bound_counts": resource_upper_bounds,
                    "resource_capacity_lower_bounds": min_resource_result.stats.get("resource_capacity_lower_bounds", []),
                    "resource_solver_status": min_resource_result.status,
                    "resource_recommendation_attempt_count": len(recommendation_attempts),
                    "resource_recommendation_attempt_limit": MAX_RESOURCE_RECOMMENDATION_ATTEMPTS,
                    "resource_recommendation_attempts": recommendation_attempts,
                    **_pressure_search_metadata(
                        status=pressure_status,
                        stop_reason=pressure_stop_reason,
                        attempts=recommendation_attempts,
                        overdue_days=overdue_days,
                        last_context=last_pressure_context,
                    ),
                    "recommended_resources": {
                        "candidate_quantities": {},
                        "added_quantities": {},
                        "search_range": _resource_search_range_from_recommendation(resource_upper_bounds),
                        "verification_result_source": "max_resources_target_failed",
                        "target_achievement": min_resource_result.stats.get("target_achievement"),
                    },
                    **_min_resource_recommendation_metadata(min_resource_result),
                },
                "validation": [
                    ValidationMessage(
                        level="error",
                        message="当前资源池最大数量仍无法满足强制里程碑；请提高资源上限或检查资源类型配置。",
                    )
                ],
            }

        if not _min_resource_result_has_capacity_verified_candidate(min_resource_result):
            pressure_status = "unconfirmed"
            pressure_stop_reason = "capacity_model_unconfirmed"
            recommendation_attempts.append(
                _resource_recommendation_attempt_summary(
                    attempt_index=attempt_index,
                    minimum_resource_counts=minimum_resource_counts,
                    min_resource_result=min_resource_result,
                    fixed_counts={},
                    candidate_result=None,
                    time_limit_seconds=search_budget.time_limit_seconds,
                    pressure_context=pressure_context,
                    stop_reason=pressure_stop_reason,
                )
            )
            return {
                "metadata": {
                    **critical_metadata,
                    "resource_recommendation_status": "resource_recommendation_unresolved",
                    "resource_recommendation_message": "最少资源模型未得到可进入完整目标函数复排的候选结果；当前求解限时内无法确认推荐资源组合。",
                    "recommended_resource_counts": [],
                    "resource_upper_bound_counts": resource_upper_bounds,
                    "resource_capacity_lower_bounds": min_resource_result.stats.get("resource_capacity_lower_bounds", []),
                    "resource_solver_status": min_resource_result.status,
                    "resource_recommendation_attempt_count": len(recommendation_attempts),
                    "resource_recommendation_attempt_limit": MAX_RESOURCE_RECOMMENDATION_ATTEMPTS,
                    "resource_recommendation_attempts": recommendation_attempts,
                    **_pressure_search_metadata(
                        status=pressure_status,
                        stop_reason=pressure_stop_reason,
                        attempts=recommendation_attempts,
                        overdue_days=overdue_days,
                        last_context=last_pressure_context,
                    ),
                    "recommended_resources": {
                        "candidate_quantities": {},
                        "added_quantities": {},
                        "search_range": _resource_search_range_from_recommendation(resource_upper_bounds),
                        "verification_result_source": "unconfirmed",
                        "target_achievement": min_resource_result.stats.get("target_achievement"),
                    },
                    **_min_resource_recommendation_metadata(min_resource_result),
                },
                "validation": [
                    ValidationMessage(
                        level="warning",
                        message="最少资源模型未得到可进入完整目标函数复排的候选结果；请提高求解限时或检查工作面并行约束、资源上限配置。",
                    )
                ],
            }

        fixed_counts = _resource_count_map(min_resource_result)
        if not _resource_counts_exceed_lower_bounds(fixed_counts, minimum_resource_counts):
            pressure_stop_reason = (
                "critical_path_floor_reached"
                if pressure_context.get("clamped_by_critical_path")
                else "same_as_lower_bounds"
            )
            pressure_status = pressure_stop_reason
            recommendation_attempts.append(
                _resource_recommendation_attempt_summary(
                    attempt_index=attempt_index,
                    minimum_resource_counts=minimum_resource_counts,
                    min_resource_result=min_resource_result,
                    fixed_counts=fixed_counts,
                    candidate_result=None,
                    time_limit_seconds=search_budget.time_limit_seconds,
                    pressure_context=pressure_context,
                    stop_reason=pressure_stop_reason,
                )
            )
            if pressure_context.get("clamped_by_critical_path"):
                break
            continue

        recommendation = _enriched_resource_counts(
            current_schedule_input=current_schedule_input,
            max_schedule_input=max_schedule_input,
            fixed_counts=fixed_counts,
        )
        last_recommendation = recommendation
        limited_schedule_input = max_generated.schedule_input.model_copy(
            update={"resources": _apply_resource_limits(max_generated.schedule_input.resources, fixed_counts)}
        )
        alternative_generated = max_generated.model_copy(update={"schedule_input": limited_schedule_input})
        verification_budget = _FixedResourceSolveBudget(recommendation_time_limit_seconds)
        candidate_result = _minimum_resource_candidate_result(
            verification_budget.with_time_limit(limited_schedule_input),
            min_resource_result.model_copy(deep=True),
            budget=verification_budget,
        )
        last_candidate_result = candidate_result
        recommendation_attempts.append(
            _resource_recommendation_attempt_summary(
                attempt_index=attempt_index,
                minimum_resource_counts=minimum_resource_counts,
                min_resource_result=min_resource_result,
                fixed_counts=fixed_counts,
                candidate_result=candidate_result,
                time_limit_seconds=verification_budget.time_limit_seconds,
                pressure_context=pressure_context,
                stop_reason="candidate_verified" if _result_business_success(candidate_result) else "full_objective_failed",
            )
        )

        if not _result_business_success(candidate_result):
            pressure_status = "candidate_failed"
            pressure_stop_reason = "full_objective_failed"
            minimum_resource_counts = _next_resource_minimum_counts(minimum_resource_counts, fixed_counts)
            continue

        pressure_status = "candidate_verified"
        pressure_stop_reason = "candidate_verified"
        recommendation_metadata = {
            "resource_recommendation_status": "recommended_resources_verified",
            "resource_recommendation_message": "已输出固定工期条件下的可行最少资源方案。",
            "recommended_resource_counts": recommendation,
            "recommended_resources": _resource_candidate_outcome(
                recommendation,
                candidate_result,
                verification_result_source="candidate_resources_full_objective",
            ),
            "resource_upper_bound_counts": resource_upper_bounds,
            "resource_solver_status": min_resource_result.status,
            "resource_recommendation_attempt_count": len(recommendation_attempts),
            "resource_recommendation_attempt_limit": MAX_RESOURCE_RECOMMENDATION_ATTEMPTS,
            "resource_recommendation_attempts": recommendation_attempts,
            **_pressure_search_metadata(
                status=pressure_status,
                stop_reason=pressure_stop_reason,
                attempts=recommendation_attempts,
                overdue_days=overdue_days,
                last_context=last_pressure_context,
            ),
            **_min_resource_recommendation_metadata(min_resource_result),
        }
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

    fallback_result = last_candidate_result or last_min_resource_result
    recommendation = last_recommendation
    recommended_resources = (
        _resource_candidate_outcome(
            recommendation,
            fallback_result,
            verification_result_source="candidate_resources_full_objective_failed",
        )
        if recommendation and fallback_result is not None
        else {
            "candidate_quantities": {},
            "added_quantities": {},
            "search_range": _resource_search_range_from_recommendation(resource_upper_bounds),
            "verification_result_source": "candidate_resources_full_objective_failed",
            "target_achievement": fallback_result.stats.get("target_achievement") if fallback_result else None,
        }
    )

    exhausted_without_increment = pressure_status in {"same_as_lower_bounds", "critical_path_floor_reached"}
    fallback_recommendation_status = (
        "resource_recommendation_unresolved"
        if exhausted_without_increment
        else "candidate_resources_full_objective_failed"
    )
    fallback_recommendation_message = (
        "资源建议压力搜索已达到关键路径下界或循环上限，容量模型仍只返回当前下限，未形成可验证的新增资源候选。"
        if exhausted_without_increment
        else (
            f"候选资源已完成 {len(recommendation_attempts)} 次完整目标函数复排验证，仍未满足硬里程碑或固定工期；"
            f"已达到 {MAX_RESOURCE_RECOMMENDATION_ATTEMPTS} 次循环上限，排程失败。"
        )
    )

    return {
        "metadata": {
            **critical_metadata,
            "resource_recommendation_status": fallback_recommendation_status,
            "resource_recommendation_message": fallback_recommendation_message,
            "resource_recommendation_message_legacy": (
                f"候选资源已完成 {len(recommendation_attempts)} 次完整目标函数复排验证，仍未满足硬里程碑或固定工期；"
                f"已达到 {MAX_RESOURCE_RECOMMENDATION_ATTEMPTS} 次循环上限，排程失败。"
            ),
            "recommended_resource_counts": recommendation,
            "resource_upper_bound_counts": resource_upper_bounds,
            "resource_capacity_lower_bounds": last_min_resource_result.stats.get("resource_capacity_lower_bounds", [])
            if last_min_resource_result
            else [],
            "resource_solver_status": last_min_resource_result.status if last_min_resource_result else "UNKNOWN",
            "resource_recommendation_attempt_count": len(recommendation_attempts),
            "resource_recommendation_attempt_limit": MAX_RESOURCE_RECOMMENDATION_ATTEMPTS,
            "resource_recommendation_attempts": recommendation_attempts,
            **_pressure_search_metadata(
                status=pressure_status,
                stop_reason=pressure_stop_reason,
                attempts=recommendation_attempts,
                overdue_days=overdue_days,
                last_context=last_pressure_context,
            ),
            "recommended_resources": recommended_resources,
            **(_min_resource_recommendation_metadata(last_min_resource_result) if last_min_resource_result else {}),
        },
        "validation": [
            ValidationMessage(
                level="error",
                message=(
                    f"候选资源-完整目标函数复排循环已达到 {MAX_RESOURCE_RECOMMENDATION_ATTEMPTS} 次上限，"
                    "仍未得到满足硬里程碑和固定工期的排程结果。"
                ),
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


def _resource_minimum_counts(schedule_input: ScheduleInput) -> dict[str, int]:
    return {
        group["key"]: int(group["max_quantity"])
        for group in _resource_groups([resource for resource in schedule_input.resources if resource.enabled])
    }


def _target_overdue_days_for_pressure(result: ScheduleResult | None) -> int:
    target = _result_target_achievement(result)
    overdue_days = max(
        _target_int(target, "hard_milestone_late_days"),
        _target_int(target, "fixed_duration_overrun_days"),
    )
    if overdue_days > 0:
        return overdue_days
    if result is None:
        return 0
    late_hard_days = [
        int(milestone.lateness_days or 0)
        for milestone in result.milestone_results
        if milestone.mode == "hard" and int(milestone.lateness_days or 0) > 0
    ]
    return max(late_hard_days, default=0)


def _milestone_target_days(start_date: Any, milestone: Any) -> int:
    offset = (milestone.target_date - start_date).days
    if milestone.target_event == "finish":
        return offset + 1
    return offset


def _date_from_target_days(start_date: Any, target_event: str, target_days: int) -> Any:
    offset = target_days - 1 if target_event == "finish" else target_days
    return start_date + timedelta(days=max(0, offset))


def _pressure_target_context(
    schedule_input: ScheduleInput,
    *,
    critical_path: dict[str, Any],
    overdue_days: int,
    attempt_index: int,
    current_result: ScheduleResult | None,
) -> dict[str, Any]:
    critical_floor_days = max(1, _int_or_none(critical_path.get("objective_days")) or 1)
    compression_days = max(0, int(overdue_days or 0) * max(1, int(attempt_index)))
    hard_milestones = [milestone for milestone in schedule_input.milestones if milestone.mode == "hard"]
    pressure_milestones: list[dict[str, Any]] = []
    original_target_days: int | None = None
    pressure_target_days: int | None = None
    clamped_by_critical_path = False

    for milestone in hard_milestones:
        milestone_original_days = max(1, _milestone_target_days(schedule_input.start_date, milestone))
        milestone_floor_days = min(milestone_original_days, critical_floor_days)
        raw_days = max(1, milestone_original_days - compression_days)
        milestone_pressure_days = max(milestone_floor_days, raw_days)
        if milestone_pressure_days != raw_days:
            clamped_by_critical_path = True
        original_target_days = max(original_target_days or 0, milestone_original_days)
        pressure_target_days = max(pressure_target_days or 0, milestone_pressure_days)
        pressure_milestones.append(
            {
                "id": milestone.id,
                "name": milestone.name,
                "original_target_date": milestone.target_date.isoformat(),
                "pressure_target_date": _date_from_target_days(
                    schedule_input.start_date,
                    milestone.target_event,
                    milestone_pressure_days,
                ).isoformat(),
                "original_target_days": milestone_original_days,
                "pressure_target_days": milestone_pressure_days,
            }
        )

    if not hard_milestones:
        fallback_target = _int_or_none(
            (current_result.stats.get("max_makespan_days") if current_result else None)
            or (current_result.objective_breakdown.get("max_makespan_days") if current_result else None)
        )
        if fallback_target is not None:
            original_target_days = max(1, fallback_target)
            raw_days = max(1, original_target_days - compression_days)
            pressure_target_days = max(min(original_target_days, critical_floor_days), raw_days)
            clamped_by_critical_path = pressure_target_days != raw_days

    return {
        "attempt": attempt_index,
        "overdue_days": max(0, int(overdue_days or 0)),
        "compression_days": compression_days,
        "original_target_days": original_target_days,
        "pressure_target_days": pressure_target_days,
        "critical_path_minimum_days": critical_floor_days,
        "clamped_by_critical_path": clamped_by_critical_path,
        "hard_milestone_count": len(hard_milestones),
        "pressure_milestones": pressure_milestones,
    }


def _schedule_input_with_pressure_target(
    schedule_input: ScheduleInput,
    pressure_context: dict[str, Any],
) -> ScheduleInput:
    pressure_by_id = {
        str(item["id"]): item
        for item in pressure_context.get("pressure_milestones", [])
        if isinstance(item, dict) and item.get("id")
    }
    if not pressure_by_id:
        return schedule_input
    milestones = []
    for milestone in schedule_input.milestones:
        pressure = pressure_by_id.get(milestone.id)
        if pressure is None:
            milestones.append(milestone)
            continue
        target_days = _int_or_none(pressure.get("pressure_target_days"))
        if target_days is None:
            milestones.append(milestone)
            continue
        milestones.append(
            milestone.model_copy(
                update={
                    "target_date": _date_from_target_days(
                        schedule_input.start_date,
                        milestone.target_event,
                        target_days,
                    )
                }
            )
        )
    return schedule_input.model_copy(update={"milestones": milestones})


def _resource_counts_exceed_lower_bounds(
    fixed_counts: dict[str, int],
    lower_bounds: dict[str, int],
) -> bool:
    return any(int(count or 0) > int(lower_bounds.get(key, 0) or 0) for key, count in fixed_counts.items())


def _pressure_search_metadata(
    *,
    status: str,
    stop_reason: str,
    attempts: list[dict[str, Any]],
    overdue_days: int,
    last_context: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "pressure_search_status": status,
        "pressure_search_stop_reason": stop_reason,
        "pressure_search_overdue_days": overdue_days,
        "pressure_search_attempt_count": len(attempts),
        "pressure_search_attempt_limit": MAX_RESOURCE_RECOMMENDATION_ATTEMPTS,
        "pressure_search_attempts": attempts,
        "pressure_search_last_target_days": last_context.get("pressure_target_days") if last_context else None,
        "pressure_search_original_target_days": last_context.get("original_target_days") if last_context else None,
        "pressure_search_critical_path_minimum_days": last_context.get("critical_path_minimum_days") if last_context else None,
    }


def _next_resource_minimum_counts(current_minimums: dict[str, int], fixed_counts: dict[str, int]) -> dict[str, int]:
    merged = dict(current_minimums)
    for key, count in fixed_counts.items():
        merged[key] = max(int(merged.get(key, 0)), int(count or 0))
    return merged


def _result_target_achievement(result: ScheduleResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    target = result.stats.get("target_achievement") or result.objective_breakdown.get("target_achievement")
    return target if isinstance(target, dict) else None


def _result_business_success(result: ScheduleResult | None) -> bool:
    target = _result_target_achievement(result)
    return bool(target and target.get("business_success") is True)


def _target_int(target: dict[str, Any] | None, key: str) -> int:
    if not target:
        return 0
    try:
        return int(target.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _min_resource_result_has_verified_recommendation(result: ScheduleResult) -> bool:
    recommended = result.stats.get("recommended_resource_counts") or result.objective_breakdown.get("recommended_resource_counts") or []
    capacity_status = result.stats.get("capacity_verification_status") or result.objective_breakdown.get("capacity_verification_status")
    target = result.stats.get("target_achievement")
    return (
        result.status in {"OPTIMAL", "FEASIBLE"}
        and bool(recommended)
        and capacity_status == "verified"
        and isinstance(target, dict)
        and target.get("business_success") is True
    )


def _min_resource_result_has_capacity_verified_candidate(result: ScheduleResult) -> bool:
    recommended = result.stats.get("recommended_resource_counts") or result.objective_breakdown.get("recommended_resource_counts") or []
    capacity_status = result.stats.get("capacity_verification_status") or result.objective_breakdown.get("capacity_verification_status")
    target = _result_target_achievement(result)
    return (
        result.status in {"OPTIMAL", "FEASIBLE"}
        and bool(recommended)
        and capacity_status == "verified"
        and target is not None
        and _target_int(target, "hard_milestone_late_days") == 0
        and _target_int(target, "fixed_duration_overrun_days") == 0
    )


def _min_resource_result_is_upper_bound_infeasible(result: ScheduleResult) -> bool:
    reason = result.stats.get("reason")
    capacity_status = result.stats.get("capacity_model_status")
    global_status = result.stats.get("global_capacity_model_status")
    target = result.stats.get("target_achievement")
    if isinstance(target, dict) and target.get("target_status") == "max_resources_target_failed":
        return True
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


def _resource_recommendation_attempt_summary(
    *,
    attempt_index: int,
    minimum_resource_counts: dict[str, int],
    min_resource_result: ScheduleResult,
    fixed_counts: dict[str, int],
    candidate_result: ScheduleResult | None,
    time_limit_seconds: float,
    pressure_context: dict[str, Any] | None = None,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    resource_target = _result_target_achievement(min_resource_result)
    candidate_target = _result_target_achievement(candidate_result)
    summary = {
        "attempt": attempt_index,
        "time_limit_seconds": time_limit_seconds,
        "search_lower_bounds": dict(minimum_resource_counts),
        "candidate_quantities": dict(fixed_counts),
        "resource_solver_status": min_resource_result.status,
        "resource_schedule_source": min_resource_result.stats.get("schedule_source")
        or min_resource_result.objective_breakdown.get("schedule_source"),
        "capacity_verification_status": min_resource_result.stats.get("capacity_verification_status")
        or min_resource_result.objective_breakdown.get("capacity_verification_status"),
        "resource_target_status": resource_target.get("target_status") if resource_target else None,
        "full_objective_status": candidate_result.status if candidate_result else None,
        "full_objective_schedule_source": candidate_result.stats.get("schedule_source")
        or candidate_result.objective_breakdown.get("schedule_source")
        if candidate_result
        else None,
        "full_objective_target_status": candidate_target.get("target_status") if candidate_target else None,
        "business_success": candidate_target.get("business_success") if candidate_target else None,
    }
    if pressure_context:
        summary.update(
            {
                "pressure_overdue_days": pressure_context.get("overdue_days"),
                "pressure_compression_days": pressure_context.get("compression_days"),
                "pressure_original_target_days": pressure_context.get("original_target_days"),
                "pressure_target_days": pressure_context.get("pressure_target_days"),
                "critical_path_minimum_days": pressure_context.get("critical_path_minimum_days"),
                "pressure_clamped_by_critical_path": pressure_context.get("clamped_by_critical_path"),
                "pressure_milestones": pressure_context.get("pressure_milestones", []),
            }
        )
    if stop_reason:
        summary["stop_reason"] = stop_reason
    return summary


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


def _resource_search_range_from_recommendation(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    for item in items:
        current_quantity = int(item.get("current_quantity") or 0)
        max_quantity = int(item.get("max_quantity") or item.get("upper_bound_quantity") or current_quantity)
        ranges.append(
            {
                "resource_type": str(item.get("resource_type") or item.get("resource_pool_id") or ""),
                "resource_pool_id": str(item.get("resource_pool_id") or ""),
                "current_quantity": current_quantity,
                "max_quantity": max_quantity,
                "lower_bound": current_quantity,
                "upper_bound": max_quantity,
            }
        )
    return ranges


def _resource_candidate_outcome(
    recommendation: list[dict[str, Any]],
    result: ScheduleResult,
    *,
    verification_result_source: str,
) -> dict[str, Any]:
    candidate_quantities: dict[str, int] = {}
    added_quantities: dict[str, int] = {}
    for item in recommendation:
        key = str(item.get("resource_pool_id") or item.get("resource_type") or "")
        if not key:
            continue
        candidate_quantities[key] = int(item.get("recommended_quantity") or 0)
        added_quantities[key] = int(item.get("added_quantity") or 0)
    return {
        "candidate_quantities": candidate_quantities,
        "added_quantities": added_quantities,
        "search_range": _resource_search_range_from_recommendation(recommendation),
        "verification_result_source": verification_result_source,
        "target_achievement": result.stats.get("target_achievement"),
    }


def _minimum_resource_candidate_result(
    limited_schedule_input: ScheduleInput,
    min_resource_result: ScheduleResult,
    *,
    budget: _FixedResourceSolveBudget | None = None,
) -> ScheduleResult:
    budget = budget or _FixedResourceSolveBudget(limited_schedule_input.time_limit_seconds)
    refined_input = budget.with_time_limit(limited_schedule_input)
    refined_result = solve_control_priority_schedule(
        refined_input,
        enforce_hard_milestones=True,
        baseline_result=min_resource_result,
        warm_start_result=min_resource_result,
        relax_target_constraints=True,
    )
    target = _apply_target_achievement(
        refined_result,
        evaluated_at_source="candidate_resources",
        default_failed_status="candidate_resources_target_failed",
        success_status="candidate_resources_target_met",
        time_budget_seconds=budget.time_limit_seconds,
        time_budget_exhausted=budget.exhausted(),
    )
    if target["business_success"]:
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

    fallback_reason = f"minimum_resource_full_objective_{refined_result.status.lower()}"
    if refined_result.status in {"OPTIMAL", "FEASIBLE"}:
        result = refined_result.model_copy(deep=True)
        result.validation = list(min_resource_result.validation) + list(result.validation)
        result.validation.append(
            ValidationMessage(
                level="warning",
                message="最少资源候选已完成完整目标函数复排，但业务目标仍未满足，不能标记为推荐成功。",
            )
        )
        metadata = {
            "schedule_source": MINIMUM_RESOURCES_BEST_EFFORT_SOURCE,
            "recommended_schedule_source": MINIMUM_RESOURCES_BEST_EFFORT_SOURCE,
            "minimum_resource_refinement_status": refined_result.status,
            "minimum_resource_best_effort_status": refined_result.status,
            "minimum_resource_refinement_fallback_reason": fallback_reason,
            "skipped_named_refinement_reason": fallback_reason,
            "warm_start_used": bool(refined_result.stats.get("warm_start_used")),
        }
        result.stats.update(metadata)
        result.objective_breakdown.update(metadata)
        _apply_best_effort_refinement_metadata(
            result,
            schedule_source=MINIMUM_RESOURCES_BEST_EFFORT_SOURCE,
            fallback_from=MINIMUM_RESOURCES_REFINED_SOURCE,
            strict_result=min_resource_result,
            strict_failure_reason=fallback_reason,
        )
        return result

    result = min_resource_result.model_copy(deep=True)
    result.validation = list(min_resource_result.validation) + list(refined_result.validation)
    result.validation.append(
        ValidationMessage(
            level="warning",
            message="最少资源候选方案的完整目标函数复排未返回可用结果，已保留资源搜索阶段结果供诊断。",
        )
    )
    metadata = {
        "schedule_source": MINIMUM_RESOURCES_FALLBACK_SOURCE,
        "recommended_schedule_source": MINIMUM_RESOURCES_FALLBACK_SOURCE,
        "minimum_resource_refinement_status": refined_result.status,
        "minimum_resource_refinement_fallback_reason": fallback_reason,
        "minimum_resource_best_effort_status": "not_run",
        "best_effort_refinement_failure_reason": fallback_reason,
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
        max_schedule_input.model_copy(
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


def solve_min_resources_scenario(
    request: MinResourcesSolveRequest,
    *,
    workpoint_id: str | None = None,
) -> ScenarioSolveResult:
    started_at = time.perf_counter()
    scenario = request.scenario
    generated = generate_schedule_input_from_scenario(
        scenario,
        use_max_resources=True,
        workpoint_id=workpoint_id,
    )
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

    _apply_resource_scope_diagnostics(result, scenario, generated)
    _apply_request_timing(result, started_at)
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


def solve_resource_cost_scenario(
    request: ResourceCostSolveRequest,
    *,
    workpoint_id: str | None = None,
) -> ScenarioSolveResult:
    started_at = time.perf_counter()
    scenario = request.scenario
    generated = generate_schedule_input_from_scenario(
        scenario,
        use_max_resources=True,
        workpoint_id=workpoint_id,
    )
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
            _resource_linear_costs_by_pool(scenario),
            fallback_target_days=request.fallback_target_days,
        )

    _apply_resource_scope_diagnostics(result, scenario, generated)
    _apply_request_timing(result, started_at)
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
    if any(item.generated.solve_scope.mode != "ALL" for item in request.results):
        raise ValueError("单工点试算结果不能保存为全项目方案或参与全项目方案比较。")
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
    resource_resolution: EffectiveResourceResolution,
    validation: list[ValidationMessage],
    *,
    use_max_quantity: bool = False,
) -> list[Task]:
    pools_by_type: dict[str, list[EffectiveResourcePool]] = defaultdict(list)
    for pool in resource_resolution.pools:
        pools_by_type[pool.resource_type].append(pool)
    warning_keys: set[str] = set()
    error_keys: set[str] = set()
    return [
        task.model_copy(
            update={
                "compatible_resource_types": _required_resource_types_for_task(
                    task,
                    pools_by_type,
                    validation,
                    warning_keys,
                    error_keys,
                    use_max_quantity=use_max_quantity,
                )
            }
        )
        for task in tasks
    ]


def _required_resource_types_for_task(
    task: Task,
    pools_by_type: dict[str, list[EffectiveResourcePool]],
    validation: list[ValidationMessage],
    warning_keys: set[str],
    error_keys: set[str],
    *,
    use_max_quantity: bool,
) -> list[str]:
    if task.properties.get("resource_neutral"):
        return []

    default_resource_type = _default_resource_type_for_task(task)
    if not default_resource_type:
        return []

    type_pools = pools_by_type.get(default_resource_type, [])
    matching_pools = [
        pool
        for pool in type_pools
        if task.bridge_id is not None and task.bridge_id in pool.eligible_workpoint_ids
    ]
    if any(
        _is_limited_pool_available(pool, use_max_quantity=use_max_quantity)
        for pool in matching_pools
    ):
        return [default_resource_type]

    matching_unlimited_pool = next(
        (
            pool
            for pool in matching_pools
            if pool.enabled and pool.resource_mode == "UNLIMITED"
        ),
        None,
    )
    if matching_unlimited_pool is not None:
        _append_unbounded_resource_warning(
            task,
            default_resource_type,
            matching_unlimited_pool,
            validation,
            warning_keys,
        )
        return []

    if type_pools:
        _append_scoped_resource_error(
            task,
            default_resource_type,
            type_pools,
            validation,
            error_keys,
            use_max_quantity=use_max_quantity,
        )
        return [default_resource_type]

    _append_scoped_resource_error(
        task,
        default_resource_type,
        type_pools,
        validation,
        error_keys,
        use_max_quantity=use_max_quantity,
    )
    return [default_resource_type]


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


def _is_limited_pool_available(
    pool: EffectiveResourcePool | None, *, use_max_quantity: bool
) -> bool:
    if not pool or not pool.enabled or pool.resource_mode != "LIMITED":
        return False
    quantity = pool.max_quantity if use_max_quantity else pool.quantity
    return quantity > 0


def _append_scoped_resource_error(
    task: Task,
    resource_type: str,
    pools: list[EffectiveResourcePool],
    validation: list[ValidationMessage],
    error_keys: set[str],
    *,
    use_max_quantity: bool,
) -> None:
    key = f"{task.id}:{resource_type}"
    if key in error_keys:
        return
    error_keys.add(key)
    pool_ids = sorted({pool.source_pool_id for pool in pools})
    reason_codes = _resource_gap_reason_codes(
        task,
        pools,
        use_max_quantity=use_max_quantity,
    )
    entity_refs = [task.id]
    if task.bridge_id:
        entity_refs.append(task.bridge_id)
    entity_refs.extend([resource_type, *pool_ids])
    validation.append(
        ValidationMessage(
            level="error",
            code="RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE",
            subject_id=task.id,
            entity_refs=entity_refs,
            details={
                "task_id": task.id,
                "workpoint_id": task.bridge_id,
                "resource_type": resource_type,
                "relevant_pool_ids": pool_ids,
                "reason": reason_codes[0],
                "reasons": reason_codes,
            },
            message=(
                f"工作项“{task.name}”在工点 {task.bridge_id or 'unknown'} 需要资源类型"
                f" {resource_type}，但没有合法当前实例；原因：{', '.join(reason_codes)}。"
            ),
        )
    )


def _resource_gap_reason_codes(
    task: Task,
    pools: list[EffectiveResourcePool],
    *,
    use_max_quantity: bool,
) -> list[str]:
    if not task.bridge_id:
        return ["WORKPOINT_ID_INVALID"]
    if not pools:
        return ["RESOURCE_TYPE_UNCONFIGURED"]

    reasons: set[str] = set()
    for pool in pools:
        matches_workpoint = task.bridge_id in pool.eligible_workpoint_ids
        if not matches_workpoint:
            reasons.add(
                "SHARED_SCOPE_MISMATCH"
                if pool.scope_mode == "PROJECT_SHARED"
                else "WORKPOINT_ID_INVALID"
            )
            continue
        if not pool.enabled:
            reasons.add(
                "LOCAL_DISABLED"
                if pool.scope_mode == "WORKPOINT_EXCLUSIVE"
                else "SHARED_DISABLED"
            )
            continue
        if pool.resource_mode != "LIMITED":
            continue
        quantity = pool.max_quantity if use_max_quantity else pool.quantity
        if quantity <= 0:
            reasons.add(
                "LOCAL_QUANTITY_ZERO"
                if pool.scope_mode == "WORKPOINT_EXCLUSIVE"
                else "SHARED_DISABLED"
            )
    return sorted(reasons or {"RESOURCE_TYPE_UNCONFIGURED"})


def _append_unbounded_resource_warning(
    task: Task,
    resource_type: str,
    pool: EffectiveResourcePool | None,
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
            subject_id=pool.source_pool_id if pool else resource_type,
            message=f"资源“{label}”{reason}，相关工作项按资源默认充足处理，不产生资源等待。",
        )
    )


def _resource_unbounded_reason(pool: EffectiveResourcePool | None) -> str:
    if pool is None:
        return "未配置"
    if not pool.enabled:
        return "未启用"
    if pool.resource_mode == "UNLIMITED":
        return "设置为默认充足"
    if pool.max_quantity <= 0:
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
                    parallel_rule_description=pool.parallel_rule_description,
                )
            )
        if quantity == 0:
            quantity_label = "最大数量" if use_max_quantity else "默认数量"
            validation.append(
                ValidationMessage(level="warning", subject_id=pool.id, message=f"资源池“{pool.label}”的{quantity_label}为 0。")
            )
    return resources, validation


def expand_effective_resource_pools(
    effective_pools: tuple[EffectiveResourcePool, ...] | list[EffectiveResourcePool],
    *,
    use_max_quantity: bool = False,
) -> tuple[list[Resource], list[ValidationMessage]]:
    resources: list[Resource] = []
    validation: list[ValidationMessage] = []
    for pool in effective_pools:
        if not pool.enabled or pool.resource_mode == "UNLIMITED":
            continue
        quantity = pool.max_quantity if use_max_quantity else pool.quantity
        for index in range(1, quantity + 1):
            resources.append(
                Resource(
                    id=f"{pool.effective_pool_id}::instance::{index}",
                    name=(
                        f"{pool.label}{index}"
                        if pool.workpoint_id is None
                        else f"{pool.label}（{pool.workpoint_id}）{index}"
                    ),
                    type=pool.resource_type,
                    pool_id=pool.effective_pool_id,
                    pool_label=pool.label,
                    enabled=True,
                    calendar_id=pool.calendar_id,
                    scope_mode=pool.scope_mode,
                    eligible_workpoint_ids=list(pool.eligible_workpoint_ids),
                    exclusive_workpoint_id=pool.workpoint_id,
                    same_structure_resource_binding=pool.same_structure_resource_binding,
                    parallel_rule_description=pool.parallel_rule_description,
                )
            )
        if quantity == 0:
            quantity_label = "最大数量" if use_max_quantity else "默认数量"
            validation.append(
                ValidationMessage(
                    level="warning",
                    subject_id=pool.effective_pool_id,
                    message=f"资源池“{pool.label}”的{quantity_label}为 0。",
                )
            )
    return resources, validation


def _resource_linear_costs_by_pool(scenario: ScenarioInput) -> dict[str, dict[str, Any]]:
    costs_by_pool: dict[str, dict[str, Any]] = {}
    resolution = resolve_effective_resource_pools(
        project_data_version_id=scenario.project_data_version_id,
        bridges=scenario.project.bridges,
        resource_pools=scenario.resource_pools,
    )
    for pool in resolution.pools:
        if not pool.enabled or pool.resource_mode == "UNLIMITED":
            continue
        costs_by_pool[pool.effective_pool_id] = {
            "resource_pool_id": pool.effective_pool_id,
            "source_pool_id": pool.source_pool_id,
            "label": pool.label,
            "resource_type": pool.resource_type,
            "scope_mode": pool.scope_mode,
            "workpoint_id": pool.workpoint_id,
            "current_quantity": pool.quantity,
            "max_quantity": pool.max_quantity,
            "cost_type": pool.cost_type,
            "incremental_unit_cost": pool.incremental_unit_cost,
            "billing_period_days": pool.billing_period_days,
        }
    return costs_by_pool


def _apply_resource_scope_diagnostics(
    result: ScheduleResult,
    scenario: ScenarioInput,
    generated: GeneratedScheduleInput,
) -> None:
    resolution = resolve_effective_resource_pools(
        project_data_version_id=scenario.project_data_version_id,
        bridges=scenario.project.bridges,
        resource_pools=scenario.resource_pools,
    )
    raw_recommendations = (
        result.stats.get("recommended_resource_counts")
        or result.objective_breakdown.get("recommended_resource_counts")
        or []
    )
    recommended_by_pool = {
        str(item.get("resource_pool_id")): int(item.get("recommended_quantity") or 0)
        for item in raw_recommendations
        if isinstance(item, dict) and item.get("resource_pool_id")
    }
    groups = [
        {
            "resource_pool_id": pool.effective_pool_id,
            "source_pool_id": pool.source_pool_id,
            "label": pool.label,
            "resource_type": pool.resource_type,
            "scope_mode": pool.scope_mode,
            "workpoint_id": pool.workpoint_id,
            "eligible_workpoint_ids": list(pool.eligible_workpoint_ids),
            "inheritance_source": pool.inheritance_source,
            "current_quantity": pool.quantity,
            "recommended_quantity": recommended_by_pool.get(pool.effective_pool_id, pool.quantity),
            "max_quantity": pool.max_quantity,
        }
        for pool in resolution.pools
    ]
    resource_by_id = {resource.id: resource for resource in generated.schedule_input.resources}
    task_by_id = {task.id: task for task in generated.schedule_input.tasks}
    allocations = []
    for allocation in result.resource_allocations:
        resource = resource_by_id.get(allocation.resource_id)
        task = task_by_id.get(allocation.task_id)
        if resource is None:
            continue
        allocations.append(
            {
                "resource_id": allocation.resource_id,
                "task_id": allocation.task_id,
                "workpoint_id": task.bridge_id if task else None,
                "scope_mode": resource.scope_mode,
                "eligible_workpoint_ids": list(resource.eligible_workpoint_ids),
                "exclusive_workpoint_id": resource.exclusive_workpoint_id,
            }
        )
    result.stats["resource_scope_diagnostics"] = {
        "rule_version": RESOURCE_SCOPE_RULE_VERSION,
        "project_shared_transfer_time_days": 0,
        "groups": groups,
        "allocations": allocations,
    }
    has_cross_workpoint_shared_pool = any(
        pool.scope_mode == "PROJECT_SHARED" and len(pool.eligible_workpoint_ids) > 1
        for pool in resolution.pools
    )
    if has_cross_workpoint_shared_pool and not any(
        message.code == "PROJECT_SHARED_TRANSFER_ZERO_DAYS" for message in result.validation
    ):
        result.validation.append(
            ValidationMessage(
                level="info",
                code="PROJECT_SHARED_TRANSFER_ZERO_DAYS",
                message="项目共享资源跨工点串行使用，转场时间按 0 天处理。",
            )
        )


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
        height = _pier_average_height(component)
        if height is not None:
            heights.append(height)
    return max(heights) if heights else None


def _build_tasks(
    scenario: ScenarioInput,
    validation: list[ValidationMessage],
    *,
    include_girder_erection: bool = False,
    workpoint_id: str | None = None,
) -> tuple[list[Task], list[PrecedenceLink]]:
    tasks: list[Task] = []
    generated_links: list[PrecedenceLink] = []
    upper_logic_rules = _upper_structure_logic_rule_by_id(scenario.upper_structure_logic_rules)
    task_overrides = scenario.task_overrides
    inferred_levels = _inferred_control_levels(scenario)
    bridges = [
        bridge
        for bridge in scenario.project.bridges
        if workpoint_id is None or bridge.id == workpoint_id
    ]
    for bridge in sorted(bridges, key=lambda item: item.order):
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
                include_girder_erection=include_girder_erection,
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
    rule = _process_to_productivity_rule(process, component)
    if component.quantity <= 0 and not (
        component.component_type == "pier_body" and rule.quantity_source == "pier_height_m"
    ):
        validation.append(
            ValidationMessage(
                level="warning",
                subject_id=component.id,
                message=f"构件“{component.name}”的工程量为 0，已跳过。",
            )
        )
        return None
    try:
        quantity, quantity_label = _quantity_for_process(component, rule.quantity_source)
    except ValueError as exc:
        validation.append(
            ValidationMessage(
                level="error",
                subject_id=component.id,
                message=f"构件“{component.name}”{exc}",
            )
        )
        return None
    if quantity <= 0:
        validation.append(
            ValidationMessage(
                level="warning",
                subject_id=component.id,
                message=f"构件“{component.name}”的工程量为 0，已跳过。",
            )
        )
        return None
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
        structure_parameter_label=_structure_parameter_label_for_component(component),
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
    include_girder_erection: bool = False,
) -> tuple[list[Task], list[PrecedenceLink]]:
    support_completions = _lower_completion_tasks_by_support(section, lower_tasks)
    tasks: list[Task] = []
    links: list[PrecedenceLink] = []
    overrides = task_overrides or {}

    if include_girder_erection:
        simple_tasks, simple_links = _build_simple_beam_erection_tasks(
            bridge=bridge,
            section=section,
            process_library=process_library,
            validation=validation,
            support_completions=support_completions,
        )
        tasks.extend(simple_tasks)
        links.extend(simple_links)

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
        group_properties = _upper_group_properties(uppers)
        structure_parameter_label = _upper_group_parameter_label(uppers)
        control_level = _upper_group_control_level(uppers, inferred_levels, default="normal")
        task = _append_upper_task(
            tasks=tasks,
            component_id=f"{bridge.id}-{side_code}-BOX-G{group_index:02d}-CAST",
            name=f"{side_label}第{group_index}联现浇箱梁",
            component_type="cast_in_place_box_beam",
            quantity=1,
            quantity_label="1联",
            structure_parameter_label=structure_parameter_label,
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
                **group_properties,
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
    structure_parameter_label: str | None = None,
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
        structure_parameter_label=structure_parameter_label,
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


def _upper_group_properties(uppers: list[UpperStructureComponent]) -> dict[str, Any]:
    ordered = sorted(uppers, key=lambda item: item.span_index)
    structure_types = list(dict.fromkeys(upper.structure_type for upper in ordered if upper.structure_type))
    expressions = list(dict.fromkeys(upper.span_group_expression for upper in ordered if upper.span_group_expression))
    return {
        "upper_structure_type": " / ".join(structure_types),
        "support_range": _upper_group_support_range(ordered),
        "span_group_expression": " / ".join(expressions),
        "span_lengths_m": [upper.span_length_m for upper in ordered],
    }


def _upper_group_support_range(uppers: list[UpperStructureComponent]) -> str:
    if not uppers:
        return ""
    first_parts = uppers[0].support_range.split("~")
    last_parts = uppers[-1].support_range.split("~")
    return f"{first_parts[0]}~{last_parts[-1]}"


def _upper_group_parameter_label(uppers: list[UpperStructureComponent], segment_type: str | None = None) -> str:
    context = _upper_group_properties(uppers)
    parts = [
        context["upper_structure_type"],
        context["support_range"],
        context["span_group_expression"],
        segment_type or "",
    ]
    return "，".join(str(part) for part in parts if part)


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
    group_properties = _upper_group_properties(uppers)
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
                **group_properties,
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
                    **group_properties,
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
                    **group_properties,
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
        properties={**group_properties, "continuous_task_type": "side_straight_segment", "group_index": group_index, "side": "left"},
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
        properties={**group_properties, "continuous_task_type": "side_closure_segment", "group_index": group_index, "side": "left"},
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
        properties={**group_properties, "continuous_task_type": "side_straight_segment", "group_index": group_index, "side": "right"},
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
        properties={**group_properties, "continuous_task_type": "side_closure_segment", "group_index": group_index, "side": "right"},
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
                **group_properties,
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
    span_group_id = _continuous_span_group_id(bridge_id, work_section_id, properties.get("group_index"))
    span_group_name = _continuous_span_group_name(structure_name, properties.get("group_index"))
    enriched_properties = {
        **properties,
        "continuous_span_group_id": span_group_id,
        "continuous_span_group_name": span_group_name,
    }
    component = _apply_task_override(ComponentModel(
        id=component_id,
        name=name,
        component_type=CONTINUOUS_BEAM_COMPONENT_TYPE,
        quantity=quantity,
        quantity_label=quantity_label,
        structure_parameter_label=_continuous_parameter_label(enriched_properties),
        method_id=method_id,
        properties=enriched_properties,
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


def _continuous_parameter_label(properties: dict[str, Any]) -> str | None:
    segment_labels = {
        "zero_block": "0号块",
        "standard_segment_batch": "标准段",
        "side_straight_segment": "边跨连续段",
        "side_closure_segment": "边跨合龙段",
        "middle_closure_segment": "中跨合龙段",
    }
    parts = [
        properties.get("upper_structure_type"),
        properties.get("support_range"),
        properties.get("span_group_expression"),
        segment_labels.get(str(properties.get("continuous_task_type"))),
    ]
    label = "，".join(str(part) for part in parts if part)
    return label or None


def _continuous_span_group_id(bridge_id: str, work_section_id: str, group_index: Any) -> str:
    return f"{bridge_id}:{work_section_id}:continuous-beam:{group_index}"


def _continuous_span_group_name(structure_name: str, group_index: Any) -> str:
    prefix = structure_name.split("#", 1)[0].rstrip("-")
    return f"{prefix}组 {group_index}" if group_index is not None else prefix


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
            return float(component.quantity), f"{component.quantity:g}块"
        if component.component_type == CONTINUOUS_BEAM_COMPONENT_TYPE:
            unit = "块" if component.properties.get("continuous_task_type") == "zero_block" else "段"
            return float(component.quantity), f"{component.quantity:g}{unit}"
        if component.component_type == "cast_in_place_box_beam":
            return float(component.quantity), f"{component.quantity:g}联"
        if component.component_type == "pile":
            return 1.0, "1根"
        return float(component.quantity), f"{component.quantity:g}个"
    if quantity_source == "pile_length_m":
        length = _dimension_value(component, "lengthM") or _property_number(component, "length_m") or component.quantity
        return float(length), f"{float(length):g}m"
    if quantity_source == "pier_height_m":
        height = _pier_average_height(component)
        if height is None:
            raise ValueError("缺少有效墩高，无法计算工程量和工期。")
        return height, f"{height:g}m"
    if quantity_source == "deck_length_m":
        length = (
            _dimension_value(component, "lengthM")
            or _dimension_value(component, "totalLengthM")
            or _property_number(component, "length_m")
            or _property_number(component, "total_length_m")
            or component.quantity
        )
        return float(length), f"{float(length):g}m"
    return float(component.quantity), f"{component.quantity:g}个"


def _dimension_value(component: ComponentModel, key: str) -> float | None:
    dimensions = component.properties.get("dimensions_m")
    if isinstance(dimensions, dict) and dimensions.get(key) is not None:
        return _positive_number(dimensions[key])
    return None


def _property_number(component: ComponentModel, key: str) -> float | None:
    return _positive_number(component.properties.get(key))


def _positive_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _pier_average_height(component: ComponentModel) -> float | None:
    column_heights = component.properties.get("column_heights_m")
    if isinstance(column_heights, list):
        valid_heights = [height for value in column_heights if (height := _positive_number(value)) is not None]
        if valid_heights:
            return sum(valid_heights) / len(valid_heights)

    for key in ("height_m", "heightM", "pier_height_m", "pierHeightM"):
        if (height := _property_number(component, key)) is not None:
            return height
    for key in ("heightM", "height_m"):
        if (height := _dimension_value(component, key)) is not None:
            return height

    count = _property_number(component, "count") or 1
    if count <= 1 and component.quantity > 0:
        return float(component.quantity)
    return None


def _structure_parameter_label_for_component(component: ComponentModel) -> str | None:
    if component.structure_parameter_label:
        return component.structure_parameter_label

    properties = component.properties
    form = properties.get("form")
    form_label = str(form).strip() if form is not None else ""
    dimensions = properties.get("dimensions_m")
    count = _property_number(component, "count")

    if component.component_type == "pile":
        diameter = _property_number(component, "diameter_m") or _dimension_value(component, "diameterM")
        parts = [form_label or "桩基础"]
        if diameter is not None:
            parts.append(f"桩径{diameter:g}m")
        return "，".join(parts)

    if component.component_type == "pier_body":
        parts = [form_label or "墩柱"]
        if isinstance(dimensions, list) and dimensions:
            values = [value for raw in dimensions if (value := _positive_number(raw)) is not None]
            if len(values) == 1:
                parts.append(f"柱径{values[0]:g}m")
            elif values:
                parts.append("截面" + " × ".join(f"{value:g}m" for value in values))
        if count is not None:
            parts.append(f"{count:g}根")
        return "，".join(parts)

    if isinstance(dimensions, list):
        values = [value for raw in dimensions if (value := _positive_number(raw)) is not None]
        if values:
            return " × ".join(f"{value:g}m" for value in values)
    return form_label or None


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


def _apply_request_timing(result: ScheduleResult, started_at: float) -> None:
    elapsed = time.perf_counter() - started_at
    timing = {
        "total_elapsed_seconds": elapsed,
        "request_elapsed_seconds": elapsed,
        "solver_time_limit_enabled": result.stats.get("solver_time_limit_enabled", True),
    }
    result.stats.update(timing)
    result.objective_breakdown.update(timing)


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
        "total_elapsed_seconds": result.stats.get("total_elapsed_seconds"),
        "request_elapsed_seconds": result.stats.get("request_elapsed_seconds"),
        "wall_time_seconds": result.stats.get("wall_time_seconds"),
        "cp_sat_wall_time_seconds": result.stats.get("cp_sat_wall_time_seconds"),
        "solver_time_limit_enabled": result.stats.get("solver_time_limit_enabled", False),
    }
