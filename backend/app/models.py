from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


StructureType = Literal["pier", "abutment"]
ComponentType = Literal[
    "pile",
    "cap",
    "spread_foundation",
    "ground_tie_beam",
    "middle_tie_beam",
    "pier_body",
    "cap_beam",
    "abutment_body",
]
WorkPointType = Literal["road", "bridge", "tunnel"]
WorkSectionSide = Literal["left", "right", "none"]
DurationMethod = Literal["units_per_day", "days_per_unit", "fixed_days"]
PredecessorStrategy = Literal["all", "first_available"]
RelationshipType = Literal["FS", "SS"]
LogicScope = Literal["same_structure", "structure_sequence"]
LogicSeverity = Literal["error", "warning"]
PileMethod = Literal["rotary_drill", "impact_drill", "manual_pile"]
MilestoneLevel = Literal["contract", "control", "internal"]
MilestoneMode = Literal["hard", "soft"]
MilestoneScopeType = Literal["project", "bridge", "work_section", "structure", "component"]
MilestoneTargetEvent = Literal["start", "finish"]


class PierConfig(BaseModel):
    pier_no: int = Field(ge=1)
    pile_count: int = Field(ge=0)
    pile_length_m: float = Field(gt=0)
    pile_diameter_m: float = Field(gt=0)
    pier_height_m: float = Field(gt=0)
    pile_method: PileMethod = "rotary_drill"
    use_manual_pile: bool = False
    has_cap: bool = True
    has_cap_beam: bool = True

    @model_validator(mode="after")
    def sync_legacy_manual_pile(self) -> "PierConfig":
        if self.use_manual_pile and self.pile_method == "rotary_drill":
            self.pile_method = "manual_pile"
        return self


class AbutmentConfig(BaseModel):
    id: str
    name: str
    pile_count: int = Field(ge=0)
    pile_length_m: float = Field(gt=0)
    pile_diameter_m: float = Field(gt=0)
    body_height_m: float = Field(gt=0)
    pile_method: PileMethod = "rotary_drill"
    use_manual_pile: bool = False
    has_cap: bool = True

    @model_validator(mode="after")
    def sync_legacy_manual_pile(self) -> "AbutmentConfig":
        if self.use_manual_pile and self.pile_method == "rotary_drill":
            self.pile_method = "manual_pile"
        return self


class BridgeModel(BaseModel):
    project_name: str
    start_date: date
    bridge_name: str
    piers: list[PierConfig]
    abutments: list[AbutmentConfig]


class ProductivityRule(BaseModel):
    id: str
    component_type: ComponentType
    process_name: str
    group_name: str
    duration_method: DurationMethod
    quantity_source: str
    productivity_value: float = Field(gt=0)
    productivity_unit: str
    resource_type: str
    is_default: bool = False


class ProductivityOption(BaseModel):
    id: str
    name: str
    duration_method: DurationMethod
    quantity_source: str
    productivity_value: float = Field(gt=0)
    productivity_unit: str
    is_default: bool = False


class LogicRule(BaseModel):
    id: str
    scope: LogicScope = "same_structure"
    structure_type: StructureType | None = None
    to_component: ComponentType
    predecessor_candidates: list[ComponentType] = Field(min_length=1)
    predecessor_strategy: PredecessorStrategy = "first_available"
    relationship: RelationshipType = "FS"
    lag_days: int = Field(ge=0)
    severity: LogicSeverity = "error"
    note: str = ""


class Resource(BaseModel):
    id: str
    name: str
    type: str
    pool_id: str | None = None
    pool_label: str | None = None
    enabled: bool = True
    calendar_id: str = "continuous"


class Task(BaseModel):
    id: str
    name: str
    bridge_id: str | None = None
    work_section_id: str | None = None
    component_id: str | None = None
    sequence_order: int = 0
    structure_id: str
    structure_name: str
    structure_type: StructureType
    component_type: ComponentType
    process_name: str
    productivity_rule_id: str
    quantity: float
    quantity_label: str
    duration_days: int = Field(ge=1)
    compatible_resource_types: list[str] = Field(min_length=1)


