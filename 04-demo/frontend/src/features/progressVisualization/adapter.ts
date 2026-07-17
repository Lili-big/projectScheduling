import { componentLabels } from "../../domain/labels";
import type {
  ComponentType,
  ForecastTaskState,
  PlanControlProjectSummary,
  ProgressEntry,
  ScheduledTask,
} from "../../contracts";
import type {
  BridgeProgressSummary,
  ComponentProgressSummary,
  ProgressCurvePoint,
  ProgressRiskEvidence,
  ProgressVisualizationData,
  ProgressVisualizationSceneConfig,
  ScenePosition,
  StructureProgressMarker,
} from "./types";

const dayMs = 86_400_000;

function clampPercent(value: number): number {
  return Math.round(Math.min(100, Math.max(0, value)) * 10) / 10;
}

function roundOne(value: number): number {
  return Math.round(value * 10) / 10;
}

function parseDate(value: string | null | undefined): number | null {
  if (!value) return null;
  const timestamp = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(timestamp) ? timestamp : null;
}

function plannedTaskProgress(task: ScheduledTask, statusDate: string): number {
  const status = parseDate(statusDate);
  const start = parseDate(task.start_date);
  const finish = parseDate(task.finish_date);
  if (status === null || start === null || finish === null) return 0;
  if (status < start) return 0;
  if (status >= finish) return 100;
  const duration = Math.max(1, Math.round((finish - start) / dayMs) + 1);
  const elapsed = Math.max(0, Math.round((status - start) / dayMs) + 1);
  return clampPercent((elapsed / duration) * 100);
}

function average(values: number[]): number {
  return values.length ? clampPercent(values.reduce((sum, value) => sum + value, 0) / values.length) : 0;
}

function numberMetric(source: Record<string, unknown> | undefined, key: string): number | null {
  const value = source?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringMetric(source: Record<string, unknown> | undefined, key: string): string | null {
  const value = source?.[key];
  return typeof value === "string" && value ? value : null;
}

function stringList(source: Record<string, unknown> | undefined, key: string): string[] {
  const value = source?.[key];
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const record = item as Record<string, unknown>;
        return String(record.name ?? record.resource_name ?? record.resource_type ?? record.task_id ?? "");
      }
      return "";
    })
    .filter(Boolean);
}

function fallbackPosition(index: number, total: number, route = false): ScenePosition {
  if (route) {
    const ratio = total <= 1 ? 0.5 : index / (total - 1);
    return { x: 37 + ratio * 21, y: 24 + ratio * 59 };
  }
  const ratio = total <= 1 ? 0.5 : index / (total - 1);
  return { x: 29 + ratio * 33, y: 69 - ratio * 34 };
}

function varianceByTask(forecastStates: ForecastTaskState[]): Map<string, number> {
  return new Map(
    forecastStates
      .filter((item) => typeof item.variance_days === "number")
      .map((item) => [item.task_id, Number(item.variance_days)]),
  );
}

function curveValue(tasks: ScheduledTask[], date: string): number {
  return average(tasks.map((task) => plannedTaskProgress(task, date)));
}

function curveDates(startDate: string, finishDate: string, statusDate: string): string[] {
  const start = parseDate(startDate);
  const finish = parseDate(finishDate);
  const status = parseDate(statusDate);
  if (start === null || finish === null) return [statusDate];
  const dates = Array.from({ length: 8 }, (_, index) => {
    const timestamp = start + ((finish - start) * index) / 7;
    return new Date(timestamp).toISOString().slice(0, 10);
  });
  if (status !== null && status >= start && status <= finish) dates.push(statusDate);
  return [...new Set(dates)].sort();
}

function deriveBridgeSummaries(
  tasks: ScheduledTask[],
  entries: Map<string, ProgressEntry>,
  statusDate: string,
  bridgeNames: Map<string, string>,
  variances: Map<string, number>,
  scene: ProgressVisualizationSceneConfig,
): BridgeProgressSummary[] {
  const groups = new Map<string, ScheduledTask[]>();
  tasks.forEach((task) => {
    const bridgeId = task.bridge_id ?? "unassigned-bridge";
    groups.set(bridgeId, [...(groups.get(bridgeId) ?? []), task]);
  });
  return [...groups.entries()].map(([bridgeId, group], index, all) => {
    const taskVariances = group.map((task) => variances.get(task.id)).filter((value): value is number => value !== undefined);
    const finishVarianceDays = taskVariances.length ? Math.max(...taskVariances) : null;
    return {
      id: bridgeId,
      name: bridgeNames.get(bridgeId) ?? group[0]?.structure_name ?? "未命名桥梁",
      plannedProgress: average(group.map((task) => plannedTaskProgress(task, statusDate))),
      actualProgress: average(group.map((task) => entries.get(task.id)?.percent_complete ?? 0)),
      finishVarianceDays,
      riskStatus: finishVarianceDays !== null && finishVarianceDays > 0 ? "late" : "on_track",
      completedTasks: group.filter((task) => entries.get(task.id)?.status === "completed").length,
      totalTasks: group.length,
      position: scene.bridgePositions?.[bridgeId] ?? fallbackPosition(index, all.length, true),
    };
  });
}

