from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


StructureType = Literal["pier", "abutment", "upper_structure", "continuous_beam"]
ComponentType = Literal[
    "pile",
    "cap",
    "spread_foundation",
    "ground_tie_beam",
    "middle_tie_beam",
    "pier_body",
    "cap_beam",
    "abutment_body",
    "precast_beam",
    "beam_erection",
    "cast_in_place_continuous_beam",
    "cast_in_place_box_beam",
    "steel_box_beam",
    "bridge_deck_system",
]
WorkPointType = Literal["road", "bridge", "tunnel"]
WorkSectionSide = Literal["left", "right", "none"]
DurationMethod = Literal["units_per_day", "days_per_unit", "fixed_days"]
_PILE_PRODUCTIVITY_UNIT_RULES: dict[str, tuple[DurationMethod, str]] = {
    "m/天": ("units_per_day", "pile_length_m"),
    "根/天": ("units_per_day", "count"),
    "天/根": ("fixed_days", "count"),
    "天/m": ("days_per_unit", "pile_length_m"),
}
PredecessorStrategy = Literal["all", "first_available"]
RelationshipType = Literal["FS", "SS", "FF", "SF"]
LogicScope = Literal["same_structure", "structure_sequence"]
LogicSeverity = Literal["error", "warning"]
PileMethod = Literal["rotary_drill", "impact_drill", "manual_pile"]
ResourceMode = Literal["LIMITED", "UNLIMITED"]
ResourceCostType = Literal["none", "monthly_rental", "one_time_purchase"]
MilestoneLevel = Literal["contract", "control", "internal"]
MilestoneMode = Literal["hard", "soft"]
MilestoneScopeType = Literal["project", "bridge", "work_section", "structure", "component"]
MilestoneTargetEvent = Literal["start", "finish"]
ScheduleStrategy = Literal[
    "shortest_duration",
    "min_resource",
    "resource_cost",
    "control_priority",
    "balanced_normal",
    "comprehensive",
]
ControlLevel = Literal["control", "key", "normal", "rough"]
ResourceGuaranteeMode = Literal["strict", "priority", "off"]
BalanceBucket = Literal["week", "month"]
ObjectiveTermId = Literal[
    "control_node_late",
    "control_buffer_risk",
    "risk_related_control_wait",
    "same_structure_craft_split",
    "resource_workload_balance",
    "resource_idle",
    "resource_path_continuity",
    "makespan_and_soft_milestone",
    "normal_balance",
    "spatial_resource_assignment",
]

OBJECTIVE_TERM_MAX_WEIGHT = 1_000_000_000
DEFAULT_OBJECTIVE_TERM_WEIGHTS: dict[ObjectiveTermId, int] = {
    "control_node_late": 1_000_000_000,
    "control_buffer_risk": 1_000_000,
    "risk_related_control_wait": 1_000_000,
    "same_structure_craft_split": 100_000,
    "resource_workload_balance": 20_000,
    "resource_idle": 2_000,
    "resource_path_continuity": 500,
    "makespan_and_soft_milestone": 100,
    "normal_balance": 1,
    "spatial_resource_assignment": 1,
}
OBJECTIVE_TERM_IDS = tuple(DEFAULT_OBJECTIVE_TERM_WEIGHTS.keys())


class ObjectiveTermConfig(BaseModel):
    enabled: bool = True
    weight: int = Field(ge=0, le=OBJECTIVE_TERM_MAX_WEIGHT)


def default_objective_terms() -> dict[ObjectiveTermId, ObjectiveTermConfig]:
    return {
        term_id: ObjectiveTermConfig(enabled=True, weight=weight)
        for term_id, weight in DEFAULT_OBJECTIVE_TERM_WEIGHTS.items()
    }


def effective_objective_weights(
    objective_terms: Mapping[str, ObjectiveTermConfig] | None,
) -> dict[ObjectiveTermId, int]:
    terms = objective_terms or default_objective_terms()
    return {
        term_id: terms[term_id].weight if terms[term_id].enabled else 0
        for term_id in DEFAULT_OBJECTIVE_TERM_WEIGHTS
    }


def objective_terms_used(
    objective_terms: Mapping[str, ObjectiveTermConfig] | None,
) -> dict[ObjectiveTermId, dict[str, int | bool]]:
    terms = objective_terms or default_objective_terms()
    weights = effective_objective_weights(terms)
    return {
        term_id: {
            "enabled": terms[term_id].enabled,
            "weight": terms[term_id].weight,
            "effective_weight": weights[term_id],
        }
        for term_id in DEFAULT_OBJECTIVE_TERM_WEIGHTS
    }


