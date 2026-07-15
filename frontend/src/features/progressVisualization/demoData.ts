import type { ComponentType } from "../../types/scheduler";
import type {
  BridgeProgressSummary,
  ComponentProgressSummary,
  ProgressVisualizationData,
  ProgressVisualizationSceneConfig,
  StructureProgressMarker,
} from "./types";

export const progressVisualizationScene: ProgressVisualizationSceneConfig = {
  bridgePositions: {
    "bridge-lianhe-1": { x: 39.2, y: 24.5 },
    "bridge-lianhe-2": { x: 40.5, y: 30.5 },
    "bridge-lianghekou": { x: 41.7, y: 37.5 },
    "bridge-yongninghe": { x: 43.3, y: 44.5 },
    "bridge-songshuwan": { x: 44.8, y: 51.5 },
    "bridge-guanyinxi": { x: 47.2, y: 58.5 },
    "bridge-qilongzui": { x: 50.1, y: 65.5 },
    "bridge-xinwuji": { x: 54.1, y: 73.5 },
  },
  structurePositions: {
    "structure-0-abutment": { x: 24.2, y: 68.5 },
    "structure-3-pier": { x: 31.5, y: 61.8 },
    "structure-6-pier": { x: 38.6, y: 55.4 },
    "structure-9-pier": { x: 45.4, y: 48.8 },
    "structure-12-pier": { x: 51.8, y: 42.7 },
    "structure-15-pier": { x: 57.3, y: 36.9 },
    "structure-18-pier": { x: 62.1, y: 32.1 },
    "structure-21-abutment": { x: 66.1, y: 28.1 },
  },
};

const bridges: BridgeProgressSummary[] = [
  ["bridge-lianhe-1", "联合村1号中桥", 86.3, 88.6, -2, "on_track", 22, 26],
  ["bridge-lianhe-2", "联合村2号大桥", 78.4, 75.2, 3, "at_risk", 34, 46],
  ["bridge-lianghekou", "两河口大桥", 67.8, 60.9, 8, "late", 89, 148],
  ["bridge-yongninghe", "永宁河特大桥", 63.1, 58.8, 4, "late", 72, 126],
  ["bridge-songshuwan", "松树湾大桥", 57.2, 55.7, 1, "at_risk", 38, 72],
  ["bridge-guanyinxi", "观音溪大桥", 49.6, 51.4, -1, "on_track", 31, 66],
  ["bridge-qilongzui", "七龙咀大桥", 41.3, 39.8, 2, "at_risk", 18, 48],
  ["bridge-xinwuji", "新屋基大桥", 30.4, 30.4, 0, "on_track", 12, 42],
].map(([id, name, plannedProgress, actualProgress, finishVarianceDays, riskStatus, completedTasks, totalTasks]) => ({
  id: String(id),
  name: String(name),
  plannedProgress: Number(plannedProgress),
  actualProgress: Number(actualProgress),
  finishVarianceDays: Number(finishVarianceDays),
  riskStatus: riskStatus as BridgeProgressSummary["riskStatus"],
  completedTasks: Number(completedTasks),
  totalTasks: Number(totalTasks),
  position: progressVisualizationScene.bridgePositions?.[String(id)] ?? { x: 50, y: 50 },
}));

const componentRows: Array<[ComponentType, string, number, number, number, number]> = [
  ["pile", "桩基", 96, 91, 109, 120],
  ["ground_tie_beam", "地系梁", 83, 76, 45, 59],
  ["cap", "承台", 78, 70, 7, 10],
  ["pier_body", "墩身", 62, 54, 18, 34],
  ["cap_beam", "盖梁", 48, 39, 18, 46],
  ["abutment_body", "桥台", 75, 75, 3, 4],
  ["cast_in_place_continuous_beam", "现浇连续梁", 27, 21, 30, 142],
  ["cast_in_place_box_beam", "现浇箱梁", 18, 14, 9, 63],
];

const components: ComponentProgressSummary[] = componentRows.map(
  ([componentType, label, plannedProgress, actualProgress, completedTasks, totalTasks]) => ({
    componentType,
    label,
    plannedProgress,
    actualProgress,
    variance: Math.round((actualProgress - plannedProgress) * 10) / 10,
    completedTasks,
    totalTasks,
  }),
);

