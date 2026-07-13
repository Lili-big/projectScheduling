from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from ..models import (
    GeneratedScheduleInput,
    PrecedenceLink,
    ResourceAssistantBatchSolveRequest,
    ResourceAssistantBatchSolveResponse,
    ResourceAssistantComparison,
    ResourceAssistantControlPierSummary,
    ResourceAssistantCoreMetrics,
    ResourceAssistantDemoCost,
    ResourceAssistantGenerationRecord,
    ResourceAssistantInitialRequest,
    ResourceAssistantInitialResponse,
    ResourceAssistantMetricRow,
    ResourceAssistantPlan,
    ResourceAssistantPlanProfile,
    ResourceAssistantPlanResult,
    ResourceAssistantProjectProfile,
    ResourceAssistantRecommendation,
    ResourceAssistantRecommendationResponse,
    ResourceAssistantReferenceExample,
    ResourceAssistantResultsRequest,
    ResourceAssistantSingleSolveRequest,
    ResourceAssistantSingleSolveResponse,
    ResourceAssistantTransferPenalty,
    ResourceAssistantUpdatePlanRequest,
    ResourceAssistantUpdatePlanResponse,
    ResourcePool,
    ScheduleResult,
    ScenarioInput,
    ScheduledTask,
    Task,
    ValidationMessage,
    WorkSectionSide,
)
from ..scenario import generate_schedule_input_from_scenario, solve_ai_strict_fixed_resource_scenario
from .ai_resource_explainer import (
    explain_recommendation,
    generate_resource_plan_payload,
    llm_config_status,
)


PILE_RESOURCE_TYPES = {"rotary_drill", "circulation_drill", "impact_drill", "manual_pile_team"}
LOWER_STRUCTURE_COMPONENT_TYPES = {
    "pile",
    "cap",
    "spread_foundation",
    "ground_tie_beam",
    "middle_tie_beam",
    "pier_body",
    "cap_beam",
    "abutment_body",
}
CONTINUOUS_BEAM_COMPONENT_TYPE = "cast_in_place_continuous_beam"
CONTINUOUS_BEAM_RESOURCE_TYPE = "cast_in_place_continuous_beam_team"
AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS = 30.0

PROFILE_LABELS: dict[str, str] = {
    "economy": "方案A 经济方案",
    "balanced": "方案B 平衡方案",
    "crash": "方案C 抢工方案",
}
PROFILE_POSITIONING: dict[str, str] = {
    "economy": "控制成本、资源投入克制，优先保证控制墩和连续梁主线。",
    "balanced": "兼顾工期与投入，提升墩柱模板和连续梁班组以降低等待。",
    "crash": "面向节点抢工，增加桩机、墩柱模板和盖梁模板，压缩关键资源排队。",
}
PROFILE_ORDER: dict[str, int] = {"economy": 0, "balanced": 1, "crash": 2, "custom": 3}
DEMO_RESOURCE_UNIT_COSTS: dict[str, float] = {
    "rotary_drill": 5800,
    "circulation_drill": 4800,
    "impact_drill": 5200,
    "manual_pile_team": 3200,
    "cap_team": 2600,
    "pier_body_team": 3000,
    "cap_beam_team": 3600,
    "cast_in_place_continuous_beam_team": 9800,
}
DEMO_MOBILIZATION_COSTS: dict[str, float] = {
    "rotary_drill": 18000,
    "circulation_drill": 15000,
    "impact_drill": 17000,
    "manual_pile_team": 8000,
    "cap_team": 6000,
    "pier_body_team": 8000,
    "cap_beam_team": 9000,
    "cast_in_place_continuous_beam_team": 30000,
}


def initialize_resource_assistant(request: ResourceAssistantInitialRequest) -> ResourceAssistantInitialResponse:
    generated = generate_schedule_input_from_scenario(request.scenario)
    profile = build_project_profile(request.scenario, generated)
    reference_examples = build_reference_examples(request.scenario, profile)
    profile.reference_examples = reference_examples
    llm_generation_context = build_llm_generation_context(profile, request.scenario)

    generation_source = "local_fallback"
    fallback_reason: str | None = None
    raw_plan_payload: list[dict[str, Any]] | None = None
    llm_status = llm_config_status()
    if request.generation_mode == "llm_first":
        raw_plan_payload, llm_status = generate_resource_plan_payload(llm_generation_context)
        validation_errors = _validate_raw_plan_payload(raw_plan_payload, request.scenario, profile)
        if raw_plan_payload and validation_errors:
            raw_plan_payload, llm_status = generate_resource_plan_payload(
                llm_generation_context,
                validation_errors=validation_errors,
            )
            validation_errors = _validate_raw_plan_payload(raw_plan_payload, request.scenario, profile)
        if raw_plan_payload and not validation_errors:
            generation_source = "llm"
        elif raw_plan_payload:
            raw_plan_payload = None
            fallback_reason = "LLM 三方案输出在一次纠错后仍不符合资源硬规则，已使用项目确定性基线。"
        elif llm_status.warning:
            fallback_reason = llm_status.warning

    plans = _plans_from_payload_or_fallback(
        scenario=request.scenario,
        raw_plans=raw_plan_payload,
        generation_source=generation_source,
        reference_examples=reference_examples,
    )
    generation_id = _stable_hash(
        {
            "scenario": request.scenario.model_dump(mode="json"),
            "plans": [plan.model_dump(mode="json") for plan in plans],
            "source": generation_source,
        }
    )[:12]
    generation = ResourceAssistantGenerationRecord(
        generation_id=f"resource-generation-{generation_id}",
        source=generation_source,
        input_fingerprint=_scenario_fingerprint(request.scenario),
        prompt_summary="工程画像 + 约束提示 + 非硬约束参考样例一次性生成三类资源配置。",
        reference_examples_used=reference_examples,
        constraint_hints_used=profile.constraint_hints,
        raw_output_available=bool(raw_plan_payload),
        parsed_plan_ids=[plan.scenario_id for plan in plans],
        validation_status=_plan_validation_status(plans),
        fallback_reason=fallback_reason,
    )
    return ResourceAssistantInitialResponse(
        project_profile=profile,
        resource_plans=plans,
        plan_generation=generation,
        reference_examples=reference_examples,
        constraint_hints=profile.constraint_hints,
        llm_generation_context=llm_generation_context,
        llm_config_status=llm_status,
        diagnostics=list(generated.validation),
    )


def update_resource_plan(request: ResourceAssistantUpdatePlanRequest) -> ResourceAssistantUpdatePlanResponse:
    plan = request.resource_plan
    diagnostics: list[ValidationMessage] = []
    if plan is None:
        raise ValueError("resource_plan is required for resource assistant plan update.")
    pools_by_type = {pool.type: pool.model_copy(deep=True) for pool in plan.resource_pools}
    for resource_type, quantity_value in request.resource_updates.items():
        pool = pools_by_type.get(resource_type)
        if pool is None:
            diagnostics.append(
                ValidationMessage(level="warning", subject_id=resource_type, message=f"资源类型 {resource_type} 不在当前方案中，已忽略。")
            )
            continue
        quantity = max(0, int(quantity_value or 0))
        max_quantity = max(quantity, int(pool.max_quantity or 0))
        pools_by_type[resource_type] = pool.model_copy(update={"quantity": quantity, "max_quantity": max_quantity})

    updated = plan.model_copy(
        update={
            "generation_source": "user_adjusted",
            "resource_pools": list(pools_by_type.values()),
            "changed_from_standard": True,
            "solve_status": "stale",
            "stale_reason": "资源数量已调整，原求解结果和推荐解释需要重新计算。",
            "validation_messages": _validate_plan_resource_pools(list(pools_by_type.values())),
        }
    )
    return ResourceAssistantUpdatePlanResponse(
        resource_plan=updated,
        invalidated_result_ids=[request.plan_id],
        generation_source="user_adjusted",
        diagnostics=diagnostics,
    )


