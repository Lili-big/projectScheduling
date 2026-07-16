import { apiGet, apiPost, apiPostFormData, apiPut } from "./client";
import type {
  AiParameterApplyRequest,
  AiParameterApplyResponse,
  AiParameterParseResponse,
  CompareResponse,
  GeneratedScheduleInput,
  ImportBridgeParamsResponse,
  LocalScenarioConfig,
  ProcessNlResponse,
  ProcessTemplate,
  ProjectModel,
  ProjectStructureParamsApplyResponse,
  ProjectStructureParamsResponse,
  ResourceAssistantBatchSolveRequest,
  ResourceAssistantBatchSolveResponse,
  ResourceAssistantComparison,
  ResourceAssistantInitialRequest,
  ResourceAssistantInitialResponse,
  ResourceAssistantRecommendationResponse,
  ResourceAssistantResultsRequest,
  ResourceAssistantSingleSolveRequest,
  ResourceAssistantSingleSolveResponse,
  ResourceAssistantUpdatePlanRequest,
  ResourceAssistantUpdatePlanResponse,
  PlanVersion,
  PlanControlProjectSummary,
  CreateBaselinePlanRequest,
  CreateProgressSnapshotRequest,
  CreateProgressSnapshotResponse,
  ForecastSchedule,
  AdjustmentComparisonResponse,
  AdoptAdjustmentResponse,
  ScenarioInput,
  ScenarioSolveResult,
  CreatePlanningScenarioVersionRequest,
  CreateProjectDataVersionRequest,
  GirderPlanningReadiness,
  GirderPlanningResult,
  GirderProgressImportPreview,
  IntegratedCalculationSnapshot,
  PlanningScenarioVersion,
  ProjectDataVersion,
} from "../types/scheduler";

type ScenarioCompareRequest = {
  results: ScenarioSolveResult[];
};

type MinResourcesSolveRequest = {
  scenario: ScenarioInput;
  fallback_target_days: number | null;
};

type ResourceCostSolveRequest = {
  scenario: ScenarioInput;
  fallback_target_days: number | null;
};

type ProcessNlRequest = {
  scenario: ScenarioInput;
  prompt: string;
};

type ProcessLibrarySaveRequest = {
  process_library: ProcessTemplate[];
};

type LocalScenarioConfigSaveRequest = LocalScenarioConfig;

type ProjectStructureParamsApplyRequest = {
  scenario: ScenarioInput;
  project: ProjectModel;
};

type ProjectStructureParamsSaveRequest = {
  project: ProjectModel;
};

export function getDemoScenario(): Promise<ScenarioInput> {
  return apiGet<ScenarioInput>("/api/demo-scenario");
}

export function getProjectStructureParams(): Promise<ProjectStructureParamsResponse> {
  return apiGet<ProjectStructureParamsResponse>("/api/project-structure-params");
}

export function applyProjectStructureParams(
  request: ProjectStructureParamsApplyRequest,
): Promise<ProjectStructureParamsApplyResponse> {
  return apiPost<ProjectStructureParamsApplyResponse>("/api/apply-project-structure-params", request);
}

export function saveProjectStructureParams(request: ProjectStructureParamsSaveRequest): Promise<ProjectStructureParamsResponse> {
  return apiPut<ProjectStructureParamsResponse>("/api/project-structure-params", request);
}

export function importLocalBridgeParams(scenario: ScenarioInput): Promise<ImportBridgeParamsResponse> {
  return apiPost<ImportBridgeParamsResponse>("/api/import-local-bridge-params", scenario);
}

export function generateScheduleInput(scenario: ScenarioInput): Promise<GeneratedScheduleInput> {
  return apiPost<GeneratedScheduleInput>("/api/generate-schedule-input", scenario);
}

export function solveScenario(scenario: ScenarioInput): Promise<ScenarioSolveResult> {
  return apiPost<ScenarioSolveResult>("/api/solve-scenario", scenario);
}

export function solveMinResources(request: MinResourcesSolveRequest): Promise<ScenarioSolveResult> {
  return apiPost<ScenarioSolveResult>("/api/solve-min-resources", request);
}

