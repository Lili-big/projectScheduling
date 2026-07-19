from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.contracts import ProjectBridge, ResourcePool, WorkpointResourceOverride  # noqa: E402
from app.scenario_data import derive_resource_catalog, derive_workpoint_possible_resource_types  # noqa: E402
from app.scheduling.application._scenario import expand_effective_resource_pools  # noqa: E402
from app.scheduling.domain.resource_scope import resolve_effective_resource_pools  # noqa: E402
from workpoint_scope_test_support import WORKPOINT_A, WORKPOINT_B, two_workpoint_scenario  # noqa: E402


def _bridges() -> list[ProjectBridge]:
    return [
        ProjectBridge(id="WP-B", name="乙工点", order=2),
        ProjectBridge(id="NOT-A-BRIDGE", name="非桥梁工点", order=3, workpoint_type="tunnel"),
        ProjectBridge(id="WP-A", name="甲工点", order=1),
    ]


def test_effective_pools_resolve_shared_exclusive_inheritance_and_partial_overrides() -> None:
    shared = ResourcePool(
        id="shared-pool",
        type="shared-team",
        label="共享班组",
        quantity=1,
        max_quantity=2,
    )
    exclusive = ResourcePool(
        id="exclusive-pool",
        type="exclusive-team",
        label="独享班组",
        scope_mode="WORKPOINT_EXCLUSIVE",
        quantity=1,
        max_quantity=3,
        authorized_workpoint_ids=["WP-B", "WP-A", "WP-A"],
        workpoint_overrides=[
            WorkpointResourceOverride(workpoint_id="WP-A", quantity=2, max_quantity=4),
            WorkpointResourceOverride(workpoint_id="WP-B", max_quantity=5),
        ],
    )

    resolution = resolve_effective_resource_pools(
        project_data_version_id="project-data-v1",
        bridges=_bridges(),
        resource_pools=[exclusive, shared],
    )

    assert resolution.diagnostics == ()
    assert [pool.effective_pool_id for pool in resolution.pools] == [
        "exclusive-pool::workpoint::WP-A",
        "exclusive-pool::workpoint::WP-B",
        "shared-pool",
    ]
    by_id = {pool.effective_pool_id: pool for pool in resolution.pools}
    assert by_id["shared-pool"].eligible_workpoint_ids == ("WP-A", "WP-B")
    assert by_id["exclusive-pool::workpoint::WP-A"].quantity == 2
    assert by_id["exclusive-pool::workpoint::WP-A"].max_quantity == 4
    assert by_id["exclusive-pool::workpoint::WP-A"].inheritance_source == "overridden"
    assert by_id["exclusive-pool::workpoint::WP-B"].quantity == 1
    assert by_id["exclusive-pool::workpoint::WP-B"].max_quantity == 5
    assert by_id["exclusive-pool::workpoint::WP-B"].inheritance_source == "overridden"
    assert resolution.inherited_workpoint_count == 0


def test_effective_pools_reject_empty_or_unknown_authorized_workpoints_without_name_fallback() -> None:
    empty = ResourcePool(
        id="empty-pool",
        type="empty-team",
        label="空范围班组",
        scope_mode="WORKPOINT_EXCLUSIVE",
        quantity=1,
        max_quantity=1,
        authorized_workpoint_ids=[],
    )
    unknown = ResourcePool(
        id="unknown-pool",
        type="unknown-team",
        label="旧版本班组",
        scope_mode="WORKPOINT_EXCLUSIVE",
        quantity=1,
        max_quantity=1,
        authorized_workpoint_ids=["OLD-VERSION-WP"],
    )

    resolution = resolve_effective_resource_pools(
        project_data_version_id="project-data-v1",
        bridges=_bridges(),
        resource_pools=[empty, unknown],
    )

    assert resolution.pools == ()
    assert {message.code for message in resolution.diagnostics} == {
        "RESOURCE_SCOPE_EMPTY_AUTHORIZED",
        "RESOURCE_SCOPE_UNKNOWN_WORKPOINT",
    }
    assert all(message.level == "error" for message in resolution.diagnostics)


def test_unlimited_pool_is_explicit_but_does_not_expand_named_resources() -> None:
    pool = ResourcePool(
        id="unlimited-pool",
        type="unlimited-team",
        label="默认充足班组",
        resource_mode="UNLIMITED",
        quantity=7,
        max_quantity=None,
        authorized_workpoint_ids=None,
    )
    resolution = resolve_effective_resource_pools(
        project_data_version_id="project-data-v1",
        bridges=_bridges(),
        resource_pools=[pool],
    )

    assert len(resolution.pools) == 1
    assert resolution.pools[0].resource_mode == "UNLIMITED"
    resources, messages = expand_effective_resource_pools(resolution.pools)
    assert resources == []
    assert messages == []


