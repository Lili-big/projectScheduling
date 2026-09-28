from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from .contracts import (
    LogicRule,
    MilestoneConstraint,
    ProcessTemplate,
    ResourcePool,
    ScenarioInput,
    UpperStructureLogicRule,
)
from .process_library_defaults import upgrade_process_library
from .local_paths import LOCAL_DATA_ROOT, REPOSITORY_ROOT, state_path


PROJECT_ROOT = REPOSITORY_ROOT
LOCAL_DATA_DIR = LOCAL_DATA_ROOT
LOCAL_SCENARIO_CONFIG_PATH = state_path("scheduler-config.json")
BUNDLED_SCENARIO_CONFIG_PATH = Path(__file__).resolve().with_name("default_scenario_config.json")
SCHEMA_VERSION = "local-scheduler-config/v5"

ModelT = TypeVar("ModelT", bound=BaseModel)


class LocalScenarioConfigError(RuntimeError):
    pass


def apply_local_scenario_config(
    scenario: ScenarioInput,
    *,
    path: Path = LOCAL_SCENARIO_CONFIG_PATH,
) -> ScenarioInput:
    return apply_scenario_config(scenario, path=path, persist_resource_cleanup=True)


def apply_bundled_scenario_config(
    scenario: ScenarioInput,
    *,
    path: Path = BUNDLED_SCENARIO_CONFIG_PATH,
) -> ScenarioInput:
    return apply_scenario_config(scenario, path=path)


def apply_scenario_config(
    scenario: ScenarioInput,
    *,
    path: Path,
    persist_resource_cleanup: bool = False,
) -> ScenarioInput:
    config = _read_config(path)
    if scenario.engineering_domain == "pavement":
        profiles = config.get("pavement_profiles", {})
        if not isinstance(profiles, dict): raise LocalScenarioConfigError("路面项目配置必须是对象。")
        profile = profiles.get(scenario.project.project_id)
        if profile is None: return scenario
        if not isinstance(profile, dict): raise LocalScenarioConfigError("路面配置内容无效。")
        try:
            restored = ScenarioInput.model_validate({**scenario.model_dump(mode="json"), **profile})
            if profile.get("project_start_date"):
                from datetime import date
                restored.project.start_date = date.fromisoformat(profile["project_start_date"])
            validate_pavement_library(restored.process_library)
            from .scheduling.domain.resource_scope import normalize_pavement_resource_pools
            restored.resource_pools, errors = normalize_pavement_resource_pools(restored.resource_pools, restored.process_library, legacy=True, require_transfer=False)
            if errors:
                raise ValueError("；".join(e.message for e in errors))
            return restored
        except (ValueError, TypeError) as exc:
            raise LocalScenarioConfigError(f"路面配置校验失败：{exc}") from exc
    if not config:
        return scenario

    next_scenario = scenario.model_copy(deep=True)
    resource_cleanup_payload: list[dict[str, Any]] | None = None

    if "process_library" in config:
        saved_processes = _validate_list(config["process_library"], ProcessTemplate, "process_library")
        next_scenario.process_library = upgrade_process_library(saved_processes, next_scenario.process_library)

    if "logic_rules" in config:
        saved_logic_rules = _validate_list(config["logic_rules"], LogicRule, "logic_rules")
        next_scenario.logic_rules = _merge_by_id(next_scenario.logic_rules, saved_logic_rules)

    if "upper_structure_logic_rules" in config:
        saved_upper_logic_rules = _validate_list(
            config["upper_structure_logic_rules"],
            UpperStructureLogicRule,
            "upper_structure_logic_rules",
        )
        next_scenario.upper_structure_logic_rules = _merge_by_id(
            next_scenario.upper_structure_logic_rules,
            saved_upper_logic_rules,
        )

    if "resource_pools" in config:
        saved_resource_pools = _validate_list(config["resource_pools"], ResourcePool, "resource_pools")
        _ensure_unique_pool_ids(saved_resource_pools)
        workpoint_ids = [
            bridge.id
            for bridge in next_scenario.project.bridges
            if bridge.workpoint_type == "bridge"
        ]
        # Merge before expanding legacy exclusive pools. Otherwise a legacy pool
        # whose id matches a bundled default would be materialized under new ids
        # and the stale bundled record would incorrectly survive beside it.
        merged_resource_pools = _merge_resource_pools(next_scenario.resource_pools, saved_resource_pools)
        normalized_resource_pools = _normalize_resource_pools(
            merged_resource_pools,
            workpoint_ids=workpoint_ids,
        )
        next_scenario.resource_pools = normalized_resource_pools
        normalized_payload = _dump_models(normalized_resource_pools)
        if persist_resource_cleanup and config["resource_pools"] != normalized_payload:
            resource_cleanup_payload = normalized_payload

    if "milestones" in config:
        saved_milestones = _validate_list(config["milestones"], MilestoneConstraint, "milestones")
        next_scenario.milestones = _merge_by_id(next_scenario.milestones, saved_milestones)

    if resource_cleanup_payload is not None:
        config["resource_pools"] = resource_cleanup_payload
        _write_config(config, path)

    return next_scenario


