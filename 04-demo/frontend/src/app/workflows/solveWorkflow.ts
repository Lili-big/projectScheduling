import type { ScenarioInput, ScenarioSolveResult } from "../../contracts";
import { scenarioFingerprintForSolve } from "./scenarioWorkflow";

type ScenarioNormalizer = (scenario: ScenarioInput) => ScenarioInput;
type ScenarioSolver = (scenario: ScenarioInput, workpointId?: string | null) => Promise<ScenarioSolveResult>;

export async function solveScenarioWorkflow(
  scenario: ScenarioInput,
  normalize: ScenarioNormalizer,
  solve: ScenarioSolver,
  workpointId: string | null = null,
): Promise<{ solved: ScenarioSolveResult; scenario: ScenarioInput; fingerprint: string }> {
  const normalizedScenario = normalize(scenario);
  return {
    solved: await solve(normalizedScenario, workpointId),
    scenario: normalizedScenario,
    fingerprint: scenarioFingerprintForSolve(normalizedScenario, workpointId),
  };
}

export function fallbackTargetDaysForScenario(
  scenarioFingerprint: string,
  resultFingerprint: string | null,
  result: ScenarioSolveResult | null,
): number | null {
  return resultFingerprint === scenarioFingerprint ? result?.result.objective_days ?? null : null;
}
