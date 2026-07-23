from __future__ import annotations

from datetime import date
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import app.models as legacy  # noqa: E402
from app.contracts import (  # noqa: E402
    Resource,
    ResourcePool,
    ResourceScopeMode,
    WorkpointResourceOverride,
)
from app.contracts import common, project, scheduling  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402


def test_scheduling_contracts_are_the_legacy_objects_not_copies() -> None:
    assert common.ValidationMessage is legacy.ValidationMessage
    assert project.ScenarioInput is legacy.ScenarioInput
    assert scheduling.ScheduleInput is legacy.ScheduleInput
    assert scheduling.ScheduleResult is legacy.ScheduleResult


def test_scenario_defaults_and_schedule_json_stay_snake_case() -> None:
    schema = project.ScenarioInput.model_json_schema()
    assert "scenario_id" in schema["properties"]
    assert scheduling.ScheduleResult.model_json_schema()["properties"]["tasks"]
    assert "details" in common.ValidationMessage.model_json_schema()["properties"]


def test_schedule_result_keeps_unified_metadata_additive_and_old_results_readable() -> None:
    unified = scheduling.ScheduleResult(
        status="OPTIMAL",
        plan_start_date=date(2026, 1, 1),
        stats={
            "solve_mode": "min_resources_fixed_duration",
            "global_search_status": "OPTIMAL",
            "minimum_resource_verification": {
                "candidate_found": True,
                "candidate_verified": False,
                "detail_solve_attempted": True,
                "detail_solver_call_count": 1,
                "detail_target_status": "not_met",
                "retry_attempted": False,
            },
        },
    )
    legacy_result = scheduling.ScheduleResult(status="FEASIBLE", plan_start_date=date(2026, 1, 1))

    dumped = unified.model_dump(mode="json")
    assert dumped["stats"]["minimum_resource_verification"]["detail_target_status"] == "not_met"
    assert dumped["stats"]["minimum_resource_verification"]["retry_attempted"] is False
    assert legacy_result.stats == {}


def test_unlimited_resource_pool_and_projection_metadata_are_open_contracts() -> None:
    pool = ResourcePool(
        id="pool-any",
        type="any_team",
        label="通用班组",
        resource_mode="UNLIMITED",
        quantity=None,
        max_quantity=None,
    )
    generated = scheduling.GeneratedScheduleInput(
        schedule_input=scheduling.ScheduleInput(
            project_name="契约测试",
            start_date=date(2026, 1, 1),
            tasks=[],
            precedence_links=[],
            resources=[],
        ),
        source_summary={
            "project_data_version_id": "pmv-contract",
            "scheduling_projection_version": "projection-contract/v1",
        },
    )

    assert pool.quantity is None
    assert pool.max_quantity is None
    assert generated.source_summary["scheduling_projection_version"] == "projection-contract/v1"


def test_resource_scope_contract_defaults_and_explicit_empty_scope_are_distinct() -> None:
    legacy_pool = ResourcePool(id="pool-legacy", type="legacy-team", label="旧资源", quantity=2, max_quantity=4)
    empty_scope_pool = ResourcePool(
        id="pool-empty",
        type="empty-team",
        label="显式空范围",
        authorized_workpoint_ids=[],
    )
    normalized_pool = ResourcePool(
        id="pool-normalized",
        type="normalized-team",
        label="标准资源",
        scope_mode="WORKPOINT_EXCLUSIVE",
        authorized_workpoint_ids=["WP-B", "WP-A", "WP-B"],
        workpoint_overrides=[
            WorkpointResourceOverride(workpoint_id="WP-B", quantity=2, max_quantity=1),
            WorkpointResourceOverride(workpoint_id="WP-A", enabled=False),
        ],
    )

    assert legacy_pool.scope_mode == "PROJECT_SHARED"
    assert legacy_pool.authorized_workpoint_ids is None
    assert legacy_pool.workpoint_overrides == []
    assert empty_scope_pool.authorized_workpoint_ids == []
    assert normalized_pool.authorized_workpoint_ids == ["WP-A", "WP-B"]
    assert [item.workpoint_id for item in normalized_pool.workpoint_overrides] == ["WP-A", "WP-B"]
    assert normalized_pool.workpoint_overrides[1].max_quantity == 2
    assert legacy.ResourceScopeMode is ResourceScopeMode


def test_resource_scope_contract_rejects_duplicate_overrides_and_negative_quantities() -> None:
    with pytest.raises(ValueError, match="duplicate workpoint_overrides"):
        ResourcePool(
            id="pool-duplicate",
            type="duplicate-team",
            label="重复覆盖",
            workpoint_overrides=[
                {"workpoint_id": "WP-A", "quantity": 1},
                {"workpoint_id": "WP-A", "quantity": 2},
            ],
        )

    with pytest.raises(ValueError):
        WorkpointResourceOverride(workpoint_id="WP-A", quantity=-1)

    with pytest.raises(ValueError):
        ResourcePool(id="pool-negative", type="negative-team", label="负数", quantity=-1)

    with pytest.raises(ValueError, match="min_quantity is not part"):
        ResourcePool.model_validate(
            {
                "id": "pool-removed-min",
                "type": "negative-team",
                "label": "已移除下限",
                "min_quantity": 1,
            }
        )


