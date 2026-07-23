"""Stable FastAPI entrypoint and endpoint compatibility façade.

Runtime assembly lives in :mod:`app.bootstrap`; route implementations are
grouped under :mod:`app.api.routers`. Imports from this module remain available
for existing tests and integrations during the architecture migration.
"""

from __future__ import annotations

from .api.errors import plan_control_http_error as _plan_control_http_error
from .api.routers import plan_control as _plan_control
from .api.routers import project_girder as _project_girder
from .api.routers.project_master import (
    cancel_project_master_import_endpoint,
    confirm_project_master_version_endpoint,
    download_project_master_template_endpoint,
    export_project_master_version_endpoint,
    get_current_project_master_version_endpoint,
    get_project_master_import_endpoint,
    get_project_master_version_endpoint,
    get_project_master_workpoint_endpoint,
    get_task_view_display_map_endpoint,
    import_project_master_endpoint,
    list_project_master_versions_endpoint,
    list_project_master_girder_workpoints_endpoint,
    list_project_master_workpoints_endpoint,
)
from .api.routers.assistants import (
    apply_ai_parameter_assistant_endpoint,
    apply_process_natural_language_endpoint,
    batch_solve_resource_plans_endpoint,
    compare_resource_plan_results_endpoint,
    generate_resource_plan_recommendation_endpoint,
    initialize_resource_assistant_endpoint,
    parse_ai_parameter_assistant_endpoint,
    solve_resource_plan_endpoint,
    update_resource_plan_endpoint,
)
from .api.routers.plan_control import (
    adopt_adjustment_endpoint,
    create_adjustment_proposals_endpoint,
    create_baseline_plan_endpoint,
    create_progress_snapshot_endpoint,
    get_plan_control_project_endpoint,
)
from .api.routers.project_girder import (
    confirm_girder_specialty_endpoint,
    get_integrated_schedule_endpoint,
    import_bridge_params_endpoint,
    import_girder_progress_endpoint,
    import_girder_workpoints_endpoint,
    import_local_bridge_params_endpoint,
    list_planning_scenario_versions_endpoint,
    list_project_data_versions_endpoint,
    preview_girder_planning_endpoint,
    solve_integrated_schedule_endpoint,
)
from .api.routers.scheduling import (
    compare_scenarios_endpoint,
    generate_schedule_input_endpoint,
    generate_wbs_endpoint,
    solve_endpoint,
    solve_min_resources_endpoint,
    solve_resource_cost_endpoint,
    solve_scenario_endpoint,
)
from .api.routers.system import (
    apply_project_structure_params_endpoint,
    demo,
    demo_scenario,
    get_process_library_endpoint,
    get_project_structure_params_endpoint,
    health,
    save_local_scenario_config_endpoint,
    save_process_library_endpoint,
    save_project_structure_params_endpoint,
)
from .bootstrap import DEFAULT_CORS_ORIGINS, DIST_DIR, NETLIFY_FRONTEND_ORIGIN, create_app, csv_env
from .contracts import (
    ConfirmProjectDataVersionRequest,
    CreateForecastRequest,
    CreatePlanningScenarioVersionRequest,
    CreateProjectDataVersionRequest,
    ForecastSchedule,
    PlanningScenarioVersion,
    ProjectDataVersion,
    ScenarioVersionReference,
    GirderPlanningReadiness,
)
from .services.plan_control_repository import default_plan_control_repository
from .services.progress_forecast import create_forecast


_csv_env = csv_env
app = create_app()


def _sync_project_repository() -> None:
    # Existing direct-call tests patch ``app.main.default_plan_control_repository``.
    _project_girder.default_plan_control_repository = default_plan_control_repository


def create_project_data_version_endpoint(request: CreateProjectDataVersionRequest) -> ProjectDataVersion:
    _sync_project_repository()
    return _project_girder.create_project_data_version_endpoint(request)


def confirm_project_data_version_endpoint(
    project_data_version_id: str,
    request: ConfirmProjectDataVersionRequest,
) -> ProjectDataVersion:
    _sync_project_repository()
    return _project_girder.confirm_project_data_version_endpoint(project_data_version_id, request)


def create_planning_scenario_version_endpoint(
    request: CreatePlanningScenarioVersionRequest,
) -> PlanningScenarioVersion:
    _sync_project_repository()
    return _project_girder.create_planning_scenario_version_endpoint(request)


def validate_girder_planning_endpoint(request: ScenarioVersionReference) -> GirderPlanningReadiness:
    _sync_project_repository()
    return _project_girder.validate_girder_planning_endpoint(request)


def create_forecast_endpoint(request: CreateForecastRequest) -> ForecastSchedule:
    # Preserve the legacy monkeypatch seam used by direct endpoint tests.
    _plan_control.create_forecast = create_forecast
    return _plan_control.create_forecast_endpoint(request)


__all__ = [name for name in globals() if name == "app" or name.endswith("_endpoint")]
