from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_scenario_config import (  # noqa: E402
    LocalScenarioConfigError,
    SCHEMA_VERSION,
    apply_bundled_scenario_config,
    apply_local_scenario_config,
    save_local_scenario_config,
)
from app.contracts import ResourcePool  # noqa: E402
from app.scenario import generate_schedule_input_from_scenario  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402


def test_missing_local_config_uses_default_scenario(tmp_path: Path) -> None:
    scenario = default_scenario()

    loaded = apply_local_scenario_config(scenario, path=tmp_path / "missing.json")

    assert loaded.process_library[0].id == scenario.process_library[0].id
    assert loaded.logic_rules[0].id == scenario.logic_rules[0].id
    assert loaded.resource_pools[0].id == scenario.resource_pools[0].id


def test_bundled_config_supplies_deployed_default_resource_quantities() -> None:
    loaded = apply_bundled_scenario_config(default_scenario())
    resources_by_type = {pool.type: pool for pool in loaded.resource_pools}

    assert resources_by_type["rotary_drill"].quantity == 8
    assert resources_by_type["cap_team"].quantity == 4
    assert resources_by_type["pier_body_team"].quantity == 8
    assert resources_by_type["cap_beam_team"].quantity == 6
    assert resources_by_type["cast_in_place_continuous_beam_team"].quantity == 4
    assert resources_by_type["abutment_team"].quantity == 1
    assert all(pool.scope_mode == "PROJECT_SHARED" for pool in loaded.resource_pools)
    assert all(pool.workpoint_id is None for pool in loaded.resource_pools)
    assert all(pool.authorized_workpoint_ids is None for pool in loaded.resource_pools)
    assert all(pool.workpoint_overrides == [] for pool in loaded.resource_pools)


