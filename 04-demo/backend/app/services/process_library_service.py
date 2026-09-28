from __future__ import annotations

from ..local_scenario_config import apply_bundled_scenario_config, apply_local_scenario_config, save_local_scenario_config, save_process_library
from ..contracts import LogicRule, MilestoneConstraint, ProcessTemplate, ResourcePool, ScenarioInput, UpperStructureLogicRule
from ..scenario_data import default_scenario, pavement_scenario
from ..local_scenario_config import save_pavement_profile


def default_scenario_with_process_library(engineering_domain="bridge", project_id=None) -> ScenarioInput:
    if engineering_domain == "pavement":
        return apply_local_scenario_config(pavement_scenario(project_id or "pavement-project"))
    scenario = default_scenario()
    scenario = apply_bundled_scenario_config(scenario)
    return apply_local_scenario_config(scenario)


def get_process_library(engineering_domain="bridge", project_id=None) -> list[ProcessTemplate]:
    return default_scenario_with_process_library(engineering_domain, project_id).process_library


def persist_process_library(process_library: list[ProcessTemplate], engineering_domain="bridge", project_id=None) -> list[ProcessTemplate]:
    if engineering_domain == "pavement":
        if not project_id: raise ValueError("保存路面配置必须提供项目ID。")
        scenario = default_scenario_with_process_library(engineering_domain, project_id)
        scenario.process_library = process_library
        return save_pavement_profile(scenario).process_library
    return save_process_library(process_library)


def persist_local_scenario_config(
    *,
    process_library: list[ProcessTemplate],
    logic_rules: list[LogicRule],
    upper_structure_logic_rules: list[UpperStructureLogicRule],
    resource_pools: list[ResourcePool],
    milestones: list[MilestoneConstraint],
    engineering_domain="bridge", project_id=None, pavement_settings=None, task_overrides=None, project_data_version_id=None, project_start_date=None,
) -> dict[str, list[object]]:
    if engineering_domain == "pavement":
        if not project_id: raise ValueError("保存路面配置必须提供项目ID。")
        scenario = default_scenario_with_process_library(engineering_domain, project_id)
        scenario = ScenarioInput.model_validate({**scenario.model_dump(mode="python"), "process_library": process_library,
            "resource_pools": resource_pools, "pavement_settings": pavement_settings, "task_overrides": task_overrides or {},
            "project_data_version_id": project_data_version_id})
        if project_start_date is not None: scenario.project.start_date = project_start_date
        save_pavement_profile(scenario)
        return {"engineering_domain": engineering_domain, "project_id": project_id,
            "process_library": process_library, "logic_rules": [], "upper_structure_logic_rules": [],
            "resource_pools": resource_pools, "milestones": [], "task_overrides": scenario.task_overrides,
            "pavement_settings": pavement_settings, "project_data_version_id": project_data_version_id, "project_start_date": scenario.project.start_date}
    return save_local_scenario_config(
        process_library=process_library,
        logic_rules=logic_rules,
        upper_structure_logic_rules=upper_structure_logic_rules,
        resource_pools=resource_pools,
        milestones=milestones,
    )