def batch_solve_resource_plans(request: ResourceAssistantBatchSolveRequest) -> ResourceAssistantBatchSolveResponse:
    profile: ResourceAssistantProjectProfile | None = None
    selected_plan_ids = _selected_plan_ids(request)
    solved_plans: list[ResourceAssistantPlan] = []
    plan_results: list[ResourceAssistantPlanResult] = []
    diagnostics: list[ValidationMessage] = []

    for plan in _ordered_plans(request.resource_plans):
        if selected_plan_ids is not None and plan.scenario_id not in selected_plan_ids:
            solved_plans.append(plan)
            continue
        solved_plan, plan_result, plan_diagnostics = _solve_single_plan(request.scenario, plan, profile)
        solved_plans.append(solved_plan)
        plan_results.append(plan_result)
        diagnostics.extend(plan_diagnostics)
        if profile is None and plan_result.generated is not None:
            profile = build_project_profile(request.scenario, plan_result.generated)

    if profile is None:
        profile = build_project_profile(request.scenario, generate_schedule_input_from_scenario(request.scenario))

    comparison = build_comparison(solved_plans, plan_results)
    recommendation = build_deterministic_recommendation(solved_plans, plan_results)
    comparison.best_scenario_id = recommendation.recommended_scenario_id
    recommendation = explain_recommendation(recommendation, comparison)
    return ResourceAssistantBatchSolveResponse(
        project_profile=profile,
        resource_plans=solved_plans,
        plan_results=plan_results,
        comparison=comparison,
        recommendation=recommendation,
        diagnostics=diagnostics,
    )


def solve_resource_plan(request: ResourceAssistantSingleSolveRequest) -> ResourceAssistantSingleSolveResponse:
    solved_plan, plan_result, diagnostics = _solve_single_plan(request.scenario, request.resource_plan, None)
    return ResourceAssistantSingleSolveResponse(
        resource_plan=solved_plan,
        plan_result=plan_result,
        diagnostics=diagnostics,
    )


def compare_resource_plan_results(request: ResourceAssistantResultsRequest) -> ResourceAssistantComparison:
    _validate_result_ids(request, require_all=False)
    return build_comparison(request.resource_plans, request.plan_results)


def generate_resource_plan_recommendation(
    request: ResourceAssistantResultsRequest,
) -> ResourceAssistantRecommendationResponse:
    _validate_result_ids(request, require_all=True)
    comparison = build_comparison(request.resource_plans, request.plan_results)
    recommendation = build_deterministic_recommendation(request.resource_plans, request.plan_results)
    comparison.best_scenario_id = recommendation.recommended_scenario_id
    return ResourceAssistantRecommendationResponse(
        comparison=comparison,
        recommendation=explain_recommendation(recommendation, comparison),
    )


def _validate_result_ids(request: ResourceAssistantResultsRequest, *, require_all: bool) -> None:
    plan_ids = [plan.scenario_id for plan in request.resource_plans]
    result_ids = [result.scenario_id for result in request.plan_results]
    if len(plan_ids) != len(set(plan_ids)):
        raise ValueError("资源方案标识重复，无法生成对比结果。")
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("方案结果标识重复，无法生成对比结果。")
    unknown_result_ids = set(result_ids) - set(plan_ids)
    if unknown_result_ids:
        raise ValueError("方案结果包含当前资源方案之外的标识。")
    if require_all and (len(plan_ids) != 3 or set(result_ids) != set(plan_ids)):
        raise ValueError("请先完成经济、平衡和抢工三套方案的求解，再生成推荐。")


def build_project_profile(scenario: ScenarioInput, generated: GeneratedScheduleInput | None = None) -> ResourceAssistantProjectProfile:
    generated = generated or generate_schedule_input_from_scenario(scenario)
    project = scenario.project
    work_sections = [
        section
        for bridge in project.bridges
        for section in bridge.work_sections
    ]
    structures = [
        structure
        for section in work_sections
        for structure in section.structures
    ]
    continuous_groups = _continuous_beam_groups_for_project(scenario)
    control_piers = _control_piers_for_project(scenario, generated.schedule_input.tasks, continuous_groups)
    resource_types = _resource_type_profile(scenario.resource_pools, generated.schedule_input.tasks)
    critical_path_candidates = _critical_path_candidates(generated.schedule_input.tasks, control_piers, continuous_groups)
    constraint_hints = _constraint_hints(scenario, control_piers, continuous_groups)
    return ResourceAssistantProjectProfile(
        project_name=project.project_name,
        start_date=project.start_date,
        bridge_count=len(project.bridges),
        work_section_count=len(work_sections),
        structure_count=len(structures),
        task_count=len(generated.schedule_input.tasks),
        control_piers=control_piers,
        resource_types=resource_types,
        continuous_beam_groups=continuous_groups,
        critical_path_candidates=critical_path_candidates,
        constraint_hints=constraint_hints,
        data_quality_messages=list(generated.validation),
    )


def build_reference_examples(
    scenario: ScenarioInput,
    project_profile: ResourceAssistantProjectProfile | None = None,
) -> list[ResourceAssistantReferenceExample]:
    profile = project_profile or build_project_profile(scenario)
    profile_quantities = _deterministic_resource_baseline(scenario, profile)
    examples: list[ResourceAssistantReferenceExample] = []
    for profile, template in profile_quantities.items():
        examples.append(
            ResourceAssistantReferenceExample(
                profile=profile,  # type: ignore[arg-type]
                description=f"{PROFILE_LABELS[profile]}参考样例，供 LLM 理解经济/平衡/抢工投入梯度，不作为固定方案。",
                resource_quantities=template,
                is_hard_constraint=False,
            )
        )
    return examples


def summarize_core_metrics(
    generated: GeneratedScheduleInput | None,
    result: ScheduleResult | None,
    profile: ResourceAssistantProjectProfile,
) -> ResourceAssistantCoreMetrics:
    if result is None or result.status not in {"OPTIMAL", "FEASIBLE"}:
        reason = "方案没有可用排程结果。"
        if result is not None:
            reason = f"方案状态为 {result.status}，核心指标不可用。"
        return ResourceAssistantCoreMetrics(target_status="not_available", not_available_reasons=[reason])

    total_days = result.objective_days
    control_release, control_wait = _control_pier_release_metrics(result, profile)
    first_cb_start, all_cb_started = _continuous_beam_start_dates(result)
    resource_utilization, resource_idle_waits = _resource_utilization_metrics(generated, result)
    predecessor_waits, continuous_waits = _predecessor_waits(generated, result)
    wait_values = [*resource_idle_waits, *predecessor_waits]
    transfer_penalty = _transfer_penalty(result)
    demo_cost = _demo_cost(generated, result, transfer_penalty)
    target = result.stats.get("target_achievement")
    target_status = target.get("target_status") if isinstance(target, dict) else "met"
    not_available: list[str] = []
    if not control_release:
        not_available.append("未识别到控制墩释放时间。")
    if first_cb_start is None:
        not_available.append("未生成连续梁任务，连续梁开工指标不可用。")
    return ResourceAssistantCoreMetrics(
        total_days=total_days,
        plan_finish_date=result.plan_finish_date,
        control_pier_release_dates=control_release,
        first_continuous_beam_start_date=first_cb_start,
        all_continuous_beams_started_date=all_cb_started,
        resource_utilization_by_type=resource_utilization,
        average_wait_days=round(sum(wait_values) / len(wait_values), 1) if wait_values else 0,
        max_wait_days=max(wait_values) if wait_values else 0,
        control_pier_wait_days=control_wait,
        continuous_beam_wait_days=max(continuous_waits) if continuous_waits else None,
        transfer_penalty=transfer_penalty,
        demo_cost=demo_cost,
        target_status=str(target_status or "not_evaluated"),
        not_available_reasons=not_available,
    )


