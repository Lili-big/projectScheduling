from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.services.ai_resource_scheduling_assistant as assistant_module  # noqa: E402
from app.models import (  # noqa: E402
    GeneratedScheduleInput,
    PrecedenceLink,
    Resource,
    ResourceAllocation,
    ResourceAssistantBatchSolveRequest,
    ResourceAssistantResultsRequest,
    ResourceAssistantSingleSolveRequest,
    ResourceAssistantControlPierSummary,
    ResourceAssistantCoreMetrics,
    ResourceAssistantInitialRequest,
    ResourceAssistantPlan,
    ResourceAssistantPlanResult,
    ResourceAssistantProjectProfile,
    ResourceAssistantUpdatePlanRequest,
    ScheduleInput,
    ScheduleResult,
    ScenarioSolveResult,
    ScheduledTask,
    Task,
)
from app.services.ai_resource_explainer import explain_recommendation, llm_config_status  # noqa: E402
from app.services.ai_resource_scheduling_assistant import (  # noqa: E402
    batch_solve_resource_plans,
    build_comparison,
    build_deterministic_recommendation,
    compare_resource_plan_results,
    generate_resource_plan_recommendation,
    initialize_resource_assistant,
    solve_resource_plan,
    summarize_core_metrics,
    update_resource_plan,
)
from app.services.process_library_service import default_scenario_with_process_library  # noqa: E402


