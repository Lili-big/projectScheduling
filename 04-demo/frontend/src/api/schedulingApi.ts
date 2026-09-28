import type { GeneratedScheduleInput, ProjectModel, ScheduleResult } from "../contracts";
import { apiPostBlob } from "./client";

export { compareScenarios, generateScheduleInput, solveMinResources, solveResourceCost, solveScenario, solvePavementScenarioStream, optimizePavementIdleStream } from "./_schedulerApi";

export function exportZpertPlan(payload: {
  project: ProjectModel;
  generated: GeneratedScheduleInput;
  result: ScheduleResult;
  plan_name?: string;
}): Promise<{ blob: Blob; fileName: string | null }> {
  return apiPostBlob("/api/zpert-plan/export", payload);
}
