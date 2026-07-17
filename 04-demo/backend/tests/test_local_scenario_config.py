from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.local_scenario_config import apply_bundled_scenario_config, apply_local_scenario_config, save_local_scenario_config  # noqa: E402
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
