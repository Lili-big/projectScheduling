from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...contracts import (
    GeneratedScheduleInput,
    MinResourcesSolveRequest,
    ResourceCostSolveRequest,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioInput,
    ScenarioSolveResult,
    ScheduleInput,
    WbsRequest,
    WbsResponse,
)
from ...scenario import (
    compare_scenarios,
    generate_schedule_input_from_scenario,
    solve_min_resources_scenario,
    solve_resource_cost_scenario,
    solve_scenario,
)
from ...solver import solve_schedule
from ...wbs import generate_wbs
from ...project_master.repository import ProjectMasterRepositoryError
from ...project_master.scheduling_adapter import project_model_from_master
from ...project_master.service import default_project_master_service
from ...scenario_data import bridge_completion_milestones
from ..errors import project_master_http_error


router = APIRouter()


@router.post("/api/generate-wbs", response_model=WbsResponse)
def generate_wbs_endpoint(request: WbsRequest) -> WbsResponse:
    return generate_wbs(request.bridge, request.productivity_rules, request.logic_rules)


@router.post("/api/solve")
def solve_endpoint(schedule_input: ScheduleInput):
    return solve_schedule(schedule_input)


@router.post("/api/generate-schedule-input", response_model=GeneratedScheduleInput)
def generate_schedule_input_endpoint(
    scenario: ScenarioInput,
    request: Request,
    workpoint_id: str | None = None,
) -> GeneratedScheduleInput:
    scenario, diagnostics = _materialize_project_master(scenario, request)
    try:
        generated = generate_schedule_input_from_scenario(scenario, workpoint_id=workpoint_id)
    except ValueError as exc:
        raise _solve_scope_http_error(exc, workpoint_id) from exc
    return generated.model_copy(update={"validation": [*diagnostics, *generated.validation]})


@router.post("/api/solve-scenario", response_model=ScenarioSolveResult)
def solve_scenario_endpoint(
    scenario: ScenarioInput,
    request: Request,
    workpoint_id: str | None = None,
) -> ScenarioSolveResult:
    scenario, diagnostics = _materialize_project_master(scenario, request)
    try:
        result = solve_scenario(scenario, workpoint_id=workpoint_id)
    except ValueError as exc:
        raise _solve_scope_http_error(exc, workpoint_id) from exc
    generated = result.generated.model_copy(update={"validation": [*diagnostics, *result.generated.validation]})
    return result.model_copy(update={"generated": generated, "diagnostics": [*diagnostics, *result.diagnostics]})


@router.post("/api/solve-min-resources", response_model=ScenarioSolveResult)
def solve_min_resources_endpoint(
    payload: MinResourcesSolveRequest,
    request: Request,
    workpoint_id: str | None = None,
) -> ScenarioSolveResult:
    scenario, diagnostics = _materialize_project_master(payload.scenario, request)
    try:
        result = solve_min_resources_scenario(
            payload.model_copy(update={"scenario": scenario}),
            workpoint_id=workpoint_id,
        )
    except ValueError as exc:
        raise _solve_scope_http_error(exc, workpoint_id) from exc
    return result.model_copy(update={"diagnostics": [*diagnostics, *result.diagnostics]})


@router.post("/api/solve-resource-cost", response_model=ScenarioSolveResult)
def solve_resource_cost_endpoint(
    payload: ResourceCostSolveRequest,
    request: Request,
    workpoint_id: str | None = None,
) -> ScenarioSolveResult:
    scenario, diagnostics = _materialize_project_master(payload.scenario, request)
    try:
        result = solve_resource_cost_scenario(
            payload.model_copy(update={"scenario": scenario}),
            workpoint_id=workpoint_id,
        )
    except ValueError as exc:
        raise _solve_scope_http_error(exc, workpoint_id) from exc
    return result.model_copy(update={"diagnostics": [*diagnostics, *result.diagnostics]})


@router.post("/api/compare-scenarios", response_model=ScenarioCompareResponse)
def compare_scenarios_endpoint(request: ScenarioCompareRequest) -> ScenarioCompareResponse:
    try:
        return compare_scenarios(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "SOLVE_SCOPE_COMPARISON_NOT_ALLOWED", "message": str(exc)},
        ) from exc


def _solve_scope_http_error(exc: ValueError, workpoint_id: str | None) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": "SOLVE_SCOPE_WORKPOINT_INVALID",
            "message": str(exc),
            "workpoint_id": workpoint_id,
        },
    )


def _materialize_project_master(scenario: ScenarioInput, request: Request) -> tuple[ScenarioInput, list]:
    if not scenario.project_data_version_id:
        return scenario, []
    service = getattr(request.app.state, "project_master_service", None) or default_project_master_service()
    try:
        version = service.repository.get_version_summary(scenario.project_data_version_id)
        snapshot = service.repository.load_snapshot(version.version_id)
        project, diagnostics = project_model_from_master(
            version=version,
            snapshot=snapshot,
            project_name=scenario.project.project_name,
            start_date=scenario.project.start_date,
        )
        return scenario.model_copy(
            update={
                "project": project,
                "milestones": bridge_completion_milestones(project, scenario.milestones),
            }
        ), diagnostics
    except ValueError as exc:
        from ...project_master.repository import ProjectMasterConflictError

        conflict = ProjectMasterConflictError(str(exc))
        conflict.code = "PROJECT_MASTER_VERSION_NOT_CONFIRMED"
        raise project_master_http_error(conflict) from exc
    except ProjectMasterRepositoryError as exc:
        raise project_master_http_error(exc) from exc
