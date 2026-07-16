from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..errors import plan_control_http_error
from ..multipart import parse_multipart_request
from ...bridge_import import BridgeImportConfigError, BridgeImportError
from ...girder_planning.import_service import GirderImportError, import_workpoints
from ...girder_planning.progress_import_service import GirderProgressImportError, import_progress_actuals
from ...girder_planning.validation import validate_girder_planning
from ...contracts import (
    ConfirmProjectDataVersionRequest,
    ConfirmSpecialtyRequest,
    CreateIntegratedScheduleRequest,
    CreatePlanningScenarioVersionRequest,
    CreateProjectDataVersionRequest,
    GirderImportPreview,
    GirderPlanningReadiness,
    GirderPlanningResult,
    GirderProgressImportPreview,
    ImportBridgeParamsResponse,
    IntegratedCalculationSnapshot,
    PlanningScenarioVersion,
    ProjectDataVersion,
    ScenarioInput,
    ScenarioVersionReference,
)
from ...girder_planning.application import preview_girder_planning, solve_integrated_schedule
from ...importing.bridge import import_local_bridge_params, import_uploaded_bridge_params
from ...plan_control.repository import PlanControlRepositoryError, default_plan_control_repository


router = APIRouter()


@router.post("/api/project-data-versions", response_model=ProjectDataVersion, status_code=201)
def create_project_data_version_endpoint(request: CreateProjectDataVersionRequest) -> ProjectDataVersion:
    try:
        return default_plan_control_repository.create_project_data_version(request)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.get("/api/projects/{project_id}/data-versions", response_model=list[ProjectDataVersion])
def list_project_data_versions_endpoint(project_id: str) -> list[ProjectDataVersion]:
    try:
        return default_plan_control_repository.list_project_data_versions(project_id)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.post("/api/project-data-versions/{project_data_version_id}/confirm", response_model=ProjectDataVersion)
def confirm_project_data_version_endpoint(
    project_data_version_id: str,
    request: ConfirmProjectDataVersionRequest,
) -> ProjectDataVersion:
    try:
        return default_plan_control_repository.confirm_project_data_version(project_data_version_id, request)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.post("/api/girder-planning/import-workpoints", response_model=GirderImportPreview, deprecated=True)
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
        raise plan_control_http_error(exc) from exc
    except GirderImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/girder-planning/import-progress", response_model=GirderProgressImportPreview)
async def import_girder_progress_endpoint(request: Request) -> GirderProgressImportPreview:
    try:
        _, files = await parse_multipart_request(request)
        upload = files.get("file")
        if upload is None:
            raise GirderProgressImportError("必须提供架梁实绩文件。")
        return import_progress_actuals(file_name=str(upload["filename"]), content=bytes(upload["content"]))
    except GirderProgressImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/planning-scenario-versions", response_model=PlanningScenarioVersion, status_code=201)
def create_planning_scenario_version_endpoint(
    request: CreatePlanningScenarioVersionRequest,
) -> PlanningScenarioVersion:
    try:
        return default_plan_control_repository.create_planning_scenario_version(request)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.get("/api/projects/{project_id}/planning-scenarios", response_model=list[PlanningScenarioVersion])
def list_planning_scenario_versions_endpoint(project_id: str) -> list[PlanningScenarioVersion]:
    try:
        return default_plan_control_repository.list_planning_scenario_versions(project_id)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.post(
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
        raise plan_control_http_error(exc) from exc


@router.post("/api/girder-planning/validate", response_model=GirderPlanningReadiness)
def validate_girder_planning_endpoint(request: ScenarioVersionReference) -> GirderPlanningReadiness:
    try:
        scenario_version = default_plan_control_repository.get_planning_scenario_version(request.scenario_version_id)
        if scenario_version.input_fingerprint != request.expected_input_fingerprint:
            raise HTTPException(status_code=409, detail="方案输入已变化，请刷新后重新校验。")
        project_version = default_plan_control_repository.get_project_data_version(scenario_version.project_data_version_id)
        return validate_girder_planning(scenario_version, project_version)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.post("/api/girder-planning/preview", response_model=GirderPlanningResult)
def preview_girder_planning_endpoint(request: ScenarioVersionReference) -> GirderPlanningResult:
    try:
        scenario_version = default_plan_control_repository.get_planning_scenario_version(request.scenario_version_id)
        if scenario_version.input_fingerprint != request.expected_input_fingerprint:
            raise HTTPException(status_code=409, detail="方案输入已变化，请刷新后重新预览。")
        project_version = default_plan_control_repository.get_project_data_version(scenario_version.project_data_version_id)
        return preview_girder_planning(scenario_version, project_version)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.post("/api/integrated-schedules", response_model=IntegratedCalculationSnapshot)
def solve_integrated_schedule_endpoint(request: CreateIntegratedScheduleRequest) -> IntegratedCalculationSnapshot:
    try:
        return solve_integrated_schedule(request, default_plan_control_repository)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.get("/api/integrated-schedules/{integrated_snapshot_id}", response_model=IntegratedCalculationSnapshot)
def get_integrated_schedule_endpoint(integrated_snapshot_id: str) -> IntegratedCalculationSnapshot:
    try:
        return default_plan_control_repository.get_integrated_snapshot(integrated_snapshot_id)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.post("/api/import-bridge-params", response_model=ImportBridgeParamsResponse, deprecated=True)
async def import_bridge_params_endpoint(request: Request) -> ImportBridgeParamsResponse:
    try:
        fields, files = await parse_multipart_request(request)
        return import_uploaded_bridge_params(fields, files)
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/import-local-bridge-params", response_model=ImportBridgeParamsResponse, deprecated=True)
def import_local_bridge_params_endpoint(scenario: ScenarioInput) -> ImportBridgeParamsResponse:
    try:
        return import_local_bridge_params(scenario)
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
