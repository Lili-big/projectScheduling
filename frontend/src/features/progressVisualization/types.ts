import type { ComponentType, ForecastRiskStatus } from "../../types/scheduler";

export type ProgressVisualizationView = "route" | "bridge";
export type ProgressVisualizationMode = "progress" | "variance";
export type ProgressVisualizationState =
  | "ready"
  | "no_plan"
  | "no_snapshot"
  | "no_forecast"
  | "stale"
  | "insufficient_data";

export type ScenePosition = { x: number; y: number };

export type ProgressVisualizationSceneConfig = {
  bridgePositions?: Record<string, ScenePosition>;
  structurePositions?: Record<string, ScenePosition>;
};

export type ProgressVisualizationOverview = {
  plannedProgress: number | null;
  actualProgress: number | null;
  progressVariance: number | null;
  coverage: number | null;
  baselineFinishDate: string | null;
  predictedFinishDate: string | null;
  finishVarianceDays: number | null;
  lateMilestoneCount: number | null;
};

export type BridgeProgressSummary = {
  id: string;
  name: string;
  plannedProgress: number;
  actualProgress: number;
  finishVarianceDays: number | null;
  riskStatus: ForecastRiskStatus;
  completedTasks: number;
  totalTasks: number;
  position: ScenePosition;
};

export type ComponentProgressSummary = {
  componentType: ComponentType;
  label: string;
  plannedProgress: number;
  actualProgress: number;
  variance: number;
  completedTasks: number;
  totalTasks: number;
};

export type StructureProgressStatus =
  | "completed"
  | "in_progress"
  | "ahead"
  | "late"
  | "on_track"
  | "not_started";

export type StructureProgressMarker = {
  id: string;
  name: string;
  bridgeId: string;
  plannedProgress: number;
  actualProgress: number;
  varianceDays: number | null;
  status: StructureProgressStatus;
  position: ScenePosition;
};

export type ProgressMilestone = {
  id: string;
  name: string;
  targetDate: string;
  predictedDate: string | null;
  latenessDays: number;
  scopeId: string | null;
  status: "met" | "late" | "not_evaluated";
};

export type ProgressRiskEvidence = {
  id: string;
  type: "project_finish" | "milestone" | "buffer" | "solver";
  message: string;
  varianceDays: number | null;
  milestoneId: string | null;
  bridgeId: string | null;
};

export type ProgressDiagnostic = {
  criticalTasks: string[];
  bottleneckResources: string[];
  resourceSuggestions: string[];
  jumpPierCount: number;
  sideSwitchCount: number;
  pathGroupSwitchCount: number;
  waitingStatus: string;
};

export type ProgressCurvePoint = {
  date: string;
  value: number;
};

export type ProgressVisualizationData = {
  state: ProgressVisualizationState;
  projectId: string;
  projectName: string;
  planVersionLabel: string;
  planStatusLabel: string;
  confirmedAt: string | null;
  statusDate: string | null;
  revisionNo: number | null;
  dataQuality: "valid" | "warning" | "invalid" | "unavailable";
  forecastConfidence: "high" | "medium" | "low" | null;
  forecastRiskStatus: ForecastRiskStatus | null;
  overview: ProgressVisualizationOverview;
  bridges: BridgeProgressSummary[];
  selectedBridgeId: string | null;
  components: ComponentProgressSummary[];
  structures: StructureProgressMarker[];
  milestones: ProgressMilestone[];
  riskEvidence: ProgressRiskEvidence[];
  diagnostics: ProgressDiagnostic;
  curve: {
    baseline: ProgressCurvePoint[];
    forecast: ProgressCurvePoint[];
    actual: ProgressCurvePoint | null;
  };
};

