from __future__ import annotations

from functools import lru_cache

from app.models import (
    CreateBaselinePlanRequest,
    ResourceAssistantInitialRequest,
    ResourceAssistantSingleSolveRequest,
)
from app.services.ai_resource_scheduling_assistant import initialize_resource_assistant, solve_resource_plan
from app.services.process_library_service import default_scenario_with_process_library


@lru_cache(maxsize=1)
def _solved_baseline_request() -> CreateBaselinePlanRequest:
    scenario = default_scenario_with_process_library()
    initial = initialize_resource_assistant(
        ResourceAssistantInitialRequest(scenario=scenario, generation_mode="local_fallback_only")
    )
    resource_plan = initial.resource_plans[0]
    solved = solve_resource_plan(
        ResourceAssistantSingleSolveRequest(scenario=scenario, resource_plan=resource_plan)
    )
    assert solved.plan_result.result is not None
    assert solved.plan_result.result.status in {"OPTIMAL", "FEASIBLE"}
    return CreateBaselinePlanRequest(
        scenario=scenario,
        resource_plan=solved.resource_plan,
        plan_result=solved.plan_result,
        confirmed_by="测试计划工程师",
        confirmation_reason="用于计划管控自动化测试",
    )


def solved_baseline_request() -> CreateBaselinePlanRequest:
    return _solved_baseline_request().model_copy(deep=True)
