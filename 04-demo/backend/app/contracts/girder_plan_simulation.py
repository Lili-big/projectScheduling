"""Contracts for the independent girder plan simulation capability."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


DiagnosticLevel = Literal["info", "warning", "error"]
ReadinessStatus = Literal["ready", "warning", "blocking"]
ScenarioStatus = Literal["draft", "ready", "calculated", "confirmed", "stale", "blocked"]
RunStatus = Literal["calculated", "blocked", "stale", "confirmed"]
NodeSide = Literal["left", "right", "unknown"]


class SimulationDiagnostic(BaseModel):
    level: DiagnosticLevel
    code: str
    message: str
    subject_id: str | None = None
    subject_type: str | None = None
    entity_refs: list[str] = Field(default_factory=list)
    suggestion: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_constructor(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        severity = normalized.pop("severity", None)
        if "level" not in normalized:
            normalized["level"] = "error" if severity == "blocking" else (severity or "info")
        if "subject_id" not in normalized:
            normalized["subject_id"] = normalized.pop("object_id", None)
        if "subject_type" not in normalized:
            normalized["subject_type"] = normalized.pop("object_type", None)
        return normalized

    @property
    def severity(self) -> str:
        return "blocking" if self.level == "error" else "warning"

    @property
    def object_id(self) -> str:
        return self.subject_id or (self.entity_refs[0] if self.entity_refs else "")

    @property
    def object_type(self) -> str:
        return self.subject_type or "entity"


class BeamDemand(BaseModel):
    beam_type_id: str
    beam_type_name: str
    span_count: int = Field(ge=1)
    beam_count: int = Field(ge=1)
    span_refs: list[str] = Field(min_length=1)

    @property
    def pieces(self) -> int:
        return self.beam_count


class LineGraphNode(BaseModel):
    node_id: str
    project_master_workpoint_id: str | None = None
    name: str
    node_type: Literal["yard", "bridge", "roadbed", "tunnel", "culvert", "access", "connection"]
    side: Literal["left", "right", "unknown"] = "unknown"
    alignment_code: str | None = None
    start_mileage_m: float | None = None
    end_mileage_m: float | None = None
    sort_order: int = Field(default=0, ge=0)
    requires_erection: bool = False
    beam_demands: list[BeamDemand] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    current_plan_finish_date: date | None = None


class ConnectionConfirmation(BaseModel):
    reason: str = Field(min_length=1)
    confirmed_by: str = Field(min_length=1)
    confirmed_at: datetime

    @field_validator("reason", "confirmed_by")
    @classmethod
    def confirmation_text_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("人工连接确认人和原因不能为空。")
        return value


class LineGraphEdge(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    direction: Literal["forward", "reverse", "bidirectional"] = "bidirectional"
    source: Literal["alignment_adjacency", "manual_connection"] = "alignment_adjacency"
    transfer_days: int = Field(default=0, ge=0)
    confirmation: ConnectionConfirmation | None = None


class LineGraphSnapshot(BaseModel):
    line_graph_id: str
    project_id: str
    project_master_version_id: str
    input_fingerprint: str
    projection_version: Literal["girder-plan-line-graph/v1"] = "girder-plan-line-graph/v1"
    status: ReadinessStatus
    nodes: list[LineGraphNode] = Field(default_factory=list)
    edges: list[LineGraphEdge] = Field(default_factory=list)
    diagnostics: list[SimulationDiagnostic] = Field(default_factory=list)


class BeamTypeCapacity(BaseModel):
    beam_type_id: str
    daily_capacity_pieces: int = Field(ge=0)
    initial_inventory_pieces: int = Field(default=0, ge=0)
    max_inventory_pieces: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def inventory_not_above_capacity(self):
        if self.max_inventory_pieces is not None and self.initial_inventory_pieces > self.max_inventory_pieces:
            raise ValueError("期初库存不能大于最大库存。")
        return self


class BeamYardPlan(BaseModel):
    beam_yard_id: str
    name: str = Field(min_length=1)
    alignment_code: str = Field(min_length=1)
    mileage_m: float
    production_start_date: date
    capacities: list[BeamTypeCapacity] = Field(default_factory=list)
    enabled: bool = True


class ErectionLinePlan(BaseModel):
    erection_line_id: str
    beam_yard_id: str
    available_date: date
    daily_erection_capacity_pieces: int = Field(ge=0)
    first_erection_preparation_days: int = Field(default=0, ge=0)
    bridge_transfer_days: int = Field(default=0, ge=0)
    side_switch_days: int = Field(default=0, ge=0)
    enabled: bool = True


class ConfirmedPathSegment(BaseModel):
    from_target_node_id: str
    to_target_node_id: str
    edge_ids: list[str] = Field(min_length=1)
    source: Literal["unique_auto_path", "user_selected_path"]


class ManualRoutePlan(BaseModel):
    route_plan_id: str
    beam_yard_id: str
    erection_line_id: str
    name: str
    target_node_ids: list[str] = Field(default_factory=list)
    confirmed_paths: list[ConfirmedPathSegment] = Field(default_factory=list)
    confirmed: bool = False


class GirderPlanSimulationParameters(BaseModel):
    default_transfer_days: int = Field(default=1, ge=0)
    bridge_readiness_buffer_days: int = Field(default=3, ge=0)
    roadbed_passage_buffer_days: int = Field(default=2, ge=0)
    tunnel_passage_buffer_days: int = Field(default=2, ge=0)
    access_passage_buffer_days: int = Field(default=1, ge=0)
    post_erection_passage_buffer_days: int = Field(default=1, ge=0)
    planning_horizon_end_date: date
    same_day_production_available: Literal[False] = False


class CreateScenarioVersionRequest(BaseModel):
    scenario_id: str | None = None
    project_id: str
    project_master_version_id: str
    line_graph_id: str
    expected_latest_version_no: int | None = Field(default=None, ge=1)
    beam_yards: list[BeamYardPlan] = Field(default_factory=list)
    erection_lines: list[ErectionLinePlan] = Field(default_factory=list)
    route_plans: list[ManualRoutePlan] = Field(default_factory=list)
    connection_overrides: list[LineGraphEdge] = Field(default_factory=list)
    parameters: GirderPlanSimulationParameters
    created_by: str = Field(min_length=1)

    @field_validator("created_by")
    @classmethod
    def creator_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("创建人不能为空。")
        return value


class GirderPlanScenarioVersion(CreateScenarioVersionRequest):
    scenario_version_id: str
    scenario_id: str
    version_no: int = Field(ge=1)
    status: ScenarioStatus
    input_fingerprint: str
    created_at: datetime
    stale_reason: str | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    confirmation_reason: str | None = None


class ExpectedFingerprintRequest(BaseModel):
    expected_input_fingerprint: str


class ReadinessCheck(BaseModel):
    code: str
    status: Literal["passed", "warning", "blocking"]
    message: str
    entity_refs: list[str] = Field(default_factory=list)


class GirderPlanReadiness(BaseModel):
    status: ReadinessStatus
    checks: list[ReadinessCheck] = Field(default_factory=list)
    diagnostics: list[SimulationDiagnostic] = Field(default_factory=list)
    expanded_routes: dict[str, list[str]] = Field(default_factory=dict)


class CreateSimulationRunRequest(BaseModel):
    scenario_version_id: str
    expected_input_fingerprint: str
    force_recompute: bool = False


class DailyBeamConsumption(BaseModel):
    date: date
    beam_type_id: str
    erected_pieces: int = Field(ge=0)


class BridgeErectionSchedule(BaseModel):
    target_node_id: str
    beam_yard_id: str
    route_plan_id: str
    sequence_index: int = Field(ge=0)
    start_date: date
    finish_date: date
    total_beam_count: int = Field(ge=1)
    beam_type_counts: dict[str, int] = Field(default_factory=dict)
    daily_erection: list[DailyBeamConsumption] = Field(default_factory=list)
    controlling_factors: list[Literal["line_available", "supply", "transfer", "side_switch", "cross_route_passage"]] = Field(default_factory=list)


class YardInventoryLedgerEntry(BaseModel):
    date: date
    beam_yard_id: str
    beam_type_id: str
    opening_inventory_pieces: int = Field(ge=0)
    produced_pieces: int = Field(ge=0)
    erected_pieces: int = Field(ge=0)
    closing_inventory_pieces: int = Field(ge=0)


class PlannedRouteRun(BaseModel):
    route_plan_id: str
    beam_yard_id: str
    start_date: date
    finish_date: date
    expanded_node_ids: list[str] = Field(default_factory=list)
    waiting_days_by_reason: dict[str, int] = Field(default_factory=dict)


class RouteDeliveryRequirement(BaseModel):
    route_plan_id: str
    required_date: date
    buffer_days: int = Field(ge=0)
    source: str


class WorkpointDeliveryControl(BaseModel):
    node_id: str
    project_master_workpoint_id: str
    side: Literal["left", "right", "unknown"]
    first_required_date: date
    latest_delivery_date: date
    buffer_days: int = Field(ge=0)
    controlling_source: Literal[
        "erection_start",
        "roadbed_passage",
        "tunnel_passage",
        "access_passage",
        "post_erection_passage",
    ]
    route_requirements: list[RouteDeliveryRequirement] = Field(default_factory=list)
    current_plan_finish_date: date | None = None
    late_days: int | None = Field(default=None, ge=0)
    risk_status: Literal["unknown", "on_time", "late"]


class GirderPlanSimulationRun(BaseModel):
    run_id: str
    scenario_version_id: str
    project_master_version_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    input_fingerprint: str
    result_fingerprint: str
    reused_from_run_id: str | None = None
    bridge_schedules: list[BridgeErectionSchedule] = Field(default_factory=list)
    inventory_ledger: list[YardInventoryLedgerEntry] = Field(default_factory=list)
    route_runs: list[PlannedRouteRun] = Field(default_factory=list)
    workpoint_controls: list[WorkpointDeliveryControl] = Field(default_factory=list)
    diagnostics: list[SimulationDiagnostic] = Field(default_factory=list)
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    confirmation_reason: str | None = None


class ConfirmSimulationRunRequest(BaseModel):
    expected_input_fingerprint: str
    confirmed_by: str = Field(min_length=1)
    confirmation_reason: str = Field(min_length=1)

    @field_validator("confirmed_by", "confirmation_reason")
    @classmethod
    def confirmation_audit_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("确认人和确认原因不能为空。")
        return value


__all__ = [name for name in globals() if not name.startswith("_")]