const structures: StructureProgressMarker[] = [
  ["structure-0-abutment", "0#桥台", 100, 100, -1, "completed"],
  ["structure-3-pier", "3#墩", 96, 100, -2, "completed"],
  ["structure-6-pier", "6#墩", 82, 78, 3, "late"],
  ["structure-9-pier", "9#墩", 71, 64, 6, "late"],
  ["structure-12-pier", "12#墩", 56, 51, 4, "late"],
  ["structure-15-pier", "15#墩", 42, 45, -2, "ahead"],
  ["structure-18-pier", "18#墩", 28, 22, 2, "in_progress"],
  ["structure-21-abutment", "21#桥台", 8, 0, null, "not_started"],
].map(([id, name, plannedProgress, actualProgress, varianceDays, status]) => ({
  id: String(id),
  name: String(name),
  bridgeId: "bridge-lianghekou",
  plannedProgress: Number(plannedProgress),
  actualProgress: Number(actualProgress),
  varianceDays: varianceDays === null ? null : Number(varianceDays),
  status: status as StructureProgressMarker["status"],
  position: progressVisualizationScene.structurePositions?.[String(id)] ?? { x: 50, y: 50 },
}));

export const demoProgressVisualizationData: ProgressVisualizationData = {
  state: "ready",
  projectId: "demo-linear-project",
  projectName: "六公司泸州至古蔺高速公路工程",
  planVersionLabel: "V4",
  planStatusLabel: "当前执行计划",
  confirmedAt: "2026-07-12T09:30:00Z",
  statusDate: "2026-07-15",
  revisionNo: 2,
  dataQuality: "valid",
  forecastConfidence: "high",
  forecastRiskStatus: "late",
  overview: {
    plannedProgress: 61.8,
    actualProgress: 56.4,
    progressVariance: -5.4,
    coverage: 100,
    baselineFinishDate: "2026-12-16",
    predictedFinishDate: "2026-12-28",
    finishVarianceDays: 12,
    lateMilestoneCount: 2,
  },
  bridges,
  selectedBridgeId: "bridge-lianghekou",
  components,
  structures,
  milestones: [
    { id: "milestone-pile", name: "桩基全部完成", targetDate: "2026-07-10", predictedDate: "2026-07-12", latenessDays: 2, scopeId: "bridge-lianghekou", status: "late" },
    { id: "milestone-substructure", name: "下部结构完成", targetDate: "2026-09-15", predictedDate: "2026-09-23", latenessDays: 8, scopeId: "bridge-lianghekou", status: "late" },
    { id: "milestone-beam", name: "架梁开始", targetDate: "2026-10-01", predictedDate: "2026-10-09", latenessDays: 8, scopeId: "bridge-lianghekou", status: "late" },
    { id: "milestone-finish", name: "项目计划完工", targetDate: "2026-12-16", predictedDate: "2026-12-28", latenessDays: 12, scopeId: null, status: "late" },
  ],
  riskEvidence: [
    { id: "risk-project-finish", type: "project_finish", message: "项目预测完成日期较基准晚 12 天。", varianceDays: 12, milestoneId: null, bridgeId: null },
    { id: "risk-lianghekou", type: "milestone", message: "两河口大桥下部结构完成节点预测迟延 8 天。", varianceDays: 8, milestoneId: "milestone-substructure", bridgeId: "bridge-lianghekou" },
    { id: "risk-yongninghe", type: "milestone", message: "永宁河特大桥右幅贯通节点预测迟延 4 天。", varianceDays: 4, milestoneId: "milestone-yongninghe", bridgeId: "bridge-yongninghe" },
  ],
  diagnostics: {
    criticalTasks: ["两河口大桥 9#墩墩身", "两河口大桥 12#墩盖梁", "永宁河特大桥右幅连续梁"],
    bottleneckResources: ["墩柱模板班组", "架桥机班组"],
    resourceSuggestions: ["墩柱模板班组建议增配 1 组", "架桥机班组建议增配 1 组"],
    jumpPierCount: 2,
    sideSwitchCount: 1,
    pathGroupSwitchCount: 0,
    waitingStatus: "关键资源存在 18 天累计等待",
  },
  curve: {
    baseline: [
      ["2026-04-01", 0], ["2026-05-01", 12], ["2026-06-01", 31], ["2026-07-15", 61.8],
      ["2026-08-15", 76], ["2026-09-15", 87], ["2026-10-15", 93], ["2026-11-15", 97], ["2026-12-16", 100],
    ].map(([date, value]) => ({ date: String(date), value: Number(value) })),
    forecast: [
      ["2026-04-01", 0], ["2026-05-01", 11], ["2026-06-01", 28], ["2026-07-15", 56.4],
      ["2026-08-15", 68], ["2026-09-15", 79], ["2026-10-15", 87], ["2026-11-15", 94], ["2026-12-16", 98], ["2026-12-28", 100],
    ].map(([date, value]) => ({ date: String(date), value: Number(value) })),
    actual: { date: "2026-07-15", value: 56.4 },
  },
};

