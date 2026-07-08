export type ComponentType =
  | "pile"
  | "cap"
  | "spread_foundation"
  | "ground_tie_beam"
  | "middle_tie_beam"
  | "pier_body"
  | "cap_beam"
  | "abutment_body"
  | "precast_beam"
  | "beam_erection"
  | "cast_in_place_continuous_beam"
  | "cast_in_place_box_beam"
  | "steel_box_beam"
  | "bridge_deck_system";
export type RelationshipType = "FS" | "SS" | "FF" | "SF";
export type WorkPointType = "road" | "bridge" | "tunnel";
export type WorkSectionSide = "left" | "right" | "none";
export type ResourceMode = "LIMITED" | "UNLIMITED";
export type ResourceCostType = "none" | "monthly_rental" | "one_time_purchase";
export type ControlLevel = "control" | "key" | "normal" | "rough";
export type BalanceBucket = "week" | "month";
export type ObjectiveTermId =
  | "control_node_late"
  | "makespan_and_soft_milestone"
  | "resource_path_continuity"
  | "resource_idle";
export type TabKey = "process" | "logic" | "resources" | "milestones" | "tasks" | "results" | "resultsMvp";
export type GanttMode = "by_time" | "by_structure" | "by_process";
export type TaskViewMode = "by_structure" | "by_process";
export type BusyState =
  | "loading"
  | "generating"
  | "solving"
  | "minResources"
  | "resourceCost"
  | "comparing"
  | "importing"
  | "nl"
  | "aiParameter"
  | "savingProcessLibrary"
  | "savingLogic"
  | "savingResources"
  | "savingMilestones"
  | null;

export type ComponentModel = {
  id: string;
  name: string;
  component_type: ComponentType;
  quantity: number;
  quantity_label: string;
  method_id?: string | null;
  productivity_option_id?: string | null;
  enabled: boolean;
  properties: Record<string, unknown>;
};

export type ScheduleStrategyConfig = {
  normal_balance_bucket: BalanceBucket;
  normal_earliest_start_offset: number;
  normal_latest_finish_offset?: number | null;
  normal_max_early_finish_days: number;
  max_parallel_normal_per_work_section: number;
  enable_balance_objective: boolean;
  objective_terms?: Record<ObjectiveTermId, ObjectiveTermConfig>;
};

export type ObjectiveTermConfig = {
  enabled: boolean;
  weight: number;
};

export type ObjectiveContribution = {
  term_id: ObjectiveTermId | string;
  label: string;
  group?: string;
  source: "objective" | "derived_objective" | "diagnostic" | string;
  enabled: boolean;
  active: boolean;
  configured_weight: number;
  effective_weight: number;
  weight?: number;
  raw_penalty: number;
  raw_value?: number;
  unit?: string;
  weighted_contribution: number;
  weighted_value?: number;
  applies_to: string[];
  parent_term_id?: ObjectiveTermId | string | null;
  notes?: string;
};

export type TargetStatus =
  | "met"
  | "current_resources_target_failed"
  | "candidate_resources_target_met"
  | "candidate_resources_target_failed"
  | "max_resources_target_failed"
  | "physical_infeasible"
  | "unconfirmed"
  | string;

export type TargetAchievement = {
  business_success: boolean;
  target_status: TargetStatus;
  solver_status: string;
  hard_milestone_late_days: number;
  fixed_duration_overrun_days: number;
  failure_reasons: string[];
  time_budget_seconds?: number;
  time_budget_exhausted?: boolean;
  evaluated_at_source?: string;
};

export type ResourceSearchRange = {
  resource_type: string;
  resource_pool_id?: string;
  current_quantity: number;
  max_quantity: number;
  lower_bound: number;
  upper_bound: number;
};

export type RecommendedResourcesOutcome = {
  candidate_quantities: Record<string, number>;
  added_quantities: Record<string, number>;
  search_range: ResourceSearchRange[];
  verification_result_source: string;
  target_achievement?: TargetAchievement | null;
};

export type ObjectiveEvaluationStatus =
  | "enabled"
  | "not_enabled"
  | "not_evaluated"
  | "ok"
  | "warning"
  | "danger"
  | string;

export type ObjectiveModelingGate = {
  term_id: ObjectiveTermId | string;
  requested_enabled: boolean;
  requested_weight: number;
  effective_weight: number;
  modeling_enabled: boolean;
  status: ObjectiveEvaluationStatus;
  reason: string;
};

