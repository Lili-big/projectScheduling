from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from .models import LogicRule, ProcessTemplate, ResourcePool, ScenarioInput, UpperStructureLogicRule
from .process_library_defaults import upgrade_process_library


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATA_DIR = PROJECT_ROOT / ".local-data"
LOCAL_SCENARIO_CONFIG_PATH = LOCAL_DATA_DIR / "scheduler-config.json"
SCHEMA_VERSION = "local-scheduler-config/v1"

ModelT = TypeVar("ModelT", bound=BaseModel)


class LocalScenarioConfigError(RuntimeError):
    pass


def apply_local_scenario_config(
    scenario: ScenarioInput,
    *,
    path: Path = LOCAL_SCENARIO_CONFIG_PATH,
) -> ScenarioInput:
    config = _read_config(path)
    if not config:
        return scenario

    next_scenario = scenario.model_copy(deep=True)

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
        next_scenario.resource_pools = _merge_by_id(next_scenario.resource_pools, saved_resource_pools)

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
    path: Path = LOCAL_SCENARIO_CONFIG_PATH,
) -> dict[str, list[Any]]:
    if not process_library:
        raise LocalScenarioConfigError("工艺工效库保存内容不能为空。")
    if not logic_rules:
        raise LocalScenarioConfigError("工艺逻辑保存内容不能为空。")
    if not resource_pools:
        raise LocalScenarioConfigError("资源配置保存内容不能为空。")

    config = _read_config(path)
    upgraded_process_library = upgrade_process_library(process_library)
    config.update(
        {
            "process_library": _dump_models(upgraded_process_library),
            "logic_rules": _dump_models(logic_rules),
            "upper_structure_logic_rules": _dump_models(upper_structure_logic_rules),
            "resource_pools": _dump_models(resource_pools),
        }
    )
    _write_config(config, path)
    return {
        "process_library": upgraded_process_library,
        "logic_rules": logic_rules,
        "upper_structure_logic_rules": upper_structure_logic_rules,
        "resource_pools": resource_pools,
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
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


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


def _dump_models(items: Iterable[BaseModel]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]
