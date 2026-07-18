from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...contracts import ProjectBridge, ResourcePool, ResourceScopeMode, ValidationMessage


RESOURCE_SCOPE_RULE_VERSION = "workpoint-resource-scope/v1"
InheritanceSource = Literal["global", "inherited", "overridden"]


@dataclass(frozen=True)
class EffectiveResourcePool:
    effective_pool_id: str
    source_pool_id: str
    resource_type: str
    label: str
    resource_mode: str
    scope_mode: ResourceScopeMode
    workpoint_id: str | None
    eligible_workpoint_ids: tuple[str, ...]
    enabled: bool
    quantity: int
    max_quantity: int
    calendar_id: str
    inheritance_source: InheritanceSource
    cost_type: str
    incremental_unit_cost: int
    billing_period_days: int
    same_structure_resource_binding: bool
    parallel_rule_description: str


@dataclass(frozen=True)
class EffectiveResourceResolution:
    pools: tuple[EffectiveResourcePool, ...]
    diagnostics: tuple[ValidationMessage, ...]
    bridge_workpoint_ids: tuple[str, ...]
    inherited_workpoint_count: int

    @property
    def shared_effective_pool_count(self) -> int:
        return sum(pool.scope_mode == "PROJECT_SHARED" for pool in self.pools)

    @property
    def exclusive_effective_pool_count(self) -> int:
        return sum(pool.scope_mode == "WORKPOINT_EXCLUSIVE" for pool in self.pools)


