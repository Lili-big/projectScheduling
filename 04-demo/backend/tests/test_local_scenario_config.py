from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.local_scenario_config as local_config_module  # noqa: E402
from app.contracts import ResourcePool  # noqa: E402
from app.local_scenario_config import (  # noqa: E402
    LocalScenarioConfigError,
    SCHEMA_VERSION,
    apply_bundled_scenario_config,
    apply_local_scenario_config,
    save_local_scenario_config,
)
from app.scenario import generate_schedule_input_from_scenario  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402


def _local_pool(
    scenario,
    *,
    pool_id: str = "local-cap",
    resource_type: str = "cap_team",
    workpoint_id: str | None = None,
    quantity: int = 1,
    max_quantity: int = 3,
    enabled: bool = True,
    resource_mode: str = "LIMITED",
) -> ResourcePool:
    target_workpoint_id = workpoint_id or scenario.project.bridges[0].id
    return ResourcePool(
        id=pool_id,
        type=resource_type,
        label=f"{target_workpoint_id} {resource_type}",
        resource_mode=resource_mode,
        scope_mode="WORKPOINT_EXCLUSIVE",
        workpoint_id=target_workpoint_id,
        quantity=quantity,
        max_quantity=max_quantity,
        enabled=enabled,
        authorized_workpoint_ids=None,
        workpoint_overrides=[],
    )


def _shared_pool(*, pool_id: str = "shared-cap", quantity: int = 2) -> ResourcePool:
    return ResourcePool(
        id=pool_id,
        type="cap_team",
        label="历史共享承台班组",
        scope_mode="PROJECT_SHARED",
        quantity=quantity,
        max_quantity=max(quantity, 4),
    )


def _save_scenario(path: Path, scenario, resource_pools: list[ResourcePool]) -> dict[str, list[object]]:
    return save_local_scenario_config(
        process_library=scenario.process_library,
        logic_rules=scenario.logic_rules,
        upper_structure_logic_rules=scenario.upper_structure_logic_rules,
        resource_pools=resource_pools,
        milestones=scenario.milestones,
        path=path,
    )


def test_missing_local_config_uses_default_scenario_without_shared_resources(tmp_path: Path) -> None:
    scenario = default_scenario()

    loaded = apply_local_scenario_config(scenario, path=tmp_path / "missing.json")

    assert loaded.process_library[0].id == scenario.process_library[0].id
    assert loaded.logic_rules[0].id == scenario.logic_rules[0].id
    assert loaded.resource_pools == []


def test_bundled_config_clears_code_default_shared_resources() -> None:
    scenario = default_scenario()
    scenario.resource_pools = [_shared_pool()]

    loaded = apply_bundled_scenario_config(scenario)

    assert loaded.resource_pools == []


