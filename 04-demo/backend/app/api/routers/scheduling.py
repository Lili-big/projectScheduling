from __future__ import annotations
import math

import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from ...contracts import (
    GeneratedScheduleInput,
    PavementIdleOptimizeRequest,
    MinResourcesSolveRequest,
    ResourceCostSolveRequest,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioInput,
    ScenarioSolveResult,
    ScheduleInput,
    ScheduleResult,
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
from ...services.zpert_plan_export import ZpertPlanExportError, ZpertPlanExportRequest, export_zpert_plan
from ...project_master.scheduling_adapter import project_model_from_master
from ...project_master.service import default_project_master_service
from ...scenario_data import bridge_completion_milestones
from ..errors import project_master_http_error, reject_pavement


router = APIRouter()


def _check_pavement_budget(value):
    if value.engineering_domain == "pavement" and (not math.isfinite(value.time_limit_seconds) or value.time_limit_seconds <= 0):
        raise HTTPException(status_code=422, detail={"code":"PAVEMENT_BUDGET_INVALID","message":"求解预算必须为大于0的有限秒数。"})


@router.post("/api/generate-wbs", response_model=WbsResponse)
def generate_wbs_endpoint(request: WbsRequest) -> WbsResponse:
    return generate_wbs(request.bridge, request.productivity_rules, request.logic_rules)


@router.post("/api/solve")
def solve_endpoint(schedule_input: ScheduleInput):
    _check_pavement_budget(schedule_input)
    if schedule_input.engineering_domain == "pavement":
        from ...scheduling.solver.strategies.pavement import validate_pavement_schedule
        errors, _ = validate_pavement_schedule(schedule_input)
        if errors:
            raise HTTPException(status_code=422, detail={"code":errors[0].code,"message":errors[0].message,"diagnostics":[e.model_dump() for e in errors]})
    elif any(t.pavement_context or t.structure_type == "pavement_section" for t in schedule_input.tasks):
        raise HTTPException(status_code=422, detail={"code":"PAVEMENT_SCOPE_NOT_SUPPORTED","message":"路面任务必须指定路面领域。"})
    return solve_schedule(schedule_input)


@router.post("/api/generate-schedule-input", response_model=GeneratedScheduleInput)
def generate_schedule_input_endpoint(
    scenario: ScenarioInput,
    request: Request,
    workpoint_id: str | None = None,
) -> GeneratedScheduleInput:
    scenario, diagnostics = _materialize_project_master(scenario, request, workpoint_id=workpoint_id)
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
    _check_pavement_budget(scenario)
    scenario, diagnostics = _materialize_project_master(scenario, request, workpoint_id=workpoint_id)
    try:
        if scenario.engineering_domain == "pavement" and any(d.level == "error" for d in diagnostics):
            generated = generate_schedule_input_from_scenario(scenario, workpoint_id=workpoint_id)
            return ScenarioSolveResult(scenario_id=scenario.scenario_id,scenario_name=scenario.scenario_name,
                generated=generated.model_copy(update={"validation":[*diagnostics,*generated.validation]}),
                result=ScheduleResult(status="MODEL_INVALID",plan_start_date=scenario.project.start_date,validation=diagnostics,
                    stats={"pavement_handover": generated.source_summary["pavement_handover"]}),diagnostics=diagnostics)
        result = solve_scenario(scenario, workpoint_id=workpoint_id)
    except ValueError as exc:
        raise _solve_scope_http_error(exc, workpoint_id) from exc
    generated = result.generated.model_copy(update={"validation": [*diagnostics, *result.generated.validation]})
    return result.model_copy(update={"generated": generated, "diagnostics": [*diagnostics, *result.diagnostics]})


@router.post("/api/solve-scenario/stream", response_class=StreamingResponse,
    responses={200: {"content": {"application/x-ndjson": {"schema": {"type": "string"}}}}})
def solve_pavement_stream_endpoint(scenario: ScenarioInput, request: Request, workpoint_id: str | None = None):
    from ...scheduling.application.pavement import solve_pavement_scenario
    from ..pavement_stream import pavement_stream_response
    if scenario.engineering_domain != "pavement":
        raise HTTPException(status_code=422, detail={"code":"PAVEMENT_STREAM_UNSUPPORTED_DOMAIN","message":"实时求解仅支持路面领域。"})
    _check_pavement_budget(scenario)
    scenario, diagnostics = _materialize_project_master(scenario, request, workpoint_id=workpoint_id)
    try:
        generated = generate_schedule_input_from_scenario(scenario, workpoint_id=workpoint_id)
    except ValueError as exc:
        raise _solve_scope_http_error(exc, workpoint_id) from exc
    generated = generated.model_copy(update={"validation": [*diagnostics, *generated.validation]})
    return pavement_stream_response(lambda publish, control: solve_pavement_scenario(scenario,
        generated=generated, on_solution=publish, control=control), scenario.time_limit_seconds)


@router.post("/api/solve-scenario/idle/stream", response_class=StreamingResponse,
    responses={200:{"content":{"application/x-ndjson":{"schema":{"type":"string"}}}}})
def optimize_pavement_idle_endpoint(payload: PavementIdleOptimizeRequest, request: Request, workpoint_id: str | None = None):
    from time import perf_counter
    from ...scheduling.application.pavement import prepare_pavement_idle, solve_pavement_idle_scenario
    from ...scheduling.solver.strategies.pavement import IdleBaselineError
    from ..pavement_stream import pavement_stream_response
    if payload.scenario.engineering_domain != "pavement":
        raise HTTPException(status_code=422,detail={"code":"PAVEMENT_IDLE_UNSUPPORTED_DOMAIN","message":"窝工优化仅支持路面方案。"})
    _check_pavement_budget(payload.scenario)
    scenario,diagnostics=_materialize_project_master(payload.scenario,request,workpoint_id=workpoint_id)
    try:
        generated=generate_schedule_input_from_scenario(scenario,workpoint_id=workpoint_id)
    except ValueError as exc:
        raise _solve_scope_http_error(exc,workpoint_id) from exc
    generated=generated.model_copy(update={"validation":[*diagnostics,*generated.validation]})
    began=perf_counter()
    try:
        prepared=prepare_pavement_idle(scenario,generated,payload.baseline)
    except IdleBaselineError as exc:
        raise HTTPException(status_code=422,detail={"code":exc.code,"message":str(exc)}) from exc
    return pavement_stream_response(lambda publish,control:solve_pavement_idle_scenario(
        scenario,generated,payload.baseline,prepared,began,on_solution=publish,control=control),scenario.time_limit_seconds)


@router.post("/api/solve-min-resources", response_model=ScenarioSolveResult)
def solve_min_resources_endpoint(
    payload: MinResourcesSolveRequest,
    request: Request,
    workpoint_id: str | None = None,
) -> ScenarioSolveResult:
    reject_pavement(payload.scenario, strategy=True)
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
    reject_pavement(payload.scenario, strategy=True)
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


@router.post("/api/zpert-plan/export")
def export_zpert_plan_endpoint(payload: ZpertPlanExportRequest) -> Response:
    try:
        document, file_name = export_zpert_plan(
            payload.project,
            payload.generated,
            payload.result,
            payload.plan_name,
        )
    except ZpertPlanExportError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "ZPERT_PLAN_NOT_EXPORTABLE", "message": str(exc)},
        ) from exc
    body = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
    encoded = quote(file_name, safe="")
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename=\"{encoded}\";filename*=UTF-8''{encoded}"},
    )


