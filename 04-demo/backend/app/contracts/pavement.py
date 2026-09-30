"""Pavement-only contracts; no implicit project-specific waiting assumptions."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EngineeringDomain = Literal["bridge", "pavement"]
PavementProcessType = Literal["granular_base", "cement_stabilized_base", "asphalt_course"]
PavementHandoverStatus = Literal["dated", "handed_over", "pending"]


class PavementShiftRegime(BaseModel):
    start_date: date
    end_date: date | None = None
    shifts: int = Field(ge=1, le=2, strict=True)

    @model_validator(mode="after")
    def check_range(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("班制区间起始日不能晚于结束日。")
        return self


class PavementOptimization(BaseModel):
    search_workers: int | None = Field(default=None, ge=1)
    lns_enabled: bool | None = None
    time_budget_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    improvement_count: int | None = Field(default=None, ge=0)
    method: Literal["greedy_cpsat"] = "greedy_cpsat"
    initial_strategy: Literal["earliest_start", "longest_chain", "least_transfer"] | None = None
    valid_candidate_count: int = Field(default=0, ge=0)
    initial_days: int | None = Field(default=None, gt=0)
    final_days: int | None = Field(default=None, gt=0)
    improvement_days: int | None = Field(default=None, ge=0)
    selected_source: Literal["greedy", "cp_sat"] | None = None
    optimizer_status: Literal["OPTIMAL", "FEASIBLE", "UNKNOWN", "INFEASIBLE", "MODEL_INVALID"] | None = None
    optimizer_not_run_reason: Literal["budget_exhausted"] | None = None
    outcome: Literal["improved", "initial_retained", "cp_sat_only", "no_plan", "inconsistent"]
    initial_plan_seconds: float = Field(default=0, ge=0)
    model_build_seconds: float = Field(default=0, ge=0)
    cp_sat_seconds: float = Field(default=0, ge=0)
    total_seconds: float = Field(default=0, ge=0)


class PavementIdleOptimization(BaseModel):
    goal: Literal["min_idle_with_makespan_cap"] = "min_idle_with_makespan_cap"
    metric: Literal["fleet_internal_idle_v1"] = "fleet_internal_idle_v1"
    baseline_input_fingerprint: str = Field(min_length=1)
    makespan_cap_days: int = Field(gt=0, strict=True)
    baseline_idle_days: int = Field(ge=0, strict=True)
    final_idle_days: int = Field(ge=0, strict=True)
    improvement_idle_days: int = Field(default=0, ge=0, strict=True)
    baseline_transfer_days: int = Field(ge=0, strict=True)
    final_transfer_days: int = Field(ge=0, strict=True)
    improvement_count: int = Field(default=0, ge=0)
    selected_source: Literal["baseline", "cp_sat"] = "baseline"
    outcome: Literal["baseline_retained", "improved", "inconsistent"] = "baseline_retained"
    optimizer_status: Literal["OPTIMAL", "FEASIBLE", "UNKNOWN", "INFEASIBLE", "MODEL_INVALID"] | None = None
    optimizer_not_run_reason: Literal["budget_exhausted", "zero_idle"] | None = None
    proved_optimal: bool = False
    search_workers: int | None = Field(default=None, ge=1)
    lns_enabled: bool | None = None
    time_budget_seconds: float = Field(gt=0, allow_inf_nan=False)
    model_build_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    cp_sat_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    total_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)


class PavementBlockedSection(BaseModel):
    structure_id: str
    section_name: str
    reason: str
    component_ids: list[str] = Field(default_factory=list)


class PavementHandoverScope(BaseModel):
    total_section_count: int = Field(default=0, ge=0)
    included_section_count: int = Field(default=0, ge=0)
    included_layer_count: int = Field(default=0, ge=0)
    blocked_sections: list[PavementBlockedSection] = Field(default_factory=list)
    pending_policy: Literal["strict_last", "per_fleet_last"] | None = Field(default=None, exclude_if=lambda value: value is None)
    pending_sections: list["PavementPendingSection"] | None = Field(default=None, exclude_if=lambda value: value is None)


class PavementPendingSection(BaseModel):
    structure_id: str
    section_name: str
    reason: str
    component_ids: list[str] = Field(default_factory=list)


class PavementPendingSectionDates(BaseModel):
    structure_id: str
    required_handover_date: date
    estimated_finish_date: date


class PavementLayerCondition(BaseModel):
    component_id: str
    wait_days: int = Field(ge=0)
    accepted_available_date: date | None = None
    basis_note: str = Field(min_length=1)


class PavementAncillaryStep(BaseModel):
    id: str
    structure_id: str
    before_component_id: str
    kind: Literal["prime", "seal", "tack", "other_preparation"]
    name: str
    duration_days: int = Field(ge=0)
    wait_after_days: int = Field(ge=0)
    available_date: date | None = None
    order: int = Field(ge=0)
    basis_note: str = Field(min_length=1)


class PavementFixedSequence(BaseModel):
    process_type: PavementProcessType
    component_ids: list[str] = Field(min_length=2)


class PavementDependencyRule(BaseModel):
    structure_id: str | None = Field(default=None, min_length=1)
    predecessor_key: str = Field(min_length=1)
    successor_key: str = Field(min_length=1)
    relationship: Literal["FS", "SS", "FF", "SF"] = "FS"
    lag_days: int | None = Field(default=None, ge=0, strict=True)


class PavementSettings(BaseModel):
    layer_conditions: list[PavementLayerCondition] = Field(default_factory=list)
    ancillary_steps: list[PavementAncillaryStep] = Field(default_factory=list)
    fixed_sequences: list[PavementFixedSequence] = Field(default_factory=list)
    input_kind: Literal["customer", "demo"] = "customer"
    dependency_rules: list[PavementDependencyRule] = Field(default_factory=list)
    shift_regimes: list[PavementShiftRegime] = Field(default_factory=list)


class PavementTaskContext(BaseModel):
    process_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    source_component_id: str
    position_id: str
    task_kind: Literal["construction", "preparation"]
    process_type: PavementProcessType
    quantity_basis: str
    input_kind: Literal["customer", "demo"]


class PavementReadinessCondition(BaseModel):
    id: str
    terminal_task_id: str
    source_component_id: str
    wait_days: int = Field(ge=0)
    available_offset: int = Field(default=0, ge=0)


class PavementReadiness(PavementReadinessCondition):
    position_id: str
    ready_offset: int
    ready_date: date


class PavementWaitInterval(BaseModel):
    source_component_id: str
    start_offset: int
    end_offset: int
    reason: str


class PavementTransfer(BaseModel):
    resource_id: str
    from_task_id: str
    to_task_id: str
    from_position_id: str
    to_position_id: str
    start_offset: int
    end_offset: int


class PavementSummary(BaseModel):
    input_kind: Literal["customer", "demo"]
    input_fingerprint: str
    project_data_version_id: str | None = None
    construction_finish_offset: int
    construction_finish_date: date
    ready_offset: int
    ready_date: date
    readiness: list[PavementReadiness] = Field(default_factory=list)
    wait_intervals: list[PavementWaitInterval] = Field(default_factory=list)
    transfers: list[PavementTransfer] = Field(default_factory=list)
    resource_assumptions: list[str] = Field(default_factory=list)
    pending_section_dates: list[PavementPendingSectionDates] | None = Field(default=None, exclude_if=lambda value: value is None)