export function solveResourceCost(request: ResourceCostSolveRequest): Promise<ScenarioSolveResult> {
  return apiPost<ScenarioSolveResult>("/api/solve-resource-cost", request);
}

export function compareScenarios(request: ScenarioCompareRequest): Promise<CompareResponse> {
  return apiPost<CompareResponse>("/api/compare-scenarios", request);
}

export function initializeAiResourceAssistant(
  request: ResourceAssistantInitialRequest,
): Promise<ResourceAssistantInitialResponse> {
  return apiPost<ResourceAssistantInitialResponse>("/api/ai-resource-assistant/initialize", request);
}

export function updateAiResourceAssistantPlan(
  request: ResourceAssistantUpdatePlanRequest,
): Promise<ResourceAssistantUpdatePlanResponse> {
  return apiPost<ResourceAssistantUpdatePlanResponse>("/api/ai-resource-assistant/update-plan", request);
}

export function batchSolveAiResourceAssistant(
  request: ResourceAssistantBatchSolveRequest,
): Promise<ResourceAssistantBatchSolveResponse> {
  return apiPost<ResourceAssistantBatchSolveResponse>("/api/ai-resource-assistant/batch-solve", request);
}

export function solveAiResourceAssistantPlan(
  request: ResourceAssistantSingleSolveRequest,
): Promise<ResourceAssistantSingleSolveResponse> {
  return apiPost<ResourceAssistantSingleSolveResponse>("/api/ai-resource-assistant/solve-plan", request);
}

export function compareAiResourceAssistantResults(
  request: ResourceAssistantResultsRequest,
): Promise<ResourceAssistantComparison> {
  return apiPost<ResourceAssistantComparison>("/api/ai-resource-assistant/compare-results", request);
}

export function generateAiResourceAssistantRecommendation(
  request: ResourceAssistantResultsRequest,
): Promise<ResourceAssistantRecommendationResponse> {
  return apiPost<ResourceAssistantRecommendationResponse>("/api/ai-resource-assistant/generate-recommendation", request);
}

export function createBaselinePlan(request: CreateBaselinePlanRequest): Promise<PlanVersion> {
  return apiPost<PlanVersion>("/api/plan-control/baselines", request);
}

export function getPlanControlProject(projectId: string): Promise<PlanControlProjectSummary> {
  return apiGet<PlanControlProjectSummary>(`/api/plan-control/projects/${encodeURIComponent(projectId)}`);
}

export function saveProgressSnapshot(request: CreateProgressSnapshotRequest): Promise<CreateProgressSnapshotResponse> {
  return apiPost<CreateProgressSnapshotResponse>("/api/plan-control/progress-snapshots", request);
}

export function generateProgressForecast(planVersionId: string, progressSnapshotId: string): Promise<ForecastSchedule> {
  return apiPost<ForecastSchedule>("/api/plan-control/forecasts", {
    plan_version_id: planVersionId,
    progress_snapshot_id: progressSnapshotId,
  });
}

export function generateAdjustmentProposals(
  forecastId: string,
  maxResourceIncrements: Record<string, number> = {},
): Promise<AdjustmentComparisonResponse> {
  return apiPost<AdjustmentComparisonResponse>(`/api/plan-control/forecasts/${encodeURIComponent(forecastId)}/adjustments`, {
    max_resource_increments: maxResourceIncrements,
  });
}

export function adoptAdjustmentProposal(
  proposalId: string,
  request: { confirmed_by: string; adoption_reason: string; source_plan_fingerprint: string },
): Promise<AdoptAdjustmentResponse> {
  return apiPost<AdoptAdjustmentResponse>(`/api/plan-control/adjustments/${encodeURIComponent(proposalId)}/adopt`, request);
}

export function uploadBridgeParams(payload: FormData): Promise<ImportBridgeParamsResponse> {
  return apiPostFormData<ImportBridgeParamsResponse>("/api/import-bridge-params", payload);
}

export function applyProcessNaturalLanguage(request: ProcessNlRequest): Promise<ProcessNlResponse> {
  return apiPost<ProcessNlResponse>("/api/apply-process-natural-language", request);
}

export function parseAiParameterAssistant(payload: FormData): Promise<AiParameterParseResponse> {
  return apiPostFormData<AiParameterParseResponse>("/api/ai-parameter-assistant/parse", payload);
}

