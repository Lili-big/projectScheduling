import type {
  ResourceAssistantBatchSolveResponse,
  ResourceAssistantCoreMetrics,
  ResourceAssistantMetricRow,
  ResourceAssistantPlan,
  ResourceAssistantPlanOutcomeStatus,
  ResourceAssistantPlanProfile,
  ResourceAssistantPlanResult,
  ResourceAssistantScheduleOutcomeReason,
  ResourceAssistantScheduleOutcomeStatus,
  ResourceAssistantPlanStatus,
  ResourceAssistantRecommendation,
  ResourceAssistantLlmConfigStatus,
  ResourcePool,
} from "../types/scheduler";

const defaultResourceTypeLabels: Record<string, string> = {
  rotary_drill: "旋挖钻",
  circulation_drill: "回旋钻",
  impact_drill: "冲击钻",
  manual_pile_team: "人工挖孔班组",
  cap_team: "承台模板",
  pier_body_team: "墩柱模板",
  cap_beam_team: "盖梁模板",
  cast_in_place_continuous_beam_team: "连续梁班组",
};

export const resourceAssistantProfileLabels: Record<ResourceAssistantPlanProfile, string> = {
  economy: "经济方案",
  balanced: "平衡方案",
  crash: "抢工方案",
  custom: "自定义方案",
};

export const resourceAssistantStatusLabels: Record<ResourceAssistantPlanStatus, string> = {
  draft: "草稿",
  ready_to_solve: "待求解",
  stale: "待重算",
  solving: "求解中",
  optimal: "最优",
  feasible: "可行",
  infeasible: "不可行",
  unknown: "未知",
  failed: "失败",
  model_invalid: "模型无效",
};

export function resourceAssistantStatusTone(status: ResourceAssistantPlanStatus): "neutral" | "good" | "warning" | "danger" {
  if (status === "optimal" || status === "feasible") return "good";
  if (status === "infeasible" || status === "failed" || status === "model_invalid") return "danger";
  if (status === "unknown" || status === "stale") return "warning";
  return "neutral";
}

export const resourceAssistantOutcomeLabels: Record<ResourceAssistantPlanOutcomeStatus, string> = {
  met: "目标已满足",
  not_met: "已证明延期",
  unconfirmed: "限时未确认",
  infeasible: "物理不可行",
};

export const resourceAssistantScheduleOutcomeLabels: Record<ResourceAssistantScheduleOutcomeStatus, string> = {
  duration_target_met: "工期目标已满足",
  duration_target_not_met: "工期目标未满足",
  no_feasible_schedule: "当前资源未获得可行排程",
};

export function resourceAssistantOutcomeTone(
  status?: ResourceAssistantScheduleOutcomeStatus | null,
): "neutral" | "good" | "warning" | "danger" {
  if (status === "duration_target_met") return "good";
  if (status === "duration_target_not_met") return "warning";
  if (status === "no_feasible_schedule") return "danger";
  return "neutral";
}

export function resourceAssistantScheduleOutcomeStatus(
  result?: ResourceAssistantPlanResult | null,
): ResourceAssistantScheduleOutcomeStatus | null {
  if (!result) return null;
  if (result.schedule_outcome_status) return result.schedule_outcome_status;
  if (result.plan_status === "met") return "duration_target_met";
  if (result.plan_status === "not_met") return "duration_target_not_met";
  if (result.plan_status === "infeasible") return "no_feasible_schedule";
  if (result.plan_status === "unconfirmed") {
    const raw = result.result?.stats?.target_achievement;
    const target = isRecord(raw) ? raw : {};
    if (target.target_present === false) return null;
    return result.result?.tasks?.length ? "duration_target_not_met" : "no_feasible_schedule";
  }
  return null;
}