def test_initialize_builds_project_profile_and_three_local_plans(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    scenario = default_scenario_with_process_library()

    response = initialize_resource_assistant(
        ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only")
    )

    assert response.plan_generation.source == "local_fallback"
    assert response.plan_generation.validation_status in {"valid", "partially_valid"}
    assert len(response.resource_plans) == 3
    assert {plan.profile for plan in response.resource_plans} == {"economy", "balanced", "crash"}
    assert response.project_profile.project_name == scenario.project.project_name
    assert response.project_profile.resource_types
    assert response.reference_examples
    assert all(example.is_hard_constraint is False for example in response.reference_examples)
    assert set(response.llm_generation_context) == {
        "project_profile",
        "resource_types",
        "constraint_hints",
        "reference_examples",
        "current_resource_pools",
        "rules",
    }


def test_initialize_returns_the_exact_context_passed_to_plan_generation(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    scenario = default_scenario_with_process_library()
    captured: dict[str, object] = {}

    def capture_context(context):
        captured.update(context)
        return None, llm_config_status()

    monkeypatch.setattr(assistant_module, "generate_resource_plan_payload", capture_context)

    response = initialize_resource_assistant(
        ResourceAssistantInitialRequest(scenario=scenario, generation_mode="llm_first")
    )

    assert response.llm_generation_context == captured
    assert response.llm_generation_context["project_profile"]["project_name"] == scenario.project.project_name
    assert response.llm_generation_context["resource_types"] == response.project_profile.resource_types
    assert response.llm_generation_context["constraint_hints"] == response.constraint_hints
    assert response.llm_generation_context["reference_examples"] == [
        example.model_dump(mode="json") for example in response.reference_examples
    ]
    assert response.llm_generation_context["current_resource_pools"] == [
        pool.model_dump(mode="json") for pool in scenario.resource_pools
    ]


def test_llm_generation_context_excludes_transport_and_secret_configuration(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_ENDPOINT", "https://secret.example.test/v1/chat/completions")
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_MODEL", "secret-model")
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_API_KEY", "secret-key")
    scenario = default_scenario_with_process_library()
    monkeypatch.setattr(
        assistant_module,
        "generate_resource_plan_payload",
        lambda _context: (None, llm_config_status("forced fallback")),
    )

    response = initialize_resource_assistant(
        ResourceAssistantInitialRequest(scenario=scenario, generation_mode="llm_first")
    )

    keys = _nested_mapping_keys(response.llm_generation_context)
    assert {"api_key", "authorization", "endpoint", "model", "output_schema", "system"}.isdisjoint(keys)
    serialized = str(response.llm_generation_context)
    assert "secret.example.test" not in serialized
    assert "secret-model" not in serialized
    assert "secret-key" not in serialized


def test_initial_plans_keep_pile_resources_split_by_process_type(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    scenario = default_scenario_with_process_library()

    response = initialize_resource_assistant(
        ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only")
    )
    economy = next(plan for plan in response.resource_plans if plan.profile == "economy")
    crash = next(plan for plan in response.resource_plans if plan.profile == "crash")
    economy_quantities = {pool.type: pool.quantity for pool in economy.resource_pools}
    crash_quantities = {pool.type: pool.quantity for pool in crash.resource_pools}

    assert economy_quantities["rotary_drill"] == 4
    assert economy_quantities["circulation_drill"] == 4
    assert economy_quantities["impact_drill"] == 4
    assert crash_quantities["rotary_drill"] == 6
    assert crash_quantities["impact_drill"] == 6


def test_update_resource_plan_marks_result_stale_and_normalizes_max_quantity(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    scenario = default_scenario_with_process_library()
    initial = initialize_resource_assistant(ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only"))
    plan = next(item for item in initial.resource_plans if item.profile == "balanced")

    response = update_resource_plan(
        ResourceAssistantUpdatePlanRequest(
            plan_id=plan.scenario_id,
            resource_plan=plan,
            resource_updates={"cast_in_place_continuous_beam_team": 12},
        )
    )

    pool = next(pool for pool in response.resource_plan.resource_pools if pool.type == "cast_in_place_continuous_beam_team")
    assert pool.quantity == 12
    assert pool.max_quantity >= 12
    assert response.resource_plan.solve_status == "stale"
    assert response.resource_plan.generation_source == "user_adjusted"
    assert response.invalidated_result_ids == [plan.scenario_id]


def test_summarize_core_metrics_covers_duration_control_wait_utilization_and_cost() -> None:
    generated, result, profile = _metric_fixture()

    metrics = summarize_core_metrics(generated, result, profile)

    assert metrics.total_days == 25
    assert metrics.plan_finish_date == date(2026, 1, 25)
    assert metrics.first_continuous_beam_start_date == date(2026, 1, 16)
    assert metrics.all_continuous_beams_started_date == date(2026, 1, 16)
    assert metrics.control_pier_release_dates[0]["structure_id"] == "P01"
    assert metrics.control_pier_wait_days == 5
    assert metrics.average_wait_days == 4.5
    assert metrics.max_wait_days == 5
    assert metrics.transfer_penalty.penalty_score > 0
    assert metrics.demo_cost.total_cost > 0
    assert metrics.demo_cost.price_source == "demo_default_price"


def test_control_pier_focus_metric_contains_lower_to_continuous_task_chain() -> None:
    generated, result, profile = _metric_fixture()

    metrics = summarize_core_metrics(generated, result, profile)
    release = metrics.control_pier_release_dates[0]
    task_ids = [item["task_id"] for item in release["task_chain"]]

    assert task_ids[:1] == ["P01-pier"]
    assert "CB-G01-zero" in task_ids
    assert release["wait_window"]["wait_days"] == 5


def test_control_pier_focus_empty_reasons_without_control_or_continuous_tasks() -> None:
    generated, result, profile = _metric_fixture()
    profile.control_piers = []
    result.tasks = [task for task in result.tasks if task.component_type != "cast_in_place_continuous_beam"]

    metrics = summarize_core_metrics(generated, result, profile)

    assert "未识别到控制墩释放时间。" in metrics.not_available_reasons
    assert "未生成连续梁任务，连续梁开工指标不可用。" in metrics.not_available_reasons


def test_comparison_marks_unavailable_metrics_for_infeasible_result() -> None:
    scenario = default_scenario_with_process_library()
    initial = initialize_resource_assistant(ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only"))
    plan = initial.resource_plans[0]
    plan_result = ResourceAssistantPlanResult(
        scenario_id=plan.scenario_id,
        generated=None,
        result=ScheduleResult(status="INFEASIBLE", plan_start_date=scenario.project.start_date),
        metrics=ResourceAssistantCoreMetrics(target_status="not_available", not_available_reasons=["不可行"]),
        diagnostics=[],
        generated_at=assistant_module.datetime.now(assistant_module.timezone.utc),
        input_fingerprint="x",
    )

    comparison = build_comparison([plan], [plan_result])

    total_days = next(row for row in comparison.metric_rows if row.metric_id == "total_days")
    assert total_days.values[plan.scenario_id]["not_available_reasons"] == ["不可行"]


def test_recommendation_prefers_balanced_when_crash_marginal_gain_is_low(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    plans, results = _recommendation_fixture(
        economy=(120, 900_000, "current_resources_target_failed"),
        balanced=(100, 1_000_000, "met"),
        crash=(98, 1_130_000, "met"),
    )

    recommendation = build_deterministic_recommendation(plans, results)

    assert recommendation.recommended_scenario_id == next(plan.scenario_id for plan in plans if plan.profile == "balanced")
    assert "边际收益不足" in recommendation.rule_reason


def test_recommendation_chooses_crash_when_only_crash_meets_target(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    plans, results = _recommendation_fixture(
        economy=(120, 900_000, "current_resources_target_failed"),
        balanced=(108, 1_000_000, "current_resources_target_failed"),
        crash=(96, 1_220_000, "met"),
    )

    recommendation = build_deterministic_recommendation(plans, results)

    assert recommendation.recommended_scenario_id == next(plan.scenario_id for plan in plans if plan.profile == "crash")


def test_recommendation_is_empty_without_comparable_results(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    scenario = default_scenario_with_process_library()
    initial = initialize_resource_assistant(ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only"))

    recommendation = build_deterministic_recommendation(initial.resource_plans, [])

    assert recommendation.recommendation_status == "insufficient_results"
    assert recommendation.recommended_scenario_id is None


def test_local_explanation_uses_rule_evidence_and_keeps_recommendation(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "local")
    plans, results = _recommendation_fixture(
        economy=(120, 900_000, "current_resources_target_failed"),
        balanced=(100, 1_000_000, "met"),
        crash=(98, 1_130_000, "met"),
    )
    recommendation = build_deterministic_recommendation(plans, results)
    comparison = build_comparison(plans, results)

    explained = explain_recommendation(recommendation, comparison)

    assert explained.recommended_scenario_id == recommendation.recommended_scenario_id
    assert explained.explanation_source == "local"
    assert len(explained.evidence) >= 3
    assert "CP-SAT" in explained.ai_explanation


def test_llm_generation_failure_falls_back_to_local_plans(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "openai_compatible")
    monkeypatch.delenv("AI_RESOURCE_ASSISTANT_ENDPOINT", raising=False)
    monkeypatch.delenv("PROCESS_NL_LLM_ENDPOINT", raising=False)
    scenario = default_scenario_with_process_library()

    response = initialize_resource_assistant(
        ResourceAssistantInitialRequest(scenario=scenario, generation_mode="llm_first")
    )

    assert response.plan_generation.source == "local_fallback"
    assert response.plan_generation.fallback_reason
    assert response.llm_config_status.status == "failed"
    assert len(response.resource_plans) == 3
    assert response.llm_generation_context["project_profile"]["project_name"] == scenario.project.project_name


def test_external_plan_generation_success_returns_the_context_used(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_ENDPOINT", "https://example.test/v1/chat/completions")
    scenario = default_scenario_with_process_library()
    captured: dict[str, object] = {}

    def fake_generation(context):
        captured.update(context)
        plans = []
        for example in context["reference_examples"]:
            plans.append(
                {
                    "profile": example["profile"],
                    "positioning": example["description"],
                    "resource_quantities": example["resource_quantities"],
                    "organization_strategy": "按项目画像组织资源。",
                    "generation_rationale": "测试外部 LLM 成功返回。",
                    "applicable_scenarios": "测试场景。",
                    "expected_risks": "测试风险。",
                }
            )
        return plans, llm_config_status()

    monkeypatch.setattr(assistant_module, "generate_resource_plan_payload", fake_generation)

    response = initialize_resource_assistant(
        ResourceAssistantInitialRequest(scenario=scenario, generation_mode="llm_first")
    )

    assert response.plan_generation.source == "llm"
    assert response.llm_generation_context == captured


def test_resource_assistant_reuses_process_nl_llm_config(monkeypatch) -> None:
    for key in (
        "AI_RESOURCE_ASSISTANT_PROVIDER",
        "AI_RESOURCE_ASSISTANT_ENDPOINT",
        "AI_RESOURCE_ASSISTANT_MODEL",
        "AI_RESOURCE_ASSISTANT_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PROCESS_NL_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("PROCESS_NL_LLM_ENDPOINT", "https://example.test/v1/chat/completions")
    monkeypatch.setenv("PROCESS_NL_LLM_MODEL", "shared-model")
    monkeypatch.setenv("PROCESS_NL_LLM_API_KEY", "test-key")

    status = llm_config_status()

    assert status.status == "configured"
    assert status.provider == "openai_compatible"
    assert status.endpoint_configured is True
    assert status.api_key_configured is True
    assert status.model == "shared-model"


def test_batch_solve_keeps_plan_results_independent(monkeypatch) -> None:
    scenario = default_scenario_with_process_library()
    initial = initialize_resource_assistant(ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only"))
    generated, result, _ = _metric_fixture()

    def fake_solve(plan_scenario):
        if plan_scenario.scenario_id.endswith("balanced"):
            raise RuntimeError("balanced failed")
        return ScenarioSolveResult(
            scenario_id=plan_scenario.scenario_id,
            scenario_name=plan_scenario.scenario_name,
            generated=generated,
            result=result,
            milestone_results=[],
            diagnostics=[],
            metrics={},
        )

    monkeypatch.setattr(assistant_module, "solve_scenario", fake_solve)

    response = batch_solve_resource_plans(
        ResourceAssistantBatchSolveRequest(scenario=scenario, resource_plans=initial.resource_plans)
    )

    statuses = {plan.profile: plan.solve_status for plan in response.resource_plans}
    assert statuses["economy"] in {"optimal", "feasible"}
    assert statuses["balanced"] == "failed"
    assert statuses["crash"] in {"optimal", "feasible"}
    assert len(response.plan_results) == 3


def test_single_plan_solve_only_runs_selected_plan_and_never_explains(monkeypatch) -> None:
    scenario = default_scenario_with_process_library()
    initial = initialize_resource_assistant(ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only"))
    generated, result, _ = _metric_fixture()
    calls: list[str] = []

    def fake_solve(plan_scenario):
        calls.append(plan_scenario.scenario_id)
        return ScenarioSolveResult(
            scenario_id=plan_scenario.scenario_id,
            scenario_name=plan_scenario.scenario_name,
            generated=generated,
            result=result,
            milestone_results=[],
            diagnostics=[],
            metrics={},
        )

    monkeypatch.setattr(assistant_module, "solve_scenario", fake_solve)
    monkeypatch.setattr(assistant_module, "explain_recommendation", lambda *_: (_ for _ in ()).throw(AssertionError("不应调用解释")))

    response = solve_resource_plan(
        ResourceAssistantSingleSolveRequest(scenario=scenario, resource_plan=initial.resource_plans[0])
    )

    assert calls == [initial.resource_plans[0].scenario_id]
    assert response.resource_plan.scenario_id == initial.resource_plans[0].scenario_id
    assert response.plan_result.scenario_id == initial.resource_plans[0].scenario_id


def test_partial_comparison_does_not_run_solver_or_llm(monkeypatch) -> None:
    plans, results = _recommendation_fixture(
        economy=(120, 900_000, "current_resources_target_failed"),
        balanced=(100, 1_000_000, "met"),
        crash=(98, 1_130_000, "met"),
    )
    monkeypatch.setattr(assistant_module, "solve_scenario", lambda *_: (_ for _ in ()).throw(AssertionError("不应求解")))
    monkeypatch.setattr(assistant_module, "explain_recommendation", lambda *_: (_ for _ in ()).throw(AssertionError("不应解释")))

    comparison = compare_resource_plan_results(
        ResourceAssistantResultsRequest(resource_plans=plans, plan_results=[results[0]])
    )

    total_days = next(row for row in comparison.metric_rows if row.metric_id == "total_days")
    assert results[0].scenario_id in total_days.values
    assert results[1].scenario_id not in total_days.values


def test_recommendation_requires_all_three_results_and_falls_back_locally(monkeypatch) -> None:
    plans, results = _recommendation_fixture(
        economy=(120, 900_000, "current_resources_target_failed"),
        balanced=(100, 1_000_000, "met"),
        crash=(98, 1_130_000, "met"),
    )
    with pytest.raises(ValueError, match="请先完成"):
        generate_resource_plan_recommendation(ResourceAssistantResultsRequest(resource_plans=plans, plan_results=results[:2]))

    monkeypatch.setattr(assistant_module, "explain_recommendation", lambda recommendation, _comparison: recommendation.model_copy(update={"ai_explanation": "本地解释", "explanation_source": "local"}))
    response = generate_resource_plan_recommendation(ResourceAssistantResultsRequest(resource_plans=plans, plan_results=results))

    assert response.recommendation.recommended_scenario_id == next(plan.scenario_id for plan in plans if plan.profile == "balanced")
    assert response.recommendation.ai_explanation == "本地解释"


def _recommendation_fixture(
    *,
    economy: tuple[int, int, str],
    balanced: tuple[int, int, str],
    crash: tuple[int, int, str],
) -> tuple[list[ResourceAssistantPlan], list[ResourceAssistantPlanResult]]:
    scenario = default_scenario_with_process_library()
    initial = initialize_resource_assistant(ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only"))
    values = {"economy": economy, "balanced": balanced, "crash": crash}
    results = []
    for plan in initial.resource_plans:
        days, cost, target_status = values[plan.profile]
        metrics = ResourceAssistantCoreMetrics(
            total_days=days,
            plan_finish_date=scenario.project.start_date + timedelta(days=days - 1),
            average_wait_days=2,
            max_wait_days=4,
            target_status=target_status,
        )
        metrics.demo_cost.total_cost = cost
        results.append(
            ResourceAssistantPlanResult(
                scenario_id=plan.scenario_id,
                generated=None,
                result=ScheduleResult(
                    status="FEASIBLE",
                    objective_days=days,
                    plan_start_date=scenario.project.start_date,
                    plan_finish_date=scenario.project.start_date + timedelta(days=days - 1),
                ),
                metrics=metrics,
                diagnostics=[],
                generated_at=assistant_module.datetime.now(assistant_module.timezone.utc),
                input_fingerprint=plan.scenario_id,
            )
        )
    return initial.resource_plans, results


def _metric_fixture() -> tuple[GeneratedScheduleInput, ScheduleResult, ResourceAssistantProjectProfile]:
    start = date(2026, 1, 1)
    lower_1 = _task("P01-pier", "1号墩-墩柱", "P01", "1号墩", "pier_body", 5)
    lower_2 = _task("P02-pier", "2号墩-墩柱", "P02", "2号墩", "pier_body", 4)
    continuous = _task(
        "CB-G01-zero",
        "连续梁1#墩T构-0号块",
        "CB-G01",
        "连续梁1#墩T构",
        "cast_in_place_continuous_beam",
        10,
        structure_type="continuous_beam",
    )
    generated = GeneratedScheduleInput(
        schedule_input=ScheduleInput(
            project_name="fixture",
            start_date=start,
            tasks=[lower_1, lower_2, continuous],
            precedence_links=[
                PrecedenceLink(
                    id="L1",
                    predecessor_id="P01-pier",
                    successor_id="CB-G01-zero",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="fixture",
                )
            ],
            resources=[
                Resource(id="pier_body_team_1", name="墩柱模板1", type="pier_body_team"),
                Resource(id="continuous_team_1", name="连续梁班组1", type="cast_in_place_continuous_beam_team"),
            ],
            milestones=[],
            time_limit_seconds=1,
        )
    )
    result = ScheduleResult(
        status="FEASIBLE",
        objective_days=25,
        plan_start_date=start,
        plan_finish_date=date(2026, 1, 25),
        tasks=[
            _scheduled(lower_1, start, 5, 10, "pier_body_team_1", "墩柱模板1", "pier_body_team"),
            _scheduled(lower_2, start, 14, 18, "pier_body_team_1", "墩柱模板1", "pier_body_team"),
            _scheduled(continuous, start, 15, 25, "continuous_team_1", "连续梁班组1", "cast_in_place_continuous_beam_team", ["P01-pier"]),
        ],
        resource_allocations=[
            _allocation("pier_body_team_1", "墩柱模板1", "pier_body_team", "P01-pier", "1号墩-墩柱", start, 5, 10),
            _allocation("pier_body_team_1", "墩柱模板1", "pier_body_team", "P02-pier", "2号墩-墩柱", start, 14, 18),
            _allocation("continuous_team_1", "连续梁班组1", "cast_in_place_continuous_beam_team", "CB-G01-zero", "连续梁1#墩T构-0号块", start, 15, 25),
        ],
        stats={
            "target_achievement": {"target_status": "met"},
            "continuity_metrics": {
                "jump_pier_count": 1,
                "side_switch_count": 1,
                "cross_side_jump_count": 0,
                "path_group_switch_count": 1,
                "max_jump_distance": 2,
                "jump_transition_details": [{"resource_name": "墩柱模板1"}],
            },
        },
    )
    profile = ResourceAssistantProjectProfile(
        project_name="fixture",
        start_date=start,
        control_piers=[
            ResourceAssistantControlPierSummary(
                structure_id="P01",
                structure_name="1号墩",
                side="none",
                recognition_sources=["structure.control_level"],
                related_continuous_beam_group_ids=["B1:WS:continuous:1"],
            )
        ],
    )
    return generated, result, profile


def _task(
    task_id: str,
    name: str,
    structure_id: str,
    structure_name: str,
    component_type: str,
    duration: int,
    *,
    structure_type: str = "pier",
) -> Task:
    return Task(
        id=task_id,
        name=name,
        structure_id=structure_id,
        structure_name=structure_name,
        structure_type=structure_type,
        component_type=component_type,
        process_name=name,
        productivity_rule_id=f"{component_type}:default",
        quantity=1,
        quantity_label="1",
        duration_days=duration,
        compatible_resource_types=["cast_in_place_continuous_beam_team" if component_type == "cast_in_place_continuous_beam" else "pier_body_team"],
    )


def _scheduled(
    task: Task,
    start: date,
    start_offset: int,
    end_offset: int,
    resource_id: str,
    resource_name: str,
    resource_type: str,
    predecessors: list[str] | None = None,
) -> ScheduledTask:
    return ScheduledTask(
        **task.model_dump(),
        start_offset=start_offset,
        end_offset=end_offset,
        start_date=start + timedelta(days=start_offset),
        finish_date=start + timedelta(days=end_offset - 1),
        assigned_resource_id=resource_id,
        assigned_resource_name=resource_name,
        assigned_resource_type=resource_type,
        predecessor_ids=predecessors or [],
    )


def _allocation(
    resource_id: str,
    resource_name: str,
    resource_type: str,
    task_id: str,
    task_name: str,
    start: date,
    start_offset: int,
    end_offset: int,
) -> ResourceAllocation:
    return ResourceAllocation(
        resource_id=resource_id,
        resource_name=resource_name,
        resource_type=resource_type,
        task_id=task_id,
        task_name=task_name,
        start_offset=start_offset,
        end_offset=end_offset,
        start_date=start + timedelta(days=start_offset),
        finish_date=start + timedelta(days=end_offset - 1),
    )


def _nested_mapping_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(_nested_mapping_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_nested_mapping_keys(nested))
    return keys