class ScheduleStrategyConfig(BaseModel):
    strategy: ScheduleStrategy = "comprehensive"
    resource_guarantee: ResourceGuaranteeMode = "priority"
    normal_balance_bucket: BalanceBucket = "month"
    normal_earliest_start_offset: int = Field(default=0, ge=0)
    normal_latest_finish_offset: int | None = Field(default=None, ge=1)
    normal_max_early_finish_days: int = Field(default=60, ge=0)
    max_parallel_normal_per_work_section: int = Field(default=5, ge=1)
    enable_balance_objective: bool = True
    objective_terms: dict[ObjectiveTermId, ObjectiveTermConfig] = Field(default_factory=default_objective_terms)

    @model_validator(mode="before")
    @classmethod
    def merge_objective_terms(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data

        values = dict(data)
        raw_terms = values.get("objective_terms")
        explicit_terms = raw_terms is not None
        if raw_terms is None:
            raw_terms = {}
        if not isinstance(raw_terms, Mapping):
            raise ValueError("objective_terms must be an object keyed by objective term id")

        unknown_terms = sorted(set(raw_terms) - set(DEFAULT_OBJECTIVE_TERM_WEIGHTS))
        if unknown_terms:
            raise ValueError(f"unknown objective_terms: {', '.join(str(term) for term in unknown_terms)}")

        merged: dict[str, dict[str, Any]] = {}
        for term_id, default_weight in DEFAULT_OBJECTIVE_TERM_WEIGHTS.items():
            raw_config = raw_terms.get(term_id, {})
            if isinstance(raw_config, ObjectiveTermConfig):
                raw_config = raw_config.model_dump()
            if not isinstance(raw_config, Mapping):
                raise ValueError(f"objective_terms.{term_id} must be an object")

            merged[term_id] = {
                "enabled": raw_config.get("enabled", True),
                "weight": raw_config.get("weight", default_weight),
            }

        if not explicit_terms or "normal_balance" not in raw_terms:
            if values.get("enable_balance_objective") is False:
                merged["normal_balance"]["enabled"] = False

        values["objective_terms"] = merged
        return values

    @model_validator(mode="after")
    def validate_objective_terms(self) -> "ScheduleStrategyConfig":
        invalid_enabled_terms = [
            term_id
            for term_id, term in self.objective_terms.items()
            if term.enabled and term.weight < 1
        ]
        if invalid_enabled_terms:
            raise ValueError(
                "enabled objective term weights must be between 1 and "
                f"{OBJECTIVE_TERM_MAX_WEIGHT}: {', '.join(invalid_enabled_terms)}"
            )
        if not any(term.enabled for term in self.objective_terms.values()):
            raise ValueError("at least one objective term must be enabled")
        self.enable_balance_objective = self.objective_terms["normal_balance"].enabled
        return self


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
    standard_section_height_m: float | None = Field(default=None, gt=0)
    resource_type: str
    is_default: bool = False


class ProductivityOption(BaseModel):
    id: str
    name: str
    duration_method: DurationMethod
    quantity_source: str
    productivity_value: float = Field(gt=0)
    productivity_unit: str
    standard_section_height_m: float | None = Field(default=None, gt=0)
    is_default: bool = False

    @model_validator(mode="after")
    def ensure_standard_section_height(self) -> "ProductivityOption":
        if self.productivity_unit == "天/节" and self.standard_section_height_m is None:
            self.standard_section_height_m = 4.5
        return self


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


class UpperStructureLogicRule(BaseModel):
    id: str
    relationship: RelationshipType = "FS"
    lag_days: int = Field(default=0, ge=0)
    max_finish_gap_days: int | None = Field(default=None, ge=0)
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
    same_structure_resource_binding: bool = False
    same_structure_parallel_limit: int | None = Field(default=None, ge=1)
    parallel_rule_description: str = ""


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
    control_level: ControlLevel = "normal"
    component_type: ComponentType
    process_name: str
    productivity_rule_id: str
    quantity: float
    quantity_label: str
    duration_days: int = Field(ge=1)
    compatible_resource_types: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = {}


class PrecedenceLink(BaseModel):
    id: str
    predecessor_id: str
    successor_id: str
    relationship: RelationshipType = "FS"
    lag_days: int = Field(ge=0)
    max_finish_gap_days: int | None = Field(default=None, ge=0)
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
    control_level: ControlLevel | None = None
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
    control_level: ControlLevel | None = None
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
                    standard_section_height_m=4.5 if self.productivity_unit == "天/节" else None,
                    is_default=True,
                )
            ]

        if self.component_type == "pile":
            for option in self.productivity_options:
                self._sync_pile_productivity_unit(option)

        if self._is_segmented_pier_formwork_process():
            for option in self.productivity_options:
                if option.productivity_unit == "天/节":
                    option.duration_method = "days_per_unit"
                    option.quantity_source = "pier_height_m"
                    if option.standard_section_height_m is None:
                        option.standard_section_height_m = 4.5
                elif option.productivity_unit == "m/天":
                    option.duration_method = "units_per_day"
                    option.quantity_source = "pier_height_m"

        default_index = next((index for index, option in enumerate(self.productivity_options) if option.is_default), 0)
        for index, option in enumerate(self.productivity_options):
            option.is_default = index == default_index
        default_option = self.productivity_options[default_index]
        self.duration_method = default_option.duration_method
        self.quantity_source = default_option.quantity_source
        self.productivity_value = default_option.productivity_value
        self.productivity_unit = default_option.productivity_unit
        return self

    def _is_segmented_pier_formwork_process(self) -> bool:
        if self.component_type != "pier_body":
            return False
        if self.method_id in {"climbing_form", "sliding_form", "turnover_form"}:
            return True
        return any(keyword in self.process_name for keyword in ("爬模", "滑模", "翻模"))

    def _sync_pile_productivity_unit(self, option: ProductivityOption) -> None:
        unit_rule = _PILE_PRODUCTIVITY_UNIT_RULES.get(option.productivity_unit)
        if unit_rule is None:
            return
        option.duration_method = unit_rule[0]
        option.quantity_source = unit_rule[1]
        option.standard_section_height_m = None