function deriveComponentSummaries(
  tasks: ScheduledTask[],
  entries: Map<string, ProgressEntry>,
  statusDate: string,
): ComponentProgressSummary[] {
  const groups = new Map<ComponentType, ScheduledTask[]>();
  tasks.forEach((task) => groups.set(task.component_type, [...(groups.get(task.component_type) ?? []), task]));
  return [...groups.entries()].map(([componentType, group]) => {
    const plannedProgress = average(group.map((task) => plannedTaskProgress(task, statusDate)));
    const actualProgress = average(group.map((task) => entries.get(task.id)?.percent_complete ?? 0));
    return {
      componentType,
      label: componentLabels[componentType] ?? componentType,
      plannedProgress,
      actualProgress,
      variance: roundOne(actualProgress - plannedProgress),
      completedTasks: group.filter((task) => entries.get(task.id)?.status === "completed").length,
      totalTasks: group.length,
    };
  });
}

function deriveStructureMarkers(
  tasks: ScheduledTask[],
  entries: Map<string, ProgressEntry>,
  statusDate: string,
  variances: Map<string, number>,
  scene: ProgressVisualizationSceneConfig,
): StructureProgressMarker[] {
  const groups = new Map<string, ScheduledTask[]>();
  tasks.forEach((task) => groups.set(task.structure_id, [...(groups.get(task.structure_id) ?? []), task]));
  return [...groups.entries()].map(([structureId, group], index, all) => {
    const plannedProgress = average(group.map((task) => plannedTaskProgress(task, statusDate)));
    const actualProgress = average(group.map((task) => entries.get(task.id)?.percent_complete ?? 0));
    const taskVariances = group.map((task) => variances.get(task.id)).filter((value): value is number => value !== undefined);
    const varianceDays = taskVariances.length ? Math.max(...taskVariances) : null;
    const completed = group.length > 0 && group.every((task) => entries.get(task.id)?.status === "completed");
    return {
      id: structureId,
      name: group[0]?.structure_name ?? structureId,
      bridgeId: group[0]?.bridge_id ?? "unassigned-bridge",
      plannedProgress,
      actualProgress,
      varianceDays,
      status: completed
        ? "completed"
        : varianceDays !== null && varianceDays > 0
          ? "late"
          : varianceDays !== null && varianceDays < 0
            ? "ahead"
            : actualProgress > 0
              ? "in_progress"
              : varianceDays === 0
                ? "on_track"
                : "not_started",
      position: scene.structurePositions?.[structureId] ?? fallbackPosition(index, all.length),
    };
  });
}

function emptyData(projectId: string, projectName: string): ProgressVisualizationData {
  return {
    state: "no_plan",
    projectId,
    projectName,
    planVersionLabel: "未确认",
    planStatusLabel: "无执行计划",
    confirmedAt: null,
    statusDate: null,
    revisionNo: null,
    dataQuality: "unavailable",
    forecastConfidence: null,
    forecastRiskStatus: null,
    overview: {
      plannedProgress: null,
      actualProgress: null,
      progressVariance: null,
      coverage: null,
      baselineFinishDate: null,
      predictedFinishDate: null,
      finishVarianceDays: null,
      lateMilestoneCount: null,
    },
    bridges: [],
    selectedBridgeId: null,
    components: [],
    structures: [],
    milestones: [],
    riskEvidence: [],
    diagnostics: {
      criticalTasks: [],
      bottleneckResources: [],
      resourceSuggestions: [],
      jumpPierCount: 0,
      sideSwitchCount: 0,
      pathGroupSwitchCount: 0,
      waitingStatus: "暂无诊断",
    },
    curve: { baseline: [], forecast: [], actual: null },
  };
}

