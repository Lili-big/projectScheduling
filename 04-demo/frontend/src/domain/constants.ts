import type { ComponentType, ResourceCostType } from "../contracts";

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
  granular_base: "granular_paving_crew",
  cement_stabilized_base: "water_stable_paving_crew",
  asphalt_course: "asphalt_paving_crew",

  spread_foundation: "spread_foundation_team",
  ground_tie_beam: "tie_beam_team",
  middle_tie_beam: "tie_beam_team",
  cap: "cap_team",
  pier_body: "pier_body_team",
  cap_beam: "cap_beam_team",
  abutment_body: "abutment_team",
  precast_beam: "precast_beam_team",
  beam_erection: "beam_erection_team",
  cast_in_place_continuous_beam: "cast_in_place_continuous_beam_team",
  cast_in_place_box_beam: "cast_in_place_box_beam_team",
  steel_box_beam: "steel_box_beam_team",
  bridge_deck_system: "bridge_deck_system_team",
};

export const standardResourceTypeLabels: Record<string, string> = {
  granular_paving_crew: "碎石机组", water_stable_paving_crew: "水稳机组", asphalt_paving_crew: "沥青机组",
  rotary_drill: "旋挖钻机",
  circulation_drill: "回旋钻机",
  impact_drill: "冲击钻机",
  manual_pile_team: "人工挖孔班组",
  cap_team: "承台模板",
  spread_foundation_team: "扩大基础班组",
  tie_beam_team: "系梁班组",
  pier_body_team: "墩柱模板",
  cap_beam_team: "盖梁模板",
  abutment_team: "桥台班组",
  precast_beam_team: "预制梁班组",
  beam_erection_team: "架梁班组",
  cast_in_place_continuous_beam_team: "连续梁班组",
  cast_in_place_box_beam_team: "现浇箱梁班组",
  steel_box_beam_team: "钢箱梁班组",
  bridge_deck_system_team: "桥面系班组",
};

export const excludedResourceCatalogTypes = new Set([
  "girder_erector",
  "beam_yard",
  "beam_yard_production_line",
  "precast_beam_team",
]);

export const projectMasterComponentTypeProjection: Record<string, ComponentType> = {
  granular_base: "granular_base",
  cement_stabilized_base: "cement_stabilized_base",
  asphalt_course: "asphalt_course",

  pile: "pile",
  cap: "cap",
  spread_foundation: "spread_foundation",
  tie_beam: "ground_tie_beam",
  pier_body: "pier_body",
  cap_beam: "cap_beam",
  precast_beam: "precast_beam",
  cast_in_place_box_beam: "cast_in_place_box_beam",
  cast_in_place_continuous_beam: "cast_in_place_continuous_beam",
};

export const projectMasterUpperStructureResourceComponent: Partial<Record<string, ComponentType>> = {
  cast_in_place_unit: "cast_in_place_box_beam",
  continuous_unit: "cast_in_place_continuous_beam",
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
