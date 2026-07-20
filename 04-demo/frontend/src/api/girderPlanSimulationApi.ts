import { apiGet, apiPost } from "./client";
import type {
  CreateScenarioVersionRequest,
  GirderPlanReadiness,
  GirderPlanScenarioVersion,
  GirderPlanSimulationRun,
  LineGraphSnapshot,
} from "../contracts";

const base = "/api/girder-plan-simulation";

export function getGirderPlanLineGraph(projectMasterVersionId: string): Promise<LineGraphSnapshot> {
  return apiGet(`${base}/line-graphs/${encodeURIComponent(projectMasterVersionId)}`);
}

export function listGirderPlanScenarios(projectId: string): Promise<GirderPlanScenarioVersion[]> {
  return apiGet(`${base}/scenarios?project_id=${encodeURIComponent(projectId)}`);
}

export function createGirderPlanScenario(payload: CreateScenarioVersionRequest): Promise<GirderPlanScenarioVersion> {
  return apiPost(`${base}/scenarios`, payload);
}

export function getGirderPlanScenario(scenarioVersionId: string): Promise<GirderPlanScenarioVersion> {
  return apiGet(`${base}/scenarios/${encodeURIComponent(scenarioVersionId)}`);
}

export function validateGirderPlanScenario(
  scenarioVersionId: string,
  expectedInputFingerprint: string,
): Promise<GirderPlanReadiness> {
  return apiPost(`${base}/scenarios/${encodeURIComponent(scenarioVersionId)}/validate`, {
    expected_input_fingerprint: expectedInputFingerprint,
  });
}

export function runGirderPlanScenario(
  scenarioVersionId: string,
  expectedInputFingerprint: string,
  forceRecompute = false,
): Promise<GirderPlanSimulationRun> {
  return apiPost(`${base}/runs`, {
    scenario_version_id: scenarioVersionId,
    expected_input_fingerprint: expectedInputFingerprint,
    force_recompute: forceRecompute,
  });
}

export function getGirderPlanRun(runId: string): Promise<GirderPlanSimulationRun> {
  return apiGet(`${base}/runs/${encodeURIComponent(runId)}`);
}

export function confirmGirderPlanRun(
  runId: string,
  expectedInputFingerprint: string,
  confirmedBy: string,
  confirmationReason: string,
): Promise<GirderPlanSimulationRun> {
  return apiPost(`${base}/runs/${encodeURIComponent(runId)}/confirm`, {
    expected_input_fingerprint: expectedInputFingerprint,
    confirmed_by: confirmedBy,
    confirmation_reason: confirmationReason,
  });
}
