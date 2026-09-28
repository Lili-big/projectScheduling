export type EngineeringDomain = "bridge" | "pavement";
export type PavementOptimization = {
  search_workers?: number | null;
  lns_enabled?: boolean | null;
  time_budget_seconds?: number | null;
  improvement_count?: number | null;
  method: "greedy_cpsat";
  initial_strategy: "earliest_start" | "longest_chain" | "least_transfer" | null;
  valid_candidate_count: number;
  initial_days: number | null;
  final_days: number | null;
  improvement_days: number | null;
  selected_source: "greedy" | "cp_sat" | null;
  optimizer_status: "OPTIMAL" | "FEASIBLE" | "UNKNOWN" | "INFEASIBLE" | "MODEL_INVALID" | null;
  optimizer_not_run_reason: "budget_exhausted" | null;
  outcome: "improved" | "initial_retained" | "cp_sat_only" | "no_plan" | "inconsistent";
  initial_plan_seconds: number; model_build_seconds: number; cp_sat_seconds: number; total_seconds: number;
};
export type PavementProcessType = "granular_base" | "cement_stabilized_base" | "asphalt_course";
export type PavementLayerCondition = {
  component_id: string; wait_days: number; accepted_available_date?: string | null; basis_note: string;
};
export type PavementAncillaryStep = {
  id: string; structure_id: string; before_component_id: string;
  kind: "prime" | "seal" | "tack" | "other_preparation";
  name: string; duration_days: number; wait_after_days: number;
  available_date?: string | null; order: number; basis_note: string;
};
export type PavementFixedSequence = { process_type: PavementProcessType; component_ids: string[] };
export type PavementDependencyRule = {
  structure_id?: string | null; predecessor_key: string; successor_key: string;
  relationship: "FS" | "SS" | "FF" | "SF"; lag_days: number | null;
};
export type PavementSettings = {
  layer_conditions: PavementLayerCondition[]; ancillary_steps: PavementAncillaryStep[];
  fixed_sequences: PavementFixedSequence[]; input_kind: "customer" | "demo";
  dependency_rules?: PavementDependencyRule[];
};
export type PavementTaskContext = {
  process_id?: string | null;
  source_component_id: string; position_id: string; task_kind: "construction" | "preparation";
  process_type: PavementProcessType; quantity_basis: string; input_kind: "customer" | "demo";
};
export type PavementReadinessCondition = {
  id: string; terminal_task_id: string; source_component_id: string; wait_days: number; available_offset: number;
};
export type PavementReadiness = PavementReadinessCondition & { position_id: string; ready_offset: number; ready_date: string };
export type PavementWaitInterval = { source_component_id: string; start_offset: number; end_offset: number; reason: string };
export type PavementTransfer = {
  resource_id: string; from_task_id: string; to_task_id: string; from_position_id: string;
  to_position_id: string; start_offset: number; end_offset: number;
};
export type PavementSummary = {
  input_kind: "customer" | "demo"; input_fingerprint: string; project_data_version_id?: string | null;
  construction_finish_offset: number; construction_finish_date: string; ready_offset: number; ready_date: string;
  readiness: PavementReadiness[]; wait_intervals: PavementWaitInterval[]; transfers: PavementTransfer[];
  resource_assumptions: string[];
  pending_section_dates?: PavementPendingSectionDates[] | null;
};
export type PavementHandoverStatus = "dated" | "handed_over" | "pending";
export type PavementBlockedSection = { structure_id: string; section_name: string; reason: string; component_ids: string[] };
export type PavementPendingSection = { structure_id: string; section_name: string; reason: string; component_ids: string[] };
export type PavementPendingSectionDates = { structure_id: string; required_handover_date: string; estimated_finish_date: string };
export type PavementHandoverScope = {
  total_section_count: number; included_section_count: number; included_layer_count: number;
  blocked_sections: PavementBlockedSection[];
  pending_policy?: "strict_last" | "per_fleet_last" | null;
  pending_sections?: PavementPendingSection[] | null;
};

export type PavementIdleOptimization = {
  goal: "min_idle_with_makespan_cap"; metric: "fleet_internal_idle_v1";
  baseline_input_fingerprint: string; makespan_cap_days: number;
  baseline_idle_days: number; final_idle_days: number; improvement_idle_days: number;
  baseline_transfer_days: number; final_transfer_days: number; improvement_count: number;
  selected_source: "baseline" | "cp_sat"; outcome: "baseline_retained" | "improved" | "inconsistent";
  optimizer_status: "OPTIMAL" | "FEASIBLE" | "UNKNOWN" | "INFEASIBLE" | "MODEL_INVALID" | null;
  optimizer_not_run_reason: "budget_exhausted" | "zero_idle" | null; proved_optimal: boolean;
  search_workers: number | null; lns_enabled: boolean | null; time_budget_seconds: number;
  model_build_seconds: number; cp_sat_seconds: number; total_seconds: number;
};