export function applyAiParameterSuggestions(request: AiParameterApplyRequest): Promise<AiParameterApplyResponse> {
  return apiPost<AiParameterApplyResponse>("/api/ai-parameter-assistant/apply", request);
}

export function saveProcessLibrary(request: ProcessLibrarySaveRequest): Promise<ProcessTemplate[]> {
  return apiPut<ProcessTemplate[]>("/api/process-library", request);
}

export function saveLocalScenarioConfig(request: LocalScenarioConfigSaveRequest): Promise<LocalScenarioConfig> {
  return apiPut<LocalScenarioConfig>("/api/local-scenario-config", request);
}

export function createProjectDataVersion(request: CreateProjectDataVersionRequest): Promise<ProjectDataVersion> {
  return apiPost<ProjectDataVersion>("/api/project-data-versions", request);
}

export function listProjectDataVersions(projectId: string): Promise<ProjectDataVersion[]> {
  return apiGet<ProjectDataVersion[]>(`/api/projects/${encodeURIComponent(projectId)}/data-versions`);
}

export function confirmProjectDataVersion(
  projectDataVersionId: string,
  request: { expected_input_fingerprint: string; confirmed_by: string; confirmation_reason: string },
): Promise<ProjectDataVersion> {
  return apiPost<ProjectDataVersion>(
    `/api/project-data-versions/${encodeURIComponent(projectDataVersionId)}/confirm`,
    request,
  );
}

export function importGirderWorkpoints(payload: FormData): Promise<{
  workpoints: unknown[];
  source_evidence: unknown[];
  field_conflicts: unknown[];
  diagnostics: unknown[];
}> {
  return apiPostFormData("/api/girder-planning/import-workpoints", payload);
}

export function importGirderProgressActuals(payload: FormData): Promise<GirderProgressImportPreview> {
  return apiPostFormData<GirderProgressImportPreview>("/api/girder-planning/import-progress", payload);
}

export function createPlanningScenarioVersion(
  request: CreatePlanningScenarioVersionRequest,
): Promise<PlanningScenarioVersion> {
  return apiPost<PlanningScenarioVersion>("/api/planning-scenario-versions", request);
}

export function listPlanningScenarioVersions(projectId: string): Promise<PlanningScenarioVersion[]> {
  return apiGet<PlanningScenarioVersion[]>(`/api/projects/${encodeURIComponent(projectId)}/planning-scenarios`);
}

export function confirmGirderSpecialty(
  scenarioVersionId: string,
  request: { expected_input_fingerprint: string; confirmed_by: string; confirmation_reason: string },
): Promise<PlanningScenarioVersion> {
  return apiPost<PlanningScenarioVersion>(
    `/api/planning-scenario-versions/${encodeURIComponent(scenarioVersionId)}/confirm-specialty`,
    request,
  );
}

export function validateGirderPlanning(
  scenarioVersionId: string,
  expectedInputFingerprint: string,
): Promise<GirderPlanningReadiness> {
  return apiPost<GirderPlanningReadiness>("/api/girder-planning/validate", {
    scenario_version_id: scenarioVersionId,
    expected_input_fingerprint: expectedInputFingerprint,
  });
}

export function previewGirderPlanning(
  scenarioVersionId: string,
  expectedInputFingerprint: string,
): Promise<GirderPlanningResult> {
  return apiPost<GirderPlanningResult>("/api/girder-planning/preview", {
    scenario_version_id: scenarioVersionId,
    expected_input_fingerprint: expectedInputFingerprint,
  });
}

export function solveIntegratedSchedule(request: {
  scenario_version_id: string;
  progress_snapshot_id?: string | null;
  expected_input_fingerprint: string;
  force_recompute?: boolean;
}): Promise<IntegratedCalculationSnapshot> {
  return apiPost<IntegratedCalculationSnapshot>("/api/integrated-schedules", request);
}

export function getIntegratedSchedule(integratedSnapshotId: string): Promise<IntegratedCalculationSnapshot> {
  return apiGet<IntegratedCalculationSnapshot>(
    `/api/integrated-schedules/${encodeURIComponent(integratedSnapshotId)}`,
  );
}