export function resourceAssistantScheduleOutcomeReason(
  result?: ResourceAssistantPlanResult | null,
): ResourceAssistantScheduleOutcomeReason | null {
  if (!result) return null;
  if (result.schedule_outcome_reason) return result.schedule_outcome_reason;
  const raw = result.result?.stats?.target_achievement;
  const target = isRecord(raw) ? raw : {};
  if (typeof target.schedule_outcome_reason === "string") {
    return target.schedule_outcome_reason as ResourceAssistantScheduleOutcomeReason;
  }
  if (result.plan_status === "met") return "target_met";
  if (result.plan_status === "not_met") return "proven_late";
  if (result.plan_status === "infeasible") return "proven_infeasible";
  if (result.plan_status === "unconfirmed") {
    if (target.target_present === false) return "target_missing";
    return result.result?.tasks?.length ? "late_unconfirmed" : "time_limit_no_schedule";
  }
  return null;
}

export function resourceAssistantMaxTargetDelayDays(result?: ResourceAssistantPlanResult | null): number {
  if (!result) return 0;
  const raw = result.result?.stats?.target_achievement;
  const target = isRecord(raw) ? raw : {};
  if (target.max_target_delay_days !== undefined && target.max_target_delay_days !== null) {
    return Math.max(0, numberValue(target.max_target_delay_days));
  }
  const hardMilestoneLateDays = (result.result?.milestone_results ?? [])
    .filter((milestone) => milestone.mode === "hard")
    .map((milestone) => Math.max(0, numberValue(milestone.lateness_days)));
  const fixedDurationOverrunDays = Math.max(0, numberValue(target.fixed_duration_overrun_days));
  if (hardMilestoneLateDays.length > 0) return Math.max(fixedDurationOverrunDays, ...hardMilestoneLateDays);
  return Math.max(fixedDurationOverrunDays, numberValue(target.hard_milestone_late_days));
}

export function resourceAssistantOutcomeDetail(result?: ResourceAssistantPlanResult | null): string {
  if (!result) return "";
  const status = resourceAssistantScheduleOutcomeStatus(result);
  const reason = resourceAssistantScheduleOutcomeReason(result);
  const maxDelay = resourceAssistantMaxTargetDelayDays(result);
  if (reason === "target_missing") return "缺少工期目标，无法评估。";
  if (status === "duration_target_met") return "当前资源已满足强制工期目标，可参与推荐。";
  if (status === "duration_target_not_met" && reason === "proven_late") {
    return `当前固定资源下最优排程最大延期 ${maxDelay} 天，不自动增加资源。`;
  }
  if (status === "duration_target_not_met") {
    return `当前排程最大延期 ${maxDelay} 天，尚未证明不存在更优排程。`;
  }
  if (status === "no_feasible_schedule" && reason === "time_limit_no_schedule") {
    return "限时内未获得可行排程，不据此判断资源一定不足。";
  }
  return result.diagnostics[0]?.message || "已证明当前资源无法形成可行排程。";
}

export function llmConfigStatusLabel(status: ResourceAssistantLlmConfigStatus): string {
  if (status.status === "configured") return `${status.provider}${status.model ? ` / ${status.model}` : ""}`;
  if (status.status === "failed") return `已回退：${status.warning || "外部模型调用失败"}`;
  return "本地回退";
}

