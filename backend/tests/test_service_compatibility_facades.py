from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.assistants.parameter import application as parameter_application  # noqa: E402
from app.assistants.resource import application as resource_application  # noqa: E402
from app.config import scenario as config_scenario  # noqa: E402
from app.girder_planning import application as girder_application  # noqa: E402
from app.importing import bridge as bridge_importing  # noqa: E402
from app.plan_control import forecasting, repository  # noqa: E402
from app.services import ai_parameter_assistant, ai_resource_scheduling_assistant  # noqa: E402
from app.services import bridge_import_service, integrated_schedule, plan_control_repository, progress_forecast  # noqa: E402
from app import local_scenario_config  # noqa: E402


def test_new_application_boundaries_reference_the_single_existing_implementations() -> None:
    assert bridge_importing.import_uploaded_bridge_params is bridge_import_service.import_uploaded_bridge_params
    assert parameter_application.parse_ai_parameter_assistant is ai_parameter_assistant.parse_ai_parameter_assistant
    assert resource_application.initialize_resource_assistant is ai_resource_scheduling_assistant.initialize_resource_assistant
    assert girder_application.solve_integrated_schedule is integrated_schedule.solve_integrated_schedule
    assert repository.PlanControlRepository is plan_control_repository.PlanControlRepository
    assert forecasting.create_forecast is progress_forecast.create_forecast


def test_config_boundary_preserves_paths_and_merge_functions() -> None:
    assert config_scenario.LOCAL_SCENARIO_CONFIG_PATH == local_scenario_config.LOCAL_SCENARIO_CONFIG_PATH
    assert config_scenario.BUNDLED_SCENARIO_CONFIG_PATH == local_scenario_config.BUNDLED_SCENARIO_CONFIG_PATH
    assert config_scenario.apply_local_scenario_config is local_scenario_config.apply_local_scenario_config