class PrecedenceLink(BaseModel):
    id: str
    predecessor_id: str
    successor_id: str
    relationship: RelationshipType = "FS"
    lag_days: int = Field(ge=0)
    source_rule_id: str
    severity: LogicSeverity = "error"


class ValidationMessage(BaseModel):
    level: Literal["info", "warning", "error"]
    message: str
    subject_id: str | None = None


class ComponentModel(BaseModel):
    id: str
    name: str
    component_type: ComponentType
    quantity: float = Field(ge=0)
    quantity_label: str = ""
    method_id: str | None = None
    productivity_option_id: str | None = None
    enabled: bool = True
    properties: dict[str, Any] = {}


class StructureModel(BaseModel):
    id: str
    name: str
    structure_type: StructureType
    order: int = 0
    support_no: str | None = None
    support_index: int | None = None
    components: list[ComponentModel] = []


class UpperStructureComponent(BaseModel):
    id: str
    name: str
    structure_type: str
    side: WorkSectionSide = "none"
    span_index: int
    support_range: str
    span_length_m: float
    beam_count_per_span: int | None = None
    span_group_expression: str
    properties: dict[str, Any] = {}


class WorkSection(BaseModel):
    id: str
    name: str
    order: int = 0
    side: WorkSectionSide = "none"
    structures: list[StructureModel] = []
    upper_structures: list[UpperStructureComponent] = []


class ProjectBridge(BaseModel):
    id: str
    name: str
    order: int = 0
    workpoint_type: WorkPointType = "bridge"
    import_source: dict[str, Any] = {}
    work_sections: list[WorkSection] = []


class ProjectModel(BaseModel):
    project_id: str
    project_name: str
    start_date: date
    bridges: list[ProjectBridge] = []


class ProcessTemplate(BaseModel):
    id: str
    component_type: ComponentType
    process_name: str
    method_id: str | None = None
    duration_method: DurationMethod
    quantity_source: str
    productivity_value: float = Field(gt=0)
    productivity_unit: str
    resource_type: str
    productivity_options: list[ProductivityOption] = Field(default_factory=list)
    applicability: dict[str, Any] = {}
    is_default: bool = False

    @model_validator(mode="after")
    def ensure_default_productivity_option(self) -> "ProcessTemplate":
        if not self.productivity_options:
            self.productivity_options = [
                ProductivityOption(
                    id=f"{self.id}-default",
                    name="默认工效",
                    duration_method=self.duration_method,
                    quantity_source=self.quantity_source,
                    productivity_value=self.productivity_value,
                    productivity_unit=self.productivity_unit,
                    is_default=True,
                )
            ]
            return self

        default_index = next((index for index, option in enumerate(self.productivity_options) if option.is_default), 0)
        for index, option in enumerate(self.productivity_options):
            option.is_default = index == default_index
        default_option = self.productivity_options[default_index]
        self.duration_method = default_option.duration_method
        self.quantity_source = default_option.quantity_source
        self.productivity_value = default_option.productivity_value
        self.productivity_unit = default_option.productivity_unit
        return self


class ResourceCalendar(BaseModel):
    id: str
    name: str
    working_weekdays: list[int] = [0, 1, 2, 3, 4, 5, 6]
    blackout_dates: list[date] = []


class ResourcePool(BaseModel):
    id: str
    type: str
    label: str
    quantity: int = Field(ge=0)
    max_quantity: int | None = Field(default=None, ge=0)
    calendar_id: str = "continuous"
    enabled: bool = True
    compatible_process_ids: list[str] = []

    @model_validator(mode="after")
    def ensure_max_quantity(self) -> "ResourcePool":
        if self.max_quantity is None or self.max_quantity < self.quantity:
            self.max_quantity = self.quantity
        return self


class MilestoneConstraint(BaseModel):
    id: str
    name: str
    level: MilestoneLevel = "internal"
    mode: MilestoneMode = "soft"
    scope_type: MilestoneScopeType = "project"
    scope_id: str | None = None
    target_event: MilestoneTargetEvent = "finish"
    target_date: date
    penalty_per_day: int = Field(default=10, ge=0)


