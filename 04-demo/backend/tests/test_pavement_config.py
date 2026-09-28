import json
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.local_scenario_config import apply_scenario_config, save_pavement_profile, LocalScenarioConfigError
from app.scenario_data import pavement_scenario


def test_pavement_profiles_roundtrip_and_preserve_bridge(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": "local-scheduler-config/v4", "logic_rules": [{"old": True}]}))
    scenario = pavement_scenario("project-a")
    from app.contracts.pavement import PavementDependencyRule
    scenario.pavement_settings.dependency_rules = [PavementDependencyRule(predecessor_key="layer:granular_base:1",
        successor_key="layer:cement_stabilized_base:1", relationship="SS", lag_days=2),
        PavementDependencyRule(structure_id="A", predecessor_key="layer:granular_base:1",
        successor_key="layer:cement_stabilized_base:1", relationship="FS", lag_days=7)]
    scenario.resource_pools[0].quantity = 3
    scenario.resource_pools[0].max_quantity = 3
    scenario.resource_pools[0].transfer_days = 2
    save_pavement_profile(scenario, path=path)
    restored = apply_scenario_config(pavement_scenario("project-a"), path=path)
    assert restored.resource_pools == scenario.resource_pools
    assert restored.pavement_settings == scenario.pavement_settings
    assert apply_scenario_config(pavement_scenario("project-b"), path=path).resource_pools[0].quantity == 0
    assert json.loads(path.read_text(encoding="utf-8"))["logic_rules"] == [{"old": True}]
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == "local-scheduler-config/v5"


def test_shared_capabilities_persist_without_changing_other_profiles(tmp_path):
    path = tmp_path / "config.json"
    other = pavement_scenario("other")
    save_pavement_profile(other, path=path)
    before = json.loads(path.read_text(encoding="utf-8"))["pavement_profiles"]["other"]
    scenario = pavement_scenario("shared")
    pool = scenario.resource_pools[1]
    pool.quantity = pool.max_quantity = 1
    pool.transfer_days = 1
    pool.compatible_process_ids = ["pavement-granular_base", "pavement-cement_stabilized_base"]
    save_pavement_profile(scenario, path=path)
    restored = apply_scenario_config(pavement_scenario("shared"), path=path)
    assert restored.resource_pools[1] == pool
    assert json.loads(path.read_text(encoding="utf-8"))["pavement_profiles"]["other"] == before
    saved = path.read_bytes()
    for ids in ([], ["unknown-process"]):
        pool.compatible_process_ids = ids
        with pytest.raises(ValueError):
            save_pavement_profile(scenario, path=path)
        assert path.read_bytes() == saved


def test_legacy_empty_capabilities_restore_only_original_category(tmp_path):
    path = tmp_path / "config.json"
    scenario = pavement_scenario("legacy")
    scenario.resource_pools[1].compatible_process_ids = []
    path.write_text(json.dumps({"pavement_profiles": {"legacy": {"resource_pools": [p.model_dump() for p in scenario.resource_pools]}}}), encoding="utf-8")
    restored = apply_scenario_config(pavement_scenario("legacy"), path=path)
    assert restored.resource_pools[1].compatible_process_ids == ["pavement-cement_stabilized_base"]
    assert scenario.resource_pools[1].compatible_process_ids == []
