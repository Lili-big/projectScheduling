from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .local_config import load_local_config
from .models import (
    AiParameterApplyRequest,
    AiParameterApplyResponse,
    AiParameterParseResponse,
    DemoPayload,
    GeneratedScheduleInput,
    ImportBridgeParamsResponse,
    LocalScenarioConfigResponse,
    LocalScenarioConfigSaveRequest,
    MinResourcesSolveRequest,
    ProcessLibrarySaveRequest,
    ProcessNlRequest,
    ProcessNlResponse,
    ProcessTemplate,
    ProjectStructureParamsApplyRequest,
    ProjectStructureParamsApplyResponse,
    ProjectStructureParamsResponse,
    ProjectStructureParamsSaveRequest,
    ResourceAssistantBatchSolveRequest,
    ResourceAssistantBatchSolveResponse,
    ResourceAssistantComparison,
    ResourceAssistantInitialRequest,
    ResourceAssistantInitialResponse,
    ResourceAssistantRecommendationResponse,
    ResourceAssistantResultsRequest,
    ResourceAssistantSingleSolveRequest,
    ResourceAssistantSingleSolveResponse,
    ResourceAssistantUpdatePlanRequest,
    ResourceAssistantUpdatePlanResponse,
    ResourceCostSolveRequest,
    ScheduleInput,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioInput,
    ScenarioSolveResult,
    WbsRequest,
    WbsResponse,
    AdoptAdjustmentRequest,
    AdoptAdjustmentResponse,
    AdjustmentComparisonResponse,
    CreateAdjustmentRequest,
    CreateBaselinePlanRequest,
    CreateForecastRequest,
    CreateProgressSnapshotRequest,
    CreateProgressSnapshotResponse,
    ForecastSchedule,
    PlanControlProjectSummary,
    PlanVersion,
    ConfirmProjectDataVersionRequest,
    ConfirmSpecialtyRequest,
    CreateIntegratedScheduleRequest,
    CreatePlanningScenarioVersionRequest,
    CreateProjectDataVersionRequest,
    GirderImportPreview,
    GirderProgressImportPreview,
    GirderPlanningReadiness,
    PlanningScenarioVersion,
    ProjectDataVersion,
    ScenarioVersionReference,
    GirderPlanningResult,
    IntegratedCalculationSnapshot,
)
from .api.multipart import parse_multipart_request
from .bridge_import import BridgeImportConfigError, BridgeImportError
from .sample_data import (
    default_bridge,
    default_logic_rules,
    default_productivity_rules,
    default_resources,
)
from .scenario import compare_scenarios, generate_schedule_input_from_scenario, solve_min_resources_scenario, solve_resource_cost_scenario, solve_scenario
from .solver import solve_schedule
from .process_nl import apply_process_natural_language
from .project_structure_params import (
    ProjectStructureParamsError,
    apply_project_structure_params,
    load_project_structure_params,
    save_project_structure_params,
)
from .local_scenario_config import LocalScenarioConfigError
from .services.bridge_import_service import import_local_bridge_params, import_uploaded_bridge_params
from .services.ai_parameter_ai_client import AiParameterAssistantConfigError
from .services.ai_parameter_assistant import AiParameterAssistantError, apply_ai_parameter_suggestions, parse_ai_parameter_assistant
from .services.ai_parameter_materials import AiParameterMaterialError
from .services.ai_resource_scheduling_assistant import (
    batch_solve_resource_plans,
    compare_resource_plan_results,
    generate_resource_plan_recommendation,
    initialize_resource_assistant,
    solve_resource_plan,
    update_resource_plan,
)
from .services.process_library_service import (
    default_scenario_with_process_library,
    get_process_library,
    persist_local_scenario_config,
    persist_process_library,
)
from .services.plan_control_repository import PlanControlRepositoryError, default_plan_control_repository
from .girder_planning.import_service import GirderImportError, import_workpoints
from .girder_planning.progress_import_service import GirderProgressImportError, import_progress_actuals
from .girder_planning.validation import validate_girder_planning
from .services.integrated_schedule import preview_girder_planning, solve_integrated_schedule
from .services.progress_forecast import (
    PlanControlValidationError,
    adopt_adjustment,
    create_adjustment_proposals,
    create_baseline_plan,
    create_forecast,
    create_progress_snapshot,
)
from .wbs import generate_wbs


