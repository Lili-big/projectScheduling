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


def test_scheduling_contracts_are_the_legacy_objects_not_copies() -> None:
    assert common.ValidationMessage is legacy.ValidationMessage
    assert project.ScenarioInput is legacy.ScenarioInput
    assert scheduling.ScheduleInput is legacy.ScheduleInput
    assert scheduling.ScheduleResult is legacy.ScheduleResult


def test_scenario_defaults_and_schedule_json_stay_snake_case() -> None:
    schema = project.ScenarioInput.model_json_schema()
    assert "scenario_id" in schema["properties"]
    assert scheduling.ScheduleResult.model_json_schema()["properties"]["tasks"]


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
