export type ProjectMasterWorkpointType =
  | "bridge"
  | "roadbed"
  | "tunnel"
  | "culvert"
  | "interchange"
  | "service_area"
  | "station_yard"
  | "access_road"
  | "other";

export type ProjectMasterSide = "left" | "right" | "shared" | "none";
export type ProjectMasterVersionStatus = "draft" | "confirmed" | "superseded";
export type ProjectMasterImportStatus =
  | "uploaded"
  | "validating"
  | "blocked"
  | "ready"
  | "confirmed"
  | "cancelled"
  | "failed"
  | "unchanged";

export type ProjectMasterSource = {
  batch_id?: string | null;
  sheet_name: string;
  row_no: number;
  column_name?: string | null;
};

export type ProjectMasterParameter = {
  parameter_code: string;
  value_type: "text" | "number" | "integer" | "boolean" | "date";
  value: unknown;
  unit?: string | null;
  sort_order: number;
  source?: ProjectMasterSource | null;
};

export type ProjectMasterComponent = {
  component_id: string;
  structure_id: string;
  component_name: string;
  component_type: string;
  quantity: number;
  unit: string;
  enabled: boolean;
  sort_order: number;
  remark?: string | null;
  parameters: ProjectMasterParameter[];
  source?: ProjectMasterSource | null;
};

export type ProjectMasterStructure = {
  structure_id: string;
  workpoint_id: string;
  structure_name: string;
  structure_category: string;
  structure_type: string;
  side: ProjectMasterSide;
  section_code?: string | null;
  section_name?: string | null;
  control_level?: string | null;
  sort_order: number;
  remark?: string | null;
  parameters: ProjectMasterParameter[];
  components: ProjectMasterComponent[];
  source?: ProjectMasterSource | null;
};

export type ProjectMasterWorkpoint = {
  workpoint_id: string;
  workpoint_name: string;
  workpoint_type: ProjectMasterWorkpointType;
  alignment_code?: string | null;
  start_mileage_m?: number | null;
  end_mileage_m?: number | null;
  sort_order: number;
  schedule_support: "bridge_supported" | "not_supported";
  remark?: string | null;
  structures: ProjectMasterStructure[];
  source?: ProjectMasterSource | null;
};

export type ProjectMasterCounts = {
  workpoints: number;
  structures: number;
  components: number;
  errors: number;
  warnings: number;
};

export type ProjectMasterDiffCounts = { added: number; modified: number; deleted: number };

export type ProjectMasterIssue = {
  issue_id: string;
  severity: "error" | "warning";
  issue_code: string;
  sheet_name: string;
  row_no?: number | null;
  field_name?: string | null;
  object_kind?: string | null;
  object_id?: string | null;
  message: string;
  suggestion?: string | null;
};

export type ProjectMasterDiffEntry = {
  diff_id?: string | null;
  object_kind: "workpoint" | "structure" | "component" | "parameter";
  object_id: string;
  change_type: "added" | "modified" | "deleted" | "unchanged";
  field_name?: string | null;
  before_value?: unknown;
  after_value?: unknown;
  blocking_reference: boolean;
};

export type ProjectMasterImportBatch = {
  batch_id: string;
  project_id: string;
  status: ProjectMasterImportStatus;
  file_name: string;
  file_sha256: string;
  content_fingerprint?: string | null;
  expected_current_version_id?: string | null;
  created_version_id?: string | null;
  existing_version_id?: string | null;
  cancelled_version_id?: string | null;
  counts: ProjectMasterCounts;
  diff_counts: ProjectMasterDiffCounts;
  issues: ProjectMasterIssue[];
  created_at: string;
  created_by: string;
  completed_at?: string | null;
  failure_message?: string | null;
};

export type ProjectMasterVersionSummary = {
  version_id: string;
  project_id: string;
  version_no: number;
  status: ProjectMasterVersionStatus;
  content_fingerprint: string;
  source_batch_id: string;
  base_version_id?: string | null;
  counts: ProjectMasterCounts;
  created_at: string;
  created_by: string;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
};

export type ProjectMasterVersionDetail = ProjectMasterVersionSummary & {
  diff_counts: ProjectMasterDiffCounts;
  diff_entries: ProjectMasterDiffEntry[];
  warning_codes: string[];
};

export type ProjectMasterVersionPage = { page: number; page_size: number; total: number; items: ProjectMasterVersionSummary[] };
export type ProjectMasterWorkpointPage = { page: number; page_size: number; total: number; items: ProjectMasterWorkpoint[] };
