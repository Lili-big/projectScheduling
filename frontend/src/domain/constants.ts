import type { ComponentType, ResourceCostType } from "../types/scheduler";

export const PREDECESSOR_HOVER_DELAY_MS = 450;
export const PREDECESSOR_HOVER_CLOSE_DELAY_MS = 140;

export const upperStructureCodes = {
  simpleBeam: "precastTGirder",
  castInPlaceBoxBeam: "castInPlaceBoxGirder",
  continuousBeam: "castInPlaceContinuousBoxGirder",
} as const;

export const resourceCostTypeLabels: Record<ResourceCostType, string> = {
  none: "不计成本",
  monthly_rental: "按月租赁",
  one_time_purchase: "一次性采购加工",
};

export const keyResourceComponentTypes = new Set<ComponentType>(["pile", "cap", "pier_body", "cap_beam", "cast_in_place_continuous_beam"]);

export const defaultResourceTypeByComponent: Partial<Record<ComponentType, string>> = {
  cap: "cap_team",
  pier_body: "pier_body_team",
  cap_beam: "cap_beam_team",
  cast_in_place_continuous_beam: "cast_in_place_continuous_beam_team",
};

export const pileResourceTypeByProcess: Record<string, string> = {
  pile_rotary_regular: "rotary_drill",
  pile_circulation: "circulation_drill",
  pile_impact: "impact_drill",
  pile_manual: "manual_pile_team",
};

export const pileResourceTypeByMethod: Record<string, string> = {
  rotary_drill: "rotary_drill",
  circulation_drill: "circulation_drill",
  impact_drill: "impact_drill",
  manual_pile: "manual_pile_team",
  manual_excavation: "manual_pile_team",
};
