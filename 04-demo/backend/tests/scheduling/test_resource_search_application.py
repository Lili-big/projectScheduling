from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.scenario as legacy  # noqa: E402
from app.contracts import (  # noqa: E402
    MinResourcesSolveRequest,
    Resource,
    ResourceCostSolveRequest,
    ResourcePool,
    ScheduleInput,
    Task,
)
from app.scheduling.application import resource_search  # noqa: E402
from app.scheduling.application._scenario import _resource_linear_costs_by_pool  # noqa: E402
from app.scheduling.solver.engine import (  # noqa: E402
    _resource_capacity_exclusive_lower_bound_diagnostics,
    _resource_capacity_lower_bound_diagnostics,
    _resource_groups,
)
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


def test_overlapping_pool_lower_bounds_count_only_tasks_with_a_unique_candidate_pool() -> None:
    resources = [
        Resource(
            id="shared-ab-1",
            name="AB 共享",
            type="cap_team",
            pool_id="shared-ab",
            scope_mode="PROJECT_SHARED",
            eligible_workpoint_ids=["WP-A", "WP-B"],
        ),
        Resource(
            id="shared-bc-1",
            name="BC 共享",
            type="cap_team",
            pool_id="shared-bc",
            scope_mode="PROJECT_SHARED",
            eligible_workpoint_ids=["WP-B", "WP-C"],
        ),
    ]
    tasks = [
        _resource_task("TASK-A", "WP-A"),
        _resource_task("TASK-B", "WP-B"),
    ]
    schedule_input = ScheduleInput(
        project_name="重叠共享池下界",
        start_date=two_workpoint_scenario(ResourcePool(id="p", type="cap_team", label="p")).project.start_date,
        tasks=tasks,
        precedence_links=[],
        resources=resources,
    )
    groups = _resource_groups(resources)

    diagnostics = _resource_capacity_lower_bound_diagnostics(schedule_input, groups, 5)
    exclusive = _resource_capacity_exclusive_lower_bound_diagnostics(schedule_input, groups, 5)

    assert diagnostics == [
        {
            "resource_pool_id": "shared-ab",
            "label": "cap_team",
            "resource_type": "cap_team",
            "window_days": 5,
            "scoped_task_count": 1,
            "workload_days": 5,
            "required_minimum": 1,
            "max_quantity": 1,
            "upper_bound_gap": 0,
            "exceeds_upper_bound": False,
        }
    ]
    assert exclusive[0]["resource_pool_id"] == "shared-ab"
    assert exclusive[0]["scoped_task_count"] == 1
    assert all(item["resource_pool_id"] != "shared-bc" for item in exclusive)


def _resource_task(task_id: str, workpoint_id: str) -> Task:
    return Task(
        id=task_id,
        name=task_id,
        bridge_id=workpoint_id,
        structure_id=f"S-{task_id}",
        structure_name=task_id,
        structure_type="pier",
        component_type="cap",
        process_name="承台施工",
        productivity_rule_id="cap-test",
        quantity=1,
        quantity_label="1个",
        duration_days=5,
        compatible_resource_types=["cap_team"],
    )
