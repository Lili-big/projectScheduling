import type { EngineeringDomain, PavementSettings, PavementTaskContext, PavementReadinessCondition, PavementSummary, PavementOptimization, PavementIdleOptimization } from "./pavement";
export type ComponentType =
  | "granular_base" | "cement_stabilized_base" | "asphalt_course" | "pavement_preparation"
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
export type WorkPointType = "road" | "bridge" | "tunnel" | "pavement";
export type WorkSectionSide = "left" | "right" | "none";
export type ResourceMode = "LIMITED" | "UNLIMITED";
export type ResourceScopeMode = "PROJECT_SHARED" | "WORKPOINT_EXCLUSIVE";
export type ResourceCostType = "none" | "monthly_rental" | "one_time_purchase";
export type ControlLevel = "control" | "key" | "normal" | "rough";
export type BalanceBucket = "week" | "month";
export type ObjectiveTermId =
  | "control_node_late"
  | "makespan_and_soft_milestone"
  | "resource_idle";
export type TabKey =
  | "projectFiles"
  | "parameterAssistant"
  | "process"
  | "logic"
  | "resources"
  | "milestones"
  | "tasks"
  | "results"
  | "girderPlanning"
  | "girderPlanSimulation"
  | "resourceAssistant"
  | "planControl"
  | "pavementProgress"
  | "progressVisualization";
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
  | "resourceAssistantGenerating"
  | "resourceAssistantSolving"
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
  structure_parameter_label?: string | null;
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
  | "not_met"
  | "infeasible"
  | "current_resources_target_failed"
  | "candidate_resources_target_met"
  | "candidate_resources_target_failed"
  | "max_resources_target_failed"
  | "physical_infeasible"
  | "unconfirmed"
  | string;

export type MinimumResourceVerification = {
  candidate_found: boolean;
  candidate_verified: boolean;
  detail_solve_attempted: boolean;
  detail_solver_call_count: number;
  detail_target_status?: TargetStatus | null;
  detail_solver_status?: string | null;
  retry_attempted: boolean;
  retry_reason?: string | null;
};

export type UnifiedSolveMetadata = {
  solve_mode?: string;
  schedule_source?: string;
  solver_call_count?: number;
  global_search_call_count?: number;
  resource_expansion_attempted?: boolean;
  objective_priority?: string[];
  global_objective_priority?: string[];
  global_search_status?: string;
  target_achievement?: TargetAchievement;
  minimum_resource_verification?: MinimumResourceVerification;
};

