import type { RelationshipType, UpperStructureLogicRule } from "../types/scheduler";

export type UpperStructureLogicDefinition = {
  id: string;
  name: string;
  upperTarget: string;
  lowerPredecessor: string;
  generation: string;
  note: string;
};

export const upperStructureLogicDefinitions: UpperStructureLogicDefinition[] = [
  {
    id: "cast_in_place_box_beam_after_lower_structure",
    name: "现浇箱梁前置",
    upperTarget: "现浇箱梁现场任务",
    lowerPredecessor: "跨组覆盖范围内墩台完成任务",
    generation: "按现浇箱梁跨组生成任务，跨组涉及支座均作为前置。",
    note: "现浇箱梁在对应跨组墩台下部结构完成后开始。",
  },
  {
    id: "continuous_beam_zero_block_after_main_pier_lower_structure",
    name: "连续梁0号块前置",
    upperTarget: "主墩T构0号块",
    lowerPredecessor: "对应主墩完成任务",
    generation: "每个主墩T构生成1个0号块任务，对应主墩完成后开始。",
    note: "连续梁0号块在对应主墩下部结构完成后开始。",
  },
  {
    id: "continuous_beam_side_straight_after_edge_lower_structure",
    name: "连续梁边跨连续段前置",
    upperTarget: "边跨连续段",
    lowerPredecessor: "对应边跨墩台完成任务",
    generation: "每联连续梁左右边跨各生成1个连续段任务，边跨墩台完成后开始。",
    note: "连续梁边跨连续段在对应边跨墩台下部结构完成后开始。",
  },
  {
    id: "continuous_beam_t_chain",
    name: "连续梁T构顺序",
    upperTarget: "同一主墩T构标准段",
    lowerPredecessor: "同一T构0号块或上一段",
    generation: "每个T构内0号块、标准段按顺序生成前后置关系。",
    note: "连续梁T构内0号块和标准段按顺序施工。",
  },
  {
    id: "continuous_beam_side_closure",
    name: "连续梁边跨合龙",
    upperTarget: "边跨合龙段",
    lowerPredecessor: "边跨连续段和相邻T构",
    generation: "左右边跨合龙段分别以前置边跨连续段和相邻T构完成为前置。",
    note: "连续梁边跨合龙段在边跨连续段和相邻T构完成后开始。",
  },
  {
    id: "continuous_beam_middle_closure",
    name: "连续梁中跨合龙",
    upperTarget: "中跨合龙段",
    lowerPredecessor: "相邻两个T构",
    generation: "每个中跨合龙段以左右相邻T构完成为前置。",
    note: "连续梁中跨合龙段在相邻两个T构完成后开始。",
  },
  {
    id: "continuous_beam_edge_before_middle_closure",
    name: "边跨先于中跨合龙",
    upperTarget: "中跨合龙段",
    lowerPredecessor: "左右边跨合龙段",
    generation: "默认所有中跨合龙段等待边跨合龙段完成后开始。",
    note: "连续梁默认边跨合龙先于中跨合龙。",
  },
  {
    id: "continuous_beam_middle_closure_sequence",
    name: "中跨合龙顺序",
    upperTarget: "后序中跨合龙段",
    lowerPredecessor: "前序中跨合龙段",
    generation: "按连续梁配置的中跨合龙顺序生成前后置关系。",
    note: "连续梁中跨合龙按配置顺序推进。",
  },
];

export function defaultUpperStructureLogicRules(): UpperStructureLogicRule[] {
  return upperStructureLogicDefinitions.map((definition) => ({
    id: definition.id,
    relationship: "FS",
    lag_days: 0,
    severity: "error",
    note: definition.note,
  }));
}

export function mergeUpperStructureLogicRules(rules: UpperStructureLogicRule[] = []): UpperStructureLogicRule[] {
  const byId = new Map(defaultUpperStructureLogicRules().map((rule) => [rule.id, rule]));
  for (const rule of rules) {
    byId.set(rule.id, {
      ...rule,
      relationship: rule.relationship ?? "FS",
      lag_days: rule.lag_days ?? 0,
      severity: rule.severity ?? "error",
    });
  }
  return upperStructureLogicDefinitions.map((definition) => byId.get(definition.id) ?? {
    id: definition.id,
    relationship: "FS",
    lag_days: 0,
    severity: "error",
    note: definition.note,
  });
}
