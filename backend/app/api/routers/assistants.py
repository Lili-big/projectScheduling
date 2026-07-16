from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..multipart import parse_multipart_request
from ...contracts import (
    AiParameterApplyRequest,
    AiParameterApplyResponse,
    AiParameterParseResponse,
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


router = APIRouter()


@router.post("/api/ai-resource-assistant/initialize", response_model=ResourceAssistantInitialResponse)
def initialize_resource_assistant_endpoint(request: ResourceAssistantInitialRequest) -> ResourceAssistantInitialResponse:
    try:
        return initialize_resource_assistant(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/ai-resource-assistant/update-plan", response_model=ResourceAssistantUpdatePlanResponse)
def update_resource_plan_endpoint(request: ResourceAssistantUpdatePlanRequest) -> ResourceAssistantUpdatePlanResponse:
    try:
        return update_resource_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/ai-resource-assistant/batch-solve", response_model=ResourceAssistantBatchSolveResponse)
def batch_solve_resource_plans_endpoint(request: ResourceAssistantBatchSolveRequest) -> ResourceAssistantBatchSolveResponse:
    return batch_solve_resource_plans(request)


@router.post("/api/ai-resource-assistant/solve-plan", response_model=ResourceAssistantSingleSolveResponse)
def solve_resource_plan_endpoint(request: ResourceAssistantSingleSolveRequest) -> ResourceAssistantSingleSolveResponse:
    return solve_resource_plan(request)


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