def build_comparison(
    plans: list[ResourceAssistantPlan],
    plan_results: list[ResourceAssistantPlanResult],
) -> ResourceAssistantComparison:
    result_by_id = {result.scenario_id: result for result in plan_results}
    columns = [
        {
            "scenario_id": plan.scenario_id,
            "scenario_name": plan.scenario_name,
            "profile": plan.profile,
            "solve_status": plan.solve_status,
        }
        for plan in _ordered_plans(plans)
    ]
    outcome_values = {
        scenario_id: {
            "value": _schedule_outcome_status(plan_result),
            "not_available_reasons": (
                ["缺少工期目标，无法评估"]
                if _schedule_outcome_reason(plan_result) == "target_missing"
                else plan_result.metrics.not_available_reasons
            ),
        }
        for scenario_id, plan_result in result_by_id.items()
    }
    rows = [
        ResourceAssistantMetricRow(
            metric_id="schedule_outcome_status",
            metric_name="方案目标状态",
            values=outcome_values,
            source_type="solver_result",
            description="严格固定资源求解的三态业务结论；只有工期目标已满足可参与推荐。",
        ),
        _metric_row("total_days", "总工期", "天", "solver_result", "CP-SAT 求解返回的项目完工跨度。", result_by_id, lambda m: m.total_days),
        _metric_row("plan_finish_date", "预计完工日期", "", "solver_result", "CP-SAT 求解返回的计划完成日期。", result_by_id, lambda m: m.plan_finish_date),
        _metric_row(
            "control_pier_release_dates",
            "控制墩释放时间",
            "",
            "derived_diagnostic",
            "由控制墩下部结构相关任务最晚完成时间派生。",
            result_by_id,
            lambda m: m.control_pier_release_dates,
        ),
        _metric_row(
            "first_continuous_beam_start_date",
            "首个连续梁开工",
            "",
            "derived_diagnostic",
            "由连续梁任务最早开工日期派生。",
            result_by_id,
            lambda m: m.first_continuous_beam_start_date,
        ),
        _metric_row(
            "all_continuous_beams_started_date",
            "连续梁全部展开",
            "",
            "derived_diagnostic",
            "由各连续梁任务组首个任务开工日期的最大值派生。",
            result_by_id,
            lambda m: m.all_continuous_beams_started_date,
        ),
        _metric_row(
            "resource_utilization_by_type",
            "资源利用率",
            "%",
            "derived_diagnostic",
            "按资源类型统计资源占用工日 / 资源数量 / 方案总工期。",
            result_by_id,
            lambda m: m.resource_utilization_by_type,
        ),
        _metric_row(
            "average_wait_days",
            "平均等待时间",
            "天",
            "derived_diagnostic",
            "资源空闲间隔与任务前置满足后的等待合并计算。",
            result_by_id,
            lambda m: m.average_wait_days,
        ),
        _metric_row(
            "max_wait_days",
            "最大等待时间",
            "天",
            "derived_diagnostic",
            "资源空闲间隔和任务前置满足后等待中的最大值。",
            result_by_id,
            lambda m: m.max_wait_days,
        ),
        _metric_row(
            "transfer_penalty",
            "转场惩罚",
            "分",
            "derived_diagnostic",
            "复用现有连续性诊断，MVP 阶段仅作为解释口径。",
            result_by_id,
            lambda m: m.transfer_penalty.model_dump(mode="json"),
        ),
        _metric_row(
            "demo_cost",
            "成本估算",
            "元",
            "demo_estimate",
            "基于演示默认单价、资源数量和求解工期估算，仅供横向比较。",
            result_by_id,
            lambda m: m.demo_cost.model_dump(mode="json"),
        ),
    ]
    return ResourceAssistantComparison(
        scenario_columns=columns,
        metric_rows=rows,
        comparison_notes=[
            "推荐结论由系统基于 CP-SAT 求解指标确定，AI 仅负责解释。",
            "转场惩罚和成本为演示口径，不作为 CP-SAT 硬约束。",
        ],
    )


def build_deterministic_recommendation(
    plans: list[ResourceAssistantPlan],
    plan_results: list[ResourceAssistantPlanResult],
) -> ResourceAssistantRecommendation:
    result_by_id = {result.scenario_id: result for result in plan_results}
    feasible = [
        plan
        for plan in _ordered_plans(plans)
        if plan.scenario_id in result_by_id
        and result_by_id[plan.scenario_id].result is not None
        and result_by_id[plan.scenario_id].result.status in {"OPTIMAL", "FEASIBLE"}
        and _plan_result_target_met(result_by_id[plan.scenario_id])
    ]
    if not feasible:
        return ResourceAssistantRecommendation(
            recommended_scenario_id=None,
            recommendation_status="insufficient_results",
            rule_reason="当前没有工期目标已满足的方案，无法生成正式推荐。",
            evidence=["工期目标未满足和当前资源未获得可行排程的方案不进入推荐候选集。"],
            risk_notes=["可查看已有排程和延期诊断后手动调整资源，再重新求解。"],
            marginal_benefit_notes=["无可行结果时不计算边际收益。"],
            llm_status=llm_config_status(),
        )

    candidates = feasible
    by_profile = {plan.profile: plan for plan in candidates}
    economy = by_profile.get("economy")
    balanced = by_profile.get("balanced")
    crash = by_profile.get("crash")

    recommended = min(candidates, key=lambda plan: _recommendation_score(result_by_id[plan.scenario_id].metrics))
    reason = "按工期、目标满足、等待和演示成本综合评分选择。"
    if crash and not economy and not balanced:
        recommended = crash
        reason = "只有抢工方案在当前指标组合下满足强节点或得到可比较可行结果。"
    elif balanced and crash:
        balanced_metrics = result_by_id[balanced.scenario_id].metrics
        crash_metrics = result_by_id[crash.scenario_id].metrics
        duration_gain = max(0, (balanced_metrics.total_days or 0) - (crash_metrics.total_days or 0))
        cost_delta = crash_metrics.demo_cost.total_cost - balanced_metrics.demo_cost.total_cost
        low_marginal_gain = duration_gain <= max(5, int((balanced_metrics.total_days or 0) * 0.03))
        costly = balanced_metrics.demo_cost.total_cost > 0 and cost_delta / balanced_metrics.demo_cost.total_cost >= 0.08
        if _target_met(balanced_metrics) and low_marginal_gain and costly:
            recommended = balanced
            reason = "平衡方案已满足节点，抢工方案工期边际收益不足且演示成本更高。"
    if economy and recommended == economy:
        economy_wait = result_by_id[economy.scenario_id].metrics.control_pier_wait_days or 0
        if economy_wait > 7 and balanced:
            recommended = balanced
            reason = "经济方案控制墩等待偏长，平衡方案能降低控制链风险。"

    metrics = result_by_id[recommended.scenario_id].metrics
    evidence = _recommendation_evidence(recommended, metrics, result_by_id[recommended.scenario_id])
    risks = _recommendation_risks(recommended, metrics)
    marginal = _marginal_benefit_notes(recommended, result_by_id, plans)
    return ResourceAssistantRecommendation(
        recommended_scenario_id=recommended.scenario_id,
        recommendation_status="recommended",
        rule_reason=reason,
        evidence=evidence,
        risk_notes=risks,
        marginal_benefit_notes=marginal,
        llm_status=llm_config_status(),
    )


def build_llm_generation_context(profile: ResourceAssistantProjectProfile, scenario: ScenarioInput) -> dict[str, Any]:
    return {
        "project_profile": profile.model_dump(mode="json"),
        "resource_types": profile.resource_types,
        "constraint_hints": profile.constraint_hints,
        "reference_examples": [item.model_dump(mode="json") for item in profile.reference_examples],
        "current_resource_pools": [pool.model_dump(mode="json") for pool in scenario.resource_pools],
        "rules": [
            "一次性输出 economy、balanced、crash 三套方案。",
            "只能输出 current_resource_pools 中存在的资源类型。",
            "桩机必须按工艺资源类型分别给数量。",
            "任何实际工作量为零、未映射、禁用或数据异常的资源，economy、balanced、crash 均必须为 0。",
            "资源数量必须是非负整数，不得超过 current_resource_pools 中的原始 max_quantity。",
            "同类有效资源数量必须满足 economy <= balanced <= crash。",
            "organization_strategy 必须是字符串，不得输出 recommended_profile 或求解前最优方案推荐。",
            "不得输出任务起止日期或最终施工计划。",
        ],
    }


def _resource_workload_states(
    scenario: ScenarioInput,
    profile: ResourceAssistantProjectProfile,
) -> dict[str, dict[str, Any]]:
    demand_by_type = {str(item.get("resource_type")): item for item in profile.resource_types}
    states: dict[str, dict[str, Any]] = {}
    for pool in scenario.resource_pools:
        demand = demand_by_type.get(pool.type, {})
        task_count = int(demand.get("task_count") or 0)
        duration_days = int(demand.get("duration_days") or 0)
        if not pool.enabled:
            status, reason = "DISABLED", "资源池已禁用"
        elif task_count <= 0 or duration_days <= 0:
            status, reason = "UNUSED_OR_UNMAPPED", "当前生成任务没有该资源的实际工作量"
        elif pool.quantity is None or (pool.max_quantity is not None and pool.max_quantity < 0):
            status, reason = "DATA_INVALID", "资源数量或上限数据无效"
        elif pool.resource_mode == "UNLIMITED":
            status, reason = "UNLIMITED", "存在实际工作量且未设置显式数量上限"
        else:
            status, reason = "ACTIVE", "存在匹配任务和累计需求工期"
        states[pool.type] = {
            "resource_type": pool.type,
            "status": status,
            "matched_task_count": task_count,
            "total_required_days": duration_days,
            "current_quantity": int(pool.quantity or 0),
            "max_quantity": pool.max_quantity,
            "diagnostic_reason": reason,
        }
    return states


