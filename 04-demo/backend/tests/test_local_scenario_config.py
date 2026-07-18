from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_scenario_config import (  # noqa: E402
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
    assert "abutment_team" not in resources_by_type
    assert all(pool.scope_mode == "PROJECT_SHARED" for pool in loaded.resource_pools)
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


@pytest.mark.parametrize("pool_state", ["missing", "disabled", "unlimited"])
def test_abutment_pool_absent_disabled_or_unlimited_uses_default_sufficient_semantics(pool_state: str) -> None:
    scenario = apply_bundled_scenario_config(default_scenario())
    assert all(pool.type != "abutment_team" for pool in scenario.resource_pools)
    if pool_state != "missing":
        scenario.resource_pools.append(
            ResourcePool(
                id=f"test-abutment-{pool_state}",
                type="abutment_team",
                label="Test team",
                resource_mode="LIMITED" if pool_state == "disabled" else "UNLIMITED",
                quantity=1,
                max_quantity=1,
                enabled=pool_state != "disabled",
            )
        )

    generated = generate_schedule_input_from_scenario(scenario)
    abutment_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "abutment_body"]

    assert abutment_tasks
    assert all(task.compatible_resource_types == [] for task in abutment_tasks)
    assert all(resource.type != "abutment_team" for resource in generated.schedule_input.resources)
    assert not any(message.level == "error" and "资源" in message.message for message in generated.validation)


def test_v1_resource_pools_migrate_to_project_shared_without_mutating_source(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v1.json"
    scenario = default_scenario()
    legacy_pool = scenario.resource_pools[0].model_dump(mode="json")
    for field in ("scope_mode", "authorized_workpoint_ids", "workpoint_overrides"):
        legacy_pool.pop(field, None)
    legacy_pool["quantity"] = 2
    legacy_pool["max_quantity"] = 5
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
    assert migrated.authorized_workpoint_ids is None
    assert migrated.workpoint_overrides == []
    assert migrated.quantity == 2
    assert migrated.max_quantity == 5

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
    assert saved_pool["authorized_workpoint_ids"] is None
    assert saved_pool["workpoint_overrides"] == []
    assert saved_pool["quantity"] == 2

    save_local_scenario_config(
        process_library=loaded.process_library,
        logic_rules=loaded.logic_rules,
        upper_structure_logic_rules=loaded.upper_structure_logic_rules,
        resource_pools=loaded.resource_pools,
        milestones=loaded.milestones,
        path=path,
    )
    assert path.read_text(encoding="utf-8") == first_saved


def test_v2_resource_pool_scope_collections_are_stably_normalized(tmp_path: Path) -> None:
    path = tmp_path / "scheduler-config-v2.json"
    scenario = default_scenario()
    pool_payload = scenario.resource_pools[0].model_dump(mode="json")
    pool_payload.update(
        {
            "scope_mode": "WORKPOINT_EXCLUSIVE",
            "authorized_workpoint_ids": ["WP-B", "WP-A", "WP-B"],
            "workpoint_overrides": [
                {"workpoint_id": "WP-B", "quantity": 3, "max_quantity": 2},
                {"workpoint_id": "WP-A", "enabled": False},
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

    assert pool.scope_mode == "WORKPOINT_EXCLUSIVE"
    assert pool.authorized_workpoint_ids == ["WP-A", "WP-B"]
    assert [item.workpoint_id for item in pool.workpoint_overrides] == ["WP-A", "WP-B"]
    assert pool.workpoint_overrides[1].quantity == 3
    assert pool.workpoint_overrides[1].max_quantity == 3
