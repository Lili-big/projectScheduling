from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...bridge_import import BridgeImportConfigError, BridgeImportError
from ...local_scenario_config import LocalScenarioConfigError
from ...contracts import (
    DemoPayload,
    LocalScenarioConfigResponse,
    LocalScenarioConfigSaveRequest,
    ProcessLibrarySaveRequest,
    ProcessTemplate,
    ProjectStructureParamsApplyRequest,
    ProjectStructureParamsApplyResponse,
    ProjectStructureParamsResponse,
    ProjectStructureParamsSaveRequest,
    ScenarioInput,
)
from ...project_structure_params import (
    ProjectStructureParamsError,
    apply_project_structure_params,
    load_project_structure_params,
    save_project_structure_params,
)
from ...sample_data import default_bridge, default_logic_rules, default_productivity_rules, default_resources
from ...services.process_library_service import (
    default_scenario_with_process_library,
    get_process_library,
    persist_local_scenario_config,
    persist_process_library,
)
from ...wbs import generate_wbs
from ...contracts.pavement import EngineeringDomain


router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/demo", response_model=DemoPayload)
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


@router.get("/api/demo-scenario", response_model=ScenarioInput)
def demo_scenario(engineering_domain: EngineeringDomain = "bridge", project_id: str | None = None) -> ScenarioInput:
    try:
        return default_scenario_with_process_library(engineering_domain, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/process-library", response_model=list[ProcessTemplate])
def get_process_library_endpoint(engineering_domain: EngineeringDomain = "bridge", project_id: str | None = None) -> list[ProcessTemplate]:
    try:
        return get_process_library(engineering_domain, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/api/process-library", response_model=list[ProcessTemplate])
def save_process_library_endpoint(request: ProcessLibrarySaveRequest) -> list[ProcessTemplate]:
    try:
        return persist_process_library(request.process_library, request.engineering_domain, request.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/api/local-scenario-config", response_model=LocalScenarioConfigResponse)
def save_local_scenario_config_endpoint(request: LocalScenarioConfigSaveRequest, http_request: Request = None) -> dict[str, list[object]]:
    try:
        if request.engineering_domain == "pavement" and request.project_data_version_id:
            _validate_pavement_config_version(request, http_request)
        return persist_local_scenario_config(
            process_library=request.process_library,
            logic_rules=request.logic_rules,
            upper_structure_logic_rules=request.upper_structure_logic_rules,
            resource_pools=request.resource_pools,
            milestones=request.milestones,
            **({"engineering_domain": request.engineering_domain, "project_id": request.project_id,
                "pavement_settings": request.pavement_settings, "task_overrides": request.task_overrides,
                "project_data_version_id": request.project_data_version_id, "project_start_date": request.project_start_date} if request.engineering_domain == "pavement" else {}),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LocalScenarioConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/project-structure-params", response_model=ProjectStructureParamsResponse, deprecated=True)
def get_project_structure_params_endpoint() -> ProjectStructureParamsResponse:
    try:
        return load_project_structure_params()
    except ProjectStructureParamsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/api/project-structure-params", response_model=ProjectStructureParamsResponse, deprecated=True)
def save_project_structure_params_endpoint(request: ProjectStructureParamsSaveRequest) -> ProjectStructureParamsResponse:
    try:
        return save_project_structure_params(request.project)
    except ProjectStructureParamsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/api/apply-project-structure-params", response_model=ProjectStructureParamsApplyResponse, deprecated=True)
def apply_project_structure_params_endpoint(request: ProjectStructureParamsApplyRequest) -> ProjectStructureParamsApplyResponse:
    return ProjectStructureParamsApplyResponse(
        scenario=apply_project_structure_params(request.scenario, request.project),
        source="request",
    )


def _validate_pavement_config_version(payload, request):
    from ...project_master.service import default_project_master_service
    from ...project_master.repository import ProjectMasterRepositoryError
    from ..errors import project_master_http_error
    service = getattr(request.app.state, "project_master_service", None) if request else None
    service = service or default_project_master_service()
    try:
        version = service.repository.get_version_summary(payload.project_data_version_id)
        current = service.repository.get_current_version(payload.project_id)
        if version.project_id != payload.project_id or version.status != "confirmed" or current is None or current.version_id != version.version_id:
            raise HTTPException(status_code=409, detail={"code":"PAVEMENT_REFERENCE_INVALID","message":"配置引用的主数据不是本项目当前确认版本。"})
    except ProjectMasterRepositoryError as exc:
        raise project_master_http_error(exc) from exc
