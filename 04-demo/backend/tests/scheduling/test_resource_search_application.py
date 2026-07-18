from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.scenario as legacy  # noqa: E402
from app.contracts import MinResourcesSolveRequest, ResourceCostSolveRequest, ResourcePool  # noqa: E402
from app.scheduling.application import resource_search  # noqa: E402
from app.scheduling.application._scenario import _resource_linear_costs_by_pool  # noqa: E402
from workpoint_scope_test_support import (  # noqa: E402
    WORKPOINT_A,
    WORKPOINT_B,
    two_workpoint_scenario,
)


def test_resource_search_application_exports_minimum_and_cost_use_cases() -> None:
    assert resource_search.solve_min_resources_scenario is legacy.solve_min_resources_scenario
    assert resource_search.solve_resource_cost_scenario is legacy.solve_resource_cost_scenario


def test_minimum_resource_search_can_recommend_below_current_quantity() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            quantity=3,
            max_quantity=5,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        ),
        target_days=5,
    )

    solved = legacy.solve_min_resources_scenario(
        MinResourcesSolveRequest(scenario=scenario, fallback_target_days=5)
    )

    recommendation = solved.result.stats["recommended_resource_counts"][0]
    diagnostics = solved.result.stats["resource_scope_diagnostics"]["groups"][0]
    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert recommendation["recommended_quantity"] == 2
    assert diagnostics["current_quantity"] == 3
    assert diagnostics["recommended_quantity"] == 2


def test_resource_cost_search_range_is_quantity_to_max_for_each_effective_pool() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            quantity=3,
            max_quantity=5,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
            cost_type="one_time_purchase",
            incremental_unit_cost=10,
        ),
        target_days=5,
    )

    costs = _resource_linear_costs_by_pool(scenario)
    solved = legacy.solve_resource_cost_scenario(
        ResourceCostSolveRequest(scenario=scenario, fallback_target_days=5)
    )

    assert set(costs) == {
        "pool-cap::workpoint::WP-A",
        "pool-cap::workpoint::WP-B",
    }
    assert all(item["current_quantity"] == 3 and item["max_quantity"] == 5 for item in costs.values())
    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert all(
        3 <= item["recommended_quantity"] <= 5
        for item in solved.result.stats["recommended_resource_counts"]
    )