def _deterministic_resource_baseline(
    scenario: ScenarioInput,
    profile: ResourceAssistantProjectProfile,
) -> dict[str, dict[str, int]]:
    states = _resource_workload_states(scenario, profile)
    result = {profile_name: {} for profile_name in ("economy", "balanced", "crash")}
    control_count = len(profile.control_piers)
    continuous_count = len(profile.continuous_beam_groups)
    pier_values: tuple[int, int, int] | None = None

    pier_pool = next((pool for pool in scenario.resource_pools if pool.type == "pier_body_team"), None)
    if pier_pool and states[pier_pool.type]["status"] in {"ACTIVE", "UNLIMITED"}:
        current = max(1, int(pier_pool.quantity or 0))
        economy = max(control_count, math.ceil(current * 0.75))
        balanced = max(economy, current)
        crash = max(balanced, current + math.ceil(control_count * 0.5))
        pier_values = (economy, balanced, crash)

    for pool in scenario.resource_pools:
        state = states[pool.type]
        if state["status"] not in {"ACTIVE", "UNLIMITED"}:
            values = (0, 0, 0)
        else:
            current = max(1, int(pool.quantity or 0))
            if pool.type == "pier_body_team" and pier_values is not None:
                values = pier_values
            elif pool.type in {"cap_team", "cap_beam_team"} and pier_values is not None:
                values = (
                    max(1, math.ceil(pier_values[0] * 0.5)),
                    max(1, math.ceil(pier_values[1] * 0.5)),
                    max(1, math.ceil(pier_values[2] * 0.75)),
                )
            elif pool.type == CONTINUOUS_BEAM_RESOURCE_TYPE:
                values = (math.ceil(continuous_count * 0.5), continuous_count, continuous_count)
            elif pool.type in PILE_RESOURCE_TYPES:
                values = (math.ceil(current * 0.75), current, math.ceil(current * 1.25))
            else:
                values = (math.ceil(current * 0.75), current, math.ceil(current * 1.25))

        limited_values: list[int] = []
        previous = 0
        for value in values:
            normalized = max(previous, int(value))
            if pool.max_quantity is not None:
                normalized = min(normalized, int(pool.max_quantity))
            limited_values.append(normalized)
            previous = normalized
        for profile_name, quantity in zip(("economy", "balanced", "crash"), limited_values):
            result[profile_name][pool.type] = quantity
    return result


def _validate_raw_plan_payload(
    raw_plans: list[dict[str, Any]] | None,
    scenario: ScenarioInput,
    profile: ResourceAssistantProjectProfile,
) -> list[dict[str, Any]]:
    if not raw_plans:
        return []
    errors: list[dict[str, Any]] = []
    expected_profiles = ("economy", "balanced", "crash")
    raw_by_profile = _raw_plans_by_profile(raw_plans)
    if len(raw_plans) != 3 or set(raw_by_profile) != set(expected_profiles):
        errors.append({"code": "INVALID_PROFILE_SET", "expected": "恰好包含 economy、balanced、crash 三个唯一方案"})
        return errors
    pools = {pool.type: pool for pool in scenario.resource_pools}
    states = _resource_workload_states(scenario, profile)
    parsed: dict[str, dict[str, int]] = {}
    for profile_name in expected_profiles:
        raw = raw_by_profile[profile_name]
        quantities = raw.get("resource_quantities")
        if not isinstance(quantities, dict):
            errors.append({"code": "INVALID_RESOURCE_MAP", "profile": profile_name, "expected": "resource_quantities 必须是对象"})
            continue
        parsed[profile_name] = {}
        for resource_type, value in quantities.items():
            if resource_type not in pools:
                errors.append({"code": "UNKNOWN_RESOURCE_TYPE", "profile": profile_name, "resource_type": resource_type, "actual": value, "expected": "仅允许 current_resource_pools 中的资源类型"})
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append({"code": "INVALID_QUANTITY", "profile": profile_name, "resource_type": resource_type, "actual": value, "expected": "非负整数"})
                continue
            parsed[profile_name][resource_type] = value
            pool = pools[resource_type]
            if states[resource_type]["status"] not in {"ACTIVE", "UNLIMITED"} and value != 0:
                errors.append({"code": "ZERO_WORKLOAD_NONZERO", "profile": profile_name, "resource_type": resource_type, "actual": value, "expected": 0})
            if pool.max_quantity is not None and value > pool.max_quantity:
                errors.append({"code": "MAX_QUANTITY_EXCEEDED", "profile": profile_name, "resource_type": resource_type, "actual": value, "expected": f"<= {pool.max_quantity}"})
        missing = set(pools) - set(quantities)
        for resource_type in sorted(missing):
            errors.append({"code": "MISSING_RESOURCE_TYPE", "profile": profile_name, "resource_type": resource_type, "expected": "完整输出所有当前资源类型"})
        if not isinstance(raw.get("organization_strategy"), str):
            errors.append({"code": "INVALID_STRATEGY_TYPE", "profile": profile_name, "expected": "organization_strategy 必须是字符串"})
    for resource_type in pools:
        if all(resource_type in parsed.get(name, {}) for name in expected_profiles):
            values = [parsed[name][resource_type] for name in expected_profiles]
            if values != sorted(values):
                errors.append({"code": "NON_MONOTONIC_QUANTITY", "resource_type": resource_type, "actual": values, "expected": "economy <= balanced <= crash"})
    return errors


def _plans_from_payload_or_fallback(
    *,
    scenario: ScenarioInput,
    raw_plans: list[dict[str, Any]] | None,
    generation_source: str,
    reference_examples: list[ResourceAssistantReferenceExample],
) -> list[ResourceAssistantPlan]:
    raw_by_profile = _raw_plans_by_profile(raw_plans or [])
    if not raw_by_profile:
        raw_by_profile = {
            example.profile: {
                "profile": example.profile,
                "positioning": PROFILE_POSITIONING[example.profile],
                "resource_quantities": example.resource_quantities,
                "organization_strategy": _fallback_strategy(example.profile),
                "generation_rationale": "未配置或未成功调用外部大模型，使用本地参考样例生成演示初始值。",
                "applicable_scenarios": _fallback_applicable_scenarios(example.profile),
                "expected_risks": _fallback_risks(example.profile),
                "reference_example_used": example.profile,
            }
            for example in reference_examples
        }
        generation_source = "local_fallback"

    plans: list[ResourceAssistantPlan] = []
    for profile in ("economy", "balanced", "crash"):
        raw = raw_by_profile.get(profile) or {}
        quantities = _resource_quantities_from_raw(raw)
        pools = _resource_pools_with_quantities(scenario.resource_pools, quantities)
        validation_messages = _validate_plan_resource_pools(pools, allowed_types={pool.type for pool in scenario.resource_pools})
        plans.append(
            ResourceAssistantPlan(
                scenario_id=f"{scenario.scenario_id}-ai-{profile}",
                scenario_name=str(raw.get("scenario_name") or PROFILE_LABELS[profile]),
                profile=profile,  # type: ignore[arg-type]
                positioning=str(raw.get("positioning") or PROFILE_POSITIONING[profile]),
                generation_source=generation_source,  # type: ignore[arg-type]
                generation_rationale=str(raw.get("generation_rationale") or "基于工程画像、约束提示和参考样例生成。"),
                reference_example_used=str(raw.get("reference_example_used") or profile),
                organization_strategy=str(raw.get("organization_strategy") or _fallback_strategy(profile)),
                validation_messages=validation_messages,
                applicable_scenarios=str(raw.get("applicable_scenarios") or _fallback_applicable_scenarios(profile)),
                expected_risks=str(raw.get("expected_risks") or _fallback_risks(profile)),
                resource_pools=pools,
                changed_from_standard=False,
                solve_status="ready_to_solve",
            )
        )
    return plans