export type DiagnosticMetric = {
  metric_id: string;
  label: string;
  value: number | string;
  unit?: string;
  source_path: string;
  read_only: boolean;
};

export type UpperStructureModel = {
  id: string;
  name: string;
  structure_type: string;
  side: WorkSectionSide;
  span_index: number;
  support_range: string;
  span_length_m: number;
  beam_count_per_span?: number | null;
  span_group_expression: string;
  control_level?: ControlLevel | null;
  properties: Record<string, unknown>;
};

export type StructureModel = {
  id: string;
  name: string;
  structure_type: "pier" | "abutment";
  order: number;
  support_no?: string | null;
  support_index?: number | null;
  control_level?: ControlLevel | null;
  components: ComponentModel[];
};

export type WorkSection = {
  id: string;
  name: string;
  order: number;
  side: WorkSectionSide;
  structures: StructureModel[];
  upper_structures: UpperStructureModel[];
};

export type ProjectBridge = {
  id: string;
  name: string;
  order: number;
  workpoint_type: WorkPointType;
  import_source: Record<string, unknown>;
  work_sections: WorkSection[];
};

export type ProjectModel = {
  project_id: string;
  project_name: string;
  start_date: string;
  bridges: ProjectBridge[];
};

export type ProductivityOption = {
  id: string;
  name: string;
  duration_method: string;
  quantity_source: string;
  productivity_value: number;
  productivity_unit: string;
  standard_section_height_m?: number | null;
  is_default: boolean;
};

export type TaskOverride = {
  method_id?: string | null;
  productivity_option_id?: string | null;
};

export type ProcessTemplate = {
  id: string;
  component_type: ComponentType;
  process_name: string;
  method_id?: string | null;
  duration_method: string;
  quantity_source: string;
  productivity_value: number;
  productivity_unit: string;
  resource_type: string;
  productivity_options?: ProductivityOption[];
  applicability: Record<string, unknown>;
  is_default: boolean;
};

export type LogicRule = {
  id: string;
  scope: "same_structure" | "structure_sequence";
  structure_type?: "pier" | "abutment" | "upper_structure" | "continuous_beam" | null;
  to_component: ComponentType;
  predecessor_candidates: ComponentType[];
  predecessor_strategy: "all" | "first_available";
  relationship: RelationshipType;
  lag_days: number;
  severity?: "error" | "warning";
  note: string;
};

export type UpperStructureLogicRule = {
  id: string;
  relationship: RelationshipType;
  lag_days: number;
  max_finish_gap_days?: number | null;
  severity?: "error" | "warning";
  note?: string;
};

export type ResourceCalendar = {
  id: string;
  name: string;
  working_weekdays: number[];
  blackout_dates: string[];
};

export type ResourcePool = {
  id: string;
  type: string;
  label: string;
  resource_mode?: ResourceMode;
  quantity: number | null;
  max_quantity?: number | null;
  calendar_id: string;
  enabled: boolean;
  compatible_process_ids: string[];
  cost_type?: ResourceCostType;
  incremental_unit_cost?: number;
  billing_period_days?: number;
  same_structure_resource_binding?: boolean;
  parallel_rule_description?: string;
};

export type MilestoneConstraint = {
  id: string;
  name: string;
  level: "contract" | "control" | "internal";
  mode: "hard" | "soft";
  scope_type: "project" | "bridge" | "work_section" | "structure" | "component";
  scope_id?: string | null;
  target_event: "start" | "finish";
  target_date: string;
  penalty_per_day: number;
  related_structure_ids?: string[];
};

export type ScenarioInput = {
  scenario_id: string;
  scenario_name: string;
  project: ProjectModel;
  process_library: ProcessTemplate[];
  logic_rules: LogicRule[];
  upper_structure_logic_rules?: UpperStructureLogicRule[];
  task_overrides?: Record<string, TaskOverride>;
  resource_calendars: ResourceCalendar[];
  resource_pools: ResourcePool[];
  milestones: MilestoneConstraint[];
  schedule_strategy?: ScheduleStrategyConfig;
  time_limit_seconds: number;
};

