from __future__ import annotations

from fastapi import Depends, APIRouter, HTTPException, Request

from ..multipart import parse_multipart_request
from ...contracts import (
    AiParameterApplyRequest,
    AiParameterApplyResponse,
    AiParameterParseResponse,
    AiWorkpointResourceInitializationRequest,
    AiWorkpointResourceInitializationResponse,
    ProcessNlRequest,
    ProcessNlResponse,
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
)
from ...process_nl import apply_process_natural_language
from ...assistants.parameter.application import AiParameterAssistantError, apply_ai_parameter_suggestions, parse_ai_parameter_assistant
from ...assistants.parameter.client import AiParameterAssistantConfigError
from ...assistants.parameter.materials import AiParameterMaterialError
from ...assistants.resource.application import (
    batch_solve_resource_plans,
    compare_resource_plan_results,
    generate_resource_plan_recommendation,
    initialize_resource_assistant,
    solve_resource_plan,
    update_resource_plan,
)
from ...services.ai_resource_explainer import AiResourceAssistantLlmError
from ...services.ai_workpoint_resource_initializer import initialize_workpoint_resources
from .scheduling import _materialize_project_master


from ..errors import reject_pavement_feature_request

router = APIRouter(dependencies=[Depends(reject_pavement_feature_request)])


@router.post(
    "/api/ai-resource-assistant/initialize-workpoint-resources",
    response_model=AiWorkpointResourceInitializationResponse,
)
def initialize_workpoint_resources_endpoint(
    payload: AiWorkpointResourceInitializationRequest,
    request: Request,
) -> AiWorkpointResourceInitializationResponse:
    try:
        scenario, _ = _materialize_project_master(payload.scenario, request)
        return initialize_workpoint_resources(scenario)
    except AiResourceAssistantLlmError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/ai-resource-assistant/initialize", response_model=ResourceAssistantInitialResponse)
def initialize_resource_assistant_endpoint(
    payload: ResourceAssistantInitialRequest,
    request: Request,
) -> ResourceAssistantInitialResponse:
    try:
        scenario, _ = _materialize_project_master(payload.scenario, request)
        return initialize_resource_assistant(payload.model_copy(update={"scenario": scenario}))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/ai-resource-assistant/update-plan", response_model=ResourceAssistantUpdatePlanResponse)
def update_resource_plan_endpoint(request: ResourceAssistantUpdatePlanRequest) -> ResourceAssistantUpdatePlanResponse:
    try:
        return update_resource_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/ai-resource-assistant/batch-solve", response_model=ResourceAssistantBatchSolveResponse)
def batch_solve_resource_plans_endpoint(
    payload: ResourceAssistantBatchSolveRequest,
    request: Request,
) -> ResourceAssistantBatchSolveResponse:
    scenario, _ = _materialize_project_master(payload.scenario, request)
    return batch_solve_resource_plans(payload.model_copy(update={"scenario": scenario}))


@router.post("/api/ai-resource-assistant/solve-plan", response_model=ResourceAssistantSingleSolveResponse)
def solve_resource_plan_endpoint(
    payload: ResourceAssistantSingleSolveRequest,
    request: Request,
) -> ResourceAssistantSingleSolveResponse:
    scenario, _ = _materialize_project_master(payload.scenario, request)
    return solve_resource_plan(payload.model_copy(update={"scenario": scenario}))


@router.post("/api/ai-resource-assistant/compare-results", response_model=ResourceAssistantComparison)
def compare_resource_plan_results_endpoint(request: ResourceAssistantResultsRequest) -> ResourceAssistantComparison:
    try:
        return compare_resource_plan_results(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/ai-resource-assistant/generate-recommendation", response_model=ResourceAssistantRecommendationResponse)
def generate_resource_plan_recommendation_endpoint(
    request: ResourceAssistantResultsRequest,
) -> ResourceAssistantRecommendationResponse:
    try:
        return generate_resource_plan_recommendation(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/apply-process-natural-language", response_model=ProcessNlResponse)
def apply_process_natural_language_endpoint(request: ProcessNlRequest) -> ProcessNlResponse:
    return apply_process_natural_language(request.scenario, request.prompt)


@router.post("/api/ai-parameter-assistant/parse", response_model=AiParameterParseResponse)
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


@router.post("/api/ai-parameter-assistant/apply", response_model=AiParameterApplyResponse)
def apply_ai_parameter_assistant_endpoint(request: AiParameterApplyRequest) -> AiParameterApplyResponse:
    try:
        return apply_ai_parameter_suggestions(request)
    except AiParameterAssistantError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