export function adaptPlanControlSummary(
  summary: PlanControlProjectSummary,
  scene: ProgressVisualizationSceneConfig = {},
): ProgressVisualizationData {
  const plan = summary.active_plan;
  if (!plan) return emptyData(summary.project_id, "未确认项目");

  const data = emptyData(summary.project_id, plan.project_name);
  const snapshot = summary.current_progress_snapshot ?? null;
  const rawForecast = summary.latest_forecast ?? null;
  const forecast = rawForecast?.status === "stale" ? null : rawForecast;
  const statusDate = snapshot?.status_date ?? plan.schedule_result_snapshot.plan_start_date;
  const tasks = plan.schedule_result_snapshot.tasks;
  const entries = new Map((snapshot?.entries ?? []).map((entry) => [entry.task_id, entry]));
  const forecastStates = forecast ? [...forecast.historical_tasks, ...forecast.predicted_tasks] : [];
  const variances = varianceByTask(forecastStates);
  const plannedProgress = average(tasks.map((task) => plannedTaskProgress(task, statusDate)));
  const actualProgress = snapshot ? average(tasks.map((task) => entries.get(task.id)?.percent_complete ?? 0)) : null;
  const bridgeNames = new Map(plan.scenario_snapshot.project.bridges.map((bridge) => [bridge.id, bridge.name]));
  const metrics = forecast?.metrics;
  const milestoneScope = new Map(
    (forecast?.schedule_result?.milestone_results ?? plan.schedule_result_snapshot.milestone_results)
      .map((item) => [item.id, item.scope_id ?? null]),
  );
  const riskEvidence: ProgressRiskEvidence[] = (forecast?.risk_evidence ?? []).map((item, index) => {
    const type = ["project_finish", "milestone", "buffer", "solver"].includes(String(item.type))
      ? String(item.type) as ProgressRiskEvidence["type"]
      : "solver";
    const milestoneId = typeof item.milestone_id === "string" ? item.milestone_id : null;
    return {
      id: `risk-evidence-${index + 1}`,
      type,
      message: String(item.message ?? "预测诊断信息"),
      varianceDays: typeof item.variance_days === "number" ? item.variance_days : null,
      milestoneId,
      bridgeId: milestoneId ? milestoneScope.get(milestoneId) ?? null : null,
    };
  });
  const milestoneResults = forecast?.schedule_result?.milestone_results ?? plan.schedule_result_snapshot.milestone_results;
  const finishDate = stringMetric(metrics, "predicted_finish_date") ?? plan.schedule_result_snapshot.plan_finish_date ?? statusDate;
  const dates = curveDates(plan.schedule_result_snapshot.plan_start_date, finishDate, statusDate);
  const forecastTasks = forecast?.schedule_result?.tasks ?? [];
  const transfer = metrics?.transfer_impact;
  const transferRecord = transfer && typeof transfer === "object" ? transfer as Record<string, unknown> : {};

  return {
    ...data,
    state: !snapshot
      ? "no_snapshot"
      : rawForecast?.status === "stale"
        ? "stale"
        : !forecast
          ? "no_forecast"
          : forecast.risk_status === "insufficient_data"
            ? "insufficient_data"
            : "ready",
    planVersionLabel: `V${plan.version_no}`,
    planStatusLabel: plan.status === "active" ? "当前执行计划" : plan.status,
    confirmedAt: plan.confirmed_at,
    statusDate: snapshot?.status_date ?? null,
    revisionNo: snapshot?.revision_no ?? null,
    dataQuality: snapshot?.data_quality_status ?? "unavailable",
    forecastConfidence: forecast?.confidence ?? null,
    forecastRiskStatus: forecast?.risk_status ?? null,
    overview: {
      plannedProgress,
      actualProgress,
      progressVariance: actualProgress === null ? null : Math.round((actualProgress - plannedProgress) * 10) / 10,
      coverage: snapshot ? clampPercent((entries.size / Math.max(1, tasks.length)) * 100) : null,
      baselineFinishDate: stringMetric(metrics, "baseline_finish_date") ?? plan.schedule_result_snapshot.plan_finish_date ?? null,
      predictedFinishDate: forecast ? stringMetric(metrics, "predicted_finish_date") : null,
      finishVarianceDays: forecast ? numberMetric(metrics, "finish_variance_days") : null,
      lateMilestoneCount: forecast ? numberMetric(metrics, "late_milestone_count") : null,
    },
    bridges: deriveBridgeSummaries(tasks, entries, statusDate, bridgeNames, variances, scene),
    selectedBridgeId: plan.scenario_snapshot.project.bridges[0]?.id ?? null,
    components: deriveComponentSummaries(tasks, entries, statusDate),
    structures: deriveStructureMarkers(tasks, entries, statusDate, variances, scene),
    milestones: milestoneResults.map((item) => ({
      id: item.id,
      name: item.name,
      targetDate: item.target_date,
      predictedDate: item.actual_date ?? null,
      latenessDays: item.lateness_days,
      scopeId: item.scope_id ?? null,
      status: item.status,
    })),
    riskEvidence,
    diagnostics: {
      criticalTasks: stringList(metrics, "critical_path_candidates"),
      bottleneckResources: stringList(metrics, "bottleneck_resources"),
      resourceSuggestions: stringList(metrics, "resource_increment_suggestions"),
      jumpPierCount: numberMetric(transferRecord, "jump_pier_count") ?? 0,
      sideSwitchCount: numberMetric(transferRecord, "side_switch_count") ?? 0,
      pathGroupSwitchCount: numberMetric(transferRecord, "path_group_switch_count") ?? 0,
      waitingStatus: typeof metrics?.waiting_impact === "string" ? metrics.waiting_impact : "查看滚动预测诊断",
    },
    curve: {
      baseline: dates.map((date): ProgressCurvePoint => ({ date, value: curveValue(tasks, date) })),
      forecast: forecastTasks.length
        ? dates.map((date): ProgressCurvePoint => ({ date, value: curveValue(forecastTasks, date) }))
        : [],
      actual: snapshot && actualProgress !== null ? { date: snapshot.status_date, value: actualProgress } : null,
    },
  };
}