def load_process_library(
    fallback: list[ProcessTemplate],
    *,
    path: Path = LOCAL_SCENARIO_CONFIG_PATH,
) -> list[ProcessTemplate]:
    config = _read_config(path)
    if "process_library" not in config:
        return upgrade_process_library(fallback, fallback)
    saved_processes = _validate_list(config["process_library"], ProcessTemplate, "process_library")
    return upgrade_process_library(saved_processes, fallback)


def save_process_library(
    process_library: list[ProcessTemplate],
    *,
    path: Path = LOCAL_SCENARIO_CONFIG_PATH,
) -> list[ProcessTemplate]:
    if not process_library:
        raise LocalScenarioConfigError("工艺工效库保存内容不能为空。")

    upgraded = upgrade_process_library(process_library)
    config = _read_config(path)
    config["process_library"] = _dump_models(upgraded)
    _write_config(config, path)
    return load_process_library(upgraded, path=path)


def save_local_scenario_config(
    *,
    process_library: list[ProcessTemplate],
    logic_rules: list[LogicRule],
    upper_structure_logic_rules: list[UpperStructureLogicRule],
    resource_pools: list[ResourcePool],
    milestones: list[MilestoneConstraint] | None = None,
    path: Path = LOCAL_SCENARIO_CONFIG_PATH,
) -> dict[str, list[Any]]:
    if not process_library:
        raise LocalScenarioConfigError("工艺工效库保存内容不能为空。")
    if not logic_rules:
        raise LocalScenarioConfigError("工艺逻辑保存内容不能为空。")
    config = _read_config(path)
    upgraded_process_library = upgrade_process_library(process_library)
    normalized_resource_pools = _normalize_resource_pools(resource_pools, for_save=True)
    config.update(
        {
            "process_library": _dump_models(upgraded_process_library),
            "logic_rules": _dump_models(logic_rules),
            "upper_structure_logic_rules": _dump_models(upper_structure_logic_rules),
            "resource_pools": _dump_models(normalized_resource_pools),
            "milestones": _dump_models(milestones or []),
        }
    )
    _write_config(config, path)
    return {
        "process_library": upgraded_process_library,
        "logic_rules": logic_rules,
        "upper_structure_logic_rules": upper_structure_logic_rules,
        "resource_pools": normalized_resource_pools,
        "milestones": milestones or [],
    }


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalScenarioConfigError(f"本地配置 JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise LocalScenarioConfigError("本地配置 JSON 顶层必须是对象。")
    return {key: value for key, value in data.items() if key != "schema_version"}


def _write_config(config: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, **config}
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise LocalScenarioConfigError(f"本地配置写入失败：{exc}") from exc


def _validate_list(value: Any, model: type[ModelT], field_name: str) -> list[ModelT]:
    if not isinstance(value, list):
        raise LocalScenarioConfigError(f"本地配置字段 {field_name} 必须是数组。")
    try:
        return [model.model_validate(item) for item in value]
    except ValidationError as exc:
        raise LocalScenarioConfigError(f"本地配置字段 {field_name} 校验失败：{exc}") from exc


def _merge_by_id(defaults: list[ModelT], saved: list[ModelT]) -> list[ModelT]:
    saved_by_id = {str(item.id): item for item in saved}  # type: ignore[attr-defined]
    merged: list[ModelT] = []
    used_ids: set[str] = set()
    for default in defaults:
        item_id = str(default.id)  # type: ignore[attr-defined]
        merged.append(saved_by_id.get(item_id, default))
        used_ids.add(item_id)
    merged.extend(item for item in saved if str(item.id) not in used_ids)  # type: ignore[attr-defined]
    return merged


def _merge_resource_pools(defaults: list[ResourcePool], saved: list[ResourcePool]) -> list[ResourcePool]:
    saved_by_id = {pool.id: pool for pool in saved}
    migrated_by_source_id: dict[str, list[ResourcePool]] = {}
    marker = "::workpoint::"
    for pool in saved:
        source_id, separator, encoded_workpoint_id = pool.id.partition(marker)
        if (
            separator
            and pool.scope_mode == "WORKPOINT_EXCLUSIVE"
            and pool.workpoint_id == encoded_workpoint_id
        ):
            migrated_by_source_id.setdefault(source_id, []).append(pool)

    merged: list[ResourcePool] = []
    used_ids: set[str] = set()
    for default in defaults:
        if default.id in saved_by_id:
            merged.append(saved_by_id[default.id])
            used_ids.add(default.id)
            continue
        migrated = migrated_by_source_id.get(default.id)
        if migrated:
            merged.extend(migrated)
            used_ids.update(pool.id for pool in migrated)
            continue
        merged.append(default)
    merged.extend(pool for pool in saved if pool.id not in used_ids)
    return merged


def _dump_models(items: Iterable[BaseModel]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


def _normalize_resource_pools(
    items: Iterable[ResourcePool],
    *,
    workpoint_ids: Iterable[str] | None = None,
    for_save: bool = False,
) -> list[ResourcePool]:
    source = [ResourcePool.model_validate(item.model_dump(mode="python")) for item in items]
    _ensure_unique_pool_ids(source)

    known_workpoint_ids = None if workpoint_ids is None else sorted(set(workpoint_ids))
    normalized: list[ResourcePool] = []
    for pool in source:
        if pool.scope_mode == "WORKPOINT_EXCLUSIVE" and pool.workpoint_id is None:
            normalized.extend(
                _materialize_legacy_exclusive_pool(
                    pool,
                    known_workpoint_ids=known_workpoint_ids,
                )
            )
        else:
            normalized.append(pool)

    normalized = [pool for pool in normalized if pool.scope_mode == "WORKPOINT_EXCLUSIVE"]
    _ensure_unique_pool_ids(normalized)
    _ensure_unique_local_resource_keys(normalized)
    return normalized


def _materialize_legacy_exclusive_pool(
    pool: ResourcePool,
    *,
    known_workpoint_ids: list[str] | None,
) -> list[ResourcePool]:
    if known_workpoint_ids is None:
        raise _migration_blocked(pool.id, "保存时缺少权威桥梁工点集合，无法证明 legacy 独享池可无损展开")

    target_ids = (
        known_workpoint_ids
        if pool.authorized_workpoint_ids is None
        else list(pool.authorized_workpoint_ids)
    )
    if not target_ids:
        raise _migration_blocked(pool.id, "legacy 独享池的工点范围为空")

    unknown_ids = sorted(set(target_ids) - set(known_workpoint_ids))
    if unknown_ids:
        raise _migration_blocked(pool.id, f"包含未知工点：{', '.join(unknown_ids)}")

    override_by_workpoint = {override.workpoint_id: override for override in pool.workpoint_overrides}
    outside_override_ids = sorted(set(override_by_workpoint) - set(target_ids))
    if outside_override_ids:
        raise _migration_blocked(
            pool.id,
            f"覆盖项不在获准工点范围：{', '.join(outside_override_ids)}",
        )

    migrated: list[ResourcePool] = []
    for workpoint_id in sorted(target_ids):
        override = override_by_workpoint.get(workpoint_id)
        quantity = pool.quantity if override is None or override.quantity is None else override.quantity
        max_quantity = pool.max_quantity if override is None or override.max_quantity is None else override.max_quantity
        enabled = pool.enabled if override is None or override.enabled is None else override.enabled
        payload = pool.model_dump(mode="python")
        payload.update(
            {
                "id": f"{pool.id}::workpoint::{workpoint_id}",
                "scope_mode": "WORKPOINT_EXCLUSIVE",
                "workpoint_id": workpoint_id,
                "authorized_workpoint_ids": None,
                "workpoint_overrides": [],
                "quantity": quantity,
                "max_quantity": max_quantity,
                "enabled": enabled,
            }
        )
        migrated.append(ResourcePool.model_validate(payload))
    return migrated


def _ensure_unique_pool_ids(items: list[ResourcePool]) -> None:
    pool_ids = [pool.id for pool in items]
    duplicate_ids = sorted({pool_id for pool_id in pool_ids if pool_ids.count(pool_id) > 1})
    if duplicate_ids:
        raise LocalScenarioConfigError(f"资源池 ID 重复：{', '.join(duplicate_ids)}")


def _ensure_unique_local_resource_keys(items: list[ResourcePool]) -> None:
    local_keys = [
        (pool.workpoint_id, pool.type)
        for pool in items
        if pool.scope_mode == "WORKPOINT_EXCLUSIVE" and pool.workpoint_id is not None
    ]
    duplicate_keys = sorted({key for key in local_keys if local_keys.count(key) > 1})
    if duplicate_keys:
        labels = [f"{workpoint_id}/{resource_type}" for workpoint_id, resource_type in duplicate_keys]
        raise LocalScenarioConfigError(f"工点资源键重复：{', '.join(labels)}")


def _migration_blocked(pool_id: str, reason: str) -> LocalScenarioConfigError:
    return LocalScenarioConfigError(f"RESOURCE_POOL_MIGRATION_BLOCKED [{pool_id}]：{reason}")


def validate_pavement_library(processes):
    import math
    from .process_library_defaults import PAVEMENT_PROCESSES
    if {p.component_type for p in processes} != set(PAVEMENT_PROCESSES):
        raise ValueError("路面工效库必须包含碎石、水稳、沥青三类工艺。")
    if len({p.id for p in processes}) != len(processes):
        raise ValueError("工艺ID重复。")
    for process in processes:
        if process.resource_type != PAVEMENT_PROCESSES[process.component_type][1]:
            raise ValueError("工艺与机组类别不匹配。")
        if len({o.id for o in process.productivity_options}) != len(process.productivity_options):
            raise ValueError("工效方案ID重复。")
        for option in process.productivity_options:
            if not math.isfinite(option.productivity_value):
                raise ValueError("工效必须是有限正数。")
            if option.productivity_unit not in {"m/天", "m2/天", "m3/天", "t/天"} or option.duration_method != "units_per_day" or option.quantity_source != "quantity":
                raise ValueError("路面工效必须为每套机组的 m/m2/m3/t 每天。")


def save_pavement_profile(scenario: ScenarioInput, *, path: Path = LOCAL_SCENARIO_CONFIG_PATH):
    validate_pavement_library(scenario.process_library)
    from .scheduling.domain.resource_scope import normalize_pavement_resource_pools
    pools, errors = normalize_pavement_resource_pools(scenario.resource_pools, scenario.process_library)
    if errors:
        raise ValueError("；".join(e.message for e in errors))
    scenario = scenario.model_copy(update={"resource_pools": pools})
    config = _read_config(path)
    profiles = config.setdefault("pavement_profiles", {})
    if not isinstance(profiles, dict): raise LocalScenarioConfigError("路面项目配置必须是对象。")
    profiles[scenario.project.project_id] = scenario.model_dump(mode="json", include={
        "process_library", "task_overrides", "resource_pools", "pavement_settings", "project_data_version_id"})
    profiles[scenario.project.project_id]["project_start_date"] = scenario.project.start_date.isoformat()
    _write_config(config, path)
    return scenario
