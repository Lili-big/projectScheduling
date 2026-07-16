import type { RelationshipType, UpperStructureLogicRule } from "../contracts";

export type UpperStructureLogicDefinition = {
  id: string;
  name: string;
  upperTarget: string;
  lowerPredecessor: string;
  generation: string;
  note: string;
  defaultMaxFinishGapDays?: number | null;
  readOnly?: boolean;
  constraintLabel?: string;
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
    upperTarget: "同一主墩T构左/右标准段",
    lowerPredecessor: "同一T构0号块或上一段",
    generation: "每个T构内0号块分别连接左侧标准段、右侧标准段。",
    note: "连续梁T构内0号块和左/右标准段按顺序施工。",
  },
  {
    id: "continuous_beam_standard_segment_sync",
    name: "左/右标准段同步",
    upperTarget: "同一主墩T构左/右标准段",
    lowerPredecessor: "同一T构0号块",
    generation: "左侧标准段、右侧标准段作为两个聚合任务生成，求解时同步开始、同步完成。",
    note: "同一T构左/右标准段必须同步开始、同步完成。",
    readOnly: true,
    constraintLabel: "同步开始/同步完成",
  },
  {
    id: "continuous_beam_side_closure",
    name: "连续梁边跨合龙",
    upperTarget: "边跨合龙段",
    lowerPredecessor: "边跨连续段和相邻T构边跨侧标准段",
    generation: "左右边跨合龙段分别以前置边跨连续段和相邻T构边跨侧标准段完成为前置。",
    note: "连续梁边跨合龙段在两侧前置完成后开始，默认两侧完成时间差不超过7天。",
    defaultMaxFinishGapDays: 7,
  },
  {
    id: "continuous_beam_middle_closure",
    name: "连续梁中跨合龙",
    upperTarget: "中跨合龙段",
    lowerPredecessor: "相邻两个T构面向合龙口的标准段",
    generation: "每个中跨合龙段以左侧T构右侧标准段、右侧T构左侧标准段完成为前置。",
    note: "连续梁中跨合龙段在两侧标准段完成后开始，默认两侧完成时间差不超过7天。",
    defaultMaxFinishGapDays: 7,
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
  return upperStructureLogicDefinitions.filter((definition) => !definition.readOnly).map((definition) => ({
    id: definition.id,
    relationship: "FS",
    lag_days: 0,
    max_finish_gap_days: definition.defaultMaxFinishGapDays ?? null,
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
      max_finish_gap_days: rule.max_finish_gap_days ?? byId.get(rule.id)?.max_finish_gap_days ?? null,
      severity: rule.severity ?? "error",
    });
  }
  return upperStructureLogicDefinitions.filter((definition) => !definition.readOnly).map((definition) => byId.get(definition.id) ?? {
    id: definition.id,
    relationship: "FS",
    lag_days: 0,
    max_finish_gap_days: definition.defaultMaxFinishGapDays ?? null,
    severity: "error",
    note: definition.note,
  });
}
