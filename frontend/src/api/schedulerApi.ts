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
  ScenarioInput,
  ScenarioSolveResult,
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