def test_local_config_save_and_reload_round_trips_local_resources_and_allows_empty(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config.json"
    scenario = default_scenario()
    scenario.process_library[0].productivity_options[0].productivity_value = 6
    scenario.process_library[0].productivity_value = 6
    scenario.logic_rules[0].lag_days = 2
    scenario.upper_structure_logic_rules[0].lag_days = 3
    scenario.milestones[0].target_date = date(2026, 7, 30)
    local = _local_pool(scenario, quantity=1, max_quantity=3)

    saved = _save_scenario(path, scenario, [local, _shared_pool()])
    loaded = apply_local_scenario_config(default_scenario(), path=path)

    assert loaded.process_library[0].productivity_value == 6
    assert loaded.logic_rules[0].lag_days == 2
    assert loaded.upper_structure_logic_rules[0].lag_days == 3
    assert [(pool.id, pool.max_quantity) for pool in loaded.resource_pools] == [(local.id, 3)]
    assert saved["resource_pools"] == [local]
    assert loaded.milestones[0].target_date == date(2026, 7, 30)

    empty_saved = _save_scenario(path, scenario, [])
    assert empty_saved["resource_pools"] == []
    assert json.loads(path.read_text(encoding="utf-8"))["resource_pools"] == []


def test_old_subset_keeps_new_non_resource_defaults_and_removes_shared_pool(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config.json"
    scenario = default_scenario()
    process_payload = scenario.process_library[0].model_dump(mode="json")
    process_payload["productivity_value"] = 7
    process_payload["productivity_options"][0]["productivity_value"] = 7
    logic_payload = scenario.logic_rules[0].model_dump(mode="json")
    logic_payload["lag_days"] = 5
    path.write_text(
        json.dumps(
            {
                "schema_version": "local-scheduler-config/v1",
                "process_library": [process_payload],
                "logic_rules": [logic_payload],
                "upper_structure_logic_rules": [],
                "resource_pools": [_shared_pool().model_dump(mode="json")],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(default_scenario(), path=path)
    process_by_id = {process.id: process for process in loaded.process_library}
    logic_by_id = {rule.id: rule for rule in loaded.logic_rules}

    assert process_by_id[scenario.process_library[0].id].productivity_value == 7
    assert "bridge_deck_system_standard" in process_by_id
    assert logic_by_id[scenario.logic_rules[0].id].lag_days == 5
    assert len(loaded.logic_rules) > 1
    assert loaded.resource_pools == []
    assert loaded.milestones[0].target_date == scenario.milestones[0].target_date


@pytest.mark.parametrize("pool_state", ["missing", "disabled", "zero", "unlimited"])
def test_abutment_local_pool_current_availability_uses_blocking_or_explicit_unlimited_compatibility(
    pool_state: str,
) -> None:
    scenario = default_scenario()
    if pool_state != "missing":
        scenario.resource_pools = [
            _local_pool(
                scenario,
                pool_id=f"test-abutment-{pool_state}",
                resource_type="abutment_team",
                resource_mode="UNLIMITED" if pool_state == "unlimited" else "LIMITED",
                quantity=0 if pool_state == "zero" else 1,
                max_quantity=1,
                enabled=pool_state != "disabled",
            )
        ]

    generated = generate_schedule_input_from_scenario(scenario)
    abutment_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "abutment_body"]

    assert abutment_tasks
    allocation_errors = [
        message
        for message in generated.validation
        if message.code == "RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE"
        and message.subject_id in {task.id for task in abutment_tasks}
    ]
    if pool_state == "unlimited":
        assert all(task.compatible_resource_types == [] for task in abutment_tasks)
        assert allocation_errors == []
        assert any(message.level == "warning" and "默认充足" in message.message for message in generated.validation)
    else:
        assert all(task.compatible_resource_types == ["abutment_team"] for task in abutment_tasks)
        assert len(allocation_errors) == len(abutment_tasks)


def test_v1_default_shared_pool_is_removed_and_config_is_rewritten_idempotently(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v1.json"
    scenario = default_scenario()
    legacy_pool = _shared_pool().model_dump(mode="json")
    for field in ("scope_mode", "workpoint_id", "authorized_workpoint_ids", "workpoint_overrides"):
        legacy_pool.pop(field, None)
    legacy_pool["legacy_extension"] = {"remove": "with-shared-record"}
    path.write_text(
        json.dumps(
            {
                "schema_version": "local-scheduler-config/v1",
                "resource_pools": [legacy_pool],
                "future_extension": {"keep": True},
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(scenario, path=path)
    first_saved = path.read_text(encoding="utf-8")
    saved_payload = json.loads(first_saved)

    assert loaded.resource_pools == []
    assert saved_payload["schema_version"] == SCHEMA_VERSION
    assert saved_payload["resource_pools"] == []
    assert saved_payload["future_extension"] == {"keep": True}

    reloaded = apply_local_scenario_config(scenario, path=path)
    assert reloaded.resource_pools == []
    assert path.read_text(encoding="utf-8") == first_saved


def test_explicit_shared_scope_and_unknown_pool_fields_are_removed(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v2.json"
    shared = _shared_pool().model_dump(mode="json")
    shared["unknown_nested_field"] = "removed-with-record"
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v2", "resource_pools": [shared]}),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(default_scenario(), path=path)

    assert loaded.resource_pools == []
    assert json.loads(path.read_text(encoding="utf-8"))["resource_pools"] == []


def test_legacy_exclusive_pool_is_losslessly_materialized_per_workpoint_and_saves_idempotently(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scheduler-config-v2.json"
    scenario = default_scenario()
    scenario.project.bridges.append(
        scenario.project.bridges[0].model_copy(deep=True, update={"id": "B2", "name": "契约迁移测试二号桥"})
    )
    workpoint_ids = [bridge.id for bridge in scenario.project.bridges[:2]]
    legacy_pool = _local_pool(scenario).model_dump(mode="json")
    legacy_pool.update(
        {
            "scope_mode": "WORKPOINT_EXCLUSIVE",
            "workpoint_id": None,
            "authorized_workpoint_ids": list(reversed(workpoint_ids)),
            "workpoint_overrides": [{"workpoint_id": workpoint_ids[1], "quantity": 3, "max_quantity": 5}],
            "quantity": 1,
            "max_quantity": 4,
        }
    )
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v2", "resource_pools": [legacy_pool]}),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(scenario, path=path)
    migrated = [pool for pool in loaded.resource_pools if pool.id.startswith(f"{legacy_pool['id']}::workpoint::")]

    assert [pool.workpoint_id for pool in migrated] == sorted(workpoint_ids)
    assert all(pool.scope_mode == "WORKPOINT_EXCLUSIVE" for pool in migrated)
    assert all(pool.authorized_workpoint_ids is None and pool.workpoint_overrides == [] for pool in migrated)
    by_workpoint = {pool.workpoint_id: pool for pool in migrated}
    assert (by_workpoint[workpoint_ids[0]].quantity, by_workpoint[workpoint_ids[0]].max_quantity) == (1, 4)
    assert (by_workpoint[workpoint_ids[1]].quantity, by_workpoint[workpoint_ids[1]].max_quantity) == (3, 5)

    first_saved = path.read_text(encoding="utf-8")
    reloaded = apply_local_scenario_config(scenario, path=path)
    assert [(pool.id, pool.quantity, pool.max_quantity) for pool in reloaded.resource_pools] == [
        (pool.id, pool.quantity, pool.max_quantity) for pool in loaded.resource_pools
    ]
    assert path.read_text(encoding="utf-8") == first_saved


def test_legacy_exclusive_pool_with_unknown_workpoint_blocks_without_mutating_source(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v2.json"
    scenario = default_scenario()
    legacy_pool = _local_pool(scenario).model_dump(mode="json")
    legacy_pool.update(
        {
            "scope_mode": "WORKPOINT_EXCLUSIVE",
            "workpoint_id": None,
            "authorized_workpoint_ids": ["WP-NOT-IN-PROJECT"],
            "workpoint_overrides": [],
        }
    )
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v2", "resource_pools": [legacy_pool]}),
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")

    with pytest.raises(LocalScenarioConfigError, match="RESOURCE_POOL_MIGRATION_BLOCKED"):
        apply_local_scenario_config(scenario, path=path)

    assert path.read_text(encoding="utf-8") == original


def test_same_type_shared_pools_are_all_removed(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v3.json"
    first = _shared_pool(pool_id="shared-a")
    second = _shared_pool(pool_id="shared-b", quantity=1)
    path.write_text(
        json.dumps(
            {"schema_version": "local-scheduler-config/v3", "resource_pools": [first.model_dump(mode="json"), second.model_dump(mode="json")]}
        ),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(default_scenario(), path=path)

    assert loaded.resource_pools == []
    assert json.loads(path.read_text(encoding="utf-8"))["resource_pools"] == []


def test_duplicate_resource_pool_ids_block_before_cleanup_without_mutating_source(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v3.json"
    first = _shared_pool().model_dump(mode="json")
    duplicate = {**first, "quantity": 3}
    path.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "resource_pools": [first, duplicate]}),
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")

    with pytest.raises(LocalScenarioConfigError, match="资源池 ID 重复"):
        apply_local_scenario_config(default_scenario(), path=path)

    assert path.read_text(encoding="utf-8") == original


def test_save_filters_shared_pool_with_explicit_empty_scope_to_empty_config(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v3.json"
    scenario = default_scenario()
    shared = _shared_pool()
    shared.authorized_workpoint_ids = []

    saved = _save_scenario(path, scenario, [shared])

    assert saved["resource_pools"] == []
    assert json.loads(path.read_text(encoding="utf-8"))["resource_pools"] == []


def test_cleanup_write_failure_preserves_original_file_and_removes_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "scheduler-config-v3.json"
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v3", "resource_pools": [_shared_pool().model_dump(mode="json")]}),
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")

    def fail_replace(_source: Path, _target: Path) -> Path:
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(LocalScenarioConfigError, match="本地配置写入失败"):
        apply_local_scenario_config(default_scenario(), path=path)

    assert path.read_text(encoding="utf-8") == original
    assert not path.with_suffix(f"{path.suffix}.tmp").exists()
