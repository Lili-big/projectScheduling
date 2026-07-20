"""FastAPI endpoints for the independent girder plan simulation path."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ...contracts.girder_plan_simulation import (
    ConfirmSimulationRunRequest,
    CreateScenarioVersionRequest,
    CreateSimulationRunRequest,
    ExpectedFingerprintRequest,
    GirderPlanReadiness,
    GirderPlanScenarioVersion,
    GirderPlanSimulationRun,
    LineGraphSnapshot,
)
from ...girder_plan_simulation.service import (
    DOMAIN_ERRORS,
    GirderPlanSimulationService,
    default_girder_plan_service,
)


router = APIRouter(prefix="/api/girder-plan-simulation", tags=["girder-plan-simulation"])


def _service(request: Request) -> GirderPlanSimulationService:
    return getattr(request.app.state, "girder_plan_simulation_service", None) or default_girder_plan_service()


def _http_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=int(getattr(exc, "status_code", 503)),
        detail={
            "code": str(getattr(exc, "code", "GIRDER_PLAN_SIMULATION_ERROR")),
            "message": str(exc),
        },
    )


@router.get("/line-graphs/{project_master_version_id}", response_model=LineGraphSnapshot)
def get_line_graph_endpoint(project_master_version_id: str, request: Request) -> LineGraphSnapshot:
    try:
        return _service(request).get_line_graph(project_master_version_id)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get("/scenarios", response_model=list[GirderPlanScenarioVersion])
def list_scenarios_endpoint(
    request: Request,
    project_id: str | None = Query(default=None),
) -> list[GirderPlanScenarioVersion]:
    try:
        return _service(request).list_scenarios(project_id)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/scenarios", response_model=GirderPlanScenarioVersion, status_code=201)
def create_scenario_endpoint(
    payload: CreateScenarioVersionRequest,
    request: Request,
) -> GirderPlanScenarioVersion:
    try:
        return _service(request).create_scenario(payload)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get("/scenarios/{scenario_version_id}", response_model=GirderPlanScenarioVersion)
def get_scenario_endpoint(scenario_version_id: str, request: Request) -> GirderPlanScenarioVersion:
    try:
        return _service(request).get_scenario(scenario_version_id)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/scenarios/{scenario_version_id}/validate", response_model=GirderPlanReadiness)
def validate_scenario_endpoint(
    scenario_version_id: str,
    payload: ExpectedFingerprintRequest,
    request: Request,
) -> GirderPlanReadiness:
    try:
        return _service(request).validate_scenario(scenario_version_id, payload)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/runs", response_model=GirderPlanSimulationRun, status_code=201)
def create_run_endpoint(payload: CreateSimulationRunRequest, request: Request) -> GirderPlanSimulationRun:
    try:
        return _service(request).create_run(payload)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get("/runs/{run_id}", response_model=GirderPlanSimulationRun)
def get_run_endpoint(run_id: str, request: Request) -> GirderPlanSimulationRun:
    try:
        return _service(request).get_run(run_id)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/confirm", response_model=GirderPlanSimulationRun)
def confirm_run_endpoint(
    run_id: str,
    payload: ConfirmSimulationRunRequest,
    request: Request,
) -> GirderPlanSimulationRun:
    try:
        return _service(request).confirm_run(run_id, payload)
    except DOMAIN_ERRORS as exc:
        raise _http_error(exc) from exc


__all__ = [name for name in globals() if name == "router" or name.endswith("_endpoint")]
