from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
ResourceScopeMode = Literal["PROJECT_SHARED", "WORKPOINT_EXCLUSIVE"]
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
AiParameterMaterialKind = Literal["text", "word", "excel", "pdf", "image"]
AiParameterParseStatus = Literal["parsed", "partially_parsed", "failed"]
AiParameterRunStatus = Literal["ready", "extracting", "completed", "partially_failed", "failed"]
AiParameterCategory = Literal["process_productivity", "process_method_assignment", "resource_pool", "milestone"]
AiParameterConfidence = Literal["High", "Medium", "Low"]
AiParameterSuggestionStatus = Literal[
    "suggested",
    "selected",
    "needs_manual_input",
    "conflict",
    "ignored",
    "applied",
    "failed",
]
AiParameterConflictResolutionStatus = Literal[
    "unresolved",
    "selected_suggestion",
    "manual_value",
    "keep_current",
]
AiParameterCandidateValidationStatus = Literal["valid", "needs_manual_input", "invalid"]
AiParameterApplicationStatus = Literal["pending", "partially_applied", "applied", "expired"]
ResourceAssistantPlanProfile = Literal["economy", "balanced", "crash", "custom"]
PlanVersionKind = Literal["baseline", "execution"]
PlanVersionStatus = Literal["draft", "active", "stale", "superseded"]
ProgressTaskStatus = Literal["not_started", "in_progress", "completed", "paused", "cancelled"]
ProgressDataQualityStatus = Literal["valid", "warning", "invalid"]
RemainingDaysSource = Literal["calculated", "manual", "baseline", "none"]
ForecastStrategy = Literal["as_is", "add_bottleneck_resources", "prioritize_critical_tasks"]
ForecastSolveStatus = Literal["ready", "solving", "feasible", "infeasible", "failed", "stale"]
ForecastRiskStatus = Literal["on_track", "at_risk", "late", "insufficient_data"]
ForecastConfidence = Literal["high", "medium", "low"]
ForecastTaskExecutionState = Literal[
    "completed_locked",
    "cancelled_excluded",
    "in_progress_remaining",
    "paused_remaining",
    "not_started_future",
]
CriticalNodeType = Literal["project_finish", "milestone"]
CriticalNodeDateSource = Literal["actual", "predicted", "combined", "unavailable"]
CriticalNodeEvidenceType = Literal[
    "driving_task",
    "bottleneck_resource",
    "precedence_wait",
    "data_quality",
    "solver",
]
ResourceAssistantGenerationSource = Literal["llm", "local_fallback", "user_adjusted"]
ResourceAssistantGenerationMode = Literal["llm_first", "local_fallback_only"]
ResourceAssistantPlanStatus = Literal[
    "draft",
    "ready_to_solve",
    "stale",
    "solving",
    "optimal",
    "feasible",
    "infeasible",
    "unknown",
    "failed",
    "model_invalid",
]
ResourceAssistantPlanOutcomeStatus = Literal["met", "not_met", "unconfirmed", "infeasible"]
ResourceAssistantScheduleOutcomeStatus = Literal[
    "duration_target_met",
    "duration_target_not_met",
    "no_feasible_schedule",
]
ResourceAssistantScheduleOutcomeReason = Literal[
    "target_met",
    "proven_late",
    "late_unconfirmed",
    "time_limit_no_schedule",
    "proven_infeasible",
    "resource_coverage_missing",
    "target_missing",
]
ResourceAssistantRecommendationStatus = Literal["recommended", "no_recommendation", "insufficient_results"]
ResourceAssistantExplanationSource = Literal["local", "llm"]

ObjectiveTermId = Literal[
    "control_node_late",
    "makespan_and_soft_milestone",
    "resource_idle",
]

OBJECTIVE_TERM_MAX_WEIGHT = 10_000_000_000
DEPRECATED_OBJECTIVE_TERM_IDS = {
    "spatial_resource_assignment",
    "same_structure_craft_split",
    "normal_balance",
    "resource_workload_balance",
    "unconfigured_normal_balance",
    "control_buffer_risk",
    "risk_related_control_wait",
    "resource_path_continuity",
}
DEFAULT_OBJECTIVE_TERM_WEIGHTS: dict[ObjectiveTermId, int] = {
    "control_node_late": 10_000_000_000,
    "makespan_and_soft_milestone": 5_000_000,
    "resource_idle": 50_000,
}
DEFAULT_OBJECTIVE_TERM_ENABLED: dict[ObjectiveTermId, bool] = {
    "control_node_late": True,
    "makespan_and_soft_milestone": True,
    "resource_idle": True,
}
OBJECTIVE_TERM_IDS = tuple(DEFAULT_OBJECTIVE_TERM_WEIGHTS.keys())
OBJECTIVE_TERM_INHERIT_CONFIG_FROM: dict[ObjectiveTermId, ObjectiveTermId] = {}
OBJECTIVE_METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "control_node_late": {
        "label": "软控制节点迟延",
        "group": "控制优先",
        "description": "控制软节点晚于目标日期的天数；权重越高，模型越优先压低控制节点迟延。",
        "default_weight": DEFAULT_OBJECTIVE_TERM_WEIGHTS["control_node_late"],
        "configurable": True,
        "source": "objective",
        "applies_to": ["control_priority", "balanced_normal", "comprehensive"],
        "legacy_fields": ["control_lateness_days", "soft_control_lateness_penalty"],
    },
    "makespan_and_soft_milestone": {
        "label": "总工期",
        "group": "工期",
        "description": "项目整体完工跨度；权重越高，模型越倾向缩短总工期。",
        "default_weight": DEFAULT_OBJECTIVE_TERM_WEIGHTS["makespan_and_soft_milestone"],
        "configurable": True,
        "source": "objective",
        "applies_to": ["control_priority", "balanced_normal", "comprehensive"],
        "legacy_fields": ["makespan_days"],
    },
    "resource_idle": {
        "label": "资源空闲",
        "group": "资源组织",
        "description": "单个资源两次任务之间的中途停等；权重越高，模型越倾向压缩资源空档。",
        "default_weight": DEFAULT_OBJECTIVE_TERM_WEIGHTS["resource_idle"],
        "configurable": True,
        "source": "objective",
        "applies_to": ["control_priority", "balanced_normal", "comprehensive"],
        "legacy_fields": ["resource_idle_penalty"],
    },
}


class ObjectiveTermConfig(BaseModel):
    enabled: bool = True
    weight: int = Field(ge=0, le=OBJECTIVE_TERM_MAX_WEIGHT)