export type AiParameterMaterialKind = "text" | "word" | "excel" | "pdf" | "image";
export type AiParameterParseStatus = "parsed" | "partially_parsed" | "failed";
export type AiParameterRunStatus = "ready" | "extracting" | "completed" | "partially_failed" | "failed";
export type AiParameterCategory = "process_productivity" | "process_method_assignment" | "resource_pool" | "milestone";
export type AiParameterConfidence = "High" | "Medium" | "Low";
export type AiParameterSuggestionStatus =
  | "suggested"
  | "selected"
  | "needs_manual_input"
  | "conflict"
  | "ignored"
  | "applied"
  | "failed";
export type AiParameterConflictResolutionStatus =
  | "unresolved"
  | "selected_suggestion"
  | "manual_value"
  | "keep_current";
export type AiParameterCandidateValidationStatus = "valid" | "needs_manual_input" | "invalid";
export type AiParameterApplicationStatus = "pending" | "partially_applied" | "applied" | "expired";

export type AiParameterUploadedMaterialSummary = {
  material_id: string;
  file_name: string;
  kind: AiParameterMaterialKind;
  size_bytes: number;
  parse_status: AiParameterParseStatus;
  source_summary: string;
  error_message?: string | null;
};

export type AiParameterSourceEvidence = {
  material_id: string;
  excerpt: string;
  page_or_sheet?: string | null;
  cell_or_region?: string | null;
  note?: string | null;
};

export type AiParameterSuggestion = {
  suggestion_id: string;
  category: AiParameterCategory;
  target_ref: Record<string, unknown>;
  parameter_key: string;
  current_value?: unknown;
  proposed_value?: unknown;
  unit?: string | null;
  confidence_label: AiParameterConfidence;
  confidence_score: number;
  source_refs: AiParameterSourceEvidence[];
  conflict_group_id?: string | null;
  status: AiParameterSuggestionStatus;
  validation_messages: ValidationMessage[];
};

export type AiParameterConflictGroup = {
  conflict_group_id: string;
  parameter_key: string;
  target_ref: Record<string, unknown>;
  suggestion_ids: string[];
  current_value?: unknown;
  resolution_status: AiParameterConflictResolutionStatus;
  selected_suggestion_id?: string | null;
  manual_value?: unknown;
};

export type AiParameterCandidateAddition = {
  candidate_id: string;
  category: AiParameterCategory;
  display_name: string;
  proposed_fields: Record<string, unknown>;
  confidence_label: AiParameterConfidence;
  confidence_score: number;
  source_refs: AiParameterSourceEvidence[];
  validation_status: AiParameterCandidateValidationStatus;
};

export type AiParameterParseResponse = {
  run_id: string;
  status: AiParameterRunStatus;
  material_count: number;
  total_size_bytes: number;
  suggestion_count: number;
  material_summaries: AiParameterUploadedMaterialSummary[];
  errors: ValidationMessage[];
  warnings: ValidationMessage[];
  expires_at: string;
  suggestions: AiParameterSuggestion[];
  conflict_groups: AiParameterConflictGroup[];
  candidate_additions: AiParameterCandidateAddition[];
  manual_completion_count: number;
};

export type AiParameterManualValue = {
  suggestion_id?: string | null;
  conflict_group_id?: string | null;
  parameter_key?: string | null;
  value?: unknown;
};

export type AiParameterApplyRequest = {
  scenario: ScenarioInput;
  run_id: string;
  selected_suggestion_ids: string[];
  conflict_resolutions: AiParameterConflictGroup[];
  manual_values: AiParameterManualValue[];
};

export type AiParameterAppliedItem = {
  suggestion_id: string;
  category: AiParameterCategory;
  target_ref: Record<string, unknown>;
  parameter_key: string;
  old_value?: unknown;
  new_value?: unknown;
};

export type AiParameterApplicationSummary = {
  applied_count: number;
  skipped_count: number;
  failed_count: number;
  manual_pending_count: number;
  applied_items: AiParameterAppliedItem[];
  failed_items: ValidationMessage[];
  stale_result_reason: string;
};

export type AiParameterApplyResponse = {
  scenario: ScenarioInput;
  application_summary: AiParameterApplicationSummary;
  stale_results: boolean;
};

export type LocalScenarioConfig = {
  process_library: ProcessTemplate[];
  logic_rules: LogicRule[];
  upper_structure_logic_rules: UpperStructureLogicRule[];
  resource_pools: ResourcePool[];
  milestones: MilestoneConstraint[];
};