class MilestoneResult(BaseModel):
    id: str
    name: str
    level: MilestoneLevel
    mode: MilestoneMode
    scope_type: MilestoneScopeType
    scope_id: str | None = None
    target_event: MilestoneTargetEvent
    target_date: date
    actual_date: date | None = None
    actual_offset: int | None = None
    lateness_days: int = 0
    penalty: int = 0
    status: Literal["met", "late", "not_evaluated"] = "not_evaluated"


class ScenarioInput(BaseModel):
    scenario_id: str
    scenario_name: str
    project: ProjectModel
    process_library: list[ProcessTemplate]
    logic_rules: list[LogicRule]
    resource_calendars: list[ResourceCalendar] = []
    resource_pools: list[ResourcePool]
    milestones: list[MilestoneConstraint] = []
    time_limit_seconds: float = Field(default=10.0, gt=0)


class ProcessNlRequest(BaseModel):
    scenario: ScenarioInput
    prompt: str


class ProcessNlChange(BaseModel):
    action: str
    process_id: str | None = None
    process_name: str | None = None
    matched_count: int = 0
    targets: list[str] = []
    message: str


class ProcessNlResponse(BaseModel):
    scenario: ScenarioInput
    changes: list[ProcessNlChange]
    warnings: list[str] = []


class ProcessLibrarySaveRequest(BaseModel):
    process_library: list[ProcessTemplate] = Field(min_length=1)


class WbsRequest(BaseModel):
    bridge: BridgeModel
    productivity_rules: list[ProductivityRule]
    logic_rules: list[LogicRule]


class WbsResponse(BaseModel):
    tasks: list[Task]
    precedence_links: list[PrecedenceLink]
    validation: list[ValidationMessage]


class ScheduleInput(BaseModel):
    project_name: str
    start_date: date
    tasks: list[Task]
    precedence_links: list[PrecedenceLink]
    resources: list[Resource]
    milestones: list[MilestoneConstraint] = []
    time_limit_seconds: float = Field(default=10.0, gt=0)


class ScheduledTask(Task):
    start_offset: int
    end_offset: int
    start_date: date
    finish_date: date
    assigned_resource_id: str | None = None
    assigned_resource_name: str | None = None
    assigned_resource_type: str | None = None
    predecessor_ids: list[str] = []


class ResourceAllocation(BaseModel):
    resource_id: str
    resource_name: str
    resource_type: str
    task_id: str
    task_name: str
    start_offset: int
    end_offset: int
    start_date: date
    finish_date: date


class ScheduleResult(BaseModel):
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"]
    objective_days: int | None = None
    plan_start_date: date
    plan_finish_date: date | None = None
    tasks: list[ScheduledTask] = []
    resource_allocations: list[ResourceAllocation] = []
    milestone_results: list[MilestoneResult] = []
    validation: list[ValidationMessage] = []
    stats: dict[str, Any] = {}
    objective_breakdown: dict[str, Any] = {}


class GeneratedScheduleInput(BaseModel):
    schedule_input: ScheduleInput
    validation: list[ValidationMessage] = []
    source_summary: dict[str, Any] = {}


class ScenarioSolveResult(BaseModel):
    scenario_id: str
    scenario_name: str
    generated: GeneratedScheduleInput
    result: ScheduleResult
    milestone_results: list[MilestoneResult] = []
    diagnostics: list[ValidationMessage] = []
    metrics: dict[str, Any] = {}


class ScenarioCompareRequest(BaseModel):
    results: list[ScenarioSolveResult]


class MinResourcesSolveRequest(BaseModel):
    scenario: ScenarioInput
    fallback_target_days: int | None = Field(default=None, ge=1)


class ScenarioCompareResponse(BaseModel):
    summaries: list[dict[str, Any]]
    best_scenario_id: str | None = None
    notes: list[str] = []


class ImportBridgeParamsResponse(BaseModel):
    scenario: ScenarioInput
    canonical_bridge: dict[str, Any]
    summary: dict[str, Any]
    quality_checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []


class DemoPayload(BaseModel):
    bridge: BridgeModel
    productivity_rules: list[ProductivityRule]
    logic_rules: list[LogicRule]
    resources: list[Resource]
    wbs: WbsResponse