def default_objective_terms() -> dict[ObjectiveTermId, ObjectiveTermConfig]:
    return {
        term_id: ObjectiveTermConfig(enabled=DEFAULT_OBJECTIVE_TERM_ENABLED[term_id], weight=weight)
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
    strategy: ScheduleStrategy = Field(default="comprehensive", exclude=True)
    resource_guarantee: ResourceGuaranteeMode = Field(default="priority", exclude=True)
    normal_balance_bucket: BalanceBucket = "month"
    normal_earliest_start_offset: int = Field(default=0, ge=0)
    normal_latest_finish_offset: int | None = Field(default=None, ge=1)
    normal_max_early_finish_days: int = Field(default=60, ge=0)
    max_parallel_normal_per_work_section: int = Field(default=5, ge=1)
    enable_balance_objective: bool = False
    objective_terms: dict[ObjectiveTermId, ObjectiveTermConfig] = Field(default_factory=default_objective_terms)

    @model_validator(mode="before")
    @classmethod
    def merge_objective_terms(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data

        values = dict(data)
        raw_terms = values.get("objective_terms")
        if raw_terms is None:
            raw_terms = {}
        if not isinstance(raw_terms, Mapping):
            raise ValueError("objective_terms must be an object keyed by objective term id")

        unknown_terms = sorted(set(raw_terms) - set(DEFAULT_OBJECTIVE_TERM_WEIGHTS) - DEPRECATED_OBJECTIVE_TERM_IDS)
        if unknown_terms:
            raise ValueError(f"unknown objective_terms: {', '.join(str(term) for term in unknown_terms)}")

        merged: dict[str, dict[str, Any]] = {}
        for term_id, default_weight in DEFAULT_OBJECTIVE_TERM_WEIGHTS.items():
            raw_config = raw_terms.get(term_id)
            inherited_from = OBJECTIVE_TERM_INHERIT_CONFIG_FROM.get(term_id)
            if raw_config is None and inherited_from is not None:
                raw_config = raw_terms.get(inherited_from)
            if raw_config is None:
                raw_config = {}
            if isinstance(raw_config, ObjectiveTermConfig):
                raw_config = raw_config.model_dump()
            if not isinstance(raw_config, Mapping):
                raise ValueError(f"objective_terms.{term_id} must be an object")

            merged[term_id] = {
                "enabled": raw_config.get("enabled", DEFAULT_OBJECTIVE_TERM_ENABLED[term_id]),
                "weight": raw_config.get("weight", default_weight),
            }

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
        self.enable_balance_objective = False
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


def _normalized_workpoint_ids(values: list[str]) -> list[str]:
    normalized = [value.strip() for value in values]
    if any(not value for value in normalized):
        raise ValueError("workpoint ids must not be blank")
    return sorted(set(normalized))


class WorkpointResourceOverride(BaseModel):
    model_config = ConfigDict(extra="allow")

    workpoint_id: str = Field(min_length=1)
    enabled: bool | None = None
    quantity: int | None = Field(default=None, ge=0)
    max_quantity: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def reject_removed_min_quantity(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and "min_quantity" in data:
            raise ValueError("min_quantity is not part of the resource contract")
        return data

    @model_validator(mode="after")
    def normalize_override(self) -> "WorkpointResourceOverride":
        self.workpoint_id = self.workpoint_id.strip()
        if not self.workpoint_id:
            raise ValueError("workpoint_id must not be blank")
        if self.quantity is not None and self.max_quantity is not None and self.max_quantity < self.quantity:
            self.max_quantity = self.quantity
        return self


class Resource(BaseModel):
    id: str
    name: str
    type: str
    pool_id: str | None = None
    pool_label: str | None = None
    enabled: bool = True
    calendar_id: str = "continuous"
    scope_mode: ResourceScopeMode = "PROJECT_SHARED"
    eligible_workpoint_ids: list[str] = Field(default_factory=list)
    exclusive_workpoint_id: str | None = None
    same_structure_resource_binding: bool = False
    parallel_rule_description: str = ""

    @model_validator(mode="after")
    def normalize_resource_scope(self) -> "Resource":
        self.eligible_workpoint_ids = _normalized_workpoint_ids(self.eligible_workpoint_ids)
        if self.exclusive_workpoint_id is not None:
            self.exclusive_workpoint_id = self.exclusive_workpoint_id.strip()
            if not self.exclusive_workpoint_id:
                raise ValueError("exclusive_workpoint_id must not be blank")
        if self.scope_mode == "PROJECT_SHARED" and self.exclusive_workpoint_id is not None:
            raise ValueError("PROJECT_SHARED resource must not set exclusive_workpoint_id")
        if self.scope_mode == "WORKPOINT_EXCLUSIVE":
            if self.exclusive_workpoint_id is None:
                raise ValueError("WORKPOINT_EXCLUSIVE resource requires exclusive_workpoint_id")
            if self.eligible_workpoint_ids != [self.exclusive_workpoint_id]:
                raise ValueError(
                    "WORKPOINT_EXCLUSIVE resource eligible_workpoint_ids must contain only exclusive_workpoint_id"
                )
        return self


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
    structure_parameter_label: str | None = None
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
    code: str | None = None
    entity_refs: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    details: dict[str, Any] | None = None


class ComponentModel(BaseModel):
    id: str
    name: str
    component_type: ComponentType
    quantity: float = Field(ge=0)
    quantity_label: str = ""
    structure_parameter_label: str | None = None
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
    structure_parameter_label: str | None = None
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
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    label: str
    resource_mode: ResourceMode = "LIMITED"
    scope_mode: ResourceScopeMode = "PROJECT_SHARED"
    workpoint_id: str | None = None
    quantity: int | None = Field(default=0, ge=0)
    max_quantity: int | None = Field(default=None, ge=0)
    authorized_workpoint_ids: list[str] | None = None
    workpoint_overrides: list[WorkpointResourceOverride] = Field(default_factory=list)
    calendar_id: str = "continuous"
    enabled: bool = True
    compatible_process_ids: list[str] = []
    cost_type: ResourceCostType = "none"
    incremental_unit_cost: int = Field(default=0, ge=0)
    billing_period_days: int = Field(default=30, ge=1)
    same_structure_resource_binding: bool = False
    parallel_rule_description: str = ""

    @model_validator(mode="before")
    @classmethod
    def reject_removed_min_quantity(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and "min_quantity" in data:
            raise ValueError("min_quantity is not part of the resource contract")
        return data

    @model_validator(mode="after")
    def ensure_max_quantity(self) -> "ResourcePool":
        if self.workpoint_id is not None:
            self.workpoint_id = self.workpoint_id.strip()
            if not self.workpoint_id:
                raise ValueError("workpoint_id must not be blank")
        if self.authorized_workpoint_ids is not None:
            self.authorized_workpoint_ids = _normalized_workpoint_ids(self.authorized_workpoint_ids)
        workpoint_ids = [item.workpoint_id for item in self.workpoint_overrides]
        duplicate_ids = sorted({item for item in workpoint_ids if workpoint_ids.count(item) > 1})
        if duplicate_ids:
            raise ValueError(f"duplicate workpoint_overrides: {', '.join(duplicate_ids)}")
        self.workpoint_overrides = sorted(self.workpoint_overrides, key=lambda item: item.workpoint_id)
        if self.resource_mode != "UNLIMITED":
            quantity = self.quantity or 0
            if self.max_quantity is None or self.max_quantity < quantity:
                self.max_quantity = quantity
        if self.scope_mode == "PROJECT_SHARED" and self.workpoint_id is not None:
            raise ValueError("PROJECT_SHARED resource pool must not set workpoint_id")
        if self.scope_mode == "WORKPOINT_EXCLUSIVE" and self.workpoint_id is not None:
            if self.authorized_workpoint_ids is not None:
                raise ValueError(
                    "WORKPOINT_EXCLUSIVE resource pool with workpoint_id must set authorized_workpoint_ids to null"
                )
            if self.workpoint_overrides:
                raise ValueError(
                    "WORKPOINT_EXCLUSIVE resource pool with workpoint_id must not set workpoint_overrides"
                )
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
    project_data_version_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    project: ProjectModel
    process_library: list[ProcessTemplate]
    logic_rules: list[LogicRule]
    upper_structure_logic_rules: list[UpperStructureLogicRule] = []
    task_overrides: dict[str, TaskOverride] = Field(default_factory=dict)
    resource_calendars: list[ResourceCalendar] = []
    resource_pools: list[ResourcePool]
    milestones: list[MilestoneConstraint] = []
    schedule_strategy: ScheduleStrategyConfig = Field(default_factory=ScheduleStrategyConfig)
    time_limit_seconds: float = Field(default=15.0, gt=0)
    girder_planning: GirderPlanningConfig | None = None

    @model_validator(mode="after")
    def validate_resource_pool_identities(self) -> "ScenarioInput":
        pool_ids = [pool.id for pool in self.resource_pools]
        duplicate_pool_ids = sorted({pool_id for pool_id in pool_ids if pool_ids.count(pool_id) > 1})
        if duplicate_pool_ids:
            raise ValueError(f"duplicate resource pool ids: {', '.join(duplicate_pool_ids)}")

        local_keys = [
            (pool.workpoint_id, pool.type)
            for pool in self.resource_pools
            if pool.scope_mode == "WORKPOINT_EXCLUSIVE" and pool.workpoint_id is not None
        ]
        duplicate_local_keys = sorted({key for key in local_keys if local_keys.count(key) > 1})
        if duplicate_local_keys:
            labels = [f"{workpoint_id}/{resource_type}" for workpoint_id, resource_type in duplicate_local_keys]
            raise ValueError(f"duplicate workpoint resource keys: {', '.join(labels)}")
        return self


class AiParameterUploadedMaterialSummary(BaseModel):
    material_id: str
    file_name: str
    kind: AiParameterMaterialKind
    size_bytes: int = Field(ge=0)
    parse_status: AiParameterParseStatus
    source_summary: str
    error_message: str | None = None


class AiParameterSourceEvidence(BaseModel):
    material_id: str
    excerpt: str
    page_or_sheet: str | None = None
    cell_or_region: str | None = None
    note: str | None = None


class AiParameterSuggestion(BaseModel):
    suggestion_id: str
    category: AiParameterCategory
    target_ref: dict[str, Any] = Field(default_factory=dict)
    parameter_key: str
    current_value: Any = None
    proposed_value: Any = None
    unit: str | None = None
    confidence_label: AiParameterConfidence
    confidence_score: int = Field(ge=0, le=100)
    source_refs: list[AiParameterSourceEvidence] = Field(default_factory=list)
    conflict_group_id: str | None = None
    status: AiParameterSuggestionStatus = "suggested"
    validation_messages: list[ValidationMessage] = Field(default_factory=list)


class AiParameterConflictGroup(BaseModel):
    conflict_group_id: str
    parameter_key: str
    target_ref: dict[str, Any] = Field(default_factory=dict)
    suggestion_ids: list[str] = Field(default_factory=list)
    current_value: Any = None
    resolution_status: AiParameterConflictResolutionStatus = "unresolved"
    selected_suggestion_id: str | None = None
    manual_value: Any = None


class AiParameterCandidateAddition(BaseModel):
    candidate_id: str
    category: AiParameterCategory
    display_name: str
    proposed_fields: dict[str, Any] = Field(default_factory=dict)
    confidence_label: AiParameterConfidence
    confidence_score: int = Field(ge=0, le=100)
    source_refs: list[AiParameterSourceEvidence] = Field(default_factory=list)
    validation_status: AiParameterCandidateValidationStatus = "valid"


class AiParameterExtractionRun(BaseModel):
    run_id: str
    status: AiParameterRunStatus
    material_count: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    suggestion_count: int = Field(ge=0)
    material_summaries: list[AiParameterUploadedMaterialSummary] = Field(default_factory=list)
    errors: list[ValidationMessage] = Field(default_factory=list)
    warnings: list[ValidationMessage] = Field(default_factory=list)
    expires_at: datetime


class AiParameterSuggestionStoreEntry(BaseModel):
    run_id: str
    created_at: datetime
    expires_at: datetime
    scenario_id: str
    suggestions: list[AiParameterSuggestion] = Field(default_factory=list)
    conflict_groups: list[AiParameterConflictGroup] = Field(default_factory=list)
    candidate_additions: list[AiParameterCandidateAddition] = Field(default_factory=list)
    material_summaries: list[AiParameterUploadedMaterialSummary] = Field(default_factory=list)
    application_status: AiParameterApplicationStatus = "pending"


class AiParameterParseResponse(AiParameterExtractionRun):
    suggestions: list[AiParameterSuggestion] = Field(default_factory=list)
    conflict_groups: list[AiParameterConflictGroup] = Field(default_factory=list)
    candidate_additions: list[AiParameterCandidateAddition] = Field(default_factory=list)
    manual_completion_count: int = Field(default=0, ge=0)


class AiParameterManualValue(BaseModel):
    suggestion_id: str | None = None
    conflict_group_id: str | None = None
    parameter_key: str | None = None
    value: Any = None


class AiParameterApplyRequest(BaseModel):
    scenario: ScenarioInput
    run_id: str
    selected_suggestion_ids: list[str] = Field(default_factory=list)
    conflict_resolutions: list[AiParameterConflictGroup] = Field(default_factory=list)
    manual_values: list[AiParameterManualValue] = Field(default_factory=list)


class AiParameterAppliedItem(BaseModel):
    suggestion_id: str
    category: AiParameterCategory
    target_ref: dict[str, Any] = Field(default_factory=dict)
    parameter_key: str
    old_value: Any = None
    new_value: Any = None


class AiParameterApplicationSummary(BaseModel):
    applied_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    manual_pending_count: int = Field(default=0, ge=0)
    applied_items: list[AiParameterAppliedItem] = Field(default_factory=list)
    failed_items: list[ValidationMessage] = Field(default_factory=list)
    stale_result_reason: str = ""


class AiParameterApplyResponse(BaseModel):
    scenario: ScenarioInput
    application_summary: AiParameterApplicationSummary
    stale_results: bool = False


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


class TaskExecutionConstraint(BaseModel):
    task_id: str
    earliest_start_offset: int | None = Field(default=None, ge=0)
    fixed_start_offset: int | None = Field(default=None, ge=0)
    fixed_resource_id: str | None = None
    source: str = "manual"

    @model_validator(mode="after")
    def validate_start_offsets(self) -> "TaskExecutionConstraint":
        if (
            self.earliest_start_offset is not None
            and self.fixed_start_offset is not None
            and self.fixed_start_offset < self.earliest_start_offset
        ):
            raise ValueError("fixed_start_offset must be greater than or equal to earliest_start_offset")
        return self


class ScheduleInput(BaseModel):
    project_name: str
    start_date: date
    tasks: list[Task]
    precedence_links: list[PrecedenceLink]
    resources: list[Resource]
    milestones: list[MilestoneConstraint] = []
    execution_constraints: list[TaskExecutionConstraint] = Field(default_factory=list)
    schedule_strategy: ScheduleStrategyConfig = Field(default_factory=ScheduleStrategyConfig)
    time_limit_seconds: float = Field(default=15.0, gt=0)


class ContinuousBeamTeamSpan(BaseModel):
    span_group_id: str
    display_name: str
    bridge_id: str | None = None
    work_section_id: str | None = None
    group_index: int | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    resource_type: str = "cast_in_place_continuous_beam_team"
    start_offset: int | None = None
    end_offset: int | None = None
    start_date: date | None = None
    finish_date: date | None = None
    task_ids: list[str] = []


class ContinuousBeamTeamSpanSummary(BaseModel):
    enabled: bool = False
    span_count: int = 0
    resource_type: str = "cast_in_place_continuous_beam_team"
    resource_quantity: int = 0
    spans: list[ContinuousBeamTeamSpan] = []
    diagnostics: list[dict[str, Any]] = []


class ScheduledTask(Task):
    start_offset: int
    end_offset: int
    start_date: date
    finish_date: date
    assigned_resource_id: str | None = None
    assigned_resource_name: str | None = None
    assigned_resource_type: str | None = None
    continuous_span_group_id: str | None = None
    continuous_span_group_name: str | None = None
    continuous_span_resource_id: str | None = None
    continuous_span_resource_name: str | None = None
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


class ResourceAssistantControlPierSummary(BaseModel):
    structure_id: str
    structure_name: str
    bridge_id: str | None = None
    bridge_name: str | None = None
    work_section_id: str | None = None
    work_section_name: str | None = None
    side: WorkSectionSide = "none"
    support_no: str | None = None
    recognition_sources: list[str] = Field(default_factory=list)
    related_continuous_beam_group_ids: list[str] = Field(default_factory=list)


class ResourceAssistantReferenceExample(BaseModel):
    profile: ResourceAssistantPlanProfile
    description: str
    resource_quantities: dict[str, int] = Field(default_factory=dict)
    is_hard_constraint: bool = False


class ResourceAssistantProjectProfile(BaseModel):
    project_name: str
    start_date: date
    bridge_count: int = 0
    work_section_count: int = 0
    structure_count: int = 0
    task_count: int = 0
    control_piers: list[ResourceAssistantControlPierSummary] = Field(default_factory=list)
    resource_types: list[dict[str, Any]] = Field(default_factory=list)
    continuous_beam_groups: list[dict[str, Any]] = Field(default_factory=list)
    critical_path_candidates: list[dict[str, Any]] = Field(default_factory=list)
    constraint_hints: list[str] = Field(default_factory=list)
    reference_examples: list[ResourceAssistantReferenceExample] = Field(default_factory=list)
    data_quality_messages: list[ValidationMessage] = Field(default_factory=list)


class ResourceAssistantPlan(BaseModel):
    scenario_id: str
    scenario_name: str
    profile: ResourceAssistantPlanProfile
    positioning: str
    generation_source: ResourceAssistantGenerationSource = "local_fallback"
    generation_rationale: str = ""
    reference_example_used: str | None = None
    organization_strategy: str = ""
    validation_messages: list[ValidationMessage] = Field(default_factory=list)
    applicable_scenarios: str = ""
    expected_risks: str = ""
    resource_pools: list[ResourcePool] = Field(default_factory=list)
    changed_from_standard: bool = False
    solve_status: ResourceAssistantPlanStatus = "draft"
    stale_reason: str | None = None


class ResourceAssistantGenerationRecord(BaseModel):
    generation_id: str
    source: ResourceAssistantGenerationSource = "local_fallback"
    input_fingerprint: str
    prompt_summary: str = ""
    reference_examples_used: list[ResourceAssistantReferenceExample] = Field(default_factory=list)
    constraint_hints_used: list[str] = Field(default_factory=list)
    raw_output_available: bool = False
    parsed_plan_ids: list[str] = Field(default_factory=list)
    validation_status: Literal["valid", "partially_valid", "invalid"] = "valid"
    fallback_reason: str | None = None


class ResourceAssistantLlmConfigStatus(BaseModel):
    provider: str = "local"
    model: str | None = None
    endpoint_configured: bool = False
    api_key_configured: bool = False
    timeout_seconds: int = 30
    status: Literal["local_fallback", "configured", "failed"] = "local_fallback"
    warning: str | None = None


class ResourceAssistantTransferPenalty(BaseModel):
    penalty_score: int = 0
    jump_pier_count: int = 0
    side_switch_count: int = 0
    cross_side_jump_count: int = 0
    path_group_switch_count: int = 0
    max_jump_distance: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)


class ResourceAssistantDemoCost(BaseModel):
    total_cost: float = 0
    work_cost: float = 0
    idle_cost: float = 0
    mobilization_cost: float = 0
    transfer_cost: float = 0
    resource_costs: list[dict[str, Any]] = Field(default_factory=list)
    price_source: str = "demo_default_price"
    disclaimer: str = "演示默认价格估算，仅用于方案横向比较。"


class ResourceAssistantCoreMetrics(BaseModel):
    total_days: int | None = None
    plan_finish_date: date | None = None
    control_pier_release_dates: list[dict[str, Any]] = Field(default_factory=list)
    first_continuous_beam_start_date: date | None = None
    all_continuous_beams_started_date: date | None = None
    resource_utilization_by_type: list[dict[str, Any]] = Field(default_factory=list)
    average_wait_days: float | None = None
    max_wait_days: int | None = None
    control_pier_wait_days: int | None = None
    continuous_beam_wait_days: int | None = None
    transfer_penalty: ResourceAssistantTransferPenalty = Field(default_factory=ResourceAssistantTransferPenalty)
    demo_cost: ResourceAssistantDemoCost = Field(default_factory=ResourceAssistantDemoCost)
    target_status: str = "not_evaluated"
    not_available_reasons: list[str] = Field(default_factory=list)


class ResourceAssistantPrimaryStageSummary(BaseModel):
    attempted: bool = True
    solver_status: str | None = None
    max_target_delay_days: int | None = Field(default=None, ge=0)
    makespan_days: int | None = Field(default=None, ge=0)
    optimality_proven: bool = False
    elapsed_seconds: float = Field(default=0.0, ge=0)
    configured_budget_seconds: float = Field(default=0.0, ge=0)


class ResourceAssistantSecondaryStageSummary(BaseModel):
    attempted: bool = False
    solver_status: str | None = None
    resource_idle_days: int | None = Field(default=None, ge=0)
    continuity_penalty: int | None = Field(default=None, ge=0)
    optimality_proven: bool = False
    elapsed_seconds: float = Field(default=0.0, ge=0)
    configured_budget_seconds: float = Field(default=0.0, ge=0)
    skipped_reason: Literal[
        "primary_no_schedule",
        "time_budget_exhausted",
        "insufficient_remaining_budget",
        "idle_already_zero",
        "not_applicable",
    ] | None = None
    validation_failure_reason: Literal[
        "primary_bounds_exceeded",
        "resource_snapshot_changed",
        "task_set_changed",
        "no_secondary_improvement",
        "model_error",
    ] | None = None


class ResourceAssistantOptimizationStages(BaseModel):
    primary: ResourceAssistantPrimaryStageSummary
    secondary: ResourceAssistantSecondaryStageSummary
    selected_stage: Literal["primary", "secondary"] = "primary"
    fallback_reason: str | None = None
    total_budget_seconds: float = Field(default=0.0, ge=0)
    total_elapsed_seconds: float = Field(default=0.0, ge=0)


class ResourcePoolQuantityResult(BaseModel):
    resource_pool_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    workpoint_id: str | None = None
    scope_mode: ResourceScopeMode
    current_quantity: int = Field(ge=0)
    recommended_quantity: int = Field(ge=0)
    max_quantity: int = Field(ge=0)
    eligible_workpoint_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pool_identity_and_quantities(self) -> "ResourcePoolQuantityResult":
        self.resource_pool_id = self.resource_pool_id.strip()
        self.resource_type = self.resource_type.strip()
        if not self.resource_pool_id or not self.resource_type:
            raise ValueError("resource pool quantity result identity must not be blank")
        self.eligible_workpoint_ids = _normalized_workpoint_ids(self.eligible_workpoint_ids)
        if self.workpoint_id is not None:
            self.workpoint_id = self.workpoint_id.strip()
            if not self.workpoint_id:
                raise ValueError("workpoint_id must not be blank")
        if self.scope_mode == "PROJECT_SHARED" and self.workpoint_id is not None:
            raise ValueError("PROJECT_SHARED quantity result must not set workpoint_id")
        if self.scope_mode == "WORKPOINT_EXCLUSIVE":
            if self.workpoint_id is None:
                raise ValueError("WORKPOINT_EXCLUSIVE quantity result requires workpoint_id")
            if self.eligible_workpoint_ids != [self.workpoint_id]:
                raise ValueError(
                    "WORKPOINT_EXCLUSIVE quantity result eligible_workpoint_ids must contain only workpoint_id"
                )
        if self.max_quantity < max(self.current_quantity, self.recommended_quantity):
            raise ValueError("max_quantity must cover current_quantity and recommended_quantity")
        return self


class ResourceAssistantPlanResult(BaseModel):
    scenario_id: str
    plan_status: ResourceAssistantPlanOutcomeStatus | None = None
    schedule_outcome_status: ResourceAssistantScheduleOutcomeStatus | None = None
    schedule_outcome_reason: ResourceAssistantScheduleOutcomeReason | None = None
    solver_status: str | None = None
    input_resource_quantities: dict[str, int] = Field(default_factory=dict)
    resource_pool_quantities: list[ResourcePoolQuantityResult] = Field(default_factory=list)
    resource_expansion_attempted: bool = False
    optimization_stages: ResourceAssistantOptimizationStages | None = None
    generated: GeneratedScheduleInput | None = None
    result: ScheduleResult | None = None
    metrics: ResourceAssistantCoreMetrics = Field(default_factory=ResourceAssistantCoreMetrics)
    diagnostics: list[ValidationMessage] = Field(default_factory=list)
    generated_at: datetime
    input_fingerprint: str


class ResourceAssistantMetricRow(BaseModel):
    metric_id: str
    metric_name: str
    unit: str = ""
    values: dict[str, Any] = Field(default_factory=dict)
    source_type: Literal["solver_result", "derived_diagnostic", "demo_estimate"]
    description: str = ""


class ResourceAssistantComparison(BaseModel):
    scenario_columns: list[dict[str, str]] = Field(default_factory=list)
    metric_rows: list[ResourceAssistantMetricRow] = Field(default_factory=list)
    best_scenario_id: str | None = None
    comparison_notes: list[str] = Field(default_factory=list)


class ResourceAssistantRecommendation(BaseModel):
    recommended_scenario_id: str | None = None
    recommendation_status: ResourceAssistantRecommendationStatus = "insufficient_results"
    rule_reason: str = ""
    evidence: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    marginal_benefit_notes: list[str] = Field(default_factory=list)
    ai_explanation: str = ""
    explanation_source: ResourceAssistantExplanationSource = "local"
    llm_status: ResourceAssistantLlmConfigStatus = Field(default_factory=ResourceAssistantLlmConfigStatus)


class ResourceAssistantInitialRequest(BaseModel):
    scenario: ScenarioInput
    generation_mode: ResourceAssistantGenerationMode = "llm_first"


class ResourceAssistantInitialResponse(BaseModel):
    project_profile: ResourceAssistantProjectProfile
    resource_plans: list[ResourceAssistantPlan]
    plan_generation: ResourceAssistantGenerationRecord
    reference_examples: list[ResourceAssistantReferenceExample] = Field(default_factory=list)
    constraint_hints: list[str] = Field(default_factory=list)
    llm_generation_context: dict[str, Any] = Field(default_factory=dict)
    llm_config_status: ResourceAssistantLlmConfigStatus
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class ScopedResourceQuantityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_pool_id: str = Field(min_length=1)
    workpoint_id: str | None = None
    quantity: int = Field(ge=0)


class ResourceAssistantUpdatePlanRequest(BaseModel):
    plan_id: str
    resource_updates: dict[str, int] = Field(default_factory=dict)
    scoped_resource_updates: list[ScopedResourceQuantityUpdate] = Field(default_factory=list)
    resource_plan: ResourceAssistantPlan | None = None


class ResourceAssistantUpdatePlanResponse(BaseModel):
    resource_plan: ResourceAssistantPlan
    invalidated_result_ids: list[str] = Field(default_factory=list)
    generation_source: ResourceAssistantGenerationSource = "user_adjusted"
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class ResourceAssistantBatchSolveRequest(BaseModel):
    scenario: ScenarioInput
    resource_plans: list[ResourceAssistantPlan]
    solve_scope: str = "all_plans"


class ResourceAssistantBatchSolveResponse(BaseModel):
    project_profile: ResourceAssistantProjectProfile
    resource_plans: list[ResourceAssistantPlan]
    plan_results: list[ResourceAssistantPlanResult]
    comparison: ResourceAssistantComparison
    recommendation: ResourceAssistantRecommendation
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class ResourceAssistantSingleSolveRequest(BaseModel):
    scenario: ScenarioInput
    resource_plan: ResourceAssistantPlan


class ResourceAssistantSingleSolveResponse(BaseModel):
    resource_plan: ResourceAssistantPlan
    plan_result: ResourceAssistantPlanResult
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class ResourceAssistantResultsRequest(BaseModel):
    resource_plans: list[ResourceAssistantPlan]
    plan_results: list[ResourceAssistantPlanResult]


class ResourceAssistantRecommendationResponse(BaseModel):
    comparison: ResourceAssistantComparison
    recommendation: ResourceAssistantRecommendation
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


GirderSide = Literal["left", "right", "both", "unknown"]
GirderWorkPointType = Literal["roadbed", "bridge", "tunnel", "culvert", "access"]
ProjectDataVersionStatus = Literal["draft", "confirmed", "superseded"]
PlanningScenarioVersionStatus = Literal["draft", "specialty_confirmed", "stale", "superseded"]
IntegratedCalculationStatus = Literal[
    "running",
    "converged",
    "not_converged",
    "infeasible",
    "blocked",
    "stale",
]


class SourceEvidence(BaseModel):
    evidence_id: str
    source_type: Literal["structure_import", "girder_import", "manual"]
    authority_domain: Literal["structure", "girder_workpoint", "user_config"]
    field_path: str
    file_name: str | None = None
    sheet_name: str | None = None
    row_or_region: str | None = None
    original_value: Any = None
    normalized_value: Any = None


class FieldCandidateValue(BaseModel):
    source_evidence_id: str
    value: Any = None


class FieldConflict(BaseModel):
    conflict_id: str
    entity_ref: str
    field_path: str
    severity: Literal["warning", "blocking"]
    status: Literal["unresolved", "resolved"] = "unresolved"
    candidate_values: list[FieldCandidateValue] = Field(default_factory=list)
    selected_value: Any = None
    resolution_reason: str | None = None


class PassageConditionRef(BaseModel):
    ref_type: Literal["structure", "upper_structure", "milestone"]
    entity_id: str
    target_event: Literal["finish"] = "finish"


class GirderWorkPoint(BaseModel):
    workpoint_id: str
    name: str
    workpoint_type: GirderWorkPointType
    side: GirderSide = "unknown"
    mileage_start_m: float
    mileage_end_m: float
    corridor_id: str
    bridge_id: str | None = None
    work_section_id: str | None = None
    requires_erection: bool = False
    rough_granularity: bool = False
    explicit_readiness_date: date | None = None
    linked_condition_refs: list[PassageConditionRef] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class CreateProjectDataVersionRequest(BaseModel):
    project: ProjectModel
    workpoints: list[GirderWorkPoint] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    field_conflicts: list[FieldConflict] = Field(default_factory=list)
    expected_latest_version_no: int | None = Field(default=None, ge=1)
    created_by: str


class ConfirmProjectDataVersionRequest(BaseModel):
    expected_input_fingerprint: str
    confirmed_by: str
    confirmation_reason: str


class ProjectDataVersion(BaseModel):
    project_data_version_id: str
    project_id: str
    version_no: int = Field(ge=1)
    status: ProjectDataVersionStatus = "draft"
    project: ProjectModel
    workpoints: list[GirderWorkPoint] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    field_conflicts: list[FieldConflict] = Field(default_factory=list)
    input_fingerprint: str
    created_by: str
    created_at: datetime
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    confirmation_reason: str | None = None


class BeamYardConfig(BaseModel):
    beam_yard_id: str
    name: str
    mileage_m: float
    side: GirderSide = "unknown"
    corridor_id: str
    production_start_date: date
    daily_production_capacity: float = Field(ge=0)
    initial_inventory_by_type: dict[str, float] = Field(default_factory=dict)
    max_inventory_by_type: dict[str, float] | None = None
    calendar_id: str = "continuous"
    enabled: bool = True

    @model_validator(mode="after")
    def validate_inventory(self) -> "BeamYardConfig":
        if any(value < 0 for value in self.initial_inventory_by_type.values()):
            raise ValueError("期初库存不能为负数。")
        if self.max_inventory_by_type and any(value < 0 for value in self.max_inventory_by_type.values()):
            raise ValueError("最大库存不能为负数。")
        return self


class ErectionMachineConfig(BaseModel):
    erection_machine_id: str
    name: str
    beam_yard_id: str
    available_date: date
    daily_erection_capacity: float = Field(gt=0)
    first_span_preparation_days: int = Field(default=0, ge=0)
    span_launching_days: int = Field(default=0, ge=0)
    bridge_transfer_days: int = Field(default=0, ge=0)
    side_switch_days: int = Field(default=0, ge=0)
    calendar_id: str = "continuous"
    enabled: bool = True


class GirderRouteNode(BaseModel):
    route_node_id: str
    workpoint_id: str
    sequence_index: int = Field(ge=0)
    node_kind: Literal["workpoint", "turn", "connection"] = "workpoint"
    connection_days: int | None = Field(default=None, ge=0)


class GirderRouteConfig(BaseModel):
    route_id: str
    name: str
    beam_yard_id: str
    erection_machine_id: str
    route_direction: Literal["mileage_increasing", "mileage_decreasing", "custom"] = "custom"
    enabled: bool = True
    confirmed: bool = False
    nodes: list[GirderRouteNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_node_order(self) -> "GirderRouteConfig":
        indexes = [item.sequence_index for item in self.nodes]
        if len(indexes) != len(set(indexes)):
            raise ValueError("同一路线的节点顺序号不能重复。")
        return self


class ErectionOwnerOverride(BaseModel):
    bridge_id: str
    side: Literal["left", "right"]
    owner_route_id: str
    reason: str
    confirmed_by: str
    confirmed_at: datetime


class PassageOverride(BaseModel):
    workpoint_id: str
    action: Literal["include", "exclude", "readiness"]
    related_route_id: str | None = None
    explicit_readiness_date: date | None = None
    reason: str


class GirderPlanningParameters(BaseModel):
    substructure_acceptance_buffer_days: int = Field(default=7, ge=0)
    roadbed_passage_buffer_days: int = Field(default=4, ge=0)
    tunnel_passage_buffer_days: int = Field(default=6, ge=0)
    post_erection_passage_buffer_days: int = Field(default=0, ge=0)
    post_erection_buffer_confirmed: bool = False
    default_transfer_days: int = Field(default=2, ge=0)
    default_bridge_preparation_days: int = Field(default=3, ge=0)
    max_iterations: int = Field(default=10, ge=1, le=50)
    date_tolerance_days: Literal[0] = 0
    enable_supply_constraint: Literal[True] = True
    enable_passage_constraint: Literal[True] = True
    enable_stock_limit: Literal[True] = True


class GirderPlanningConfig(BaseModel):
    enabled: bool = False
    beam_yards: list[BeamYardConfig] = Field(default_factory=list)
    erection_machines: list[ErectionMachineConfig] = Field(default_factory=list)
    routes: list[GirderRouteConfig] = Field(default_factory=list)
    parameters: GirderPlanningParameters = Field(default_factory=GirderPlanningParameters)
    owner_overrides: list[ErectionOwnerOverride] = Field(default_factory=list)
    manual_passage_overrides: list[PassageOverride] = Field(default_factory=list)
    coarse_mode: bool = False


class CreatePlanningScenarioVersionRequest(BaseModel):
    scenario: ScenarioInput
    project_data_version_id: str
    girder_planning: GirderPlanningConfig = Field(default_factory=GirderPlanningConfig)
    expected_latest_version_no: int | None = Field(default=None, ge=1)
    created_by: str


class PlanningScenarioVersion(BaseModel):
    scenario_version_id: str
    scenario_id: str
    project_data_version_id: str
    version_no: int = Field(ge=1)
    status: PlanningScenarioVersionStatus = "draft"
    scenario: ScenarioInput
    girder_planning: GirderPlanningConfig = Field(default_factory=GirderPlanningConfig)
    input_fingerprint: str
    created_by: str
    created_at: datetime
    specialty_confirmed_by: str | None = None
    specialty_confirmed_at: datetime | None = None
    specialty_confirmation_reason: str | None = None


class ConfirmSpecialtyRequest(BaseModel):
    expected_input_fingerprint: str
    confirmed_by: str
    confirmation_reason: str


class ScenarioVersionReference(BaseModel):
    scenario_version_id: str
    expected_input_fingerprint: str


class GirderPlanningReadinessCheck(BaseModel):
    code: str
    status: Literal["passed", "warning", "blocking"]
    message: str
    entity_refs: list[str] = Field(default_factory=list)


class GirderPlanningReadiness(BaseModel):
    status: Literal["ready", "warning", "blocking"]
    checks: list[GirderPlanningReadinessCheck] = Field(default_factory=list)
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class GirderImportPreview(BaseModel):
    workpoints: list[GirderWorkPoint] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    field_conflicts: list[FieldConflict] = Field(default_factory=list)
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class CompetingRouteOccurrence(BaseModel):
    route_id: str
    route_node_id: str
    arrival_date: date


class ErectionOwnership(BaseModel):
    bridge_id: str
    side: GirderSide
    owner_route_id: str
    owner_node_id: str
    arrival_date: date
    resolution_source: Literal["earliest_arrival", "manual_override", "actual_fact"]
    competing_occurrences: list[CompetingRouteOccurrence] = Field(default_factory=list)


class GirderSpanPlan(BaseModel):
    task_id: str
    bridge_id: str
    work_section_id: str
    span_id: str
    route_id: str
    beam_yard_id: str
    erection_machine_id: str
    beam_type: str
    beam_count: int = Field(ge=1)
    earliest_start_date: date
    suggested_latest_finish_date: date | None = None
    planned_start_date: date | None = None
    planned_finish_date: date | None = None
    inventory_before: float | None = Field(default=None, ge=0)
    inventory_after: float | None = Field(default=None, ge=0)
    diagnostic_refs: list[str] = Field(default_factory=list)


class PassageReleaseResult(BaseModel):
    workpoint_id: str
    passable_date: date | None = None
    erection_buffer_date: date | None = None
    explicit_readiness_date: date | None = None
    linked_condition_finish_dates: dict[str, date] = Field(default_factory=dict)
    controlling_source: Literal["erection_buffer", "explicit_readiness", "linked_condition", "actual_fact", "none"] = "none"
    status: Literal["ready", "waiting", "blocked"] = "blocked"


class YardInventoryPoint(BaseModel):
    beam_yard_id: str
    beam_type: str
    date: date
    opening_inventory: float = Field(ge=0)
    produced: float = Field(ge=0)
    consumed: float = Field(ge=0)
    closing_inventory: float = Field(ge=0)
    max_inventory: float | None = Field(default=None, ge=0)


class RouteRun(BaseModel):
    route_id: str
    beam_yard_id: str
    erection_machine_id: str
    start_date: date
    finish_date: date
    waiting_days: int = Field(default=0, ge=0)
    event_refs: list[str] = Field(default_factory=list)


class LatestFinishControl(BaseModel):
    entity_ref: str
    controlled_by: str
    latest_finish_date: date
    mode: Literal["soft"] = "soft"
    priority: int = Field(default=1, ge=1)


class GirderPlanningResult(BaseModel):
    result_id: str
    status: Literal["ready", "blocked"]
    ownerships: list[ErectionOwnership] = Field(default_factory=list)
    span_plans: list[GirderSpanPlan] = Field(default_factory=list)
    passage_releases: list[PassageReleaseResult] = Field(default_factory=list)
    yard_inventory_series: list[YardInventoryPoint] = Field(default_factory=list)
    route_runs: list[RouteRun] = Field(default_factory=list)
    latest_finish_controls: list[LatestFinishControl] = Field(default_factory=list)
    diagnostics: list[ValidationMessage] = Field(default_factory=list)
    input_fingerprint: str


class IntegratedIterationRecord(BaseModel):
    iteration_no: int = Field(ge=1)
    input_fingerprint: str
    ownership_fingerprint: str
    date_state_fingerprint: str
    girder_result_id: str
    schedule_status: Literal["feasible", "infeasible", "blocked"]
    changed_owner_refs: list[str] = Field(default_factory=list)
    changed_date_refs: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CreateIntegratedScheduleRequest(BaseModel):
    scenario_version_id: str
    progress_snapshot_id: str | None = None
    expected_input_fingerprint: str
    force_recompute: bool = False


class IntegratedCalculationSnapshot(BaseModel):
    integrated_snapshot_id: str
    project_data_version_id: str
    scenario_version_id: str
    progress_snapshot_id: str | None = None
    status: IntegratedCalculationStatus
    iterations: list[IntegratedIterationRecord] = Field(default_factory=list)
    girder_result: GirderPlanningResult | None = None
    generated_snapshot: GeneratedScheduleInput | None = None
    schedule_result: ScheduleResult | None = None
    input_fingerprint: str
    diagnostics: list[ValidationMessage] = Field(default_factory=list)
    created_at: datetime


class YardInventoryActual(BaseModel):
    beam_yard_id: str
    beam_type: str
    cumulative_produced: float = Field(ge=0)
    opening_inventory_adjustment: float = 0
    observed_inventory: float = Field(ge=0)
    adjustment_reason: str | None = None
    source: Literal["manual", "excel"] = "manual"


class GirderExecutionActual(BaseModel):
    span_task_id: str
    status: Literal["not_started", "in_progress", "completed"]
    actual_route_id: str | None = None
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    erected_beam_count: int = Field(default=0, ge=0)
    erection_machine_id: str | None = None


class GirderMachineActual(BaseModel):
    erection_machine_id: str
    position_workpoint_id: str | None = None
    availability_status: Literal["available", "unavailable", "maintenance"]
    expected_resume_date: date | None = None
    reason: str | None = None


class PassageActual(BaseModel):
    workpoint_id: str
    status: Literal["closed", "conditional", "open"]
    actual_open_date: date | None = None
    restrictions: str | None = None


class GirderProgressImportPreview(BaseModel):
    source_file_name: str
    yard_inventory_actuals: list[YardInventoryActual] = Field(default_factory=list)
    girder_execution_actuals: list[GirderExecutionActual] = Field(default_factory=list)
    girder_machine_actuals: list[GirderMachineActual] = Field(default_factory=list)
    passage_actuals: list[PassageActual] = Field(default_factory=list)
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class PlanVersion(BaseModel):
    plan_version_id: str
    project_id: str
    project_name: str
    plan_type: Literal["master"] = "master"
    version_no: int = Field(ge=1)
    version_kind: PlanVersionKind
    status: PlanVersionStatus = "active"
    parent_version_id: str | None = None
    source_scenario_id: str
    scenario_snapshot: ScenarioInput
    generated_snapshot: GeneratedScheduleInput
    schedule_result_snapshot: ScheduleResult
    resource_plan_snapshot: ResourceAssistantPlan
    input_fingerprint: str
    confirmed_by: str
    confirmed_at: datetime
    confirmation_reason: str
    project_data_version_id: str | None = None
    scenario_version_id: str | None = None
    integrated_snapshot_id: str | None = None
    girder_result_snapshot: GirderPlanningResult | None = None


class ProgressEntry(BaseModel):
    task_id: str
    status: ProgressTaskStatus = "not_started"
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    percent_complete: float = Field(default=0, ge=0, le=100)
    completed_quantity: float | None = Field(default=None, ge=0)
    remaining_quantity: float | None = Field(default=None, ge=0)
    actual_productivity: float | None = Field(default=None, gt=0)
    estimated_remaining_days: int | None = Field(default=None, ge=0)
    remaining_days: int = Field(default=0, ge=0)
    remaining_days_source: RemainingDaysSource = "none"
    expected_resume_date: date | None = None
    reason: str | None = None
    notes: str = ""


class ProgressSnapshot(BaseModel):
    progress_snapshot_id: str
    plan_version_id: str
    status_date: date
    revision_no: int = Field(ge=1)
    is_current: bool = True
    entries: list[ProgressEntry] = Field(default_factory=list)
    data_quality_status: ProgressDataQualityStatus = "valid"
    validation_messages: list[ValidationMessage] = Field(default_factory=list)
    submitted_by: str
    submitted_at: datetime
    correction_reason: str | None = None
    yard_inventory_actuals: list[YardInventoryActual] = Field(default_factory=list)
    girder_execution_actuals: list[GirderExecutionActual] = Field(default_factory=list)
    girder_machine_actuals: list[GirderMachineActual] = Field(default_factory=list)
    passage_actuals: list[PassageActual] = Field(default_factory=list)


class ProgressCorrectionRecord(BaseModel):
    correction_id: str
    plan_version_id: str
    status_date: date
    previous_snapshot_id: str
    new_snapshot_id: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    correction_reason: str
    corrected_by: str
    corrected_at: datetime


class ForecastTaskState(BaseModel):
    task_id: str
    task_name: str
    state: Literal["baseline", "actual", "predicted"]
    baseline_start_date: date | None = None
    baseline_finish_date: date | None = None
    actual_start_date: date | None = None
    actual_finish_date: date | None = None
    predicted_start_date: date | None = None
    predicted_finish_date: date | None = None
    assigned_resource_type: str | None = None
    assigned_resource_id: str | None = None
    progress_status: ProgressTaskStatus | None = None
    execution_state: ForecastTaskExecutionState | None = None
    remaining_days: int | None = Field(default=None, ge=0)
    related_diagnostics: list[str] = Field(default_factory=list)
    variance_days: int | None = None


class ForecastExecutionSummary(BaseModel):
    completed_locked_count: int = Field(default=0, ge=0)
    cancelled_excluded_count: int = Field(default=0, ge=0)
    in_progress_remaining_count: int = Field(default=0, ge=0)
    paused_remaining_count: int = Field(default=0, ge=0)
    not_started_future_count: int = Field(default=0, ge=0)
    resource_policy: Literal["baseline_fixed", "bottleneck_expanded"] = "baseline_fixed"
    sequence_policy: Literal["baseline_order", "critical_priority"] = "baseline_order"


class CriticalNodeEvidence(BaseModel):
    type: CriticalNodeEvidenceType
    message: str
    task_ids: list[str] = Field(default_factory=list)
    resource_types: list[str] = Field(default_factory=list)
    variance_days: int | None = None


class CriticalNodeForecast(BaseModel):
    node_id: str
    name: str
    node_type: CriticalNodeType
    level: MilestoneLevel | None = None
    mode: MilestoneMode | None = None
    target_date: date
    evaluated_date: date | None = None
    date_source: CriticalNodeDateSource = "unavailable"
    variance_days: int | None = None
    buffer_days: int | None = None
    status: ForecastRiskStatus = "insufficient_data"
    related_task_ids: list[str] = Field(default_factory=list)
    evidence: list[CriticalNodeEvidence] = Field(default_factory=list)


class ForecastSchedule(BaseModel):
    forecast_id: str
    plan_version_id: str
    progress_snapshot_id: str
    status_date: date
    strategy: ForecastStrategy = "as_is"
    status: ForecastSolveStatus = "ready"
    input_fingerprint: str
    historical_tasks: list[ForecastTaskState] = Field(default_factory=list)
    predicted_tasks: list[ForecastTaskState] = Field(default_factory=list)
    schedule_result: ScheduleResult | None = None
    execution_summary: ForecastExecutionSummary = Field(default_factory=ForecastExecutionSummary)
    critical_nodes: list[CriticalNodeForecast] = Field(default_factory=list)
    risk_status: ForecastRiskStatus = "insufficient_data"
    risk_evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: ForecastConfidence = "low"
    metrics: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[ValidationMessage] = Field(default_factory=list)
    created_at: datetime


class AdjustmentProposal(BaseModel):
    proposal_id: str
    forecast_id: str
    plan_version_id: str
    strategy: ForecastStrategy
    status: ForecastSolveStatus
    strategy_parameters: dict[str, Any] = Field(default_factory=dict)
    forecast: ForecastSchedule
    metrics: dict[str, Any] = Field(default_factory=dict)
    recommended: bool = False
    recommendation_reason: str = ""
    explanation: str = ""
    diagnostics: list[ValidationMessage] = Field(default_factory=list)
    created_at: datetime


class PlanChangeRecord(BaseModel):
    change_id: str
    source_plan_version_id: str
    source_forecast_id: str
    proposal_id: str
    new_plan_version_id: str
    adoption_reason: str
    confirmed_by: str
    confirmed_at: datetime


class PlanControlStore(BaseModel):
    schema_version: str = "plan-control/v2"
    plan_versions: list[PlanVersion] = Field(default_factory=list)
    project_data_versions: list[ProjectDataVersion] = Field(default_factory=list)
    planning_scenario_versions: list[PlanningScenarioVersion] = Field(default_factory=list)
    integrated_calculation_snapshots: list[IntegratedCalculationSnapshot] = Field(default_factory=list)
    progress_snapshots: list[ProgressSnapshot] = Field(default_factory=list)
    correction_records: list[ProgressCorrectionRecord] = Field(default_factory=list)
    forecasts: list[ForecastSchedule] = Field(default_factory=list)
    adjustment_proposals: list[AdjustmentProposal] = Field(default_factory=list)
    plan_change_records: list[PlanChangeRecord] = Field(default_factory=list)


class CreateBaselinePlanRequest(BaseModel):
    scenario: ScenarioInput
    resource_plan: ResourceAssistantPlan
    plan_result: ResourceAssistantPlanResult
    confirmed_by: str = "本地计划工程师"
    confirmation_reason: str = "确认为执行基准计划"
    integrated_snapshot_id: str | None = None


class PlanControlProjectSummary(BaseModel):
    project_id: str
    active_plan: PlanVersion | None = None
    plan_versions: list[PlanVersion] = Field(default_factory=list)
    current_progress_snapshot: ProgressSnapshot | None = None
    latest_forecast: ForecastSchedule | None = None


class CreateProgressSnapshotRequest(BaseModel):
    plan_version_id: str
    status_date: date
    entries: list[ProgressEntry] = Field(default_factory=list)
    submitted_by: str = "本地计划工程师"
    correction_reason: str | None = None
    expected_revision_no: int | None = Field(default=None, ge=1)
    yard_inventory_actuals: list[YardInventoryActual] = Field(default_factory=list)
    girder_execution_actuals: list[GirderExecutionActual] = Field(default_factory=list)
    girder_machine_actuals: list[GirderMachineActual] = Field(default_factory=list)
    passage_actuals: list[PassageActual] = Field(default_factory=list)


class CreateProgressSnapshotResponse(BaseModel):
    progress_snapshot: ProgressSnapshot
    stale_forecast_ids: list[str] = Field(default_factory=list)
    stale_integrated_snapshot_ids: list[str] = Field(default_factory=list)
    diagnostics: list[ValidationMessage] = Field(default_factory=list)


class CreateForecastRequest(BaseModel):
    plan_version_id: str
    progress_snapshot_id: str


class CreateAdjustmentRequest(BaseModel):
    max_resource_increments: dict[str, int] = Field(default_factory=dict)


class AdjustmentComparisonResponse(BaseModel):
    forecast_id: str
    proposals: list[AdjustmentProposal]
    recommended_proposal_id: str | None = None


class AdoptAdjustmentRequest(BaseModel):
    confirmed_by: str = "本地计划工程师"
    adoption_reason: str
    source_plan_fingerprint: str


class AdoptAdjustmentResponse(BaseModel):
    new_plan_version: PlanVersion
    previous_plan_version: PlanVersion
    change_record: PlanChangeRecord


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