export type ProjectStructureParamsSource = "local_config" | "local_workbook" | "default_demo" | "request";

export type ProjectStructureParamsResponse = {
  project: ProjectModel;
  source: ProjectStructureParamsSource;
  warnings: Array<Record<string, unknown>>;
};

export type ProjectStructureParamsApplyResponse = {
  scenario: ScenarioInput;
  source: ProjectStructureParamsSource;
};

export type Task = {
  id: string;
  name: string;
  bridge_id?: string | null;
  work_section_id?: string | null;
  component_id?: string | null;
  sequence_order: number;
  structure_id: string;
  structure_name: string;
  structure_type: string;
  control_level?: ControlLevel;
  component_type: ComponentType;
  process_name: string;
  productivity_rule_id: string;
  quantity: number;
  quantity_label: string;
  duration_days: number;
  compatible_resource_types: string[];
  properties?: Record<string, unknown>;
};

export type ScheduledTask = Task & {
  start_offset: number;
  end_offset: number;
  start_date: string;
  finish_date: string;
  assigned_resource_id?: string | null;
  assigned_resource_name?: string | null;
  assigned_resource_type?: string | null;
  continuous_span_group_id?: string | null;
  continuous_span_group_name?: string | null;
  continuous_span_resource_id?: string | null;
  continuous_span_resource_name?: string | null;
  predecessor_ids: string[];
};

export type PrecedenceLink = {
  id: string;
  predecessor_id: string;
  successor_id: string;
  relationship: RelationshipType;
  lag_days: number;
  max_finish_gap_days?: number | null;
  source_rule_id: string;
  severity?: "error" | "warning";
};

export type Resource = {
  id: string;
  name: string;
  type: string;
  pool_id?: string | null;
  pool_label?: string | null;
  enabled: boolean;
  calendar_id: string;
  same_structure_resource_binding?: boolean;
  parallel_rule_description?: string;
};

export type ResourceAllocation = {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  task_id: string;
  task_name: string;
  start_offset: number;
  end_offset: number;
  start_date: string;
  finish_date: string;
};

export type ContinuousBeamTeamSpan = {
  span_id: string;
  span_name: string;
  bridge_id?: string | null;
  work_section_id?: string | null;
  group_index?: string | number | null;
  task_ids: string[];
  start_offset: number;
  end_offset: number;
  start_date: string;
  finish_date: string;
  resource_id?: string | null;
  resource_name?: string | null;
};

export type ContinuousBeamTeamSpanSummary = {
  enabled: boolean;
  span_count: number;
  resource_count: number;
  spans: ContinuousBeamTeamSpan[];
  diagnostics: ValidationMessage[];
};

export type MilestoneResult = MilestoneConstraint & {
  actual_date?: string | null;
  actual_offset?: number | null;
  lateness_days: number;
  penalty: number;
  status: "met" | "late" | "not_evaluated";
};

export type ValidationMessage = {
  level: "info" | "warning" | "error";
  message: string;
  subject_id?: string | null;
};

export type ScheduleInput = {
  project_name: string;
  start_date: string;
  tasks: Task[];
  precedence_links: PrecedenceLink[];
  resources: Resource[];
  milestones: MilestoneConstraint[];
  schedule_strategy?: ScheduleStrategyConfig;
  time_limit_seconds: number;
};

export type GeneratedScheduleInput = {
  schedule_input: ScheduleInput;
  validation: ValidationMessage[];
  source_summary: Record<string, unknown>;
};

export type ScheduleResult = {
  status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | "MODEL_INVALID";
  objective_days: number | null;
  plan_start_date: string;
  plan_finish_date?: string | null;
  tasks: ScheduledTask[];
  resource_allocations: ResourceAllocation[];
  milestone_results: MilestoneResult[];
  validation: ValidationMessage[];
  stats: Record<string, unknown>;
  objective_breakdown: Record<string, unknown>;
};

export type ScenarioSolveResult = {
  scenario_id: string;
  scenario_name: string;
  generated: GeneratedScheduleInput;
  result: ScheduleResult;
  milestone_results: MilestoneResult[];
  diagnostics: ValidationMessage[];
  metrics: Record<string, unknown>;
  alternative_results?: ScenarioAlternativeResult[];
};

