from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.scenario as legacy  # noqa: E402
import app.scheduling.application._scenario as scenario_module  # noqa: E402
from app.contracts import ResourcePool, ScheduleResult, WorkpointResourceOverride  # noqa: E402
from app.local_scenario_config import apply_local_scenario_config  # noqa: E402
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


def test_simulation_and_ai_fixed_resource_entries_share_one_authoritative_solve(monkeypatch) -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            quantity=2,
            max_quantity=4,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        ),
        target_days=5,
    )
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_solve(schedule_input, **kwargs):
        calls.append((str(kwargs.get("optimization_stage")), tuple(resource.id for resource in schedule_input.resources)))
        return ScheduleResult(
            status="OPTIMAL",
            objective_days=5,
            plan_start_date=schedule_input.start_date,
            milestone_results=[],
        )

    monkeypatch.setattr(scenario_module, "solve_control_priority_schedule_once", fake_solve)

    simulation = scenario_module.solve_scenario(scenario)
    ai = scenario_module.solve_ai_strict_fixed_resource_scenario(scenario)

    assert len(calls) == 2
    assert calls[0][0] == calls[1][0] == "unified_fixed_resource"
    assert calls[0][1] == calls[1][1]
    for solved in (simulation, ai):
        assert solved.result.stats["solver_call_count"] == 1
        assert solved.result.stats["resource_expansion_attempted"] is False
        assert solved.result.stats["objective_priority"] == ["max_target_delay_days", "makespan_days"]
        assert solved.alternative_results == []


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


def test_project_config_cleanup_prevents_shared_resources_from_reaching_generation(tmp_path: Path) -> None:
    base = two_workpoint_scenario(
        ResourcePool(
            id="local-a",
            type="cap_team",
            label="A 本地班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id=WORKPOINT_A,
            quantity=1,
            max_quantity=2,
        )
    )
    local_b = ResourcePool(
        id="local-b",
        type="cap_team",
        label="B 本地班组",
        scope_mode="WORKPOINT_EXCLUSIVE",
        workpoint_id=WORKPOINT_B,
        quantity=1,
        max_quantity=2,
    )
    shared = ResourcePool(
        id="shared-ab",
        type="cap_team",
        label="AB 旧共享班组",
        scope_mode="PROJECT_SHARED",
        quantity=2,
        max_quantity=3,
        authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
    )
    path = tmp_path / "scheduler-config.json"
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v3", "resource_pools": [base.resource_pools[0].model_dump(mode="json"), local_b.model_dump(mode="json"), shared.model_dump(mode="json")]}),
        encoding="utf-8",
    )
    base.resource_pools = []

    cleaned = apply_local_scenario_config(base, path=path)
    generated = legacy.generate_schedule_input_from_scenario(cleaned)

    assert {pool.id for pool in cleaned.resource_pools} == {"local-a", "local-b"}
    assert {resource.pool_id for resource in generated.schedule_input.resources} == {"local-a", "local-b"}
    assert generated.source_summary["shared_effective_pool_count"] == 0
    assert not any(message.code == "PROJECT_SHARED_TRANSFER_ZERO_DAYS" for message in generated.validation)


def test_shared_only_project_cleanup_blocks_tasks_as_unconfigured_local_resources(tmp_path: Path) -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="shared-ab",
            type="cap_team",
            label="AB 旧共享班组",
            scope_mode="PROJECT_SHARED",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        )
    )
    path = tmp_path / "scheduler-config.json"
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v3", "resource_pools": [scenario.resource_pools[0].model_dump(mode="json")]}),
        encoding="utf-8",
    )
    scenario.resource_pools = []

    cleaned = apply_local_scenario_config(scenario, path=path)
    generated = legacy.generate_schedule_input_from_scenario(cleaned)

    errors = [message for message in generated.validation if message.code == "RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE"]
    assert cleaned.resource_pools == []
    assert generated.schedule_input.resources == []
    assert len(errors) == len(generated.schedule_input.tasks)
    assert all(message.details["reason"] == "RESOURCE_TYPE_UNCONFIGURED" for message in errors)
