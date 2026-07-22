from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.scenario as scenario_module  # noqa: E402
from app.contracts import (  # noqa: E402
    MinResourcesSolveRequest,
    ResourceCostSolveRequest,
    ResourcePool,
    ScenarioCompareRequest,
)
from workpoint_scope_test_support import (  # noqa: E402
    WORKPOINT_A,
    WORKPOINT_B,
    two_workpoint_scenario,
)


def _shared_scenario(*, target_days: int | None = 5):
    return two_workpoint_scenario(
        ResourcePool(
            id="shared-cap",
            type="cap_team",
            label="共享承台班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
            cost_type="one_time_purchase",
            incremental_unit_cost=10,
        ),
        target_days=target_days,
    )


def test_single_workpoint_generation_scopes_tasks_links_resources_and_milestones() -> None:
    generated = scenario_module.generate_schedule_input_from_scenario(
        _shared_scenario(),
        workpoint_id=WORKPOINT_A,
    )

    assert generated.solve_scope.mode == "WORKPOINT"
    assert generated.solve_scope.workpoint_id == WORKPOINT_A
    assert generated.solve_scope.workpoint_name == "工点 1"
    assert generated.schedule_input.tasks
    assert {task.bridge_id for task in generated.schedule_input.tasks} == {WORKPOINT_A}
    task_ids = {task.id for task in generated.schedule_input.tasks}
    assert all(
        link.predecessor_id in task_ids and link.successor_id in task_ids
        for link in generated.schedule_input.precedence_links
    )
    assert all(WORKPOINT_A in resource.eligible_workpoint_ids for resource in generated.schedule_input.resources)
    assert generated.schedule_input.milestones
    assert generated.source_summary["bridge_count"] == 1


def test_single_workpoint_scope_is_shared_by_all_three_solve_modes() -> None:
    scenario = _shared_scenario()
    fixed = scenario_module.solve_scenario(scenario, workpoint_id=WORKPOINT_A)
    minimum = scenario_module.solve_min_resources_scenario(
        MinResourcesSolveRequest(scenario=scenario, fallback_target_days=5),
        workpoint_id=WORKPOINT_A,
    )
    cost = scenario_module.solve_resource_cost_scenario(
        ResourceCostSolveRequest(scenario=scenario, fallback_target_days=5),
        workpoint_id=WORKPOINT_A,
    )

    for solved in (fixed, minimum, cost):
        assert solved.generated.solve_scope.workpoint_id == WORKPOINT_A
        assert {task.bridge_id for task in solved.generated.schedule_input.tasks} == {WORKPOINT_A}
        assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
        assert all(
            alternative.generated.solve_scope == solved.generated.solve_scope
            for alternative in solved.alternative_results
        )


def test_missing_or_non_bridge_workpoint_does_not_fall_back_to_all() -> None:
    with pytest.raises(ValueError, match="不存在"):
        scenario_module.generate_schedule_input_from_scenario(_shared_scenario(), workpoint_id="WP-MISSING")


def test_single_workpoint_zero_resource_keeps_structured_blocking_diagnostic() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="local-a",
            type="cap_team",
            label="A 本地班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id=WORKPOINT_A,
            quantity=0,
            max_quantity=0,
        )
    )

    generated = scenario_module.generate_schedule_input_from_scenario(scenario, workpoint_id=WORKPOINT_A)
    errors = [
        message
        for message in generated.validation
        if message.code == "RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE"
    ]

    assert len(errors) == len(generated.schedule_input.tasks)
    assert all(message.details["workpoint_id"] == WORKPOINT_A for message in errors)


def test_full_project_scope_remains_default_and_only_full_results_can_compare() -> None:
    scenario = _shared_scenario()
    full = scenario_module.solve_scenario(scenario)
    scoped = scenario_module.solve_scenario(scenario, workpoint_id=WORKPOINT_A)

    assert full.generated.solve_scope.mode == "ALL"
    assert full.generated.solve_scope.workpoint_id is None
    compared = scenario_module.compare_scenarios(ScenarioCompareRequest(results=[full]))
    assert compared.best_scenario_id == full.scenario_id

    with pytest.raises(ValueError, match="单工点试算结果"):
        scenario_module.compare_scenarios(ScenarioCompareRequest(results=[full, scoped]))
