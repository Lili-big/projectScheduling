from __future__ import annotations

from ..local_scenario_config import apply_bundled_scenario_config, apply_local_scenario_config, save_local_scenario_config, save_process_library
from ..models import LogicRule, MilestoneConstraint, ProcessTemplate, ResourcePool, ScenarioInput, UpperStructureLogicRule
from ..scenario_data import default_scenario


def default_scenario_with_process_library() -> ScenarioInput:
    scenario = default_scenario()
    scenario = apply_bundled_scenario_config(scenario)
    return apply_local_scenario_config(scenario)


def get_process_library() -> list[ProcessTemplate]:
    return default_scenario_with_process_library().process_library


def persist_process_library(process_library: list[ProcessTemplate]) -> list[ProcessTemplate]:
    return save_process_library(process_library)


def persist_local_scenario_config(
    *,
    process_library: list[ProcessTemplate],
    logic_rules: list[LogicRule],
    upper_structure_logic_rules: list[UpperStructureLogicRule],
    resource_pools: list[ResourcePool],
    milestones: list[MilestoneConstraint],
) -> dict[str, list[object]]:
    return save_local_scenario_config(
        process_library=process_library,
        logic_rules=logic_rules,
        upper_structure_logic_rules=upper_structure_logic_rules,
        resource_pools=resource_pools,
        milestones=milestones,
    )
