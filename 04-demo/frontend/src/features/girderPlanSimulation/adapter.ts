import type {
  BeamYardPlan,
  ErectionLinePlan,
  GirderPlanScenarioVersion,
  GirderPlanSimulationParameters,
  LineGraphNode,
  ManualRoutePlan,
  SimulationDiagnostic,
} from "../../contracts";

export type GirderPlanDraft = {
  scenarioId: string | null;
  latestVersionNo: number | null;
  beamYards: BeamYardPlan[];
  erectionLines: ErectionLinePlan[];
  routePlans: ManualRoutePlan[];
  parameters: GirderPlanSimulationParameters;
};

export function emptyGirderPlanDraft(): GirderPlanDraft {
  const horizon = new Date();
  horizon.setFullYear(horizon.getFullYear() + 3);
  return {
    scenarioId: null,
    latestVersionNo: null,
    beamYards: [],
    erectionLines: [],
    routePlans: [],
    parameters: {
      default_transfer_days: 1,
      bridge_readiness_buffer_days: 3,
      roadbed_passage_buffer_days: 2,
      tunnel_passage_buffer_days: 2,
      access_passage_buffer_days: 1,
      post_erection_passage_buffer_days: 1,
      planning_horizon_end_date: horizon.toISOString().slice(0, 10),
      same_day_production_available: false,
    },
  };
}

export function draftFromScenario(scenario: GirderPlanScenarioVersion): GirderPlanDraft {
  return {
    scenarioId: scenario.scenario_id,
    latestVersionNo: scenario.version_no,
    beamYards: scenario.beam_yards,
    erectionLines: scenario.erection_lines,
    routePlans: scenario.route_plans,
    parameters: scenario.parameters,
  };
}

export function girderTargets(nodes: LineGraphNode[]): LineGraphNode[] {
  return nodes.filter((node) => node.requires_erection).sort((left, right) =>
    (left.alignment_code ?? "").localeCompare(right.alignment_code ?? "")
      || (left.start_mileage_m ?? Number.MAX_SAFE_INTEGER) - (right.start_mileage_m ?? Number.MAX_SAFE_INTEGER)
      || left.node_id.localeCompare(right.node_id));
}

export function yardNodeId(yard: BeamYardPlan, nodes: LineGraphNode[]): string {
  if (yard.deployment_node_id) return yard.deployment_node_id;
  const candidates = nodes.filter((node) => node.alignment_code === yard.alignment_code
    && node.start_mileage_m != null
    && node.end_mileage_m != null
    && Math.min(node.start_mileage_m, node.end_mileage_m) <= yard.mileage_m
    && yard.mileage_m <= Math.max(node.start_mileage_m, node.end_mileage_m));
  const exactStart = candidates.filter((node) => node.start_mileage_m === yard.mileage_m);
  const exactStartPreferred = exactStart.filter((node) => node.side === "unknown" && !node.requires_erection);
  if (exactStartPreferred.length === 1) return exactStartPreferred[0].node_id;
  if (exactStart.length === 1) return exactStart[0].node_id;
  const preferred = candidates.filter((node) => node.side === "unknown" && !node.requires_erection);
  return (preferred.length === 1 ? preferred[0] : candidates.length === 1 ? candidates[0] : null)?.node_id ?? "";
}

export function diagnosticLabel(item: SimulationDiagnostic): string {
  return `${item.code}｜${item.message}${item.suggestion ? `；建议：${item.suggestion}` : ""}`;
}

export function diagnosticClass(item: SimulationDiagnostic): "success" | "warning" | "blocking" {
  return item.level === "error" ? "blocking" : item.level === "warning" ? "warning" : "success";
}

export function focusDiagnostic(item: SimulationDiagnostic): void {
  const candidates = [item.subject_id, ...item.entity_refs].filter((value): value is string => Boolean(value));
  const elements = [...document.querySelectorAll<HTMLElement>("[data-entity-id]")];
  const target = elements.find((element) => candidates.includes(element.dataset.entityId ?? ""));
  target?.scrollIntoView({ behavior: "smooth", block: "center" });
  target?.focus({ preventScroll: true });
}

export function moveItem<T>(items: T[], index: number, offset: -1 | 1): T[] {
  const target = index + offset;
  if (target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}
