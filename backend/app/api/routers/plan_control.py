from __future__ import annotations

from fastapi import APIRouter

from ..errors import plan_control_http_error
from ...contracts import (
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
)
from ...plan_control.repository import PlanControlRepositoryError, default_plan_control_repository
from ...plan_control.forecasting import (
    PlanControlValidationError,
    adopt_adjustment,
    create_adjustment_proposals,
    create_baseline_plan,
    create_forecast,
    create_progress_snapshot,
)


router = APIRouter()


@router.post("/api/plan-control/baselines", response_model=PlanVersion)
def create_baseline_plan_endpoint(request: CreateBaselinePlanRequest) -> PlanVersion:
    try:
        return create_baseline_plan(request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise plan_control_http_error(exc) from exc


@router.get("/api/plan-control/projects/{project_id}", response_model=PlanControlProjectSummary)
def get_plan_control_project_endpoint(project_id: str) -> PlanControlProjectSummary:
    try:
        return default_plan_control_repository.project_summary(project_id)
    except PlanControlRepositoryError as exc:
        raise plan_control_http_error(exc) from exc


@router.post("/api/plan-control/progress-snapshots", response_model=CreateProgressSnapshotResponse)
def create_progress_snapshot_endpoint(request: CreateProgressSnapshotRequest) -> CreateProgressSnapshotResponse:
    try:
        return create_progress_snapshot(request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise plan_control_http_error(exc) from exc


@router.post("/api/plan-control/forecasts", response_model=ForecastSchedule)
def create_forecast_endpoint(request: CreateForecastRequest) -> ForecastSchedule:
    try:
        return create_forecast(request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise plan_control_http_error(exc) from exc


@router.post(
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
        raise plan_control_http_error(exc) from exc


@router.post("/api/plan-control/adjustments/{proposal_id}/adopt", response_model=AdoptAdjustmentResponse)
def adopt_adjustment_endpoint(proposal_id: str, request: AdoptAdjustmentRequest) -> AdoptAdjustmentResponse:
    try:
        return adopt_adjustment(proposal_id, request)
    except (PlanControlValidationError, PlanControlRepositoryError) as exc:
        raise plan_control_http_error(exc) from exc
