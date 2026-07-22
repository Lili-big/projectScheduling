from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import app.services.ai_resource_scheduling_assistant as assistant_module  # noqa: E402
from app.contracts import (  # noqa: E402
    CreateBaselinePlanRequest,
    ResourceAssistantInitialRequest,
    ResourceAssistantResultsRequest,
    ResourceAssistantSingleSolveRequest,
    ResourceAssistantUpdatePlanRequest,
    ResourcePool,
)
from app.scenario import generate_schedule_input_from_scenario  # noqa: E402
from app.services.ai_resource_scheduling_assistant import (  # noqa: E402
    compare_resource_plan_results,
    initialize_resource_assistant,
    solve_resource_plan,
    update_resource_plan,
)
from app.services.process_library_service import default_scenario_with_process_library  # noqa: E402
from app.services.plan_control_repository import PlanControlRepository  # noqa: E402
from app.services.progress_forecast import PlanControlValidationError, create_baseline_plan  # noqa: E402


def _scenario_with_scoped_resources():
    scenario = default_scenario_with_process_library()
    bridge_a = scenario.project.bridges[0]
    bridge_b = bridge_a.model_copy(deep=True, update={"id": "B2", "name": "青洛河2号大桥", "work_sections": []})
    project = scenario.project.model_copy(deep=True, update={"bridges": [bridge_a, bridge_b]})
    generated = generate_schedule_input_from_scenario(scenario)
    resource_types = sorted(
        {
            resource_type
            for task in generated.schedule_input.tasks
            for resource_type in task.compatible_resource_types
        }
    )
    pools = [
        ResourcePool(
            id=f"local-b1-{resource_type}",
            type=resource_type,
            label=f"B1 {resource_type}",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id=bridge_a.id,
            quantity=2,
            max_quantity=5,
        )
        for resource_type in resource_types
    ]
    pools.extend(
        [
            ResourcePool(
                id="local-b2-rotary",
                type="rotary_drill",
                label="B2 旋挖钻",
                scope_mode="WORKPOINT_EXCLUSIVE",
                workpoint_id=bridge_b.id,
                quantity=7,
                max_quantity=9,
            ),
            ResourcePool(
                id="shared-rotary",
                type="rotary_drill",
                label="共享旋挖钻",
                scope_mode="PROJECT_SHARED",
                authorized_workpoint_ids=[bridge_a.id, bridge_b.id],
                quantity=3,
                max_quantity=6,
            ),
        ]
    )
    return scenario.model_copy(deep=True, update={"project": project, "resource_pools": pools}), bridge_a.id, bridge_b.id


def _initialize(scenario, target_workpoint_id: str):
    return initialize_resource_assistant(
        ResourceAssistantInitialRequest(
            scenario=scenario,
            target_workpoint_id=target_workpoint_id,
            generation_mode="local_fallback_only",
        )
    )


def test_initial_request_requires_explicit_workpoint_and_rejects_unknown_identity() -> None:
    scenario, workpoint_a, _ = _scenario_with_scoped_resources()
    with pytest.raises(ValidationError):
        ResourceAssistantInitialRequest.model_validate({"scenario": scenario.model_dump(mode="json")})
    with pytest.raises(ValueError, match="不属于当前项目版本"):
        _initialize(scenario, "missing-workpoint")
    assert _initialize(scenario, workpoint_a).resource_plans[0].target_workpoint_id == workpoint_a


def test_three_plans_only_change_selected_workpoint_local_quantities() -> None:
    scenario, workpoint_a, workpoint_b = _scenario_with_scoped_resources()
    response = _initialize(scenario, workpoint_a)
    base_by_id = {pool.id: pool.model_dump(mode="json") for pool in scenario.resource_pools}

    assert len(response.resource_plans) == 3
    for plan in response.resource_plans:
        assert plan.target_workpoint_id == workpoint_a
        assert plan.target_workpoint_name == "青洛河1号大桥"
        plan_by_id = {pool.id: pool for pool in plan.resource_pools}
        assert plan_by_id["local-b2-rotary"].model_dump(mode="json") == base_by_id["local-b2-rotary"]
        assert plan_by_id["shared-rotary"].model_dump(mode="json") == base_by_id["shared-rotary"]
        assert plan_by_id["local-b2-rotary"].workpoint_id == workpoint_b
    selected_values = [
        next(pool.quantity for pool in plan.resource_pools if pool.id == "local-b1-rotary_drill")
        for plan in response.resource_plans
    ]
    assert selected_values == sorted(selected_values)
    assert len(set(selected_values)) > 1