def _solve_scope_http_error(exc: ValueError, workpoint_id: str | None) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": "SOLVE_SCOPE_WORKPOINT_INVALID",
            "message": str(exc),
            "workpoint_id": workpoint_id,
        },
    )


def _materialize_project_master(scenario: ScenarioInput, request: Request, *, workpoint_id: str | None = None) -> tuple[ScenarioInput, list]:
    if scenario.engineering_domain == "pavement":
        from ...contracts import ScheduleStrategyConfig
        if scenario.schedule_strategy != ScheduleStrategyConfig():
            raise HTTPException(status_code=422, detail={"code": "PAVEMENT_STRATEGY_NOT_SUPPORTED", "message": "路面首版不支持桥梁策略参数。"})
    if not scenario.project_data_version_id:
        if scenario.engineering_domain == "pavement" and scenario.project.bridges and (not scenario.pavement_settings or scenario.pavement_settings.input_kind != "demo"):
            raise HTTPException(status_code=409, detail={"code":"PROJECT_MASTER_VERSION_NOT_CONFIRMED","message":"客户路面计划必须引用已确认的主数据版本。"})
        return scenario, []
    service = getattr(request.app.state, "project_master_service", None) or default_project_master_service()
    try:
        version = service.repository.get_version_summary(scenario.project_data_version_id)
        if scenario.engineering_domain == "pavement" and version.project_id != scenario.project.project_id:
            raise HTTPException(status_code=409,detail={"code":"PAVEMENT_REFERENCE_INVALID","message":"主数据版本不属于当前项目。"})
        snapshot = service.repository.load_snapshot(version.version_id)
        project, diagnostics = project_model_from_master(
            version=version,
            snapshot=snapshot,
            project_name=scenario.project.project_name,
            start_date=scenario.project.start_date,
            engineering_domain=scenario.engineering_domain,
        )
        if scenario.engineering_domain == "pavement" and workpoint_id:
            # Keep the full project for saved references and resource scope resolution.
            # Only materialization issues inside the requested workpoint block this solve.
            scoped_ids = {workpoint_id}
            for workpoint in snapshot.workpoints:
                if workpoint.workpoint_id == workpoint_id:
                    for structure in workpoint.structures:
                        scoped_ids.add(structure.structure_id)
                        scoped_ids.update(c.component_id for c in structure.components)
            diagnostics = [d for d in diagnostics if not d.subject_id or d.subject_id in scoped_ids]
        return scenario.model_copy(
            update={
                "project": project,
                "milestones": scenario.milestones if scenario.engineering_domain == "pavement" else bridge_completion_milestones(project, scenario.milestones),
            }
        ), diagnostics
    except ValueError as exc:
        from ...project_master.repository import ProjectMasterConflictError

        conflict = ProjectMasterConflictError(str(exc))
        conflict.code = "PROJECT_MASTER_VERSION_NOT_CONFIRMED"
        raise project_master_http_error(conflict) from exc
    except ProjectMasterRepositoryError as exc:
        raise project_master_http_error(exc) from exc
