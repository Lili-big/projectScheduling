from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts import ProjectBridge, ResourcePool, WorkpointResourceOverride  # noqa: E402
from app.scheduling.application._scenario import expand_effective_resource_pools  # noqa: E402
from app.scheduling.domain.resource_scope import resolve_effective_resource_pools  # noqa: E402


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
