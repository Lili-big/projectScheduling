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

export type PavementPreviewState = {
  status: "idle" | "loading" | "ready" | "error";
  fingerprint: string | null;
  generation: GeneratedScheduleInput | null;
  error: string | null;
};
export const emptyPavementPreview = (): PavementPreviewState => ({ status: "idle", fingerprint: null, generation: null, error: null });

// No persistence or solve dependencies: automatic preparation has read-only side effects.
export function createPavementPreviewController(generate: (scenario: ScenarioInput, scope: null) => Promise<GeneratedScheduleInput>) {
  let sequence = 0;
  let state = emptyPavementPreview();
  return {
    invalidate() { sequence++; if (state.status === "loading") state = emptyPavementPreview(); },
    async request(scenario: ScenarioInput, publish: (value: PavementPreviewState) => void, retry = false) {
      const fingerprint = scenarioFingerprintForSolve(scenario);
      if (!retry && state.fingerprint === fingerprint && state.status !== "idle") { publish(state); return; }
      const requestId = ++sequence;
      state = { status: "loading", fingerprint, generation: null, error: null };
      publish(state);
      try {
        const generation = await generate(scenario, null);
        if (sequence !== requestId) return;
        state = { status: "ready", fingerprint, generation, error: null };
      } catch (reason) {
        if (sequence !== requestId) return;
        state = { status: "error", fingerprint, generation: null, error: reason instanceof Error ? reason.message : String(reason) };
      }
      publish(state);
    },
  };
}
