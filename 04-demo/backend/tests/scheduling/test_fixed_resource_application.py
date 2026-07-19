from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.scenario as legacy  # noqa: E402
from app.contracts import ResourcePool, WorkpointResourceOverride  # noqa: E402
from app.scheduling.application import fixed_resource  # noqa: E402
from app.scheduling.solver.engine import solve_shortest_duration_schedule  # noqa: E402
from workpoint_scope_test_support import (  # noqa: E402
    WORKPOINT_A,
    WORKPOINT_B,
    two_workpoint_scenario,
)


def test_fixed_resource_application_exports_the_legacy_use_cases() -> None:
    assert fixed_resource.solve_scenario is legacy.solve_scenario
    assert fixed_resource.solve_ai_strict_fixed_resource_scenario is legacy.solve_ai_strict_fixed_resource_scenario


def test_fixed_resource_generation_uses_each_effective_pool_quantity() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            quantity=1,
            max_quantity=3,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
            workpoint_overrides=[
                WorkpointResourceOverride(workpoint_id=WORKPOINT_A, quantity=2, max_quantity=4)
            ],
        )
    )

    generated = legacy.generate_schedule_input_from_scenario(scenario)

    resources = generated.schedule_input.resources
    assert len([item for item in resources if item.exclusive_workpoint_id == WORKPOINT_A]) == 2
    assert len([item for item in resources if item.exclusive_workpoint_id == WORKPOINT_B]) == 1
    assert generated.source_summary["resource_scope_rule_version"] == "workpoint-resource-scope/v1"
    assert generated.source_summary["exclusive_effective_pool_count"] == 2
    assert generated.source_summary["inherited_workpoint_count"] == 1


def test_project_shared_fixed_resource_adds_no_transfer_duration_or_precedence() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        )
    )
    generated = legacy.generate_schedule_input_from_scenario(scenario)
    result = solve_shortest_duration_schedule(generated.schedule_input)

    assert generated.schedule_input.precedence_links == []
    assert {task.duration_days for task in generated.schedule_input.tasks} == {5}
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 10
    assert generated.source_summary["project_shared_transfer_time_days"] == 0


def test_current_generation_uses_quantity_and_shared_pool_can_fill_zero_local_pool() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="local-a",
            type="cap_team",
            label="A 本地班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id=WORKPOINT_A,
            quantity=0,
            max_quantity=3,
        )
    )
    scenario.resource_pools.append(
        ResourcePool(
            id="shared-ab",
            type="cap_team",
            label="AB 共享班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        )
    )

    generated = legacy.generate_schedule_input_from_scenario(scenario)

    assert {resource.pool_id for resource in generated.schedule_input.resources} == {"shared-ab"}
    assert all(task.compatible_resource_types == ["cap_team"] for task in generated.schedule_input.tasks)
    assert not any(
        message.code == "RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE"
        for message in generated.validation
    )


def test_zero_local_without_legal_shared_pool_blocks_with_task_workpoint_type_and_pool_refs() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="local-a",
            type="cap_team",
            label="A 本地班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id=WORKPOINT_A,
            quantity=0,
            max_quantity=3,
        )
    )
    scenario.resource_pools.append(
        ResourcePool(
            id="shared-b",
            type="cap_team",
            label="B 共享班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=[WORKPOINT_B],
        )
    )

    generated = legacy.generate_schedule_input_from_scenario(scenario)
    task_a = next(task for task in generated.schedule_input.tasks if task.bridge_id == WORKPOINT_A)
    diagnostic = next(
        message
        for message in generated.validation
        if message.code == "RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE"
        and message.subject_id == task_a.id
    )

    assert diagnostic.level == "error"
    assert diagnostic.entity_refs == [task_a.id, WORKPOINT_A, "cap_team", "local-a", "shared-b"]
    assert "LOCAL_QUANTITY_ZERO" in diagnostic.message
    assert "SHARED_SCOPE_MISMATCH" in diagnostic.message
