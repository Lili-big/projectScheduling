from __future__ import annotations

from ..models import ProcessTemplate, ScenarioInput
from ..process_repository import load_process_library, save_process_library
from ..scenario_data import apply_resource_max_quantity_defaults, default_scenario


def default_scenario_with_process_library() -> ScenarioInput:
    scenario = default_scenario()
    scenario.process_library = load_process_library(scenario.process_library)
    apply_resource_max_quantity_defaults(scenario)
    return scenario


def get_process_library() -> list[ProcessTemplate]:
    scenario = default_scenario()
    return load_process_library(scenario.process_library)


def persist_process_library(process_library: list[ProcessTemplate]) -> list[ProcessTemplate]:
    return save_process_library(process_library)