def resolve_effective_resource_pools(
    *,
    project_data_version_id: str | None,
    bridges: list[ProjectBridge],
    resource_pools: list[ResourcePool],
) -> EffectiveResourceResolution:
    """Resolve the single authoritative resource configuration for scheduling.

    The resolver only reads explicit contract fields and the current bridge workpoint
    identities. It never interprets names, identifier shapes, quantities, or resource
    types to infer scope.
    """

    bridge_workpoint_ids = tuple(
        sorted({bridge.id for bridge in bridges if bridge.workpoint_type == "bridge"})
    )
    valid_workpoint_ids = set(bridge_workpoint_ids)
    diagnostics: list[ValidationMessage] = []
    effective_pools: list[EffectiveResourcePool] = []
    inherited_workpoint_count = 0

    pools_by_type: dict[str, list[ResourcePool]] = {}
    for pool in resource_pools:
        pools_by_type.setdefault(pool.type, []).append(pool)
    duplicate_types = sorted(resource_type for resource_type, pools in pools_by_type.items() if len(pools) > 1)
    for resource_type in duplicate_types:
        duplicates = sorted(pool.id for pool in pools_by_type[resource_type])
        diagnostics.append(
            ValidationMessage(
                level="error",
                code="RESOURCE_SCOPE_DUPLICATE_TYPE",
                subject_id=resource_type,
                entity_refs=duplicates,
                message=f"资源类型 {resource_type} 存在多个权威资源池：{', '.join(duplicates)}。",
            )
        )

    for pool in sorted(resource_pools, key=lambda item: (item.type, item.id)):
        if pool.type in duplicate_types:
            continue
        authorized = (
            bridge_workpoint_ids
            if pool.authorized_workpoint_ids is None
            else tuple(pool.authorized_workpoint_ids)
        )
        if pool.authorized_workpoint_ids == []:
            diagnostics.append(
                ValidationMessage(
                    level="error",
                    code="RESOURCE_SCOPE_EMPTY_AUTHORIZED",
                    subject_id=pool.id,
                    entity_refs=[pool.id],
                    message=f"资源池“{pool.label}”显式配置了空获准工点集合。",
                )
            )
            continue

        unknown_authorized = sorted(set(authorized) - valid_workpoint_ids)
        if unknown_authorized:
            diagnostics.append(
                ValidationMessage(
                    level="error",
                    code="RESOURCE_SCOPE_UNKNOWN_WORKPOINT",
                    subject_id=pool.id,
                    entity_refs=[pool.id, *unknown_authorized],
                    message=(
                        f"资源池“{pool.label}”引用了不属于当前项目主数据版本"
                        f" {project_data_version_id or 'unknown'} 的桥梁工点：{', '.join(unknown_authorized)}。"
                    ),
                )
            )
            continue

        override_by_workpoint = {override.workpoint_id: override for override in pool.workpoint_overrides}
        unknown_overrides = sorted(set(override_by_workpoint) - valid_workpoint_ids)
        if unknown_overrides:
            diagnostics.append(
                ValidationMessage(
                    level="error",
                    code="RESOURCE_SCOPE_UNKNOWN_OVERRIDE_WORKPOINT",
                    subject_id=pool.id,
                    entity_refs=[pool.id, *unknown_overrides],
                    message=(
                        f"资源池“{pool.label}”的覆盖引用了不属于当前项目主数据版本"
                        f" {project_data_version_id or 'unknown'} 的桥梁工点：{', '.join(unknown_overrides)}。"
                    ),
                )
            )
            continue
        unauthorized_overrides = sorted(set(override_by_workpoint) - set(authorized))
        if unauthorized_overrides:
            diagnostics.append(
                ValidationMessage(
                    level="error",
                    code="RESOURCE_SCOPE_OVERRIDE_NOT_AUTHORIZED",
                    subject_id=pool.id,
                    entity_refs=[pool.id, *unauthorized_overrides],
                    message=(
                        f"资源池“{pool.label}”的覆盖工点不在获准集合内："
                        f"{', '.join(unauthorized_overrides)}。"
                    ),
                )
            )
            continue

        if pool.scope_mode == "PROJECT_SHARED":
            if pool.workpoint_overrides:
                diagnostics.append(
                    ValidationMessage(
                        level="error",
                        code="RESOURCE_SCOPE_SHARED_OVERRIDE_UNSUPPORTED",
                        subject_id=pool.id,
                        entity_refs=[pool.id, *sorted(override_by_workpoint)],
                        message=f"项目共享资源池“{pool.label}”不能混用工点数量覆盖。",
                    )
                )
                continue
            quantity = int(pool.quantity or 0)
            max_quantity = max(quantity, int(pool.max_quantity if pool.max_quantity is not None else quantity))
            effective_pools.append(
                _effective_pool(
                    pool,
                    effective_pool_id=pool.id,
                    workpoint_id=None,
                    eligible_workpoint_ids=authorized,
                    enabled=pool.enabled,
                    quantity=quantity,
                    max_quantity=max_quantity,
                    inheritance_source="global",
                )
            )
            continue

        for workpoint_id in authorized:
            override = override_by_workpoint.get(workpoint_id)
            has_override = bool(
                override
                and any(
                    value is not None
                    for value in (override.enabled, override.quantity, override.max_quantity)
                )
            )
            enabled = override.enabled if override and override.enabled is not None else pool.enabled
            quantity = int(
                override.quantity
                if override and override.quantity is not None
                else (pool.quantity or 0)
            )
            raw_max_quantity = (
                override.max_quantity
                if override and override.max_quantity is not None
                else pool.max_quantity
            )
            max_quantity = max(quantity, int(raw_max_quantity if raw_max_quantity is not None else quantity))
            inheritance_source: InheritanceSource = "overridden" if has_override else "inherited"
            if inheritance_source == "inherited":
                inherited_workpoint_count += 1
            effective_pools.append(
                _effective_pool(
                    pool,
                    effective_pool_id=f"{pool.id}::workpoint::{workpoint_id}",
                    workpoint_id=workpoint_id,
                    eligible_workpoint_ids=(workpoint_id,),
                    enabled=enabled,
                    quantity=quantity,
                    max_quantity=max_quantity,
                    inheritance_source=inheritance_source,
                )
            )

    return EffectiveResourceResolution(
        pools=tuple(
            sorted(
                effective_pools,
                key=lambda item: (
                    item.resource_type,
                    item.source_pool_id,
                    item.workpoint_id or "",
                    item.effective_pool_id,
                ),
            )
        ),
        diagnostics=tuple(diagnostics),
        bridge_workpoint_ids=bridge_workpoint_ids,
        inherited_workpoint_count=inherited_workpoint_count,
    )


def _effective_pool(
    pool: ResourcePool,
    *,
    effective_pool_id: str,
    workpoint_id: str | None,
    eligible_workpoint_ids: tuple[str, ...],
    enabled: bool,
    quantity: int,
    max_quantity: int,
    inheritance_source: InheritanceSource,
) -> EffectiveResourcePool:
    return EffectiveResourcePool(
        effective_pool_id=effective_pool_id,
        source_pool_id=pool.id,
        resource_type=pool.type,
        label=pool.label,
        resource_mode=pool.resource_mode,
        scope_mode=pool.scope_mode,
        workpoint_id=workpoint_id,
        eligible_workpoint_ids=eligible_workpoint_ids,
        enabled=enabled,
        quantity=quantity,
        max_quantity=max_quantity,
        calendar_id=pool.calendar_id,
        inheritance_source=inheritance_source,
        cost_type=pool.cost_type,
        incremental_unit_cost=pool.incremental_unit_cost,
        billing_period_days=pool.billing_period_days,
        same_structure_resource_binding=pool.same_structure_resource_binding,
        parallel_rule_description=pool.parallel_rule_description,
    )
