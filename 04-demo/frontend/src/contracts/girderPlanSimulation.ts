export type SimulationDiagnostic = {
  level: "info" | "warning" | "error";
  code: string;
  message: string;
  subject_id?: string | null;
  subject_type?: string | null;
  entity_refs: string[];
  suggestion?: string | null;
};

export type BeamDemand = {
  beam_type_id: string;
  beam_type_name: string;
  span_count: number;
  beam_count: number;
  span_refs: string[];
};

export type LineGraphNode = {
  node_id: string;
  project_master_workpoint_id?: string | null;
  name: string;
  node_type: "yard" | "bridge" | "roadbed" | "tunnel" | "culvert" | "access" | "connection";
  side: "left" | "right" | "unknown";
  alignment_code?: string | null;
  start_mileage_m?: number | null;
  end_mileage_m?: number | null;
  sort_order: number;
  requires_erection: boolean;
  beam_demands: BeamDemand[];
  source_refs: string[];
  current_plan_finish_date?: string | null;
};

export type LineGraphEdge = {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  direction: "forward" | "reverse" | "bidirectional";
  source: "alignment_adjacency" | "manual_connection";
  transfer_days: number;
  confirmation?: {
    reason: string;
    confirmed_by: string;
    confirmed_at: string;
  } | null;
};

export type LineGraphSnapshot = {
  line_graph_id: string;
  project_id: string;
  project_master_version_id: string;
  input_fingerprint: string;
  projection_version: "girder-plan-line-graph/v1";
  status: "ready" | "warning" | "blocking";
  nodes: LineGraphNode[];
  edges: LineGraphEdge[];
  diagnostics: SimulationDiagnostic[];
};

export type BeamTypeCapacity = {
  beam_type_id: string;
  daily_capacity_pieces: number;
  initial_inventory_pieces: number;
  max_inventory_pieces?: number | null;
};

export type BeamYardPlan = {
  beam_yard_id: string;
  name: string;
  alignment_code: string;
  mileage_m: number;
  production_start_date: string;
  capacities: BeamTypeCapacity[];
  enabled: boolean;
};

export type ErectionLinePlan = {
  erection_line_id: string;
  beam_yard_id: string;
  available_date: string;
  daily_erection_capacity_pieces: number;
  first_erection_preparation_days: number;
  bridge_transfer_days: number;
  side_switch_days: number;
  enabled: boolean;
};

export type ConfirmedPathSegment = {
  from_target_node_id: string;
  to_target_node_id: string;
  edge_ids: string[];
  source: "unique_auto_path" | "user_selected_path";
};

export type ManualRoutePlan = {
  route_plan_id: string;
  beam_yard_id: string;
  erection_line_id: string;
  name: string;
  target_node_ids: string[];
  confirmed_paths: ConfirmedPathSegment[];
  confirmed: boolean;
};

export type GirderPlanSimulationParameters = {
  default_transfer_days: number;
  bridge_readiness_buffer_days: number;
  roadbed_passage_buffer_days: number;
  tunnel_passage_buffer_days: number;
  access_passage_buffer_days: number;
  post_erection_passage_buffer_days: number;
  planning_horizon_end_date: string;
  same_day_production_available: false;
};

export type CreateScenarioVersionRequest = {
  scenario_id?: string | null;
  project_id: string;
  project_master_version_id: string;
  line_graph_id: string;
  expected_latest_version_no?: number | null;
  beam_yards: BeamYardPlan[];
  erection_lines: ErectionLinePlan[];
  route_plans: ManualRoutePlan[];
  connection_overrides: LineGraphEdge[];
  parameters: GirderPlanSimulationParameters;
  created_by: string;
};

export type GirderPlanScenarioVersion = CreateScenarioVersionRequest & {
  scenario_version_id: string;
  scenario_id: string;
  version_no: number;
  status: "draft" | "ready" | "calculated" | "confirmed" | "stale" | "blocked";
  input_fingerprint: string;
  created_at: string;
  stale_reason?: string | null;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  confirmation_reason?: string | null;
};

export type ReadinessCheck = {
  code: string;
  status: "passed" | "warning" | "blocking";
  message: string;
  entity_refs: string[];
};

export type GirderPlanReadiness = {
  status: "ready" | "warning" | "blocking";
  checks: ReadinessCheck[];
  diagnostics: SimulationDiagnostic[];
  expanded_routes: Record<string, string[]>;
};

export type DailyBeamConsumption = { date: string; beam_type_id: string; erected_pieces: number };

export type BridgeErectionSchedule = {
  target_node_id: string;
  beam_yard_id: string;
  route_plan_id: string;
  sequence_index: number;
  start_date: string;
  finish_date: string;
  total_beam_count: number;
  beam_type_counts: Record<string, number>;
  daily_erection: DailyBeamConsumption[];
  controlling_factors: Array<"line_available" | "supply" | "transfer" | "side_switch" | "cross_route_passage">;
};

export type YardInventoryLedgerEntry = {
  date: string;
  beam_yard_id: string;
  beam_type_id: string;
  opening_inventory_pieces: number;
  produced_pieces: number;
  erected_pieces: number;
  closing_inventory_pieces: number;
};

export type PlannedRouteRun = {
  route_plan_id: string;
  beam_yard_id: string;
  start_date: string;
  finish_date: string;
  expanded_node_ids: string[];
  waiting_days_by_reason: Record<string, number>;
};

export type RouteDeliveryRequirement = {
  route_plan_id: string;
  required_date: string;
  buffer_days: number;
  source: string;
};

export type WorkpointDeliveryControl = {
  node_id: string;
  project_master_workpoint_id: string;
  side: "left" | "right" | "unknown";
  first_required_date: string;
  latest_delivery_date: string;
  buffer_days: number;
  controlling_source: "erection_start" | "roadbed_passage" | "tunnel_passage" | "access_passage" | "post_erection_passage";
  route_requirements: RouteDeliveryRequirement[];
  current_plan_finish_date?: string | null;
  late_days?: number | null;
  risk_status: "unknown" | "on_time" | "late";
};

export type GirderPlanSimulationRun = {
  run_id: string;
  scenario_version_id: string;
  project_master_version_id: string;
  status: "calculated" | "blocked" | "stale" | "confirmed";
  started_at: string;
  finished_at: string;
  input_fingerprint: string;
  result_fingerprint: string;
  reused_from_run_id?: string | null;
  bridge_schedules: BridgeErectionSchedule[];
  inventory_ledger: YardInventoryLedgerEntry[];
  route_runs: PlannedRouteRun[];
  workpoint_controls: WorkpointDeliveryControl[];
  diagnostics: SimulationDiagnostic[];
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  confirmation_reason?: string | null;
};