class ResourceCalendar(BaseModel):
    id: str
    name: str
    working_weekdays: list[int] = [0, 1, 2, 3, 4, 5, 6]
    blackout_dates: list[date] = []


class ResourcePool(BaseModel):
    id: str
    type: str
    label: str
    resource_mode: ResourceMode = "LIMITED"
    quantity: int | None = Field(default=0, ge=0)
    max_quantity: int | None = Field(default=None, ge=0)
    calendar_id: str = "continuous"
    enabled: bool = True
    compatible_process_ids: list[str] = []
    cost_type: ResourceCostType = "none"
    incremental_unit_cost: int = Field(default=0, ge=0)
    billing_period_days: int = Field(default=30, ge=1)
    same_structure_resource_binding: bool = False
    same_structure_parallel_limit: int | None = Field(default=None, ge=1)
    parallel_rule_description: str = ""

    @model_validator(mode="after")
    def ensure_max_quantity(self) -> "ResourcePool":
        if self.resource_mode == "UNLIMITED":
            return self
        quantity = self.quantity or 0
        if self.max_quantity is None or self.max_quantity < quantity:
            self.max_quantity = quantity
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
    related_structure_ids: list[str] = Field(default_factory=list)


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


class TaskOverride(BaseModel):
    method_id: str | None = None
    productivity_option_id: str | None = None


class ScenarioInput(BaseModel):
    scenario_id: str
    scenario_name: str
    project: ProjectModel
    process_library: list[ProcessTemplate]
    logic_rules: list[LogicRule]
    upper_structure_logic_rules: list[UpperStructureLogicRule] = []
    task_overrides: dict[str, TaskOverride] = Field(default_factory=dict)
    resource_calendars: list[ResourceCalendar] = []
    resource_pools: list[ResourcePool]
    milestones: list[MilestoneConstraint] = []
    schedule_strategy: ScheduleStrategyConfig = Field(default_factory=ScheduleStrategyConfig)
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


class LocalScenarioConfigSaveRequest(BaseModel):
    process_library: list[ProcessTemplate] = Field(min_length=1)
    logic_rules: list[LogicRule] = Field(min_length=1)
    upper_structure_logic_rules: list[UpperStructureLogicRule] = Field(default_factory=list)
    resource_pools: list[ResourcePool] = Field(min_length=1)
    milestones: list[MilestoneConstraint] = Field(default_factory=list)


class LocalScenarioConfigResponse(BaseModel):
    process_library: list[ProcessTemplate]
    logic_rules: list[LogicRule]
    upper_structure_logic_rules: list[UpperStructureLogicRule]
    resource_pools: list[ResourcePool]
    milestones: list[MilestoneConstraint]


ProjectStructureParamsSource = Literal["local_config", "local_workbook", "default_demo", "request"]


class ProjectStructureParamsResponse(BaseModel):
    project: ProjectModel
    source: ProjectStructureParamsSource
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class ProjectStructureParamsSaveRequest(BaseModel):
    project: ProjectModel


class ProjectStructureParamsApplyRequest(BaseModel):
    scenario: ScenarioInput
    project: ProjectModel


class ProjectStructureParamsApplyResponse(BaseModel):
    scenario: ScenarioInput
    source: ProjectStructureParamsSource = "request"


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
    schedule_strategy: ScheduleStrategyConfig = Field(default_factory=ScheduleStrategyConfig)
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


class ScenarioAlternativeResult(BaseModel):
    scenario_id: str
    scenario_name: str
    role: str
    generated: GeneratedScheduleInput
    result: ScheduleResult
    milestone_results: list[MilestoneResult] = []
    diagnostics: list[ValidationMessage] = []
    metrics: dict[str, Any] = {}


class ScenarioSolveResult(BaseModel):
    scenario_id: str
    scenario_name: str
    generated: GeneratedScheduleInput
    result: ScheduleResult
    milestone_results: list[MilestoneResult] = []
    diagnostics: list[ValidationMessage] = []
    metrics: dict[str, Any] = {}
    alternative_results: list[ScenarioAlternativeResult] = []


class ScenarioCompareRequest(BaseModel):
    results: list[ScenarioSolveResult]


class MinResourcesSolveRequest(BaseModel):
    scenario: ScenarioInput
    fallback_target_days: int | None = Field(default=None, ge=1)


class ResourceCostSolveRequest(BaseModel):
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