export function metricValueDisplay(row: ResourceAssistantMetricRow, scenarioId: string): string {
  const payload = row.values[scenarioId];
  if (!payload) return "-";
  const value = payload.value;
  if (value === null || value === undefined || value === "") return unavailableDisplay(payload.not_available_reasons);
  if (row.metric_id === "schedule_outcome_status" && typeof value === "string") {
    return resourceAssistantScheduleOutcomeLabels[value as ResourceAssistantScheduleOutcomeStatus] ?? value;
  }
  if (row.metric_id === "plan_status" && typeof value === "string") {
    return resourceAssistantOutcomeLabels[value as ResourceAssistantPlanOutcomeStatus] ?? value;
  }
  if (row.metric_id === "demo_cost" && isRecord(value)) {
    return currencyDisplay(numberValue(value.total_cost));
  }
  if (row.metric_id === "transfer_penalty" && isRecord(value)) {
    return `${numberValue(value.penalty_score).toFixed(0)} 分`;
  }
  if (row.metric_id === "resource_utilization_by_type" && Array.isArray(value)) {
    const top = value
      .filter(isRecord)
      .slice(0, 3)
      .map((item) => `${resourceAssistantResourceLabel(String(item.resource_type || ""))} ${Math.round(numberValue(item.utilization_rate) * 100)}%`);
    return top.length ? top.join(" / ") : "-";
  }
  if (row.metric_id === "control_pier_release_dates" && Array.isArray(value)) {
    const top = value.filter(isRecord).slice(0, 2).map((item) => `${item.structure_name || "控制墩"} ${item.release_date || "-"}`);
    return top.length ? top.join(" / ") : unavailableDisplay(payload.not_available_reasons);
  }
  if (typeof value === "number") return `${Number.isInteger(value) ? value : value.toFixed(1)}${row.unit ? ` ${row.unit}` : ""}`;
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function planResultFor(response: ResourceAssistantBatchSolveResponse | null, scenarioId: string): ResourceAssistantPlanResult | null {
  return response?.plan_results.find((item) => item.scenario_id === scenarioId) || null;
}

export function resultByPlanId(results: ResourceAssistantPlanResult[] = []): Record<string, ResourceAssistantPlanResult> {
  return Object.fromEntries(results.map((result) => [result.scenario_id, result]));
}

export function metricsSummary(metrics?: ResourceAssistantCoreMetrics | null): string {
  if (!metrics || metrics.total_days == null) return "暂无指标";
  return `${metrics.total_days} 天 / 等待 ${metrics.average_wait_days ?? 0} 天 / ${currencyDisplay(metrics.demo_cost.total_cost)}`;
}

export function normalizePlanResourceQuantity(plan: ResourceAssistantPlan, resourceType: string, quantity: number): ResourceAssistantPlan {
  const nextQuantity = Math.max(0, Math.floor(Number.isFinite(quantity) ? quantity : 0));
  return {
    ...plan,
    generation_source: "user_adjusted",
    changed_from_standard: true,
    solve_status: "stale",
    stale_reason: "资源数量已调整，原求解结果和推荐解释需要重新计算。",
    resource_pools: plan.resource_pools.map((pool) =>
      pool.type === resourceType
        ? {
            ...pool,
            quantity: nextQuantity,
            max_quantity: Math.max(nextQuantity, pool.max_quantity ?? 0),
          }
        : pool,
    ),
  };
}

export function invalidatedAfterPlanChange(results: ResourceAssistantPlanResult[], planId: string): ResourceAssistantPlanResult[] {
  return results.filter((result) => result.scenario_id !== planId);
}

export function editableResourcePools(plan: ResourceAssistantPlan): ResourcePool[] {
  return plan.resource_pools.filter((pool) => pool.enabled && (pool.resource_mode ?? "LIMITED") === "LIMITED");
}

export function resourceAssistantResourceLabel(resourceType: string, pools: ResourcePool[] = []): string {
  return pools.find((pool) => pool.type === resourceType)?.label ?? defaultResourceTypeLabels[resourceType] ?? resourceType;
}

export function recommendationTitle(recommendation?: ResourceAssistantRecommendation | null): string {
  if (!recommendation || recommendation.recommendation_status !== "recommended" || !recommendation.recommended_scenario_id) {
    return "暂无推荐";
  }
  return `推荐 ${recommendation.recommended_scenario_id}`;
}

export function currencyDisplay(value: number): string {
  if (!Number.isFinite(value)) return "-";
  if (Math.abs(value) >= 10_000) return `${(value / 10_000).toFixed(1)} 万`;
  return `${Math.round(value)} 元`;
}

export function numberValue(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function unavailableDisplay(reasons?: string[]): string {
  return reasons?.[0] || "-";
}