export type TargetAchievement = {
  business_success: boolean;
  target_status: TargetStatus;
  schedule_outcome_status?: ResourceAssistantScheduleOutcomeStatus | null;
  schedule_outcome_reason?: ResourceAssistantScheduleOutcomeReason | null;
  solver_status: string;
  target_present?: boolean;
  has_schedule?: boolean;
  optimality_proven?: boolean;
  hard_milestone_late_days: number;
  fixed_duration_overrun_days: number;
  max_target_delay_days?: number;
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

export type PressureSearchAttempt = {
  attempt: number;
  search_lower_bounds: Record<string, number>;
  candidate_quantities: Record<string, number>;
  pressure_overdue_days?: number | null;
  pressure_compression_days?: number | null;
  pressure_original_target_days?: number | null;
  pressure_target_days?: number | null;
  critical_path_minimum_days?: number | null;
  pressure_clamped_by_critical_path?: boolean;
  resource_solver_status?: string | null;
  resource_target_status?: string | null;
  full_objective_status?: string | null;
  full_objective_target_status?: string | null;
  business_success?: boolean | null;
  stop_reason?: string | null;
};

export type PressureSearchDiagnostics = {
  pressure_search_status?: string | null;
  pressure_search_stop_reason?: string | null;
  pressure_search_overdue_days?: number | null;
  pressure_search_attempt_count?: number | null;
  pressure_search_attempt_limit?: number | null;
  pressure_search_last_target_days?: number | null;
  pressure_search_original_target_days?: number | null;
  pressure_search_critical_path_minimum_days?: number | null;
  pressure_search_attempts?: PressureSearchAttempt[];
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
  structure_parameter_label?: string | null;
  control_level?: ControlLevel | null;
  properties: Record<string, unknown>;
};

export type StructureModel = {
  properties?: Record<string, unknown>;
  id: string;
  name: string;
  structure_type: "pier" | "abutment" | "pavement_section";
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
  structure_type?: "pier" | "abutment" | "upper_structure" | "continuous_beam" | "pavement_section" | null;
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

export type WorkpointResourceOverride = {
  workpoint_id: string;
  enabled?: boolean | null;
  quantity?: number | null;
  max_quantity?: number | null;
};

export type ResourcePool = {
  transfer_days?: number | null;
  id: string;
  type: string;
  label: string;
  resource_mode?: ResourceMode;
  scope_mode?: ResourceScopeMode;
  workpoint_id?: string | null;
  quantity: number | null;
  max_quantity?: number | null;
  authorized_workpoint_ids?: string[] | null;
  workpoint_overrides?: WorkpointResourceOverride[];
  calendar_id: string;
  enabled: boolean;
  compatible_process_ids: string[];
  cost_type?: ResourceCostType;
  incremental_unit_cost?: number;
  billing_period_days?: number;
  same_structure_resource_binding?: boolean;
  parallel_rule_description?: string;
};

export type ResourcePoolQuantityResult = {
  resource_pool_id: string;
  resource_type: string;
  workpoint_id?: string | null;
  scope_mode: ResourceScopeMode;
  current_quantity: number;
  recommended_quantity: number;
  max_quantity: number;
  eligible_workpoint_ids: string[];
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
  pavement_settings?: PavementSettings | null;
  engineering_domain?: EngineeringDomain;
  scenario_id: string;
  scenario_name: string;
  project_data_version_id?: string | null;
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
  girder_planning?: GirderPlanningConfig | null;
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
  project_start_date?: string | null;
  engineering_domain?: EngineeringDomain;
  project_id?: string | null;
  project_data_version_id?: string | null;
  pavement_settings?: PavementSettings | null;
  task_overrides?: Record<string, TaskOverride>;
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
  pavement_context?: PavementTaskContext | null;
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
  structure_parameter_label?: string | null;
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
  compatible_process_ids?: string[] | null;
  transfer_days?: number | null;
  id: string;
  name: string;
  type: string;
  pool_id?: string | null;
  pool_label?: string | null;
  enabled: boolean;
  calendar_id: string;
  scope_mode?: ResourceScopeMode;
  eligible_workpoint_ids: string[];
  exclusive_workpoint_id?: string | null;
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
  code?: string | null;
  entity_refs?: string[];
  suggestion?: string | null;
};

export type ScheduleInput = {
  readiness_conditions?: PavementReadinessCondition[];
  pavement_handover_scope?: import("./pavement").PavementHandoverScope | null;
  shift_regimes?: import("./pavement").PavementShiftRegime[];
  project_data_version_id?: string | null;
  engineering_domain?: EngineeringDomain;
  project_name: string;
  start_date: string;
  tasks: Task[];
  precedence_links: PrecedenceLink[];
  resources: Resource[];
  milestones: MilestoneConstraint[];
  execution_constraints?: TaskExecutionConstraint[];
  schedule_strategy?: ScheduleStrategyConfig;
  time_limit_seconds: number;
};

export type GeneratedScheduleInput = {
  schedule_input: ScheduleInput;
  validation: ValidationMessage[];
  source_summary: Record<string, unknown>;
  solve_scope: SolveScope;
};

export type SolveScope = {
  mode: "ALL" | "WORKPOINT";
  workpoint_id: string | null;
  workpoint_name: string | null;
};

export type ScheduleResult = {
  pavement_idle_optimization?: PavementIdleOptimization | null;
  pavement_optimization?: PavementOptimization | null;
  pavement_summary?: PavementSummary | null;
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

export type TaskExecutionConstraint = {
  task_id: string;
  earliest_start_offset?: number | null;
  fixed_start_offset?: number | null;
  fixed_resource_id?: string | null;
  source: string;
};

export type ResourceAssistantPlanProfile = "economy" | "balanced" | "crash" | "custom";
export type ResourceAssistantGenerationSource = "llm" | "local_fallback" | "user_adjusted";
export type ResourceAssistantGenerationMode = "llm_first" | "local_fallback_only";
export type ResourceAssistantPlanStatus =
  | "draft"
  | "ready_to_solve"
  | "stale"
  | "solving"
  | "optimal"
  | "feasible"
  | "infeasible"
  | "unknown"
  | "failed"
  | "model_invalid";
export type ResourceAssistantPlanOutcomeStatus = "met" | "not_met" | "unconfirmed" | "infeasible";
export type ResourceAssistantScheduleOutcomeStatus =
  | "duration_target_met"
  | "duration_target_not_met"
  | "no_feasible_schedule";
export type ResourceAssistantScheduleOutcomeReason =
  | "target_met"
  | "proven_late"
  | "late_unconfirmed"
  | "time_limit_no_schedule"
  | "proven_infeasible"
  | "resource_coverage_missing"
  | "target_missing";
export type ResourceAssistantRecommendationStatus = "recommended" | "no_recommendation" | "insufficient_results";
export type ResourceAssistantExplanationSource = "local" | "llm";
export type ResourceAssistantMetricSourceType = "solver_result" | "derived_diagnostic" | "demo_estimate";

export type ResourceAssistantControlPierSummary = {
  structure_id: string;
  structure_name: string;
  bridge_id?: string | null;
  bridge_name?: string | null;
  work_section_id?: string | null;
  work_section_name?: string | null;
  side: WorkSectionSide;
  support_no?: string | null;
  recognition_sources: string[];
  related_continuous_beam_group_ids: string[];
};

export type ResourceAssistantReferenceExample = {
  profile: ResourceAssistantPlanProfile;
  description: string;
  resource_quantities: Record<string, number>;
  is_hard_constraint: boolean;
};

export type ResourceAssistantProjectProfile = {
  project_name: string;
  start_date: string;
  bridge_count: number;
  work_section_count: number;
  structure_count: number;
  task_count: number;
  control_piers: ResourceAssistantControlPierSummary[];
  resource_types: Array<Record<string, unknown>>;
  continuous_beam_groups: Array<Record<string, unknown>>;
  critical_path_candidates: Array<Record<string, unknown>>;
  constraint_hints: string[];
  reference_examples: ResourceAssistantReferenceExample[];
  data_quality_messages: ValidationMessage[];
};

export type ResourceAssistantLlmGenerationContext = {
  project_profile: ResourceAssistantProjectProfile;
  target_workpoint: { workpoint_id: string; workpoint_name: string };
  editable_resource_pools: Array<Record<string, unknown>>;
  resource_types: Array<Record<string, unknown>>;
  constraint_hints: string[];
  reference_examples: ResourceAssistantReferenceExample[];
  current_resource_pools: ResourcePool[];
  rules: string[];
};

export type ResourceAssistantPlan = {
  scenario_id: string;
  scenario_name: string;
  target_workpoint_id?: string | null;
  target_workpoint_name?: string | null;
  profile: ResourceAssistantPlanProfile;
  positioning: string;
  generation_source: ResourceAssistantGenerationSource;
  generation_rationale: string;
  reference_example_used?: string | null;
  organization_strategy: string;
  validation_messages: ValidationMessage[];
  applicable_scenarios: string;
  expected_risks: string;
  resource_pools: ResourcePool[];
  changed_from_standard: boolean;
  solve_status: ResourceAssistantPlanStatus;
  stale_reason?: string | null;
};

export type ResourceAssistantGenerationRecord = {
  generation_id: string;
  source: ResourceAssistantGenerationSource;
  input_fingerprint: string;
  prompt_summary: string;
  reference_examples_used: ResourceAssistantReferenceExample[];
  constraint_hints_used: string[];
  raw_output_available: boolean;
  parsed_plan_ids: string[];
  validation_status: "valid" | "partially_valid" | "invalid";
  fallback_reason?: string | null;
};

export type ResourceAssistantLlmConfigStatus = {
  provider: string;
  model?: string | null;
  endpoint_configured: boolean;
  api_key_configured: boolean;
  timeout_seconds: number;
  status: "local_fallback" | "configured" | "failed";
  warning?: string | null;
};

export type ResourceAssistantTransferPenalty = {
  penalty_score: number;
  jump_pier_count: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  path_group_switch_count: number;
  max_jump_distance: number;
  details: Array<Record<string, unknown>>;
};

export type ResourceAssistantDemoCost = {
  total_cost: number;
  work_cost: number;
  idle_cost: number;
  mobilization_cost: number;
  transfer_cost: number;
  resource_costs: Array<Record<string, unknown>>;
  price_source: string;
  disclaimer: string;
};

export type ResourceAssistantCoreMetrics = {
  total_days?: number | null;
  plan_finish_date?: string | null;
  control_pier_release_dates: Array<Record<string, unknown>>;
  first_continuous_beam_start_date?: string | null;
  all_continuous_beams_started_date?: string | null;
  resource_utilization_by_type: Array<Record<string, unknown>>;
  average_wait_days?: number | null;
  max_wait_days?: number | null;
  control_pier_wait_days?: number | null;
  continuous_beam_wait_days?: number | null;
  transfer_penalty: ResourceAssistantTransferPenalty;
  demo_cost: ResourceAssistantDemoCost;
  target_status: string;
  not_available_reasons: string[];
};

export type ResourceAssistantPrimaryStageSummary = {
  attempted: boolean;
  solver_status?: string | null;
  max_target_delay_days?: number | null;
  makespan_days?: number | null;
  optimality_proven: boolean;
  elapsed_seconds: number;
  configured_budget_seconds: number;
};

export type ResourceAssistantSecondaryStageSummary = {
  attempted: boolean;
  solver_status?: string | null;
  resource_idle_days?: number | null;
  continuity_penalty?: number | null;
  optimality_proven: boolean;
  elapsed_seconds: number;
  configured_budget_seconds: number;
  skipped_reason?: "primary_no_schedule" | "time_budget_exhausted" | "insufficient_remaining_budget" | "idle_already_zero" | "not_applicable" | null;
  validation_failure_reason?: "primary_bounds_exceeded" | "resource_snapshot_changed" | "task_set_changed" | "no_secondary_improvement" | "model_error" | null;
};

export type ResourceAssistantOptimizationStages = {
  primary: ResourceAssistantPrimaryStageSummary;
  secondary: ResourceAssistantSecondaryStageSummary;
  selected_stage: "primary" | "secondary";
  fallback_reason?: string | null;
  total_budget_seconds: number;
  total_elapsed_seconds: number;
};

export type ResourceAssistantPlanResult = {
  scenario_id: string;
  plan_status?: ResourceAssistantPlanOutcomeStatus | null;
  schedule_outcome_status?: ResourceAssistantScheduleOutcomeStatus | null;
  schedule_outcome_reason?: ResourceAssistantScheduleOutcomeReason | null;
  solver_status?: string | null;
  input_resource_quantities: Record<string, number>;
  resource_pool_quantities?: ResourcePoolQuantityResult[];
  resource_expansion_attempted: boolean;
  optimization_stages?: ResourceAssistantOptimizationStages | null;
  generated?: GeneratedScheduleInput | null;
  result?: ScheduleResult | null;
  metrics: ResourceAssistantCoreMetrics;
  diagnostics: ValidationMessage[];
  generated_at: string;
  input_fingerprint: string;
};

export type ResourceAssistantMetricRow = {
  metric_id: string;
  metric_name: string;
  unit: string;
  values: Record<string, { value: unknown; not_available_reasons?: string[] }>;
  source_type: ResourceAssistantMetricSourceType;
  description: string;
};

export type ResourceAssistantComparison = {
  scenario_columns: Array<Record<string, string>>;
  metric_rows: ResourceAssistantMetricRow[];
  best_scenario_id?: string | null;
  comparison_notes: string[];
};

export type ResourceAssistantRecommendation = {
  recommended_scenario_id?: string | null;
  recommendation_status: ResourceAssistantRecommendationStatus;
  rule_reason: string;
  evidence: string[];
  risk_notes: string[];
  marginal_benefit_notes: string[];
  ai_explanation: string;
  explanation_source: ResourceAssistantExplanationSource;
  llm_status: ResourceAssistantLlmConfigStatus;
};

export type ResourceAssistantInitialRequest = {
  scenario: ScenarioInput;
  target_workpoint_id: string;
  generation_mode?: ResourceAssistantGenerationMode;
};

export type ResourceAssistantInitialResponse = {
  project_profile: ResourceAssistantProjectProfile;
  resource_plans: ResourceAssistantPlan[];
  plan_generation: ResourceAssistantGenerationRecord;
  reference_examples: ResourceAssistantReferenceExample[];
  constraint_hints: string[];
  llm_generation_context: ResourceAssistantLlmGenerationContext;
  llm_config_status: ResourceAssistantLlmConfigStatus;
  diagnostics: ValidationMessage[];
};

export type AiResourceQuantityRecommendation = {
  resource_type: string;
  quantity: number;
  max_quantity: number;
  reason: string;
};

export type AiWorkpointResourceRecommendation = {
  workpoint_id: string;
  resources: AiResourceQuantityRecommendation[];
};

export type AiWorkpointResourceInitializationRequest = {
  scenario: ScenarioInput;
};

export type AiWorkpointResourceInitializationSummary = {
  workpoint_count: number;
  recommended_workpoint_count: number;
  unchanged_workpoint_ids: string[];
  added_resource_count: number;
};

export type AiWorkpointResourceInitializationResponse = {
  project_data_version_id: string;
  input_fingerprint: string;
  resource_pools_to_add: ResourcePool[];
  summary: AiWorkpointResourceInitializationSummary;
  llm_config_status: ResourceAssistantLlmConfigStatus;
  diagnostics: ValidationMessage[];
};

export type ScopedResourceQuantityUpdate = {
  resource_pool_id: string;
  workpoint_id: string | null;
  quantity: number;
};

export type ResourceAssistantUpdatePlanRequest = {
  plan_id: string;
  resource_updates: Record<string, number>;
  scoped_resource_updates?: ScopedResourceQuantityUpdate[];
  resource_plan?: ResourceAssistantPlan | null;
};

export type ResourceAssistantUpdatePlanResponse = {
  resource_plan: ResourceAssistantPlan;
  invalidated_result_ids: string[];
  generation_source: ResourceAssistantGenerationSource;
  diagnostics: ValidationMessage[];
};

export type ResourceAssistantBatchSolveRequest = {
  scenario: ScenarioInput;
  resource_plans: ResourceAssistantPlan[];
  solve_scope?: string;
};

export type ResourceAssistantBatchSolveResponse = {
  project_profile: ResourceAssistantProjectProfile;
  resource_plans: ResourceAssistantPlan[];
  plan_results: ResourceAssistantPlanResult[];
  comparison: ResourceAssistantComparison;
  recommendation: ResourceAssistantRecommendation;
  diagnostics: ValidationMessage[];
};

export type ResourceAssistantSingleSolveRequest = {
  scenario: ScenarioInput;
  resource_plan: ResourceAssistantPlan;
};

export type ResourceAssistantSingleSolveResponse = {
  resource_plan: ResourceAssistantPlan;
  plan_result: ResourceAssistantPlanResult;
  diagnostics: ValidationMessage[];
};

export type ResourceAssistantResultsRequest = {
  resource_plans: ResourceAssistantPlan[];
  plan_results: ResourceAssistantPlanResult[];
};

export type ResourceAssistantRecommendationResponse = {
  comparison: ResourceAssistantComparison;
  recommendation: ResourceAssistantRecommendation;
  diagnostics: ValidationMessage[];
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

export type PlanVersionStatus = "draft" | "active" | "superseded";
export type ProgressTaskStatus = "not_started" | "in_progress" | "completed" | "paused" | "cancelled";
export type ForecastStrategy = "as_is" | "add_bottleneck_resources" | "prioritize_critical_tasks";
export type ForecastSolveStatus = "ready" | "solving" | "feasible" | "infeasible" | "failed" | "stale";
export type ForecastRiskStatus = "on_track" | "at_risk" | "late" | "insufficient_data";
export type ForecastTaskExecutionState =
  | "completed_locked"
  | "cancelled_excluded"
  | "in_progress_remaining"
  | "paused_remaining"
  | "not_started_future";
export type CriticalNodeDateSource = "actual" | "predicted" | "combined" | "unavailable";

export type PlanVersion = {
  plan_version_id: string;
  project_id: string;
  project_name: string;
  plan_type: "master";
  version_no: number;
  version_kind: "baseline" | "execution";
  status: PlanVersionStatus;
  parent_version_id?: string | null;
  source_scenario_id: string;
  scenario_snapshot: ScenarioInput;
  generated_snapshot: GeneratedScheduleInput;
  schedule_result_snapshot: ScheduleResult;
  resource_plan_snapshot: ResourceAssistantPlan;
  input_fingerprint: string;
  confirmed_by: string;
  confirmed_at: string;
  confirmation_reason: string;
  project_data_version_id?: string | null;
  scenario_version_id?: string | null;
  integrated_snapshot_id?: string | null;
  girder_result_snapshot?: GirderPlanningResult | null;
};

export type ProgressEntry = {
  task_id: string;
  status: ProgressTaskStatus;
  actual_start_date?: string | null;
  actual_finish_date?: string | null;
  percent_complete: number;
  completed_quantity?: number | null;
  remaining_quantity?: number | null;
  actual_productivity?: number | null;
  estimated_remaining_days?: number | null;
  remaining_days: number;
  remaining_days_source: "calculated" | "manual" | "baseline" | "none";
  expected_resume_date?: string | null;
  reason?: string | null;
  notes: string;
};

export type ProgressSnapshot = {
  progress_snapshot_id: string;
  plan_version_id: string;
  status_date: string;
  revision_no: number;
  is_current: boolean;
  entries: ProgressEntry[];
  data_quality_status: "valid" | "warning" | "invalid";
  validation_messages: ValidationMessage[];
  submitted_by: string;
  submitted_at: string;
  correction_reason?: string | null;
  yard_inventory_actuals: YardInventoryActual[];
  girder_execution_actuals: GirderExecutionActual[];
  girder_machine_actuals: GirderMachineActual[];
  passage_actuals: PassageActual[];
};

export type ForecastTaskState = {
  task_id: string;
  task_name: string;
  state: "baseline" | "actual" | "predicted";
  baseline_start_date?: string | null;
  baseline_finish_date?: string | null;
  actual_start_date?: string | null;
  actual_finish_date?: string | null;
  predicted_start_date?: string | null;
  predicted_finish_date?: string | null;
  assigned_resource_type?: string | null;
  assigned_resource_id?: string | null;
  progress_status?: ProgressTaskStatus | null;
  execution_state?: ForecastTaskExecutionState | null;
  remaining_days?: number | null;
  related_diagnostics: string[];
  variance_days?: number | null;
};

export type ForecastExecutionSummary = {
  completed_locked_count: number;
  cancelled_excluded_count: number;
  in_progress_remaining_count: number;
  paused_remaining_count: number;
  not_started_future_count: number;
  resource_policy: "baseline_fixed" | "bottleneck_expanded";
  sequence_policy: "baseline_order" | "critical_priority";
};

export type CriticalNodeEvidence = {
  type: "driving_task" | "bottleneck_resource" | "precedence_wait" | "data_quality" | "solver";
  message: string;
  task_ids: string[];
  resource_types: string[];
  variance_days?: number | null;
};

export type CriticalNodeForecast = {
  node_id: string;
  name: string;
  node_type: "project_finish" | "milestone";
  level?: MilestoneConstraint["level"] | null;
  mode?: MilestoneConstraint["mode"] | null;
  target_date: string;
  evaluated_date?: string | null;
  date_source: CriticalNodeDateSource;
  variance_days?: number | null;
  buffer_days?: number | null;
  status: ForecastRiskStatus;
  related_task_ids: string[];
  evidence: CriticalNodeEvidence[];
};

export type ForecastSchedule = {
  forecast_id: string;
  plan_version_id: string;
  progress_snapshot_id: string;
  status_date: string;
  strategy: ForecastStrategy;
  status: ForecastSolveStatus;
  input_fingerprint: string;
  historical_tasks: ForecastTaskState[];
  predicted_tasks: ForecastTaskState[];
  schedule_result?: ScheduleResult | null;
  execution_summary: ForecastExecutionSummary;
  critical_nodes: CriticalNodeForecast[];
  risk_status: ForecastRiskStatus;
  risk_evidence: Array<Record<string, unknown>>;
  confidence: "high" | "medium" | "low";
  metrics: Record<string, unknown>;
  diagnostics: ValidationMessage[];
  created_at: string;
};

export type AdjustmentProposal = {
  proposal_id: string;
  forecast_id: string;
  plan_version_id: string;
  strategy: ForecastStrategy;
  status: ForecastSolveStatus;
  strategy_parameters: Record<string, unknown>;
  forecast: ForecastSchedule;
  metrics: Record<string, unknown>;
  recommended: boolean;
  recommendation_reason: string;
  explanation: string;
  diagnostics: ValidationMessage[];
  created_at: string;
};

export type PlanControlProjectSummary = {
  project_id: string;
  active_plan?: PlanVersion | null;
  plan_versions: PlanVersion[];
  current_progress_snapshot?: ProgressSnapshot | null;
  latest_forecast?: ForecastSchedule | null;
};

export type CreateBaselinePlanRequest = {
  scenario: ScenarioInput;
  resource_plan: ResourceAssistantPlan;
  plan_result: ResourceAssistantPlanResult;
  confirmed_by: string;
  confirmation_reason: string;
  integrated_snapshot_id?: string | null;
};

export type CreateProgressSnapshotRequest = {
  plan_version_id: string;
  status_date: string;
  entries: ProgressEntry[];
  submitted_by: string;
  correction_reason?: string | null;
  expected_revision_no?: number | null;
  yard_inventory_actuals?: YardInventoryActual[];
  girder_execution_actuals?: GirderExecutionActual[];
  girder_machine_actuals?: GirderMachineActual[];
  passage_actuals?: PassageActual[];
};

export type CreateProgressSnapshotResponse = {
  progress_snapshot: ProgressSnapshot;
  stale_forecast_ids: string[];
  stale_integrated_snapshot_ids: string[];
  diagnostics: ValidationMessage[];
};

export type AdjustmentComparisonResponse = {
  forecast_id: string;
  proposals: AdjustmentProposal[];
  recommended_proposal_id?: string | null;
};

export type AdoptAdjustmentResponse = {
  new_plan_version: PlanVersion;
  previous_plan_version: PlanVersion;
  change_record: Record<string, unknown>;
};

export type GirderSide = "left" | "right" | "both" | "unknown";
export type ProjectDataVersionStatus = "draft" | "confirmed" | "superseded";
export type PlanningScenarioVersionStatus = "draft" | "specialty_confirmed" | "stale" | "superseded";
export type IntegratedCalculationStatus =
  | "running"
  | "converged"
  | "not_converged"
  | "infeasible"
  | "blocked"
  | "stale";

export type SourceEvidence = {
  evidence_id: string;
  source_type: "structure_import" | "girder_import" | "manual";
  authority_domain: "structure" | "girder_workpoint" | "user_config";
  field_path: string;
  file_name?: string | null;
  sheet_name?: string | null;
  row_or_region?: string | null;
  original_value?: unknown;
  normalized_value?: unknown;
};

export type FieldConflict = {
  conflict_id: string;
  entity_ref: string;
  field_path: string;
  severity: "warning" | "blocking";
  status: "unresolved" | "resolved";
  candidate_values: Array<{ source_evidence_id: string; value: unknown }>;
  selected_value?: unknown;
  resolution_reason?: string | null;
};

export type PassageConditionRef = {
  ref_type: "structure" | "upper_structure" | "milestone";
  entity_id: string;
  target_event: "finish";
};

export type GirderWorkPoint = {
  workpoint_id: string;
  name: string;
  workpoint_type: "roadbed" | "bridge" | "tunnel" | "culvert" | "access";
  side: GirderSide;
  mileage_start_m: number;
  mileage_end_m: number;
  corridor_id: string;
  bridge_id?: string | null;
  work_section_id?: string | null;
  requires_erection: boolean;
  rough_granularity: boolean;
  explicit_readiness_date?: string | null;
  linked_condition_refs: PassageConditionRef[];
  properties?: Record<string, unknown>;
};

export type CreateProjectDataVersionRequest = {
  project: ProjectModel;
  workpoints: GirderWorkPoint[];
  source_evidence: SourceEvidence[];
  field_conflicts: FieldConflict[];
  expected_latest_version_no?: number | null;
  created_by: string;
};

export type ProjectDataVersion = CreateProjectDataVersionRequest & {
  project_data_version_id: string;
  project_id: string;
  version_no: number;
  status: ProjectDataVersionStatus;
  input_fingerprint: string;
  created_at: string;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  confirmation_reason?: string | null;
};

export type BeamYardConfig = {
  beam_yard_id: string;
  name: string;
  mileage_m: number;
  side: GirderSide;
  corridor_id: string;
  production_start_date: string;
  daily_production_capacity: number;
  initial_inventory_by_type: Record<string, number>;
  max_inventory_by_type?: Record<string, number> | null;
  calendar_id: string;
  enabled: boolean;
};

export type ErectionMachineConfig = {
  erection_machine_id: string;
  name: string;
  beam_yard_id: string;
  available_date: string;
  daily_erection_capacity: number;
  first_span_preparation_days: number;
  span_launching_days: number;
  bridge_transfer_days: number;
  side_switch_days: number;
  calendar_id: string;
  enabled: boolean;
};

export type GirderRouteNode = {
  route_node_id: string;
  workpoint_id: string;
  sequence_index: number;
  node_kind: "workpoint" | "turn" | "connection";
  connection_days?: number | null;
};

export type GirderRouteConfig = {
  route_id: string;
  name: string;
  beam_yard_id: string;
  erection_machine_id: string;
  route_direction: "mileage_increasing" | "mileage_decreasing" | "custom";
  enabled: boolean;
  confirmed: boolean;
  nodes: GirderRouteNode[];
};

export type ErectionOwnerOverride = {
  bridge_id: string;
  side: "left" | "right";
  owner_route_id: string;
  reason: string;
  confirmed_by: string;
  confirmed_at: string;
};

export type PassageOverride = {
  workpoint_id: string;
  action: "include" | "exclude" | "readiness";
  related_route_id?: string | null;
  explicit_readiness_date?: string | null;
  reason: string;
};

export type GirderPlanningParameters = {
  substructure_acceptance_buffer_days: number;
  roadbed_passage_buffer_days: number;
  tunnel_passage_buffer_days: number;
  post_erection_passage_buffer_days: number;
  post_erection_buffer_confirmed: boolean;
  default_transfer_days: number;
  default_bridge_preparation_days: number;
  max_iterations: number;
  date_tolerance_days: 0;
  enable_supply_constraint: true;
  enable_passage_constraint: true;
  enable_stock_limit: true;
};

export type GirderPlanningConfig = {
  enabled: boolean;
  beam_yards: BeamYardConfig[];
  erection_machines: ErectionMachineConfig[];
  routes: GirderRouteConfig[];
  parameters: GirderPlanningParameters;
  owner_overrides: ErectionOwnerOverride[];
  manual_passage_overrides: PassageOverride[];
  coarse_mode: boolean;
};

export type CreatePlanningScenarioVersionRequest = {
  scenario: ScenarioInput;
  project_data_version_id: string;
  girder_planning: GirderPlanningConfig;
  expected_latest_version_no?: number | null;
  created_by: string;
};

export type PlanningScenarioVersion = CreatePlanningScenarioVersionRequest & {
  scenario_version_id: string;
  scenario_id: string;
  version_no: number;
  status: PlanningScenarioVersionStatus;
  input_fingerprint: string;
  created_at: string;
  specialty_confirmed_by?: string | null;
  specialty_confirmed_at?: string | null;
  specialty_confirmation_reason?: string | null;
};

export type GirderPlanningReadiness = {
  status: "ready" | "warning" | "blocking";
  checks: Array<{
    code: string;
    status: "passed" | "warning" | "blocking";
    message: string;
    entity_refs: string[];
  }>;
  diagnostics: ValidationMessage[];
};

export type GirderImportPreview = {
  workpoints: GirderWorkPoint[];
  source_evidence: SourceEvidence[];
  field_conflicts: FieldConflict[];
  diagnostics: ValidationMessage[];
};

export type ErectionOwnership = {
  bridge_id: string;
  side: GirderSide;
  owner_route_id: string;
  owner_node_id: string;
  arrival_date: string;
  resolution_source: "earliest_arrival" | "manual_override" | "actual_fact";
  competing_occurrences: Array<{ route_id: string; route_node_id: string; arrival_date: string }>;
};

export type GirderSpanPlan = {
  task_id: string;
  bridge_id: string;
  work_section_id: string;
  span_id: string;
  route_id: string;
  beam_yard_id: string;
  erection_machine_id: string;
  beam_type: string;
  beam_count: number;
  earliest_start_date: string;
  suggested_latest_finish_date?: string | null;
  planned_start_date?: string | null;
  planned_finish_date?: string | null;
  inventory_before?: number | null;
  inventory_after?: number | null;
  diagnostic_refs: string[];
};

export type PassageReleaseResult = {
  workpoint_id: string;
  passable_date?: string | null;
  erection_buffer_date?: string | null;
  explicit_readiness_date?: string | null;
  linked_condition_finish_dates: Record<string, string>;
  controlling_source: "erection_buffer" | "explicit_readiness" | "linked_condition" | "actual_fact" | "none";
  status: "ready" | "waiting" | "blocked";
};

export type YardInventoryPoint = {
  beam_yard_id: string;
  beam_type: string;
  date: string;
  opening_inventory: number;
  produced: number;
  consumed: number;
  closing_inventory: number;
  max_inventory?: number | null;
};

export type RouteRun = {
  route_id: string;
  beam_yard_id: string;
  erection_machine_id: string;
  start_date: string;
  finish_date: string;
  waiting_days: number;
  event_refs: string[];
};

export type LatestFinishControl = {
  entity_ref: string;
  controlled_by: string;
  latest_finish_date: string;
  mode: "soft";
  priority: number;
};

export type GirderPlanningResult = {
  result_id: string;
  status: "ready" | "blocked";
  ownerships: ErectionOwnership[];
  span_plans: GirderSpanPlan[];
  passage_releases: PassageReleaseResult[];
  yard_inventory_series: YardInventoryPoint[];
  route_runs: RouteRun[];
  latest_finish_controls: LatestFinishControl[];
  diagnostics: ValidationMessage[];
  input_fingerprint: string;
};

export type IntegratedIterationRecord = {
  iteration_no: number;
  input_fingerprint: string;
  ownership_fingerprint: string;
  date_state_fingerprint: string;
  girder_result_id: string;
  schedule_status: "feasible" | "infeasible" | "blocked";
  changed_owner_refs: string[];
  changed_date_refs: string[];
  started_at?: string | null;
  finished_at?: string | null;
};

export type IntegratedCalculationSnapshot = {
  integrated_snapshot_id: string;
  project_data_version_id: string;
  scenario_version_id: string;
  progress_snapshot_id?: string | null;
  status: IntegratedCalculationStatus;
  iterations: IntegratedIterationRecord[];
  girder_result?: GirderPlanningResult | null;
  generated_snapshot?: GeneratedScheduleInput | null;
  schedule_result?: ScheduleResult | null;
  input_fingerprint: string;
  diagnostics: ValidationMessage[];
  created_at: string;
};

export type YardInventoryActual = {
  beam_yard_id: string;
  beam_type: string;
  cumulative_produced: number;
  opening_inventory_adjustment: number;
  observed_inventory: number;
  adjustment_reason?: string | null;
  source: "manual" | "excel";
};

export type GirderExecutionActual = {
  span_task_id: string;
  status: "not_started" | "in_progress" | "completed";
  actual_route_id?: string | null;
  actual_start_date?: string | null;
  actual_finish_date?: string | null;
  erected_beam_count: number;
  erection_machine_id?: string | null;
};

export type GirderMachineActual = {
  erection_machine_id: string;
  position_workpoint_id?: string | null;
  availability_status: "available" | "unavailable" | "maintenance";
  expected_resume_date?: string | null;
  reason?: string | null;
};

export type PassageActual = {
  workpoint_id: string;
  status: "closed" | "conditional" | "open";
  actual_open_date?: string | null;
  restrictions?: string | null;
};

export type GirderProgressImportPreview = {
  source_file_name: string;
  yard_inventory_actuals: YardInventoryActual[];
  girder_execution_actuals: GirderExecutionActual[];
  girder_machine_actuals: GirderMachineActual[];
  passage_actuals: PassageActual[];
  diagnostics: ValidationMessage[];
};

export type PavementIdleOptimizeRequest = { scenario: ScenarioInput; baseline: ScenarioSolveResult; time_budget_seconds?: number | null };
