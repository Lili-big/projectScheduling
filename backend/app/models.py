from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
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

ObjectiveTermId = Literal[
    "control_node_late",
    "makespan_and_soft_milestone",
    "resource_path_continuity",
    "resource_slot_balance",
    "resource_idle",
    "target_relaxation",
]

OBJECTIVE_TERM_MAX_WEIGHT = 1_000_000_000
DEPRECATED_OBJECTIVE_TERM_IDS = {
    "spatial_resource_assignment",
    "same_structure_craft_split",
    "normal_balance",
    "resource_workload_balance",
    "unconfigured_normal_balance",
    "control_buffer_risk",
    "risk_related_control_wait",
}
DEFAULT_OBJECTIVE_TERM_WEIGHTS: dict[ObjectiveTermId, int] = {
    "control_node_late": 1_000_000_000,
    "makespan_and_soft_milestone": 5_000_000,
    "resource_path_continuity": 50_000,
    "resource_slot_balance": 50_000,
    "resource_idle": 50_000,
    "target_relaxation": 1_000_000_000,
}
DEFAULT_OBJECTIVE_TERM_ENABLED: dict[ObjectiveTermId, bool] = {
    "control_node_late": True,
    "makespan_and_soft_milestone": True,
    "resource_path_continuity": True,
    "resource_slot_balance": False,
    "resource_idle": True,
    "target_relaxation": False,
}
OBJECTIVE_TERM_IDS = tuple(DEFAULT_OBJECTIVE_TERM_WEIGHTS.keys())
OBJECTIVE_TERM_INHERIT_CONFIG_FROM: dict[ObjectiveTermId, ObjectiveTermId] = {
    "target_relaxation": "control_node_late",
}
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
    "resource_path_continuity": {
        "label": "资源路径连续性",
        "group": "资源组织",
        "description": "同一资源相邻任务的同幅邻近推进程度；权重越高，模型越倾向减少空间跳跃和幅别切换。",
        "default_weight": DEFAULT_OBJECTIVE_TERM_WEIGHTS["resource_path_continuity"],
        "configurable": True,
        "source": "objective",
        "applies_to": ["control_priority", "balanced_normal", "comprehensive"],
        "legacy_fields": ["resource_path_continuity_penalty"],
    },
    "resource_slot_balance": {
        "label": "资源槽位均衡",
        "group": "资源组织",
        "description": "同结构并行槽位的资源分配均衡程度；权重越高，模型越倾向均衡使用并行槽位。",
        "default_weight": DEFAULT_OBJECTIVE_TERM_WEIGHTS["resource_slot_balance"],
        "configurable": True,
        "source": "derived_objective",
        "applies_to": ["control_priority", "balanced_normal", "comprehensive"],
        "legacy_fields": ["resource_slot_balance_penalty"],
        "parent_term_id": "resource_path_continuity",
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
    "target_relaxation": {
        "label": "目标放松迟延",
        "group": "最佳努力",
        "description": "最佳努力精排中强制节点迟延和固定工期超期；权重越高，模型越优先减少被放松目标的迟延。",
        "default_weight": DEFAULT_OBJECTIVE_TERM_WEIGHTS["target_relaxation"],
        "configurable": True,
        "source": "derived_objective",
        "applies_to": ["best_effort_refinement"],
        "legacy_fields": [
            "target_relaxation_penalty",
            "relaxed_hard_milestone_lateness_days",
            "fixed_duration_overrun_days",
        ],
        "parent_term_id": "control_node_late",
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


class Resource(BaseModel):
    id: str
    name: str
    type: str
    pool_id: str | None = None
    pool_label: str | None = None
    enabled: bool = True
    calendar_id: str = "continuous"
    same_structure_resource_binding: bool = False
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
    time_limit_seconds: float = Field(default=20.0, gt=0)


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


class ScheduleInput(BaseModel):
    project_name: str
    start_date: date
    tasks: list[Task]
    precedence_links: list[PrecedenceLink]
    resources: list[Resource]
    milestones: list[MilestoneConstraint] = []
    schedule_strategy: ScheduleStrategyConfig = Field(default_factory=ScheduleStrategyConfig)
    time_limit_seconds: float = Field(default=20.0, gt=0)


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