export type ScenarioAlternativeResult = {
  scenario_id: string;
  scenario_name: string;
  role: string;
  generated: GeneratedScheduleInput;
  result: ScheduleResult;
  milestone_results: MilestoneResult[];
  diagnostics: ValidationMessage[];
  metrics: Record<string, unknown>;
};

export type CompareResponse = {
  summaries: Array<Record<string, unknown>>;
  best_scenario_id?: string | null;
  notes: string[];
};

export type ImportBridgeParamsResponse = {
  scenario: ScenarioInput;
  canonical_bridge: Record<string, unknown>;
  summary: Record<string, unknown>;
  quality_checks: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
};

export type ProcessNlChange = {
  action: string;
  process_id?: string | null;
  process_name?: string | null;
  matched_count: number;
  targets: string[];
  message: string;
};

export type ProcessNlResponse = {
  scenario: ScenarioInput;
  changes: ProcessNlChange[];
  warnings: string[];
};

export type ContinuitySplitDetail = {
  structure_id: string;
  structure_name: string;
  component_label: string;
  process_name: string;
  resource_count: number;
  resource_names: string[];
};

export type ContinuityJumpDetail = {
  resource_id: string;
  resource_name: string;
  from_location: string;
  to_location: string;
  jump_distance: number | null;
  is_jump_pier: boolean;
  is_side_switch: boolean;
  is_cross_side_jump: boolean;
  is_direction_reversal: boolean;
};

export type PathGroupDiagnostic = {
  key: string;
  bridge_id?: string | null;
  work_section_id?: string | null;
  side: string;
  side_label: string;
  resource_type: string;
  component_type: ComponentType;
  component_label: string;
  process_name: string;
  task_count: number;
  resource_count: number;
  resource_names: string[];
  structure_count: number;
  actual_sequence: string[];
};

export type ResourcePathStep = {
  task_id: string;
  task_name: string;
  location: string;
  component_type: ComponentType;
  component_label: string;
  start_date: string;
  finish_date: string;
};

export type ResourcePath = {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  task_count: number;
  start_date?: string | null;
  finish_date?: string | null;
  jump_pier_count: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  path_group_switch_count: number;
  path: ResourcePathStep[];
};

export type DrillGroupRefinementStatus =
  | "not_applicable"
  | "coarse_only"
  | "stage1_final"
  | "stage2_refined"
  | "stage2_fallback"
  | string;

export type DrillGroupRefinementDiagnostics = {
  status: DrillGroupRefinementStatus;
  coarse_group_count: number;
  coarse_child_task_count: number;
  stage2_node_count: number;
  stage2_arc_count: number;
  baseline_candidate_arc_count: number;
  arc_reduction_ratio: number;
  adjacent_resource_switch_penalty: number;
  hole_jump_penalty: number;
  makespan_tolerance: number;
  fallback_reason?: string | null;
};

export type ContinuityMetrics = {
  continuity_score: number;
  same_structure_craft_split_count: number;
  jump_pier_count: number;
  max_jump_distance: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  direction_reversal_count: number;
  path_group_switch_count: number;
  same_structure_craft_split_details: ContinuitySplitDetail[];
  jump_transition_details: ContinuityJumpDetail[];
  path_group_diagnostics: PathGroupDiagnostic[];
  resource_paths: ResourcePath[];
};

export type ControlBufferRisk = {
  task_id: string;
  task_name: string;
  control_level: ControlLevel;
  is_control_target: boolean;
  target_source: string;
  deadline_source: string;
  latest_safe_finish_date: string;
  necessary_buffer_days: number;
  finish_date: string;
  remaining_buffer_days: number;
  buffer_risk_days: number;
  status: string;
};

export type ControlPriorityTarget = {
  task_id: string;
  task_name: string;
  control_level: ControlLevel;
  component_type: ComponentType;
  source: string;
};

export type ControlObjectRef = {
  id: string;
  name: string;
};

export type ControlObject = {
  id: string;
  name: string;
  object_type: string;
  source: string;
  source_label: string;
  task_count: number;
  task_ids: string[];
  remaining_buffer_days: number | null;
  buffer_risk_days: number;
  status: string;
};

export type ControlObjectTask = {
  task_id: string;
  task_name: string;
  object_id: string;
  object_name: string;
  task_role: string;
  source: string;
  source_label: string;
  control_level: ControlLevel;
  component_type: ComponentType;
  finish_date: string;
  latest_safe_finish_date: string | null;
  remaining_buffer_days: number | null;
  buffer_risk_days: number;
  status: string;
};

