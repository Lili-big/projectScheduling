from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...contracts import ProjectBridge, ResourcePool, ResourceScopeMode, ValidationMessage


RESOURCE_SCOPE_RULE_VERSION = "workpoint-resource-scope/v1"
InheritanceSource = Literal["global", "inherited", "overridden"]

PAVEMENT_SHARED_RESOURCE_TYPE = "pavement_paving_crew"


def pavement_pool_has_capacity(pool: ResourcePool) -> bool:
    """Use the same quantities/enabled overrides as scope resolution, before master loading."""
    if pool.scope_mode == "PROJECT_SHARED" or pool.workpoint_id is not None:
        return pool.enabled and (pool.quantity or 0) > 0
    overrides = {o.workpoint_id: o for o in pool.workpoint_overrides}
    ids = pool.authorized_workpoint_ids
    if ids is None:
        if pool.enabled and (pool.quantity or 0) > 0:
            return True
        ids = list(overrides)
    return any(
        (overrides[wid].enabled if wid in overrides and overrides[wid].enabled is not None else pool.enabled)
        and (overrides[wid].quantity if wid in overrides and overrides[wid].quantity is not None else (pool.quantity or 0)) > 0
        for wid in ids
    )


def normalize_pavement_resource_pools(pools, processes, *, legacy=False, require_transfer=True):
    """Resolve explicit process IDs; legacy empty lists retain only their original category."""
    from ...process_library_defaults import PAVEMENT_PROCESSES
    known = {p.id: p for p in processes if p.component_type in PAVEMENT_PROCESSES}
    types = {v[1] for v in PAVEMENT_PROCESSES.values()}
    normalized, diagnostics, seen = [], [], set()
    for pool in pools:
        def error(text, code="PAVEMENT_REFERENCE_INVALID"):
            diagnostics.append(ValidationMessage(level="error", code=code, message=text, subject_id=pool.id))
        if pool.id in seen:
            error("机组ID重复。")
        seen.add(pool.id)
        if not pool.label.strip():
            error("请填写机组名称。")
        if pool.type not in types | {PAVEMENT_SHARED_RESOURCE_TYPE} or pool.resource_mode != "LIMITED":
            error("路面机组必须为固定数量的摊铺机组。")
        ids = list(dict.fromkeys(pool.compatible_process_ids))
        if not ids and legacy and pool.type in types:
            ids = [p.id for p in known.values() if p.resource_type == pool.type]
        if set(ids) - known.keys():
            error("机组适用工艺引用无效，请重新选择当前工艺库中的工艺。")
        if pavement_pool_has_capacity(pool):
            if not ids:
                error("可用机组至少选择一种适用工艺。")
            if require_transfer and pool.transfer_days is None:
                error("请确认可用机组跨段转场天数，零天也需填写。", "PAVEMENT_TRANSFER_UNCONFIRMED")
        normalized.append(pool.model_copy(update={"compatible_process_ids": ids}))
    return normalized, diagnostics


def pavement_resource_matches(task, resource) -> bool:
    from ...process_library_defaults import PAVEMENT_PROCESSES
    context = task.pavement_context
    if not context or context.task_kind != "construction" or not resource.enabled or task.bridge_id not in resource.eligible_workpoint_ids:
        return False
    if resource.compatible_process_ids is not None:
        return bool(context.process_id and context.process_id in resource.compatible_process_ids)
    expected = PAVEMENT_PROCESSES.get(task.component_type)
    return bool(expected and resource.type == expected[1])


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
    transfer_days: int | None = None


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
    engineering_domain: str = "bridge",
) -> EffectiveResourceResolution:
    """Resolve the single authoritative resource configuration for scheduling.

    The resolver only reads explicit contract fields and the current bridge workpoint
    identities. It never interprets names, identifier shapes, quantities, or resource
    types to infer scope.
    """

    bridge_workpoint_ids = tuple(
        sorted({bridge.id for bridge in bridges if bridge.workpoint_type == engineering_domain})
    )
    valid_workpoint_ids = set(bridge_workpoint_ids)
    diagnostics: list[ValidationMessage] = []
    effective_pools: list[EffectiveResourcePool] = []
    inherited_workpoint_count = 0

    pools_by_id: dict[str, list[ResourcePool]] = {}
    for pool in resource_pools:
        pools_by_id.setdefault(pool.id, []).append(pool)
    duplicate_pool_ids = {pool_id for pool_id, pools in pools_by_id.items() if len(pools) > 1}
    for pool_id in sorted(duplicate_pool_ids):
        diagnostics.append(
            ValidationMessage(
                level="error",
                code="RESOURCE_SCOPE_DUPLICATE_POOL_ID",
                subject_id=pool_id,
                entity_refs=[pool_id],
                message=f"资源池 ID {pool_id} 重复，无法确定资源池身份。",
            )
        )

    direct_local_by_key: dict[tuple[str, str], list[ResourcePool]] = {}
    for pool in resource_pools:
        if pool.scope_mode == "WORKPOINT_EXCLUSIVE" and pool.workpoint_id is not None:
            direct_local_by_key.setdefault((pool.workpoint_id, pool.type), []).append(pool)
    duplicate_local_keys = {
        key: pools for key, pools in direct_local_by_key.items() if len(pools) > 1
    }
    duplicate_local_pool_ids: set[str] = set()
    for (workpoint_id, resource_type), pools in sorted(duplicate_local_keys.items()):
        pool_ids = sorted(pool.id for pool in pools)
        duplicate_local_pool_ids.update(pool_ids)
        diagnostics.append(
            ValidationMessage(
                level="error",
                code="RESOURCE_SCOPE_DUPLICATE_LOCAL_KEY",
                subject_id=f"{workpoint_id}:{resource_type}",
                entity_refs=[workpoint_id, resource_type, *pool_ids],
                message=(
                    f"工点 {workpoint_id} 的资源类型 {resource_type} 存在多条本地记录："
                    f"{', '.join(pool_ids)}。"
                ),
            )
        )

    for pool in sorted(resource_pools, key=lambda item: item.id):
        if pool.id in duplicate_pool_ids or pool.id in duplicate_local_pool_ids:
            continue

        if pool.scope_mode == "WORKPOINT_EXCLUSIVE" and pool.workpoint_id is not None:
            if pool.workpoint_id not in valid_workpoint_ids:
                diagnostics.append(
                    ValidationMessage(
                        level="error",
                        code="RESOURCE_SCOPE_UNKNOWN_WORKPOINT",
                        subject_id=pool.id,
                        entity_refs=[pool.id, pool.workpoint_id],
                        message=(
                            f"本地资源池“{pool.label}”引用了不属于当前项目主数据版本"
                            f" {project_data_version_id or 'unknown'} 的桥梁工点：{pool.workpoint_id}。"
                        ),
                    )
                )
                continue
            quantity = int(pool.quantity or 0)
            max_quantity = max(
                quantity,
                int(pool.max_quantity if pool.max_quantity is not None else quantity),
            )
            effective_pools.append(
                _effective_pool(
                    pool,
                    effective_pool_id=pool.id,
                    workpoint_id=pool.workpoint_id,
                    eligible_workpoint_ids=(pool.workpoint_id,),
                    enabled=pool.enabled,
                    quantity=quantity,
                    max_quantity=max_quantity,
                    inheritance_source="global",
                )
            )
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
                key=lambda item: item.effective_pool_id,
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
        transfer_days=pool.transfer_days,
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
