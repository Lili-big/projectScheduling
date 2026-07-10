import type {
  ResourceAssistantBatchSolveResponse,
  ResourceAssistantCoreMetrics,
  ResourceAssistantMetricRow,
  ResourceAssistantPlan,
  ResourceAssistantPlanProfile,
  ResourceAssistantPlanResult,
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