export type ControlChainPredecessor = {
  task_id: string;
  task_name: string;
  source: string;
  source_label: string;
  control_level: ControlLevel;
  component_type: ComponentType;
  finish_date: string;
  latest_safe_finish_date: string | null;
  remaining_buffer_days: number | null;
  buffer_risk_days: number;
  status: string;
  deadline_source: string;
  impacted_control_objects: ControlObjectRef[];
};

export type ResourceOrganizationResource = {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  same_structure_resource_binding?: boolean;
  parallel_rule_description?: string;
  task_count: number;
  active_days: number;
  first_start_offset: number | null;
  last_end_offset: number | null;
  active_span_days: number;
  idle_days: number;
  max_idle_gap_days: number;
  idle_gap_count: number;
  utilization_within_span: number;
  project_utilization: number;
  jump_pier_count: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  path_group_switch_count: number;
};

export type ResourceOrganizationType = {
  resource_type: string;
  resource_count: number;
  used_resource_count: number;
  same_structure_resource_binding?: boolean;
  parallel_rule_description?: string;
  task_count: number;
  active_days: number;
  min_workload_days: number;
  max_workload_days: number;
  average_workload_days: number;
  workload_range_days: number;
  idle_days: number;
  max_idle_gap_days: number;
  jump_pier_count: number;
  side_switch_count: number;
  path_group_switch_count: number;
  balance_status: string;
  idle_status: string;
};

export type ResourceOrganizationAnalysis = {
  resource_count: number;
  used_resource_count: number;
  resource_balance_status: string;
  resource_idle_status: string;
  resource_path_status?: string;
  workload_balance_enabled?: boolean;
  idle_enabled?: boolean;
  path_continuity_enabled?: boolean;
  resources: ResourceOrganizationResource[];
  resource_types: ResourceOrganizationType[];
};

export type NormalBalanceBucket = {
  bucket_index: number;
  start_offset: number;
  finish_offset: number;
  task_count: number;
  duration_days: number;
  ideal_workload_floor_days?: number;
  ideal_workload_ceiling_days?: number;
  deviation_days?: number;
  task_ids?: string[];
  resource_types?: string[];
};

export type NormalBalanceMetrics = {
  bucket: BalanceBucket;
  bucket_size_days: number;
  normal_task_count: number;
  configured_resource_normal_task_count: number;
  unconfigured_resource_normal_task_count: number;
  bucket_loads: NormalBalanceBucket[];
  peak_task_count: number;
  min_task_count: number;
  peak_duration_days?: number;
  min_duration_days?: number;
  total_unconfigured_workload_days?: number;
  ideal_workload_floor_days?: number;
  ideal_workload_ceiling_days?: number;
  balance_penalty?: number;
  balance_weight?: number;
  balance_score: number;
  metric_scope?: string;
};

export type ControlPriorityAnalysis = {
  control_task_count: number;
  control_objects: ControlObject[];
  control_object_tasks: ControlObjectTask[];
  control_chain_predecessors: ControlChainPredecessor[];
  control_targets: ControlPriorityTarget[];
  control_buffer_risks: ControlBufferRisk[];
  control_buffer_status: string;
  normal_balance_status: string;
  resource_path_status: string;
  resource_balance_status?: string;
  resource_idle_status?: string;
  resource_organization_analysis?: ResourceOrganizationAnalysis;
  path_group_diagnostics: PathGroupDiagnostic[];
  fallback_reason?: string;
};

export type TaskViewFilters = {
  structureText: string;
  processText: string;
};

export type TaskViewRow = {
  task: Task;
  bridgeName: string;
  bridgeOrder: number;
  sectionName: string;
  sectionOrder: number;
  sideLabel: string;
  structureLabel: string;
  parentStructureId: string;
  parentStructureLabel: string;
  predecessorLinks: PrecedenceLink[];
  searchText: string;
};

export type TaskViewGroup = {
  id: string;
  title: string;
  subtitle: string;
  rows: TaskViewRow[];
};

export type TaskViewParentGroup = {
  id: string;
  title: string;
  subtitle: string;
  rows: TaskViewRow[];
  groups: TaskViewGroup[];
};