def test_workpoint_first_resource_pool_contract_enforces_identity_and_allows_same_type_pools() -> None:
    local_pool = ResourcePool(
        id="pool-local-a",
        type="rotary_drill",
        label="A 工点旋挖钻",
        scope_mode="WORKPOINT_EXCLUSIVE",
        workpoint_id=" WP-A ",
        quantity=0,
        max_quantity=3,
    )
    shared_one = ResourcePool(
        id="pool-shared-one",
        type="rotary_drill",
        label="共享池一",
        authorized_workpoint_ids=["WP-B", "WP-A"],
        quantity=2,
        max_quantity=4,
    )
    shared_two = ResourcePool(
        id="pool-shared-two",
        type="rotary_drill",
        label="共享池二",
        authorized_workpoint_ids=["WP-C", "WP-B"],
        quantity=1,
        max_quantity=2,
    )

    scenario_payload = default_scenario().model_dump(mode="python")
    scenario_payload["resource_pools"] = [local_pool, shared_one, shared_two]
    scenario = project.ScenarioInput.model_validate(scenario_payload)

    assert local_pool.workpoint_id == "WP-A"
    assert local_pool.authorized_workpoint_ids is None
    assert local_pool.workpoint_overrides == []
    assert [pool.id for pool in scenario.resource_pools] == [
        "pool-local-a",
        "pool-shared-one",
        "pool-shared-two",
    ]
    assert [pool.type for pool in scenario.resource_pools] == ["rotary_drill"] * 3


def test_workpoint_first_resource_pool_contract_rejects_invalid_combinations_and_duplicate_keys() -> None:
    with pytest.raises(ValueError, match="PROJECT_SHARED.*workpoint_id"):
        ResourcePool(
            id="pool-invalid-shared",
            type="rotary_drill",
            label="非法共享池",
            workpoint_id="WP-A",
        )

    with pytest.raises(ValueError, match="authorized_workpoint_ids"):
        ResourcePool(
            id="pool-invalid-local",
            type="rotary_drill",
            label="非法本地池",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id="WP-A",
            authorized_workpoint_ids=["WP-A"],
        )

    base = default_scenario().model_dump(mode="python")
    duplicate_id = ResourcePool(id="pool-duplicate", type="type-a", label="一")
    base["resource_pools"] = [
        duplicate_id,
        ResourcePool(id="pool-duplicate", type="type-b", label="二"),
    ]
    with pytest.raises(ValueError, match="duplicate resource pool ids"):
        project.ScenarioInput.model_validate(base)

    base["resource_pools"] = [
        ResourcePool(
            id="pool-local-a-1",
            type="type-a",
            label="A-1",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id="WP-A",
        ),
        ResourcePool(
            id="pool-local-a-2",
            type="type-a",
            label="A-2",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id="WP-A",
        ),
    ]
    with pytest.raises(ValueError, match="duplicate workpoint resource keys"):
        project.ScenarioInput.model_validate(base)


def test_resource_pool_preserves_unknown_legacy_fields_instead_of_silently_dropping_them() -> None:
    pool = ResourcePool.model_validate(
        {
            "id": "pool-legacy-extra",
            "type": "rotary_drill",
            "label": "旧共享池",
            "quantity": 2,
            "legacy_extension": {"keep": True},
        }
    )

    assert pool.model_dump(mode="json")["legacy_extension"] == {"keep": True}
    assert pool.scope_mode == "PROJECT_SHARED"
    assert pool.workpoint_id is None


def test_resource_gap_validation_contract_carries_machine_readable_details_additively() -> None:
    diagnostic = common.ValidationMessage(
        level="error",
        code="RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE",
        subject_id="task-a",
        entity_refs=["task-a", "WP-A", "rotary_drill", "pool-a"],
        message="当前资源计划没有合法候选。",
        details={
            "task_id": "task-a",
            "workpoint_id": "WP-A",
            "resource_type": "rotary_drill",
            "relevant_pool_ids": ["pool-a"],
            "reasons": ["LOCAL_QUANTITY_ZERO"],
        },
    )

    assert diagnostic.details is not None
    assert diagnostic.details["reasons"] == ["LOCAL_QUANTITY_ZERO"]


def test_named_resource_carries_explicit_scope_without_min_quantity() -> None:
    shared = Resource(
        id="resource-shared",
        name="共享资源",
        type="shared-team",
        scope_mode="PROJECT_SHARED",
        eligible_workpoint_ids=["WP-B", "WP-A", "WP-B"],
    )
    exclusive = Resource(
        id="resource-exclusive",
        name="独享资源",
        type="exclusive-team",
        scope_mode="WORKPOINT_EXCLUSIVE",
        eligible_workpoint_ids=["WP-A"],
        exclusive_workpoint_id="WP-A",
    )

    assert shared.eligible_workpoint_ids == ["WP-A", "WP-B"]
    assert shared.exclusive_workpoint_id is None
    assert exclusive.eligible_workpoint_ids == ["WP-A"]
    assert exclusive.exclusive_workpoint_id == "WP-A"
    assert "min_quantity" not in ResourcePool.model_fields
    assert "min_quantity" not in WorkpointResourceOverride.model_fields
    assert "min_quantity" not in Resource.model_fields