def test_named_resources_expand_once_for_shared_and_per_workpoint_for_exclusive() -> None:
    pools = [
        ResourcePool(
            id="shared-pool",
            type="shared-team",
            label="共享班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=["WP-A", "WP-B"],
        ),
        ResourcePool(
            id="exclusive-pool",
            type="exclusive-team",
            label="独享班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            quantity=1,
            max_quantity=3,
            authorized_workpoint_ids=["WP-A", "WP-B"],
            workpoint_overrides=[WorkpointResourceOverride(workpoint_id="WP-A", quantity=2, max_quantity=4)],
        ),
    ]
    resolution = resolve_effective_resource_pools(
        project_data_version_id="project-data-v1",
        bridges=_bridges(),
        resource_pools=pools,
    )

    fixed, fixed_messages = expand_effective_resource_pools(resolution.pools)
    maximum, maximum_messages = expand_effective_resource_pools(resolution.pools, use_max_quantity=True)

    assert fixed_messages == []
    assert maximum_messages == []
    assert len([item for item in fixed if item.type == "shared-team"]) == 1
    assert len([item for item in maximum if item.type == "shared-team"]) == 2
    assert len([item for item in fixed if item.type == "exclusive-team"]) == 3
    assert len([item for item in maximum if item.type == "exclusive-team"]) == 7
    assert len({item.id for item in maximum}) == len(maximum)
    assert all(item.eligible_workpoint_ids == ["WP-A", "WP-B"] for item in maximum if item.type == "shared-team")
    assert all(
        item.eligible_workpoint_ids == [item.exclusive_workpoint_id]
        for item in maximum
        if item.type == "exclusive-team"
    )


def test_direct_workpoint_pool_and_multiple_same_type_shared_pools_keep_pool_identity() -> None:
    pools = [
        ResourcePool(
            id="local-a",
            type="cap_team",
            label="A 本地班组",
            scope_mode="WORKPOINT_EXCLUSIVE",
            workpoint_id="WP-A",
            quantity=2,
            max_quantity=4,
        ),
        ResourcePool(
            id="shared-ab",
            type="cap_team",
            label="AB 共享班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=["WP-A", "WP-B"],
        ),
        ResourcePool(
            id="shared-b",
            type="cap_team",
            label="B 共享班组",
            quantity=1,
            max_quantity=3,
            authorized_workpoint_ids=["WP-B"],
        ),
    ]

    resolution = resolve_effective_resource_pools(
        project_data_version_id="project-data-v1",
        bridges=_bridges(),
        resource_pools=list(reversed(pools)),
    )

    assert resolution.diagnostics == ()
    assert [pool.effective_pool_id for pool in resolution.pools] == [
        "local-a",
        "shared-ab",
        "shared-b",
    ]
    by_id = {pool.effective_pool_id: pool for pool in resolution.pools}
    assert by_id["local-a"].workpoint_id == "WP-A"
    assert by_id["local-a"].eligible_workpoint_ids == ("WP-A",)
    assert by_id["local-a"].inheritance_source == "global"
    assert by_id["shared-ab"].eligible_workpoint_ids == ("WP-A", "WP-B")
    assert by_id["shared-b"].eligible_workpoint_ids == ("WP-B",)

    resources, messages = expand_effective_resource_pools(resolution.pools)
    assert messages == []
    assert {resource.pool_id for resource in resources} == {"local-a", "shared-ab", "shared-b"}
    assert len([resource for resource in resources if resource.pool_id == "local-a"]) == 2


def test_effective_pools_reject_duplicate_pool_ids_duplicate_local_keys_and_unknown_local_workpoint() -> None:
    resolution = resolve_effective_resource_pools(
        project_data_version_id="project-data-v1",
        bridges=_bridges(),
        resource_pools=[
            ResourcePool(id="duplicate", type="cap_team", label="共享一", quantity=1),
            ResourcePool(id="duplicate", type="pier_body_team", label="共享二", quantity=1),
            ResourcePool(
                id="local-a-1",
                type="cap_team",
                label="A 本地一",
                scope_mode="WORKPOINT_EXCLUSIVE",
                workpoint_id="WP-A",
                quantity=1,
            ),
            ResourcePool(
                id="local-a-2",
                type="cap_team",
                label="A 本地二",
                scope_mode="WORKPOINT_EXCLUSIVE",
                workpoint_id="WP-A",
                quantity=1,
            ),
            ResourcePool(
                id="local-old",
                type="cap_beam_team",
                label="旧工点本地",
                scope_mode="WORKPOINT_EXCLUSIVE",
                workpoint_id="OLD-WP",
                quantity=1,
            ),
        ],
    )

    assert resolution.pools == ()
    assert {message.code for message in resolution.diagnostics} == {
        "RESOURCE_SCOPE_DUPLICATE_POOL_ID",
        "RESOURCE_SCOPE_DUPLICATE_LOCAL_KEY",
        "RESOURCE_SCOPE_UNKNOWN_WORKPOINT",
    }


def test_resource_catalog_and_workpoint_possible_types_are_deterministic_projections() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="shared-cap",
            type="cap_team",
            label="项目承台班组",
            quantity=1,
            max_quantity=3,
        )
    )
    scenario.resource_pools.append(
        ResourcePool(
            id="configured-generator",
            type="generator",
            label="发电机",
            quantity=0,
            max_quantity=2,
        )
    )

    catalog = derive_resource_catalog(scenario)

    assert [item["resource_type"] for item in catalog] == sorted(
        item["resource_type"] for item in catalog
    )
    assert next(item for item in catalog if item["resource_type"] == "cap_team")[
        "applicable_process_ids"
    ] == ["cap-scope-test"]
    assert next(item for item in catalog if item["resource_type"] == "generator")["label"] == "发电机"
    assert derive_workpoint_possible_resource_types(scenario, WORKPOINT_A) == ["cap_team"]
    assert derive_workpoint_possible_resource_types(scenario, WORKPOINT_B) == ["cap_team"]