def _raw_plans_by_profile(raw_plans: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in raw_plans:
        profile = str(raw.get("profile") or "").strip().lower()
        if profile in {"economy", "balanced", "crash"}:
            result[profile] = raw
    return result


def _resource_quantities_from_raw(raw: dict[str, Any]) -> dict[str, int]:
    value = raw.get("resource_quantities") or raw.get("resources") or {}
    if not isinstance(value, dict):
        return {}
    quantities: dict[str, int] = {}
    for resource_type, quantity_value in value.items():
        try:
            quantities[str(resource_type)] = max(0, int(quantity_value))
        except (TypeError, ValueError):
            continue
    return quantities


def _resource_pools_with_quantities(base_pools: list[ResourcePool], quantities: dict[str, int]) -> list[ResourcePool]:
    updated: list[ResourcePool] = []
    for pool in base_pools:
        quantity = 0 if not pool.enabled else quantities.get(pool.type, pool.quantity or 0)
        quantity = max(0, int(quantity or 0))
        if pool.max_quantity is not None:
            quantity = min(quantity, int(pool.max_quantity))
        updated.append(pool.model_copy(deep=True, update={"quantity": quantity, "max_quantity": pool.max_quantity}))
    return updated


def _validate_plan_resource_pools(
    pools: list[ResourcePool],
    *,
    allowed_types: set[str] | None = None,
) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    seen: set[str] = set()
    for pool in pools:
        if allowed_types is not None and pool.type not in allowed_types:
            messages.append(ValidationMessage(level="warning", subject_id=pool.type, message="AI 输出的资源类型不在当前项目资源池中，已忽略。"))
            continue
        if pool.type in seen:
            messages.append(ValidationMessage(level="warning", subject_id=pool.type, message="资源类型重复，求解前将按资源池 ID 保留。"))
        seen.add(pool.type)
        if pool.resource_mode == "LIMITED" and (pool.quantity or 0) < 1:
            messages.append(ValidationMessage(level="warning", subject_id=pool.id, message=f"{pool.label} 数量为 0，相关任务可能无法分配受限资源。"))
        if pool.max_quantity is not None and (pool.quantity or 0) > pool.max_quantity:
            messages.append(ValidationMessage(level="error", subject_id=pool.id, message=f"{pool.label} 数量超过 max_quantity。"))
    return messages


def _plan_validation_status(plans: list[ResourceAssistantPlan]) -> str:
    levels = [message.level for plan in plans for message in plan.validation_messages]
    if "error" in levels:
        return "invalid"
    if "warning" in levels:
        return "partially_valid"
    return "valid"


def _solve_single_plan(
    scenario: ScenarioInput,
    plan: ResourceAssistantPlan,
    profile: ResourceAssistantProjectProfile | None,
) -> tuple[ResourceAssistantPlan, ResourceAssistantPlanResult, list[ValidationMessage]]:
    diagnostics: list[ValidationMessage] = []
    try:
        plan_scenario = scenario.model_copy(
            deep=True,
            update={
                "scenario_id": plan.scenario_id,
                "scenario_name": plan.scenario_name,
                "resource_pools": plan.resource_pools,
                "time_limit_seconds": AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS,
            },
        )
        solved = solve_ai_strict_fixed_resource_scenario(plan_scenario)
        active_profile = profile or build_project_profile(scenario, solved.generated)
        metrics = summarize_core_metrics(solved.generated, solved.result, active_profile)
        target = solved.result.stats.get("target_achievement")
        plan_status = str(target.get("target_status")) if isinstance(target, dict) else None
        if plan_status not in {"met", "not_met", "unconfirmed", "infeasible"}:
            plan_status = None
        if plan_status is not None:
            metrics = metrics.model_copy(update={"target_status": plan_status})
        schedule_outcome_status = str(target.get("schedule_outcome_status")) if isinstance(target, dict) and target.get("schedule_outcome_status") else None
        if schedule_outcome_status not in {"duration_target_met", "duration_target_not_met", "no_feasible_schedule"}:
            schedule_outcome_status = None
        schedule_outcome_reason = str(target.get("schedule_outcome_reason")) if isinstance(target, dict) and target.get("schedule_outcome_reason") else None
        if schedule_outcome_reason not in {
            "target_met",
            "proven_late",
            "late_unconfirmed",
            "time_limit_no_schedule",
            "proven_infeasible",
            "resource_coverage_missing",
            "target_missing",
        }:
            schedule_outcome_reason = None
        status = _plan_status_from_result(solved.result)
        solved_plan = plan.model_copy(update={"solve_status": status, "stale_reason": None})
        plan_result = ResourceAssistantPlanResult(
            scenario_id=plan.scenario_id,
            plan_status=plan_status,
            schedule_outcome_status=schedule_outcome_status,
            schedule_outcome_reason=schedule_outcome_reason,
            solver_status=solved.result.status,
            input_resource_quantities={pool.type: max(0, int(pool.quantity or 0)) for pool in plan.resource_pools},
            resource_expansion_attempted=False,
            generated=solved.generated,
            result=solved.result,
            metrics=metrics,
            diagnostics=solved.diagnostics,
            generated_at=datetime.now(timezone.utc),
            input_fingerprint=_plan_input_fingerprint(scenario, plan),
        )
        return solved_plan, plan_result, diagnostics
    except Exception as exc:  # pragma: no cover - defensive API isolation.
        diagnostics.append(
            ValidationMessage(level="error", subject_id=plan.scenario_id, message=f"{plan.scenario_name} 求解失败：{exc}")
        )
        failed_plan = plan.model_copy(update={"solve_status": "failed"})
        failed_result = ResourceAssistantPlanResult(
            scenario_id=plan.scenario_id,
            plan_status=None,
            schedule_outcome_status=None,
            schedule_outcome_reason=None,
            solver_status=None,
            input_resource_quantities={pool.type: max(0, int(pool.quantity or 0)) for pool in plan.resource_pools},
            resource_expansion_attempted=False,
            generated=None,
            result=None,
            metrics=ResourceAssistantCoreMetrics(target_status="failed", not_available_reasons=[str(exc)]),
            diagnostics=diagnostics,
            generated_at=datetime.now(timezone.utc),
            input_fingerprint=_plan_input_fingerprint(scenario, plan),
        )
        return failed_plan, failed_result, diagnostics


def _plan_status_from_result(result: ScheduleResult) -> str:
    return {
        "OPTIMAL": "optimal",
        "FEASIBLE": "feasible",
        "INFEASIBLE": "infeasible",
        "UNKNOWN": "unknown",
        "MODEL_INVALID": "model_invalid",
    }.get(result.status, "failed")


def _selected_plan_ids(request: ResourceAssistantBatchSolveRequest) -> set[str] | None:
    if request.solve_scope in {"", "all", "all_plans"}:
        return None
    return {request.solve_scope}


def _ordered_plans(plans: list[ResourceAssistantPlan]) -> list[ResourceAssistantPlan]:
    return sorted(plans, key=lambda plan: (PROFILE_ORDER.get(plan.profile, 99), plan.scenario_id))


def _continuous_beam_groups_for_project(scenario: ScenarioInput) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            grouped: dict[int, list[Any]] = defaultdict(list)
            for upper in section.upper_structures:
                if _is_continuous_beam_upper(upper):
                    grouped[_continuous_group_index(upper)].append(upper)
            for group_index, uppers in sorted(grouped.items(), key=lambda item: item[0]):
                span_indices = sorted({int(upper.span_index) for upper in uppers})
                main_supports = _continuous_main_support_indices(uppers, span_indices)
                support_refs = [f"{support}#墩" for support in main_supports]
                groups.append(
                    {
                        "group_id": f"{bridge.id}:{section.id}:continuous:{group_index}",
                        "group_index": group_index,
                        "display_name": f"{bridge.name}-{section.name}-连续梁组{group_index}",
                        "bridge_id": bridge.id,
                        "bridge_name": bridge.name,
                        "work_section_id": section.id,
                        "work_section_name": section.name,
                        "side": section.side,
                        "span_indices": span_indices,
                        "support_range": "、".join(upper.support_range for upper in uppers if upper.support_range),
                        "main_support_indices": main_supports,
                        "main_support_refs": support_refs,
                        "upper_structure_ids": [upper.id for upper in uppers],
                    }
                )
    return groups


def _is_continuous_beam_upper(upper: Any) -> bool:
    if upper.properties.get("structure_code") == "castInPlaceContinuousBoxGirder":
        return True
    return "连续" in upper.structure_type or "刚构" in upper.structure_type


def _continuous_group_index(upper: Any) -> int:
    try:
        return int(upper.properties.get("group_index"))
    except (TypeError, ValueError):
        return int(upper.span_index)


def _continuous_main_support_indices(uppers: list[Any], span_indices: list[int]) -> list[int]:
    configured = _continuous_list_setting(uppers, ["main_support_indices", "main_pier_indices"])
    if configured:
        return sorted(set(configured))
    if len(span_indices) < 2:
        return []
    return list(range(min(span_indices), max(span_indices)))


def _continuous_list_setting(uppers: list[Any], keys: list[str]) -> list[int]:
    result: list[int] = []
    for upper in uppers:
        nested = upper.properties.get("continuous_beam")
        for key in keys:
            value = nested.get(key) if isinstance(nested, dict) else upper.properties.get(key)
            if isinstance(value, list):
                for item in value:
                    try:
                        result.append(int(item))
                    except (TypeError, ValueError):
                        continue
    return result


def _control_piers_for_project(
    scenario: ScenarioInput,
    tasks: list[Task],
    continuous_groups: list[dict[str, Any]],
) -> list[ResourceAssistantControlPierSummary]:
    control_task_structure_ids = {
        task.structure_id
        for task in tasks
        if task.structure_type == "pier" and task.control_level in {"control", "key"}
    }
    continuous_main_supports: dict[str, set[str]] = defaultdict(set)
    for group in continuous_groups:
        for support_index in group.get("main_support_indices", []):
            continuous_main_supports[str(support_index)].add(group["group_id"])

    summaries: dict[str, ResourceAssistantControlPierSummary] = {}
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            for structure in section.structures:
                if structure.structure_type != "pier":
                    continue
                sources: list[str] = []
                if structure.control_level in {"control", "key"}:
                    sources.append("structure.control_level")
                if structure.id in control_task_structure_ids:
                    sources.append("task.control_level")
                support_index = structure.support_index
                if support_index is None:
                    support_index = _support_index_from_text(structure.support_no or structure.name)
                related_groups = sorted(continuous_main_supports.get(str(support_index), set())) if support_index is not None else []
                if related_groups:
                    sources.append("continuous_beam_main_pier")
                if not sources:
                    continue
                summaries[structure.id] = ResourceAssistantControlPierSummary(
                    structure_id=structure.id,
                    structure_name=structure.name,
                    bridge_id=bridge.id,
                    bridge_name=bridge.name,
                    work_section_id=section.id,
                    work_section_name=section.name,
                    side=section.side if section.side in {"left", "right", "none"} else "none",
                    support_no=structure.support_no or (f"{support_index}#墩" if support_index is not None else None),
                    recognition_sources=sorted(set(sources)),
                    related_continuous_beam_group_ids=related_groups,
                )
    return sorted(summaries.values(), key=lambda item: (item.bridge_id or "", item.work_section_id or "", item.structure_name))


def _support_index_from_text(value: str | None) -> int | None:
    if not value:
        return None
    digits = "".join(ch if ch.isdigit() else " " for ch in value).split()
    if not digits:
        return None
    try:
        return int(digits[0])
    except ValueError:
        return None


def _resource_type_profile(resource_pools: list[ResourcePool], tasks: list[Task]) -> list[dict[str, Any]]:
    demand: dict[str, dict[str, Any]] = defaultdict(lambda: {"task_count": 0, "duration_days": 0, "component_types": set()})
    for task in tasks:
        for resource_type in task.compatible_resource_types:
            demand[resource_type]["task_count"] += 1
            demand[resource_type]["duration_days"] += task.duration_days
            demand[resource_type]["component_types"].add(task.component_type)
    result: list[dict[str, Any]] = []
    for pool in sorted(resource_pools, key=lambda item: item.label):
        item = demand.get(pool.type, {"task_count": 0, "duration_days": 0, "component_types": set()})
        result.append(
            {
                "resource_type": pool.type,
                "label": pool.label,
                "quantity": pool.quantity,
                "max_quantity": pool.max_quantity,
                "resource_mode": pool.resource_mode,
                "enabled": pool.enabled,
                "task_count": item["task_count"],
                "duration_days": item["duration_days"],
                "component_types": sorted(item["component_types"]),
                "is_pile_resource": pool.type in PILE_RESOURCE_TYPES,
            }
        )
    return result


def _critical_path_candidates(
    tasks: list[Task],
    control_piers: list[ResourceAssistantControlPierSummary],
    continuous_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    control_ids = {pier.structure_id for pier in control_piers}
    for structure_id in sorted(control_ids):
        structure_tasks = [task for task in tasks if task.structure_id == structure_id]
        if not structure_tasks:
            continue
        candidates.append(
            {
                "candidate_id": f"control-pier:{structure_id}",
                "candidate_name": f"{structure_tasks[0].structure_name}下部结构控制链",
                "task_count": len(structure_tasks),
                "duration_days": sum(task.duration_days for task in structure_tasks),
                "reason": "控制墩或连续梁主墩相关下部结构。",
                "task_ids": [task.id for task in sorted(structure_tasks, key=lambda item: item.sequence_order)],
            }
        )
    for group in continuous_groups:
        group_tasks = [
            task for task in tasks if task.component_type == CONTINUOUS_BEAM_COMPONENT_TYPE and group["group_id"].split(":")[-1] in task.structure_id
        ]
        candidates.append(
            {
                "candidate_id": group["group_id"],
                "candidate_name": group["display_name"],
                "task_count": len(group_tasks),
                "duration_days": sum(task.duration_days for task in group_tasks),
                "reason": "连续梁 T 构、合龙段和边跨连续段形成关键线路候选。",
                "task_ids": [task.id for task in sorted(group_tasks, key=lambda item: item.sequence_order)[:30]],
            }
        )
    return candidates[:20]


def _constraint_hints(
    scenario: ScenarioInput,
    control_piers: list[ResourceAssistantControlPierSummary],
    continuous_groups: list[dict[str, Any]],
) -> list[str]:
    hard_milestones = [milestone for milestone in scenario.milestones if milestone.mode == "hard"]
    hints = [
        "资源配置方案只给资源数量和施工组织策略，不生成最终施工计划。",
        "CP-SAT 负责可行性校验、资源互斥、前置逻辑、工期和排程结果。",
        "桩机必须按工艺资源类型分别配置，不能把所有桩机合并成一个总数。",
    ]
    if control_piers:
        hints.append(f"已识别 {len(control_piers)} 个控制墩或连续梁主墩，资源策略需优先说明控制墩释放。")
    if continuous_groups:
        hints.append(f"已识别 {len(continuous_groups)} 组连续梁，需关注连续梁班组展开节奏。")
    if hard_milestones:
        hints.append(f"存在 {len(hard_milestones)} 个强制里程碑，推荐解释需引用求解后的节点满足状态。")
    return hints


def _control_pier_release_metrics(
    result: ScheduleResult,
    profile: ResourceAssistantProjectProfile,
) -> tuple[list[dict[str, Any]], int | None]:
    tasks_by_structure: dict[str, list[ScheduledTask]] = defaultdict(list)
    for task in result.tasks:
        if task.component_type in LOWER_STRUCTURE_COMPONENT_TYPES:
            tasks_by_structure[task.structure_id].append(task)
    continuous_tasks = [task for task in result.tasks if task.component_type == CONTINUOUS_BEAM_COMPONENT_TYPE or task.structure_type == "continuous_beam"]
    releases: list[dict[str, Any]] = []
    wait_days: list[int] = []
    for pier in profile.control_piers:
        tasks = tasks_by_structure.get(pier.structure_id, [])
        if not tasks:
            continue
        release_task = max(tasks, key=lambda task: (task.end_offset, task.id))
        related_continuous_tasks = _related_continuous_tasks(pier, continuous_tasks, result)
        related_start = min((task.start_offset for task in related_continuous_tasks), default=None)
        wait = max(0, related_start - release_task.end_offset) if related_start is not None else None
        if wait is not None:
            wait_days.append(wait)
        task_chain = [
            {
                "task_id": task.id,
                "task_name": task.name,
                "component_type": task.component_type,
                "start_date": task.start_date,
                "finish_date": task.finish_date,
                "role": "lower_structure",
            }
            for task in sorted(tasks, key=lambda item: (item.start_offset, item.end_offset, item.id))
        ]
        task_chain.extend(
            {
                "task_id": task.id,
                "task_name": task.name,
                "component_type": task.component_type,
                "start_date": task.start_date,
                "finish_date": task.finish_date,
                "role": "continuous_beam",
            }
            for task in sorted(related_continuous_tasks, key=lambda item: (item.start_offset, item.end_offset, item.id))[:12]
        )
        releases.append(
            {
                "structure_id": pier.structure_id,
                "structure_name": pier.structure_name,
                "release_date": release_task.finish_date,
                "release_offset": release_task.end_offset,
                "release_task_id": release_task.id,
                "release_task_name": release_task.name,
                "continuous_beam_start_offset": related_start,
                "wait_days": wait,
                "wait_window": {
                    "from_date": release_task.finish_date,
                    "to_offset": related_start,
                    "wait_days": wait,
                    "empty_reason": None if related_start is not None else "未匹配到该控制墩关联连续梁任务。",
                },
                "task_chain": task_chain,
                "recognition_sources": pier.recognition_sources,
            }
        )
    return sorted(releases, key=lambda item: (item["release_offset"], item["structure_name"])), max(wait_days) if wait_days else None


def _related_continuous_tasks(
    pier: ResourceAssistantControlPierSummary,
    continuous_tasks: list[ScheduledTask],
    result: ScheduleResult,
) -> list[ScheduledTask]:
    if not continuous_tasks:
        return []
    related_ids = set(pier.related_continuous_beam_group_ids)
    if related_ids:
        matching = [
            task
            for task in continuous_tasks
            if any(group_id.split(":")[-1].replace("continuous:", "") in (task.continuous_span_group_id or task.structure_id) for group_id in related_ids)
        ]
        if matching:
            return matching
    lower_task_ids = {task.id for task in result.tasks if task.structure_id == pier.structure_id}
    successor_ids: set[str] = set()
    for task in continuous_tasks:
        if lower_task_ids.intersection(task.predecessor_ids):
            successor_ids.add(task.id)
    if successor_ids:
        return [task for task in continuous_tasks if task.id in successor_ids]
    return continuous_tasks


def _continuous_beam_start_dates(result: ScheduleResult) -> tuple[Any, Any]:
    continuous_tasks = [task for task in result.tasks if task.component_type == CONTINUOUS_BEAM_COMPONENT_TYPE or task.structure_type == "continuous_beam"]
    if not continuous_tasks:
        return None, None
    first_start = min(task.start_date for task in continuous_tasks)
    by_group: dict[str, list[ScheduledTask]] = defaultdict(list)
    for task in continuous_tasks:
        by_group[task.continuous_span_group_id or task.structure_id].append(task)
    all_started = max(min(task.start_date for task in tasks) for tasks in by_group.values())
    return first_start, all_started


def _resource_utilization_metrics(
    generated: GeneratedScheduleInput | None,
    result: ScheduleResult,
) -> tuple[list[dict[str, Any]], list[int]]:
    resources_by_type: dict[str, set[str]] = defaultdict(set)
    if generated is not None:
        for resource in generated.schedule_input.resources:
            if resource.enabled:
                resources_by_type[resource.type].add(resource.id)
    work_days: dict[str, int] = defaultdict(int)
    idle_waits: list[int] = []
    allocations_by_resource: dict[str, list[Any]] = defaultdict(list)
    for allocation in result.resource_allocations:
        work_days[allocation.resource_type] += max(0, allocation.end_offset - allocation.start_offset)
        resources_by_type[allocation.resource_type].add(allocation.resource_id)
        allocations_by_resource[allocation.resource_id].append(allocation)
    for allocations in allocations_by_resource.values():
        ordered = sorted(allocations, key=lambda item: (item.start_offset, item.end_offset))
        for previous, current in zip(ordered, ordered[1:]):
            gap = max(0, current.start_offset - previous.end_offset)
            if gap:
                idle_waits.append(gap)
    horizon = max(1, result.objective_days or 1)
    utilization: list[dict[str, Any]] = []
    for resource_type in sorted(resources_by_type):
        resource_count = max(1, len(resources_by_type[resource_type]))
        capacity_days = resource_count * horizon
        work = work_days.get(resource_type, 0)
        utilization.append(
            {
                "resource_type": resource_type,
                "resource_count": resource_count,
                "work_days": work,
                "capacity_days": capacity_days,
                "idle_days": max(0, capacity_days - work),
                "utilization_rate": round(work / capacity_days, 3) if capacity_days else 0,
            }
        )
    return utilization, idle_waits


def _predecessor_waits(
    generated: GeneratedScheduleInput | None,
    result: ScheduleResult,
) -> tuple[list[int], list[int]]:
    if generated is None:
        return [], []
    tasks_by_id = {task.id: task for task in result.tasks}
    base_tasks_by_id = {task.id: task for task in generated.schedule_input.tasks}
    waits: list[int] = []
    continuous_waits: list[int] = []
    for task in result.tasks:
        ready_offsets = []
        for link in generated.schedule_input.precedence_links:
            if link.successor_id != task.id:
                continue
            predecessor = tasks_by_id.get(link.predecessor_id)
            base_successor = base_tasks_by_id.get(task.id)
            if predecessor is None or base_successor is None:
                continue
            ready_offsets.append(_ready_offset(predecessor, base_successor, link))
        if not ready_offsets:
            continue
        wait = max(0, task.start_offset - max(ready_offsets))
        if wait:
            waits.append(wait)
            if task.component_type == CONTINUOUS_BEAM_COMPONENT_TYPE or task.structure_type == "continuous_beam":
                continuous_waits.append(wait)
    return waits, continuous_waits


def _ready_offset(predecessor: ScheduledTask, successor: Task, link: PrecedenceLink) -> int:
    if link.relationship == "SS":
        return predecessor.start_offset + link.lag_days
    if link.relationship == "FF":
        return predecessor.end_offset + link.lag_days - successor.duration_days
    if link.relationship == "SF":
        return predecessor.start_offset + link.lag_days - successor.duration_days
    return predecessor.end_offset + link.lag_days


def _transfer_penalty(result: ScheduleResult) -> ResourceAssistantTransferPenalty:
    continuity = result.stats.get("continuity_metrics")
    if not isinstance(continuity, dict):
        return ResourceAssistantTransferPenalty()
    jump_pier_count = int(continuity.get("jump_pier_count") or 0)
    side_switch_count = int(continuity.get("side_switch_count") or 0)
    cross_side_jump_count = int(continuity.get("cross_side_jump_count") or 0)
    path_group_switch_count = int(continuity.get("path_group_switch_count") or 0)
    penalty_score = (
        jump_pier_count * 4
        + side_switch_count * 2
        + cross_side_jump_count * 6
        + path_group_switch_count
    )
    return ResourceAssistantTransferPenalty(
        penalty_score=penalty_score,
        jump_pier_count=jump_pier_count,
        side_switch_count=side_switch_count,
        cross_side_jump_count=cross_side_jump_count,
        path_group_switch_count=path_group_switch_count,
        max_jump_distance=int(continuity.get("max_jump_distance") or 0),
        details=list(continuity.get("jump_transition_details") or [])[:10],
    )


def _demo_cost(
    generated: GeneratedScheduleInput | None,
    result: ScheduleResult,
    transfer_penalty: ResourceAssistantTransferPenalty,
) -> ResourceAssistantDemoCost:
    if generated is None:
        return ResourceAssistantDemoCost()
    horizon = max(1, result.objective_days or 1)
    by_type: dict[str, dict[str, Any]] = defaultdict(lambda: {"resource_count": 0, "unit_cost": 0.0, "work_days": 0})
    for resource in generated.schedule_input.resources:
        if not resource.enabled:
            continue
        item = by_type[resource.type]
        item["resource_count"] += 1
        item["unit_cost"] = DEMO_RESOURCE_UNIT_COSTS.get(resource.type, 2000)
    for allocation in result.resource_allocations:
        item = by_type[allocation.resource_type]
        item["work_days"] += max(0, allocation.end_offset - allocation.start_offset)
        item["unit_cost"] = DEMO_RESOURCE_UNIT_COSTS.get(allocation.resource_type, 2000)

    resource_costs: list[dict[str, Any]] = []
    work_cost = 0.0
    idle_cost = 0.0
    mobilization_cost = 0.0
    for resource_type, item in sorted(by_type.items()):
        resource_count = int(item["resource_count"] or 0)
        unit_cost = float(item["unit_cost"] or DEMO_RESOURCE_UNIT_COSTS.get(resource_type, 2000))
        capacity_days = resource_count * horizon
        idle_days = max(0, capacity_days - int(item["work_days"] or 0))
        type_work_cost = int(item["work_days"] or 0) * unit_cost
        type_idle_cost = idle_days * unit_cost * 0.15
        type_mobilization = resource_count * DEMO_MOBILIZATION_COSTS.get(resource_type, 5000)
        work_cost += type_work_cost
        idle_cost += type_idle_cost
        mobilization_cost += type_mobilization
        resource_costs.append(
            {
                "resource_type": resource_type,
                "resource_count": resource_count,
                "unit_cost_per_day": unit_cost,
                "work_days": int(item["work_days"] or 0),
                "idle_days": idle_days,
                "work_cost": round(type_work_cost, 2),
                "idle_cost": round(type_idle_cost, 2),
                "mobilization_cost": round(type_mobilization, 2),
            }
        )
    transfer_cost = transfer_penalty.penalty_score * 1200
    return ResourceAssistantDemoCost(
        total_cost=round(work_cost + idle_cost + mobilization_cost + transfer_cost, 2),
        work_cost=round(work_cost, 2),
        idle_cost=round(idle_cost, 2),
        mobilization_cost=round(mobilization_cost, 2),
        transfer_cost=round(transfer_cost, 2),
        resource_costs=resource_costs,
    )


def _metric_row(
    metric_id: str,
    metric_name: str,
    unit: str,
    source_type: str,
    description: str,
    result_by_id: dict[str, ResourceAssistantPlanResult],
    getter: Any,
) -> ResourceAssistantMetricRow:
    values: dict[str, Any] = {}
    for scenario_id, plan_result in result_by_id.items():
        value = getter(plan_result.metrics)
        values[scenario_id] = {
            "value": value,
            "not_available_reasons": plan_result.metrics.not_available_reasons,
        }
    return ResourceAssistantMetricRow(
        metric_id=metric_id,
        metric_name=metric_name,
        unit=unit,
        values=values,
        source_type=source_type,  # type: ignore[arg-type]
        description=description,
    )


def _target_met(metrics: ResourceAssistantCoreMetrics) -> bool:
    return metrics.target_status in {"met", "candidate_resources_target_met"}


def _plan_result_target_met(plan_result: ResourceAssistantPlanResult) -> bool:
    schedule_outcome_status = _schedule_outcome_status(plan_result)
    if schedule_outcome_status is not None:
        return schedule_outcome_status == "duration_target_met"
    return _target_met(plan_result.metrics)


def _schedule_outcome_status(plan_result: ResourceAssistantPlanResult) -> str | None:
    if plan_result.schedule_outcome_status is not None:
        return plan_result.schedule_outcome_status
    if plan_result.plan_status == "met":
        return "duration_target_met"
    if plan_result.plan_status == "not_met":
        return "duration_target_not_met"
    if plan_result.plan_status == "infeasible":
        return "no_feasible_schedule"
    if plan_result.plan_status == "unconfirmed":
        target = plan_result.result.stats.get("target_achievement") if plan_result.result is not None else None
        if isinstance(target, dict) and target.get("target_present") is False:
            return None
        if plan_result.result is not None and plan_result.result.tasks:
            return "duration_target_not_met"
        return "no_feasible_schedule"
    if _target_met(plan_result.metrics):
        return "duration_target_met"
    return None


def _schedule_outcome_reason(plan_result: ResourceAssistantPlanResult) -> str | None:
    if plan_result.schedule_outcome_reason is not None:
        return plan_result.schedule_outcome_reason
    target = plan_result.result.stats.get("target_achievement") if plan_result.result is not None else None
    if isinstance(target, dict) and target.get("schedule_outcome_reason"):
        return str(target["schedule_outcome_reason"])
    if plan_result.plan_status == "met":
        return "target_met"
    if plan_result.plan_status == "not_met":
        return "proven_late"
    if plan_result.plan_status == "infeasible":
        return "proven_infeasible"
    if plan_result.plan_status == "unconfirmed":
        if isinstance(target, dict) and target.get("target_present") is False:
            return "target_missing"
        if plan_result.result is not None and plan_result.result.tasks:
            return "late_unconfirmed"
        return "time_limit_no_schedule"
    return None


def _recommendation_score(metrics: ResourceAssistantCoreMetrics) -> float:
    duration = float(metrics.total_days or 999_999)
    cost = metrics.demo_cost.total_cost / 100_000
    wait = float(metrics.average_wait_days or 0) * 2
    target_penalty = 0 if _target_met(metrics) else 10_000
    return duration + cost + wait + target_penalty


def _recommendation_evidence(
    plan: ResourceAssistantPlan,
    metrics: ResourceAssistantCoreMetrics,
    plan_result: ResourceAssistantPlanResult,
) -> list[str]:
    outcome_label = {
        "duration_target_met": "工期目标已满足",
        "duration_target_not_met": "工期目标未满足",
        "no_feasible_schedule": "当前资源未获得可行排程",
    }.get(_schedule_outcome_status(plan_result), "缺少工期目标，无法评估")
    return [
        f"{plan.scenario_name} 总工期 {metrics.total_days if metrics.total_days is not None else '不可用'} 天。",
        f"方案目标状态为 {outcome_label}。",
        f"平均等待 {metrics.average_wait_days if metrics.average_wait_days is not None else '不可用'} 天，最大等待 {metrics.max_wait_days if metrics.max_wait_days is not None else '不可用'} 天。",
        f"演示成本约 {round(metrics.demo_cost.total_cost, 0)} 元。",
    ]


def _recommendation_risks(plan: ResourceAssistantPlan, metrics: ResourceAssistantCoreMetrics) -> list[str]:
    risks = []
    if metrics.control_pier_wait_days and metrics.control_pier_wait_days > 7:
        risks.append(f"控制墩释放后最大等待 {metrics.control_pier_wait_days} 天，连续梁开工仍有排队风险。")
    if metrics.transfer_penalty.penalty_score > 0:
        risks.append(f"资源转场诊断分 {metrics.transfer_penalty.penalty_score}，需关注工作面连续性。")
    if metrics.average_wait_days and metrics.average_wait_days > 5:
        risks.append("平均等待偏高，可能存在资源错峰或前置释放后的空等。")
    if plan.profile == "crash":
        risks.append("抢工方案资源投入较高，真实成本和场地组织需进一步核算。")
    return risks or ["当前指标未暴露明显不可接受风险，仍需结合现场约束复核。"]


def _marginal_benefit_notes(
    recommended: ResourceAssistantPlan,
    result_by_id: dict[str, ResourceAssistantPlanResult],
    plans: list[ResourceAssistantPlan],
) -> list[str]:
    notes: list[str] = []
    recommended_metrics = result_by_id[recommended.scenario_id].metrics
    for plan in _ordered_plans(plans):
        if plan.scenario_id == recommended.scenario_id or plan.scenario_id not in result_by_id:
            continue
        metrics = result_by_id[plan.scenario_id].metrics
        if metrics.total_days is None or recommended_metrics.total_days is None:
            continue
        day_delta = metrics.total_days - recommended_metrics.total_days
        cost_delta = recommended_metrics.demo_cost.total_cost - metrics.demo_cost.total_cost
        if day_delta > 0:
            notes.append(f"相对 {plan.scenario_name}，推荐方案缩短约 {day_delta} 天，演示成本变化约 {round(cost_delta, 0)} 元。")
        elif day_delta < 0:
            notes.append(f"相对 {plan.scenario_name}，推荐方案工期多 {abs(day_delta)} 天，但投入或等待指标更可控。")
    return notes[:3] or ["三方案边际收益差异较小，建议按风险和资源可得性复核。"]


def _fallback_strategy(profile: str) -> str:
    return {
        "economy": "优先保障控制墩和连续梁主墩，普通墩按工区顺序推进，尽量减少模板和班组投入。",
        "balanced": "控制墩、普通墩和连续梁班组同步展开，通过增加墩柱模板降低下部结构等待。",
        "crash": "桩基、墩柱和盖梁资源同步加压，优先释放连续梁主墩并缩短关键工作面排队。",
    }[profile]


def _fallback_applicable_scenarios(profile: str) -> str:
    return {
        "economy": "适用于成本敏感、节点压力较低或资源采购受限的场景。",
        "balanced": "适用于需要稳妥压缩工期且资源投入可控的常规施工组织。",
        "crash": "适用于控制节点压力较大、需要快速释放连续梁工作面的抢工场景。",
    }[profile]


def _fallback_risks(profile: str) -> str:
    return {
        "economy": "控制墩释放和连续梁开工可能受模板周转与资源排队影响。",
        "balanced": "资源投入中等，仍需关注连续梁班组与控制墩释放节奏是否匹配。",
        "crash": "投入较高，需复核场地、运输、人员组织和真实成本。",
    }[profile]


def _scenario_fingerprint(scenario: ScenarioInput) -> str:
    return _stable_hash(scenario.model_dump(mode="json"))


def _plan_input_fingerprint(scenario: ScenarioInput, plan: ResourceAssistantPlan) -> str:
    return _stable_hash(
        {
            "scenario": scenario.model_dump(mode="json"),
            "resource_pools": [pool.model_dump(mode="json") for pool in plan.resource_pools],
        }
    )


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