load_local_config()

app = FastAPI(title="Bridge Lower-Structure CP-SAT Scheduler", version="0.1.0")

NETLIFY_FRONTEND_ORIGIN = "https://project-scheduling-lili-big.netlify.app"

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8888",
    NETLIFY_FRONTEND_ORIGIN,
]


def _csv_env(name: str, defaults: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    values = [value.strip().rstrip("/") for value in raw.split(",") if value.strip()]
    return values or defaults


app.add_middleware(
    CORSMiddleware,
    allow_origins=_csv_env("SCHEDULER_CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
    allow_origin_regex=os.getenv(
        "SCHEDULER_CORS_ORIGIN_REGEX",
        r"https://[a-z0-9-]+--project-scheduling-lili-big\.netlify\.app",
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo", response_model=DemoPayload)
def demo() -> DemoPayload:
    bridge = default_bridge()
    productivity_rules = default_productivity_rules()
    logic_rules = default_logic_rules()
    resources = default_resources()
    wbs = generate_wbs(bridge, productivity_rules, logic_rules)
    return DemoPayload(
        bridge=bridge,
        productivity_rules=productivity_rules,
        logic_rules=logic_rules,
        resources=resources,
        wbs=wbs,
    )


@app.get("/api/demo-scenario", response_model=ScenarioInput)
def demo_scenario() -> ScenarioInput:
    try:
        return default_scenario_with_process_library()
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/process-library", response_model=list[ProcessTemplate])
def get_process_library_endpoint() -> list[ProcessTemplate]:
    try:
        return get_process_library()
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.put("/api/process-library", response_model=list[ProcessTemplate])
def save_process_library_endpoint(request: ProcessLibrarySaveRequest) -> list[ProcessTemplate]:
    try:
        return persist_process_library(request.process_library)
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.put("/api/local-scenario-config", response_model=LocalScenarioConfigResponse)
def save_local_scenario_config_endpoint(request: LocalScenarioConfigSaveRequest) -> dict[str, list[object]]:
    try:
        return persist_local_scenario_config(
            process_library=request.process_library,
            logic_rules=request.logic_rules,
            upper_structure_logic_rules=request.upper_structure_logic_rules,
            resource_pools=request.resource_pools,
            milestones=request.milestones,
        )
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/project-structure-params", response_model=ProjectStructureParamsResponse)
def get_project_structure_params_endpoint() -> ProjectStructureParamsResponse:
    try:
        return load_project_structure_params()
    except ProjectStructureParamsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.put("/api/project-structure-params", response_model=ProjectStructureParamsResponse)
def save_project_structure_params_endpoint(request: ProjectStructureParamsSaveRequest) -> ProjectStructureParamsResponse:
    try:
        return save_project_structure_params(request.project)
    except ProjectStructureParamsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/apply-project-structure-params", response_model=ProjectStructureParamsApplyResponse)
def apply_project_structure_params_endpoint(request: ProjectStructureParamsApplyRequest) -> ProjectStructureParamsApplyResponse:
    return ProjectStructureParamsApplyResponse(
        scenario=apply_project_structure_params(request.scenario, request.project),
        source="request",
    )


@app.post("/api/generate-wbs", response_model=WbsResponse)
def generate_wbs_endpoint(request: WbsRequest) -> WbsResponse:
    return generate_wbs(request.bridge, request.productivity_rules, request.logic_rules)


@app.post("/api/solve")
def solve_endpoint(schedule_input: ScheduleInput):
    return solve_schedule(schedule_input)


@app.post("/api/generate-schedule-input", response_model=GeneratedScheduleInput)
def generate_schedule_input_endpoint(scenario: ScenarioInput) -> GeneratedScheduleInput:
    return generate_schedule_input_from_scenario(scenario)


@app.post("/api/solve-scenario", response_model=ScenarioSolveResult)
def solve_scenario_endpoint(scenario: ScenarioInput) -> ScenarioSolveResult:
    return solve_scenario(scenario)


@app.post("/api/solve-min-resources", response_model=ScenarioSolveResult)
def solve_min_resources_endpoint(request: MinResourcesSolveRequest) -> ScenarioSolveResult:
    return solve_min_resources_scenario(request)


@app.post("/api/solve-resource-cost", response_model=ScenarioSolveResult)
def solve_resource_cost_endpoint(request: ResourceCostSolveRequest) -> ScenarioSolveResult:
    return solve_resource_cost_scenario(request)


@app.post("/api/compare-scenarios", response_model=ScenarioCompareResponse)
def compare_scenarios_endpoint(request: ScenarioCompareRequest) -> ScenarioCompareResponse:
    return compare_scenarios(request)


@app.post("/api/ai-resource-assistant/initialize", response_model=ResourceAssistantInitialResponse)
def initialize_resource_assistant_endpoint(request: ResourceAssistantInitialRequest) -> ResourceAssistantInitialResponse:
    try:
        return initialize_resource_assistant(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/ai-resource-assistant/update-plan", response_model=ResourceAssistantUpdatePlanResponse)
def update_resource_plan_endpoint(request: ResourceAssistantUpdatePlanRequest) -> ResourceAssistantUpdatePlanResponse:
    try:
        return update_resource_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/ai-resource-assistant/batch-solve", response_model=ResourceAssistantBatchSolveResponse)
def batch_solve_resource_plans_endpoint(request: ResourceAssistantBatchSolveRequest) -> ResourceAssistantBatchSolveResponse:
    return batch_solve_resource_plans(request)


@app.post("/api/ai-resource-assistant/solve-plan", response_model=ResourceAssistantSingleSolveResponse)
def solve_resource_plan_endpoint(request: ResourceAssistantSingleSolveRequest) -> ResourceAssistantSingleSolveResponse:
    return solve_resource_plan(request)


@app.post("/api/ai-resource-assistant/compare-results", response_model=ResourceAssistantComparison)
def compare_resource_plan_results_endpoint(request: ResourceAssistantResultsRequest) -> ResourceAssistantComparison:
    try:
        return compare_resource_plan_results(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/ai-resource-assistant/generate-recommendation", response_model=ResourceAssistantRecommendationResponse)
def generate_resource_plan_recommendation_endpoint(
    request: ResourceAssistantResultsRequest,
) -> ResourceAssistantRecommendationResponse:
    try:
        return generate_resource_plan_recommendation(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _plan_control_http_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=int(getattr(exc, "status_code", 503)), detail=str(exc))


@app.post("/api/project-data-versions", response_model=ProjectDataVersion, status_code=201)
def create_project_data_version_endpoint(request: CreateProjectDataVersionRequest) -> ProjectDataVersion:
    try:
        return default_plan_control_repository.create_project_data_version(request)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.get("/api/projects/{project_id}/data-versions", response_model=list[ProjectDataVersion])
def list_project_data_versions_endpoint(project_id: str) -> list[ProjectDataVersion]:
    try:
        return default_plan_control_repository.list_project_data_versions(project_id)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/project-data-versions/{project_data_version_id}/confirm", response_model=ProjectDataVersion)
def confirm_project_data_version_endpoint(
    project_data_version_id: str,
    request: ConfirmProjectDataVersionRequest,
) -> ProjectDataVersion:
    try:
        return default_plan_control_repository.confirm_project_data_version(project_data_version_id, request)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/girder-planning/import-workpoints", response_model=GirderImportPreview)
async def import_girder_workpoints_endpoint(request: Request) -> GirderImportPreview:
    try:
        fields, files = await parse_multipart_request(request)
        project_data_version_id = fields.get("project_data_version_id", "").strip()
        upload = files.get("file")
        if not project_data_version_id or upload is None:
            raise GirderImportError("必须提供 project_data_version_id 和架梁工点文件。")
        project_version = default_plan_control_repository.get_project_data_version(project_data_version_id)
        return import_workpoints(
            file_name=str(upload["filename"]),
            content=bytes(upload["content"]),
            project_version=project_version,
            coarse_mode=fields.get("coarse_mode", "false").strip().lower() in {"1", "true", "yes"},
        )
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc
    except GirderImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/girder-planning/import-progress", response_model=GirderProgressImportPreview)
async def import_girder_progress_endpoint(request: Request) -> GirderProgressImportPreview:
    try:
        _, files = await parse_multipart_request(request)
        upload = files.get("file")
        if upload is None:
            raise GirderProgressImportError("必须提供架梁实绩文件。")
        return import_progress_actuals(file_name=str(upload["filename"]), content=bytes(upload["content"]))
    except GirderProgressImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/planning-scenario-versions", response_model=PlanningScenarioVersion, status_code=201)
def create_planning_scenario_version_endpoint(
    request: CreatePlanningScenarioVersionRequest,
) -> PlanningScenarioVersion:
    try:
        return default_plan_control_repository.create_planning_scenario_version(request)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.get("/api/projects/{project_id}/planning-scenarios", response_model=list[PlanningScenarioVersion])
def list_planning_scenario_versions_endpoint(project_id: str) -> list[PlanningScenarioVersion]:
    try:
        return default_plan_control_repository.list_planning_scenario_versions(project_id)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post(
    "/api/planning-scenario-versions/{scenario_version_id}/confirm-specialty",
    response_model=PlanningScenarioVersion,
)
def confirm_girder_specialty_endpoint(
    scenario_version_id: str,
    request: ConfirmSpecialtyRequest,
) -> PlanningScenarioVersion:
    try:
        scenario_version = default_plan_control_repository.get_planning_scenario_version(scenario_version_id)
        project_version = default_plan_control_repository.get_project_data_version(scenario_version.project_data_version_id)
        readiness = validate_girder_planning(scenario_version, project_version)
        if readiness.status == "blocking":
            raise HTTPException(status_code=422, detail="架梁专项仍存在阻断项，不能确认。")
        return default_plan_control_repository.confirm_specialty(scenario_version_id, request)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/girder-planning/validate", response_model=GirderPlanningReadiness)
def validate_girder_planning_endpoint(request: ScenarioVersionReference) -> GirderPlanningReadiness:
    try:
        scenario_version = default_plan_control_repository.get_planning_scenario_version(request.scenario_version_id)
        if scenario_version.input_fingerprint != request.expected_input_fingerprint:
            raise HTTPException(status_code=409, detail="方案输入已变化，请刷新后重新校验。")
        project_version = default_plan_control_repository.get_project_data_version(scenario_version.project_data_version_id)
        return validate_girder_planning(scenario_version, project_version)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/girder-planning/preview", response_model=GirderPlanningResult)
def preview_girder_planning_endpoint(request: ScenarioVersionReference) -> GirderPlanningResult:
    try:
        scenario_version = default_plan_control_repository.get_planning_scenario_version(request.scenario_version_id)
        if scenario_version.input_fingerprint != request.expected_input_fingerprint:
            raise HTTPException(status_code=409, detail="方案输入已变化，请刷新后重新预览。")
        project_version = default_plan_control_repository.get_project_data_version(scenario_version.project_data_version_id)
        return preview_girder_planning(scenario_version, project_version)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/integrated-schedules", response_model=IntegratedCalculationSnapshot)
def solve_integrated_schedule_endpoint(request: CreateIntegratedScheduleRequest) -> IntegratedCalculationSnapshot:
    try:
        return solve_integrated_schedule(request, default_plan_control_repository)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.get("/api/integrated-schedules/{integrated_snapshot_id}", response_model=IntegratedCalculationSnapshot)
def get_integrated_schedule_endpoint(integrated_snapshot_id: str) -> IntegratedCalculationSnapshot:
    try:
        return default_plan_control_repository.get_integrated_snapshot(integrated_snapshot_id)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/plan-control/baselines", response_model=PlanVersion)
def create_baseline_plan_endpoint(request: CreateBaselinePlanRequest) -> PlanVersion:
    try:
        return create_baseline_plan(request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise _plan_control_http_error(exc) from exc


@app.get("/api/plan-control/projects/{project_id}", response_model=PlanControlProjectSummary)
def get_plan_control_project_endpoint(project_id: str) -> PlanControlProjectSummary:
    try:
        return default_plan_control_repository.project_summary(project_id)
    except PlanControlRepositoryError as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/plan-control/progress-snapshots", response_model=CreateProgressSnapshotResponse)
def create_progress_snapshot_endpoint(request: CreateProgressSnapshotRequest) -> CreateProgressSnapshotResponse:
    try:
        return create_progress_snapshot(request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/plan-control/forecasts", response_model=ForecastSchedule)
def create_forecast_endpoint(request: CreateForecastRequest) -> ForecastSchedule:
    try:
        return create_forecast(request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise _plan_control_http_error(exc) from exc


@app.post(
    "/api/plan-control/forecasts/{forecast_id}/adjustments",
    response_model=AdjustmentComparisonResponse,
)
def create_adjustment_proposals_endpoint(
    forecast_id: str,
    request: CreateAdjustmentRequest,
) -> AdjustmentComparisonResponse:
    try:
        return create_adjustment_proposals(forecast_id, request.max_resource_increments)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/plan-control/adjustments/{proposal_id}/adopt", response_model=AdoptAdjustmentResponse)
def adopt_adjustment_endpoint(proposal_id: str, request: AdoptAdjustmentRequest) -> AdoptAdjustmentResponse:
    try:
        return adopt_adjustment(proposal_id, request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise _plan_control_http_error(exc) from exc


@app.post("/api/apply-process-natural-language", response_model=ProcessNlResponse)
def apply_process_natural_language_endpoint(request: ProcessNlRequest) -> ProcessNlResponse:
    return apply_process_natural_language(request.scenario, request.prompt)


@app.post("/api/ai-parameter-assistant/parse", response_model=AiParameterParseResponse)
async def parse_ai_parameter_assistant_endpoint(request: Request) -> AiParameterParseResponse:
    try:
        fields, files = await parse_multipart_request(request)
        return parse_ai_parameter_assistant(fields, files)
    except AiParameterMaterialError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except AiParameterAssistantConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AiParameterAssistantError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/api/ai-parameter-assistant/apply", response_model=AiParameterApplyResponse)
def apply_ai_parameter_assistant_endpoint(request: AiParameterApplyRequest) -> AiParameterApplyResponse:
    try:
        return apply_ai_parameter_suggestions(request)
    except AiParameterAssistantError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/api/import-bridge-params", response_model=ImportBridgeParamsResponse)
async def import_bridge_params_endpoint(request: Request) -> ImportBridgeParamsResponse:
    try:
        fields, files = await parse_multipart_request(request)
        return import_uploaded_bridge_params(fields, files)
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/import-local-bridge-params", response_model=ImportBridgeParamsResponse)
def import_local_bridge_params_endpoint(scenario: ScenarioInput) -> ImportBridgeParamsResponse:
    try:
        return import_local_bridge_params(scenario)
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        requested = DIST_DIR / full_path
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(DIST_DIR / "index.html")
