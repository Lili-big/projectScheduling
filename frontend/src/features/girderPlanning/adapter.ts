import type {
  GirderPlanningConfig,
  GirderPlanningResult,
  IntegratedCalculationSnapshot,
  ScenarioInput,
} from "../../types/scheduler";

export function createDefaultGirderPlanningConfig(startDate: string): GirderPlanningConfig {
  return {
    enabled: false,
    beam_yards: [],
    erection_machines: [],
    routes: [],
    parameters: {
      substructure_acceptance_buffer_days: 7,
      roadbed_passage_buffer_days: 4,
      tunnel_passage_buffer_days: 6,
      post_erection_passage_buffer_days: 0,
      post_erection_buffer_confirmed: false,
      default_transfer_days: 2,
      default_bridge_preparation_days: 3,
      max_iterations: 10,
      date_tolerance_days: 0,
      enable_supply_constraint: true,
      enable_passage_constraint: true,
      enable_stock_limit: true,
    },
    owner_overrides: [],
    manual_passage_overrides: [],
    coarse_mode: false,
  };
}

export function normalizeGirderPlanningConfig(scenario: ScenarioInput): GirderPlanningConfig {
  const defaults = createDefaultGirderPlanningConfig(scenario.project.start_date);
  const current = scenario.girder_planning;
  if (!current) return defaults;
  return {
    ...defaults,
    ...current,
    parameters: { ...defaults.parameters, ...current.parameters },
    beam_yards: current.beam_yards ?? [],
    erection_machines: current.erection_machines ?? [],
    routes: current.routes ?? [],
    owner_overrides: current.owner_overrides ?? [],
    manual_passage_overrides: current.manual_passage_overrides ?? [],
  };
}

export function withGirderPlanningConfig(scenario: ScenarioInput, config: GirderPlanningConfig): ScenarioInput {
  return { ...scenario, girder_planning: structuredClone(config) };
}

export function girderConfigFingerprint(value: unknown): string {
  return JSON.stringify(sortValue(value));
}

export function isGirderResultCurrent(
  result: GirderPlanningResult | IntegratedCalculationSnapshot | null,
  inputFingerprint: string | null,
): boolean {
  return Boolean(result && inputFingerprint && result.input_fingerprint === inputFingerprint);
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sortValue(item)]),
    );
  }
  return value;
}
