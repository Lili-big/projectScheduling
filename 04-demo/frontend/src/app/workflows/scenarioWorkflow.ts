import type { GeneratedScheduleInput, ScenarioInput } from "../../contracts";

type ScenarioNormalizer = (scenario: ScenarioInput) => ScenarioInput;

export function scenarioFingerprintForSolve(scenario: ScenarioInput): string {
  return JSON.stringify(scenario);
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
  generate: (scenario: ScenarioInput) => Promise<GeneratedScheduleInput>,
): Promise<{ generated: GeneratedScheduleInput; scenario: ScenarioInput; fingerprint: string }> {
  const normalizedScenario = normalize(scenario);
  return {
    generated: await generate(normalizedScenario),
    scenario: normalizedScenario,
    fingerprint: scenarioFingerprintForSolve(normalizedScenario),
  };
}