def test_local_config_save_and_reload_round_trips_config(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config.json"
    scenario = default_scenario()
    scenario.process_library[0].productivity_options[0].productivity_value = 6
    scenario.process_library[0].productivity_value = 6
    scenario.logic_rules[0].lag_days = 2
    scenario.upper_structure_logic_rules[0].lag_days = 3
    scenario.resource_pools[0].quantity = 1
    scenario.resource_pools[0].max_quantity = 3
    scenario.milestones[0].target_date = date(2026, 7, 30)

    save_local_scenario_config(
        process_library=scenario.process_library,
        logic_rules=scenario.logic_rules,
        upper_structure_logic_rules=scenario.upper_structure_logic_rules,
        resource_pools=scenario.resource_pools,
        milestones=scenario.milestones,
        path=path,
    )
    loaded = apply_local_scenario_config(default_scenario(), path=path)

    assert loaded.process_library[0].productivity_value == 6
    assert loaded.logic_rules[0].lag_days == 2
    assert loaded.upper_structure_logic_rules[0].lag_days == 3
    assert loaded.resource_pools[0].max_quantity == 3
    assert loaded.milestones[0].target_date == date(2026, 7, 30)


def test_local_config_keeps_new_defaults_when_file_has_old_subset(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config.json"
    scenario = default_scenario()
    process_payload = scenario.process_library[0].model_dump(mode="json")
    process_payload["productivity_value"] = 7
    process_payload["productivity_options"][0]["productivity_value"] = 7
    logic_payload = scenario.logic_rules[0].model_dump(mode="json")
    logic_payload["lag_days"] = 5
    resource_payload = scenario.resource_pools[0].model_dump(mode="json")
    resource_payload["max_quantity"] = 3
    path.write_text(
        json.dumps(
            {
                "schema_version": "local-scheduler-config/v1",
                "process_library": [process_payload],
                "logic_rules": [logic_payload],
                "upper_structure_logic_rules": [],
                "resource_pools": [resource_payload],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(default_scenario(), path=path)
    process_by_id = {process.id: process for process in loaded.process_library}
    logic_by_id = {rule.id: rule for rule in loaded.logic_rules}
    resource_by_id = {pool.id: pool for pool in loaded.resource_pools}

    assert process_by_id[scenario.process_library[0].id].productivity_value == 7
    assert "bridge_deck_system_standard" in process_by_id
    assert logic_by_id[scenario.logic_rules[0].id].lag_days == 5
    assert len(loaded.logic_rules) > 1
    assert resource_by_id[scenario.resource_pools[0].id].max_quantity == 3
    assert "pool-cap" in resource_by_id
    assert loaded.milestones[0].target_date == scenario.milestones[0].target_date


@pytest.mark.parametrize("pool_state", ["missing", "disabled", "zero", "unlimited"])
def test_abutment_pool_current_availability_uses_blocking_or_explicit_unlimited_compatibility(
    pool_state: str,
) -> None:
    scenario = apply_bundled_scenario_config(default_scenario())
    scenario.resource_pools = [pool for pool in scenario.resource_pools if pool.type != "abutment_team"]
    if pool_state != "missing":
        scenario.resource_pools.append(
            ResourcePool(
                id=f"test-abutment-{pool_state}",
                type="abutment_team",
                label="Test team",
                resource_mode="UNLIMITED" if pool_state == "unlimited" else "LIMITED",
                quantity=0 if pool_state == "zero" else 1,
                max_quantity=1,
                enabled=pool_state != "disabled",
            )
        )

    generated = generate_schedule_input_from_scenario(scenario)
    abutment_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "abutment_body"]

    assert abutment_tasks
    assert all(resource.type != "abutment_team" for resource in generated.schedule_input.resources)
    allocation_errors = [
        message
        for message in generated.validation
        if message.code == "RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE"
        and message.subject_id in {task.id for task in abutment_tasks}
    ]
    if pool_state == "unlimited":
        assert all(task.compatible_resource_types == [] for task in abutment_tasks)
        assert allocation_errors == []
        assert any(
            message.level == "warning" and "默认充足" in message.message
            for message in generated.validation
        )
    else:
        assert all(task.compatible_resource_types == ["abutment_team"] for task in abutment_tasks)
        assert len(allocation_errors) == len(abutment_tasks)
        for task, message in zip(abutment_tasks, allocation_errors, strict=True):
            assert {task.id, task.bridge_id, "abutment_team"} <= set(message.entity_refs)
            if pool_state != "missing":
                assert f"test-abutment-{pool_state}" in message.entity_refs


def test_v1_resource_pools_migrate_to_project_shared_without_mutating_source(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v1.json"
    scenario = default_scenario()
    legacy_pool = scenario.resource_pools[0].model_dump(mode="json")
    for field in ("scope_mode", "authorized_workpoint_ids", "workpoint_overrides"):
        legacy_pool.pop(field, None)
    legacy_pool["quantity"] = 2
    legacy_pool["max_quantity"] = 5
    legacy_pool["enabled"] = False
    legacy_pool["calendar_id"] = "legacy-calendar"
    legacy_pool["cost_type"] = "monthly_rental"
    legacy_pool["incremental_unit_cost"] = 12345
    legacy_pool["authorized_workpoint_ids"] = [scenario.project.bridges[0].id]
    legacy_pool["legacy_extension"] = {"keep": "pool-field"}
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
    original = path.read_text(encoding="utf-8")

    loaded = apply_local_scenario_config(scenario, path=path)
    migrated = next(pool for pool in loaded.resource_pools if pool.id == legacy_pool["id"])

    assert path.read_text(encoding="utf-8") == original
    assert migrated.scope_mode == "PROJECT_SHARED"
    assert migrated.authorized_workpoint_ids == [scenario.project.bridges[0].id]
    assert migrated.workpoint_overrides == []
    assert migrated.quantity == 2
    assert migrated.max_quantity == 5
    assert migrated.enabled is False
    assert migrated.calendar_id == "legacy-calendar"
    assert migrated.cost_type == "monthly_rental"
    assert migrated.incremental_unit_cost == 12345
    assert migrated.authorized_workpoint_ids == [scenario.project.bridges[0].id]
    assert migrated.model_dump(mode="json")["legacy_extension"] == {"keep": "pool-field"}

    save_local_scenario_config(
        process_library=loaded.process_library,
        logic_rules=loaded.logic_rules,
        upper_structure_logic_rules=loaded.upper_structure_logic_rules,
        resource_pools=loaded.resource_pools,
        milestones=loaded.milestones,
        path=path,
    )
    first_saved = path.read_text(encoding="utf-8")
    saved_payload = json.loads(first_saved)
    saved_pool = next(pool for pool in saved_payload["resource_pools"] if pool["id"] == legacy_pool["id"])

    assert saved_payload["schema_version"] == SCHEMA_VERSION
    assert saved_payload["future_extension"] == {"keep": True}
    assert saved_pool["scope_mode"] == "PROJECT_SHARED"
    assert saved_pool["authorized_workpoint_ids"] == [scenario.project.bridges[0].id]
    assert saved_pool["workpoint_overrides"] == []
    assert saved_pool["quantity"] == 2
    assert saved_pool["max_quantity"] == 5
    assert saved_pool["enabled"] is False
    assert saved_pool["calendar_id"] == "legacy-calendar"
    assert saved_pool["cost_type"] == "monthly_rental"
    assert saved_pool["incremental_unit_cost"] == 12345
    assert saved_pool["authorized_workpoint_ids"] == [scenario.project.bridges[0].id]
    assert saved_pool["legacy_extension"] == {"keep": "pool-field"}

    save_local_scenario_config(
        process_library=loaded.process_library,
        logic_rules=loaded.logic_rules,
        upper_structure_logic_rules=loaded.upper_structure_logic_rules,
        resource_pools=loaded.resource_pools,
        milestones=loaded.milestones,
        path=path,
    )
    assert path.read_text(encoding="utf-8") == first_saved


def test_v2_resource_pool_scope_collections_and_unknown_fields_are_stably_preserved(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v2.json"
    scenario = default_scenario()
    pool_payload = scenario.resource_pools[0].model_dump(mode="json")
    pool_payload.update(
        {
            "scope_mode": "PROJECT_SHARED",
            "workpoint_id": None,
            "authorized_workpoint_ids": ["B1", "B1"],
            "workpoint_overrides": [
                {"workpoint_id": "B1", "quantity": 3, "max_quantity": 2},
            ],
            "unknown_nested_field": "ignored-for-forward-compatibility",
        }
    )
    path.write_text(
        json.dumps(
            {
                "schema_version": "local-scheduler-config/v2",
                "resource_pools": [pool_payload],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(scenario, path=path)
    pool = next(item for item in loaded.resource_pools if item.id == pool_payload["id"])

    assert pool.scope_mode == "PROJECT_SHARED"
    assert pool.workpoint_id is None
    assert pool.authorized_workpoint_ids == ["B1"]
    assert [item.workpoint_id for item in pool.workpoint_overrides] == ["B1"]
    assert pool.workpoint_overrides[0].quantity == 3
    assert pool.workpoint_overrides[0].max_quantity == 3

    save_local_scenario_config(
        process_library=loaded.process_library,
        logic_rules=loaded.logic_rules,
        upper_structure_logic_rules=loaded.upper_structure_logic_rules,
        resource_pools=loaded.resource_pools,
        milestones=loaded.milestones,
        path=path,
    )
    saved_pool = next(
        item for item in json.loads(path.read_text(encoding="utf-8"))["resource_pools"]
        if item["id"] == pool_payload["id"]
    )
    assert saved_pool["unknown_nested_field"] == "ignored-for-forward-compatibility"


def test_legacy_exclusive_pool_is_losslessly_materialized_per_workpoint_and_saves_idempotently(
    tmp_path: Path,
) -> None:
    path = tmp_path / "scheduler-config-v2.json"
    scenario = default_scenario()
    scenario.project.bridges.append(
        scenario.project.bridges[0].model_copy(
            deep=True,
            update={"id": "B2", "name": "契约迁移测试二号桥"},
        )
    )
    workpoint_ids = [bridge.id for bridge in scenario.project.bridges[:2]]
    assert len(workpoint_ids) == 2
    legacy_pool = scenario.resource_pools[0].model_dump(mode="json")
    legacy_pool.update(
        {
            "scope_mode": "WORKPOINT_EXCLUSIVE",
            "workpoint_id": None,
            "authorized_workpoint_ids": list(reversed(workpoint_ids)),
            "workpoint_overrides": [
                {"workpoint_id": workpoint_ids[1], "quantity": 3, "max_quantity": 5},
            ],
            "quantity": 1,
            "max_quantity": 4,
        }
    )
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v2", "resource_pools": [legacy_pool]}),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(scenario, path=path)
    migrated = [
        pool for pool in loaded.resource_pools
        if pool.id.startswith(f"{legacy_pool['id']}::workpoint::")
    ]

    assert [pool.workpoint_id for pool in migrated] == sorted(workpoint_ids)
    assert all(pool.scope_mode == "WORKPOINT_EXCLUSIVE" for pool in migrated)
    assert all(pool.authorized_workpoint_ids is None for pool in migrated)
    assert all(pool.workpoint_overrides == [] for pool in migrated)
    by_workpoint = {pool.workpoint_id: pool for pool in migrated}
    assert by_workpoint[workpoint_ids[0]].quantity == 1
    assert by_workpoint[workpoint_ids[0]].max_quantity == 4
    assert by_workpoint[workpoint_ids[1]].quantity == 3
    assert by_workpoint[workpoint_ids[1]].max_quantity == 5
    assert all(pool.id != legacy_pool["id"] for pool in loaded.resource_pools)

    save_local_scenario_config(
        process_library=loaded.process_library,
        logic_rules=loaded.logic_rules,
        upper_structure_logic_rules=loaded.upper_structure_logic_rules,
        resource_pools=loaded.resource_pools,
        milestones=loaded.milestones,
        path=path,
    )
    first_saved = path.read_text(encoding="utf-8")
    reloaded = apply_local_scenario_config(scenario, path=path)
    save_local_scenario_config(
        process_library=reloaded.process_library,
        logic_rules=reloaded.logic_rules,
        upper_structure_logic_rules=reloaded.upper_structure_logic_rules,
        resource_pools=reloaded.resource_pools,
        milestones=reloaded.milestones,
        path=path,
    )
    assert path.read_text(encoding="utf-8") == first_saved


def test_legacy_exclusive_pool_with_unknown_workpoint_blocks_without_mutating_source(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v2.json"
    scenario = default_scenario()
    legacy_pool = scenario.resource_pools[0].model_dump(mode="json")
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


def test_same_type_shared_pools_merge_by_id_and_round_trip_independently(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v3.json"
    scenario = default_scenario()
    first = scenario.resource_pools[0].model_dump(mode="json")
    first.update({"quantity": 2, "max_quantity": 4, "authorized_workpoint_ids": None})
    second = {**first, "id": f"{first['id']}-second", "label": "同类型第二共享池", "quantity": 1, "max_quantity": 3}
    path.write_text(
        json.dumps({"schema_version": "local-scheduler-config/v3", "resource_pools": [first, second]}),
        encoding="utf-8",
    )

    loaded = apply_local_scenario_config(scenario, path=path)
    matching = [pool for pool in loaded.resource_pools if pool.type == first["type"]]
    by_id = {pool.id: pool for pool in matching}

    assert by_id[first["id"]].quantity == 2
    assert by_id[second["id"]].quantity == 1
    assert by_id[first["id"]].max_quantity == 4
    assert by_id[second["id"]].max_quantity == 3

    save_local_scenario_config(
        process_library=loaded.process_library,
        logic_rules=loaded.logic_rules,
        upper_structure_logic_rules=loaded.upper_structure_logic_rules,
        resource_pools=loaded.resource_pools,
        milestones=loaded.milestones,
        path=path,
    )
    saved = json.loads(path.read_text(encoding="utf-8"))["resource_pools"]
    assert {item["id"] for item in saved if item["type"] == first["type"]} == {first["id"], second["id"]}


def test_duplicate_resource_pool_ids_block_before_merge_without_mutating_source(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v3.json"
    scenario = default_scenario()
    first = scenario.resource_pools[0].model_dump(mode="json")
    duplicate = {**first, "quantity": 3}
    path.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "resource_pools": [first, duplicate]}),
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")

    with pytest.raises(LocalScenarioConfigError, match="资源池 ID 重复"):
        apply_local_scenario_config(scenario, path=path)

    assert path.read_text(encoding="utf-8") == original


def test_save_rejects_shared_pool_with_explicit_empty_workpoint_scope(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v3.json"
    scenario = default_scenario()
    scenario.resource_pools[0].authorized_workpoint_ids = []

    with pytest.raises(LocalScenarioConfigError, match="允许流转工点集合不能为空"):
        save_local_scenario_config(
            process_library=scenario.process_library,
            logic_rules=scenario.logic_rules,
            upper_structure_logic_rules=scenario.upper_structure_logic_rules,
            resource_pools=scenario.resource_pools,
            milestones=scenario.milestones,
            path=path,
        )

    assert not path.exists()