def test_update_and_solve_reject_shared_or_other_workpoint_changes() -> None:
    scenario, workpoint_a, workpoint_b = _scenario_with_scoped_resources()
    plan = _initialize(scenario, workpoint_a).resource_plans[1]

    with pytest.raises(ValueError, match="只能调整当前资源推进工点"):
        update_resource_plan(
            ResourceAssistantUpdatePlanRequest(
                plan_id=plan.scenario_id,
                resource_plan=plan,
                scoped_resource_updates=[
                    {"resource_pool_id": "local-b2-rotary", "workpoint_id": workpoint_b, "quantity": 8}
                ],
            )
        )
    with pytest.raises(ValueError, match="共享池"):
        update_resource_plan(
            ResourceAssistantUpdatePlanRequest(
                plan_id=plan.scenario_id,
                resource_plan=plan,
                scoped_resource_updates=[
                    {"resource_pool_id": "shared-rotary", "workpoint_id": workpoint_a, "quantity": 4}
                ],
            )
        )
    tampered = plan.model_copy(
        deep=True,
        update={
            "resource_pools": [
                pool.model_copy(update={"quantity": 4}) if pool.id == "shared-rotary" else pool
                for pool in plan.resource_pools
            ]
        },
    )
    with pytest.raises(ValueError, match="共享池必须保持当前配置"):
        solve_resource_plan(ResourceAssistantSingleSolveRequest(scenario=scenario, resource_plan=tampered))


def test_solve_keeps_full_project_scenario_and_target_in_fingerprint(monkeypatch) -> None:
    scenario, workpoint_a, _ = _scenario_with_scoped_resources()
    plan = _initialize(scenario, workpoint_a).resource_plans[1]
    monkeypatch.setattr(assistant_module, "AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS", 1.0)

    solved = solve_resource_plan(ResourceAssistantSingleSolveRequest(scenario=scenario, resource_plan=plan))

    assert solved.plan_result.generated is not None
    assert len(solved.plan_result.generated.schedule_input.tasks) == 68
    assert solved.plan_result.input_fingerprint == assistant_module._plan_input_fingerprint(scenario, plan)


def test_comparison_rejects_plans_from_different_target_workpoints() -> None:
    scenario, workpoint_a, workpoint_b = _scenario_with_scoped_resources()
    plans_a = _initialize(scenario, workpoint_a).resource_plans
    plans_b = _initialize(scenario, workpoint_b).resource_plans
    mixed = [plans_a[0], plans_a[1], plans_b[2]]

    with pytest.raises(ValueError, match="同一资源推进工点"):
        compare_resource_plan_results(ResourceAssistantResultsRequest(resource_plans=mixed, plan_results=[]))


def test_baseline_confirmation_requires_current_target_workpoint(tmp_path: Path, monkeypatch) -> None:
    scenario, workpoint_a, _ = _scenario_with_scoped_resources()
    plan = _initialize(scenario, workpoint_a).resource_plans[1]
    monkeypatch.setattr(assistant_module, "AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS", 1.0)
    solved = solve_resource_plan(ResourceAssistantSingleSolveRequest(scenario=scenario, resource_plan=plan))
    assert solved.plan_result.result is not None
    assert solved.plan_result.result.status in {"OPTIMAL", "FEASIBLE"}
    repository = PlanControlRepository(tmp_path / "plan-control.json")
    valid_request = CreateBaselinePlanRequest(
        scenario=scenario,
        resource_plan=solved.resource_plan,
        plan_result=solved.plan_result,
        confirmed_by="测试计划工程师",
        confirmation_reason="验证单工点资源方案可发布全项目基准",
    )

    baseline = create_baseline_plan(valid_request, repository)
    assert baseline.resource_plan_snapshot.target_workpoint_id == workpoint_a

    legacy_request = valid_request.model_copy(
        deep=True,
        update={
            "resource_plan": valid_request.resource_plan.model_copy(
                update={"target_workpoint_id": None, "target_workpoint_name": None}
            )
        },
    )
    with pytest.raises(PlanControlValidationError, match="缺少资源推进工点"):
        create_baseline_plan(legacy_request, repository)
