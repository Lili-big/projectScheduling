import type { GeneratedScheduleInput, ScenarioInput } from "../../contracts";

type ScenarioNormalizer = (scenario: ScenarioInput) => ScenarioInput;

export function scenarioFingerprintForSolve(scenario: ScenarioInput, workpointId: string | null = null): string {
  return JSON.stringify({
    scenario,
    solve_scope: workpointId ? { mode: "WORKPOINT", workpoint_id: workpointId } : { mode: "ALL", workpoint_id: null },
  });
}

export async function loadScenarioWorkflow(
  loadDemo: () => Promise<ScenarioInput>,
  normalize: ScenarioNormalizer,
): Promise<ScenarioInput> {
  const demo = await loadDemo();
  return normalize(demo);
}

export async function generateScheduleWorkflow(
  scenario: ScenarioInput,
  normalize: ScenarioNormalizer,
  generate: (scenario: ScenarioInput, workpointId?: string | null) => Promise<GeneratedScheduleInput>,
  workpointId: string | null = null,
): Promise<{ generated: GeneratedScheduleInput; scenario: ScenarioInput; fingerprint: string }> {
  const normalizedScenario = normalize(scenario);
  return {
    generated: await generate(normalizedScenario, workpointId),
    scenario: normalizedScenario,
    fingerprint: scenarioFingerprintForSolve(normalizedScenario, workpointId),
  };
}
